# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Rules
- Runtime: PowerShell 7.x (pwsh)
- Do not use legacy WMI cmdlets (use CIM instead).
- Use forward slashes `/` for paths to prevent escape-character bugs during CLI tool execution.

## What This App Does

Windows system-tray app. Configurable hotkey (default Ctrl+Alt+M) opens overlay near cursor. User types LaTeX (e.g. `\sqrt{x^2}`), sees Unicode preview, hits Enter → Unicode copied to clipboard and auto-pasted into previous window.

## Build & Run

```powershell
# Install deps
pip install -r requirements.txt

# Run (must be admin — keyboard hooks require elevation)
python main.py

# Build installer (generates dist/LaTeX-Inserter.exe + dist/LaTeX-Inserter-setup.exe)
python build.py
```

Requires admin privileges. The `admin.manifest` forces `requireAdministrator` in the built exe. Build also requires Inno Setup (`choco install innosetup`) for compiling the installer.

## Versioning & Release
- Version tracked in `main.py` as `__version__ = "x.y.z"` (semver) — always match current release
- Bump `__version__` before tagging a release
- Tag format: `vx.y.z`. Push tag → GitHub Actions builds + publishes release
- Release assets: `LaTeX-Inserter-setup.exe`, `LaTeX-Inserter-setup.exe.sha256`
- To release: `git tag v1.x.x && git push origin v1.x.x`

## Architecture

### File layout
| File | Purpose |
|------|---------|
| `main.py` | App entry point, LaTeXOverlay, AppManager, tray menu |
| `updater.py` | Self-update logic: GitHub API check, download installer, SHA256 verify, launch installer, themed dialogs (UpToDateDialog, UpdateDialog) |
| `settings.py` | App settings (JSON-based), startup registration, hotkey dialog (HotkeyRecorder, HotkeyDialog), hotkey normalize/format/validate, blocked hotkey blocklist |
| `installer.iss` | Inno Setup script — builds the single-file installer |
| `build.py` | PyInstaller build + Inno Setup compile of installer |
| `.github/workflows/release.yml` | Tag-triggered CI: build + SHA256 + publish GitHub Release |

### Entry flow (main.py)
`if __name__` → check admin → `QApplication` (with window icon set from `LaTeX-Inserter-icon-final.ico`) → `AppManager` → `QSystemTrayIcon` with context menu.

### Constants (module-level in main.py)
- `__version__` — semver string
- `APP_DATA_FOLDER` — `"LaTeX Inserter"`
- `CUSTOM_MAPPINGS_FILENAME` — `"custom_mappings.txt"`
- `ICON_FILENAME` — `"LaTeX-Inserter-icon-final.ico"` (used by both overlay and QApplication)

### AppManager (QObject)
- Owns event-driven hotkey via `keyboard.add_hotkey` + `pyqtSignal` bridge (`hotkey_triggered → toggle_overlay_visibility`)
- Hotkey configurable via tray menu "Change Hotkey..." → opens `HotkeyDialog` → records new combo → validates + saves to `settings.json`
- Loads + merges Unicode mappings (built-in from `unicodeitplus.data.COMMANDS` + user custom file at `%APPDATA%\LaTeX Inserter\custom_mappings.txt`)
- Monkey-patches `unicodeitplus.transform.COMMANDS` and `HAS_ARG` with merged data
- Builds a fresh `Lark` LALR parser using the same grammar as unicodeitplus, but with the patched transformer
- `replace_latex_with_unicode()`: wraps input in `$...$` math mode, parses via custom Lark instance
- `check_for_updates()`: queries GitHub Releases API, shows `UpToDateDialog` (if up to date) or `UpdateDialog` (if update available) — both are frameless themed dialogs
- `edit_custom_mappings()`: opens the mappings file with `os.startfile()` — no confirmation dialog shown
- `setup_tray()`: builds and owns `QSystemTrayIcon` + `QMenu` with all actions as `self.*` attributes (prevents GC)
- `change_hotkey()`: unregisters old hotkey, opens dialog, re-registers in `finally` block (new if accepted, old if rejected)
- `cleanup()`: calls `keyboard.unhook_all()` on app quit to clean up all hooks
- On startup: validates stored hotkey against blocklist — silently resets to `DEFAULT_HOTKEY` if blocked
- On startup: cleans temp download dir from previous updates

### LaTeXOverlay (QWidget)
- Frameless, translucent, always-on-top
- Window icon set from `LaTeX-Inserter-icon-final.ico` (appears in taskbar when overlay is visible)
- `QLineEdit` input + `QLabel` preview + `QListWidget` autocomplete popup + small version label (bottom-left)
- Real-time preview on every keystroke via `update_preview` → `replace_latex_with_unicode`
- Enter → hide overlay, activate previous window, clipboard + Ctrl+V paste
- Escape → hide
- Draggable by clicking outside input box
- `force_foreground_qt_window()`: uses Win32 `AttachThreadInput` + `SetForegroundWindow` to steal focus from other apps
- Version label: small gray text showing current `__version__` at bottom-left of overlay (7pt, `#666`, 12px height)

### Tray menu structure
```
Show/Hide Overlay (Ctrl+Alt+M)
---
Edit Custom Mappings...
Reload Mappings
---
Change Hotkey...
---
Check for Updates...
---
Quit
```
The hotkey in the "Show/Hide" label updates dynamically when the user changes it. All menu actions are stored as `self.*` attributes on AppManager to prevent Python GC from collecting the Qt wrappers.

### Hotkey system (settings.py + main.py)
- **Event-driven**: `keyboard.add_hotkey(hotkey_str, callback, suppress=False)` — no polling
- **Thread-safety**: `add_hotkey` callback runs on keyboard's background thread → emits `hotkey_triggered` pyqtSignal → main thread calls `toggle_overlay_visibility`
- **Normalization**: `normalize_hotkey()` sorts keys canonically: modifiers first (ctrl → alt → shift → windows), then non-modifiers alphabetically. Left/right variants collapsed.
- **Validation**: `is_valid_hotkey()` requires ≥1 modifier and rejects blocked combos
- **Blocklist**: `BLOCKED_HOTKEYS` frozenset in settings.py — Windows-reserved combos (Ctrl+C, Alt+Tab, Win+L, etc.) and common editing shortcuts. Checked on recording and on startup.
- **Persistence**: Hotkey stored as lowercase normalized string in `%APPDATA%\LaTeX Inserter\settings.json` (e.g. `"ctrl+alt+m"`)
- **Recording**: `HotkeyRecorder` (QThread) uses `keyboard.hook()` to capture 2+ key combos. Suppresses all events during recording. `add_hotkey` is unregistered before recording starts to avoid conflicts, re-registered in `finally` after dialog closes.
- **Startup invalid hotkey**: If `settings.json` contains a blocked hotkey (e.g. from a version upgrade that added new blocklist entries), the app silently resets to `DEFAULT_HOTKEY` and overwrites the setting

### Custom mappings format
One mapping per line: `\command Unicode_char`. `#` comments. Lines with `{` in command name auto-added to `HAS_ARG` set. Override built-ins.

### Autocomplete
Regex extracts trailing `\word` from input, matches against all commands in merged map, shows popup above input box.

### Themed update dialogs (updater.py)

Both dialogs extend `_FramelessDialog` — a base class providing:
- `Qt.FramelessWindowHint` + translucent background (no white title bar)
- `paintEvent` draws rounded dark rect (same `#2b2b2b` rgba as overlay)
- Custom X close button (top-right), ESC key to reject, draggable
- `DIALOG_BASE_STYLE` stylesheet: Calibri font, dark bg, styled buttons/progress bar

**UpToDateDialog** — shown when already up to date:
- Bold heading "You are running the latest version"
- Subtitle shows current version, e.g. "LaTeX Inserter v1.3.1" (non-bold, gray)
- Big green OK button (`#2d7d46`, hover `#3da85a`, 40px height, bold)
- Accepts `current_version` arg

**UpdateDialog** — shown when update available:
- Bold heading "Version X.Y.Z is available"
- Subtitle shows current version, e.g. "Current: LaTeX Inserter v1.3.1"
- Changelog rendered as Markdown with orange links (`#f90` via `QPalette.Link`)
- Blue "Install Update" button (`#0078d7`, hover `#1a8ae8`)
- "Later" button, progress bar, status label
- Accepts `update_info` + `current_version` args

### Self-update mechanism (updater.py)

1. User clicks "Check for Updates..." → `fetch_latest_release()` queries GitHub Releases API
2. Compares semver of remote `tag_name` vs local `__version__`
3. If newer: `UpdateDialog` shows changelog + Install/Later buttons
4. Install → downloads installer exe + .sha256 to `%TEMP%\latex-inserter-update\` → verifies SHA256
5. Launches `LaTeX-Inserter-setup.exe` with `/SILENT /CLOSEAPPLICATIONS` via `ShellExecuteW("runas")`
6. App quits; installer overwrites files in Program Files and relaunches the app
7. On first install: full wizard (welcome → dir → shortcuts → install → finish with launch checkbox)
8. On upgrade: installer detects previous install via registry and skips wizard pages

### Installer (installer.iss)
- Inno Setup script, built by `iscc /DAppVersion=x.y.z installer.iss`
- Installs to `C:\Program Files\LaTeX Inserter\` by default
- Desktop and Start Menu shortcut options (desktop unchecked, start menu checked)
- "Launch LaTeX Inserter" checkbox on Finish page (checked by default)
- Uninstall prompts whether to remove `%APPDATA%\LaTeX Inserter\` (custom mappings)
- `/SILENT` mode for auto-updates (progress bar only, no interaction)
- `PrivilegesRequired=admin` — app manifest already requires elevation

## Key Dependencies
- **PyQt5** — GUI (overlay, system tray, dialogs)
- **unicodeitplus** — LaTeX↔Unicode command table + Lark grammar + `ToUnicode` transformer
- **keyboard** — global hotkey detection (requires admin)
- **pyautogui** — simulates Ctrl+V paste
- **pygetwindow** — captures last active window before overlay steals focus
- **lark** — parser (transitive via unicodeitplus, also directly imported for custom parser rebuild)
- **Inno Setup** — builds the installer exe (install via `choco install innosetup`)
- No `requests` — update logic uses stdlib `urllib.request`

## PyInstaller Build (build.py)
1. Cleans `build/`, `dist/`, old `.spec`
2. Validates icon + manifest + installer.iss exist
3. Dynamically locates `unicodeitplus` package path for `--add-data`
4. Builds onefile exe with admin manifest and `keyboard._winkeyboard` hidden import
5. Extracts version from `main.py`, compiles `installer.iss` with `iscc` → `dist/LaTeX-Inserter-setup.exe`

## Notes
- The `.spec` file is auto-generated by build.py; don't hand-edit it, it gets cleaned and rebuilt each run
- The app patches `unicodeitplus.transform` module globals at runtime — any change to how the transformer imports its data dict will break the monkey-patching
- GitHub API rate-limits unauthenticated requests to 60/hour — acceptable for manual "Check for Updates"
- The installer launches via `ShellExecuteW` with `"runas"` verb — this triggers a UAC prompt so it can write to the install directory
- Dialog font is Calibri; overlay font is Segoe UI (input/preview) and Consolas (autocomplete)

## Anti-patterns
- **No separate update helper** — the installer handles exe replacement. Never reintroduce a separate `update_helper.exe` that must sit alongside the main exe. The single `LaTeX-Inserter-setup.exe` installer is both the first-install and update mechanism.
- **No shipping loose exes** — release assets are always the installer + sha256 only. Never upload raw `LaTeX-Inserter.exe` as a release asset.
- **No `.bak` file swap pattern** — the old update mechanism renamed the exe to `.bak` and swapped. The installer overwrites in-place instead. Don't reintroduce `.bak` cleanup logic.
- **Don't change the Inno Setup `AppId` GUID** — it's used for registry-based upgrade detection. Changing it would cause the installer to not detect previous installs, breaking the silent upgrade flow.
- **The `.iss` `AppVersion` must be passed via `/DAppVersion=` at build time** — don't hardcode the version in `installer.iss`. `build.py` extracts it from `main.py` and passes it to `iscc`.
- **No hotkey polling** — never reintroduce `QTimer` + `keyboard.is_pressed` polling for hotkey detection. Use `keyboard.add_hotkey` with a `pyqtSignal` bridge for thread-safe main-thread invocation. Polling wastes CPU and adds input latency.
- **No local-only QActions in QMenu** — when building `QMenu` for `QSystemTrayIcon`, all `QAction` objects must be stored as `self.*` attributes on the parent object AND pass the menu as parent in the `QAction(text, parent)` constructor. Local variables get Python-GC'd, causing actions to disappear from the menu at runtime. This is a PyQt bug where Python wrapper GC destroys the underlying Qt object even when `QMenu.addAction` should hold a C++ reference.
- **Unregister hotkey before recording** — `HotkeyRecorder` uses `keyboard.hook()` which suppresses all events. If `add_hotkey` is still active during recording, hook ordering can cause the active hotkey to interfere. Always `remove_hotkey` before recording, `add_hotkey` in `finally` after.
- **Canonical hotkey sort order** — `normalize_hotkey` must sort keys deterministically (modifiers first in fixed order, then non-modifiers alphabetically). Without this, hotkey strings from different press orders (e.g. `alt+ctrl+m` vs `ctrl+alt+m`) won't match the blocklist or each other.
