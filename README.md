<div align="center">
  <img src="LaTeX-Inserter-icon-final-png.png" width="256" height="256" alt="LaTeX Inserter logo">
</div>

<div align="center">
<a href="https://github.com/lsutorus/latex-inserter/releases/latest">
  <img src="https://img.shields.io/github/v/release/lsutorus/latex-inserter?color=800f00&style=flat-square" alt="GitHub release">
  <img src="https://img.shields.io/badge/OS-Windows-blue?style=flat-square&logo=windows&color=0a348f" alt="Windows OS">
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
</a>
<a href="https://github.com/lsutorus/latex-inserter/blob/master/LICENSE">
  <img src="https://img.shields.io/github/license/lsutorus/latex-inserter?style=flat-square&color=C41E3A" alt="License">
</a>
</div>

# LaTeX Inserter

A Windows system-tray app that lets you type LaTeX and paste Unicode equivalents anywhere. Press **Ctrl+Alt+M**, type LaTeX, hit Enter--unicode equivalent will paste and copy to clipboard.

## How it works

1. **Ctrl+Alt+M** opens a floating overlay near your cursor
2. Type LaTeX: e.g. `\alpha`, `\sqrt{x^2}`, `\sum`, `\Rightarrow`
3. See the Unicode preview in real time
4. Press **Enter**: the Unicode is copied to clipboard and auto-pasted into whatever window you were in


## Install
> Requires Windows 10 or later. The app runs as admin (needed for global hotkey detection).
1. Go to [Releases](https://github.com/lsutorus/latex-inserter/releases/latest)
2. Download **LaTeX-Inserter-setup.exe**
3. Run it. The installer walks you through the rest
   - Default install location: `C:\Program Files\LaTeX Inserter`
   - Choose Desktop and/or Start Menu shortcuts
   - App launches automatically when setup finishes

## Features

- Autocomplete
- Ability to edit/create mappings
- Easy updating

## Examples

| LaTeX | Unicode |
|-------|---------|
| `\alpha` | α |
| `\beta` | β |
| `\sqrt{x^2}` | √(x²) |
| `\sum` | ∑ |
| `\longrightarrow` | ⟶ |
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

This project is licensed under the [MIT](https://choosealicense.com/licenses/mit/) License. See [LICENSE](LICENSE) for details.
