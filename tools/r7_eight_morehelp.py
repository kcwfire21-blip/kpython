# KPython help for the 6 Tools > More buttons (Dev tools, Terminal, Job tracker, GitHub browser, Loan calc, Rent check), in r6_eight_help format; mergeable via MORE_ENTRIES.
"""Stdlib-only. Each More button runs a snippet from snippets.js (matched by name prefix) as a new script in the Code tab.
Merge into r6:  from r7_eight_morehelp import MORE_ENTRIES  (replaces r6's 6 generic More entries by label)."""

# (label, purpose, how to use, example, keywords)
_RAW = [
 ("🛠 Dev tools",
  "Menu of quick dev helpers: regex tester, JSON format/validate, Base64/URL codec, hashes, UUID + timestamps, Python syntax check.",
  "Tools > 🛠 More > 🛠 Dev tools. Pick 1 Regex tester (Pattern:, then text ending with a '.' line), 2 JSON format/validate (paste, end with '.'), "
  "3 Base64 / URL codec (1 b64 encode, 2 b64 decode, 3 url encode, 4 url decode, then Text:), 4 Hashes (md5/sha1/sha256/sha512 of Text:), "
  "5 UUID + timestamps (new UUID4, current Unix time, optional timestamp to convert), 6 Python syntax check (paste code, end with '.'). q quits.",
  "Pick 4, type 'hello' to see its md5, sha1, sha256 and sha512.",
  "regex json base64 url encode decode hash md5 sha256 uuid timestamp syntax check toolkit"),
 ("⌨️ Terminal",
  "Unix-style shell for the app's files under /home/pyodide: ls, cd, cat, edit, mkdir, rm, cp, mv, grep, find, run Python, pip install.",
  "Tools > 🛠 More > ⌨️ Terminal. At the '~ $' prompt type commands: pwd, cd, ls [-l -a], cat, echo, mkdir, touch, rm, cp, mv, head, tail, wc, "
  "grep <text> [files], find [dir] -name <pattern>, edit/nano/vi <file>, python <file>, pip install <pkg>, pip list, clear, help, exit. "
  "Use > or >> to send output to a file and && to chain commands. rm and overwrites ask (y/n). In the editor: p print, a append (end with '.'), "
  "'N text' replace line N, dN delete, iN insert before N, w save, q quit.",
  "echo hello > notes.txt && cat notes.txt",
  "terminal shell command line ls cd files grep find edit nano pip"),
 ("💼 Job tracker",
  "Tracks job applications (company, role, pay, status, date) in /home/pyodide/job_apps.json and lists follow-ups due.",
  "Tools > 🛠 More > 💼 Job tracker. Menu: 1 Add (Company:, Role:, Pay (optional):; status starts as applied, dated today), 2 List, "
  "3 Update (pick a number, then a status: applied, interview, offer, rejected, withdrawn), 4 Follow-ups (still 'applied' after 7+ days), 5 Quit.",
  "1, then Bunzl / Order Selector / $19.75; a week later 4 lists it as a follow-up.",
  "job application tracker apply status interview follow up hiring"),
 ("🐙 GitHub browser",
  "Read-only browser for public GitHub repos (no login): search repos, browse folders, view files, save them under /home/pyodide/repos, optionally run a .py.",
  "Tools > 🛠 More > 🐙 GitHub browser. Enter owner/repo or a github.com URL, '?' (or Enter) to search, q to quit. In a repo: <number> opens a folder or views a file, "
  ".. goes up, s <number> saves that file, sa saves the current folder (up to 200 files, each under 1 MB), r runs the last viewed file after you type 'yes', q leaves the repo.",
  "Type psf/requests, then the number of README.md to view it, then s with that number to save it.",
  "github repo browse public read only search download save view"),
 ("🏦 Loan calc",
  "Loan payment calculator: monthly payment, total paid, total interest, and an optional yearly amortization schedule.",
  "Tools > 🛠 More > 🏦 Loan calc. Answer Loan amount ($):, Annual interest rate (%):, Term in years: (100 or less; $, commas and % are ignored). "
  "Then answer y to 'Show yearly schedule?' for principal, interest and balance per year.",
  "$10,000 at 7% for 5 years: monthly payment $198.01, total interest about $1,880.",
  "loan payment interest mortgage car amortization schedule finance"),
 ("🏠 Rent check",
  "Rent affordability and move-in cost check: monthly housing total, share of income, 30% rule, landlord 3x-rent check, and move-in cash needed.",
  "Tools > 🛠 More > 🏠 Rent check. Answer each prompt or press Enter for the default in brackets: income, rent [1100], monthly fees [0], pet rent [0], "
  "utilities [150], deposit [= rent], application fee(s) [50], one-time pet fee [0], moving costs [200]. Verdict: Comfortable (30% or less), Tight (40% or less), Risky.",
  "Income 3600, rent 1100, other defaults: $1,250/mo (34.7%, Tight), 3x check PASS, move-in total $2,450.",
  "rent afford affordability apartment housing deposit move in budget landlord 3x"),
]

ENTRIES = [dict(label=l, tab="Tools", purpose=p, how=h, example=e, keywords=k) for l, p, h, e, k in _RAW]
MORE_ENTRIES = ENTRIES  # export name for merging into r6_eight_help


def _norm(s):
    return " ".join((s or "").lower().split())


def get(label):
    """Return the entry with this label (exact, or without the emoji, case-insensitive), else None."""
    q = _norm(label)
    for e in ENTRIES:
        if _norm(e["label"]) == q or _norm(e["label"]).split(" ", 1)[-1] == q:
            return e
    return None


def search(query):
    """Entries containing every word of query; label/keyword hits rank first."""
    words = _norm(query).split()
    if not words:
        return []
    hits = []
    for i, e in enumerate(ENTRIES):
        text = _norm(" ".join(e.values()))
        if all(w in text for w in words):
            hits.append((-sum(3 * (w in _norm(e["label"])) + 2 * (w in e["keywords"]) for w in words), i, e))
    return [e for _, _, e in sorted(hits)]


def show(e):
    return f"[{e['tab']}] {e['label']}\n  What: {e['purpose']}\n  How: {e['how']}\n  Example: {e['example']}\n"


def main():
    print(f"KPython More-tools help: {len(ENTRIES)} tools. Type a keyword, 'list' for all, Enter to quit.")
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
        else:
            hits = search(q)
            print("\n".join(show(e) for e in hits) if hits else "No matches. Try 'list'.")


def _self_test():
    labels = ["🛠 Dev tools", "⌨️ Terminal", "💼 Job tracker", "🐙 GitHub browser", "🏦 Loan calc", "🏠 Rent check"]
    assert [e["label"] for e in ENTRIES] == labels and MORE_ENTRIES is ENTRIES
    for lab in labels:
        e = get(lab)
        assert e and e["tab"] == "Tools" and all(e[k] for k in ("purpose", "how", "example", "keywords"))
        assert e in search(lab.split(" ", 1)[1])
    for q, want in [("sha256", "🛠 Dev tools"), ("grep", "⌨️ Terminal"), ("interview", "💼 Job tracker"),
                    ("public repo", "🐙 GitHub browser"), ("amortization", "🏦 Loan calc"), ("deposit", "🏠 Rent check")]:
        assert search(q)[0]["label"] == want, q
    assert get("loan calc")["label"] == "🏦 Loan calc" and get("nope") is None and search("") == []
    print("self-test OK: 6/6 entries present and searchable")


# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    import sys
    _self_test() if "--selftest" in sys.argv else main()
