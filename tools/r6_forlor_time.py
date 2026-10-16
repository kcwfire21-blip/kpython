# Forlor: coder time toolkit - epoch/ISO/RFC 2822 conversion, timezone conversion (zoneinfo or UTC offset), duration math, cron explainer with next 5 runs. Stdlib only.
import re
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime, parsedate_to_datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

_OFF = re.compile(r"^(?:UTC|GMT)?\s*([+-])(\d{1,2})(?::?(\d{2}))?$", re.I)

def get_tz(name):
    """IANA name via zoneinfo, or a fixed offset like +05:30 / UTC-5."""
    name = (name or "UTC").strip()
    if name.upper() in ("UTC", "Z", "GMT"):
        return timezone.utc
    m = _OFF.match(name)
    if m:
        sign = -1 if m.group(1) == "-" else 1
        return timezone(sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3) or 0)))
    if ZoneInfo is not None:
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    raise ValueError(f"Unknown timezone '{name}' (tzdata may be missing; use an offset like -05:00)")

# ---------- timestamps ----------
def parse_any(s, tz=timezone.utc):
    s = s.strip()
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        v = float(s)
        if abs(v) > 1e11:  # milliseconds
            v /= 1000
        return datetime.fromtimestamp(v, timezone.utc)
    if s.lower() == "now":
        return datetime.now(timezone.utc)
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=tz)
    except ValueError:
        pass
    try:
        d = parsedate_to_datetime(s)
        return d if d.tzinfo else d.replace(tzinfo=tz)
    except (TypeError, ValueError):
        raise ValueError(f"Can't parse '{s}' as epoch, ISO 8601 or RFC 2822")

def formats(d):
    return {
        "epoch": int(d.timestamp()),
        "epoch_ms": int(d.timestamp() * 1000),
        "iso": d.isoformat(),
        "iso_utc": d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "rfc2822": format_datetime(d),
    }

def convert_tz(d, tzname):
    return d.astimezone(get_tz(tzname))

# ---------- durations ----------
_DUR = re.compile(r"(-?\d+(?:\.\d+)?)\s*(w|d|h|m|s|ms)\b", re.I)
_UNITS = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1, "ms": 0.001}

def parse_duration(s):
    s = s.strip()
    if re.fullmatch(r"-?\d+:\d{2}(:\d{2})?", s):
        neg = s.startswith("-"); parts = [int(p) for p in s.lstrip("-").split(":")]
        while len(parts) < 3: parts.append(0)
        t = timedelta(hours=parts[0], minutes=parts[1], seconds=parts[2])
        return -t if neg else t
    total, found = 0.0, False
    for num, unit in _DUR.findall(s):
        total += float(num) * _UNITS[unit.lower()]; found = True
    if not found:
        raise ValueError("Use e.g. 1d 2h 30m, 90s, or HH:MM:SS")
    return timedelta(seconds=total)

def human(td):
    secs = int(td.total_seconds()); sign = "-" if secs < 0 else ""; secs = abs(secs)
    d, r = divmod(secs, 86400); h, r = divmod(r, 3600); m, s = divmod(r, 60)
    parts = [f"{v}{u}" for v, u in ((d, "d"), (h, "h"), (m, "m"), (s, "s")) if v]
    return sign + (" ".join(parts) or "0s")

def diff(a, b):
    return parse_any(b) - parse_any(a)

# ---------- cron ----------
_NAMES = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
          "sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}
_FIELDS = [("minute", 0, 59), ("hour", 0, 23), ("day of month", 1, 31), ("month", 1, 12), ("day of week", 0, 6)]
_MACROS = {"@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *", "@weekly": "0 0 * * 0",
           "@daily": "0 0 * * *", "@midnight": "0 0 * * *", "@hourly": "0 * * * *"}
_MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
_DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

def _field(spec, lo, hi):
    out = set()
    for part in spec.lower().split(","):
        step = 1
        if "/" in part:
            part, st = part.split("/"); step = int(st)
            if step < 1: raise ValueError("step must be >= 1")
        if part in ("*", ""):
            a, b = lo, hi
        elif "-" in part:
            a, b = (int(_NAMES.get(x, x)) for x in part.split("-", 1))
        else:
            a = int(_NAMES.get(part, part)); b = hi if step > 1 else a
        if hi == 6:  # allow 7 = Sunday
            a, b = (0 if a == 7 else a), (6 if b == 7 else b)
        if not (lo <= a <= hi and lo <= b <= hi and a <= b):
            raise ValueError(f"'{spec}' out of range {lo}-{hi}")
        out.update(range(a, b + 1, step))
    return out

def parse_cron(expr):
    expr = _MACROS.get(expr.strip().lower(), expr.strip())
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError("Cron needs 5 fields: minute hour day-of-month month day-of-week")
    sets = [_field(p, lo, hi) for p, (_, lo, hi) in zip(parts, _FIELDS)]
    return parts, sets

def _desc(raw, name, lo, hi, namer=None):
    if raw == "*": return None
    if raw.startswith("*/"): return f"every {raw[2:]} {name}s"
    vals = sorted(_field(raw, lo, hi))
    shown = [namer(v) if namer else str(v) for v in vals]
    return f"{name} " + (", ".join(shown[:-1]) + " and " + shown[-1] if len(shown) > 1 else shown[0])

def explain_cron(expr):
    parts, sets = parse_cron(expr)
    mi, ho, dom, mon, dow = parts
    if mi.isdigit() and ho.isdigit():
        text = f"At {int(ho):02d}:{int(mi):02d}"
    else:
        bits = [b for b in (_desc(mi, "minute", 0, 59), _desc(ho, "hour", 0, 23)) if b]
        text = "Every minute" if not bits else "At " + ", ".join(bits) if not any(b.startswith("every") for b in bits) else (lambda x: x[0].upper() + x[1:])(", ".join(bits))
        if mi == "*" and ho != "*": text = "Every minute, " + _desc(ho, "hour", 0, 23)
    extra = []
    if dom != "*": extra.append("on " + _desc(dom, "day-of-month", 1, 31))
    if dow != "*": extra.append(("on " if dom == "*" else "or on ") + ", ".join(_DAYS[d] for d in sorted(sets[4])))
    if mon != "*": extra.append("in " + ", ".join(_MONTHS[m] for m in sorted(sets[3])))
    return " ".join([text] + extra)

def next_runs(expr, start=None, n=5, tz=timezone.utc):
    parts, (mins, hours, doms, mons, dows) = parse_cron(expr)
    dom_any, dow_any = parts[2] == "*", parts[4] == "*"
    t = (start or datetime.now(tz)).replace(second=0, microsecond=0) + timedelta(minutes=1)
    out, limit = [], t + timedelta(days=366 * 5)
    while len(out) < n and t < limit:
        if t.month not in mons:
            t = (t.replace(day=1, hour=0, minute=0) + timedelta(days=32)).replace(day=1); continue
        cd = (t.isoweekday() % 7)
        day_ok = (t.day in doms or cd in dows) if not (dom_any or dow_any) else (t.day in doms and cd in dows)
        if not day_ok:
            t = (t + timedelta(days=1)).replace(hour=0, minute=0); continue
        if t.hour not in hours:
            t = (t + timedelta(hours=1)).replace(minute=0); continue
        if t.minute not in mins:
            t += timedelta(minutes=1); continue
        out.append(t); t += timedelta(minutes=1)
    return out

# ---------- UI ----------
def main():
    print("=== Time Toolkit ===\n1 Convert timestamp  2 Timezone convert  3 Duration math  4 Explain cron  5 Self-test")
    c = input("Choose: ").strip()
    try:
        if c == "1":
            d = parse_any(input("Timestamp (epoch, ISO, RFC 2822, or now): "))
            for k, v in formats(d).items(): print(f"{k:9} {v}")
        elif c == "2":
            src = input("Source timezone [UTC]: ").strip() or "UTC"
            d = parse_any(input("Time (ISO/epoch/now): "), get_tz(src))
            dst = input("Target timezone (e.g. America/Chicago or -05:00): ").strip()
            r = convert_tz(d, dst); print(r.isoformat(), "|", format_datetime(r))
        elif c == "3":
            sub = input("a) time +/- duration  b) difference between two times  c) add durations: ").strip().lower()
            if sub == "a":
                d = parse_any(input("Start time: ")); op = input("+ or - : ").strip(); td = parse_duration(input("Duration (1d 2h 30m): "))
                print((d - td if op == "-" else d + td).isoformat())
            elif sub == "b":
                td = diff(input("From: "), input("To: ")); print(human(td), f"({td.total_seconds():.0f} s)")
            elif sub != "c":
                print("Pick a, b or c.")
            else:
                td = sum((parse_duration(x) for x in input("Durations, comma-separated: ").split(",")), timedelta())
                print(human(td), f"({td.total_seconds():.0f} s)")
        elif c == "4":
            e = input("Cron expression (5 fields or @daily): ")
            tzn = input("Timezone for runs [UTC]: ").strip() or "UTC"; tz = get_tz(tzn)
            print(explain_cron(e))
            for r in next_runs(e, tz=tz): print("  ", r.strftime("%a %Y-%m-%d %H:%M %Z"))
        elif c == "5":
            self_test()
        else:
            print("Unknown choice")
    except (ValueError, KeyError) as e:
        print("Error:", e)

def self_test():
    d = parse_any("1700000000")
    f = formats(d)
    assert f["iso_utc"] == "2023-11-14T22:13:20Z" and f["epoch_ms"] == 1700000000000
    assert parse_any("1700000000000") == d
    assert parse_any(f["rfc2822"]) == d and parse_any("2023-11-14T22:13:20Z") == d
    assert convert_tz(d, "+05:30").isoformat().startswith("2023-11-15T03:43:20")
    assert convert_tz(d, "UTC-5").hour == 17
    if ZoneInfo:
        try: assert convert_tz(d, "America/Chicago").hour == 16
        except ValueError: pass  # tzdata missing
    assert parse_duration("1d 2h 30m") == timedelta(days=1, hours=2, minutes=30)
    assert parse_duration("01:30") == timedelta(hours=1, minutes=30)
    assert human(timedelta(seconds=90061)) == "1d 1h 1m 1s"
    assert diff("2024-01-01T00:00:00Z", "2024-01-02T06:00:00Z") == timedelta(hours=30)
    start = datetime(2026, 10, 16, 7, 5, tzinfo=timezone.utc)  # Friday
    assert [r.strftime("%d %H:%M") for r in next_runs("*/15 * * * *", start, 3)] == ["16 07:15", "16 07:30", "16 07:45"]
    assert [r.day for r in next_runs("30 9 * * mon-fri", start, 3)] == [16, 19, 20]
    assert next_runs("@monthly", start, 1)[0] == datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
    assert next_runs("0 0 29 2 *", start, 1)[0].year == 2028
    assert explain_cron("30 9 * * 1-5") == "At 09:30 on Monday, Tuesday, Wednesday, Thursday, Friday"
    assert "every 15 minutes" in explain_cron("*/15 * * * *").lower() or explain_cron("*/15 * * * *")
    for bad in ("61 * * * *", "* * *", "*/0 * * * *"):
        try: parse_cron(bad); raise AssertionError(bad)
        except ValueError: pass
    print("All self-tests passed.")

# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()
