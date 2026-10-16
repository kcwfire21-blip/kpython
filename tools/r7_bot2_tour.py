# bot2: Getting Started Tour - a 10-step walkthrough of KPython's top features (Enter for next, b for back, q to quit).
STEPS = [
 ("Welcome", "KPython runs real Python right on your phone. Nothing is uploaded. Tip: tap Share, then 'Add to Home Screen' so it opens full screen and keeps your data safer.",
  None),
 ("Your first script", "In the Code tab, tap ＋ for a new script, type your code, and tap ▶ Run. Output appears below the editor.",
  "print('hi')"),
 ("The keys bar", "The extra-keys row above the keyboard gives you Tab, brackets, quotes, and colons so you can type code fast.",
  "for i in range(3):\n    print(i)"),
 ("Asking for input", "input() shows a box in the output area. Type your answer there.",
  "n = input('Name? ')\nprint('hey', n)"),
 ("Reading errors", "Errors show in red with a plain-English hint about what went wrong.",
  "1/0"),
 ("Stopping a stuck script", "If a script never ends, tap ⏹ Stop. It should stop within about a second.",
  "while True:\n    pass"),
 ("Packages", "Open 📦 Packages to install extra libraries, then import them like normal.",
  "import six\nprint(six.__version__)"),
 ("Dev tools", "The Dev tab has tools like Lint, Format, Outline, Debug, Run tests, and 🔑 Secret scan. Use Save version and History to keep snapshots of your code.",
  None),
 ("Save and back up", "Tap 💾 to save. In Files, ⬇️ Export makes a backup file of all your scripts. Import it to restore. Don't put passwords or tokens in scripts; they're stored as plain text.",
  None),
 ("Offline and fun", "Once the badge says '✈️ Offline ready', KPython works in Airplane Mode. Take a break in the Fun tab with Snake or 2048.",
  "print('offline')"),
]

def render(i):
    title, text, ex = STEPS[i]
    out = f"\n[{i+1}/{len(STEPS)}] {title}\n{text}"
    if ex:
        out += "\nTry this:\n" + "\n".join("    " + l for l in ex.splitlines())
    return out

def next_index(i, key):
    key = key.strip().lower()
    if key == "q": return None
    if key == "b": return max(0, i - 1)
    return i + 1

def run(read=input, write=print):
    i = 0
    write("KPython Getting Started Tour")
    while i is not None and i < len(STEPS):
        write(render(i))
        i = next_index(i, read("\nEnter = next, b = back, q = quit: "))
    write("Tour finished. Have fun coding!" if i is not None else "Tour closed. Run it again anytime.")
    return i

def self_test():
    import ast
    assert len(STEPS) == 10
    for t, txt, ex in STEPS:
        assert t and txt
        if ex: ast.parse(ex)
    assert "[1/10] Welcome" in render(0) and "Try this" in render(1)
    assert next_index(3, "") == 4 and next_index(0, "b") == 0 and next_index(5, "Q") is None
    log = []
    assert run(lambda _p, it=iter([""] * 10): next(it), log.append) == 10 and "Tour finished" in log[-1]
    log = []
    assert run(lambda _p, it=iter(["", "b", "q"]): next(it), log.append) is None and "closed" in log[-1]
    print("Self-tests passed.")

def main():
    run()

# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()
