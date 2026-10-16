# SQLite playground: open/create a database in /home/pyodide, run SQL, view aligned tables, inspect schema, import/export CSV, load sample data.
import sqlite3, csv, os

HOME = "/home/pyodide"  # KPython: fixed base, no env override

def safe_path(name, ext):
    """Keep every file inside HOME; strip directories and '..'."""
    name = os.path.basename(name.strip()) or "playground"
    if not name.endswith(ext):
        name += ext
    os.makedirs(HOME, exist_ok=True)
    full = os.path.realpath(os.path.join(HOME, name))
    if not full.startswith(HOME + os.sep): raise ValueError("refused: outside " + HOME)
    return full

def show(cur, limit=200):
    if cur.description is None:
        print(f"OK ({cur.rowcount} row(s) affected)" if cur.rowcount >= 0 else "OK")
        return
    cols = [d[0] for d in cur.description]
    rows = cur.fetchmany(limit + 1)
    more = len(rows) > limit
    rows = [["NULL" if v is None else str(v) for v in r] for r in rows[:limit]]
    w = [min(30, max([len(c)] + [len(r[i]) for r in rows])) for i, c in enumerate(cols)]
    fmt = lambda vals: " | ".join(v[:30].ljust(w[i]) for i, v in enumerate(vals))
    print(fmt(cols)); print("-+-".join("-" * x for x in w))
    for r in rows: print(fmt(r))
    print(f"({len(rows)} row(s){', more not shown' if more else ''})")

def sample(con):
    con.executescript("""
    DROP TABLE IF EXISTS jobs;
    CREATE TABLE jobs(id INTEGER PRIMARY KEY, company TEXT, role TEXT, pay REAL, city TEXT);
    INSERT INTO jobs(company, role, pay, city) VALUES
      ('Acme Logistics','Order Selector',19.75,'Hazelwood'),
      ('North Freight','Forklift Operator',22.50,'St. Louis'),
      ('Gateway Supply','Picker/Packer',18.00,'Florissant'),
      ('River Parts','Shipping Clerk',20.25,'Bridgeton');""")
    con.commit(); print("Loaded sample table 'jobs'. Try: SELECT * FROM jobs ORDER BY pay DESC;")

def tables(con):
    for (n,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        cnt = con.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]
        print(f"{n} ({cnt} rows)")

def schema(con, t):
    row = con.execute("SELECT sql FROM sqlite_master WHERE name=?", (t,)).fetchone()
    print(row[0] if row else "No such table.")

def export_csv(con, t, fname):
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone():
        return print("No such table.")
    p = safe_path(fname or t, ".csv")
    if os.path.exists(p) and input(f"{p} exists. Overwrite? type yes: ").strip().lower() != "yes": return print("Export cancelled.")
    cur = con.execute(f'SELECT * FROM "{t}"')
    with open(p, "w", newline="") as f:
        wr = csv.writer(f); wr.writerow([d[0] for d in cur.description]); wr.writerows(cur)
    print("Exported to", p)

def import_csv(con, fname, t):
    p = safe_path(fname, ".csv")
    if not os.path.exists(p): return print("Not found:", p)
    if os.path.getsize(p) > 5_000_000: return print("CSV too big (max 5 MB).")
    with open(p, newline="") as f:
        rd = csv.reader(f); head = next(rd, None)
        if not head: return print("Empty CSV.")
        t = t or os.path.splitext(os.path.basename(p))[0]
        q = lambda s: '"' + s.replace('"', '""') + '"'
        con.execute(f"CREATE TABLE IF NOT EXISTS {q(t)} ({', '.join(q(h) for h in head)})")
        rows = [r for r in rd if len(r) == len(head)]
        con.executemany(f"INSERT INTO {q(t)} VALUES ({','.join('?'*len(head))})", rows)
    con.commit(); print(f"Imported {len(rows)} row(s) into {t}")

HELP = """Commands (anything else runs as SQL; end multi-line SQL with ';'):
  .tables            list tables        .schema <table>   show CREATE statement
  .sample            load sample data   .open <name>      open/create db in /home/pyodide
  .export <table> [file]   save table to CSV
  .import <file> [table]   load CSV (first row = headers)
  .help  .quit"""

def _kp_auth(action, *a):
    # KPython: block ATTACH/DETACH so SQL cannot open files outside /home/pyodide
    return sqlite3.SQLITE_DENY if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH) else sqlite3.SQLITE_OK

def main():
    path = safe_path("playground", ".db"); con = sqlite3.connect(path); con.set_authorizer(_kp_auth)
    print("SQLite playground. DB:", path); print(HELP)
    buf = ""
    while True:
        try: line = input("...> " if buf else "sql> ")
        except EOFError: break
        s = line.strip()
        if not buf and s.startswith("."):
            p = s.split(); c = p[0].lower(); a = p[1:]
            try:
                if c in (".quit", ".exit", ".q"): break
                elif c == ".help": print(HELP)
                elif c == ".tables": tables(con)
                elif c == ".schema" and a: schema(con, a[0])
                elif c == ".sample": sample(con)
                elif c == ".open" and a:
                    con.close(); path = safe_path(a[0], ".db"); con = sqlite3.connect(path); con.set_authorizer(_kp_auth); print("Opened", path)
                elif c == ".export" and a: export_csv(con, a[0], a[1] if len(a) > 1 else "")
                elif c == ".import" and a: import_csv(con, a[0], a[1] if len(a) > 1 else "")
                else: print("Unknown or incomplete command. Type .help")
            except Exception as e: print("Error:", e)
            continue
        buf += line + "\n"
        if sqlite3.complete_statement(buf):
            try:
                cur = con.cursor()
                stmts = buf.strip()
                if stmts.count(";") > 1: con.executescript(stmts); print("OK")
                else: cur.execute(stmts); show(cur)
                con.commit()
            except Exception as e: print("Error:", e)
            buf = ""
    con.close(); print("Bye.")

if __name__ == "__main__":
    main()
