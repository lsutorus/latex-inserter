import PyInstaller.__main__
import os
import shutil
import subprocess
import sys
import re
import unicodeitplus

# --- CONFIGURATION ---
ICON_FILENAME = "LaTeX-inserter-icon.ico"


# --- Step 1: Clean up old build files ---
print("Cleaning up old build directories...")
for folder in ['build', 'dist', 'main.spec']:
    if os.path.exists(folder):
        try:
            if os.path.isdir(folder):
                shutil.rmtree(folder)
            else:
                os.remove(folder)
            print(f"Removed old '{folder}'.")
        except OSError as e:
            print(f"Error removing {folder}: {e}")
            print("Please ensure the application is not running and try again.")
            sys.exit(1)

# --- Step 2: Validate that necessary files exist ---
if not os.path.exists(ICON_FILENAME):
    print(f"ERROR: '{ICON_FILENAME}' not found. Please add it to the project folder.")
    sys.exit(1)
if not os.path.exists('admin.manifest'):
    print("ERROR: 'admin.manifest' not found. Please add it to the project folder.")
    sys.exit(1)
if not os.path.exists('installer.iss'):
    print("ERROR: 'installer.iss' not found. Please add it to the project folder.")
    sys.exit(1)


# --- Step 3: Dynamically find paths for data ---
package_path = unicodeitplus.__path__[0]
add_data_unicode = f'{package_path}{os.pathsep}unicodeitplus'
print(f"Found unicodeitplus data at: {package_path}")

add_data_icon = f'{ICON_FILENAME}{os.pathsep}.'
print(f"Will bundle '{ICON_FILENAME}' for the system tray.")


# --- Step 4: Run the PyInstaller Build Command ---
print("\nStarting PyInstaller build...")
try:
    PyInstaller.__main__.run([
        'main.py',
        '--name=LaTeX-Inserter',
        '--onefile',
        '--noconsole',
        f'--icon={ICON_FILENAME}',
        f'--add-data={add_data_unicode}',
        f'--add-data={add_data_icon}',
        '--hidden-import=keyboard._winkeyboard',
        '--manifest=admin.manifest'
    ])
    print("\nBuild complete! The .exe file is in the 'dist' folder.")

except Exception as e:
    print(f"\nAn error occurred during the build process: {e}")
    sys.exit(1)


# --- Step 5: Build installer with Inno Setup ---
ISS_SCRIPT = "installer.iss"

print("\nBuilding installer...")

# Find iscc — it may not be on PATH after choco install
iscc_exe = "iscc"
iscc_check = subprocess.run([iscc_exe, "--version"], capture_output=True)
if iscc_check.returncode != 0:
    # Try common Inno Setup install locations
    for candidate in [
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Inno Setup 6", "iscc.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Inno Setup 6", "iscc.exe"),
    ]:
        if os.path.exists(candidate):
            iscc_exe = candidate
            break
    else:
        print("ERROR: Inno Setup Compiler (iscc) not found.")
        print("Install via: choco install innosetup")
        sys.exit(1)

# Extract version from main.py
with open("main.py", "r", encoding="utf-8") as f:
    version_match = re.search(r'__version__\s*=\s*"([^"]+)"', f.read())
if not version_match:
    print("ERROR: Could not find __version__ in main.py")
    sys.exit(1)
app_version = version_match.group(1)
print(f"Building installer for version {app_version}...")

result = subprocess.run(
    [iscc_exe, f"/DAppVersion={app_version}", ISS_SCRIPT],
    capture_output=True, text=True
)
if result.returncode != 0:
    print(f"ERROR: Inno Setup compilation failed:\n{result.stderr}\n{result.stdout}")
    sys.exit(1)

print("Installer built successfully.")
print("\nAll build artifacts are in the 'dist' folder.")
