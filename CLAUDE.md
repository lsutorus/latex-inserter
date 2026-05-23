# CLAUDE.md This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Rules
- Runtime: PowerShell 7.x (pwsh)
- Do not use legacy WMI cmdlets (use CIM instead).
- Use forward slashes `/` for paths to prevent escape-character bugs during CLI tool execution.

## What This App Does
Windows system-tray app. Hotkey Ctrl+Alt+M opens overlay near cursor. User types LaTeX (e.g. `\sqrt{x^2}`), sees Unicode preview, hits Enter → Unicode copied to clipboard and auto-pasted into previous window.

## Build & Run
```powershell
# Install deps
pip install -r requirements.txt

# Run (must be admin — keyboard hooks require elevation)
python main.py

# Build exe (generates dist/LaTeX-Inserter.exe + dist/update_helper.exe)
python build.py
```
Requires admin privileges. The `admin.manifest` forces `requireAdministrator` in the built exe. Build also requires GCC (MinGW) for compiling `update_helper.c`.

## Versioning & Release
- Version tracked in `main.py` as `__version__ = "1.0.0"` (semver)
- Bump `__version__` before tagging a release
- Tag format: `v1.0.0`. Push tag → GitHub Actions builds + publishes release
- Release assets: `LaTeX-Inserter.exe`, `update_helper.exe`, `LaTeX-Inserter.exe.sha256`
- To release: `git tag v1.x.x && git push origin v1.x.x`

## Architecture

### File layout
| File | Purpose |
|------|---------|
| `main.py` | App entry point, LaTeXOverlay, AppManager, tray menu |
| `updater.py` | Self-update logic: GitHub API check, download, SHA256 verify, helper launch, UpdateDialog |
| `update_helper.c` | C program that swaps exe files (compiled to `update_helper.exe` via GCC) |
| `build.py` | PyInstaller build + GCC compile of update_helper |
| `.github/workflows/release.yml` | Tag-triggered CI: build + SHA256 + publish GitHub Release |

### Entry flow (main.py)
`if __name__` → check admin → `QApplication` → `AppManager` → `QSystemTrayIcon` with context menu.

### AppManager (QObject)
- Owns hotkey polling (`QTimer` every 50ms checking `keyboard.is_pressed`)
- Loads + merges Unicode mappings (built-in from `unicodeitplus.data.COMMANDS` + user custom file at `%APPDATA%\LaTeX-Overlay-Utility\custom_mappings.txt`)
- Monkey-patches `unicodeitplus.transform.COMMANDS` and `HAS_ARG` with merged data
- Builds a fresh `Lark` LALR parser using the same grammar as unicodeitplus, but with the patched transformer
- `replace_latex_with_unicode()`: wraps input in `$...$` math mode, parses via custom Lark instance
- `check_for_updates()`: queries GitHub Releases API, shows UpdateDialog if newer version found
- On startup: cleans stale `.bak` file and temp download dir from previous updates

### LaTeXOverlay (QWidget)
- Frameless, translucent, always-on-top
- `QLineEdit` input + `QLabel` preview + `QListWidget` autocomplete popup
- Real-time preview on every keystroke via `update_preview` → `replace_latex_with_unicode`
- Enter → hide overlay, activate previous window, clipboard + Ctrl+V paste
- Escape → hide
- Draggable by clicking outside input box
- `force_foreground_qt_window()`: uses Win32 `AttachThreadInput` + `SetForegroundWindow` to steal focus from other apps

### Tray menu structure
```
Show/Hide Overlay (Ctrl+Alt+M)
---
Edit Custom Mappings...
Reload Mappings
---
Check for Updates...
---
Quit
```

### Custom mappings format
One mapping per line: `\command Unicode_char`. `#` comments. Lines with `{` in command name auto-added to `HAS_ARG` set. Override built-ins.

### Autocomplete
Regex extracts trailing `\word` from input, matches against all commands in merged map, shows popup above input box.

### Self-update mechanism (updater.py)
1. User clicks "Check for Updates..." → `fetch_latest_release()` queries GitHub Releases API
2. Compares semver of remote `tag_name` vs local `__version__`
3. If newer: `UpdateDialog` shows changelog + Install/Later buttons
4. Install → downloads exe + .sha256 to `%TEMP%\latex-inserter-update\` → verifies SHA256
5. Launches `update_helper.exe --pid <PID> --src <new_exe> --dst <old_exe>`, then quits app
6. Helper waits for main process to exit, renames old exe to `.bak`, copies new into place
7. On copy failure: restores from `.bak` (rollback)
8. On success: relaunches exe via `ShellExecuteA("runas")`, deletes `.bak`, cleans temp dir

### update_helper.c
- ~60 lines of C, compiled with `gcc -mwindows -Os -s -lkernel32`
- No console window (`-mwindows`), ~15KB binary
- **Cannot modify this at runtime** — it ships alongside the exe in the same directory
- If the helper itself needs updating, it ships in a new release; the old helper swaps the main exe, and the new exe uses the new helper on next update

## Key Dependencies
- **PyQt5** — GUI (overlay, system tray)
- **unicodeitplus** — LaTeX↔Unicode command table + Lark grammar + `ToUnicode` transformer
- **keyboard** — global hotkey detection (requires admin)
- **pyautogui** — simulates Ctrl+V paste
- **pygetwindow** — captures last active window before overlay steals focus
- **lark** — parser (transitive via unicodeitplus, also directly imported for custom parser rebuild)
- No `requests` — update logic uses stdlib `urllib.request`

## PyInstaller Build (build.py)
1. Cleans `build/`, `dist/`, old `.spec`
2. Validates icon + manifest + update_helper.c exist
3. Dynamically locates `unicodeitplus` package path for `--add-data`
4. Builds onefile exe with admin manifest and `keyboard._winkeyboard` hidden import
5. Compiles `update_helper.c` with GCC → `dist/update_helper.exe`

## Notes
- The `.spec` file is auto-generated by build.py; don't hand-edit it, it gets cleaned and rebuilt each run
- The app patches `unicodeitplus.transform` module globals at runtime — any change to how the transformer imports its data dict will break the monkey-patching
- `update_helper.exe` must sit alongside `LaTeX-Inserter.exe` in the same directory for self-update to work
- GitHub API rate-limits unauthenticated requests to 60/hour — acceptable for manual "Check for Updates"
