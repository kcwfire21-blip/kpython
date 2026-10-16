# Dyno: regex tester - enter pattern, flags, sample text; shows matches, groups, sub() preview, plus a cheat sheet. Stdlib only, no file access.
import re

CHEAT = """Regex cheat sheet
 .  any char      \\d digit      \\w word char   \\s space
 ^  start         $  end         \\b word edge
 *  0+   +  1+    ?  0/1         {m,n} m to n   *? lazy
 [abc] set   [^abc] not   (a|b) or   (...) group   (?P<name>...) named
 (?:...) non-capturing   (?=...) lookahead   (?!...) neg lookahead
Flags: i=IGNORECASE m=MULTILINE s=DOTALL x=VERBOSE
sub() refs: \\1 or \\g<name>"""

FLAGMAP = {"i": re.I, "m": re.M, "s": re.S, "x": re.X}

def parse_flags(s):
    f = 0
    for ch in s.lower():
        if ch in FLAGMAP:
            f |= FLAGMAP[ch]
        elif ch.strip():
            raise ValueError("Unknown flag: " + ch)
    return f

def analyze(pattern, flags, text, repl=None):
    # KPython: ReDoS guard. Caps sizes and warns on nested quantifiers; it runs in the worker, so Stop can kill it.
    if len(pattern) > 2000 or len(text) > 100_000: raise ValueError("pattern max 2000 chars, text max 100 KB")
    if re.search(r"\((?:[^()\\]|\\.)*[+*}]\)[+*{]", pattern): print("Warning: nested quantifier like (a+)+ can be very slow (ReDoS). Tap Stop if it hangs.")
    rx = re.compile(pattern, flags)
    out = []
    ms = list(rx.finditer(text))
    out.append(f"{len(ms)} match(es)")
    for n, m in enumerate(ms, 1):
        out.append(f"#{n} {m.group(0)!r} at {m.start()}-{m.end()}")
        for i, g in enumerate(m.groups(), 1):
            out.append(f"   group {i}: {g!r}")
        for k, v in m.groupdict().items():
            out.append(f"   {k}: {v!r}")
    if repl is not None:
        out.append("sub() preview: " + repr(rx.sub(repl, text)))
    return out

def self_test():
    r = analyze(r"(?P<n>\d+)", 0, "a1 b22")
    assert r[0] == "2 match(es)" and "'22'" in r[4], r
    assert analyze(r"x", parse_flags("i"), "X")[0] == "1 match(es)"
    assert analyze(r"(\w)(\d)", 0, "a1", r"\2\1")[-1] == "sub() preview: '1a'"
    try:
        parse_flags("q"); assert False
    except ValueError:
        pass
    print("self-tests passed")

def main():
    print("== Regex Tester ==  (type ? for cheat sheet, t for self-test)")
    while True:
        p = input("\nPattern (blank or q to quit): ")
        if not p or p.strip().lower() in ("q", "quit"): break
        if p == "?": print(CHEAT); continue
        if p == "t": self_test(); continue
        try:
            flags = parse_flags(input("Flags (i m s x, blank for none): "))
            text = input("Sample text (use \\n for newline): ").replace("\\n", "\n")
            r = input("Replacement for sub() (blank to skip): ")
            for line in analyze(p, flags, text, r if r else None):
                print(line)
        except (re.error, ValueError) as e:
            print("Error:", e)

# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()
