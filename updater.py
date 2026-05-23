# updater.py — Self-update logic for LaTeX-Inserter

import urllib.request
import urllib.error
import json
import hashlib
import os
import sys
import ssl
import shutil
import tempfile

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QProgressBar, QHBoxLayout
)

GITHUB_API_URL = "https://api.github.com/repos/lsutorus/latex-inserter/releases/latest"
UPDATE_TEMP_DIR = os.path.join(tempfile.gettempdir(), "latex-inserter-update")
USER_AGENT = "LaTeX-Inserter-Updater"


class UpdateInfo:
    """Parsed result from the GitHub Releases API."""
    def __init__(self, version, changelog, exe_url, sha256_url):
        self.version = version          # "1.1.0" (no v prefix)
        self.changelog = changelog      # release body markdown
        self.exe_url = exe_url          # browser_download_url for .exe
        self.sha256_url = sha256_url    # browser_download_url for .sha256


def parse_version(tag):
    """Convert version string like 'v1.2.3' or '1.2.3' to (1, 2, 3)."""
    v = tag.lstrip("v")
    parts = [int(p) for p in v.split(".")]
    # Pad to 3 components for consistent comparison
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def fetch_latest_release(current_version):
    """
    Query GitHub Releases API. Returns UpdateInfo if a newer version exists,
    None if current is up to date. Raises on network/API errors.
    """
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    req = urllib.request.Request(
        GITHUB_API_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    )
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # no releases yet
        raise

    tag_name = data.get("tag_name", "")
    remote_version = tag_name.lstrip("v")
    if parse_version(remote_version) <= parse_version(current_version):
        return None

    changelog = data.get("body", "") or "No changelog provided."

    exe_url = None
    sha256_url = None
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        url = asset.get("browser_download_url", "")
        if name == "LaTeX-Inserter.exe":
            exe_url = url
        elif name == "LaTeX-Inserter.exe.sha256":
            sha256_url = url

    if not exe_url:
        raise RuntimeError("Release has no LaTeX-Inserter.exe asset.")
    if not sha256_url:
        raise RuntimeError("Release has no SHA256 hash file asset.")

    return UpdateInfo(remote_version, changelog, exe_url, sha256_url)


def download_file(url, dest, progress_callback=None):
    """Download url to dest. Reports progress via callback(0.0-1.0)."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total and progress_callback:
                        progress_callback(downloaded / total)
    except Exception:
        # Clean up partial download
        if os.path.exists(dest):
            try:
                os.remove(dest)
            except OSError:
                pass
        raise


def verify_sha256(filepath, expected_hex):
    """Compute SHA256 of file, compare to expected hex string."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest().lower() == expected_hex.lower()


def perform_update(update_info, current_pid, current_exe):
    """
    Full update sequence:
    1. Download new exe + .sha256 to temp dir
    2. Verify SHA256
    3. Launch update_helper.exe
    Caller must call QApplication.quit() after this returns.
    """
    os.makedirs(UPDATE_TEMP_DIR, exist_ok=True)
    new_exe_path = os.path.join(UPDATE_TEMP_DIR, "LaTeX-Inserter.exe")
    sha256_path = os.path.join(UPDATE_TEMP_DIR, "LaTeX-Inserter.exe.sha256")

    download_file(update_info.exe_url, new_exe_path)
    download_file(update_info.sha256_url, sha256_path)

    # Parse expected hash from .sha256 file (sha256sum format: "hash  filename")
    with open(sha256_path, "r") as f:
        expected_hash = f.read().split()[0]

    if not verify_sha256(new_exe_path, expected_hash):
        # Clean up — don't leave unverified binary around
        for p in (new_exe_path, sha256_path):
            if os.path.exists(p):
                try: os.remove(p)
                except OSError: pass
        raise RuntimeError(
            "SHA256 verification failed.\n"
            "The download may be corrupted or tampered with.\n"
            "Update aborted for safety."
        )

    # Locate update_helper.exe — same directory as current exe
    if getattr(sys, 'frozen', False):
        helper_path = os.path.join(os.path.dirname(current_exe), "update_helper.exe")
    else:
        helper_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "update_helper.exe")

    if not os.path.exists(helper_path):
        raise FileNotFoundError(
            f"Update helper not found at:\n{helper_path}\n\n"
            "Reinstall the application to restore the helper."
        )

    import subprocess
    subprocess.Popen(
        [helper_path, "--pid", str(current_pid), "--src", new_exe_path, "--dst", current_exe],
        close_fds=True
    )


class UpdateDialog(QDialog):
    """Dialog showing available update with Install/Later buttons."""

    def __init__(self, update_info, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.setWindowTitle("Update Available")
        self.setFixedSize(460, 320)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout()

        title = QLabel(f"Version {self.update_info.version} is available")
        title.setFont(title.font())
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(title)

        changelog_label = QLabel(self.update_info.changelog or "No changelog.")
        changelog_label.setWordWrap(True)
        changelog_label.setTextFormat(Qt.MarkdownText)
        changelog_label.setStyleSheet("color: #aaa; margin: 8px 0;")
        layout.addWidget(changelog_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()
        layout.addWidget(self.progress)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: #f90;")
        layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()
        self.install_btn = QPushButton("Install Update")
        self.install_btn.setDefault(True)
        self.install_btn.clicked.connect(self._on_install)
        self.later_btn = QPushButton("Later")
        self.later_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.later_btn)
        btn_layout.addWidget(self.install_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def _on_install(self):
        self.install_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.progress.show()
        self.status_label.setText("Downloading update...")

        from PyQt5.QtCore import QCoreApplication

        def on_progress(pct):
            self.progress.setValue(int(pct * 100))
            QCoreApplication.processEvents()

        try:
            # Download + verify
            os.makedirs(UPDATE_TEMP_DIR, exist_ok=True)
            new_exe = os.path.join(UPDATE_TEMP_DIR, "LaTeX-Inserter.exe")
            sha_file = os.path.join(UPDATE_TEMP_DIR, "LaTeX-Inserter.exe.sha256")

            download_file(
                self.update_info.exe_url, new_exe,
                progress_callback=on_progress
            )
            download_file(self.update_info.sha256_url, sha_file)

            self.status_label.setText("Verifying integrity...")
            QCoreApplication.processEvents()

            with open(sha_file, "r") as f:
                expected_hash = f.read().split()[0]

            if not verify_sha256(new_exe, expected_hash):
                for p in (new_exe, sha_file):
                    if os.path.exists(p):
                        try: os.remove(p)
                        except OSError: pass
                self.status_label.setText("SHA256 verification failed. Update aborted.")
                self.status_label.setStyleSheet("color: #f44;")
                self.install_btn.setEnabled(True)
                self.later_btn.setEnabled(True)
                self.progress.hide()
                return

            # Launch helper and quit
            self.status_label.setText("Installing... the app will restart shortly.")
            QCoreApplication.processEvents()

            perform_update(
                self.update_info, os.getpid(), sys.executable
            )
            # If perform_update didn't raise, accept dialog and quit app
            self.accept()
            from PyQt5.QtWidgets import QApplication
            QApplication.quit()

        except Exception as e:
            self.status_label.setText(f"Update failed: {e}")
            self.status_label.setStyleSheet("color: #f44;")
            self.install_btn.setEnabled(True)
            self.later_btn.setEnabled(True)
            self.progress.hide()
