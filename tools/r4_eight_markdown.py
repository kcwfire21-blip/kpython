# Safe Markdown-to-HTML previewer: headings, lists, code blocks, links, tables, bold/italic/inline code; all raw HTML is escaped.
"""Stdlib-only Markdown renderer for KPython. to_html(md) returns escaped, script-free HTML."""
import html
import os
import re

SAFE_ROOT = "/home/pyodide"
MAX_BYTES = 500 * 1024
SAFE_SCHEMES = ("http://", "https://", "mailto:", "#", "/")


def _safe_url(url):
    u = url.strip()
    low = re.sub(r"[\x00-\x20]", "", html.unescape(u)).lower()
    if low.startswith(SAFE_SCHEMES) or not re.match(r"^[a-z][a-z0-9+.-]*:", low):
        return html.escape(u, quote=True)
    return "#"


def _inline(text):
    """Render inline markdown on already-raw text; escapes everything first."""
    codes = []

    def keep_code(m):
        codes.append("<code>" + html.escape(m.group(1)) + "</code>")
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", keep_code, text)
    text = html.escape(text, quote=True)
    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)",
                  lambda m: f'<img alt="{m.group(1)}" src="{_safe_url(html.unescape(m.group(2)))}">', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
                  lambda m: f'<a href="{_safe_url(html.unescape(m.group(2)))}" rel="noopener noreferrer">{m.group(1)}</a>', text)
    text = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*|(?<![\w.])__(?=\S)(.+?)(?<=\S)__(?![\w_])", lambda m: f"<strong>{m.group(1) or m.group(2)}</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<em>\1</em>", text)
    text = re.sub(r"~~(.+?)~~", r"<del>\1</del>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


def _row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def to_html(md):
    """Convert Markdown text to safe HTML text."""
    if len(md.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Input over 500KB.")
    lines = md.replace("\r\n", "\n").split("\n")
    out, para, i = [], [], 0

    def flush():
        if para:
            out.append("<p>" + "<br>".join(_inline(p) for p in para) + "</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        fence = re.match(r"^(```|~~~)\s*([\w+-]*)", s)
        if fence:
            flush()
            lang = fence.group(2)
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith(fence.group(1)):
                code.append(lines[i])
                i += 1
            cls = f' class="language-{html.escape(lang)}"' if lang else ""
            out.append(f"<pre><code{cls}>" + html.escape("\n".join(code)) + "</code></pre>")
            i += 1
            continue
        if not s:
            flush()
            i += 1
            continue
        h = re.match(r"^(#{1,6})\s+(.*?)\s*#*$", s)
        if h:
            flush()
            n = len(h.group(1))
            out.append(f"<h{n}>{_inline(h.group(2))}</h{n}>")
            i += 1
            continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            flush()
            out.append("<hr>")
            i += 1
            continue
        if s.startswith(">"):
            flush()
            q = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                q.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>" + to_html("\n".join(q)) + "</blockquote>")
            continue
        if "|" in s and i + 1 < len(lines) and re.match(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?$", lines[i + 1].strip()):
            flush()
            aligns = []
            for c in _row(lines[i + 1]):
                aligns.append("center" if c.startswith(":") and c.endswith(":") else
                              "right" if c.endswith(":") else "left" if c.startswith(":") else "")
            head = _row(line)

            def cell(tag, txt, k):
                a = aligns[k] if k < len(aligns) and aligns[k] else ""
                st = f' style="text-align:{a}"' if a else ""
                return f"<{tag}{st}>{_inline(txt)}</{tag}>"

            t = ["<table>", "<thead><tr>" + "".join(cell("th", c, k) for k, c in enumerate(head)) + "</tr></thead>", "<tbody>"]
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                cells = _row(lines[i])
                cells += [""] * (len(head) - len(cells))
                t.append("<tr>" + "".join(cell("td", c, k) for k, c in enumerate(cells[:len(head)])) + "</tr>")
                i += 1
            out.append("\n".join(t + ["</tbody>", "</table>"]))
            continue
        lm = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)", line)
        if lm:
            flush()
            ordered = lm.group(2)[0].isdigit()
            tag = "ol" if ordered else "ul"
            items = []
            while i < len(lines):
                m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)", lines[i])
                if not m or m.group(2)[0].isdigit() != ordered:
                    break
                txt = m.group(3)
                tm = re.match(r"^\[([ xX])\]\s+(.*)", txt)
                if tm:
                    chk = " checked" if tm.group(1).lower() == "x" else ""
                    items.append(f'<li><input type="checkbox" disabled{chk}> {_inline(tm.group(2))}</li>')
                else:
                    items.append(f"<li>{_inline(txt)}</li>")
                i += 1
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        para.append(s)
        i += 1
    flush()
    return "\n".join(out)


def _safe_path(path):
    full = os.path.realpath(os.path.join(SAFE_ROOT, path))
    if not (full == SAFE_ROOT or full.startswith(SAFE_ROOT + os.sep)):
        raise ValueError(f"Only files under {SAFE_ROOT} are allowed.")
    return full


def convert_file(src, dest=None):
    """Convert a .md file under /home/pyodide; optionally write .html after confirming overwrite."""
    full = _safe_path(src)
    if os.path.getsize(full) > MAX_BYTES:
        raise ValueError("File over 500KB.")
    with open(full, encoding="utf-8") as f:
        result = to_html(f.read())
    if dest:
        out = _safe_path(dest)
        if os.path.exists(out) and input(f"{out} exists. Overwrite? (y/N): ").strip().lower() not in ("y", "yes"):
            print("Not saved.")
            return result
        with open(out, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"Saved {out}")
    return result


def _self_test():
    r = to_html("# Hi <b>\n\nSome **bold** and *it* and `x<y`.")
    assert "<h1>Hi &lt;b&gt;</h1>" in r and "<strong>bold</strong>" in r and "<em>it</em>" in r
    assert "<code>x&lt;y</code>" in r, r
    bad = to_html("<script>alert(1)</script>\n\n[x](javascript:alert(1)) [y]( JaVaScRiPt:1) [z](data:text/html,hi)\n\n![i](javascript:1)")
    assert "<script" not in bad and not re.search(r'(href|src)="[^"]*(javascript|data):', bad, re.I), bad
    assert 'href="https://a.com?a=1&amp;b=2"' in to_html("[a](https://a.com?a=1&b=2)")
    assert '"><' not in to_html('[a](https://x.com"onmouseover="1)')
    c = to_html("```py\n<div>\n```")
    assert '<pre><code class="language-py">&lt;div&gt;</code></pre>' == c, c
    l = to_html("- a\n- [x] b\n\n1. one\n2. two")
    assert "<ul><li>a</li><li><input type=\"checkbox\" disabled checked> b</li></ul>" in l and "<ol><li>one</li><li>two</li></ol>" in l, l
    t = to_html("| A | B |\n|:--|--:|\n| 1 | <i> |")
    assert '<th style="text-align:left">A</th>' in t and '<td style="text-align:right">&lt;i&gt;</td>' in t, t
    assert "<blockquote><p>q</p></blockquote>" in to_html("> q")
    try:
        to_html("a" * (MAX_BYTES + 1))
        raise AssertionError("size limit")
    except ValueError:
        pass
    try:
        _safe_path("../etc/passwd")
        raise AssertionError("path escape")
    except ValueError:
        pass
    print("Self-tests passed.")


def main():
    """Run self-tests, then preview pasted Markdown or a file under /home/pyodide."""
    _self_test()
    choice = input(f"\n.md file under {SAFE_ROOT} (or Enter to paste Markdown): ").strip()
    try:
        if choice:
            dest = input("Save HTML to (path under /home/pyodide, or Enter to just print): ").strip()
            print(convert_file(choice, dest or None))
            return
        print("Paste Markdown, then a line with just END:")
        buf = []
        while True:
            try:
                ln = input()
            except (EOFError, KeyboardInterrupt):
                break
            if ln == "END":
                break
            buf.append(ln)
        print(to_html("\n".join(buf)))
    except (OSError, ValueError) as e:
        print(f"Error: {e}")


# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()
