# settings.py — App settings, startup registration, and hotkey dialog

import json
import os
import sys
import winreg

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPainter, QBrush, QColor
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout

SETTINGS_FILENAME = "settings.json"
DEFAULT_HOTKEY = "ctrl+alt+m"
STARTUP_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_REG_NAME = "LaTeX Inserter"

MODIFIERS = {"ctrl", "alt", "shift", "windows"}

_MODIFIER_ORDER = {"ctrl": 0, "alt": 1, "shift": 2, "windows": 3}

_MODIFIER_MAP = {
    "left ctrl": "ctrl", "right ctrl": "ctrl",
    "left alt": "alt", "right alt": "alt",
    "left shift": "shift", "right shift": "shift",
    "left windows": "windows", "right windows": "windows",
}


def normalize_hotkey(hotkey_str):
    """Normalize hotkey string: collapse left/right variants, deduplicate, canonical sort.

    Keys are sorted with modifiers first in fixed order (ctrl, alt, shift, windows),
    then non-modifier keys alphabetically.
    """
    keys = [k.strip() for k in hotkey_str.split("+")]
    normalized = [_MODIFIER_MAP.get(k.lower(), k.lower()) for k in keys]
    seen = set()
    unique = []
    for k in normalized:
        if k not in seen:
            seen.add(k)
            unique.append(k)

    modifiers = [k for k in unique if k in _MODIFIER_ORDER]
    non_modifiers = [k for k in unique if k not in _MODIFIER_ORDER]
    modifiers.sort(key=lambda k: _MODIFIER_ORDER[k])
    non_modifiers.sort()
    return "+".join(modifiers + non_modifiers)


def format_hotkey(hotkey_str):
    """Format hotkey for display: 'ctrl+alt+m' → 'Ctrl+Alt+M'."""
    return "+".join(k.capitalize() for k in hotkey_str.split("+"))


def is_valid_hotkey(hotkey_str):
    """Check that the hotkey contains at least one modifier and is not blocked."""
    norm = normalize_hotkey(hotkey_str)
    keys = [k.strip() for k in norm.split("+")]
    if not any(k in MODIFIERS for k in keys):
        return False
    if norm in BLOCKED_HOTKEYS:
        return False
    return True


def is_blocked_hotkey(hotkey_str):
    """Check if the hotkey is in the Windows-reserved blocklist."""
    return normalize_hotkey(hotkey_str) in BLOCKED_HOTKEYS


BLOCKED_HOTKEYS = frozenset({
    # System-critical
    normalize_hotkey("ctrl+alt+delete"),
    normalize_hotkey("ctrl+shift+escape"),
    # Alt combos
    normalize_hotkey("alt+tab"),
    normalize_hotkey("alt+shift+tab"),
    normalize_hotkey("alt+f4"),
    normalize_hotkey("alt+space"),
    normalize_hotkey("alt+escape"),
    # Ctrl combos
    normalize_hotkey("ctrl+escape"),
    normalize_hotkey("ctrl+c"),
    normalize_hotkey("ctrl+v"),
    normalize_hotkey("ctrl+x"),
    normalize_hotkey("ctrl+z"),
    normalize_hotkey("ctrl+a"),
    # Windows key combos
    normalize_hotkey("windows+tab"),
    normalize_hotkey("windows+l"),
    normalize_hotkey("windows+d"),
    normalize_hotkey("windows+e"),
    normalize_hotkey("windows+r"),
    normalize_hotkey("windows+i"),
    normalize_hotkey("windows+s"),
    normalize_hotkey("windows+a"),
    normalize_hotkey("windows+p"),
    normalize_hotkey("windows+v"),
    normalize_hotkey("windows+x"),
    normalize_hotkey("windows+g"),
    normalize_hotkey("windows+m"),
    normalize_hotkey("windows+shift+s"),
    normalize_hotkey("windows+ctrl+d"),
    normalize_hotkey("windows+ctrl+f4"),
    normalize_hotkey("windows+ctrl+left"),
    normalize_hotkey("windows+ctrl+right"),
    normalize_hotkey("windows+up"),
    normalize_hotkey("windows+down"),
    normalize_hotkey("windows+left"),
    normalize_hotkey("windows+right"),
})


class Settings:
    """Simple JSON-based settings manager with defaults."""

    _defaults = {
        "start_on_startup": False,
        "hotkey": DEFAULT_HOTKEY,
    }

    def __init__(self, app_data_folder):
        self._path = os.path.join(
            os.getenv("APPDATA"), app_data_folder, SETTINGS_FILENAME
        )
        self._data = dict(self._defaults)
        self.load()

    def load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data.update(saved)
            except Exception as e:
                print(f"Error loading settings: {e}")

    def save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get(self, key):
        return self._data.get(key, self._defaults.get(key))

    def set(self, key, value):
        self._data[key] = value
        self.save()


# --- Windows startup registration ---

def is_startup_enabled():
    """Check if the app is registered in Windows startup."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, STARTUP_REG_PATH, 0, winreg.KEY_READ
        )
        try:
            winreg.QueryValueEx(key, STARTUP_REG_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False


def set_startup_enabled(enabled):
    """Register or unregister the app from Windows startup (HKCU)."""
    try:
        if enabled:
            if getattr(sys, "frozen", False):
                app_path = sys.executable
            else:
                app_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, STARTUP_REG_PATH, 0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, STARTUP_REG_NAME, 0, winreg.REG_SZ, app_path)
            winreg.CloseKey(key)
        else:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, STARTUP_REG_PATH, 0, winreg.KEY_SET_VALUE
            )
            try:
                winreg.DeleteValue(key, STARTUP_REG_NAME)
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"Error setting startup: {e}")
        return False


# --- Hotkey recording ---

class HotkeyRecorder(QThread):
    """Records a new hotkey combination using keyboard hooks."""
    recorded = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._active = True

    def stop(self):
        self._active = False

    def run(self):
        import keyboard
        import time

        pressed = set()
        result = None

        def on_event(event):
            nonlocal result
            if not self._active:
                return True  # Stop suppressing, unhook will clean up

            name = event.name.lower() if event.name else ""
            if event.event_type == keyboard.KEY_DOWN:
                pressed.add(name)
            elif event.event_type == keyboard.KEY_UP:
                if len(pressed) >= 2:
                    combo = "+".join(sorted(pressed))
                    result = combo
                    pressed.clear()
                    self._active = False
                    return False  # Suppress this last event
                pressed.discard(name)
            return False  # Suppress all events during recording

        hook = keyboard.hook(on_event)

        # Wait until combo captured or told to stop
        while self._active and result is None:
            time.sleep(0.05)

        keyboard.unhook(hook)

        if result:
            self.recorded.emit(result)


# --- Dialogs ---

DIALOG_STYLE = """
QDialog {
    background-color: transparent;
    font-family: Calibri;
}
QLabel {
    color: #dcdcdc;
    font-family: Calibri;
}
QPushButton {
    background-color: #3c3c3c;
    color: #dcdcdc;
    border: 1px solid #555;
    border-radius: 5px;
    padding: 8px 20px;
    font-size: 10pt;
    font-family: Calibri;
}
QPushButton:hover {
    background-color: #555;
}
 QPushButton:disabled {
    color: #666;
    background-color: #333;
}
"""


class _FramelessDialog(QDialog):
    """Base class for frameless dark-themed dialogs."""

    _BG_COLOR = QColor(43, 43, 43, 235)
    _RADIUS = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Dialog
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(DIALOG_STYLE)
        self._drag_pos = None
        try:
            from main import resource_path, ICON_FILENAME
            self.setWindowIcon(QIcon(resource_path(ICON_FILENAME)))
        except Exception:
            pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(self._BG_COLOR))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), self._RADIUS, self._RADIUS)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def _make_close_btn(self):
        btn = QPushButton("X")
        btn.setFixedSize(28, 28)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #999;
                border: none;
                font-size: 14pt;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                color: #f44;
                background-color: rgba(255,255,255,30);
                border-radius: 4px;
            }
        """)
        btn.clicked.connect(self.reject)
        return btn


class HotkeyDialog(_FramelessDialog):
    """Dialog for recording and setting a new hotkey."""

    def __init__(self, current_hotkey, parent=None):
        super().__init__(parent)
        self.current_hotkey = current_hotkey
        self.new_hotkey = None
        self._recorder = None
        self.setFixedSize(360, 210)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 12, 24, 16)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_row.addWidget(self._make_close_btn())
        layout.addLayout(close_row)

        self.title = QLabel("Change Hotkey")
        self.title.setStyleSheet(
            "font-size: 13pt; font-weight: bold; color: #dcdcdc;"
        )
        self.title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title)

        self.hotkey_label = QLabel(
            f"Current: {format_hotkey(self.current_hotkey)}"
        )
        self.hotkey_label.setStyleSheet("font-size: 11pt; color: #aaa;")
        self.hotkey_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.hotkey_label)

        self.record_btn = QPushButton("Record New Hotkey")
        self.record_btn.setFixedHeight(40)
        self.record_btn.setCursor(Qt.PointingHandCursor)
        self.record_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d7;
                color: #fff;
                border: none;
                border-radius: 5px;
                padding: 8px 24px;
                font-size: 11pt;
                font-weight: bold;
                font-family: Calibri;
            }
            QPushButton:hover {
                background-color: #1a8ae8;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #666;
            }
        """)
        self.record_btn.clicked.connect(self._on_record)
        layout.addWidget(self.record_btn)

        btn_row = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedHeight(32)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setFixedHeight(32)
        self.apply_btn.setCursor(Qt.PointingHandCursor)
        self.apply_btn.setEnabled(False)
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d7d46;
                color: #fff;
                border: none;
                border-radius: 5px;
                padding: 8px 24px;
                font-size: 10pt;
                font-weight: bold;
                font-family: Calibri;
            }
            QPushButton:hover {
                background-color: #3da85a;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #666;
            }
        """)
        self.apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(self.apply_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)

    def _on_record(self):
        self.record_btn.setText("Press new hotkey...")
        self.record_btn.setEnabled(False)
        self.apply_btn.setEnabled(False)
        self._recorder = HotkeyRecorder()
        self._recorder.recorded.connect(self._on_recorded)
        self._recorder.start()

    def _on_recorded(self, hotkey_str):
        normalized = normalize_hotkey(hotkey_str)
        if not is_valid_hotkey(normalized):
            if is_blocked_hotkey(normalized):
                self.hotkey_label.setText(
                    "That combination is reserved by Windows"
                )
            else:
                self.hotkey_label.setText(
                    "Must include a modifier (Ctrl/Alt/Shift/Win)"
                )
            self.hotkey_label.setStyleSheet("font-size: 10pt; color: #f90;")
            self.record_btn.setText("Record Again")
            self.record_btn.setEnabled(True)
            self.new_hotkey = None
            return

        self.new_hotkey = normalized
        self.hotkey_label.setText(f"New: {format_hotkey(normalized)}")
        self.hotkey_label.setStyleSheet("font-size: 11pt; color: #dcdcdc;")
        self.record_btn.setText("Record Again")
        self.record_btn.setEnabled(True)
        self.apply_btn.setEnabled(True)

    def _on_apply(self):
        if self.new_hotkey:
            self.accept()

    def reject(self):
        if self._recorder and self._recorder.isRunning():
            self._recorder.stop()
        super().reject()
