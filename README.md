# KPython (Keivon's Python)

KPython is a Python app for iPhone that runs inside Safari. Python runs **on the phone** through [Pyodide](https://pyodide.org) 0.26.4, so your code isn't uploaded anywhere. It's an installable web app (PWA) with an editor, a console, about 50 developer tools, everyday helper tools and a few games.

**Live app:** https://kcwfire21-blip.github.io/kpython/ · Current version: **v11** (cache `kpython-v11`)

## Install on iPhone
1. Open the live URL in **Safari**.
2. Tap Share ▸ **Add to Home Screen**, then open **KPython** from the new icon. It opens full screen, with no address bar.
3. **Passcode:** on first launch it asks you to *Create a passcode (4+ characters)*. Tap **Unlock**, and tap 🔒 to lock again.
   - The passcode is stored as a salted PBKDF2 hash.
   - It only hides the screen. It does **not** encrypt your data.
4. **Offline:** after one load with internet, a service worker caches the app, Python and its standard library. The badge changes from **⏳ Caching…** to **✈️ Offline ready**.
   - Packages you install are cached for offline use too.
   - Updates never reload the app by themselves. A bar shows *⟳ KPython update ready. Tap to reload (your scripts are saved).*
   - Each version's service worker caches and checks **its own** files: a new version installs only when every file matches its sha384 manifest.
5. **Lite start (optional, off by default):** 📁 Files ▸ ⚙️ Settings ▸ **Lite start** skips the ~6 MB Python download until your first ▶ Run (or console, package install, Python tool). The first Run then waits for the download.

`IPHONE_TEST.md` has a 15-step check you can run on a phone.

## Security model
- **Allowed sites allowlist.** Python can only connect to the defaults (the app itself, `api.github.com`, the Pyodide CDN, `pypi.org`, `files.pythonhosted.org`) plus sites you add in **🧰 Tools ▸ 🌐 Allowed sites**. The service worker enforces this through the worker's Content Security Policy.
  - **Only https.** Addresses must be `https://` with no path.
  - **Typed confirms.** Adding a site needs a typed `yes`. A raw IP also needs `IP`. Private-network addresses get a warning.
  - **Wildcard limits.** Wildcards aren't allowed on shared hosts like `*.github.io`.
  - **Script requests.** A running script may *ask* to add one site per run. You approve or decline it in a popup.
  - **Reset.** **Reset to defaults…** needs a typed `RESET`.
- **`/home/pyodide` file area.** Python files live under `/home/pyodide` and are saved in IndexedDB, so they survive restarts.
  - **`kp_safe_path` guard.** Tools resolve paths through it. It refuses paths outside `/home/pyodide` and paths through symlinks, and the app sets it again before every run.
  - **Not a true sandbox.** The code itself says `kp_safe_path` is "a guard against mistakes, not a sandbox". Code in the same interpreter can get around it. (Since v11 the app puts back `kp_safe_path` and the `os.path` functions it uses before every run, and says so if a script changed them.)
- **Verified Dev tools.** Tools are downloaded only through the service worker's manifest check and kept by the worker in JavaScript. Before **every** run they are re-written to `/kptools` and re-imported, and tool names (and any `kp_*` name) load only from there, so a file in `~` called `kp_common.py` or a tool name can't replace them. The standard library comes before `~` on `sys.path`, so `~/json.py` or `~/json/` can't shadow it either. Saved scripts and GitHub-import folders can't take those reserved names.
- **Job tokens.** Every request from Python to the app (saved scripts, Allowed sites, editor insert) carries the id of the run that made it. Code left over from an earlier run (a JS timer, a stray task) has no token and is refused; leftover tasks are cancelled, JS timers cleared, and if something still won't stop, Python is restarted.
- **GitHub token.**
  - **Token type.** The **🐙 GitHub** panel asks for a fine-grained token (Contents: Read and write only, chosen repos, 30-day expiry).
  - **Storage.** The token lives only in a JavaScript closure: not on `window`, not in storage. Python's `js` module can't reach it.
  - **When it's wiped.** On lock, reload or **Log out**.
  - **Pushing.** **⬆ Push…** shows the repo, path and branch, and needs a typed `yes`.
  - **Running downloads.** **▶ Run…** on a downloaded file asks first.
- **Confirms elsewhere.**
  - **Dev tools that run code** ask first: ✅ Run tests, ⏱ Profile, 🐞 Debug, 🧪 Coverage, 🧠 Memory.
  - **Code-changing tools** show a diff and ask before applying: ✨ Format, 📝 Docstrings.
  - **Python can only *ask*** to change saved scripts. Requests are tied to the run in progress, and the full diff opens in an app-owned sheet (closed by 🔒; nothing is applied if the run ended meanwhile).
  - **Editor insert.** 📎 Snippet library's *insert at cursor* shows the full text in an app sheet and inserts only if you tap **Insert** (max 20,000 characters, 5 per run, only from the run in progress).
  - **Files.** Deleting a script asks first and can be undone. Importing a backup asks first.
  - **🛠 More** buttons ask before opening and running a team script.
  - **⌨️ Terminal:** since v10, `python <file>` and `pip install` ask for `y` first.
  - **Packages.** Dev ▸ **📦 Packages** confirms and pins installs.
- **Other safeguards.**
  - **Pinned core.** The Pyodide core files are pinned by sha384, and `release.py` writes a sha384 manifest of every app file into `sw.js` (a git pre-commit hook runs `python3 release.py --check`). A file that doesn't match is never served.
  - **Hidden input.** Secrets typed into `input()` that look like `Authorization:` / token headers are hidden in the output.
  - **No leftover tasks.** Background tasks a run leaves behind are cancelled.

### Known caveats
- **Passcode:** it doesn't encrypt anything. Scripts, console history and History versions are plain text on the phone. Don't paste passwords or tokens into scripts; check with Dev ▸ **🔑 Secret scan**.
- **File area:** `/home/pyodide` is a guard, not a sandbox (see above).
- **Backups:** **⬇️ Export** saves scripts, tool data, History versions **and the files in `~`** (projects, SQLite databases, `.tasks.json`, `job_apps.json`, GitHub imports). It skips files over 2 MB and anything past 6 MB of files in total, and tells you which ones. Your passcode and GitHub token are never included.
- **Find bar:** **All** (replace all) has no confirm. Use editor undo.
- **Packages:** `pip`/micropip only works for pure-Python or Pyodide-built packages.

## Features by tab
- **⌨️ Code:** CodeMirror editor with an extra-keys row, **▶ Run** / **⏹ Stop**, `input()` support, **＋** new, **💾** save (it also autosaves).
  - **🔍** opens find/replace with ▲ ▼, **Replace**, **All** and **Match case**.
  - **#** goes to a line. **A− / A+** change the text size, and **↩︎** turns word wrap on or off.
  - **📤 Export this file**, **📥** import .py, **📚** snippet library.
  - The **📦 Packages** panel has **Install** and one-tap numpy / pandas / matplotlib.
- **>_ REPL:** a Python console where variables stay between commands. Saved scripts can be imported by name, and there's built-in `help()` lookup.
- **🛠 Dev:** 56 tools in these sections (Cancel at a question goes back to the tool's start; Cancel twice in a row closes it):
  - **✅ Check & test:** 🧪 Self-test all tools, 🧹 Lint (Eight's + bot2's checkers), 🧹 Quick lint (menu), ✅ Run tests, 🧪 Coverage, 🧪 Test generator, 🔤 Type check, 📏 Metrics, 🔑 Secret scan, 🛡 Dependency audit
  - **✏️ Edit & refactor:** ✨ Format, ✏️ Rename…, 🛠 Refactor, 📝 Docstrings, 📎 Snippet library, 🔍 Project search, 🔁 Find & replace in files, ✏️ Replace in saved scripts, 🔀 3-way merge, Patch…
  - **⏱ Run & measure:** 🧩 Cell runner (# %%), ⏱ Profile, 📊 Benchmark, ⏱ Compare speed, 📈 Big-O estimator, 🧠 Memory, 🐞 Debug
  - **📖 Understand & learn:** 🧭 Getting-started tour, 📘 Examples, 🗂 Outline, 📖 Explain code, 🕸 Import map, 📄 Markdown preview, ❓ Help guide, 📝 Cheat sheets, 🥋 Katas
  - **🗄 Data, web & time:** 🗄 SQL, 🌐 HTTP, 📮 API collections, 📋 Data viewer, 🧾 JSON, 📊 Charts, 📜 Log analyzer, 🕒 Time & cron, 🔎 Regex, 🔐 Encode/Hash, 🔁 Convert config, 🧩 Templates
  - **📦 Projects & files:** 📦 Projects, ⬇️ GitHub import, 📦 Packages, ✅ Task board, 🕘 Save version, 📜 History, 🔑 Passwords
  - **🧰 Other:** everything not listed above, such as Compare
  - The **🔎** command palette (Ctrl/⌘+K) searches every tool and button.
- **🧰 Tools:**
  - **🧽 Quote** (cleaning quote & invoice), **⏱ Hours** (shift pay with overtime), **💵 Budget**, **🚗 Miles** (mileage log), **🧮 Calc** (tip & split, unit converter).
  - **🐙 GitHub** (browse, edit, push), **🌐 Allowed sites**.
  - **🛠 More:** Dev tools, Terminal, Job tracker, GitHub browser (read-only), Loan calc, Rent check.
- **🎮 Fun:** 🐍 Snake, 🔢 2048, 🎯 Guess, 🎱 8-Ball, 🐢 Turtle.
- **📁 Files:** My Scripts (Open, ⧉, ✎, 🗑), **＋ New**, **📥 Import .py**, **📂 Files in ~** (everything tools saved, e.g. GitHub imports: open text files as a script or save them to the phone), 📚 Snippets, **⚙️ Settings** (Lite start).
  - Backup has **⬇️ Export**, **⬆️ Import**, **↶ Undo (last Python change or deleted script)** and **Reset all data…**.
- **Everywhere:** **📖** opens the in-app guide (sections menu at the top, Esc or ✕ closes it), the **🌓** menu sets System / Light / Dark, and **🔒** locks.

## Credits
Built by Keivon's bot team. These names appear in the app's credits line, the snippet authors and the tool file headers:
- **Kai:** coordinator: merges every round, security fixes, releases and regression tests
- **Eight:** lint, format, Markdown preview, task board, help guide, user guide, this README
- **Dyno:** tests, regex, coverage, test generator, cell runner, self-tests, find & replace in files, job tracker
- **Forlor:** HTTP, JSON, config converter, API collections, time & cron, nav helpers, snippet library, rent check
- **Drop:** diff & patch, history, packages, project search, 3-way merge, GitHub import
- **Get back:** SQL, encode/hash, secret scan, passwords, dependency audit, and security review findings cited in the code
- **bot:** projects, type check, docstrings, refactor, benchmark fixes
- **bot2:** outline/rename, templates, katas, explain code, cheat sheets, tour, examples, quick lint
- **bot2help:** data viewer, metrics, import map, charts, log analyzer self-tests, accessibility review
- **bot3:** profiler, debugger, memory profiler, compare speed, Big-O estimator, performance work, Lite start

The 📜 Log analyzer's file header doesn't name an author.
