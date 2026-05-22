import PyInstaller.__main__
import os
import shutil
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