# main.py

import sys
import time
import pyautogui
import pygetwindow as gw
import keyboard
import os
import re
import subprocess
import ctypes
import shutil

# --- unicodeitplus components we need to build our own parser ---
from lark import Lark
import unicodeitplus
import unicodeitplus.data
from unicodeitplus.transform import ToUnicode

from PyQt5.QtCore import Qt, QObject, QTimer, QPoint
from PyQt5.QtGui import (QIcon, QFont, QPalette, QColor, QPixmap, QPainter, QBrush,
                         QPen, QCursor)
from PyQt5.QtWidgets import (QApplication, QSystemTrayIcon, QMenu, QAction, QWidget,
                             QVBoxLayout, QLineEdit, QLabel, QSizePolicy, QListWidget,
                             QListWidgetItem, QMessageBox)


def force_foreground_qt_window(widget):
    """
    Windows: make widget real foreground window.
    Qt focus APIs alone often fail when switching from another app.
    """
    try:
        hwnd = int(widget.winId())
    except Exception:
        return

    try:
        user32 = ctypes.windll.user32
        SW_SHOW = 5
        kernel32 = ctypes.windll.kernel32

        user32.ShowWindow(hwnd, SW_SHOW)
        user32.BringWindowToTop(hwnd)

        # Win focus-steal rules: SetForegroundWindow often ignored unless
        # calling thread temporarily attached to foreground thread.
        fg_hwnd = user32.GetForegroundWindow()
        if fg_hwnd:
            fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None)
        else:
            fg_tid = 0
        this_tid = kernel32.GetCurrentThreadId()

        if fg_tid and fg_tid != this_tid:
            user32.AttachThreadInput(this_tid, fg_tid, True)
            try:
                user32.SetForegroundWindow(hwnd)
                user32.SetActiveWindow(hwnd)
                user32.SetFocus(hwnd)
            finally:
                user32.AttachThreadInput(this_tid, fg_tid, False)
        else:
            user32.SetForegroundWindow(hwnd)
            user32.SetActiveWindow(hwnd)
            user32.SetFocus(hwnd)
    except Exception:
        return

# --- Constants ---
__version__ = "1.3.0"
APP_DATA_FOLDER = "LaTeX Inserter"
CUSTOM_MAPPINGS_FILENAME = "custom_mappings.txt"
ICON_FILENAME = "LaTeX-Inserter-icon-final.ico"

# This is the exact grammar used by the unicodeitplus library.
# By using it, we ensure our custom parser behaves identically.
UNICODEITPLUS_GRAMMAR = r"""
start: (item | math)*

?atom: CHARACTER
    | COMMAND

?item: atom
    | WS+
    | group

CHARACTER: /[^%#&\{\}^_]/ | ESCAPED
ESCAPED: "\\\\" | "\\#" | "\\%" | "\\&"  | "\\{" | "\\}" | "\\_" | "\\,"
group: "{" item* "}"
math: "$" item* "$"
SUBSCRIPT: "_"
SUPERSCRIPT: "^"
COMMAND: (("\\" WORD WS*) | SUBSCRIPT | SUPERSCRIPT)

%import common.WS
%import common.WORD
"""


# Helper function to find resource files (like icons)
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# --- The PyQt5 GUI Class ---
# This class does not require any further changes.
class LaTeXOverlay(QWidget):
    def __init__(self, app_manager):
        super().__init__()
        self.app_manager = app_manager
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Window
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedSize(450, 195)
        self.setWindowTitle("LaTeX to Unicode Inserter")
        self.setWindowIcon(QIcon(resource_path(ICON_FILENAME)))
        self.last_active_window = None
        self.drag_position = None
        self.setup_ui()
        self.setup_dark_theme_styles()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        brush = QBrush(QColor(43, 43, 43, 235))
        painter.setBrush(brush)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)

    def setup_ui(self):
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(self.layout)
        self.autocomplete_list = QListWidget(self)
        self.autocomplete_list.setWindowFlags(Qt.ToolTip)
        self.autocomplete_list.setFont(QFont("Consolas", 10))
        self.autocomplete_list.hide()
        self.autocomplete_list.itemClicked.connect(self.complete_from_list)
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Enter LaTeX (e.g., \\sqrt{x^2} or \\nu)")
        self.input_box.setFont(QFont("Segoe UI", 16))
        self.input_box.setFocusPolicy(Qt.StrongFocus)
        self.input_box.textChanged.connect(self.update_preview)
        self.input_box.returnPressed.connect(self.handle_return_pressed)
        self.canvas_label = QLabel("Preview will appear here")
        self.canvas_label.setAlignment(Qt.AlignCenter)
        self.canvas_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas_label.setFont(QFont("Segoe UI", 24))
        self.layout.addWidget(self.input_box)
        self.layout.addWidget(self.canvas_label)

        self.version_label = QLabel(f"v{__version__}")
        self.version_label.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        self.version_label.setStyleSheet("color: #666; font-size: 7pt; margin: 0px;")
        self.version_label.setFixedHeight(12)
        self.layout.addWidget(self.version_label)

    def setup_dark_theme_styles(self):
        self.setStyleSheet("""
            QWidget {
                color: #dcdcdc;
            }
            QLineEdit {
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 6px;
                color: #dcdcdc;
                font-family: "Segoe UI";
            }
            QListWidget { /* Style for autocomplete */
                background-color: #3c3c3c;
                border: 1px solid #555;
                color: #dcdcdc;
            }
            QListWidget::item:hover {
                background-color: #555;
            }
            QListWidget::item:selected {
                background-color: #0078d7;
            }
        """)

    def showEvent(self, event):
        self.input_box.clear()
        self.canvas_label.clear()
        self.raise_()
        self.activateWindow()
        force_foreground_qt_window(self)
        for delay_ms in (0, 50, 150):
            QTimer.singleShot(delay_ms, lambda: (force_foreground_qt_window(self),
                                                 self.input_box.setFocus(Qt.ActiveWindowFocusReason)))
        super().showEvent(event)

    def keyPressEvent(self, event):
        if self.autocomplete_list.isVisible():
            if event.key() in (Qt.Key_Down, Qt.Key_Up):
                self.autocomplete_list.setFocus()
                count = self.autocomplete_list.count()
                if count == 0: return
                current_row = self.autocomplete_list.currentRow()
                if event.key() == Qt.Key_Down:
                    next_row = (current_row + 1) % count
                    self.autocomplete_list.setCurrentRow(next_row)
                elif event.key() == Qt.Key_Up:
                    next_row = (current_row - 1 + count) % count
                    self.autocomplete_list.setCurrentRow(next_row)
                return
            elif event.key() == Qt.Key_Escape:
                self.hide()
                return
        if event.key() == Qt.Key_Escape:
            self.hide()

    def handle_return_pressed(self):
        if self.autocomplete_list.isVisible() and self.autocomplete_list.currentItem():
            self.complete_from_list(self.autocomplete_list.currentItem())
        else:
            latex_code = self.input_box.text().strip()
            if not latex_code:
                self.hide()
                return
            self.hide()
            if self.last_active_window:
                try:
                    time.sleep(0.1)
                    self.last_active_window.activate()
                    time.sleep(0.1)
                except Exception as e:
                    print(f"Could not activate previous window: {e}")
            self.paste_as_unicode(latex_code)

    def hideEvent(self, event):
        self.autocomplete_list.hide()
        super().hideEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            input_box_rect = self.input_box.geometry()
            if not input_box_rect.contains(event.pos()):
                self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()
            else:
                self.drag_position = None
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_position and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def update_preview(self, text=""):
        self.update_autocomplete(self.input_box.text())
        latex_code = self.input_box.text().strip()
        if not latex_code:
            self.canvas_label.setText("Preview will appear here")
            self.canvas_label.setPixmap(QPixmap())
            return
        self.render_unicode_preview(latex_code)

    def update_autocomplete(self, text):
        last_word_match = re.search(r'(\\\w*)$', text)
        if not last_word_match:
            self.autocomplete_list.hide()
            return
        partial_command = last_word_match.group(1)
        if len(partial_command) < 2:
            self.autocomplete_list.hide()
            return
        display_suggestions = []
        for cmd in self.app_manager.latex_commands:
            if cmd.startswith(partial_command):
                symbol = self.app_manager.unicode_map.get(cmd, '')
                display_text = f"{cmd:<20} {symbol}"
                display_suggestions.append(display_text)
        if not display_suggestions:
            self.autocomplete_list.hide()
            return
        self.autocomplete_list.clear()
        self.autocomplete_list.addItems(display_suggestions)
        input_pos = self.input_box.mapToGlobal(QPoint(0, 0))
        list_height = min(200, self.autocomplete_list.sizeHintForRow(0) * len(display_suggestions) + 5)
        self.autocomplete_list.setGeometry(
            input_pos.x(),
            input_pos.y() - list_height,
            self.input_box.width(),
            list_height
        )
        self.autocomplete_list.show()

    def complete_from_list(self, item):
        selected_text = item.text()
        selected_command = selected_text.split()[0]
        current_text = self.input_box.text()
        last_backslash_pos = current_text.rfind('\\')
        if last_backslash_pos != -1:
            new_text = current_text[:last_backslash_pos] + selected_command + ' '
            self.input_box.setText(new_text)
            self.input_box.setFocus()
            self.input_box.setCursorPosition(len(new_text))
        self.autocomplete_list.hide()

    def render_unicode_preview(self, latex_code):
        try:
            unicode_result = self.app_manager.replace_latex_with_unicode(latex_code)
            self.canvas_label.setText(unicode_result)
        except Exception as e:
            self.canvas_label.setText("Invalid Unicode")
            # print(f"Unicode conversion error: {e}") # Can be noisy, uncomment for debug

    def paste_as_unicode(self, latex_code):
        try:
            result = self.app_manager.replace_latex_with_unicode(latex_code)
            QApplication.clipboard().setText(result)
            pyautogui.hotkey('ctrl', 'v')
        except Exception as e:
            print(f"Failed to insert Unicode for '{latex_code}': {e}")


# --- Global Hotkey Polling and Application Management ---
class AppManager(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.overlay_window = None
        self.hotkey_was_down = False
        self.original_default_commands = unicodeitplus.data.COMMANDS.copy()
        self.original_has_arg = unicodeitplus.data.HAS_ARG.copy()
        self.custom_parser = None
        self.unicode_map = {}
        self.latex_commands = []
        self.custom_mappings_path = self._get_custom_mappings_path()
        self.load_mappings()

        # Cleanup stale temp files from previous update
        if getattr(sys, 'frozen', False):
            from updater import UPDATE_TEMP_DIR
            if os.path.exists(UPDATE_TEMP_DIR):
                shutil.rmtree(UPDATE_TEMP_DIR, ignore_errors=True)
        self.timer = QTimer()
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.check_hotkey)
        self.timer.start()

    def _build_custom_parser(self):
        """
        Creates a new Lark parser instance with an up-to-date transformer.
        This is the core of the fix.
        """
        print("Building new custom parser instance...")
        self.custom_parser = Lark(UNICODEITPLUS_GRAMMAR, parser="lalr", transformer=ToUnicode())
        print("Parser built successfully.")

    def load_mappings(self):
        print("Loading and merging Unicode mappings...")
        combined_map = self.original_default_commands.copy()
        combined_has_arg = self.original_has_arg.copy()

        if os.path.exists(self.custom_mappings_path):
            try:
                custom_count = 0
                with open(self.custom_mappings_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip() and not line.strip().startswith('#'):
                            parts = line.split(maxsplit=1)
                            if len(parts) >= 2:
                                key, value = parts[0], parts[1].strip()
                                combined_map[key] = value
                                custom_count += 1
                                # Auto-detect if a new command takes an argument
                                if '{' in key:
                                    command_base = key.split('{')[0]
                                    combined_has_arg.add(command_base)
                print(f"Loaded and merged {custom_count} custom mappings.")
            except Exception as e:
                print(f"ERROR: Could not load custom mappings file: {e}")

        # THE DEFINITIVE FIX:
        # We must directly modify the command list that the ToUnicode transformer
        # imported and is using locally.
        unicodeitplus.transform.COMMANDS = combined_map
        unicodeitplus.transform.HAS_ARG = combined_has_arg
        print("Patched the transformer's local command list.")

        # Now, we still build a new parser instance to ensure it uses the
        # newly patched data when it creates its ToUnicode transformer.
        self._build_custom_parser()

        # Store the combined map for the UI (autocomplete) to use.
        self.unicode_map = combined_map
        self.latex_commands = sorted([cmd for cmd in combined_map.keys() if cmd.startswith('\\')])
        print("Mappings loaded successfully.")

    def replace_latex_with_unicode(self, text):
        """
        Converts LaTeX to Unicode using our own custom-built parser instance.
        """
        if not self.custom_parser:
            return text # Should not happen, but a safe fallback
        # The library's `replace` function is just a wrapper for `parse(f"${s}$")`
        return self.custom_parser.parse(f"${text}$")

    def _get_custom_mappings_path(self):
        app_data_path = os.path.join(os.getenv('APPDATA'), APP_DATA_FOLDER)
        os.makedirs(app_data_path, exist_ok=True)
        return os.path.join(app_data_path, CUSTOM_MAPPINGS_FILENAME)

    def edit_custom_mappings(self):
        if not os.path.exists(self.custom_mappings_path):
            try:
                print(f"Creating new custom mappings file at: {self.custom_mappings_path}")
                with open(self.custom_mappings_path, 'w', encoding='utf-8') as f:
                    f.write("# This is your custom LaTeX-to-Unicode mappings file.\n")
                    f.write("# Format: <LaTeX_Command> <Unicode_Character(s)>\n")
                    f.write("# Your entries here will override the built-in defaults.\n\n")
                    for key, value in sorted(self.original_default_commands.items()):
                        f.write(f"{key} {value}\n")
            except Exception as e:
                QMessageBox.critical(None, "Error", f"Could not create custom mappings file:\n{e}")
                return
        try:
            os.startfile(self.custom_mappings_path)
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Could not open mappings file:\n{e}")

    def check_hotkey(self):
        try:
            keys_are_down = (
                    keyboard.is_pressed('ctrl') and
                    keyboard.is_pressed('alt') and
                    keyboard.is_pressed('m')
            )
        except ImportError:
            keys_are_down = False
        if keys_are_down and not self.hotkey_was_down:
            self.toggle_overlay_visibility()
        self.hotkey_was_down = keys_are_down

    def toggle_overlay_visibility(self):
        if self.overlay_window is None:
            self.overlay_window = LaTeXOverlay(self)
        if self.overlay_window.isVisible():
            self.overlay_window.hide()
        else:
            try:
                self.overlay_window.last_active_window = gw.getActiveWindow()
            except Exception:
                self.overlay_window.last_active_window = None
            win = self.overlay_window
            pos = QCursor.pos()
            screen = self.app.screenAt(pos)
            if not screen:
                screen = self.app.primaryScreen()
            screen_rect = screen.availableGeometry()
            screen_left = screen_rect.left()
            screen_top = screen_rect.top()
            screen_right = screen_rect.left() + screen_rect.width()
            screen_bottom = screen_rect.top() + screen_rect.height()

            win_w = win.width()
            win_h = win.height()

            # Default: cursor hugs top-left corner (cursor == window top-left).
            # If screen edge blocks, flip to other side so cursor hugs window edge.
            ideal_x = pos.x()
            if ideal_x + win_w > screen_right:
                ideal_x = pos.x() - win_w

            ideal_y = pos.y()
            if ideal_y + win_h > screen_bottom:
                ideal_y = pos.y() - win_h

            final_x = max(screen_left, min(ideal_x, screen_right - win_w))
            final_y = max(screen_top, min(ideal_y, screen_bottom - win_h))
            win.move(final_x, final_y)
            win.show()
            win.raise_()
            win.activateWindow()
            for delay_ms in (0, 50, 150):
                QTimer.singleShot(delay_ms, lambda: (force_foreground_qt_window(win),
                                                     win.input_box.setFocus(Qt.ActiveWindowFocusReason)))

    def check_for_updates(self):
        from updater import fetch_latest_release, parse_version, UpdateDialog, UpToDateDialog
        try:
            update_info = fetch_latest_release(__version__)
        except Exception as e:
            QMessageBox.warning(None, "Update Check Failed",
                                f"Could not check for updates:\n{e}")
            return
        if update_info is None:
            UpToDateDialog(__version__).exec_()
            return
        current = parse_version(__version__)
        latest = parse_version(update_info.version)
        if latest <= current:
            UpToDateDialog(__version__).exec_()
            return
        dialog = UpdateDialog(update_info, current_version=__version__)
        if dialog.exec_() == 1:  # QDialog.Accepted
            from updater import perform_update
            try:
                perform_update(update_info)
            except Exception as e:
                QMessageBox.critical(None, "Update Failed", f"Update failed:\n{e}")
                return
            QApplication.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon(resource_path(ICON_FILENAME)))
    print("Checking for administrator privileges...")
    try:
        keyboard.is_pressed('ctrl')
        print("Privileges seem OK.")
    except Exception as e:
        print("---")
        print("ERROR: Failed to access keyboard hooks.")
        print("You MUST run this script as an administrator.")
        print(f"Details: {e}")
        print("---")
        sys.exit(1)

    manager = AppManager(app)
    tray_icon = QSystemTrayIcon()
    try:
        icon_path = resource_path(ICON_FILENAME)
        tray_icon.setIcon(QIcon(icon_path))
    except Exception as e:
        print(f"Could not load icon from path '{icon_path}': {e}")

    tray_icon.setVisible(True)
    menu = QMenu()
    show_action = QAction("Show/Hide Overlay (Ctrl+Alt+M)")
    show_action.triggered.connect(manager.toggle_overlay_visibility)
    menu.addAction(show_action)
    menu.addSeparator()

    # FIX: Corrected the variable name to be consistent (one underscore)
    edit_action = QAction("Edit Custom Mappings...")
    edit_action.triggered.connect(manager.edit_custom_mappings)
    menu.addAction(edit_action)

    reload_action = QAction("Reload Mappings")
    reload_action.triggered.connect(manager.load_mappings)
    menu.addAction(reload_action)
    menu.addSeparator()

    update_action = QAction("Check for Updates...")
    update_action.triggered.connect(manager.check_for_updates)
    menu.addAction(update_action)
    menu.addSeparator()
    quit_action = QAction("Quit")
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)
    tray_icon.setContextMenu(menu)
    tray_icon.setToolTip("LaTeX Inserter")
    print("LaTeX Inserter is running. Press Ctrl+Alt+M to open the overlay.")
    sys.exit(app.exec_())
