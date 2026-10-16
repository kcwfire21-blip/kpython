# KPython iPhone test (about 10 minutes)

Open Safari on your iPhone and go to https://kcwfire21-blip.github.io/kpython/. Do each step and check that what you see matches **Expect**. If something doesn't match, take a screenshot and send it to a bot.

1. **Open the app.** Load the page and wait.
   **Expect:** the passcode screen shows. After you unlock, the header shows a Python version pill, and the badge changes from "⏳ Caching…" to "✈️ Offline ready".
2. **Add to Home Screen.** Tap Share, then "Add to Home Screen", then open KPython from the new icon.
   **Expect:** it opens full screen with no Safari address bar.
3. **Hello world.** In the Code tab, tap ＋ to make a new script. Type `print('hi')` and tap ▶ Run straight away.
   **Expect:** `hi` prints. Run it 3 times; it should print every time.
4. **Typing in the editor.** Use the extra-keys row to type `for i in range(3):`, then a new line and `print(i)`.
   **Expect:** the keys bar stays right above the keyboard and nothing is cut off. Run prints 0, 1, 2.
5. **input().** Run `n = input('Name? '); print('hey', n)`.
   **Expect:** an input box appears in the output area, not a popup. Type your name and it prints `hey <name>`.
6. **Error message.** Run `1/0`.
   **Expect:** a red `ZeroDivisionError` and a plain-English hint.
7. **Stop.** Run `while True: pass`, wait 2 seconds, then tap ⏹ Stop.
   **Expect:** it stops within about 1 second, and running `print('ok')` afterward works.
8. **Install a package.** Open 📦 Packages, type `six`, and install it. Then run `import six; print(six.__version__)`.
   **Expect:** a version number prints.
9. **Prompts show without pressing Enter.** Open Dev → 📦 Packages.
   **Expect:** the menu shows right away. You shouldn't have to press Enter to see it.
10. **A Dev tool.** Open Dev → 🔑 Secret scan on your script.
    **Expect:** it finishes with no errors (it says no secrets found).
11. **Saving survives a reload.** Save your test script with 💾, close the app completely, then open it again.
    **Expect:** after you unlock, your script is still there with its code.
12. **Offline.** Turn on Airplane Mode, open the app, and run `print('offline')`.
    **Expect:** it loads and prints `offline`.
13. **Backup.** In Files, tap ⬇️ Export and save the file to the Files app.
    **Expect:** a `kpython-backup-….json` file is saved. Import it again and it says "Imported N scripts".
14. **Game check.** In the Fun tab, play Snake or 2048 for 10 seconds.
    **Expect:** swiping or tapping moves the pieces, and the page doesn't scroll or zoom.
15. **Clean up.** Delete the test script in Files (🗑).
    **Expect:** it's gone, and your other scripts are untouched.

**Tell the bots:** list the step numbers that failed, your iPhone model and iOS version (Settings → General → About), and any screenshots.
