# Data viewer: load CSV/JSON (paste or file), paginated table, column types & stats, filter/sort, CSV<->JSON convert. Stdlib only.
import csv, io, json, os

DEFAULT_DIR = "/home/pyodide"

def base_dir():
    return DEFAULT_DIR if os.path.isdir(DEFAULT_DIR) else os.getcwd()

def resolve_path(p):
    p = p.strip()
    full = os.path.realpath(os.path.join(DEFAULT_DIR, p))
    if full != DEFAULT_DIR and not full.startswith(DEFAULT_DIR + os.sep):
        raise ValueError(f"refused: {p} is outside {DEFAULT_DIR}")
    return full

def parse_csv(text):
    rows = list(csv.DictReader(io.StringIO(text.strip())))
    return [{k: ("" if v is None else v) for k, v in r.items() if k is not None} for r in rows]

def parse_json(text):
    data = json.loads(text)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
        raise ValueError("JSON must be a list of objects")
    return data

def parse_auto(text):
    t = text.strip()
    if t[:1] in "[{":
        return parse_json(t)
    return parse_csv(t)

def columns(rows):
    cols = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    return cols

def to_number(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = v.strip()
        try:
            return int(s)
        except ValueError:
            try:
                f = float(s)
                return f if f == f else None
            except ValueError:
                return None
    return None

def value_type(v):
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return "empty"
    if isinstance(v, bool) or (isinstance(v, str) and v.strip().lower() in ("true", "false")):
        return "bool"
    n = to_number(v)
    if isinstance(n, int):
        return "int"
    if isinstance(n, float):
        return "float"
    return "str"

def infer_type(values):
    ts = {value_type(v) for v in values} - {"empty"}
    if not ts:
        return "empty"
    if len(ts) == 1:
        return ts.pop()
    if ts == {"int", "float"}:
        return "float"
    return "str"

def column_stats(rows, col):
    vals = [r.get(col) for r in rows]
    ne = [v for v in vals if value_type(v) != "empty"]
    t = infer_type(vals)
    st = {"column": col, "type": t, "count": len(vals), "non_empty": len(ne),
          "unique": len({json.dumps(v, sort_keys=True, default=str) for v in ne}),
          "min": None, "max": None, "mean": None}
    if t in ("int", "float"):
        nums = [to_number(v) for v in ne]
        st["min"], st["max"], st["mean"] = min(nums), max(nums), sum(nums) / len(nums)
    elif ne:
        ss = [cell_str(v) for v in ne]
        st["min"], st["max"] = min(ss), max(ss)
    return st

def all_stats(rows):
    return [column_stats(rows, c) for c in columns(rows)]

def cell_str(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return str(v)

OPS = ["==", "!=", ">", "<", ">=", "<=", "contains"]

def match(v, op, target):
    if op == "contains":
        return target.lower() in cell_str(v).lower()
    a, b = to_number(v), to_number(target)
    if a is None or b is None:
        a, b = cell_str(v), target
    try:
        return {"==": a == b, "!=": a != b, ">": a > b, "<": a < b,
                ">=": a >= b, "<=": a <= b}[op]
    except TypeError:
        return False

def filter_rows(rows, col, op, target):
    if op not in OPS:
        raise ValueError("bad operator: %s" % op)
    return [r for r in rows if match(r.get(col), op, str(target))]

def sort_rows(rows, col, desc=False):
    def key(r):
        v = r.get(col)
        if value_type(v) == "empty":
            return (2, 0, "")
        n = to_number(v)
        return (0, n, "") if n is not None else (1, 0, cell_str(v).lower())
    full = [r for r in rows if value_type(r.get(col)) != "empty"]
    empty = [r for r in rows if value_type(r.get(col)) == "empty"]
    nums = [r for r in full if to_number(r.get(col)) is not None]
    strs = [r for r in full if to_number(r.get(col)) is None]
    return sorted(nums, key=key, reverse=desc) + sorted(strs, key=key, reverse=desc) + empty

def truncate(s, w):
    s = s.replace("\n", " ")
    return s if len(s) <= w else s[:max(w - 1, 0)] + "~"

def format_table(rows, cols=None, start=0, size=10, max_width=16):
    cols = cols or columns(rows)
    page = rows[start:start + size]
    if not cols:
        return "(no data)"
    cells = [[truncate(cell_str(r.get(c)), max_width) for c in cols] for r in page]
    hdr = [truncate(str(c), max_width) for c in cols]
    w = [max([len(hdr[i])] + [len(row[i]) for row in cells]) for i in range(len(cols))]
    line = lambda xs: " | ".join(x.ljust(w[i]) for i, x in enumerate(xs))
    out = [line(hdr), "-+-".join("-" * x for x in w)] + [line(r) for r in cells]
    return "\n".join(out)

def rows_to_csv(rows):
    buf = io.StringIO()
    cols = columns(rows)
    wr = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    wr.writeheader()
    for r in rows:
        wr.writerow({c: cell_str(r.get(c)) for c in cols})
    return buf.getvalue()

def convert_value(v):
    t = value_type(v)
    if t == "empty":
        return None
    if t == "bool":
        return v if isinstance(v, bool) else v.strip().lower() == "true"
    if t in ("int", "float"):
        return to_number(v)
    return v

def rows_to_json(rows, typed=True, indent=2):
    data = [{k: (convert_value(v) if typed else v) for k, v in r.items()} for r in rows]
    return json.dumps(data, indent=indent)

def csv_to_json(text, typed=True):
    return rows_to_json(parse_csv(text), typed)

def json_to_csv(text):
    return rows_to_csv(parse_json(text))

# ---------- interactive ----------
class Quit(Exception):
    pass

def ask(prompt):
    try:
        return input(prompt)
    except EOFError:
        raise Quit()

def read_paste():
    print("Paste data; finish with a line containing only END:")
    lines = []
    while True:
        try:
            l = input()
        except EOFError:
            break
        if l.strip() == "END":
            break
        lines.append(l)
    return "\n".join(lines)

def load_menu():
    src = ask("Load from (p)aste or (f)ile? ").strip().lower()
    if src.startswith("f"):
        print("Base dir:", base_dir())
        path = resolve_path(ask("File path: "))
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if path.lower().endswith(".json"):
            return parse_json(text)
        if path.lower().endswith(".csv"):
            return parse_csv(text)
        return parse_auto(text)
    text = read_paste()
    if not text.strip():
        raise ValueError("nothing pasted")
    return parse_auto(text)

def output(text):
    dest = ask("(p)rint or (s)ave to file? ").strip().lower()
    if dest.startswith("s"):
        path = resolve_path(ask("Save as: "))
        if os.path.exists(path) and ask(f"{path} exists. Overwrite? type yes: ").strip().lower() != "yes":
            return print("Not saved.")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print("Saved to", path)
    else:
        print(text)

def view(rows):
    size, start = 10, 0
    while True:
        print(format_table(rows, start=start, size=size))
        total = len(rows)
        print("Rows %d-%d of %d" % (min(start + 1, total), min(start + size, total), total))
        c = ask("(n)ext (p)rev (q)back: ").strip().lower()
        if c == "n" and start + size < total:
            start += size
        elif c == "p":
            start = max(0, start - size)
        elif c in ("q", ""):
            return

def pick_col(rows):
    cols = columns(rows)
    for i, c in enumerate(cols, 1):
        print(" %d. %s" % (i, c))
    s = ask("Column (number or name): ").strip()
    if s.isdigit() and 1 <= int(s) <= len(cols):
        return cols[int(s) - 1]
    if s in cols:
        return s
    raise ValueError("unknown column")

MENU = """
== Data Viewer ==
1 Load  2 View  3 Types/Stats  4 Filter  5 Sort  6 Reset
7 Export CSV  8 Export JSON  9 Convert pasted/file CSV<->JSON  0 Quit"""

def main():
    orig, rows = [], []
    while True:
        try:
            print(MENU)
            print("(%d rows loaded, %d shown)" % (len(orig), len(rows)))
            c = ask("> ").strip()
            if c == "0" or c.lower() in ("q", "quit"):
                break
            if c == "1":
                orig = load_menu(); rows = list(orig)
                print("Loaded %d rows, columns: %s" % (len(rows), ", ".join(columns(rows))))
            elif c in "2345678" and c and not orig:
                print("Load data first.")
            elif c == "2":
                view(rows)
            elif c == "3":
                for s in all_stats(rows):
                    mean = "" if s["mean"] is None else " mean=%.4g" % s["mean"]
                    print("%s [%s] count=%d non_empty=%d unique=%d min=%s max=%s%s" % (
                        s["column"], s["type"], s["count"], s["non_empty"], s["unique"],
                        truncate(cell_str(s["min"]), 20), truncate(cell_str(s["max"]), 20), mean))
            elif c == "4":
                col = pick_col(rows)
                op = ask("Operator %s: " % " ".join(OPS)).strip()
                rows = filter_rows(rows, col, op, ask("Value: "))
                print("%d rows match." % len(rows))
            elif c == "5":
                col = pick_col(rows)
                rows = sort_rows(rows, col, ask("(a)sc or (d)esc? ").strip().lower().startswith("d"))
                print("Sorted.")
            elif c == "6":
                rows = list(orig); print("Reset.")
            elif c == "7":
                output(rows_to_csv(rows))
            elif c == "8":
                output(rows_to_json(rows))
            elif c == "9":
                d = ask("(1) CSV->JSON or (2) JSON->CSV? ").strip()
                src = ask("Source (p)aste or (f)ile? ").strip().lower()
                if src.startswith("f"):
                    with open(resolve_path(ask("File path: ")), encoding="utf-8") as f:
                        text = f.read()
                else:
                    text = read_paste()
                output(csv_to_json(text) if d == "1" else json_to_csv(text))
            else:
                print("Unknown choice.")
        except Quit:
            break
        except KeyboardInterrupt:
            break
        except Exception as e:
            print("Error:", e)
    print("Bye.")

if __name__ == "__main__":
    main()
