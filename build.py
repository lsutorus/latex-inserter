import PyInstaller.__main__
import os
import shutil
import subprocess
import sys
import unicodeitplus

# --- CONFIGURATION ---
# Define your specific icon filename here.
ICON_FILENAME = "LaTeX-inserter-icon.ico"


# --- Step 1: Clean up old build files ---
print("Cleaning up old build directories...")
for folder in ['build', 'dist', 'main.spec']:
    if os.path.exists(folder):
        try:
            if os.path.isdir(folder):
                shutil.rmtree(folder)
            else:
                os.remove(folder) # Also remove the .spec file
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


# --- Step 3: Dynamically find paths for data ---
# For unicodeitplus data
package_path = unicodeitplus.__path__[0]
add_data_unicode = f'{package_path}{os.pathsep}unicodeitplus'
print(f"Found unicodeitplus data at: {package_path}")

# For the icon file
add_data_icon = f'{ICON_FILENAME}{os.pathsep}.'
print(f"Will bundle '{ICON_FILENAME}' for the system tray.")


# --- Step 4: Run the PyInstaller Build Command ---
print("\nStarting PyInstaller build...")
try:
    PyInstaller.__main__.run([
        'main.py',
        '--name=LaTeX-Inserter', # Set a nice name for the .exe
        '--onefile',
        '--noconsole',
        f'--icon={ICON_FILENAME}', # Use the variable to set the EXE's file icon
        f'--add-data={add_data_unicode}',
        f'--add-data={add_data_icon}', # Use the variable to bundle the icon
        '--hidden-import=keyboard._winkeyboard',
        '--manifest=admin.manifest'
    ])
    print("\nBuild complete! The .exe file is in the 'dist' folder.")

except Exception as e:
    print(f"\nAn error occurred during the build process: {e}")
    sys.exit(1)


# --- Step 5: Compile update_helper.c ---
HELPER_SRC = "update_helper.c"
HELPER_EXE = "dist/update_helper.exe"

print("\nCompiling update_helper.exe...")
gcc_check = subprocess.run(["gcc", "--version"], capture_output=True)
if gcc_check.returncode != 0:
    print("ERROR: GCC not found. Install MinGW-w64 and add to PATH.")
    print("Download from: https://www.mingw-w64.org/")
    sys.exit(1)

if not os.path.exists(HELPER_SRC):
    print(f"ERROR: '{HELPER_SRC}' not found.")
    sys.exit(1)

result = subprocess.run(
    ["gcc", "-o", HELPER_EXE, HELPER_SRC, "-lkernel32", "-mwindows", "-Os", "-s"],
    capture_output=True, text=True
)
if result.returncode != 0:
    print(f"ERROR: Failed to compile update_helper.c:\n{result.stderr}")
    sys.exit(1)

print(f"update_helper.exe compiled to {HELPER_EXE}")
print("\nAll build artifacts are in the 'dist' folder.")