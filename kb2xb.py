#!/usr/bin/env python3
"""
kb2xb — Keyboard + Mouse → Xbox One virtual gamepad
         evdev/uinput · Wayland & X11 · profile-based

https://github.com/yourname/kb2xb
"""
from __future__ import annotations

__version__ = "1.0.0"
__author__  = "yourname"
__license__ = "MIT"

# ── Dependency bootstrap ────────────────────────────────────────────────────
# Fast path: if all deps are already importable (system packages from pacman,
# or a venv that's already active), skip venv creation entirely.
# This means `pacman -S python-evdev python-uinput` users get zero overhead.
import importlib.util, os, subprocess, sys
from pathlib import Path

_DEPS = {"uinput": "python-uinput", "evdev": "python-evdev"}
_VENV = Path(__file__).parent / ".kb2xb-venv"


def _bootstrap() -> None:
    # 1. All deps already importable? Nothing to do.
    if all(importlib.util.find_spec(mod) for mod in _DEPS):
        return
    # 2. Already inside our managed venv — install whatever is still missing.
    if sys.prefix == str(_VENV):
        missing = [pip for mod, pip in _DEPS.items()
                   if importlib.util.find_spec(mod) is None]
        if missing:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-q", *missing])
            os.execv(sys.executable, [sys.executable] + sys.argv)
        return
    # 3. Not in venv yet — create it (idempotent) and re-exec into it.
    venv_py = _VENV / "bin" / "python"
    if not venv_py.exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(_VENV)])
    os.execv(str(venv_py), [str(venv_py)] + sys.argv)


_bootstrap()
# ─────────────────────────────────────────────────────────────────────────────

import argparse, curses, json, logging, math, re, signal, threading, time
from dataclasses import asdict, dataclass, field
from threading import Lock
from typing import Optional

import evdev
from evdev import ecodes
import uinput


# ── Paths ───────────────────────────────────────────────────────────────────

_CONFIG_DIR    = Path.home() / ".config" / "kb2xb"
_PROFILES_DIR  = _CONFIG_DIR / "profiles"
_SETTINGS_FILE = _CONFIG_DIR / "settings.json"

_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
_PROFILES_DIR.mkdir(parents=True, exist_ok=True)


# ── Logging ─────────────────────────────────────────────────────────────────

log = logging.getLogger("kb2xb")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    fmt   = "%(levelname)-8s %(name)s  %(message)s" if verbose else "%(levelname)-8s %(message)s"
    logging.basicConfig(level=level, format=fmt)


# ── Key name → evdev code ────────────────────────────────────────────────────

def _build_name_map() -> dict[str, int]:
    """Build the canonical key-name → evdev-code mapping."""
    m: dict[str, int] = {}

    # a-z
    for c in "abcdefghijklmnopqrstuvwxyz":
        m[c] = getattr(ecodes, f"KEY_{c.upper()}")
    # 0-9
    for n in range(10):
        m[str(n)] = getattr(ecodes, f"KEY_{n}")
    # F1-F12
    for n in range(1, 13):
        m[f"f{n}"] = getattr(ecodes, f"KEY_F{n}")

    # ── Navigation & control ─────────────────────────────────────────────
    m.update({
        "space":       ecodes.KEY_SPACE,
        "return":      ecodes.KEY_ENTER,
        "enter":       ecodes.KEY_ENTER,
        "backspace":   ecodes.KEY_BACKSPACE,
        "tab":         ecodes.KEY_TAB,
        "escape":      ecodes.KEY_ESC,
        "esc":         ecodes.KEY_ESC,
        "delete":      ecodes.KEY_DELETE,
        "insert":      ecodes.KEY_INSERT,
        "home":        ecodes.KEY_HOME,
        "end":         ecodes.KEY_END,
        "page_up":     ecodes.KEY_PAGEUP,
        "page_down":   ecodes.KEY_PAGEDOWN,
        "up":          ecodes.KEY_UP,
        "down":        ecodes.KEY_DOWN,
        "left":        ecodes.KEY_LEFT,
        "right":       ecodes.KEY_RIGHT,
        "print_screen":ecodes.KEY_SYSRQ,
        "scroll_lock": ecodes.KEY_SCROLLLOCK,
        "pause":       ecodes.KEY_PAUSE,
        "num_lock":    ecodes.KEY_NUMLOCK,
        "caps_lock":   ecodes.KEY_CAPSLOCK,
        "menu":        ecodes.KEY_COMPOSE,
    })

    # ── Modifiers ────────────────────────────────────────────────────────
    m.update({
        "ctrl_l":  ecodes.KEY_LEFTCTRL,
        "ctrl_r":  ecodes.KEY_RIGHTCTRL,
        "alt_l":   ecodes.KEY_LEFTALT,
        "alt_r":   ecodes.KEY_RIGHTALT,
        "shift_l": ecodes.KEY_LEFTSHIFT,
        "shift_r": ecodes.KEY_RIGHTSHIFT,
        "super_l": ecodes.KEY_LEFTMETA,
        "super_r": ecodes.KEY_RIGHTMETA,
    })

    # ── Punctuation ──────────────────────────────────────────────────────
    m.update({
        "minus":         ecodes.KEY_MINUS,
        "equal":         ecodes.KEY_EQUAL,
        "bracket_left":  ecodes.KEY_LEFTBRACE,
        "bracket_right": ecodes.KEY_RIGHTBRACE,
        "semicolon":     ecodes.KEY_SEMICOLON,
        "apostrophe":    ecodes.KEY_APOSTROPHE,
        "grave":         ecodes.KEY_GRAVE,
        "comma":         ecodes.KEY_COMMA,
        "period":        ecodes.KEY_DOT,
        "slash":         ecodes.KEY_SLASH,
        "backslash":     ecodes.KEY_BACKSLASH,
    })

    # ── Numpad ───────────────────────────────────────────────────────────
    for n in range(10):
        m[f"kp{n}"] = getattr(ecodes, f"KEY_KP{n}")
    m.update({
        "kp_enter":    ecodes.KEY_KPENTER,
        "kp_plus":     ecodes.KEY_KPPLUS,
        "kp_minus":    ecodes.KEY_KPMINUS,
        "kp_multiply": ecodes.KEY_KPASTERISK,
        "kp_divide":   ecodes.KEY_KPSLASH,
        "kp_dot":      ecodes.KEY_KPDOT,
    })

    # ── Media keys ───────────────────────────────────────────────────────
    m.update({
        "mute":        ecodes.KEY_MUTE,
        "volume_up":   ecodes.KEY_VOLUMEUP,
        "volume_down": ecodes.KEY_VOLUMEDOWN,
        "play_pause":  ecodes.KEY_PLAYPAUSE,
        "next_track":  ecodes.KEY_NEXTSONG,
        "prev_track":  ecodes.KEY_PREVIOUSSONG,
        "stop_media":  ecodes.KEY_STOPCD,
    })

    return m


_NAME_TO_CODE: dict[str, int] = _build_name_map()


def _resolve(name: str) -> int:
    code = _NAME_TO_CODE.get(name.lower().strip())
    if code is None:
        raise ValueError(
            f"Unknown key name: {name!r}\n"
            f"Run `kb2xb keys` to list all valid names."
        )
    return code


# ── Axis constants ───────────────────────────────────────────────────────────

STICK_MIN, STICK_CTR, STICK_MAX = -32768, 0, 32767
TRIG_MIN,  TRIG_MAX             =      0, 255
HAT_MIN,   HAT_CTR,  HAT_MAX   =     -1, 0, 1

_UINPUT_EVENTS = (
    uinput.BTN_A, uinput.BTN_B, uinput.BTN_X, uinput.BTN_Y,
    uinput.BTN_TL, uinput.BTN_TR,
    uinput.BTN_THUMBL, uinput.BTN_THUMBR,
    uinput.BTN_START, uinput.BTN_SELECT,
    uinput.ABS_X     + (STICK_MIN, STICK_MAX, 16, 128),
    uinput.ABS_Y     + (STICK_MIN, STICK_MAX, 16, 128),
    uinput.ABS_RX    + (STICK_MIN, STICK_MAX, 16, 128),
    uinput.ABS_RY    + (STICK_MIN, STICK_MAX, 16, 128),
    uinput.ABS_Z     + (TRIG_MIN,  TRIG_MAX,   0,   0),
    uinput.ABS_RZ    + (TRIG_MIN,  TRIG_MAX,   0,   0),
    uinput.ABS_HAT0X + (HAT_MIN,   HAT_MAX,    0,   0),
    uinput.ABS_HAT0Y + (HAT_MIN,   HAT_MAX,    0,   0),
)

_BUTTON_FIELDS: dict[str, object] = {
    "a_btn": uinput.BTN_A,      "b_btn": uinput.BTN_B,
    "x_btn": uinput.BTN_X,      "y_btn": uinput.BTN_Y,
    "lb":    uinput.BTN_TL,     "rb":    uinput.BTN_TR,
    "l3":    uinput.BTN_THUMBL, "r3":    uinput.BTN_THUMBR,
    "start": uinput.BTN_START,  "view":  uinput.BTN_SELECT,
}


# ── Data models ──────────────────────────────────────────────────────────────

@dataclass
class MouseConfig:
    """Per-profile mouse-to-stick settings. Each stick is independently configurable."""
    ls_enabled:     bool = True
    rs_enabled:     bool = False
    ls_key:         str  = "ctrl_l"
    rs_key:         str  = "ctrl_r"
    ls_sensitivity: int  = 200
    rs_sensitivity: int  = 200

    def validate(self) -> None:
        if self.ls_enabled:
            _resolve(self.ls_key)
        if self.rs_enabled:
            _resolve(self.rs_key)
        for attr in ("ls_sensitivity", "rs_sensitivity"):
            sens = getattr(self, attr)
            if not (10 <= sens <= 2000):
                raise ValueError(f"{attr} must be 10–2000, got {sens}")


@dataclass
class KeyMap:
    # Left stick
    ls_up:    str = "w";    ls_down:  str = "s"
    ls_left:  str = "a";    ls_right: str = "d"
    # Right stick
    rs_up:    str = "i";    rs_down:  str = "k"
    rs_left:  str = "j";    rs_right: str = "l"
    # D-pad
    dp_up:    str = "up";   dp_down:  str = "down"
    dp_left:  str = "left"; dp_right: str = "right"
    # Face buttons
    a_btn:    str = "space"; b_btn:   str = "f"
    x_btn:    str = "e";     y_btn:   str = "q"
    # Bumpers / Triggers
    lb:       str = "tab";   rb:      str = "r"
    lt:       str = "z";     rt:      str = "c"
    # Stick clicks
    l3:       str = "g";     r3:      str = "v"
    # Menu buttons
    start:    str = "return"; view:   str = "backspace"

    def validate(self) -> None:
        for fname in self.__dataclass_fields__:
            _resolve(getattr(self, fname))


@dataclass
class DeviceConfig:
    vendor:  int = 0x045E          # Microsoft
    product: int = 0x02D1          # Xbox One pad
    version: int = 0x0110
    name:    str = "Microsoft Xbox One pad"


@dataclass
class Profile:
    id:               str          = "bg3"
    display_name:     str          = "Baldur's Gate 3"
    device:           DeviceConfig = field(default_factory=DeviceConfig)
    keymap:           KeyMap       = field(default_factory=KeyMap)
    mouse:            MouseConfig  = field(default_factory=MouseConfig)
    startup_delay_ms: int          = 600
    grab:             bool         = False

    # ── Serialization ────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "display_name":     self.display_name,
            "device":           asdict(self.device),
            "keymap":           asdict(self.keymap),
            "mouse":            asdict(self.mouse),
            "startup_delay_ms": self.startup_delay_ms,
            "grab":             self.grab,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        try:
            profile = cls(
                id=d.get("id", "unnamed"),
                display_name=d.get("display_name", d.get("id", "Unnamed")),
                device=DeviceConfig(**d.get("device", {})),
                keymap=KeyMap(**d.get("keymap", {})),
                mouse=MouseConfig(**d.get("mouse", {})),
                startup_delay_ms=d.get("startup_delay_ms", 600),
                grab=d.get("grab", False),
            )
        except TypeError as e:
            raise ValueError(f"Invalid profile structure: {e}") from e
        profile.validate()
        return profile

    def validate(self) -> None:
        self.keymap.validate()
        self.mouse.validate()

    def save(self) -> Path:
        path = _PROFILES_DIR / f"{self.id}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path

    @classmethod
    def load(cls, path: Path) -> "Profile":
        return cls.from_dict(json.loads(path.read_text()))

    @classmethod
    def load_by_id(cls, profile_id: str) -> "Profile":
        path = _PROFILES_DIR / f"{profile_id}.json"
        if not path.exists():
            raise FileNotFoundError(
                f"Profile '{profile_id}' not found.\n"
                f"  Available: {', '.join(p.stem for p in sorted(_PROFILES_DIR.glob('*.json'))) or '(none)'}\n"
                f"  Create:    kb2xb profile create {profile_id}"
            )
        return cls.load(path)


# ── Settings ─────────────────────────────────────────────────────────────────

@dataclass
class Settings:
    last_profile:        str       = "bg3"
    preferred_keyboards: list[str] = field(default_factory=list)

    def save(self) -> None:
        _SETTINGS_FILE.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls) -> "Settings":
        if not _SETTINGS_FILE.exists():
            return cls()
        try:
            d = json.loads(_SETTINGS_FILE.read_text())
            return cls(
                last_profile=d.get("last_profile", "bg3"),
                preferred_keyboards=d.get("preferred_keyboards", []),
            )
        except Exception:
            return cls()


# ── Profile manager ──────────────────────────────────────────────────────────

class ProfileManager:
    """CRUD operations for profiles stored in ~/.config/kb2xb/profiles/."""

    @staticmethod
    def list_all() -> list[Profile]:
        profiles: list[Profile] = []
        for path in sorted(_PROFILES_DIR.glob("*.json")):
            try:
                profiles.append(Profile.load(path))
            except Exception as e:
                log.warning("Skipping malformed profile %s: %s", path.name, e)
        return profiles

    @staticmethod
    def exists(profile_id: str) -> bool:
        return (_PROFILES_DIR / f"{profile_id}.json").exists()

    @staticmethod
    def ensure_defaults() -> None:
        """Seed the BG3 default profile when no profiles exist yet."""
        if not any(_PROFILES_DIR.glob("*.json")):
            p = Profile()
            p.save()
            print(f"[kb2xb] Created default profile: '{p.display_name}'")

    @staticmethod
    def delete(profile_id: str) -> None:
        path = _PROFILES_DIR / f"{profile_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Profile '{profile_id}' not found.")
        path.unlink()

    @staticmethod
    def create(profile_id: str, display_name: str,
               clone_from: Optional[str] = None) -> Profile:
        if not re.match(r'^[a-z0-9][a-z0-9_-]*$', profile_id):
            raise ValueError(
                "Profile ID must start with a letter/digit "
                "and use only [a-z0-9_-]."
            )
        if ProfileManager.exists(profile_id):
            raise FileExistsError(f"Profile '{profile_id}' already exists.")
        base = Profile.load_by_id(clone_from) if clone_from else Profile()
        base.id           = profile_id
        base.display_name = display_name
        base.save()
        return base

    @staticmethod
    def open_in_editor(profile_id: str) -> None:
        path = _PROFILES_DIR / f"{profile_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Profile '{profile_id}' not found.")
        editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "nano"))
        os.execvp(editor, [editor, str(path)])


# ── TUI utilities ─────────────────────────────────────────────────────────────

_C_TITLE  = 1
_C_SELECT = 2
_C_DIM    = 3


def _init_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(_C_TITLE,  curses.COLOR_CYAN,  -1)
    curses.init_pair(_C_SELECT, curses.COLOR_BLACK,  curses.COLOR_CYAN)
    curses.init_pair(_C_DIM,    curses.COLOR_WHITE, -1)


def _tui_pick(
    title:    str,
    options:  list[str],
    *,
    default:  int  = 0,
    multi:    bool = False,
    subtitle: str  = "",
) -> int | list[int]:
    """
    Arrow-key curses menu.
    - Single mode → selected index, or -1 on cancel.
    - Multi  mode → list of selected indices (empty = cancel / use all).
    """
    toggled: set[int] = set()

    def draw(scr: curses.window, cursor: int) -> None:
        scr.erase()
        h, w = scr.getmaxyx()

        scr.attron(curses.color_pair(_C_TITLE) | curses.A_BOLD)
        scr.addstr(0, 2, f" {title} "[:w - 2])
        scr.attroff(curses.color_pair(_C_TITLE) | curses.A_BOLD)

        if subtitle:
            scr.attron(curses.color_pair(_C_DIM))
            scr.addstr(1, 2, subtitle[:w - 2])
            scr.attroff(curses.color_pair(_C_DIM))

        y0 = 3 if subtitle else 2
        for i, opt in enumerate(options):
            y = y0 + i
            if y >= h - 2:
                break
            prefix = f"  {'◉' if i in toggled else '○'}  " if multi else "   "
            text   = (prefix + opt)[:w - 4]
            if i == cursor:
                scr.attron(curses.color_pair(_C_SELECT))
                scr.addstr(y, 2, text.ljust(w - 4))
                scr.attroff(curses.color_pair(_C_SELECT))
            else:
                scr.addstr(y, 2, text)

        hint = ("Space=toggle  Enter=confirm  q=cancel"
                if multi else "↑/↓/j/k=navigate  Enter=select  q=cancel")
        scr.attron(curses.color_pair(_C_DIM))
        scr.addstr(h - 1, 2, hint[:w - 2])
        scr.attroff(curses.color_pair(_C_DIM))
        scr.refresh()

    def run(scr: curses.window) -> int | list[int]:
        nonlocal toggled
        curses.curs_set(0)
        _init_colors()
        cursor = max(0, min(default, len(options) - 1))

        while True:
            draw(scr, cursor)
            key = scr.getch()

            if key in (curses.KEY_UP, ord('k')) and cursor > 0:
                cursor -= 1
            elif key in (curses.KEY_DOWN, ord('j')) and cursor < len(options) - 1:
                cursor += 1
            elif key == ord(' ') and multi:
                toggled = toggled ^ {cursor}
            elif key in (curses.KEY_ENTER, ord('\n'), ord('\r')):
                return list(toggled) if multi else cursor
            elif key in (ord('q'), 27):  # q or ESC
                return [] if multi else -1

    return curses.wrapper(run)


def _confirm(question: str) -> bool:
    try:
        return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


# ── Device discovery ──────────────────────────────────────────────────────────

# Minimum key set every real keyboard must expose
_KB_SIGNATURE = frozenset({
    ecodes.KEY_A, ecodes.KEY_Z, ecodes.KEY_1,
    ecodes.KEY_SPACE, ecodes.KEY_ENTER, ecodes.KEY_LEFTSHIFT,
})


def _find_keyboards() -> list[evdev.InputDevice]:
    result: list[evdev.InputDevice] = []
    for dev_path in evdev.list_devices():
        try:
            dev  = evdev.InputDevice(dev_path)
            caps = dev.capabilities()
            keys = set(caps.get(ecodes.EV_KEY, []))
            # Require a keyboard-sized key set; exclude mice (EV_REL)
            # and gamepads/touchscreens (EV_ABS).
            if (
                _KB_SIGNATURE.issubset(keys)
                and ecodes.EV_REL not in caps
                and ecodes.EV_ABS not in caps
            ):
                result.append(dev)
        except Exception:
            pass
    return result


def _find_mice() -> list[evdev.InputDevice]:
    result: list[evdev.InputDevice] = []
    for path in evdev.list_devices():
        try:
            dev  = evdev.InputDevice(path)
            caps = dev.capabilities()
            # Must have relative axes (REL_X, REL_Y) and no keyboard keys
            rel = set(caps.get(ecodes.EV_REL, []))
            if ecodes.REL_X in rel and ecodes.REL_Y in rel:
                result.append(dev)
        except Exception:
            pass
    return result


def _select_profile(profiles: list[Profile], last_id: str) -> Optional[Profile]:
    options = [f"{p.display_name}  [{p.id}]" for p in profiles]
    default = next((i for i, p in enumerate(profiles) if p.id == last_id), 0)
    idx     = _tui_pick("Select profile", options, default=default,
                        subtitle="Last used profile is pre-selected")
    return profiles[idx] if idx >= 0 else None


def _select_keyboards(kbs: list[evdev.InputDevice],
                      prefs: list[str]) -> list[evdev.InputDevice]:
    options = [f"{d.name}  ({d.path})" for d in kbs]
    indices = _tui_pick(
        "Select keyboards", options, multi=True,
        subtitle="Space=toggle  Enter=confirm with selection  (empty = use all)",
    )
    selected = [kbs[i] for i in (indices if indices else range(len(kbs)))]
    return selected


# ── Emulator core ─────────────────────────────────────────────────────────────

class XboxEmulator:
    """
    Translates raw evdev events from keyboards and mice into uinput events
    on a virtual Xbox One gamepad.
    """

    def __init__(self, profile: Profile) -> None:
        self._profile = profile
        self._lock    = Lock()
        self._stop    = threading.Event()
        self._device: Optional[uinput.Device] = None

        km = profile.keymap
        mc = profile.mouse

        # Resolve mouse modifier codes (may raise ValueError early)
        self._ls_mode_code: int = _resolve(mc.ls_key) if mc.ls_enabled else -1
        self._rs_mode_code: int = _resolve(mc.rs_key) if mc.rs_enabled else -1
        self._mc = mc

        # Mouse state
        self._mouse_x = self._mouse_y = 0
        self._ls_active = self._rs_active = False
        self._ls_anchor_x = self._ls_anchor_y = 0
        self._rs_anchor_x = self._rs_anchor_y = 0

        # ── Axis pairs ─────────────────────────────────────────────────
        # Each pair: ((pos_code, neg_code), (uinput_axis_x, uinput_axis_y))
        self._ls_pair = (
            (_resolve(km.ls_right), _resolve(km.ls_left)),
            (uinput.ABS_X, uinput.ABS_Y),
            (_resolve(km.ls_up),   _resolve(km.ls_down)),
        )
        self._rs_pair = (
            (_resolve(km.rs_right), _resolve(km.rs_left)),
            (uinput.ABS_RX, uinput.ABS_RY),
            (_resolve(km.rs_up),   _resolve(km.rs_down)),
        )
        dp_pair = (
            (_resolve(km.dp_right), _resolve(km.dp_left)),
            (uinput.ABS_HAT0X, uinput.ABS_HAT0Y),
            (_resolve(km.dp_up),   _resolve(km.dp_down)),
        )

        self._axis_pairs = [self._ls_pair, self._rs_pair, dp_pair]

        # Triggers: key → (uinput axis, max value)
        self._trigger_map: dict[int, tuple] = {
            _resolve(km.lt): (uinput.ABS_Z,  TRIG_MAX),
            _resolve(km.rt): (uinput.ABS_RZ, TRIG_MAX),
        }

        # Buttons: key → uinput button
        self._button_map: dict[int, object] = {
            _resolve(getattr(km, fname)): btn
            for fname, btn in _BUTTON_FIELDS.items()
        }

        # Build reverse maps for quick lookup
        self._axis_codes:    set[int] = set()
        self._code_to_pairs: dict[int, list] = {}
        for pair in self._axis_pairs:
            (pos, neg), _, (up, down) = pair
            for code in (pos, neg, up, down):
                self._axis_codes.add(code)
                self._code_to_pairs.setdefault(code, []).append(pair)

        self._trigger_codes = set(self._trigger_map)
        self._button_codes  = set(self._button_map)
        self._all_codes     = (self._axis_codes
                               | self._trigger_codes
                               | self._button_codes)
        self._held: set[int] = set()

    # ── Device factory ────────────────────────────────────────────────────────

    def _make_device(self) -> uinput.Device:
        dc = self._profile.device
        return uinput.Device(
            _UINPUT_EVENTS,
            vendor=dc.vendor,
            product=dc.product,
            version=dc.version,
            name=dc.name,
        )

    # ── Axis helpers ──────────────────────────────────────────────────────────

    def _emit_pair(self, pair: tuple) -> None:
        """Emit both axes of a stick/dpad pair based on currently held keys."""
        (pos_x, neg_x), (ax_x, ax_y), (pos_y, neg_y) = pair
        val_x  = (STICK_MAX if pos_x in self._held else
                  STICK_MIN if neg_x in self._held else STICK_CTR)
        val_y  = (STICK_MIN if pos_y in self._held else
                  STICK_MAX if neg_y in self._held else STICK_CTR)
        # HAT axes use ±1 range; stick axes use ±32767 range
        if ax_x in (uinput.ABS_HAT0X, uinput.ABS_HAT0Y):
            val_x = HAT_MAX if val_x > 0 else (HAT_MIN if val_x < 0 else 0)
            val_y = HAT_MAX if val_y > 0 else (HAT_MIN if val_y < 0 else 0)
        self._device.emit(ax_x, val_x, syn=False)
        self._device.emit(ax_y, val_y, syn=True)

    @staticmethod
    def _offset_to_stick(dx: int, dy: int, sensitivity: int) -> tuple[int, int]:
        length = math.hypot(dx, dy)
        if length == 0:
            return STICK_CTR, STICK_CTR
        scale  = min(length, sensitivity) / sensitivity
        nx, ny = dx / length * scale, dy / length * scale
        # Y axis: mouse-up = stick-up = negative ABS_Y
        return int(nx * STICK_MAX), int(ny * STICK_MAX)

    def _emit_mouse_ls(self) -> None:
        sx, sy = self._offset_to_stick(
            self._mouse_x - self._ls_anchor_x,
            self._mouse_y - self._ls_anchor_y,
            self._mc.ls_sensitivity,
        )
        self._device.emit(uinput.ABS_X, sx, syn=False)
        self._device.emit(uinput.ABS_Y, sy, syn=True)

    def _emit_mouse_rs(self) -> None:
        sx, sy = self._offset_to_stick(
            self._mouse_x - self._rs_anchor_x,
            self._mouse_y - self._rs_anchor_y,
            self._mc.rs_sensitivity,
        )
        self._device.emit(uinput.ABS_RX, sx, syn=False)
        self._device.emit(uinput.ABS_RY, sy, syn=True)

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_key(self, code: int, value: int) -> None:
        if value == 2:      # key-repeat → ignore
            return
        pressed = value == 1

        # ── Mouse LS mode ─────────────────────────────────────────────
        if self._mc.ls_enabled and code == self._ls_mode_code:
            with self._lock:
                if pressed and not self._ls_active:
                    self._ls_active   = True
                    self._ls_anchor_x = self._mouse_x
                    self._ls_anchor_y = self._mouse_y
                    if self._device:
                        self._device.emit(uinput.ABS_X, STICK_CTR, syn=False)
                        self._device.emit(uinput.ABS_Y, STICK_CTR, syn=True)
                elif not pressed and self._ls_active:
                    self._ls_active = False
                    if self._device:
                        self._emit_pair(self._ls_pair)
            return

        # ── Mouse RS mode ─────────────────────────────────────────────
        if self._mc.rs_enabled and code == self._rs_mode_code:
            with self._lock:
                if pressed and not self._rs_active:
                    self._rs_active   = True
                    self._rs_anchor_x = self._mouse_x
                    self._rs_anchor_y = self._mouse_y
                    if self._device:
                        self._device.emit(uinput.ABS_RX, STICK_CTR, syn=False)
                        self._device.emit(uinput.ABS_RY, STICK_CTR, syn=True)
                elif not pressed and self._rs_active:
                    self._rs_active = False
                    if self._device:
                        self._emit_pair(self._rs_pair)
            return

        if code not in self._all_codes:
            return

        with self._lock:
            if pressed:
                if code in self._held:
                    return
                self._held.add(code)
            else:
                self._held.discard(code)

            if not self._device:
                return

            if code in self._axis_codes:
                for pair in self._code_to_pairs[code]:
                    if pair is self._ls_pair and self._ls_active:
                        continue
                    if pair is self._rs_pair and self._rs_active:
                        continue
                    self._emit_pair(pair)
            elif code in self._trigger_codes:
                axis, val = self._trigger_map[code]
                self._device.emit(axis, val if pressed else TRIG_MIN)
            elif code in self._button_codes:
                self._device.emit(self._button_map[code], int(pressed))

    def _on_mouse_rel(self, dx: int, dy: int) -> None:
        with self._lock:
            self._mouse_x += dx
            self._mouse_y += dy
            if not self._device:
                return
            if self._ls_active:
                self._emit_mouse_ls()
            if self._rs_active:
                self._emit_mouse_rs()

    # ── Reader threads ────────────────────────────────────────────────────────

    def _kb_reader(self, dev: evdev.InputDevice) -> None:
        log.debug("Keyboard reader started: %s", dev.path)
        try:
            for evt in dev.read_loop():
                if self._stop.is_set():
                    break
                if evt.type == ecodes.EV_KEY:
                    self._on_key(evt.code, evt.value)
        except OSError:
            log.warning("Keyboard disconnected: %s  (%s)", dev.name, dev.path)

    def _mouse_reader(self, dev: evdev.InputDevice) -> None:
        log.debug("Mouse reader started: %s", dev.path)
        rel_x = rel_y = 0
        try:
            for evt in dev.read_loop():
                if self._stop.is_set():
                    break
                if evt.type == ecodes.EV_REL:
                    if   evt.code == ecodes.REL_X: rel_x += evt.value
                    elif evt.code == ecodes.REL_Y: rel_y += evt.value
                elif evt.type == ecodes.EV_SYN and (rel_x or rel_y):
                    self._on_mouse_rel(rel_x, rel_y)
                    rel_x = rel_y = 0
        except OSError:
            log.warning("Mouse disconnected: %s  (%s)", dev.name, dev.path)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(
        self,
        keyboards: list[evdev.InputDevice],
        mice:      list[evdev.InputDevice],
    ) -> None:
        if self._profile.grab:
            for dev in keyboards + mice:
                try:
                    dev.grab()
                except Exception as e:
                    log.warning("Could not grab %s: %s", dev.name, e)

        self._device = self._make_device()

        delay_s = self._profile.startup_delay_ms / 1000
        if delay_s > 0:
            time.sleep(delay_s)

        _print_banner(self._profile)

        threads = [
            *(threading.Thread(target=self._kb_reader,    args=(kb,), daemon=True)
              for kb in keyboards),
            *(threading.Thread(target=self._mouse_reader, args=(ms,), daemon=True)
              for ms in mice),
        ]
        for t in threads:
            t.start()

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._handle_signal)

        print("Running — press Ctrl+C to quit.\n")
        self._stop.wait()

    def _release_all(self) -> None:
        if not self._device:
            return
        for btn in self._button_map.values():
            self._device.emit(btn, 0)
        for ax, val in (
            (uinput.ABS_X,     STICK_CTR),
            (uinput.ABS_Y,     STICK_CTR),
            (uinput.ABS_RX,    STICK_CTR),
            (uinput.ABS_RY,    STICK_CTR),
            (uinput.ABS_Z,     TRIG_MIN),
            (uinput.ABS_RZ,    TRIG_MIN),
            (uinput.ABS_HAT0X, HAT_CTR),
        ):
            self._device.emit(ax, val, syn=False)
        self._device.emit(uinput.ABS_HAT0Y, HAT_CTR, syn=True)

    def stop(self) -> None:
        self._stop.set()
        self._release_all()

    def _handle_signal(self, _signum: int, _frame) -> None:
        print("\nStopping…")
        self.stop()
        sys.exit(0)


# ── Banner ────────────────────────────────────────────────────────────────────

def _print_banner(profile: Profile) -> None:
    km, mc = profile.keymap, profile.mouse
    W = 52  # inner content width between ║ chars

    def divider() -> str:
        return f"  ╠{'═'*W}╣"

    def center(text: str) -> str:
        return f"  ║{text:^{W}}║"

    def row(label: str, key: str) -> str:
        val = repr(key)
        return f"  ║  {val:>16}  →  {label:<{W - 23}}  ║"

    def mouse_row(label: str, key: str, sens: int) -> list[str]:
        return [row(label, key),
                f"  ║  {'sensitivity':>16}       {sens}px{'':<{W - 27}}  ║"]

    lines: list[str] = [
        "",
        f"  ╔{'═'*W}╗",
        center(f"  kb2xb  v{__version__}"),
        center(f"  {profile.display_name}"),
        divider(),
        row("L-Stick  ↑/↓/←/→",
            f"{km.ls_up}/{km.ls_down}/{km.ls_left}/{km.ls_right}"),
    ]
    if mc.ls_enabled:
        lines += mouse_row("L-Stick  mouse mode", mc.ls_key, mc.ls_sensitivity)

    lines += [
        divider(),
        row("R-Stick  ↑/↓/←/→",
            f"{km.rs_up}/{km.rs_down}/{km.rs_left}/{km.rs_right}"),
    ]
    if mc.rs_enabled:
        lines += mouse_row("R-Stick  mouse mode", mc.rs_key, mc.rs_sensitivity)

    lines += [
        divider(),
        row("D-Pad  ↑/↓/←/→",
            f"{km.dp_up}/{km.dp_down}/{km.dp_left}/{km.dp_right}"),
        divider(),
        row("A",     km.a_btn),  row("B",    km.b_btn),
        row("X",     km.x_btn),  row("Y",    km.y_btn),
        row("LB",    km.lb),     row("RB",   km.rb),
        row("LT",    km.lt),     row("RT",   km.rt),
        row("L3",    km.l3),     row("R3",   km.r3),
        row("Start", km.start),  row("View", km.view),
        f"  ╚{'═'*W}╝",
        "",
    ]
    print("\n".join(lines))


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_run(args: argparse.Namespace) -> None:
    ProfileManager.ensure_defaults()
    settings = Settings.load()

    # ── Profile selection ─────────────────────────────────────────────
    if args.profile:
        try:
            profile = Profile.load_by_id(args.profile)
        except FileNotFoundError as e:
            sys.exit(str(e))
    else:
        profiles = ProfileManager.list_all()
        if not profiles:
            sys.exit("No profiles found.  Run: kb2xb profile create <id>")
        profile = _select_profile(profiles, settings.last_profile)
        if profile is None:
            sys.exit(0)

    # ── Keyboard selection ────────────────────────────────────────────
    all_kbs = _find_keyboards()
    if not all_kbs:
        sys.exit(
            "No keyboard found in /dev/input/.\n"
            "  Fix: sudo usermod -aG input $USER  (re-login required)\n"
            "  Or:  sudo kb2xb"
        )

    if args.keyboard:
        keyboards = [d for d in all_kbs if d.path == args.keyboard]
        if not keyboards:
            sys.exit(f"Device '{args.keyboard}' not found or is not a keyboard.\n"
                     f"  Available: {', '.join(d.path for d in all_kbs)}")
    else:
        keyboards = _select_keyboards(all_kbs, settings.preferred_keyboards)

    # ── Mouse detection ───────────────────────────────────────────────
    mice = _find_mice()
    mouse_wanted = profile.mouse.ls_enabled or profile.mouse.rs_enabled
    if not mice and mouse_wanted:
        log.warning("No mouse found — mouse-to-stick modes disabled.")

    # Persist selections for next launch
    settings.last_profile        = profile.id
    settings.preferred_keyboards = [d.path for d in keyboards]
    settings.save()

    print(f"\n  Profile  : {profile.display_name}")
    print(f"  Keyboards: {', '.join(d.name for d in keyboards)}")
    print(f"  Mice     : {', '.join(d.name for d in mice) or 'none'}\n")

    XboxEmulator(profile).start(keyboards, mice)


def cmd_profile_list(_args: argparse.Namespace) -> None:
    ProfileManager.ensure_defaults()
    profiles = ProfileManager.list_all()
    settings = Settings.load()

    if not profiles:
        print("No profiles.  Create one: kb2xb profile create <id>")
        return

    col = {"id": 20, "name": 32, "ls": 16, "rs": 16}
    header = (f"{'ID':<{col['id']}}  {'Display name':<{col['name']}}"
              f"  {'Mouse LS':<{col['ls']}}  {'Mouse RS'}")
    print(f"\n{header}")
    print("─" * (sum(col.values()) + 8))
    for p in profiles:
        ls = (f"✓ {p.mouse.ls_key} ({p.mouse.ls_sensitivity}px)"
              if p.mouse.ls_enabled else "—")
        rs = (f"✓ {p.mouse.rs_key} ({p.mouse.rs_sensitivity}px)"
              if p.mouse.rs_enabled else "—")
        mark = "  ← last used" if p.id == settings.last_profile else ""
        print(f"{p.id:<{col['id']}}  {p.display_name:<{col['name']}}"
              f"  {ls:<{col['ls']}}  {rs}{mark}")
    print()


def cmd_profile_create(args: argparse.Namespace) -> None:
    pid = args.name
    try:
        display = input(f"Display name [{pid}]: ").strip() or pid
        profile = ProfileManager.create(pid, display, clone_from=args.clone)
        path    = profile.save()
        print(f"\nCreated: {path}")
        print(f"  Edit keymap : kb2xb profile edit {pid}")
        print(f"  Run now     : kb2xb --profile {pid}\n")
    except (FileExistsError, FileNotFoundError, ValueError) as e:
        sys.exit(str(e))


def cmd_profile_edit(args: argparse.Namespace) -> None:
    ProfileManager.ensure_defaults()
    try:
        ProfileManager.open_in_editor(args.name)  # os.execvp → no return
    except FileNotFoundError as e:
        sys.exit(str(e))


def cmd_profile_show(args: argparse.Namespace) -> None:
    try:
        print(json.dumps(Profile.load_by_id(args.name).to_dict(), indent=2))
    except FileNotFoundError as e:
        sys.exit(str(e))


def cmd_profile_delete(args: argparse.Namespace) -> None:
    try:
        if _confirm(f"Permanently delete profile '{args.name}'?"):
            ProfileManager.delete(args.name)
            print(f"Deleted '{args.name}'.")
    except FileNotFoundError as e:
        sys.exit(str(e))


def cmd_keys(_args: argparse.Namespace) -> None:
    keys  = sorted(_NAME_TO_CODE)
    cols  = 5
    width = 16
    print(f"\nValid key names  ({len(keys)} total):\n")
    for i in range(0, len(keys), cols):
        print("  " + "".join(f"{k:<{width}}" for k in keys[i:i + cols]))
    print()


def cmd_version(_args: argparse.Namespace) -> None:
    print(f"kb2xb {__version__}")


# ── Argument parser ───────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="kb2xb",
        description="Keyboard + Mouse → Xbox One virtual pad  (evdev/uinput)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Quick start:
  kb2xb                              # interactive profile + keyboard selector
  kb2xb --profile bg3                # skip selectors
  kb2xb --profile bg3 -k /dev/input/event3

Profile management:
  kb2xb profile list
  kb2xb profile create elden_ring
  kb2xb profile create elden_ring --clone bg3
  kb2xb profile edit   elden_ring   # opens in $EDITOR
  kb2xb profile show   elden_ring
  kb2xb profile delete elden_ring

Utilities:
  kb2xb keys                         # list all valid key names
  kb2xb version                      # print version
  kb2xb --verbose --profile bg3      # debug output
""",
    )
    root.add_argument("--profile",  "-p", metavar="ID",
                      help="Profile ID to load (skips interactive selector)")
    root.add_argument("--keyboard", "-k", metavar="PATH",
                      help="Force a specific keyboard device path")
    root.add_argument("--verbose",  "-v", action="store_true",
                      help="Enable debug logging")
    root.add_argument("--version",  "-V", action="version",
                      version=f"kb2xb {__version__}")

    sub = root.add_subparsers(dest="command")

    # ── profile ───────────────────────────────────────────────────────
    pr     = sub.add_parser("profile", help="Manage game profiles")
    pr_sub = pr.add_subparsers(dest="profile_cmd")

    pr_sub.add_parser("list", help="List all profiles")

    pc = pr_sub.add_parser("create", help="Create a new profile")
    pc.add_argument("name",    help="Profile ID (e.g. elden_ring)")
    pc.add_argument("--clone", metavar="ID",
                    help="Clone keybindings from an existing profile")

    pe = pr_sub.add_parser("edit",   help="Open profile JSON in $EDITOR")
    pe.add_argument("name", help="Profile ID")

    ps = pr_sub.add_parser("show",   help="Print profile JSON to stdout")
    ps.add_argument("name", help="Profile ID")

    pd = pr_sub.add_parser("delete", help="Permanently delete a profile")
    pd.add_argument("name", help="Profile ID")

    # ── utilities ─────────────────────────────────────────────────────
    sub.add_parser("keys",    help="List all valid key names")
    sub.add_parser("version", help="Print version and exit")

    return root


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    _setup_logging(getattr(args, "verbose", False))

    match args.command:
        case "profile":
            match getattr(args, "profile_cmd", None):
                case "list":   cmd_profile_list(args)
                case "create": cmd_profile_create(args)
                case "edit":   cmd_profile_edit(args)
                case "show":   cmd_profile_show(args)
                case "delete": cmd_profile_delete(args)
                case _:        parser.parse_args(["profile", "--help"])
        case "keys":
            cmd_keys(args)
        case "version":
            cmd_version(args)
        case _:
            cmd_run(args)


if __name__ == "__main__":
    main()
