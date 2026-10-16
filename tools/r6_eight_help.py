# KPython in-app help guide: searchable entries (purpose, how to use, example) for every Dev and Tools tab button; optional confirmed export to Markdown.
"""Stdlib-only help guide for KPython. search(query) -> list of entries; get(label) -> entry or None."""
import os

SAFE_ROOT = "/home/pyodide"
MAX_BYTES = 500 * 1024

try:
    kp_safe_path  # provided by the KPython app when merged
except NameError:
    def kp_safe_path(path):
        """Fallback: resolve path and refuse anything outside /home/pyodide."""
        full = os.path.realpath(os.path.join(SAFE_ROOT, path))
        if not (full == SAFE_ROOT or full.startswith(SAFE_ROOT + os.sep)):
            raise ValueError(f"Only paths under {SAFE_ROOT} are allowed.")
        return full

# (label, purpose, how to use, example, keywords)
_RAW = [
 ("🧹 Lint", "Check the open script for syntax errors, unused imports/variables, undefined names, long lines and missing docstrings. Never runs your code.",
  "Open a script in the editor, go to Dev, tap 🧹 Lint. Read the line-numbered report.", "A file with 'import os' never used shows: unused import 'os' on line 1.", "lint check errors syntax unused undefined style"),
 ("✅ Run tests", "Run unittest TestCases and doctests in the open script and show pass/fail counts, tracebacks and timing.",
  "Tap ✅ Run tests and confirm (it executes the script).", "A script with class T(unittest.TestCase) shows 'Ran 3 tests: 3 passed'.", "test unittest doctest pass fail"),
 ("🗂 Outline", "List the classes and functions in the open script with their signatures.",
  "Tap 🗂 Outline with a script open.", "Shows 'def add(a, b)' and 'class Cart' with line numbers.", "outline structure functions classes signatures"),
 ("✏️ Rename…", "Rename a name across the open script, skipping strings and comments (token-safe).",
  "Tap ✏️ Rename…, type the old name, then the new name. Undo with ↶ in the editor.", "Rename 'tot' to 'total' everywhere it is used as a name.", "rename refactor variable identifier"),
 ("⏱ Profile", "Run the open script under cProfile and show the slowest functions (top 15 by cumulative time).",
  "Tap ⏱ Profile and confirm (it executes the script). Tap Stop if it hangs.", "See that slow_loop() takes most of the run time.", "profile cprofile slow performance speed"),
 ("📊 Benchmark", "Time code snippets with timeit, profile code, or compare two snippets.",
  "Tap 📊 Benchmark and follow the menu; paste code and finish with an empty line.", "Compare '[x*2 for x in r]' vs 'list(map(...))'.", "benchmark timeit timing speed"),
 ("✨ Format", "PEP8-ish formatter: tabs to spaces, trailing spaces, comma spacing, import sorting, blank lines. Shows a diff first.",
  "Tap ✨ Format, review the before/after diff, then confirm to apply. Undo with ↶.", "'import sys,os' and 'f(a,b)' become sorted imports and 'f(a, b)'.", "format pep8 style indent imports spacing"),
 ("🐞 Debug", "Step debugger: run the script line by line with step, next, continue, breakpoints and locals.",
  "Tap 🐞 Debug and confirm. Type s (step), n (next), c (continue), b N (breakpoint at line N).", "'b 12' then 'c' stops at line 12 and shows local variables.", "debug step breakpoint trace locals"),
 ("📏 Metrics", "Report lines, functions/classes, per-function complexity, long/complex flags and TODO/FIXME notes.",
  "Tap 📏 Metrics with a script open.", "Flags a function with complexity 14 as complex.", "metrics complexity lines size todo"),
 ("🔤 Type check", "Flag missing type annotations and obvious literal type mismatches in calls, returns and annotated assignments.",
  "Tap 🔤 Type check with a script open.", "'x: int = \"5\"' is flagged as str assigned to int.", "type hints annotations mypy check"),
 ("🕘 Save version", "Save a snapshot of the open script into local history (/home/pyodide/.history).",
  "Tap 🕘 Save version, type an optional note, tap OK.", "Note 'before refactor' saves a version you can restore later.", "save version snapshot backup history"),
 ("📜 History", "Browse saved versions of files: list, diff and restore. Also turns a pasted snippet into a function.",
  "Tap 📜 History and follow the menu.", "Diff version 3 against the current file, then restore it.", "history versions restore diff undo function maker"),
 ("📝 Docstrings", "Add Google-style docstring stubs (Args/Returns/Raises) from signatures and type hints.",
  "Tap 📝 Docstrings, review the diff, confirm to apply. Undo with ↶.", "def add(a: int, b: int) -> int gets an Args/Returns docstring.", "docstring docs documentation generate"),
 ("🧪 Coverage", "Run the script and its tests and show per-line hit/miss and coverage % per function.",
  "Tap 🧪 Coverage and confirm (it executes the script).", "Shows parse(): 80% with lines 14-15 missed.", "coverage tests lines hit miss"),
 ("🧠 Memory", "Run the script under tracemalloc and show top allocations by line and peak memory.",
  "Tap 🧠 Memory and confirm. Needs tracemalloc in this Python build.", "Shows line 8 allocating 4 MB in a big list.", "memory tracemalloc allocations peak"),
 ("🔑 Secret scan", "Find hard-coded tokens, keys and passwords in your scripts; shows file:line with masked values and how to fix.",
  "Tap 🔑 Secret scan.", "Flags 'ghp_abcd...[40 chars]' on line 3 of deploy.py.", "secrets tokens keys passwords security scan"),
 ("🕸 Import map", "Map local imports between your scripts: graph, cycles, unused imports, missing modules, text tree and Mermaid.",
  "Tap 🕸 Import map.", "Shows main.py -> helpers.py and warns about a cycle.", "imports dependencies graph cycles modules"),
 ("📄 Markdown preview", "Render the open script/text as Markdown (headings, lists, code, links, tables) with all raw HTML escaped.",
  "Open a .md text in the editor and tap 📄 Markdown preview. It shows in a sandboxed frame.", "'# Title' and '- item' render as a heading and a bullet list.", "markdown preview html render readme"),
 ("Compare", "Show a diff between the two scripts picked in the A/B dropdowns (unified, or side-by-side if checked).",
  "Pick scripts in the two dropdowns, optionally tick side-by-side, tap Compare.", "Compare old.py with new.py to see changed lines.", "diff compare files changes"),
 ("Patch…", "Diff & patch tool: compare snippets/files and apply unified patches safely inside /home/pyodide.",
  "Tap Patch… and follow the menu; paste a unified diff to apply.", "Apply a '--- a/x.py +++ b/x.py' patch to x.py.", "patch diff apply unified"),
 ("✅ Task board", "Task board: TODO/FIXME/HACK/XXX from your scripts plus manual tasks with priority and done state (/home/pyodide/.tasks.json).",
  "Tap ✅ Task board, then scan, add, mark done, or delete tasks. It asks before saving.", "Add 'fix login bug' as high priority, later mark it done.", "todo tasks fixme board priority"),
 ("🧪 Test generator", "Write a test_<name>.py unittest skeleton from a script's functions; previews a diff first.",
  "Tap 🧪 Test generator, choose a script, review and confirm.", "math_utils.py produces test_math_utils.py with one test per function.", "test generate unittest skeleton"),
 ("📮 API collections", "Saved API request collections with {{var}} variables; secret headers are never saved and are masked in output.",
  "Tap 📮 API collections, create a collection, add requests, run them.", "GET {{base}}/users with base=https://api.example.com.", "api http requests collections postman"),
 ("🔑 Passwords", "Generate secure passwords, passphrases, tokens and PINs with a strength meter; check a password's strength. Nothing saved.",
  "Tap 🔑 Passwords and pick from the menu.", "A 5-word passphrase like 'amber-atlas-...' with its entropy.", "password passphrase generator pin token strength"),
 ("🔍 Project search", "Search text files under /home/pyodide (plain or regex, case, whole word), preview matches, and replace after a typed confirm.",
  "Tap 🔍 Project search, enter the pattern and options.", "Find every 'print(' across your files.", "search find grep replace regex files"),
 ("✏️ Replace in saved scripts", "Search-and-replace across your saved app scripts with a preview and confirm.",
  "Tap ✏️ Replace in saved scripts, enter find and replace text, confirm.", "Replace 'old_name' with 'new_name' in all scripts.", "replace find saved scripts bulk"),
 ("⏱ Compare speed", "Time 2-4 code variants and show a ranked table with relative speed and a text bar chart.",
  "Tap ⏱ Compare speed and paste each variant.", "''.join(list) ranks 3x faster than += in a loop.", "compare speed benchmark timeit variants"),
 ("📖 Explain code", "Offline plain-English walkthrough of a script's functions, classes and Python features used.",
  "Tap 📖 Explain code and choose a script.", "Explains that a script uses a list comprehension and a decorator.", "explain learn understand walkthrough"),
 ("📊 Charts", "Load CSV/JSON (pasted or a file), pick columns, draw line/bar/scatter/histogram (matplotlib or text), optionally save PNG/TXT.",
  "Tap 📊 Charts, load data, pick columns and chart type.", "Bar chart of 'hours' by 'day' from a pasted CSV.", "chart graph plot csv matplotlib"),
 ("🛠 Refactor", "Extract lines into a function, inline a variable, or convert %/.format() to f-strings; diff + confirm.",
  "Tap 🛠 Refactor, choose an action, review the diff, confirm.", "'Hi %s' % name becomes f'Hi {name}'.", "refactor extract inline fstring"),
 ("🗄 SQL", "SQLite playground: create/open a database in /home/pyodide, run SQL, view tables and schema, import/export CSV, sample data.",
  "Tap 🗄 SQL, open a database, type SQL.", "SELECT * FROM people WHERE age > 30;", "sql sqlite database query tables csv"),
 ("🌐 HTTP", "Mini HTTP/API tester: GET/POST/PUT/DELETE with headers and JSON body; shows status, headers, timing, pretty JSON. Stores nothing.",
  "Tap 🌐 HTTP, enter method, URL, headers and body.", "GET https://api.github.com shows 200 and JSON.", "http api request get post rest"),
 ("📋 Data viewer", "Load CSV/JSON (paste or file), paginated table, column types and stats, filter/sort, CSV<->JSON convert.",
  "Tap 📋 Data viewer and load data.", "Sort a CSV by 'price' and see column stats.", "data csv json table stats filter sort"),
 ("📦 Projects", "Multi-file projects in /home/pyodide/projects: create, run main.py, zip/unzip, import a public GitHub repo as zip.",
  "Tap 📦 Projects and follow the menu.", "Create project 'demo' with main.py and helpers.py, then run it.", "projects zip folders github import multi-file"),
 ("🔎 Regex", "Regex tester: pattern, flags and sample text; shows matches, groups, sub() preview and a cheat sheet. No files.",
  "Tap 🔎 Regex, enter pattern, flags and text.", r"Pattern \d{3}-\d{4} finds '283-1189'.", "regex regular expression match pattern"),
 ("🧾 JSON", "JSON toolkit: pretty/minify, validate with error line, JSONPath-like query, dataclass generator.",
  "Tap 🧾 JSON and pick an action.", "Query 'users[0].name' from pasted JSON.", "json pretty validate query dataclass"),
 ("🔐 Encode/Hash", "base64, URL, hex, JWT decode (no verify), md5/sha1/sha256, UUID, timestamp<->date; masks secret-looking input.",
  "Tap 🔐 Encode/Hash and pick an action.", "sha256 of 'hello' or a Unix timestamp to a date.", "encode decode base64 hash sha256 jwt uuid"),
 ("🧩 Templates", "Snippet library: search Python templates (CLI, dataclass, unittest, fetch, file I/O, async) and save one as a new script.",
  "Tap 🧩 Templates, search, pick one, save it.", "Search 'cli' to get an argparse starter.", "templates snippets starter boilerplate"),
 ("🔁 Convert config", "Convert between JSON, TOML, INI, CSV and Python dict literals (input under 500KB).",
  "Tap 🔁 Convert config, choose formats, paste or load input.", "Turn an INI file into JSON.", "convert json toml ini csv config"),
 ("🥋 Katas", "16 coding challenges (easy to hard) with starter code, hidden tests, hints and saved progress.",
  "Tap 🥋 Katas, pick a challenge, write your solution.", "'reverse': return s reversed (hint: s[::-1]).", "katas challenges practice exercises learn"),
 ("📦 Packages", "List installed packages, look up PyPI names, warn on typos, and do confirmed, pinned micropip installs.",
  "Tap 📦 Packages and follow the menu.", "Look up 'requests' version and whether it has a pure-Python wheel.", "packages pypi micropip install"),
]


# Tools tab buttons (same tuple format)
_TOOLS = [
 ("🧽 Quote", "Cleaning quote & invoice: price = sq ft x rate, plus checked extras, for the chosen frequency.",
  "Open Tools > 🧽 Quote, enter client, sq ft, rate $/sq ft, frequency, tick extras (windows +$40, fridge/microwave +$25, restroom deep clean +$35, carpet +$30, trash haul-away +$20, floor mop & shine +$45), notes, then tap Build invoice. Use 📋 Copy or 📤 Share on the result.",
  "1500 sq ft at $0.10, weekly, with Restroom deep clean builds an invoice you can share.", "quote invoice cleaning price client extras share copy"),
 ("⏱ Hours", "Shift hours & pay log grouped by week (Mon-Sun); hours over 40 a week pay 1.5x; overnight shifts handled.",
  "Open Tools > ⏱ Hours, set date, rate $/hr, start, end and break minutes, tap Add shift. Tap ✕ on a shift to delete (asks first).",
  "22:00 to 06:30 with a 30 min break logs 8.00 h.", "hours shifts pay overtime wage timesheet"),
 ("💵 Budget", "Simple income/expense log with running balance and totals in/out.",
  "Open Tools > 💵 Budget, pick Expense or Income, enter amount, what, date, tap Add. Tap ✕ to delete (asks first).",
  "Income $500 'paycheck' then Expense $40 'gas' shows balance $460.", "budget money income expense balance spending"),
 ("🚗 Miles", "Mileage log with total miles, this year's miles and an estimated deduction at your $/mile rate (default 0.70).",
  "Open Tools > 🚗 Miles, enter date, miles, purpose and $/mile, tap Log trip. Tap ✕ to delete (asks first).",
  "12.5 mi 'Client walkthrough' adds to the year total and deduction estimate.", "miles mileage trips deduction gas taxes"),
 ("🧮 Calc", "Tip & split calculator plus a unit converter.",
  "Open Tools > 🧮 Calc. Enter bill, tip % and people, tap Calculate tip. Or enter a value, pick a conversion, tap Convert.",
  "$50 bill, 18% tip, 2 people gives each person's share.", "calc calculator tip split unit convert"),
 ("🐙 GitHub", "Browse GitHub repos (public without login), open files, send them to the editor or run them (asks first), and push edits with a typed 'yes'.",
  "Open Tools > 🐙 GitHub, enter owner/repo, branch and path, tap Open (⬆ Up goes to the parent folder). For private repos or pushing, log in with a fine-grained token (kept in memory only, never saved).",
  "Open kcwfire21-blip/kpython, tap a file, then 📝 To editor.", "github repo git push pull browse token"),
 ("🌐 Allowed sites", "Controls which https sites Python (scripts, the HTTP tester, pyfetch) can reach; only this screen can change the list.",
  "Open Tools > 🌐 Allowed sites, type an https origin (no path) and tap Add. Reset to defaults… restores the default list.",
  "Add https://api.example.com so a script can fetch from it.", "sites allowlist network https fetch permissions"),
 ("🛠 More", "Shows team-made tools that open as a new script in the Code tab and run there.",
  "Open Tools > 🛠 More and tap one of its buttons.", "Tap 🏦 Loan calc to open and run the loan script.", "more extra team snippets"),
 ("🛠 Dev tools", "Under More: opens the team's 'Dev tools' snippet as a new script and runs it in the Code tab.",
  "Tools > 🛠 More > 🛠 Dev tools.", "Tap it, then answer the script's prompts in the Code tab.", "more dev tools snippet"),
 ("⌨️ Terminal", "Under More: opens the team's 'Terminal' snippet as a new script and runs it in the Code tab.",
  "Tools > 🛠 More > ⌨️ Terminal.", "Tap it, then type commands at the script's prompt.", "more terminal shell snippet"),
 ("💼 Job tracker", "Under More: opens the team's 'Job application' tracker snippet and runs it in the Code tab.",
  "Tools > 🛠 More > 💼 Job tracker.", "Tap it and follow its prompts to log applications.", "more job tracker applications snippet"),
 ("🐙 GitHub browser", "Under More: opens the team's 'GitHub repo' browser snippet and runs it in the Code tab.",
  "Tools > 🛠 More > 🐙 GitHub browser.", "Tap it and follow its prompts.", "more github browser snippet"),
 ("🏦 Loan calc", "Under More: opens the team's 'Loan' calculator snippet and runs it in the Code tab.",
  "Tools > 🛠 More > 🏦 Loan calc.", "Tap it and answer its prompts.", "more loan calculator payment snippet"),
 ("🏠 Rent check", "Under More: opens the team's 'Rent' check snippet and runs it in the Code tab.",
  "Tools > 🛠 More > 🏠 Rent check.", "Tap it and answer its prompts.", "more rent housing afford snippet"),
]

ENTRIES = ([dict(label=l, tab="Dev", purpose=p, how=h, example=e, keywords=k) for l, p, h, e, k in _RAW]
           + [dict(label=l, tab="Tools", purpose=p, how=h, example=e, keywords=k) for l, p, h, e, k in _TOOLS])


def _norm(s):
    return " ".join(s.lower().split())


def get(label):
    """Return the entry whose button label matches (exact, or ignoring emoji/case), else None."""
    q = _norm(label or "")
    for e in ENTRIES:
        if _norm(e["label"]) == q:
            return e
    for e in ENTRIES:
        if _norm(e["label"]).split(" ", 1)[-1].rstrip("…") == q.rstrip("…"):
            return e
    return None


def search(query):
    """Return entries matching all words of query, best matches (label/keyword hits) first."""
    words = _norm(query or "").split()
    if not words:
        return []
    scored = []
    for i, e in enumerate(ENTRIES):
        text = _norm(" ".join(e.values()))
        if all(w in text for w in words):
            score = sum(3 * (w in _norm(e["label"])) + 2 * (w in e["keywords"]) for w in words)
            scored.append((-score, i, e))
    return [e for _, _, e in sorted(scored)]


def show(e):
    """Format one entry as text."""
    return f"[{e['tab']}] {e['label']}\n  What: {e['purpose']}\n  How: {e['how']}\n  Example: {e['example']}\n"


def to_markdown():
    out = ["# KPython tools help\n"]
    for e in ENTRIES:
        out.append(f"## {e['label']} ({e['tab']} tab)\n- **What:** {e['purpose']}\n- **How:** {e['how']}\n- **Example:** {e['example']}\n")
    return "\n".join(out)


def export(path="kpython_help.md", ask=input):
    """Write the guide as Markdown under /home/pyodide after a y/N confirm."""
    full = kp_safe_path(path)
    data = to_markdown()
    if len(data.encode()) > MAX_BYTES:
        return "Too big to export."
    verb = "Overwrite" if os.path.exists(full) else "Write"
    if ask(f"{verb} {full}? [y/N] ").strip().lower() != "y":
        return "Cancelled."
    with open(full, "w", encoding="utf-8") as f:
        f.write(data)
    return f"Saved {full}"


def main():
    print(f"KPython help: {len(ENTRIES)} tools (Dev + Tools tabs). Type a keyword, 'list' for all, 'export' to save Markdown, Enter to quit.")
    while True:
        try:
            q = input("help> ").strip()
        except EOFError:
            break
        if not q:
            break
        if q.lower() == "list":
            for e in ENTRIES:
                print(f"[{e['tab']}] {e['label']}: {e['purpose']}")
        elif q.lower() == "export":
            try:
                print(export())
            except (ValueError, OSError) as ex:
                print("Error:", ex)
        else:
            hits = search(q)
            print("\n".join(show(e) for e in hits) if hits else "No matches. Try 'list'.")


def _self_test():
    assert len(ENTRIES) == 55 and len({e["label"] for e in ENTRIES}) == 55
    assert sum(e["tab"] == "Dev" for e in ENTRIES) == 41 and sum(e["tab"] == "Tools" for e in ENTRIES) == 14
    assert get("🧽 Quote")["tab"] == "Tools" and get("quote")["label"] == "🧽 Quote"
    assert search("mileage")[0]["label"] == "🚗 Miles" and search("invoice")[0]["tab"] == "Tools"
    assert len(search("tools")) >= 14 and all(e["tab"] == "Tools" for e in search("rent check"))
    assert all(all(e[k] for k in e) for e in ENTRIES)
    assert get("🧹 Lint")["label"] == "🧹 Lint" and get("lint")["label"] == "🧹 Lint"
    assert get("rename")["label"] == "✏️ Rename…" and get("nope") is None
    assert search("regex")[0]["label"] == "🔎 Regex"
    assert search("") == [] and search("zzzqqq") == []
    try:
        kp_safe_path("../etc/passwd")
        raise AssertionError("escape allowed")
    except ValueError:
        pass
    assert export("x.md", ask=lambda _: "n") == "Cancelled."
    print("self-test OK")


# --- KPython v5: size caps on text inputs (Drop's review) ---
_KP_MAX = 500_000
def _kp_cap(fn):
    def w(*a, **k):
        for x in list(a) + list(k.values()):
            if isinstance(x, str) and len(x) > _KP_MAX: raise ValueError("input too big (max 500 KB)")
        return fn(*a, **k)
    w.__wrapped__ = fn; return w
for _n in ("format_code", "analyze", "check", "report", "pretty", "minify", "validate", "gen_dataclasses", "b64dec", "hexdec", "run_tests", "generate", "to_html", "cover", "profile_source", "scan_text", "convert", "parse", "split_cells", "merge3", "parse_requirements", "scan_setup", "parse_cron", "parse_any", "analyze_lines"):
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
        return _kp_b.kp_safe_path(r) if hasattr(_kp_b, "kp_safe_path") and isinstance(r, str) and r.startswith("/") and all(globals().get(v, "/home/pyodide") == "/home/pyodide" for v in ("BASE", "BASE_DIR", "SAFE_ROOT", "HOME")) else r
    return w
for _n in ("safe_path", "_safe_path", "_safe"):
    if callable(globals().get(_n)): globals()[_n] = _kp_wrap(globals()[_n])

if __name__ == "__main__":
    import sys
    _self_test() if "--selftest" in sys.argv else main()
