# Drop's Diff & Patch: compare two code snippets or files (unified or phone-width side-by-side diff) and apply unified patches safely inside /home/pyodide.
import difflib, os, re

BASE_DIR = "/home/pyodide"   # all file access is confined here
MAX_CHARS = 200_000          # input size cap
MAX_LINES = 5000
COL = 35                     # side-by-side column width


def safe_path(p):
    """Return the real path if it's inside BASE_DIR, else raise ValueError."""
    p = (p or "").strip()
    if not p or "\x00" in p:
        raise ValueError("empty or invalid path")
    base = os.path.realpath(BASE_DIR)
    if p == "~" or p.startswith("~/"):
        p = p[2:] or "."
    full = os.path.realpath(os.path.join(base, p))
    if full != base and not full.startswith(base + os.sep):
        raise ValueError(f"refused: {p} is outside {BASE_DIR}")
    return full


def read_file(p):
    full = safe_path(p)
    if not os.path.isfile(full):
        raise ValueError(f"not a file: {p}")
    if os.path.getsize(full) > MAX_CHARS:
        raise ValueError(f"file too big (max {MAX_CHARS:,} bytes)")
    with open(full, encoding="utf-8", errors="replace") as f:
        return f.read()


def write_file(p, text):
    full = safe_path(p)
    if os.path.isdir(full):
        raise ValueError("that's a folder")
    if os.path.exists(full) and input(f"{p} exists. Overwrite? y/n: ").strip().lower() != "y":
        print("Not saved.")
        return
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(text)
    print("Saved", full)


def paste(label):
    print(f"Paste {label}. End with a line containing only END:")
    lines, size = [], 0
    while True:
        l = input()
        if l == "END":
            break
        size += len(l) + 1
        if size > MAX_CHARS or len(lines) >= MAX_LINES:
            raise ValueError(f"too much input (max {MAX_LINES} lines / {MAX_CHARS:,} chars)")
        lines.append(l)
    return "\n".join(lines) + ("\n" if lines else "")


def get_text(label):
    src = input(f"{label}: (p)aste or (f)ile? ").strip().lower()
    if src == "f":
        return read_file(input("File path (inside ~): "))
    return paste(label)


def unified(a, b, na="a", nb="b"):
    return "\n".join(difflib.unified_diff(a.splitlines(), b.splitlines(), na, nb, lineterm=""))


def side_by_side(a, b):
    al, bl = a.splitlines(), b.splitlines()
    cut = lambda s: (s[:COL - 1] + "…") if len(s) > COL else s
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, al, bl).get_opcodes():
        for k in range(max(i2 - i1, j2 - j1)):
            i, j = i1 + k, j1 + k
            l = f"{i+1:>4} {cut(al[i]):<{COL}}" if i < i2 else " " * (COL + 5)
            r = f"{j+1:>4} {cut(bl[j])}" if j < j2 else ""
            mark = {"equal": " ", "replace": "|", "delete": "<", "insert": ">"}[tag]
            out.append(f"{l} {mark} {r}".rstrip())
    return "\n".join(out)


HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def apply_patch(text, patch):
    """Apply a unified diff to text. Raises ValueError with a clear message on mismatch."""
    src = text.splitlines()
    out, pos = [], 0  # pos = index into src of next unconsumed line
    plines = patch.splitlines()
    i, hunks = 0, 0
    while i < len(plines):
        m = HUNK.match(plines[i])
        if not m:
            i += 1
            continue
        hunks += 1
        old_start, old_len = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
        new_len = int(m.group(4) if m.group(4) is not None else 1)
        start = old_start - 1 if old_len else old_start  # empty hunk inserts after that line
        if start < pos or start > len(src):
            raise ValueError(f"hunk {hunks}: starts at line {old_start}, which is out of order or past end of file")
        out.extend(src[pos:start])
        pos = start
        i += 1
        seen_old = seen_new = 0
        while i < len(plines) and (seen_old < old_len or seen_new < new_len):
            l = plines[i]
            if l.startswith("\\"):
                i += 1
                continue
            op, body = (l[:1] or " "), l[1:]
            if op in " -":
                if pos >= len(src) or src[pos] != body:
                    got = src[pos] if pos < len(src) else "<end of file>"
                    raise ValueError(f"hunk {hunks}: line {pos+1} doesn't match.\n  patch expects: {body!r}\n  file has:      {got!r}")
                if op == " ":
                    out.append(body)
                    seen_new += 1
                pos += 1
                seen_old += 1
            elif op == "+":
                out.append(body)
                seen_new += 1
            else:
                raise ValueError(f"hunk {hunks}: bad patch line {l!r}")
            i += 1
        if seen_old != old_len or seen_new != new_len:
            raise ValueError(f"hunk {hunks}: patch is truncated or line counts are wrong")
    if not hunks:
        raise ValueError("no hunks found (need lines starting with @@)")
    out.extend(src[pos:])
    return "\n".join(out) + ("\n" if out else "")


def main():
    print("=== Diff & Patch ===  (files must be inside ~ = " + BASE_DIR + ")")
    last = None
    while True:
        c = input("\n1 Unified diff  2 Side-by-side  3 Apply patch  4 Save last result  q Quit: ").strip().lower()
        try:
            if c in ("q", "quit", "exit"):
                break
            elif c in ("1", "2"):
                a, b = get_text("OLD"), get_text("NEW")
                res = unified(a, b) if c == "1" else side_by_side(a, b)
                print(res or "(no differences)")
                last = res
            elif c == "3":
                text = get_text("ORIGINAL")
                patch = get_text("PATCH")
                last = apply_patch(text, patch)
                print("Patch applied OK. Result:\n" + last)
            elif c == "4":
                if last is None:
                    print("Nothing to save yet.")
                else:
                    write_file(input("Save to (inside ~): "), last)
            else:
                print("Pick 1, 2, 3, 4 or q.")
        except (ValueError, OSError, UnicodeError) as e:
            print("Error:", e)


if __name__ == "__main__":
    main()
