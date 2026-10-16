# Log analyzer (KPython r6): auto-detects Python logging / nginx-apache access / JSON-lines logs; level counts, top errors, timeline, level+regex filters. Stdlib only.
import os, re, sys, json
from collections import Counter, OrderedDict
from datetime import datetime

BASE_DIR = "/home/pyodide"
MAX_PATTERN = 200
MAX_LINE = 2000
MAX_LINES = 50000
LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_LVL_ALIAS = {"WARN": "WARNING", "FATAL": "CRITICAL", "ERR": "ERROR", "TRACE": "DEBUG",
              "NOTICE": "INFO", "CRIT": "CRITICAL", "EXCEPTION": "ERROR"}

def norm_level(s):
    if s is None:
        return "UNKNOWN"
    s = str(s).strip().upper()
    s = _LVL_ALIAS.get(s, s)
    return s if s in LEVELS else "UNKNOWN"

def safe_path(path, base=None):
    base = os.path.realpath(base or BASE_DIR)
    if not path:
        raise ValueError("empty path")
    p = path if os.path.isabs(path) else os.path.join(base, path)
    real = os.path.realpath(p)
    if real != base and not real.startswith(base + os.sep):
        raise ValueError("path outside %s refused" % base)
    return real

def read_file(path, base=None):
    real = safe_path(path, base)
    if not os.path.isfile(real):
        raise ValueError("not a file: %s" % path)
    if os.path.getsize(real) > 20_000_000:  # KPython: size cap
        raise ValueError("log file over 20 MB")
    lines = []
    with open(real, "r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if i >= MAX_LINES:
                break
            lines.append(line.rstrip("\n"))
    return lines

# ---- parsing ----
PY_RES = [
    re.compile(r"^(?P<time>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\s*[-|]?\s*(?:\S+\s*[-|]\s*)?(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\s*[-|:]?\s*(?:(?P<name>[\w.]+)\s*[-|:]\s*)?(?P<msg>.*)$"),
    re.compile(r"^\[?(?P<time>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)\]?\s*\[?(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL)\]?\s*(?P<msg>.*)$"),
    re.compile(r"^(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL):(?P<name>[^:]*):(?P<msg>.*)$"),
]
ACCESS_RE = re.compile(r'^(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] "(?P<req>[^"]*)" (?P<status>\d{3}) (?P<size>\S+)(?: "(?P<ref>[^"]*)" "(?P<ua>[^"]*)")?')

def parse_time(s):
    if not s:
        return None
    s = str(s).strip()
    m = re.match(r"(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2})", s)
    if m:
        try:
            return datetime.strptime(m.group(1), "%d/%b/%Y:%H:%M:%S")
        except ValueError:
            return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})", s)
    if m:
        try:
            return datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    try:
        t = s.replace("Z", "+00:00")
        return datetime.fromisoformat(t).replace(tzinfo=None)
    except ValueError:
        pass
    try:
        v = float(s)
        if v > 1e12:
            v /= 1000.0
        from datetime import timezone
        return datetime.fromtimestamp(v, timezone.utc).replace(tzinfo=None)
    except (ValueError, OverflowError, OSError):
        return None

def status_level(code):
    c = int(code)
    if c >= 500: return "ERROR"
    if c >= 400: return "WARNING"
    return "INFO"

def parse_python(line):
    for r in PY_RES:
        m = r.match(line)
        if m:
            d = m.groupdict()
            return {"time": parse_time(d.get("time")), "level": norm_level(d["level"]), "msg": (d.get("msg") or "").strip()}
    return None

def parse_access(line):
    m = ACCESS_RE.match(line)
    if not m:
        return None
    return {"time": parse_time(m.group("time")), "level": status_level(m.group("status")),
            "msg": "%s %s" % (m.group("status"), m.group("req"))}

def parse_json(line):
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        o = json.loads(line)
    except ValueError:
        return None
    if not isinstance(o, dict):
        return None
    def get(*keys):
        for k in keys:
            if k in o and o[k] is not None:
                return o[k]
        return None
    return {"time": parse_time(get("time", "timestamp", "ts", "@timestamp", "asctime")),
            "level": norm_level(get("level", "levelname", "severity", "lvl")),
            "msg": str(get("msg", "message", "event") or "")}

PARSERS = OrderedDict([("python", parse_python), ("access", parse_access), ("json", parse_json)])

def detect_format(lines, sample=200):
    best, score = "python", -1
    sl = [l for l in lines if l.strip()][:sample]
    for name, fn in PARSERS.items():
        n = sum(1 for l in sl if fn(l[:MAX_LINE]))
        if n > score:
            best, score = name, n
    return best if score > 0 else "python"

def parse_lines(lines, fmt="auto"):
    lines = lines[:MAX_LINES]
    if fmt == "auto":
        fmt = detect_format(lines)
    if fmt not in PARSERS:
        raise ValueError("unknown format: %s" % fmt)
    fn = PARSERS[fmt]
    entries, last = [], None
    for raw in lines:
        line = raw[:MAX_LINE]
        if not line.strip():
            continue
        e = fn(line)
        if e is None:
            if last is not None and fmt == "python":  # traceback continuation
                last["extra"] = last.get("extra", 0) + 1
                continue
            e = {"time": None, "level": "UNKNOWN", "msg": line.strip()}
        e["raw"] = line
        entries.append(e)
        last = e
    return fmt, entries

# ---- reports ----
_NORM = [
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<uuid>"),
    (re.compile(r'"[^"]{0,500}"'), "<str>"),
    (re.compile(r"'[^']{0,500}'"), "<str>"),
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), "<hex>"),
    (re.compile(r"\b[0-9a-fA-F]{12,}\b"), "<hex>"),
    (re.compile(r"\d+(?:\.\d+)?"), "<n>"),
]

def normalize_msg(msg):
    s = msg[:MAX_LINE]
    for r, rep in _NORM:
        s = r.sub(rep, s)
    return s.strip()

def count_levels(entries):
    c = Counter(e["level"] for e in entries)
    return OrderedDict((l, c[l]) for l in LEVELS + ["UNKNOWN"] if c[l])

def top_errors(entries, n=10, min_level="WARNING"):
    keep = set(LEVELS[LEVELS.index(min_level):])
    c = Counter(normalize_msg(e["msg"]) for e in entries if e["level"] in keep)
    return c.most_common(n)

def timeline(entries, bucket="minute"):
    fmt = "%Y-%m-%d %H:%M" if bucket == "minute" else "%Y-%m-%d %H:00"
    c = Counter(e["time"].strftime(fmt) for e in entries if e.get("time"))
    return sorted(c.items())

def bar_chart(pairs, width=30):
    if not pairs:
        return "(no timestamped entries)"
    mx = max(v for _, v in pairs) or 1
    kw = max(len(str(k)) for k, _ in pairs)
    return "\n".join("%s | %s %d" % (str(k).ljust(kw), "#" * max(1 if v else 0, int(v * width / mx)), v) for k, v in pairs)

_NESTED = re.compile(r"\((?:[^()\\]|\\.)*[+*}](?:[^()\\]|\\.)*\)\s*(?:[+*]|\{\d*,?\d*\})")
_ALT_REPEAT = re.compile(r"\((?:[^()\\]|\\.)*\|(?:[^()\\]|\\.)*\)\s*[+*]")

def check_pattern(p):
    if not isinstance(p, str) or not p:
        raise ValueError("empty pattern")
    if len(p) > MAX_PATTERN:
        raise ValueError("pattern longer than %d chars" % MAX_PATTERN)
    if _NESTED.search(p):
        raise ValueError("nested quantifier rejected (ReDoS risk)")
    if _ALT_REPEAT.search(p):
        raise ValueError("repeated alternation rejected (ReDoS risk)")
    if re.search(r"\\[1-9]", p):
        raise ValueError("backreferences not allowed")
    try:
        return re.compile(p, re.IGNORECASE)
    except re.error as ex:
        raise ValueError("bad regex: %s" % ex)

def filter_entries(entries, levels=None, pattern=None):
    rx = check_pattern(pattern) if pattern else None
    lv = set(norm_level(l) for l in levels) if levels else None
    out = []
    for e in entries:
        if lv and e["level"] not in lv:
            continue
        if rx and not rx.search(e["raw"][:MAX_LINE]):
            continue
        out.append(e)
    return out

def full_report(entries, fmt, bucket="minute"):
    out = ["Format: %s   Entries: %d" % (fmt, len(entries)), "", "Counts by level:"]
    for k, v in count_levels(entries).items():
        out.append("  %-9s %d" % (k, v))
    out += ["", "Top warnings/errors:"]
    te = top_errors(entries)
    out += ["  %4d  %s" % (n, m[:120]) for m, n in te] or ["  (none)"]
    out += ["", "Timeline per %s:" % bucket, bar_chart(timeline(entries, bucket))]
    return "\n".join(out)

# ---- UI ----
def read_pasted(inp=input):
    print("Paste log lines; finish with a line containing only END")
    lines = []
    while len(lines) < MAX_LINES:
        try:
            l = inp()
        except EOFError:
            break
        if l.strip() == "END":
            break
        lines.append(l)
    return lines

def main(inp=input):
    lines, entries, fmt = [], [], None
    while True:
        print("\n== Log Analyzer ==  (%d entries%s)" % (len(entries), ", " + fmt if fmt else ""))
        print("1 Paste log  2 Load file  3 Set format  4 Report  5 Timeline by hour")
        print("6 Filter by level  7 Filter by regex  8 Self-test  0 Quit")
        try:
            ch = inp("> ").strip()
        except EOFError:
            break
        try:
            if ch == "1":
                lines = read_pasted(inp); fmt, entries = parse_lines(lines)
                print("Loaded %d entries (%s)" % (len(entries), fmt))
            elif ch == "2":
                lines = read_file(inp("Path under %s: " % BASE_DIR).strip())
                fmt, entries = parse_lines(lines)
                print("Loaded %d entries (%s)" % (len(entries), fmt))
            elif ch == "3":
                f = inp("Format (auto/python/access/json): ").strip().lower() or "auto"
                fmt, entries = parse_lines(lines, f); print("Parsed as %s" % fmt)
            elif ch == "4":
                print(full_report(entries, fmt or "-"))
            elif ch == "5":
                print(bar_chart(timeline(entries, "hour")))
            elif ch in ("6", "7"):
                if ch == "6":
                    res = filter_entries(entries, levels=inp("Levels (comma sep): ").split(","))
                else:
                    res = filter_entries(entries, pattern=inp("Regex: ").strip())
                print("%d matches" % len(res))
                for e in res[:50]:
                    print("  [%s] %s" % (e["level"], e["raw"][:160]))
                if len(res) > 50: print("  ... (%d more)" % (len(res) - 50))
            elif ch == "8":
                run_selftests()
            elif ch in ("0", "q"):
                break
            else:
                print("Unknown choice")
        except (ValueError, OSError) as ex:
            print("Error:", ex)

def run_selftests():
    import tempfile
    ok = 0
    def t(cond, name):
        nonlocal ok
        assert cond, name
        ok += 1
    py = ["2026-10-16 10:01:02,123 - app - INFO - started",
          "2026-10-16 10:01:30,000 - app - ERROR - failed id 42 at 0xdeadbeef",
          "Traceback (most recent call last):", "  boom",
          "2026-10-16 10:02:00,000 - app - ERROR - failed id 7 at 0xabc",
          "2026-10-16 11:00:00 WARNING disk 91% used",
          "WARNING:root:old style"]
    f, e = parse_lines(py)
    t(f == "python", "detect python")
    c = count_levels(e)
    t(c["ERROR"] == 2 and c["INFO"] == 1 and c["WARNING"] == 2, "levels %s" % c)
    t(top_errors(e)[0] == ("failed id <n> at <hex>", 2), "group errors")
    t(len(timeline(e, "minute")) == 3 and len(timeline(e, "hour")) == 2, "timeline")
    acc = ['1.2.3.4 - - [16/Oct/2026:10:00:01 +0000] "GET / HTTP/1.1" 200 12 "-" "ua"',
           '1.2.3.4 - - [16/Oct/2026:10:00:05 +0000] "GET /x HTTP/1.1" 404 0',
           '1.2.3.4 - - [16/Oct/2026:10:01:05 +0000] "POST /y HTTP/1.1" 502 0 "-" "ua"']
    f, e = parse_lines(acc)
    t(f == "access", "detect access")
    t(count_levels(e) == OrderedDict([("INFO", 1), ("WARNING", 1), ("ERROR", 1)]), "status levels")
    t(e[0]["time"] == datetime(2026, 10, 16, 10, 0, 1), "access time")
    js = ['{"time":"2026-10-16T10:00:00Z","level":"warn","msg":"user \\"bob\\" slow"}',
          '{"ts":1760608800,"level":"error","message":"req 550e8400-e29b-41d4-a716-446655440000 failed"}',
          'not json']
    f, e = parse_lines(js)
    t(f == "json", "detect json")
    t(e[0]["level"] == "WARNING" and e[1]["level"] == "ERROR" and e[2]["level"] == "UNKNOWN", "json levels")
    t(normalize_msg(e[1]["msg"]) == "req <uuid> failed", "uuid norm")
    t(normalize_msg("user 'bob' x") == "user <str> x", "str norm")
    f, e = parse_lines(py, "access")
    t(f == "access" and all(x["level"] == "UNKNOWN" for x in e), "override")
    try:
        parse_lines(py, "bogus"); t(False, "bad fmt")
    except ValueError: ok += 1
    f, e = parse_lines(py)
    t(len(filter_entries(e, levels=["error"])) == 2, "level filter")
    t(len(filter_entries(e, pattern=r"id \d+")) == 2, "regex filter")
    for bad in ["(a+)+", "(a*)*b", "(x|xy)+", "a" * 201, "(", r"(a)\1", ""]:
        try:
            check_pattern(bad); t(False, "accepted " + bad)
        except ValueError: ok += 1
    long_line = ["2026-10-16 10:00:00 ERROR " + "x" * 10000]
    t(len(parse_lines(long_line)[1][0]["raw"]) == MAX_LINE, "line cap")
    t(len(parse_lines(["x"] * (MAX_LINES + 10), "access")[1]) == MAX_LINES, "lines cap")
    t(bar_chart([]) == "(no timestamped entries)", "empty chart")
    t("Format" in full_report([], "-"), "empty report")
    d = tempfile.mkdtemp(dir="/home/pyodide" if os.path.isdir("/home/pyodide") else None)  # KPython: test folder inside ~
    with open(os.path.join(d, "a.log"), "w") as fh:
        fh.write("\n".join(py))
    t(len(read_file("a.log", d)) == len(py), "read file")
    outside = tempfile.mkdtemp()
    with open(os.path.join(outside, "s.log"), "w") as fh: fh.write("x")
    os.symlink(os.path.join(outside, "s.log"), os.path.join(d, "link.log"))
    for bad in ["../etc/passwd", "/etc/passwd", "link.log", "missing.log", ""]:
        try:
            read_file(bad, d); t(False, "allowed " + bad)
        except ValueError: ok += 1
    print("All %d self-tests passed." % ok)
    return True

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
    if "--selftest" in sys.argv:
        run_selftests()
    else:
        main()
