# Dev task board: scans scripts for TODO/FIXME/HACK/XXX, plus manual tasks with priority and done state, saved to /home/pyodide/.tasks.json.
"""Stdlib-only task board for KPython."""
import json
import os
import re
import time

SAFE_ROOT = "/home/pyodide"
MAX_BYTES = 500 * 1024
PRIORITIES = ("high", "med", "low")
TAG_RE = re.compile(r"#\s*(TODO|FIXME|HACK|XXX|BUG)\b[:\s-]*(.*)", re.I)

try:
    kp_safe_path  # provided by the KPython app
except NameError:
    def kp_safe_path(path):
        """Fallback: resolve path and refuse anything outside /home/pyodide."""
        full = os.path.realpath(os.path.join(SAFE_ROOT, path))
        if not (full == SAFE_ROOT or full.startswith(SAFE_ROOT + os.sep)):
            raise ValueError(f"Only paths under {SAFE_ROOT} are allowed.")
        return full

TASKS_FILE = ".tasks.json"


def load_tasks(path=TASKS_FILE):
    """Load the task list; returns [] if missing or unreadable."""
    full = kp_safe_path(path)
    if not os.path.exists(full):
        return []
    if os.path.getsize(full) > MAX_BYTES:
        raise ValueError("Task file over 500KB.")
    try:
        with open(full, encoding="utf-8") as f:
            data = json.load(f)
        # KPython: keep only well-formed tasks so a hand-edited file can't crash the board
        return [t for t in data if isinstance(t, dict) and isinstance(t.get("id"), int) and isinstance(t.get("text"), str)] if isinstance(data, list) else []
    except (OSError, ValueError):
        print("Warning: task file unreadable; starting fresh (not overwritten until you save).")
        return []


def save_tasks(tasks, path=TASKS_FILE):
    """Write tasks as JSON (the task file is the board's own storage)."""
    full = kp_safe_path(path)
    blob = json.dumps(tasks, indent=1)
    if len(blob.encode()) > MAX_BYTES:
        raise ValueError("Task list would exceed 500KB.")
    tmp = full + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(blob)
    os.replace(tmp, full)


def _next_id(tasks):
    return max([t["id"] for t in tasks] + [0]) + 1


def add_task(tasks, text, priority="med", source=None):
    """Add a task; skips duplicates from the same source line. Returns the task or None."""
    priority = priority if priority in PRIORITIES else "med"
    for t in tasks:
        if source and t.get("source") == source and t["text"] == text:
            return None
    t = {"id": _next_id(tasks), "text": text.strip()[:300], "priority": priority,
         "done": False, "source": source, "created": time.strftime("%Y-%m-%d")}
    tasks.append(t)
    return t


def scan_code(code, filename="<code>"):
    """Return [(line, tag, text)] for TODO-style comments in code."""
    found = []
    for n, line in enumerate(code.splitlines(), 1):
        m = TAG_RE.search(line)
        if m:
            found.append((n, m.group(1).upper(), m.group(2).strip() or "(no description)"))
    return found


def scan_files(tasks, folder="."):
    """Scan .py files under folder (inside /home/pyodide) and add new TODO items. Returns count added."""
    root = kp_safe_path(folder)
    added = 0
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            if not name.endswith(".py"):
                continue
            full = os.path.join(dirpath, name)
            # KPython: skip symlinks and anything that resolves outside the scanned folder
            if os.path.islink(full) or not os.path.realpath(full).startswith(os.path.realpath(root) + os.sep):
                continue
            if os.path.getsize(full) > MAX_BYTES:
                continue
            try:
                with open(full, encoding="utf-8", errors="replace") as f:
                    code = f.read()
            except OSError:
                continue
            rel = os.path.relpath(full, SAFE_ROOT)
            for ln, tag, text in scan_code(code, rel):
                pri = "high" if tag in ("FIXME", "BUG") else "med"
                if add_task(tasks, f"{tag}: {text}", pri, f"{rel}:{ln}"):
                    added += 1
    return added


def set_done(tasks, task_id, done=True):
    """Mark a task done/undone. Returns True if found."""
    for t in tasks:
        if t["id"] == task_id:
            t["done"] = done
            return True
    return False


def remove_task(tasks, task_id):
    """Delete a task by id. Returns True if removed."""
    before = len(tasks)
    tasks[:] = [t for t in tasks if t["id"] != task_id]
    return len(tasks) < before


def board(tasks, show_done=False):
    """Return the board as text, sorted by done, priority, id."""
    order = {p: i for i, p in enumerate(PRIORITIES)}
    rows = sorted((t for t in tasks if show_done or not t["done"]),
                  key=lambda t: (t["done"], order.get(t["priority"], 1), t["id"]))
    if not rows:
        return "No tasks. 🎉"
    out = []
    for t in rows:
        box = "[x]" if t["done"] else "[ ]"
        src = f"  ({t['source']})" if t.get("source") else ""
        out.append(f"{t['id']:>3} {box} {t['priority'].upper():<4} {t['text']}{src}")
    left = sum(1 for t in tasks if not t["done"])
    out.append(f"\n{left} open / {len(tasks)} total")
    return "\n".join(out)


def _self_test():
    tasks = []
    found = scan_code("x = 1  # TODO: fix this\n# fixme crash on empty\ny = 'TODO not a comment'\n")
    assert found == [(1, "TODO", "fix this"), (2, "FIXME", "crash on empty")], found
    a = add_task(tasks, "Write tests", "high")
    assert a["id"] == 1 and add_task(tasks, "Ship", "bogus")["priority"] == "med"
    assert add_task(tasks, "TODO: x", "med", "a.py:1") and add_task(tasks, "TODO: x", "med", "a.py:1") is None
    assert set_done(tasks, 1) and "[x]" in board(tasks, True) and "Write tests" not in board(tasks)
    assert remove_task(tasks, 2) and len(tasks) == 2
    try:
        kp_safe_path("../../etc/passwd")
        raise AssertionError("path escape")
    except ValueError:
        pass
    print("Self-tests passed.")


MENU = """
1) Show board   2) Show all (incl. done)   3) Add task   4) Mark done
5) Mark not done   6) Delete task   7) Scan .py files for TODO/FIXME   8) Save & quit   9) Quit without saving"""


def main():
    """Interactive task board."""
    _self_test()
    tasks = load_tasks()
    dirty = False
    while True:
        print(MENU)
        try:
            c = input("Choose: ").strip()
        except (EOFError, KeyboardInterrupt):
            c = "9"
        try:
            if c == "1":
                print(board(tasks))
            elif c == "2":
                print(board(tasks, True))
            elif c == "3":
                text = input("Task: ").strip()
                if text:
                    while True:  # KPython: reject anything but high/med/low
                        pri = input("Priority (high/med/low) [med], q = cancel: ").strip().lower() or "med"
                        if pri in PRIORITIES or pri == "q": break
                        print("Type high, med or low.")
                    if pri == "q": print("Not added."); continue
                    if pri == "q": print("Not added."); continue
                    if pri == "q": print("Not added."); continue
                    print("Added #%d" % add_task(tasks, text, pri)["id"])
                    dirty = True
            elif c in ("4", "5", "6"):
                s = input("Task id (blank = back): ").strip()
                if not s: continue
                if not s.isdigit(): print("Enter a task id number."); continue
                tid = int(s)
                if c == "6":
                    ok = input(f"Delete #{tid}? (y/N): ").strip().lower() in ("y", "yes") and remove_task(tasks, tid)
                else:
                    ok = set_done(tasks, tid, c == "4")
                print("OK" if ok else "No change.")
                dirty = dirty or bool(ok)
            elif c == "7":
                folder = input("Folder under /home/pyodide [.]: ").strip() or "."
                n = scan_files(tasks, folder)
                print(f"Added {n} new item(s).")
                dirty = dirty or n > 0
            elif c == "8":
                if dirty or not os.path.exists(kp_safe_path(TASKS_FILE)):
                    if input(f"Save to {kp_safe_path(TASKS_FILE)}? (y/N): ").strip().lower() in ("y", "yes"):
                        save_tasks(tasks)
                        print("Saved.")
                break
            elif c == "9":
                if dirty and input("Unsaved changes. Quit anyway? (y/N): ").strip().lower() not in ("y", "yes"):
                    continue
                break
            elif c:
                print("Pick 1-9.")
        except (ValueError, OSError) as e:
            print(f"Error: {e}")


# --- KPython v9: shared hardening (size caps + path checks before use) lives in kp_common.py ---
try:
    from kp_common import harden as _kp_harden
    _kp_harden(globals())
except ImportError:  # running outside KPython
    pass

if __name__ == "__main__":
    main()
