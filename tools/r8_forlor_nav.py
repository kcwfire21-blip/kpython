# KPython r8 nav helpers: Cancel/blank = back in inner menus, Cancel/q = clean exit at top (builds on kp_common).
"""Composable navigation helpers for KPython tools (stdlib only).

Reuses kp_common.ask / yes / pick_index / read_paste / is_quit when available;
falls back to tiny local copies so this file also runs standalone.

    from r8_forlor_nav import ask, confirm, choose, paste, run_menu, run_tool, Back, Quit, need
"""
import builtins

try:
    from kp_common import ask as _raw_ask, yes as _yes, pick_index as _pick_index, read_paste as _read_paste
except ImportError:  # tiny fallback, same behavior as kp_common
    def _raw_ask(prompt=""):
        try:
            return input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            return None

    def _yes(prompt, default=False):
        a = _raw_ask(prompt + (" (Y/n): " if default else " (y/N): "))
        return default if not a else a.lower() in ("y", "yes")

    def _pick_index(prompt, n):
        while True:
            a = _raw_ask(f"{prompt} (1-{n}, blank = back): ")
            if not a or a.lower() in ("q", "quit", "exit"):
                return None
            if a.isdigit() and 1 <= int(a) <= n:
                return int(a) - 1
            print(f"Enter a number 1-{n}, or press Enter to go back.")

    def _read_paste(end="END", prompt=None):
        if prompt:
            print(prompt)
        lines = []
        while True:
            try:
                l = input("")
            except (KeyboardInterrupt, EOFError):
                break
            if l.strip() in (end, "."):
                break
            lines.append(l)
        return "\n".join(lines)

QUIT_WORDS = ("q", "quit", "exit")


class Back(Exception):
    """Raise inside a handler to return to the menu that called it."""


class Quit(Exception):
    """Raise anywhere to leave the whole tool cleanly."""


def ask(prompt=""):
    """Stripped answer, or None on blank or Cancel/EOF."""
    a = _raw_ask(prompt)
    return a or None


def need(prompt=""):
    """Like ask() but raises Back on blank/Cancel, so a multi-step flow unwinds in one line."""
    a = ask(prompt)
    if a is None:
        raise Back()
    return a


def confirm(prompt):
    """y/N, defaults to No; Cancel = No."""
    return _yes(prompt, default=False)


def choose(prompt, items, label=str):
    """Show items 1..N and return the chosen item, or None for blank/q/Cancel. Re-prompts on bad input."""
    items = list(items)
    if not items:
        print("(nothing to choose from)")
        return None
    for i, it in enumerate(items, 1):
        print(f"  {i}) {label(it)}")
    i = _pick_index(prompt, len(items))
    return None if i is None else items[i]


def paste(prompt="Paste text, then a line with only END:", end="END"):
    """Read lines until END (or '.'), Cancel or EOF. Returns the text (maybe empty)."""
    return _read_paste(end=end, prompt=prompt)


def run_menu(title, options, top=False, prompt="> "):
    """Run a menu loop.

    options: list of (label, handler) -> numbered 1..N, or (key, label, handler) for letter keys.
    Inner menu: blank or Cancel returns (back one level); q raises Quit.
    Top menu (top=True): Cancel or q returns (clean exit); blank re-shows the menu.
    A handler may raise Back (stay here), Quit (leave tool) or hit a raw Cancel (treated as Back).
    """
    entries = []
    for n, opt in enumerate(options, 1):
        key, label, fn = (str(n), *opt) if len(opt) == 2 else opt
        entries.append((str(key).lower(), label, fn))
    keys = [k for k, _, _ in entries]
    hint = "q = quit" if top else "blank = back, q = quit"
    while True:
        print(f"\n{title}")
        for k, label, _ in entries:
            print(f"  {k}) {label}")
        a = _raw_ask(f"{prompt}({hint}) ") if prompt.endswith(" ") else _raw_ask(prompt)
        if a is None:                      # Cancel / EOF
            return
        if a == "":
            if top:
                continue
            return
        a = a.lower()
        if a in QUIT_WORDS:
            if top:
                return
            raise Quit()
        fn = next((f for k, _, f in entries if k == a), None)
        if fn is None:
            print(f"Pick {', '.join(keys)}" + (" or q." if top else ", blank to go back, or q."))
            continue
        try:
            fn()
        except Back:
            pass
        except KeyboardInterrupt:          # a raw input() inside the handler was cancelled
            print("(cancelled)")
        except Quit:
            if top:
                return
            raise


def run_tool(main_fn, *a, **k):
    """Call a tool's main() so Quit, Cancel and EOF end it with one line instead of a traceback."""
    try:
        return main_fn(*a, **k)
    except (Quit, Back):
        pass
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
    return None


# ---------------- self-test ----------------
def self_test():
    import io, contextlib

    CANCEL = object()
    old = builtins.input

    def feed(answers):
        it = iter(answers)
        def fake(p=""):
            v = next(it, CANCEL)
            if v is CANCEL:
                raise KeyboardInterrupt("input cancelled")
            if v is EOF:
                raise EOFError()
            return v
        builtins.input = fake

    EOF = object()
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            # ask / need / confirm
            feed(["  hi "]); assert ask("x") == "hi"
            feed([""]); assert ask("x") is None
            feed([CANCEL]); assert ask("x") is None
            feed([EOF]); assert ask("x") is None
            feed([""])
            try: need("x"); raise AssertionError("need")
            except Back: pass
            for ans, exp in (("", False), (" YES ", True), ("y", True), ("yeah", False), ("n", False), (CANCEL, False)):
                feed([ans]); assert confirm("ok?") is exp, ans

            # choose: bad, 0, out of range, then valid; blank/cancel -> None
            feed(["abc", "0", "-1", "9", "2"]); assert choose("pick", ["a", "b", "c"]) == "b"
            feed([""]); assert choose("pick", ["a"]) is None
            feed([CANCEL]); assert choose("pick", ["a"]) is None
            feed(["q"]); assert choose("pick", ["a"]) is None
            assert choose("pick", []) is None

            # paste: END, '.', Cancel, EOF
            feed(["a", "b", "END"]); assert paste() == "a\nb"
            feed(["a", "."]); assert paste() == "a"
            feed(["a", "", CANCEL]); assert paste() == "a\n"
            feed(["a", EOF]); assert paste() == "a"

            # nested menus
            log = []
            def inner():
                run_menu("Inner", [("one", lambda: log.append("i1")),
                                   ("ask", lambda: log.append(need("name: ")))])
            def raw_inner():                       # handler using raw input(); Cancel -> back
                log.append(input("raw: "))
            top = [("go inner", inner), ("raw", raw_inner), ("t", "test", lambda: log.append("t"))]

            # top: bad, blank(reshow), 1 -> inner: 1, bad, Cancel(back) ; top: t, q(quit)
            feed(["zz", "", "1", "1", "7", CANCEL, "T", "q"])
            run_menu("Top", top, top=True); assert log == ["i1", "t"], log

            # inner blank = back; inner need() blank -> Back -> stays in inner; then Cancel inner, Cancel top
            log.clear(); feed(["1", "2", "", "2", "bob", "", CANCEL])
            run_menu("Top", top, top=True); assert log == ["bob"], log

            # q inside inner quits the whole tool
            log.clear(); feed(["1", "q", "t"])
            run_menu("Top", top, top=True); assert log == [], log

            # raw input() Cancel inside handler -> back to top, menu continues
            log.clear(); feed(["2", CANCEL, "t", "quit"])
            run_menu("Top", top, top=True); assert log == ["t"], log

            # EOF at top exits; Cancel at top exits
            feed([EOF]); run_menu("Top", top, top=True)
            feed([CANCEL]); run_menu("Top", top, top=True)

            # run_tool swallows Cancel/Quit
            def boom(): raise KeyboardInterrupt
            def q(): raise Quit
            assert run_tool(boom) is None and run_tool(q) is None and run_tool(lambda: 5) == 5
    finally:
        builtins.input = old
    print("r8_forlor_nav self-tests passed.")
    return True


def main():
    a = ask("r8 nav helpers. t = self-test, d = demo menu, blank = quit: ")
    if a is None:
        return
    if a.lower() == "t":
        self_test(); return
    if a.lower() == "d":
        items = ["apple", "banana", "cherry"]
        def pick():
            it = choose("Fruit", items)
            print("You picked:", it if it else "(back)")
        def sub():
            run_menu("Submenu", [("say hi", lambda: print("hi")),
                                 ("delete demo", lambda: print("Deleted." if confirm("Delete?") else "Kept."))])
        def pst():
            print(f"Got {len(paste())} chars.")
        run_menu("Demo (Cancel or q exits)", [("Pick a fruit", pick), ("Submenu", sub), ("Paste", pst)], top=True)



# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    run_tool(main)
