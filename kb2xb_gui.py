#!/usr/bin/env python3
"""
kb2xb_gui.py  —  PySide6 front-end for the kb2xb engine.

Place this file alongside kb2xb.py.

Dependencies (Arch / CachyOS):
  sudo pacman -S python-pyside6 python-evdev
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
QWidget {
    background: #0d1117;
    color: #c9d1d9;
    font-size: 13px;
}
QMainWindow, QDialog { background: #0d1117; }

QGroupBox {
    border: 1px solid #30363d;
    border-radius: 6px;
    margin-top: 1.1em;
    padding-top: 10px;
    font-weight: 700;
    color: #58a6ff;
    font-size: 12px;
    letter-spacing: 0.5px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

QListWidget {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    outline: none;
    padding: 4px;
}
QListWidget::item {
    padding: 7px 10px;
    border-radius: 4px;
    margin: 1px 0;
}
QListWidget::item:selected {
    background: #1f6feb;
    color: #ffffff;
}
QListWidget::item:hover:!selected { background: #1c2128; }

QPushButton {
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 5px 14px;
    color: #c9d1d9;
    min-height: 28px;
}
QPushButton:hover   { background: #30363d; border-color: #8b949e; color: #fff; }
QPushButton:pressed { background: #1f6feb; border-color: #1f6feb; color: #fff; }
QPushButton:disabled { color: #484f58; border-color: #21262d; background: #161b22; }

/* ── Primary action: START / HOTSWAP / RUNNING (driven by `mode` property) ── */
QPushButton#btn_primary {
    font-size: 15px;
    font-weight: 700;
    min-height: 52px;
    border-radius: 8px;
    letter-spacing: 1px;
    color: #ffffff;
}
QPushButton#btn_primary[mode="start"] {
    background: #1a7f37;
    border-color: #238636;
}
QPushButton#btn_primary[mode="start"]:hover   { background: #238636; border-color: #3fb950; }
QPushButton#btn_primary[mode="start"]:pressed { background: #196c2e; }

QPushButton#btn_primary[mode="hotswap"] {
    background: #7d4e00;
    border-color: #d29922;
}
QPushButton#btn_primary[mode="hotswap"]:hover   { background: #bb8009; border-color: #e3b341; }
QPushButton#btn_primary[mode="hotswap"]:pressed { background: #5a3700; }

QPushButton#btn_primary[mode="running"] {
    background: #161b22;
    border-color: #21262d;
    color: #484f58;
    letter-spacing: 0.5px;
}

/* ── Stop ── */
QPushButton#btn_stop {
    background: #6e1117;
    border-color: #b62324;
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
    min-height: 52px;
    border-radius: 8px;
    letter-spacing: 1px;
}
QPushButton#btn_stop:hover   { background: #b62324; border-color: #ff7b72; }
QPushButton#btn_stop:pressed { background: #5c0a10; }
QPushButton#btn_stop:disabled { background: #161b22; border-color: #21262d; color: #484f58; }

/* ── Key-capture buttons ── */
QPushButton#btn_capture {
    background: #0d1117;
    border: 1px dashed #30363d;
    border-radius: 4px;
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 12px;
    padding: 3px 10px;
    min-width: 90px;
    color: #79c0ff;
    min-height: 24px;
}
QPushButton#btn_capture:hover { background: #161b22; border-color: #58a6ff; }
QPushButton#btn_capture[capturing="true"] {
    border-style: solid;
    border-color: #f78166;
    color: #f78166;
    background: #160c07;
}

/* ── Small toolbar buttons ── */
QPushButton#btn_sm {
    background: #21262d;
    border: 1px solid #30363d;
    border-radius: 5px;
    padding: 3px 10px;
    min-height: 24px;
    font-size: 12px;
}
QPushButton#btn_sm:hover   { background: #30363d; color: #fff; }
QPushButton#btn_sm:pressed { background: #1f6feb; border-color: #1f6feb; }
QPushButton#btn_sm:disabled { color: #484f58; border-color: #21262d; background: #161b22; }

QLineEdit, QSpinBox {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 4px 8px;
    color: #c9d1d9;
    min-height: 28px;
    selection-background-color: #1f6feb;
}
QLineEdit:focus, QSpinBox:focus { border-color: #58a6ff; }
QSpinBox::up-button, QSpinBox::down-button { width: 18px; }

QSlider::groove:horizontal {
    height: 4px;
    background: #30363d;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 14px; height: 14px;
    margin: -5px 0;
    background: #58a6ff;
    border-radius: 7px;
    border: none;
}
QSlider::sub-page:horizontal { background: #1f6feb; border-radius: 2px; }

QTabWidget::pane {
    border: 1px solid #30363d;
    border-radius: 0 6px 6px 6px;
    background: #161b22;
    top: -1px;
}
QTabBar::tab {
    background: #0d1117;
    border: 1px solid #30363d;
    border-bottom: none;
    padding: 7px 18px;
    color: #8b949e;
    border-radius: 6px 6px 0 0;
    margin-right: 3px;
    font-size: 12px;
}
QTabBar::tab:selected { background: #161b22; color: #c9d1d9; border-bottom: 1px solid #161b22; }
QTabBar::tab:hover:!selected { color: #c9d1d9; background: #1c2128; }

QCheckBox { spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #30363d;
    border-radius: 3px;
    background: #161b22;
}
QCheckBox::indicator:checked { background: #1f6feb; border-color: #1f6feb; }
QCheckBox::indicator:hover   { border-color: #58a6ff; }

QScrollBar:vertical {
    width: 8px; background: transparent; border-radius: 4px; margin: 2px;
}
QScrollBar::handle:vertical {
    background: #30363d; border-radius: 4px; min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #484f58; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { height: 8px; background: transparent; }
QScrollBar::handle:horizontal { background: #30363d; border-radius: 4px; min-width: 24px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QFrame[frameShape="4"], QFrame[frameShape="5"] { color: #21262d; }

QMenu {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item { padding: 6px 20px; border-radius: 4px; }
QMenu::item:selected { background: #1f6feb; color: #fff; }
QMenu::separator { height: 1px; background: #30363d; margin: 4px 8px; }

QDialogButtonBox QPushButton { min-width: 80px; }

QLabel#lbl_dot { font-size: 20px; }

QLabel#lbl_section {
    font-size: 10px;
    font-weight: 700;
    color: #8b949e;
    letter-spacing: 1px;
    padding: 2px 0 4px 2px;
}
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
        self.setText("… press a key …")
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
        self.setWindowTitle(f"Edit profile — {profile.display_name}")
        self.setMinimumWidth(560)
        self.setMinimumHeight(520)

        self._key_btns:       dict[str, KeyCaptureButton] = {}
        self._mouse_widgets:  dict = {}
        self._device_widgets: dict = {}
        self._opt_widgets:    dict = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 12)
        root.setSpacing(10)

        tabs = QTabWidget()
        tabs.addTab(self._make_keymap_tab(),  "Keymap")
        tabs.addTab(self._make_mouse_tab(),   "Mouse")
        tabs.addTab(self._make_device_tab(),  "Device")
        tabs.addTab(self._make_options_tab(), "Options")
        root.addWidget(tabs)

        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._on_save)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _make_keymap_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        inner = QWidget()
        vbox  = QVBoxLayout(inner)
        vbox.setContentsMargins(12, 12, 12, 12)
        vbox.setSpacing(10)

        km = self._profile.keymap

        groups = [
            ("Left Stick", [
                ("↑  Up",    "ls_up"),   ("↓  Down",  "ls_down"),
                ("←  Left",  "ls_left"), ("→  Right", "ls_right"),
            ]),
            ("Right Stick", [
                ("↑  Up",    "rs_up"),   ("↓  Down",  "rs_down"),
                ("←  Left",  "rs_left"), ("→  Right", "rs_right"),
            ]),
            ("D-Pad", [
                ("↑  Up",    "dp_up"),   ("↓  Down",  "dp_down"),
                ("←  Left",  "dp_left"), ("→  Right", "dp_right"),
            ]),
            ("Face Buttons", [
                ("A",  "a_btn"), ("B",  "b_btn"),
                ("X",  "x_btn"), ("Y",  "y_btn"),
            ]),
            ("Bumpers & Triggers", [
                ("LB",  "lb"), ("RB",  "rb"),
                ("LT",  "lt"), ("RT",  "rt"),
            ]),
            ("Stick Clicks & Menu", [
                ("L3",    "l3"),    ("R3",    "r3"),
                ("Start", "start"), ("View",  "view"),
            ]),
        ]

        for group_name, fields in groups:
            gb   = QGroupBox(group_name)
            grid = QGridLayout(gb)
            grid.setSpacing(6)
            for i, (label, fname) in enumerate(fields):
                row, col = divmod(i, 2)
                lbl = QLabel(label)
                btn = KeyCaptureButton(getattr(km, fname))
                btn.key_captured.connect(lambda name, f=fname: self._key_btns[f].set_key(name))
                self._key_btns[fname] = btn
                grid.addWidget(lbl, row, col * 2,     Qt.AlignRight)
                grid.addWidget(btn, row, col * 2 + 1, Qt.AlignLeft)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(3, 1)
            vbox.addWidget(gb)

        vbox.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _make_mouse_tab(self) -> QWidget:
        w    = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(14, 14, 14, 14)
        vbox.setSpacing(14)
        mc   = self._profile.mouse

        for prefix, label in [("ls", "Left Stick"), ("rs", "Right Stick")]:
            gb   = QGroupBox(f"Mouse → {label}")
            form = QFormLayout(gb)
            form.setSpacing(10)
            form.setLabelAlignment(Qt.AlignRight)

            enabled = QCheckBox("Enable mouse-to-stick")
            enabled.setChecked(getattr(mc, f"{prefix}_enabled"))

            key_btn = KeyCaptureButton(getattr(mc, f"{prefix}_key"))
            key_btn.key_captured.connect(lambda name, b=key_btn: b.set_key(name))

            sens_val    = QLabel(str(getattr(mc, f"{prefix}_sensitivity")))
            sens_slider = QSlider(Qt.Horizontal)
            sens_slider.setRange(10, 2000)
            sens_slider.setValue(getattr(mc, f"{prefix}_sensitivity"))
            sens_slider.valueChanged.connect(lambda v, lbl=sens_val: lbl.setText(str(v)))

            sens_row = QWidget()
            sens_h   = QHBoxLayout(sens_row)
            sens_h.setContentsMargins(0, 0, 0, 0)
            sens_h.addWidget(sens_slider, 1)
            sens_h.addWidget(sens_val)
            sens_h.addWidget(QLabel("px"))

            form.addRow("",             enabled)
            form.addRow("Hold key:",    key_btn)
            form.addRow("Sensitivity:", sens_row)

            self._mouse_widgets[f"{prefix}_enabled"]     = enabled
            self._mouse_widgets[f"{prefix}_key"]         = key_btn
            self._mouse_widgets[f"{prefix}_sensitivity"] = sens_slider

            vbox.addWidget(gb)

        vbox.addStretch()
        return w

    def _make_device_tab(self) -> QWidget:
        w    = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)
        dc   = self._profile.device

        name_edit    = QLineEdit(dc.name)
        vendor_spin  = QSpinBox(); vendor_spin.setRange(0, 0xFFFF);  vendor_spin.setValue(dc.vendor)
        product_spin = QSpinBox(); product_spin.setRange(0, 0xFFFF); product_spin.setValue(dc.product)
        version_spin = QSpinBox(); version_spin.setRange(0, 0xFFFF); version_spin.setValue(dc.version)

        form.addRow("Device name:", name_edit)
        form.addRow("Vendor ID:",   vendor_spin)
        form.addRow("Product ID:",  product_spin)
        form.addRow("Version:",     version_spin)
        form.addRow("", QLabel(
            "<small style='color:#8b949e'>"
            "Default mimics Microsoft Xbox One pad (045E:02D1).<br>"
            "Change if a game rejects the default identity."
            "</small>"
        ))

        self._device_widgets = {
            "name": name_edit, "vendor": vendor_spin,
            "product": product_spin, "version": version_spin,
        }
        return w

    def _make_options_tab(self) -> QWidget:
        w    = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)
        p    = self._profile

        display_edit = QLineEdit(p.display_name)

        delay_spin = QSpinBox()
        delay_spin.setRange(0, 5000)
        delay_spin.setSuffix(" ms")
        delay_spin.setValue(p.startup_delay_ms)

        grab_chk = QCheckBox("Grab input devices (exclusive access)")
        grab_chk.setChecked(p.grab)

        form.addRow("Display name:",  display_edit)
        form.addRow("Startup delay:", delay_spin)
        form.addRow("",               grab_chk)
        form.addRow("", QLabel(
            "<small style='color:#8b949e'>"
            "Grab prevents other apps from reading keyboard/mouse while active."
            "</small>"
        ))

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
        self.setWindowTitle("New profile")
        self.setFixedWidth(380)

        form = QFormLayout(self)
        form.setContentsMargins(16, 16, 16, 12)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        self._id_edit    = QLineEdit()
        self._name_edit  = QLineEdit()
        self._clone_edit = QLineEdit()

        self._id_edit.setPlaceholderText("e.g. elden_ring  (a-z, 0-9, _, -)")
        self._name_edit.setPlaceholderText("e.g. Elden Ring")
        self._clone_edit.setPlaceholderText("leave empty for default keymap")

        form.addRow("Profile ID:",    self._id_edit)
        form.addRow("Display name:",  self._name_edit)
        form.addRow("Clone from ID:", self._clone_edit)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

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
        self.setWindowTitle("About Kb2Xb")
        self.setFixedSize(400, 220)

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(28, 24, 28, 20)
        vbox.setSpacing(8)

        title = QLabel("Kb2Xb")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #58a6ff;")
        title.setAlignment(Qt.AlignCenter)

        sub = QLabel(f"v{__version__}  —  Keyboard + Mouse → Xbox One gamepad")
        sub.setStyleSheet("color: #8b949e; font-size: 12px;")
        sub.setAlignment(Qt.AlignCenter)

        desc = QLabel(
            "Maps any keyboard (and optionally a mouse) to a virtual Xbox One "
            "controller via evdev/uinput.  Works on Wayland and X11 with no "
            "configuration inside the game."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #c9d1d9; font-size: 12px; padding-top: 6px;")
        desc.setAlignment(Qt.AlignCenter)

        link = QLabel(
            "<a style='color:#58a6ff' href='https://github.com/janyel-lima/kb2xb'>"
            "github.com/yourname/kb2xb</a>"
        )
        link.setOpenExternalLinks(True)
        link.setAlignment(Qt.AlignCenter)
        link.setStyleSheet("padding-top: 4px;")

        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)

        vbox.addWidget(title)
        vbox.addWidget(sub)
        vbox.addWidget(_h_sep())
        vbox.addWidget(desc)
        vbox.addWidget(link)
        vbox.addStretch()
        vbox.addWidget(bb)


# ─────────────────────────────────────────────────────────────────────────────
#  MainWindow
# ─────────────────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Kb2Xb  v{__version__}")
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
        splitter.setSizes([280, 400])
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter, 1)
        root.addWidget(self._build_bottom_bar())

    def _build_left_panel(self) -> QWidget:
        w    = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(12, 12, 6, 12)
        vbox.setSpacing(6)

        vbox.addWidget(_section("Profiles"))

        self._profile_list = QListWidget()
        self._profile_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._profile_list.currentRowChanged.connect(self._on_profile_selected)
        vbox.addWidget(self._profile_list, 1)

        btns = QHBoxLayout()
        btns.setSpacing(4)
        for label, slot in [("New", self._on_new), ("Clone", self._on_clone),
                             ("Edit", self._on_edit), ("Delete", self._on_delete)]:
            b = QPushButton(label)
            b.setObjectName("btn_sm")
            b.clicked.connect(slot)
            btns.addWidget(b)
        vbox.addLayout(btns)

        return w

    def _build_right_panel(self) -> QWidget:
        w    = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(6, 12, 12, 12)
        vbox.setSpacing(6)

        vbox.addWidget(_section("Input Devices"))

        self._kb_list = QListWidget()
        self._kb_list.setSelectionMode(QAbstractItemView.NoSelection)
        self._kb_list.itemChanged.connect(self._on_kb_check)
        vbox.addWidget(self._kb_list, 1)

        refresh_btn = QPushButton("Refresh devices")
        refresh_btn.setObjectName("btn_sm")
        refresh_btn.clicked.connect(self._refresh_devices)
        vbox.addWidget(refresh_btn)

        vbox.addWidget(_h_sep())

        # ── Status ─────────────────────────────────────────────────────
        status_row = QHBoxLayout()
        self._status_dot = QLabel("●")
        self._status_dot.setObjectName("lbl_dot")
        self._status_dot.setStyleSheet("color: #484f58;")
        self._status_lbl = QLabel("Stopped")
        self._status_lbl.setStyleSheet("color: #8b949e;")
        status_row.addWidget(self._status_dot)
        status_row.addWidget(self._status_lbl, 1)
        vbox.addLayout(status_row)

        return w

    def _build_bottom_bar(self) -> QWidget:
        bar  = QWidget()
        bar.setStyleSheet("background: #161b22; border-top: 1px solid #21262d;")
        hbox = QHBoxLayout(bar)
        hbox.setContentsMargins(12, 10, 12, 10)
        hbox.setSpacing(8)

        self._primary_btn = QPushButton("START")
        self._primary_btn.setObjectName("btn_primary")
        self._primary_btn.setProperty("mode", "start")
        self._primary_btn.clicked.connect(self._on_primary)

        self._stop_btn = QPushButton("STOP")
        self._stop_btn.setObjectName("btn_stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)

        hbox.addWidget(self._primary_btn, 3)
        hbox.addWidget(self._stop_btn,    1)
        return bar

    def _build_tray(self) -> None:
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(_dot_icon("#484f58"))
        self._tray.setToolTip("Kb2Xb — stopped")

        menu = QMenu()
        self._tray_status_action = menu.addAction("Stopped")
        self._tray_status_action.setEnabled(False)
        menu.addSeparator()
        menu.addAction("Show", self._show_window)
        menu.addAction("Stop", self._on_stop)
        menu.addSeparator()
        menu.addAction(f"About  (v{__version__})", self._show_about)
        menu.addAction("Quit", self._quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    # ── Status helpers ────────────────────────────────────────────────────────

    def _set_running_status(self, profile_name: str) -> None:
        self._status_dot.setStyleSheet("color: #3fb950;")
        self._status_lbl.setText(f"Running  ·  {profile_name}")
        self._status_lbl.setStyleSheet("color: #3fb950;")

    def _set_stopped_status(self) -> None:
        self._status_dot.setStyleSheet("color: #484f58;")
        self._status_lbl.setText("Stopped")
        self._status_lbl.setStyleSheet("color: #8b949e;")

    def _set_error_status(self) -> None:
        self._status_dot.setStyleSheet("color: #f85149;")
        self._status_lbl.setText("Error — see dialog")
        self._status_lbl.setStyleSheet("color: #f85149;")
        self._running           = False
        self._active_profile_id = None
        self._stop_btn.setEnabled(False)
        self._refresh_profile_list_style()
        self._update_primary_btn()
        self._update_tray(False)

    def _set_swapping_status(self) -> None:
        self._status_dot.setStyleSheet("color: #d29922;")
        self._status_lbl.setText("Swapping profile…")
        self._status_lbl.setStyleSheet("color: #d29922;")

    def _update_tray(self, running: bool, profile_name: str = "") -> None:
        if running:
            self._tray.setIcon(_dot_icon("#3fb950"))
            self._tray.setToolTip(f"Kb2Xb — {profile_name}")
            self._tray_status_action.setText(f"Running: {profile_name}")
        else:
            self._tray.setIcon(_dot_icon("#484f58"))
            self._tray.setToolTip("Kb2Xb — stopped")
            self._tray_status_action.setText("Stopped")

    def _update_primary_btn(self) -> None:
        p = self._current_profile()
        if not self._running:
            self._primary_btn.setText("START")
            self._primary_btn.setProperty("mode", "start")
            self._primary_btn.setEnabled(True)
        elif p and p.id != self._active_profile_id:
            self._primary_btn.setText(f"HOT-SWAP → {p.display_name}")
            self._primary_btn.setProperty("mode", "hotswap")
            self._primary_btn.setEnabled(True)
        else:
            self._primary_btn.setText("RUNNING")
            self._primary_btn.setProperty("mode", "running")
            self._primary_btn.setEnabled(False)
        _repaint_btn(self._primary_btn)

    # ── Data refresh ──────────────────────────────────────────────────────────

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
            label     = f"{'▶  ' if is_active else '    '}{p.display_name}   [{p.id}]"
            item      = QListWidgetItem(label)
            if is_active:
                item.setForeground(QColor("#3fb950"))
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
            item.setForeground(QColor("#f85149"))
            self._kb_list.addItem(item)
        else:
            for dev in self._keyboards:
                item = QListWidgetItem(f"{dev.name}  ({dev.path})")
                item.setData(Qt.UserRole, dev)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if dev.path in prefs else Qt.Unchecked)
                self._kb_list.addItem(item)

        if self._mice:
            sep = QListWidgetItem(f"🖱  {len(self._mice)} mouse device(s) detected")
        else:
            sep = QListWidgetItem("🖱  No mouse detected")
        sep.setFlags(Qt.NoItemFlags)
        sep.setForeground(QColor("#8b949e" if self._mice else "#484f58"))
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
            self._stop_btn.setEnabled(False)
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
        self._stop_btn.setEnabled(True)
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
        self._stop_btn.setEnabled(False)
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
