# Quick chart maker: load CSV/JSON (pasted or file under /home/pyodide), pick columns, draw line/bar/scatter/histogram via matplotlib or text charts, optionally save PNG/TXT.
"""KPython r5 - bot2help chart maker. Stdlib only, matplotlib optional (Agg).
Run: python r5_bot2help_chart.py            (menu)
     python r5_bot2help_chart.py --selftest
"""
import csv, io, json, math, os, sys

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAVE_MPL = True
except Exception:  # pragma: no cover
    plt = None
    HAVE_MPL = False

BASE_DIR = "/home/pyodide"
CHART_TYPES = ("line", "bar", "scatter", "hist")


# ---------- paths ----------
def safe_path(path, base_dir=None):
    """Resolve path inside base_dir; raise ValueError on escape (../ or symlink)."""
    base = os.path.realpath(base_dir or BASE_DIR)
    if not path or not str(path).strip():
        raise ValueError("empty path")
    p = str(path).strip()
    full = p if os.path.isabs(p) else os.path.join(base, p)
    real = os.path.realpath(full)
    if real != base and not real.startswith(base + os.sep):
        raise ValueError("path outside %s refused" % base)
    return real


# ---------- loading ----------
def parse_data(text):
    """Parse CSV or JSON (list of objects) -> (columns, rows as list of dicts)."""
    t = (text or "").strip()
    if not t:
        raise ValueError("no data")
    if t[0] in "[{":
        try:
            data = json.loads(t)
        except json.JSONDecodeError as e:
            raise ValueError("bad JSON: %s" % e)
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
            raise ValueError("JSON must be a list of objects")
        cols = []
        for r in data:
            for k in r:
                if k not in cols:
                    cols.append(k)
        rows = [{c: r.get(c) for c in cols} for r in data]
    else:
        reader = csv.DictReader(io.StringIO(t))
        cols = [c.strip() for c in (reader.fieldnames or []) if c is not None]
        rows = []
        for r in reader:
            rows.append({c.strip(): (v.strip() if isinstance(v, str) else v)
                         for c, v in r.items() if c is not None})
    if not cols or not rows:
        raise ValueError("no rows/columns found")
    return cols, rows


def load_file(path, base_dir=None):
    real = safe_path(path, base_dir)
    if not os.path.isfile(real):
        raise ValueError("file not found: %s" % path)
    if os.path.getsize(real) > 2_000_000:  # KPython: size cap
        raise ValueError("file over 2 MB")
    with open(real, encoding="utf-8") as f:
        return parse_data(f.read())


def to_float(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(str(v).replace(",", "").strip())
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def numeric_columns(cols, rows):
    return [c for c in cols if any(to_float(r.get(c)) is not None for r in rows)]


def extract(rows, x, y=None):
    """Return (xs, ys, skipped). xs keep labels if non-numeric; ys numeric only."""
    xs, ys, skipped = [], [], 0
    for r in rows:
        xv = r.get(x)
        if y is None:
            f = to_float(xv)
            if f is None:
                skipped += 1
                continue
            xs.append(f)
            continue
        yv = to_float(r.get(y))
        if yv is None or xv in (None, ""):
            skipped += 1
            continue
        xs.append(xv)
        ys.append(yv)
    return xs, ys, skipped


def histogram(values, bins=10):
    """Return list of (lo, hi, count)."""
    if not values:
        return []
    bins = max(1, int(bins))
    lo, hi = min(values), max(values)
    if lo == hi:
        return [(lo, hi, len(values))]
    w = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        i = min(int((v - lo) / w), bins - 1)
        counts[i] += 1
    return [(lo + i * w, lo + (i + 1) * w, counts[i]) for i in range(bins)]


# ---------- text charts ----------
def _fmt(v):
    return ("%g" % v) if isinstance(v, float) else str(v)


def text_bar(labels, values, width=40):
    if not values:
        return "(no data)"
    m = max(abs(v) for v in values) or 1
    lw = min(max(len(_fmt(l)) for l in labels), 20)
    out = []
    for l, v in zip(labels, values):
        n = int(round(abs(v) / m * width))
        out.append("%s | %s %s" % (_fmt(l)[:20].ljust(lw), ("#" if v >= 0 else "-") * n, _fmt(v)))
    return "\n".join(out)


def text_line(values, width=60):
    if not values:
        return "(no data)"
    ticks = "▁▂▃▄▅▆▇█"
    if len(values) > width:  # downsample
        step = len(values) / width
        values = [values[int(i * step)] for i in range(width)]
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    spark = "".join(ticks[int((v - lo) / span * (len(ticks) - 1))] for v in values)
    return "%s\nmin %s  max %s  n=%d" % (spark, _fmt(lo), _fmt(hi), len(values))


def text_scatter(xs, ys, width=50, height=15):
    pts = [(to_float(a), b) for a, b in zip(xs, ys)]
    pts = [(a, b) for a, b in pts if a is not None]
    if not pts:
        return "(no numeric x/y points)"
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    grid = [[" "] * width for _ in range(height)]
    for a, b in pts:
        c = int((a - x0) / ((x1 - x0) or 1) * (width - 1))
        r = height - 1 - int((b - y0) / ((y1 - y0) or 1) * (height - 1))
        grid[r][c] = "*" if grid[r][c] == " " else "@"
    lines = ["%10s |%s" % (_fmt(y1) if i == 0 else (_fmt(y0) if i == height - 1 else ""), "".join(row))
             for i, row in enumerate(grid)]
    lines.append(" " * 11 + "+" + "-" * width)
    lines.append(" " * 12 + _fmt(x0) + " " * max(1, width - len(_fmt(x0)) - len(_fmt(x1))) + _fmt(x1))
    return "\n".join(lines)


def text_hist(values, bins=10, width=40):
    h = histogram(values, bins)
    if not h:
        return "(no data)"
    labels = ["%g-%g" % (round(a, 3), round(b, 3)) for a, b, _ in h]
    return text_bar(labels, [float(c) for _, _, c in h], width)


def text_chart(kind, rows, x, y=None, bins=10):
    if kind not in CHART_TYPES:
        raise ValueError("unknown chart type")
    if kind == "hist":
        vals, _, sk = extract(rows, x)
        body = text_hist(vals, bins)
    else:
        if y is None:
            raise ValueError("y column required")
        xs, ys, sk = extract(rows, x, y)
        if kind == "bar":
            body = text_bar(xs, ys)
        elif kind == "line":
            body = text_line(ys)
        else:
            body = text_scatter(xs, ys)
    title = "%s: %s" % (kind, x if kind == "hist" else "%s vs %s" % (y, x))
    note = "\n(skipped %d non-numeric/empty rows)" % sk if sk else ""
    return title + "\n" + body + note


# ---------- matplotlib ----------
def mpl_figure(kind, rows, x, y=None, bins=10):
    if not HAVE_MPL:
        raise RuntimeError("matplotlib not available")
    fig, ax = plt.subplots(figsize=(6, 4))
    if kind == "hist":
        vals, _, _ = extract(rows, x)
        if not vals:
            plt.close(fig)
            raise ValueError("no numeric values")
        ax.hist(vals, bins=max(1, int(bins)))
        ax.set_xlabel(x); ax.set_ylabel("count")
    else:
        xs, ys, _ = extract(rows, x, y)
        if not ys:
            plt.close(fig)
            raise ValueError("no numeric y values")
        nx = [to_float(v) for v in xs]
        xplot = nx if all(v is not None for v in nx) else [str(v) for v in xs]
        if kind == "line":
            ax.plot(xplot, ys, marker="o")
        elif kind == "bar":
            ax.bar([str(v) for v in xs], ys)
        else:
            ax.scatter(xplot, ys)
        ax.set_xlabel(x); ax.set_ylabel(y)
    ax.set_title(kind)
    fig.tight_layout()
    return fig


def save_output(path, writer, base_dir=None, confirm=None):
    """writer(real_path). confirm(msg)->bool asked if file exists. Returns path or None."""
    real = safe_path(path, base_dir)
    if os.path.isdir(real):
        raise ValueError("path is a directory")
    if os.path.exists(real) and not (confirm and confirm("%s exists. Overwrite? (y/n) " % real)):
        return None
    d = os.path.dirname(real)
    if not os.path.isdir(d):
        raise ValueError("folder does not exist")
    writer(real)
    return real


def save_png(fig, path, base_dir=None, confirm=None):
    if not path.lower().endswith(".png"):
        path += ".png"
    return save_output(path, lambda p: fig.savefig(p), base_dir, confirm)


def save_txt(text, path, base_dir=None, confirm=None):
    if not path.lower().endswith(".txt"):
        path += ".txt"
    def w(p):
        with open(p, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    return save_output(path, w, base_dir, confirm)


# ---------- menu ----------
def _ask(prompt):
    try:
        return input(prompt)
    except EOFError:
        return None


def read_pasted():
    print("Paste CSV or JSON; finish with a line saying END")
    lines = []
    while True:
        l = _ask("")
        if l is None or l.strip() == "END":
            break
        lines.append(l)
    return "\n".join(lines)


def _pick(prompt, options, allow_blank=False, allowed=None):
    """KPython: numbers stay the same for every list (allowed= limits which can be picked);
    names work too (any case); blank or q goes back."""
    for i, o in enumerate(options, 1):
        print("  %d) %s%s" % (i, o, "" if allowed is None or o in allowed else "  (not numeric)"))
    while True:
        a = _ask(prompt + "(blank or q = back) ")
        if a is None:
            return None
        a = a.strip()
        if a == "":
            return "" if allow_blank else None
        if a.lower() == "q":
            return None
        pick = None
        if a.isdigit() and 1 <= int(a) <= len(options):
            pick = options[int(a) - 1]
        else:
            pick = next((o for o in options if str(o).lower() == a.lower()), None)
        if pick is not None and (allowed is None or pick in allowed):
            return pick
        print("Invalid choice. Pick a number or name from the list, or blank to go back.")


def _yes(msg):
    a = _ask(msg)
    return bool(a) and a.strip().lower().startswith("y")


def main(base_dir=None, force_text=False):
    use_mpl = HAVE_MPL and not force_text
    cols, rows = None, None
    print("Chart maker (%s mode)" % ("matplotlib" if use_mpl else "text"))
    while True:
        print("\n1) Paste data  2) Load file  3) Columns  4) Make chart  q) Quit")
        c = _ask("> ")
        if c is None or c.strip().lower() in ("q", "quit"):
            print("Bye.")
            return 0
        c = c.strip()
        try:
            if c == "1":
                cols, rows = parse_data(read_pasted())
                print("Loaded %d rows, columns: %s" % (len(rows), ", ".join(cols)))
            elif c == "2":
                p = _ask("Path under %s: " % (base_dir or BASE_DIR)) or ""
                cols, rows = load_file(p, base_dir)
                print("Loaded %d rows, columns: %s" % (len(rows), ", ".join(cols)))
            elif c == "3":
                if not cols:
                    print("Load data first."); continue
                num = numeric_columns(cols, rows)
                for col in cols:
                    print("  %s%s" % (col, " (numeric)" if col in num else ""))
            elif c == "4":
                if not cols:
                    print("Load data first."); continue
                kind = _pick("Chart type: ", list(CHART_TYPES))
                if kind is None:
                    continue
                num = numeric_columns(cols, rows)
                y, bins = None, 10
                if kind == "hist":
                    if not num:
                        print("No numeric columns."); continue
                    x = _pick("Column: ", cols, allowed=num)
                    b = (_ask("Bins [10]: ") or "").strip()
                    bins = int(b) if b.isdigit() and int(b) > 0 else 10
                else:
                    x = _pick("X column: ", cols)
                    if not num:
                        print("No numeric columns for Y."); continue
                    y = _pick("Y column: ", cols, allowed=num)
                if x is None or (kind != "hist" and y is None):
                    continue
                text = text_chart(kind, rows, x, y, bins)
                print(text)
                if use_mpl:
                    fig = mpl_figure(kind, rows, x, y, bins)
                    if _yes("Save PNG? (y/n) "):
                        p = _ask("PNG path under %s: " % (base_dir or BASE_DIR)) or ""
                        r = save_png(fig, p, base_dir, _yes)
                        print("Saved %s" % r if r else "Not saved.")
                    plt.close(fig)
                elif _yes("Save text chart as .txt? (y/n) "):
                    p = _ask("TXT path under %s: " % (base_dir or BASE_DIR)) or ""
                    r = save_txt(text, p, base_dir, _yes)
                    print("Saved %s" % r if r else "Not saved.")
            else:
                print("Unknown option.")
        except (ValueError, RuntimeError, OSError) as e:
            print("Error: %s" % e)


# ---------- self-tests ----------
def run_selftests(verbose=True):
    import tempfile
    passed = failed = 0

    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print("FAIL:", name)

    def raises(fn):
        try:
            fn()
        except (ValueError, RuntimeError):
            return True
        return False

    csv_t = "month,sales,note\nJan,10,a\nFeb,20,b\nMar,x,c\nApr,5,d\n"
    cols, rows = parse_data(csv_t)
    check("csv cols", cols == ["month", "sales", "note"] and len(rows) == 4)
    jc, jr = parse_data('[{"a":1,"b":2},{"a":3,"c":"z"}]')
    check("json cols", jc == ["a", "b", "c"] and jr[1]["b"] is None)
    check("empty", raises(lambda: parse_data("  ")))
    check("bad json", raises(lambda: parse_data("[1,2")))
    check("json not objects", raises(lambda: parse_data("[1,2]")))
    check("numeric cols", numeric_columns(cols, rows) == ["sales"])
    xs, ys, sk = extract(rows, "month", "sales")
    check("extract skip", ys == [10, 20, 5] and sk == 1)
    check("to_float", to_float("1,000") == 1000 and to_float("nan") is None and to_float(True) is None)
    h = histogram([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5)
    check("hist", len(h) == 5 and sum(c for _, _, c in h) == 10)
    check("hist const", histogram([3, 3], 4) == [(3, 3, 2)])
    for k in CHART_TYPES:
        t = text_chart(k, rows, "sales" if k == "hist" else "month", None if k == "hist" else "sales", 3)
        check("text " + k, t.startswith(k))
    check("text bar skip note", "skipped 1" in text_chart("bar", rows, "month", "sales"))
    check("scatter non-numeric x", "no numeric" in text_scatter(["a"], [1.0]))
    check("bad kind", raises(lambda: text_chart("pie", rows, "month", "sales")))
    check("text empty", text_bar([], []) == "(no data)" and text_line([]) == "(no data)")

    with tempfile.TemporaryDirectory(dir="/home/pyodide" if os.path.isdir("/home/pyodide") else None) as tmp, tempfile.TemporaryDirectory() as outside:
        base = os.path.realpath(tmp)
        with open(os.path.join(base, "d.csv"), "w") as f:
            f.write(csv_t)
        check("load file", load_file("d.csv", base)[0] == cols)
        check("dotdot refused", raises(lambda: safe_path("../etc/passwd", base)))
        check("abs outside refused", raises(lambda: safe_path("/etc/passwd", base)))
        with open(os.path.join(outside, "s.csv"), "w") as f:
            f.write(csv_t)
        try:
            os.symlink(outside, os.path.join(base, "link"))
            check("symlink refused", raises(lambda: load_file("link/s.csv", base)))
        except (OSError, NotImplementedError):
            pass
        check("missing file", raises(lambda: load_file("nope.csv", base)))
        txt = text_chart("bar", rows, "month", "sales")
        check("save txt", save_txt(txt, "c", base) == os.path.join(base, "c.txt"))
        check("no overwrite", save_txt("x", "c.txt", base, lambda m: False) is None)
        check("kept", open(os.path.join(base, "c.txt")).read().startswith("bar"))
        check("overwrite yes", save_txt("new", "c.txt", base, lambda m: True) is not None
              and open(os.path.join(base, "c.txt")).read() == "new\n")
        check("save outside refused", raises(lambda: save_txt("x", "../x.txt", base)))
        if HAVE_MPL:
            for k in CHART_TYPES:
                fig = mpl_figure(k, rows, "sales" if k == "hist" else "month",
                                 None if k == "hist" else "sales", 4)
                p = save_png(fig, "chart_" + k, base)
                plt.close(fig)
                check("png " + k, p and os.path.getsize(p) > 0)
            fig = mpl_figure("line", rows, "month", "sales")
            check("png no overwrite", save_png(fig, "chart_line.png", base, lambda m: False) is None)
            plt.close(fig)
            check("mpl no data", raises(lambda: mpl_figure("hist", rows, "note")))
        # forced-text menu run via fake stdin
        old_in, old_out = sys.stdin, sys.stdout
        sys.stdin = io.StringIO("2\nd.csv\n4\nbar\n1\n2\ny\nmenu_out\nq\n")
        sys.stdout = io.StringIO()
        import builtins as _kpb
        _kp_in = _kpb.input
        _kpb.input = lambda p="": (sys.stdin.readline() or "q").rstrip("\n")  # KPython: app input() ignores sys.stdin
        try:
            main(base_dir=base, force_text=True)
            out = sys.stdout.getvalue()
        finally:
            sys.stdin, sys.stdout = old_in, old_out
            _kpb.input = _kp_in
        check("menu text mode", "text mode" in out and os.path.exists(os.path.join(base, "menu_out.txt")))
    if verbose:
        print("Self-tests: %d passed, %d failed (matplotlib %s)" %
              (passed, failed, "available" if HAVE_MPL else "not available"))
    return failed == 0


# --- KPython v5: size caps on text inputs (Drop's review) ---
_KP_MAX = 500_000
def _kp_cap(fn):
    def w(*a, **k):
        for x in list(a) + list(k.values()):
            if isinstance(x, str) and len(x) > _KP_MAX: raise ValueError("input too big (max 500 KB)")
        return fn(*a, **k)
    w.__wrapped__ = fn; return w
for _n in ("format_code", "analyze", "check", "report", "pretty", "minify", "validate", "gen_dataclasses", "b64dec", "hexdec", "run_tests", "generate", "to_html", "cover", "profile_source", "scan_text", "convert", "parse", "explain", "gen_tests", "scan_code", "to_fstrings", "extract", "inline", "check"):
    if callable(globals().get(_n)) and not isinstance(globals()[_n], type): globals()[_n] = _kp_cap(globals()[_n])
if "Debugger" in globals():
    _kp_dinit = Debugger.__init__
    def _kp_dinit2(self, source, *a, **k):
        if len(source) > _KP_MAX: raise ValueError("code too big to debug (max 500 KB)")
        _kp_dinit(self, source, *a, **k)
    Debugger.__init__ = _kp_dinit2

# --- KPython v5 security wrapper: every path also goes through the app's shared kp_safe_path (/home/pyodide only) ---
import builtins as _kp_b
def _kp_wrap(fn):
    def w(*a, **k):
        r = fn(*a, **k)
        return _kp_b.kp_safe_path(r) if hasattr(_kp_b, "kp_safe_path") and isinstance(r, str) and r.startswith("/") and all(globals().get(v, "/home/pyodide") == "/home/pyodide" for v in ("BASE", "BASE_DIR", "SAFE_ROOT")) else r
    return w
for _n in ("safe_path", "_safe_path", "_safe"):
    if callable(globals().get(_n)): globals()[_n] = _kp_wrap(globals()[_n])

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(0 if run_selftests() else 1)
    main(force_text="--text" in sys.argv)
