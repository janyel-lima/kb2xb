#!/usr/bin/env python3
"""
kb2xb_gui.py  —  PySide6 front-end for the kb2xb engine.

Place this file alongside kb2xb.py.

Dependencies (Arch / CachyOS):
  sudo pacman -S pyside6 python-evdev
  yay  -S python-uinput

Run:
  python kb2xb_gui.py
  kb2xb-gui
"""
from __future__ import annotations

import os, sys, re, types, time
from pathlib import Path
from typing  import Optional

# ─────────────────────────────────────────────────────────────────────────────
#  Engine — loaded without triggering the venv bootstrap
# ─────────────────────────────────────────────────────────────────────────────
def _load_engine() -> types.ModuleType:
    p = Path(__file__).with_name("kb2xb.py")
    if not p.exists():
        sys.exit(f"[gui] kb2xb.py not found next to this script ({p})")
    src = p.read_text().replace(
        "\n_bootstrap()\n",
        "\n# bootstrap disabled (GUI mode — deps managed externally)\n",
    )
    mod = types.ModuleType("kb2xb")
    mod.__file__ = str(p)
    # Register before exec so Python 3.14+ dataclass machinery can find it.
    sys.modules["kb2xb"] = mod
    exec(compile(src, str(p), "exec"), mod.__dict__)
    return mod

_eng            = _load_engine()
__version__     = _eng.__version__
Profile         = _eng.Profile
ProfileManager  = _eng.ProfileManager
Settings        = _eng.Settings
KeyMap          = _eng.KeyMap
MouseConfig     = _eng.MouseConfig
DeviceConfig    = _eng.DeviceConfig
XboxEmulator    = _eng.XboxEmulator
_find_keyboards = _eng._find_keyboards
_find_mice      = _eng._find_mice
_NAME_TO_CODE   = _eng._NAME_TO_CODE

# ─────────────────────────────────────────────────────────────────────────────
#  Qt
# ─────────────────────────────────────────────────────────────────────────────
try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QDialog, QDialogButtonBox,
        QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
        QPushButton, QLabel, QListWidget, QListWidgetItem,
        QCheckBox, QSlider, QSpinBox, QLineEdit, QTabWidget,
        QGroupBox, QScrollArea, QSplitter, QFrame, QSizePolicy,
        QSystemTrayIcon, QMenu, QMessageBox, QAbstractItemView,
        QSizeGrip,
    )
    from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize, QPoint
    from PySide6.QtGui  import (
        QColor, QFont, QIcon, QPainter, QPixmap, QKeyEvent, QAction,
    )
except ImportError as exc:
    sys.exit(
        f"PySide6 not found ({exc}).\n"
        "  Install: sudo pacman -S python-pyside6"
    )

# ─────────────────────────────────────────────────────────────────────────────
#  Qt key → kb2xb name
# ─────────────────────────────────────────────────────────────────────────────
_QK = Qt.Key
_QT_TO_NAME: dict[int, str] = {
    **{getattr(_QK, f"Key_{c.upper()}"): c for c in "abcdefghijklmnopqrstuvwxyz"},
    **{getattr(_QK, f"Key_{n}"): str(n) for n in range(10)},
    **{getattr(_QK, f"Key_F{n}"): f"f{n}" for n in range(1, 13)},
    _QK.Key_Space:    "space",       _QK.Key_Return:    "return",
    _QK.Key_Enter:    "enter",       _QK.Key_Backspace: "backspace",
    _QK.Key_Tab:      "tab",         _QK.Key_Escape:    "escape",
    _QK.Key_Up:       "up",          _QK.Key_Down:      "down",
    _QK.Key_Left:     "left",        _QK.Key_Right:     "right",
    _QK.Key_Control:  "ctrl_l",      _QK.Key_Alt:       "alt_l",
    _QK.Key_Shift:    "shift_l",     _QK.Key_Meta:      "super_l",
    _QK.Key_CapsLock: "caps_lock",   _QK.Key_Delete:    "delete",
    _QK.Key_Insert:   "insert",      _QK.Key_Home:      "home",
    _QK.Key_End:      "end",         _QK.Key_PageUp:    "page_up",
    _QK.Key_PageDown: "page_down",   _QK.Key_Minus:     "minus",
    _QK.Key_Equal:    "equal",       _QK.Key_Comma:     "comma",
    _QK.Key_Period:   "period",      _QK.Key_Slash:     "slash",
    _QK.Key_Semicolon:"semicolon",   _QK.Key_Apostrophe:"apostrophe",
    _QK.Key_BracketLeft:"bracket_left", _QK.Key_BracketRight:"bracket_right",
    _QK.Key_Backslash:"backslash",   _QK.Key_QuoteLeft: "grave",
    _QK.Key_Print:    "print_screen",_QK.Key_ScrollLock:"scroll_lock",
    _QK.Key_Pause:    "pause",       _QK.Key_NumLock:   "num_lock",
    _QK.Key_Menu:     "menu",
}

# ─────────────────────────────────────────────────────────────────────────────
#  Stylesheet  (GitHub dark theme palette)
# ─────────────────────────────────────────────────────────────────────────────
_STYLE = """
/* ══════════════════════════════════════════════════════════════════════
   Kb2Xb · Arcana Theme · CachyOS KDE Plasma
   Palette:
     Void     #0a0a11  #0e0e1a  #12121f  #18182c
     Border   #1e1e38  #2c2c50  #6e5bdf (glow)
     Violet   #4c1d95  #5b21b6  #7c3aed  #8b5cf6  #a78bfa  #c4b5fd
     Cyan     #67e8f9
     Green    #86efac
     Red      #f87171
     Amber    #fbbf24
     Text     #e2e8f0  #cbd5e1  #94a3b8  #475569
   ══════════════════════════════════════════════════════════════════════ */

* { outline: none; }

QWidget {
    background: #0a0a11;
    color: #e2e8f0;
    font-size: 13px;
    font-family: "Noto Sans", "Inter", "Segoe UI", sans-serif;
}

QMainWindow, QDialog { background: #0a0a11; }

/* ── GroupBox ─────────────────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid #1e1e38;
    border-radius: 9px;
    margin-top: 1.3em;
    padding-top: 14px;
    font-weight: 800;
    color: #8b5cf6;
    font-size: 10px;
    letter-spacing: 1.5px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    background: #0a0a11;
}

/* ── List ─────────────────────────────────────────────────────────────── */
QListWidget {
    background: #0e0e1a;
    border: 1px solid #1e1e38;
    border-radius: 9px;
    outline: none;
    padding: 5px;
}
QListWidget::item {
    padding: 9px 14px;
    border-radius: 6px;
    margin: 1px 0;
    color: #cbd5e1;
}
QListWidget::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #3b0764, stop:1 #4c1d95);
    color: #ede9fe;
    border: 1px solid #5b21b6;
}
QListWidget::item:hover:!selected {
    background: #14142a;
    color: #e2e8f0;
}

/* ── Default Button ───────────────────────────────────────────────────── */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1a1a30, stop:1 #121224);
    border: 1px solid #2c2c50;
    border-radius: 7px;
    padding: 5px 16px;
    color: #b0bac8;
    min-height: 28px;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #252548, stop:1 #1a1a38);
    border-color: #6e5bdf;
    color: #ede9fe;
}
QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #4c1d95, stop:1 #3b0764);
    border-color: #8b5cf6;
    color: #fff;
}
QPushButton:disabled {
    color: #334155;
    border-color: #151528;
    background: #0c0c18;
}

/* ── Primary btn: base ────────────────────────────────────────────────── */
QPushButton#btn_primary {
    font-size: 13px;
    font-weight: 800;
    min-height: 58px;
    border-radius: 10px;
    letter-spacing: 2.5px;
    padding: 0 24px;
    color: #ffffff;
}

/* ── STOP button — styled via setStyleSheet() in code ────────────────── */
QPushButton#btn_stop {
    font-size: 13px;
    font-weight: 800;
    min-height: 58px;
    border-radius: 10px;
    letter-spacing: 2.5px;
    padding: 0 24px;
}

/* ── Key-capture button ───────────────────────────────────────────────── */
QPushButton#btn_capture {
    background: #0e0e1a;
    border: 1px dashed #2c2c50;
    border-radius: 6px;
    font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", monospace;
    font-size: 12px;
    padding: 3px 12px;
    min-width: 96px;
    color: #67e8f9;
    min-height: 26px;
}
QPushButton#btn_capture:hover {
    background: #12122a;
    border-style: solid;
    border-color: #8b5cf6;
    color: #a78bfa;
}
QPushButton#btn_capture[capturing="true"] {
    border-style: solid;
    border-color: #f87171;
    color: #f87171;
    background: #1a0a0a;
}

/* ── Small toolbar button ─────────────────────────────────────────────── */
QPushButton#btn_sm {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1a1a30, stop:1 #121224);
    border: 1px solid #2c2c50;
    border-radius: 6px;
    padding: 3px 12px;
    min-height: 26px;
    font-size: 12px;
    color: #94a3b8;
}
QPushButton#btn_sm:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #252548, stop:1 #1a1a38);
    border-color: #6e5bdf;
    color: #ede9fe;
}
QPushButton#btn_sm:pressed {
    background: #3b0764;
    border-color: #8b5cf6;
    color: #fff;
}
QPushButton#btn_sm:disabled {
    color: #334155;
    border-color: #151528;
    background: #0c0c18;
}

/* ── Line edit / Spin box ─────────────────────────────────────────────── */
QLineEdit, QSpinBox {
    background: #0e0e1a;
    border: 1px solid #2c2c50;
    border-radius: 7px;
    padding: 4px 10px;
    color: #e2e8f0;
    min-height: 30px;
    selection-background-color: #4c1d95;
    selection-color: #ede9fe;
}
QLineEdit:hover, QSpinBox:hover { border-color: #3d3d70; }
QLineEdit:focus, QSpinBox:focus {
    border-color: #7c3aed;
    background: #10101f;
}
QSpinBox::up-button, QSpinBox::down-button {
    width: 20px;
    border: none;
    background: #1e1e38;
    border-radius: 3px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #2c2c50; }

/* ── Slider ───────────────────────────────────────────────────────────── */
QSlider::groove:horizontal {
    height: 4px;
    background: #1e1e38;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    margin: -6px 0;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #a78bfa, stop:1 #7c3aed);
    border-radius: 8px;
    border: 2px solid #0a0a11;
}
QSlider::handle:horizontal:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #c4b5fd, stop:1 #a78bfa);
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #4c1d95, stop:1 #7c3aed);
    border-radius: 2px;
}

/* ── Tabs ─────────────────────────────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #1e1e38;
    border-radius: 0 9px 9px 9px;
    background: #0e0e1a;
    top: -1px;
}
QTabBar::tab {
    background: #0a0a11;
    border: 1px solid #1e1e38;
    border-bottom: none;
    padding: 8px 22px;
    color: #475569;
    border-radius: 7px 7px 0 0;
    margin-right: 3px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.4px;
}
QTabBar::tab:selected {
    background: #0e0e1a;
    color: #a78bfa;
    border-color: #2c2c50;
    border-bottom: 1px solid #0e0e1a;
}
QTabBar::tab:hover:!selected {
    color: #c4b5fd;
    background: #10101e;
    border-color: #2c2c50;
}

/* ── Checkbox ─────────────────────────────────────────────────────────── */
QCheckBox { spacing: 10px; color: #cbd5e1; }
QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border: 1px solid #2c2c50;
    border-radius: 5px;
    background: #0e0e1a;
}
QCheckBox::indicator:checked {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #7c3aed, stop:1 #4c1d95);
    border-color: #8b5cf6;
}
QCheckBox::indicator:hover { border-color: #7c3aed; }

/* ── Scrollbars ───────────────────────────────────────────────────────── */
QScrollBar:vertical {
    width: 6px;
    background: transparent;
    border-radius: 3px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #2c2c50;
    border-radius: 3px;
    min-height: 28px;
}
QScrollBar::handle:vertical:hover { background: #5b21b6; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { height: 6px; background: transparent; }
QScrollBar::handle:horizontal {
    background: #2c2c50;
    border-radius: 3px;
    min-width: 28px;
}
QScrollBar::handle:horizontal:hover { background: #5b21b6; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Separator lines ──────────────────────────────────────────────────── */
QFrame[frameShape="4"], QFrame[frameShape="5"] { color: #18182c; }

/* ── Context menu ─────────────────────────────────────────────────────── */
QMenu {
    background: #10101e;
    border: 1px solid #2c2c50;
    border-radius: 9px;
    padding: 5px;
}
QMenu::item {
    padding: 8px 22px;
    border-radius: 5px;
    color: #cbd5e1;
    font-size: 13px;
}
QMenu::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #3b0764, stop:1 #4c1d95);
    color: #ede9fe;
}
QMenu::separator {
    height: 1px;
    background: #1e1e38;
    margin: 5px 10px;
}

/* ── Dialog buttons ───────────────────────────────────────────────────── */
QDialogButtonBox QPushButton { min-width: 88px; }

/* ── Custom named labels ──────────────────────────────────────────────── */
QLabel#lbl_dot { font-size: 20px; }

QLabel#lbl_section {
    font-size: 10px;
    font-weight: 800;
    color: #4b4b7a;
    letter-spacing: 2px;
    padding: 2px 0 6px 2px;
}

/* ── Splitter ─────────────────────────────────────────────────────────── */
QSplitter::handle { background: #18182c; }
"""

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _dot_icon(color: str, size: int = 20) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawEllipse(1, 1, size - 2, size - 2)
    p.end()
    return QIcon(pm)


def _section(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("lbl_section")
    return lbl


def _h_sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    return f


def _repaint_btn(btn: QPushButton) -> None:
    """Force QSS re-evaluation after a dynamic property change."""
    btn.style().unpolish(btn)
    btn.style().polish(btn)
    btn.update()


# ─────────────────────────────────────────────────────────────────────────────
#  KeyCaptureButton
# ─────────────────────────────────────────────────────────────────────────────
class KeyCaptureButton(QPushButton):
    key_captured = Signal(str)

    def __init__(self, key_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(key_name, parent)
        self._capturing  = False
        self._stored_key = key_name
        self.setObjectName("btn_capture")
        self.setFocusPolicy(Qt.StrongFocus)
        self.clicked.connect(self._start_capture)

    def set_key(self, name: str) -> None:
        self._stored_key = name
        if not self._capturing:
            self.setText(name)

    def _set_capturing(self, on: bool) -> None:
        self._capturing = on
        self.setProperty("capturing", "true" if on else "false")
        _repaint_btn(self)

    def _start_capture(self) -> None:
        self._set_capturing(True)
        self.setText("⌨  press a key …")
        self.setFocus()
        self.grabKeyboard()

    def _finish(self, name: str) -> None:
        self.releaseKeyboard()
        self._set_capturing(False)
        self._stored_key = name
        self.setText(name)
        self.key_captured.emit(name)

    def _cancel(self) -> None:
        self.releaseKeyboard()
        self._set_capturing(False)
        self.setText(self._stored_key)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self._capturing:
            return super().keyPressEvent(event)
        if event.key() == Qt.Key_Escape:
            self._cancel()
            return
        name = _QT_TO_NAME.get(event.key())
        if name and name in _NAME_TO_CODE:
            self._finish(name)

    def focusOutEvent(self, event) -> None:
        if self._capturing:
            self._cancel()
        super().focusOutEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
#  EmulatorThread
#
#  Key design decisions:
#  - The uinput device is destroyed explicitly in the `finally` block so the
#    kernel releases the slot before `stopped` is emitted.  Without this Steam
#    registers a new ghost gamepad on every start/stop cycle without removing
#    the old one.
#  - Grabbed devices are ungrabbed in `finally` so the keyboard is always
#    returned to the desktop, even on error.
#  - `stopped` is always emitted, even when an exception occurs.
#  - `stop()` swallows OSError because `_release_all()` inside `emu.stop()`
#    may try to emit on an already-destroyed uinput fd — the device is gone,
#    so no keys are stuck.
# ─────────────────────────────────────────────────────────────────────────────
class EmulatorThread(QThread):
    started_ok = Signal()
    error      = Signal(str)
    stopped    = Signal()

    def __init__(self, profile: Profile, keyboards: list, mice: list) -> None:
        super().__init__()
        self._emu  = XboxEmulator(profile)
        self._kbs  = keyboards
        self._mice = mice

    def run(self) -> None:
        import threading as _th
        try:
            profile = self._emu._profile

            if profile.grab:
                for dev in self._kbs + self._mice:
                    try:
                        dev.grab()
                    except Exception:
                        pass

            self._emu._device = self._emu._make_device()

            delay = profile.startup_delay_ms / 1000.0
            if delay > 0:
                time.sleep(delay)

            threads = [
                *(_th.Thread(target=self._emu._kb_reader,    args=(kb,), daemon=True)
                  for kb in self._kbs),
                *(_th.Thread(target=self._emu._mouse_reader, args=(ms,), daemon=True)
                  for ms in self._mice),
            ]
            for t in threads:
                t.start()

            self.started_ok.emit()
            self._emu._stop.wait()

        except PermissionError:
            self.error.emit(
                "Permission denied — /dev/uinput is not accessible.\n\n"
                "Fix:\n"
                "  sudo usermod -aG input,uinput $USER\n"
                "  echo 'uinput' | sudo tee /etc/modules-load.d/uinput.conf\n"
                "  echo 'KERNEL==\"uinput\", GROUP=\"uinput\", MODE=\"0660\"'"
                "  | sudo tee /etc/udev/rules.d/60-kb2xb.rules\n"
                "  sudo udevadm control --reload-rules\n"
                "Then re-login or reboot."
            )
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            # Destroy the uinput device *before* signalling stopped.
            # This ensures the kernel releases the slot so Steam does not
            # accumulate ghost gamepads across start/stop cycles.
            try:
                dev = getattr(self._emu, "_device", None)
                if dev is not None:
                    dev.destroy()
                    self._emu._device = None
            except Exception:
                pass

            # Always ungrab input devices so the keyboard is returned
            # to the desktop immediately, even when an error occurred.
            for d in self._kbs + self._mice:
                try:
                    d.ungrab()
                except Exception:
                    pass

            self.stopped.emit()

    def stop(self) -> None:
        # `_release_all()` inside `emu.stop()` may attempt to emit/syn on a
        # uinput file-descriptor that the `finally` block already destroyed,
        # resulting in OSError EINVAL.  Silence it: the virtual device is gone
        # so no buttons are stuck.
        try:
            self._emu.stop()
        except OSError:
            pass


# ─────────────────────────────────────────────────────────────────────────────
#  ProfileEditorDialog
# ─────────────────────────────────────────────────────────────────────────────
class ProfileEditorDialog(QDialog):
    def __init__(self, profile: Profile, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._profile = profile
        self.setWindowTitle(f"✎  Edit  ·  {profile.display_name}")
        self.setMinimumWidth(600)
        self.setMinimumHeight(560)

        self._key_btns:       dict[str, KeyCaptureButton] = {}
        self._mouse_widgets:  dict = {}
        self._device_widgets: dict = {}
        self._opt_widgets:    dict = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 14)
        root.setSpacing(14)

        tabs = QTabWidget()
        tabs.addTab(self._make_keymap_tab(),  "⌨  Keymap")
        tabs.addTab(self._make_mouse_tab(),   "◈  Mouse")
        tabs.addTab(self._make_device_tab(),  "⬡  Device")
        tabs.addTab(self._make_options_tab(), "⚙  Options")
        root.addWidget(tabs)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        root.addWidget(sep)

        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        # Style save button green, cancel neutral
        save_btn   = bb.button(QDialogButtonBox.Save)
        cancel_btn = bb.button(QDialogButtonBox.Cancel)
        save_btn.setText("✔  Save")
        cancel_btn.setText("✕  Cancel")
        save_btn.setStyleSheet(
            "QPushButton { background:#15803d; border:1.5px solid #86efac;"
            " color:#ffffff; font-weight:700; padding:6px 20px; border-radius:7px;}"
            "QPushButton:hover { background:#16a34a; border-color:#bbf7d0;}"
            "QPushButton:pressed { background:#166534;}"
        )
        cancel_btn.setStyleSheet(
            "QPushButton { background:#1e1e38; border:1.5px solid #2c2c50;"
            " color:#94a3b8; font-weight:600; padding:6px 20px; border-radius:7px;}"
            "QPushButton:hover { background:#252548; color:#e2e8f0;}"
        )
        bb.accepted.connect(self._on_save)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _field_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#94a3b8; font-size:12px; font-weight:600;")
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return lbl

    @staticmethod
    def _hint(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            "color:#4b4b7a; font-size:11px; padding:6px 10px;"
            "background:#0c0c1a; border-radius:6px; border:1px solid #1e1e38;"
        )
        return lbl

    def _make_keymap_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        inner = QWidget()
        vbox  = QVBoxLayout(inner)
        vbox.setContentsMargins(14, 14, 14, 14)
        vbox.setSpacing(12)

        km = self._profile.keymap

        groups = [
            ("⬤  Left Stick", [
                ("↑  Up",    "ls_up"),   ("↓  Down",  "ls_down"),
                ("←  Left",  "ls_left"), ("→  Right", "ls_right"),
            ]),
            ("⬤  Right Stick", [
                ("↑  Up",    "rs_up"),   ("↓  Down",  "rs_down"),
                ("←  Left",  "rs_left"), ("→  Right", "rs_right"),
            ]),
            ("✛  D-Pad", [
                ("↑  Up",    "dp_up"),   ("↓  Down",  "dp_down"),
                ("←  Left",  "dp_left"), ("→  Right", "dp_right"),
            ]),
            ("◉  Face Buttons", [
                ("Ⓐ  A",  "a_btn"), ("Ⓑ  B",  "b_btn"),
                ("Ⓧ  X",  "x_btn"), ("Ⓨ  Y",  "y_btn"),
            ]),
            ("⊡  Bumpers & Triggers", [
                ("LB",  "lb"), ("RB",  "rb"),
                ("LT",  "lt"), ("RT",  "rt"),
            ]),
            ("⊙  Stick Clicks & Menu", [
                ("L3",    "l3"),    ("R3",    "r3"),
                ("Start ▶", "start"), ("View ☰",  "view"),
            ]),
        ]

        for group_name, fields in groups:
            gb   = QGroupBox(group_name)
            grid = QGridLayout(gb)
            grid.setSpacing(8)
            grid.setContentsMargins(12, 16, 12, 12)
            for i, (label, fname) in enumerate(fields):
                row, col = divmod(i, 2)
                lbl = self._field_label(label)
                btn = KeyCaptureButton(getattr(km, fname))
                btn.key_captured.connect(lambda name, f=fname: self._key_btns[f].set_key(name))
                self._key_btns[fname] = btn
                grid.addWidget(lbl, row, col * 2,     Qt.AlignRight)
                grid.addWidget(btn, row, col * 2 + 1, Qt.AlignLeft)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(3, 1)
            vbox.addWidget(gb)

        vbox.addWidget(self._hint(
            "⌨  Click any key button to enter capture mode, then press the desired key."
            "  Press Esc to cancel."
        ))
        vbox.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _make_mouse_tab(self) -> QWidget:
        w    = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(16, 16, 16, 16)
        vbox.setSpacing(16)
        mc   = self._profile.mouse

        for prefix, label, icon in [("ls", "Left Stick", "◈  "), ("rs", "Right Stick", "◈  ")]:
            gb   = QGroupBox(f"{icon}Mouse → {label}")
            form = QFormLayout(gb)
            form.setSpacing(12)
            form.setContentsMargins(14, 18, 14, 14)
            form.setLabelAlignment(Qt.AlignRight)

            enabled = QCheckBox("Enable mouse-to-stick")
            enabled.setChecked(getattr(mc, f"{prefix}_enabled"))

            key_btn = KeyCaptureButton(getattr(mc, f"{prefix}_key"))
            key_btn.key_captured.connect(lambda name, b=key_btn: b.set_key(name))

            sens_val    = QLabel(str(getattr(mc, f"{prefix}_sensitivity")))
            sens_val.setStyleSheet("color:#a78bfa; font-weight:700; min-width:36px;")
            sens_slider = QSlider(Qt.Horizontal)
            sens_slider.setRange(10, 2000)
            sens_slider.setValue(getattr(mc, f"{prefix}_sensitivity"))
            sens_slider.valueChanged.connect(lambda v, lbl=sens_val: lbl.setText(str(v)))

            sens_row = QWidget()
            sens_h   = QHBoxLayout(sens_row)
            sens_h.setContentsMargins(0, 0, 0, 0)
            sens_h.setSpacing(8)
            sens_h.addWidget(sens_slider, 1)
            sens_h.addWidget(sens_val)
            px_lbl = QLabel("px")
            px_lbl.setStyleSheet("color:#475569; font-size:11px;")
            sens_h.addWidget(px_lbl)

            form.addRow(self._field_label(""), enabled)
            form.addRow(self._field_label("Hold key:"),    key_btn)
            form.addRow(self._field_label("Sensitivity:"), sens_row)

            self._mouse_widgets[f"{prefix}_enabled"]     = enabled
            self._mouse_widgets[f"{prefix}_key"]         = key_btn
            self._mouse_widgets[f"{prefix}_sensitivity"] = sens_slider

            vbox.addWidget(gb)

        vbox.addWidget(self._hint(
            "◈  Hold the configured key while moving the mouse to steer the analog stick."
            "  Sensitivity = pixels needed for full deflection (lower = faster)."
        ))
        vbox.addStretch()
        return w

    def _make_device_tab(self) -> QWidget:
        w    = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(16, 16, 16, 16)
        vbox.setSpacing(12)
        dc   = self._profile.device

        gb   = QGroupBox("⬡  Virtual Gamepad Identity")
        form = QFormLayout(gb)
        form.setSpacing(12)
        form.setContentsMargins(14, 18, 14, 14)
        form.setLabelAlignment(Qt.AlignRight)

        name_edit    = QLineEdit(dc.name)
        vendor_spin  = QSpinBox(); vendor_spin.setRange(0, 0xFFFF);  vendor_spin.setValue(dc.vendor)
        product_spin = QSpinBox(); product_spin.setRange(0, 0xFFFF); product_spin.setValue(dc.product)
        version_spin = QSpinBox(); version_spin.setRange(0, 0xFFFF); version_spin.setValue(dc.version)

        form.addRow(self._field_label("Device name:"), name_edit)
        form.addRow(self._field_label("Vendor ID:"),   vendor_spin)
        form.addRow(self._field_label("Product ID:"),  product_spin)
        form.addRow(self._field_label("Version:"),     version_spin)

        vbox.addWidget(gb)
        vbox.addWidget(self._hint(
            "⬡  Default identity mimics a Microsoft Xbox One pad (045E:02D1).\n"
            "If a game rejects the pad, change Vendor/Product to match a controller it already supports.\n"
            "Set both to 0 for a generic HID gamepad."
        ))
        vbox.addStretch()

        self._device_widgets = {
            "name": name_edit, "vendor": vendor_spin,
            "product": product_spin, "version": version_spin,
        }
        return w

    def _make_options_tab(self) -> QWidget:
        w    = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(16, 16, 16, 16)
        vbox.setSpacing(12)
        p    = self._profile

        gb   = QGroupBox("⚙  Profile Settings")
        form = QFormLayout(gb)
        form.setSpacing(12)
        form.setContentsMargins(14, 18, 14, 14)
        form.setLabelAlignment(Qt.AlignRight)

        display_edit = QLineEdit(p.display_name)

        delay_spin = QSpinBox()
        delay_spin.setRange(0, 5000)
        delay_spin.setSuffix("  ms")
        delay_spin.setValue(p.startup_delay_ms)

        grab_chk = QCheckBox("Grab input devices  (exclusive access)")
        grab_chk.setChecked(p.grab)

        form.addRow(self._field_label("Display name:"),  display_edit)
        form.addRow(self._field_label("Startup delay:"), delay_spin)
        form.addRow(self._field_label(""),               grab_chk)

        vbox.addWidget(gb)
        vbox.addWidget(self._hint(
            "⚙  Startup delay — wait before the virtual pad becomes active (useful for games "
            "that scan controllers at launch).\n\n"
            "Grab — prevents other apps from reading the keyboard/mouse while active. "
            "Recommended for full immersion; disable if you need global hotkeys."
        ))
        vbox.addStretch()

        self._opt_widgets = {
            "display_name":     display_edit,
            "startup_delay_ms": delay_spin,
            "grab":             grab_chk,
        }
        return w

    def _on_save(self) -> None:
        p  = self._profile
        km = p.keymap
        mc = p.mouse
        dc = p.device

        for fname, btn in self._key_btns.items():
            setattr(km, fname, btn._stored_key)

        mc.ls_enabled     = self._mouse_widgets["ls_enabled"].isChecked()
        mc.ls_key         = self._mouse_widgets["ls_key"]._stored_key
        mc.ls_sensitivity = self._mouse_widgets["ls_sensitivity"].value()
        mc.rs_enabled     = self._mouse_widgets["rs_enabled"].isChecked()
        mc.rs_key         = self._mouse_widgets["rs_key"]._stored_key
        mc.rs_sensitivity = self._mouse_widgets["rs_sensitivity"].value()

        dc.name    = self._device_widgets["name"].text().strip()
        dc.vendor  = self._device_widgets["vendor"].value()
        dc.product = self._device_widgets["product"].value()
        dc.version = self._device_widgets["version"].value()

        p.display_name     = self._opt_widgets["display_name"].text().strip() or p.id
        p.startup_delay_ms = self._opt_widgets["startup_delay_ms"].value()
        p.grab             = self._opt_widgets["grab"].isChecked()

        try:
            p.validate()
        except ValueError as exc:
            QMessageBox.critical(self, "Validation error", str(exc))
            return

        p.save()
        self.accept()


# ─────────────────────────────────────────────────────────────────────────────
#  NewProfileDialog
# ─────────────────────────────────────────────────────────────────────────────
class NewProfileDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("＋  New Profile")
        self.setFixedWidth(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(14)

        # Header
        header = QLabel("＋  Create Profile")
        header.setStyleSheet(
            "font-size:15px; font-weight:800; color:#a78bfa; letter-spacing:1px;"
        )
        root.addWidget(header)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        root.addWidget(sep)

        # Form
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight)

        self._id_edit    = QLineEdit()
        self._name_edit  = QLineEdit()
        self._clone_edit = QLineEdit()

        self._id_edit.setPlaceholderText("e.g. elden_ring   (a-z  0-9  _  -)")
        self._name_edit.setPlaceholderText("e.g. Elden Ring")
        self._clone_edit.setPlaceholderText("leave empty to start from defaults")

        def _lbl(t):
            l = QLabel(t)
            l.setStyleSheet("color:#94a3b8; font-size:12px; font-weight:600;")
            return l

        form.addRow(_lbl("⬡  Profile ID:"),    self._id_edit)
        form.addRow(_lbl("✎  Display name:"),  self._name_edit)
        form.addRow(_lbl("⊕  Clone from ID:"), self._clone_edit)
        root.addLayout(form)

        # Hint
        hint = QLabel(
            "Profile ID is used internally (no spaces). Display name is shown in the list."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            "color:#4b4b7a; font-size:11px; padding:8px 10px;"
            "background:#0c0c1a; border-radius:6px; border:1px solid #1e1e38;"
        )
        root.addWidget(hint)

        root.addStretch()

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        root.addWidget(sep2)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_btn     = bb.button(QDialogButtonBox.Ok)
        cancel_btn = bb.button(QDialogButtonBox.Cancel)
        ok_btn.setText("＋  Create")
        cancel_btn.setText("✕  Cancel")
        ok_btn.setStyleSheet(
            "QPushButton { background:#5b21b6; border:1.5px solid #8b5cf6;"
            " color:#fff; font-weight:700; padding:6px 20px; border-radius:7px;}"
            "QPushButton:hover { background:#6d28d9; border-color:#a78bfa;}"
            "QPushButton:pressed { background:#4c1d95;}"
        )
        cancel_btn.setStyleSheet(
            "QPushButton { background:#1e1e38; border:1.5px solid #2c2c50;"
            " color:#94a3b8; font-weight:600; padding:6px 20px; border-radius:7px;}"
            "QPushButton:hover { background:#252548; color:#e2e8f0;}"
        )
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _on_ok(self) -> None:
        pid = self._id_edit.text().strip()
        if not re.match(r'^[a-z0-9][a-z0-9_-]*$', pid):
            QMessageBox.warning(self, "Invalid ID",
                "Profile ID must start with a letter/digit "
                "and contain only [a-z 0-9 _ -].")
            return
        self.accept()

    @property
    def profile_id(self) -> str:
        return self._id_edit.text().strip()

    @property
    def display_name(self) -> str:
        return self._name_edit.text().strip() or self.profile_id

    @property
    def clone_from(self) -> Optional[str]:
        v = self._clone_edit.text().strip()
        return v if v else None


# ─────────────────────────────────────────────────────────────────────────────
#  AboutDialog
# ─────────────────────────────────────────────────────────────────────────────
class AboutDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ℹ  About  Kb2Xb")
        self.setFixedSize(460, 290)

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(32, 28, 32, 22)
        vbox.setSpacing(0)

        title = QLabel("Kb2Xb")
        title.setStyleSheet(
            "font-size:28px; font-weight:800; color:#a78bfa; letter-spacing:3px;"
        )
        title.setAlignment(Qt.AlignCenter)
        vbox.addWidget(title)

        sub = QLabel(f"v{__version__}  ·  Keyboard + Mouse  →  Xbox One gamepad")
        sub.setStyleSheet("color:#6d6d9e; font-size:11px; font-style:italic;")
        sub.setAlignment(Qt.AlignCenter)
        vbox.addWidget(sub)

        vbox.addSpacing(14)
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        vbox.addWidget(sep)
        vbox.addSpacing(12)

        desc = QLabel(
            "Maps any keyboard (and optionally mouse) to a virtual Xbox One "
            "controller via evdev/uinput — no game configuration required. "
            "Works on Wayland and X11."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#cbd5e1; font-size:12px; line-height:1.6;")
        desc.setAlignment(Qt.AlignCenter)
        vbox.addWidget(desc)

        vbox.addSpacing(10)

        author = QLabel(
            "<span style='color:#475569'>by </span>"
            "<a style='color:#a78bfa;text-decoration:none;font-weight:700' "
            "href='https://github.com/janyel-lima'>Janyel Lima</a>"
        )
        author.setOpenExternalLinks(True)
        author.setAlignment(Qt.AlignCenter)
        author.setStyleSheet("font-size:12px;")
        vbox.addWidget(author)

        vbox.addSpacing(6)

        link = QLabel(
            "<a style='color:#6d6d9e;text-decoration:none;font-size:11px' "
            "href='https://github.com/janyel-lima/kb2xb'>"
            "⇗  github.com/janyel-lima/kb2xb</a>"
        )
        link.setOpenExternalLinks(True)
        link.setAlignment(Qt.AlignCenter)
        vbox.addWidget(link)

        vbox.addStretch()

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        vbox.addWidget(sep2)
        vbox.addSpacing(10)

        bb = QDialogButtonBox(QDialogButtonBox.Close)
        close_btn = bb.button(QDialogButtonBox.Close)
        close_btn.setText("✕  Close")
        close_btn.setStyleSheet(
            "QPushButton { background:#1e1e38; border:1.5px solid #2c2c50;"
            " color:#94a3b8; font-weight:600; padding:6px 20px; border-radius:7px;}"
            "QPushButton:hover { background:#252548; color:#e2e8f0;}"
        )
        bb.rejected.connect(self.reject)
        vbox.addWidget(bb)


# ─────────────────────────────────────────────────────────────────────────────
#  MainWindow
# ─────────────────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Kb2Xb  —  v{__version__}")
        self.setMinimumSize(680, 480)

        ProfileManager.ensure_defaults()
        self._settings = Settings.load()
        self._profiles: list[Profile] = []
        self._keyboards: list        = []
        self._mice:      list        = []
        self._selected_kbs: list     = []

        self._running           = False
        self._active_profile_id: Optional[str] = None
        self._hotswap_pending   = False
        self._emu_thread: Optional[EmulatorThread] = None

        self._build_ui()
        self._build_tray()
        self._refresh_profiles()
        self._refresh_devices()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)

        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([300, 420])
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter, 1)
        root.addWidget(self._build_bottom_bar())

    def _build_left_panel(self) -> QWidget:
        w    = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(16, 16, 8, 16)
        vbox.setSpacing(10)

        vbox.addWidget(_section("⊟  Profiles"))

        self._profile_list = QListWidget()
        self._profile_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._profile_list.currentRowChanged.connect(self._on_profile_selected)
        vbox.addWidget(self._profile_list, 1)

        btns = QHBoxLayout()
        btns.setSpacing(6)
        for label, slot in [("＋  New", self._on_new), ("⊕  Clone", self._on_clone),
                             ("✎  Edit", self._on_edit), ("✕  Delete", self._on_delete)]:
            b = QPushButton(label)
            b.setObjectName("btn_sm")
            b.clicked.connect(slot)
            btns.addWidget(b)
        vbox.addLayout(btns)

        return w

    def _build_right_panel(self) -> QWidget:
        w    = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(8, 16, 16, 16)
        vbox.setSpacing(10)

        vbox.addWidget(_section("⌨  Input Devices"))

        self._kb_list = QListWidget()
        self._kb_list.setSelectionMode(QAbstractItemView.NoSelection)
        self._kb_list.itemChanged.connect(self._on_kb_check)
        vbox.addWidget(self._kb_list, 1)

        refresh_btn = QPushButton("↺  Refresh Devices")
        refresh_btn.setObjectName("btn_sm")
        refresh_btn.clicked.connect(self._refresh_devices)
        vbox.addWidget(refresh_btn)

        vbox.addSpacing(4)
        vbox.addWidget(_h_sep())
        vbox.addSpacing(4)

        # ── Status ─────────────────────────────────────────────────────
        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        self._status_dot = QLabel("⬤")
        self._status_dot.setObjectName("lbl_dot")
        self._status_dot.setStyleSheet("color: #334155;")
        self._status_lbl = QLabel("Stopped")
        self._status_lbl.setStyleSheet("color: #475569; font-size: 12px; font-weight: 600;")
        status_row.addWidget(self._status_dot)
        status_row.addWidget(self._status_lbl, 1)
        vbox.addLayout(status_row)

        return w

    def _build_bottom_bar(self) -> QWidget:
        bar  = QWidget()
        bar.setStyleSheet("background: #0c0c1a; border-top: 1px solid #1e1e38;")
        hbox = QHBoxLayout(bar)
        hbox.setContentsMargins(16, 12, 16, 12)
        hbox.setSpacing(10)

        self._primary_btn = QPushButton("▶  START")
        self._primary_btn.setObjectName("btn_primary")
        self._primary_btn.clicked.connect(self._on_primary)

        self._stop_btn = QPushButton("■  STOP")
        self._stop_btn.setObjectName("btn_stop")
        self._set_stop(False)
        self._stop_btn.clicked.connect(self._on_stop)

        hbox.addWidget(self._primary_btn, 3)
        hbox.addWidget(self._stop_btn,    1)
        return bar

    def _build_tray(self) -> None:
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(_dot_icon("#334155"))
        self._tray.setToolTip("Kb2Xb — stopped")

        menu = QMenu()
        self._tray_status_action = menu.addAction("Stopped")
        self._tray_status_action.setEnabled(False)
        menu.addSeparator()
        menu.addAction("◻  Show window", self._show_window)
        menu.addAction("■  Stop", self._on_stop)
        menu.addSeparator()
        menu.addAction(f"ℹ  About  v{__version__}", self._show_about)
        menu.addAction("⏻  Quit", self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    # ── Status helpers ────────────────────────────────────────────────────────

    def _set_running_status(self, profile_name: str) -> None:
        self._status_dot.setStyleSheet("color: #86efac;")
        self._status_lbl.setText(f"Running  ·  {profile_name}")
        self._status_lbl.setStyleSheet("color: #86efac; font-size: 12px; font-weight: 600;")

    def _set_stopped_status(self) -> None:
        self._status_dot.setStyleSheet("color: #334155;")
        self._status_lbl.setText("Stopped")
        self._status_lbl.setStyleSheet("color: #475569; font-size: 12px; font-weight: 600;")

    def _set_error_status(self) -> None:
        self._status_dot.setStyleSheet("color: #f87171;")
        self._status_lbl.setText("Error — see dialog")
        self._status_lbl.setStyleSheet("color: #f87171; font-size: 12px; font-weight: 600;")
        self._running           = False
        self._active_profile_id = None
        self._set_stop(False)
        self._refresh_profile_list_style()
        self._update_primary_btn()
        self._update_tray(False)

    def _set_swapping_status(self) -> None:
        self._status_dot.setStyleSheet("color: #fbbf24;")
        self._status_lbl.setText("Swapping profile…")
        self._status_lbl.setStyleSheet("color: #fbbf24; font-size: 12px; font-weight: 600;")

    def _update_tray(self, running: bool, profile_name: str = "") -> None:
        if running:
            self._tray.setIcon(_dot_icon("#86efac"))
            self._tray.setToolTip(f"Kb2Xb — {profile_name}")
            self._tray_status_action.setText(f"Running: {profile_name}")
        else:
            self._tray.setIcon(_dot_icon("#334155"))
            self._tray.setToolTip("Kb2Xb — stopped")
            self._tray_status_action.setText("Stopped")

    # ── Button style constants ─────────────────────────────────────────────
    _BTN_START = (
        "QPushButton {"
        "  background: #7c3aed;"
        "  border: 1.5px solid #a78bfa;"
        "  color: #ffffff;"
        "}"
        "QPushButton:hover {"
        "  background: #8b5cf6;"
        "  border-color: #c4b5fd;"
        "}"
        "QPushButton:pressed {"
        "  background: #6d28d9;"
        "}"
    )
    _BTN_HOTSWAP = (
        "QPushButton {"
        "  background: #d97706;"
        "  border: 1.5px solid #fbbf24;"
        "  color: #ffffff;"
        "}"
        "QPushButton:hover {"
        "  background: #f59e0b;"
        "  border-color: #fde68a;"
        "}"
        "QPushButton:pressed {"
        "  background: #b45309;"
        "}"
    )
    _BTN_RUNNING = (
        "QPushButton {"
        "  background: #12122a;"
        "  border: 1.5px solid #2c2c50;"
        "  color: #4b4b7a;"
        "  letter-spacing: 1.5px;"
        "}"
    )
    _BTN_STOP_ON = (
        "QPushButton {"
        "  background: #dc2626;"
        "  border: 1.5px solid #f87171;"
        "  color: #ffffff;"
        "}"
        "QPushButton:hover {"
        "  background: #ef4444;"
        "  border-color: #fca5a5;"
        "}"
        "QPushButton:pressed {"
        "  background: #b91c1c;"
        "}"
    )
    _BTN_STOP_OFF = (
        "QPushButton {"
        "  background: #12122a;"
        "  border: 1.5px solid #2c2c50;"
        "  color: #4b4b7a;"
        "}"
    )

    def _update_primary_btn(self) -> None:
        p = self._current_profile()
        if not self._running:
            self._primary_btn.setText("▶  START")
            self._primary_btn.setStyleSheet(self._BTN_START)
            self._primary_btn.setEnabled(True)
        elif p and p.id != self._active_profile_id:
            self._primary_btn.setText(f"⇄  SWAP  →  {p.display_name}")
            self._primary_btn.setStyleSheet(self._BTN_HOTSWAP)
            self._primary_btn.setEnabled(True)
        else:
            self._primary_btn.setText("● RUNNING")
            self._primary_btn.setStyleSheet(self._BTN_RUNNING)
            self._primary_btn.setEnabled(False)

    def _set_stop(self, active: bool) -> None:
        self._stop_btn.setEnabled(active)
        self._stop_btn.setStyleSheet(
            self._BTN_STOP_ON if active else self._BTN_STOP_OFF
        )

    def _refresh_profiles(self) -> None:
        self._profiles = ProfileManager.list_all()
        self._refresh_profile_list_style()
        self._update_primary_btn()

    def _refresh_profile_list_style(self) -> None:
        row = self._profile_list.currentRow()
        self._profile_list.blockSignals(True)
        self._profile_list.clear()
        for p in self._profiles:
            is_active = self._running and p.id == self._active_profile_id
            label     = f"{'▶  ' if is_active else '    '}{p.display_name}  ·  {p.id}"
            item      = QListWidgetItem(label)
            if is_active:
                item.setForeground(QColor("#86efac"))
            self._profile_list.addItem(item)
        if 0 <= row < len(self._profiles):
            self._profile_list.setCurrentRow(row)
        elif self._profiles:
            # Auto-select last-used profile on startup
            last = self._settings.last_profile
            idx  = next((i for i, p in enumerate(self._profiles)
                         if p.id == last), 0)
            self._profile_list.setCurrentRow(idx)
        self._profile_list.blockSignals(False)

    def _refresh_devices(self) -> None:
        self._keyboards = _find_keyboards()
        self._mice      = _find_mice()
        prefs           = set(self._settings.preferred_keyboards)

        self._kb_list.blockSignals(True)
        self._kb_list.clear()

        if not self._keyboards:
            item = QListWidgetItem("⚠  No keyboards found in /dev/input/")
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(QColor("#f87171"))
            self._kb_list.addItem(item)
        else:
            for dev in self._keyboards:
                item = QListWidgetItem(f"⌨  {dev.name}    {dev.path}")
                item.setData(Qt.UserRole, dev)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if dev.path in prefs else Qt.Unchecked)
                self._kb_list.addItem(item)

        if self._mice:
            sep = QListWidgetItem(f"◈  {len(self._mice)} mouse device(s) detected")
        else:
            sep = QListWidgetItem("◈  No mouse detected")
        sep.setFlags(Qt.NoItemFlags)
        sep.setForeground(QColor("#475569" if self._mice else "#334155"))
        self._kb_list.addItem(sep)

        self._kb_list.blockSignals(False)
        self._update_selected_kbs()

    def _update_selected_kbs(self) -> None:
        self._selected_kbs = []
        for i in range(self._kb_list.count()):
            item = self._kb_list.item(i)
            dev  = item.data(Qt.UserRole)
            if dev and item.checkState() == Qt.Checked:
                self._selected_kbs.append(dev)

    def _current_profile(self) -> Optional[Profile]:
        row = self._profile_list.currentRow()
        if 0 <= row < len(self._profiles):
            return self._profiles[row]
        return None

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_profile_selected(self, _row: int) -> None:
        # Update primary button label even while an emulator session is running
        # (enables the hot-swap button when a different profile is selected).
        self._update_primary_btn()

    def _on_kb_check(self, _item: QListWidgetItem) -> None:
        self._update_selected_kbs()

    def _on_new(self) -> None:
        dlg = NewProfileDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            ProfileManager.create(dlg.profile_id, dlg.display_name, dlg.clone_from)
        except (FileExistsError, FileNotFoundError, ValueError) as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._refresh_profiles()
        for i, p in enumerate(self._profiles):
            if p.id == dlg.profile_id:
                self._profile_list.setCurrentRow(i)
                break

    def _on_clone(self) -> None:
        p = self._current_profile()
        if not p:
            return
        dlg = NewProfileDialog(self)
        dlg._clone_edit.setText(p.id)
        dlg._name_edit.setText(f"{p.display_name} (copy)")
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            ProfileManager.create(dlg.profile_id, dlg.display_name, p.id)
        except (FileExistsError, FileNotFoundError, ValueError) as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._refresh_profiles()

    def _on_edit(self) -> None:
        p = self._current_profile()
        if not p:
            return
        if self._running and p.id == self._active_profile_id:
            ans = QMessageBox.question(
                self, "Edit active profile",
                f"'{p.display_name}' is currently running.\n"
                "Changes will take effect on the next Start or Hot-Swap.\n\n"
                "Continue editing?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if ans != QMessageBox.Yes:
                return
        dlg = ProfileEditorDialog(p, self)
        if dlg.exec() == QDialog.Accepted:
            self._refresh_profiles()

    def _on_delete(self) -> None:
        p = self._current_profile()
        if not p:
            return
        # Block deletion of the actively running profile
        if self._running and p.id == self._active_profile_id:
            QMessageBox.warning(
                self, "Cannot delete active profile",
                f"'{p.display_name}' is currently running.\n"
                "Stop the emulator before deleting this profile."
            )
            return
        ans = QMessageBox.question(
            self, "Delete profile",
            f"Permanently delete '{p.display_name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ans != QMessageBox.Yes:
            return
        try:
            ProfileManager.delete(p.id)
        except FileNotFoundError as exc:
            QMessageBox.critical(self, "Error", str(exc))
        self._refresh_profiles()

    # ── Primary action: START or HOT-SWAP ─────────────────────────────────────

    def _on_primary(self) -> None:
        if self._running:
            # Hot-swap: stop current session, restart with the selected profile
            p = self._current_profile()
            if not p or p.id == self._active_profile_id:
                return
            self._hotswap_pending = True
            self._set_swapping_status()
            self._primary_btn.setEnabled(False)
            self._set_stop(False)
            self._on_stop()
        else:
            self._do_start()

    def _do_start(self) -> None:
        p = self._current_profile()
        if not p:
            QMessageBox.warning(self, "No profile selected",
                                "Select a profile before starting.")
            return

        kbs = self._selected_kbs or self._keyboards
        if not kbs:
            QMessageBox.critical(
                self, "No keyboard found",
                "No keyboard was found in /dev/input/.\n\n"
                "Make sure you are in the 'input' group:\n"
                "  sudo usermod -aG input $USER\n"
                "Then re-login or reboot."
            )
            return

        self._running           = True
        self._active_profile_id = p.id
        self._set_stop(True)
        self._set_running_status(p.display_name)
        self._update_tray(True, p.display_name)
        self._refresh_profile_list_style()
        self._update_primary_btn()

        self._settings.last_profile        = p.id
        self._settings.preferred_keyboards = [d.path for d in kbs]
        self._settings.save()

        self._emu_thread = EmulatorThread(p, kbs, self._mice)
        self._emu_thread.started_ok.connect(lambda: None)
        self._emu_thread.error.connect(self._on_emu_error)
        self._emu_thread.stopped.connect(self._on_emu_stopped)
        self._emu_thread.start()

    def _on_stop(self) -> None:
        if self._emu_thread:
            self._emu_thread.stop()

    def _on_emu_error(self, msg: str) -> None:
        self._hotswap_pending = False
        QMessageBox.critical(self, "Emulator error", msg)
        self._set_error_status()

    def _on_emu_stopped(self) -> None:
        # Wait for the thread to finish completely before proceeding.
        # This ensures the uinput slot is fully released by the kernel,
        # preventing Steam from registering multiple ghost gamepads across
        # start/stop cycles.
        thread = self._emu_thread
        self._emu_thread = None

        if thread:
            thread.wait(2000)

        self._running           = False
        self._active_profile_id = None
        self._set_stop(False)
        self._refresh_profile_list_style()

        if self._hotswap_pending:
            self._hotswap_pending = False
            # Give the kernel 300 ms to fully release the uinput node
            # before opening a new one in the next session.
            QTimer.singleShot(300, self._do_start)
        else:
            self._set_stopped_status()
            self._update_tray(False)
            self._update_primary_btn()

    # ── Tray helpers ──────────────────────────────────────────────────────────

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self._show_window()

    def _show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _show_about(self) -> None:
        AboutDialog(self).exec()

    # ── Window close / quit ───────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        if self._tray.isSystemTrayAvailable():
            self.hide()
            event.ignore()
        else:
            self._quit()
            event.accept()

    def _quit(self) -> None:
        if self._running and self._emu_thread:
            self._emu_thread.stop()
            self._emu_thread.wait(3000)
        QApplication.quit()


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    # On Wayland, force Qt to use the XCB (X11) backend so the window
    # is managed by XWayland.  evdev reads raw /dev/input/* regardless,
    # so input capture is unaffected by the display backend.
    if os.environ.get("WAYLAND_DISPLAY") and "QT_QPA_PLATFORM" not in os.environ:
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

    app = QApplication(sys.argv)
    app.setApplicationName("kb2xb")
    app.setApplicationDisplayName("Kb2Xb")
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(_STYLE)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("Warning: no system tray — close button will quit.", file=sys.stderr)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
