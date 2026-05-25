# LaTeX Inserter

A Windows system-tray app that lets you type LaTeX and paste Unicode equivalents anywhere. Press **Ctrl+Alt+M**, type your LaTeX, hit Enter — done.

## How it works

1. **Ctrl+Alt+M** opens a floating overlay near your cursor
2. Type LaTeX — e.g. `\alpha`, `\sqrt{x^2}`, `\sum`, `\Rightarrow`
3. See the Unicode preview in real time
4. Press **Enter** — the Unicode is copied to clipboard and auto-pasted into whatever window you were in

![Overlay screenshot](docs/overlay.png)

## Install

1. Go to [Releases](https://github.com/lsutorus/latex-inserter/releases/latest)
2. Download **LaTeX-Inserter-setup.exe**
3. Run it — the installer walks you through the rest
   - Default install location: `C:\Program Files\LaTeX Inserter`
   - Choose Desktop and/or Start Menu shortcuts
   - App launches automatically when setup finishes

> Requires Windows 10 or later. The app runs as admin (needed for global hotkey detection).

## Usage

### Basic

| Action | How |
|--------|-----|
| Open overlay | **Ctrl+Alt+M** |
| Insert LaTeX | Type, then **Enter** |
| Cancel | **Escape** |
| Move overlay | Click and drag outside the input box |

### Autocomplete

While typing, any `\command` prefix triggers an autocomplete popup showing matching LaTeX commands and their Unicode symbols. Use **Up/Down arrows** to navigate, **Enter** to select.

### Custom mappings

Right-click the tray icon → **Edit Custom Mappings...** to open your personal mappings file. Add one mapping per line:

```
\mycommand ⚡
```

Lines starting with `#` are comments. Your custom mappings override built-in ones. Click **Reload Mappings** in the tray menu to apply changes without restarting.

### Updating

Right-click the tray icon → **Check for Updates...**. If a new version is available, click **Install Update** — the app downloads, verifies, and updates itself automatically.

## Examples

| LaTeX | Unicode |
|-------|---------|
| `\alpha` | α |
| `\beta` | β |
| `\sqrt{x^2}` | √(x²) |
| `\sum` | ∑ |
| `\Rightarrow` | ⇒ |
| `\infty` | ∞ |
| `\partial` | ∂ |
| `\nabla` | ∇ |
| `\forall` | ∀ |
| `\exists` | ∃ |

## Uninstall

Use **Add/Remove Programs** in Windows Settings, or run `unins000.exe` from the install directory. The uninstaller will ask whether to keep or remove your custom mappings.

## Building from source

```powershell
# Install Python dependencies
pip install -r requirements.txt

# Install Inno Setup (for building the installer)
choco install innosetup

# Build
python build.py
```

Output: `dist/LaTeX-Inserter-setup.exe`

## License

MIT
