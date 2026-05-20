# Kb2Xb

**Keyboard + Mouse → Xbox One virtual gamepad** — evdev/uinput · Wayland & X11 · profile-based

Maps any keyboard (and optionally a mouse) to a virtual Xbox One controller that any game or emulator sees as a real gamepad — no configuration inside the game required.

---

## Features

- **Profile-based** — keep separate keymaps per game, switch in seconds
- **Mouse → analog stick** — hold a modifier key to steer any analog axis with your mouse
- **GUI** — PySide6 app with system tray, live key capture, profile editor
- **CLI** — headless, scriptable, terminal-friendly
- **Zero root at runtime** — one-time udev/group setup, then runs as a normal user
- **Wayland & X11** — reads raw evdev events, no display server involvement
- **Shell completions** — bash, zsh, and fish

---

## Requirements

| Package         | Source | Purpose                    |
| --------------- | ------ | -------------------------- |
| `python` ≥ 3.10 | pacman | Runtime                    |
| `python-evdev`  | pacman | Read keyboard/mouse events |
| `python-uinput` | AUR    | Create virtual gamepad     |
| `pyside6`       | pacman | GUI only                   |

---

## Installation

### AUR (Arch / CachyOS — recommended)

```bash
yay -S kb2xb
# or
paru -S kb2xb
```

After install, add your user to the required groups and re-login:

```bash
sudo groupadd -f uinput
sudo usermod -aG input,uinput $USER
# Re-login or reboot required
```

> **Note:** if you previously installed `python-uinput` via pip, remove it first or
> pacman will refuse to install the AUR package due to conflicting files:
>
> ```bash
> sudo rm -rf \
>   /usr/lib/python3*/site-packages/uinput \
>   /usr/lib/python3*/site-packages/_libsuinput*.so \
>   /usr/lib/python3*/site-packages/python_uinput-*.dist-info
> ```

---

### One-command install from source (Arch / CachyOS)

```bash
git clone https://github.com/janyel-lima/kb2xb
cd kb2xb
chmod +x install.sh
./install.sh
```

The script:

1. Installs `python-evdev` and `pyside6` via pacman
2. Installs `python-uinput` via your AUR helper (yay or paru)
3. Loads the `uinput` kernel module and makes it persistent
4. Writes a udev rule so `/dev/uinput` is accessible to the `uinput` group
5. Adds your user to the `input` and `uinput` groups
6. Copies files to `~/.local/share/kb2xb/`
7. Creates `~/.local/share/applications/kb2xb.desktop` (KDE launcher, shown as **Kb2Xb**)
8. Creates `kb2xb` and `kb2xb-gui` commands in `~/.local/bin/`

**After install, re-login (or reboot) to activate group membership.**

---

### Manual installation

#### 1 — System packages

```bash
sudo pacman -S python-evdev pyside6

# python-uinput is AUR-only
yay -S python-uinput
# or: paru -S python-uinput
```

#### 2 — uinput module

```bash
# Load now
sudo modprobe uinput

# Load on every boot
echo 'uinput' | sudo tee /etc/modules-load.d/uinput.conf
```

#### 3 — udev rule (access without sudo)

```bash
echo 'KERNEL=="uinput", GROUP="uinput", MODE="0660"' \
  | sudo tee /etc/udev/rules.d/99-uinput.rules

sudo udevadm control --reload-rules
sudo udevadm trigger
```

#### 4 — User groups

```bash
sudo groupadd -f uinput
sudo usermod -aG input,uinput "$USER"
# Re-login required
```

#### 5 — Copy files

```bash
mkdir -p ~/.local/share/kb2xb
cp kb2xb.py kb2xb_gui.py ~/.local/share/kb2xb/

# Icon (optional)
# Source file is icon.svg; installed as kb2xb.svg so the desktop entry resolves it correctly
mkdir -p ~/.local/share/icons/hicolor/scalable/apps
cp icon.svg ~/.local/share/icons/hicolor/scalable/apps/kb2xb.svg
touch ~/.local/share/icons/hicolor
gtk-update-icon-cache --force --ignore-theme-index ~/.local/share/icons/hicolor/
kbuildsycoca6 --noincremental   # KDE Plasma: rebuild app/icon cache
```

#### 6 — Desktop entry (optional)

```bash
cat > ~/.local/share/applications/kb2xb.desktop << 'EOF'
[Desktop Entry]
Version=1.1
Name=Kb2Xb
GenericName=Keyboard to Xbox Controller
Comment=Map keyboard and mouse to a virtual Xbox One gamepad
Exec=kb2xb-gui
Icon=kb2xb
Terminal=false
Type=Application
Categories=Game;Utility;
Keywords=gamepad;controller;keyboard;mouse;xbox;uinput;evdev;emulator;
StartupNotify=true
StartupWMClass=kb2xb
EOF

update-desktop-database ~/.local/share/applications/
kbuildsycoca6 --noincremental   # KDE Plasma: makes the entry appear immediately
```

---

## Running

### GUI

```bash
kb2xb-gui
# or
python ~/.local/share/kb2xb/kb2xb_gui.py
# or: search "Kb2Xb" in KDE app launcher (Meta key)
```

The GUI window shows:

- **Left panel** — profile list with New / Clone / Edit / Delete buttons
- **Right panel** — detected keyboards (check the ones to use), status dot, Start/Stop
- **System tray** — colored icon when active; right-click for quick Stop/Quit

Closing the window minimises to tray. The emulator keeps running.

### CLI

```bash
# Interactive selector (profile + keyboard)
kb2xb

# Skip selectors
kb2xb --profile bg3
kb2xb --profile bg3 --keyboard /dev/input/event3
kb2xb --profile bg3 --verbose
```

Press **Ctrl+C** to stop.

---

## Profile management

### GUI

Click **Edit** in the profile panel to open the editor:

- **Keymap tab** — click any button to enter capture mode, then press the key you want
- **Mouse tab** — enable mouse-to-stick for LS and/or RS, set modifier key and sensitivity
- **Device tab** — vendor/product IDs for the virtual gamepad
- **Options tab** — display name, startup delay, exclusive grab

### CLI

```bash
# List all profiles
kb2xb profile list

# Create a new profile (prompts for display name)
kb2xb profile create elden_ring

# Clone an existing profile's keymap
kb2xb profile create elden_ring --clone bg3

# Edit JSON directly in $EDITOR
kb2xb profile edit elden_ring

# Print profile JSON
kb2xb profile show elden_ring

# Delete
kb2xb profile delete elden_ring

# Valid key names
kb2xb keys
```

---

## Default keymap (BG3 profile)

| Xbox input          | Key                |
| ------------------- | ------------------ |
| L-Stick ↑↓←→        | W S A D            |
| R-Stick ↑↓←→        | I K J L            |
| D-Pad ↑↓←→          | ↑ ↓ ← →            |
| A / B / X / Y       | Space / F / E / Q  |
| LB / RB             | Tab / R            |
| LT / RT             | Z / C              |
| L3 / R3             | G / V              |
| Start / View        | Enter / Backspace  |
| **Mouse → L-Stick** | hold **Left Ctrl** |

---

## Mouse → analog stick

When a mouse mode is enabled, hold the configured key (default `ctrl_l` for L-Stick) to enter mouse mode:

- The mouse cursor's **displacement** from the hold position is mapped to the analog stick
- Moving the mouse 200 px (default sensitivity) in any direction = full deflection
- Releasing the key returns the stick to center and restores keyboard control

Adjust sensitivity in **Profile → Mouse tab** (10–2000 px = full range).

---

## Profile JSON format

Profiles live in `~/.config/kb2xb/profiles/<id>.json`.

```jsonc
{
  "id": "elden_ring",
  "display_name": "Elden Ring",
  "device": {
    "vendor": 1118, // 0x045E — Microsoft
    "product": 721, // 0x02D1 — Xbox One pad
    "version": 272,
    "name": "Microsoft Xbox One pad",
  },
  "keymap": {
    "ls_up": "w",
    "ls_down": "s",
    "ls_left": "a",
    "ls_right": "d",
    "rs_up": "i",
    "rs_down": "k",
    "rs_left": "j",
    "rs_right": "l",
    "dp_up": "up",
    "dp_down": "down",
    "dp_left": "left",
    "dp_right": "right",
    "a_btn": "space",
    "b_btn": "f",
    "x_btn": "e",
    "y_btn": "q",
    "lb": "tab",
    "rb": "r",
    "lt": "z",
    "rt": "c",
    "l3": "g",
    "r3": "v",
    "start": "return",
    "view": "backspace",
  },
  "mouse": {
    "ls_enabled": true,
    "rs_enabled": false,
    "ls_key": "ctrl_l",
    "rs_key": "ctrl_r",
    "ls_sensitivity": 200,
    "rs_sensitivity": 200,
  },
  "startup_delay_ms": 600,
  "grab": false, // true = exclusive device access
}
```

Run `kb2xb keys` to list all valid key name strings.

---

## Autostart with KDE

To launch Kb2Xb automatically when KDE starts:

```bash
# Method 1 — KDE autostart (GUI appears in system tray)
cp ~/.local/share/applications/kb2xb.desktop ~/.config/autostart/

# Method 2 — start hidden to tray (no window on boot)
# Edit the Exec line in ~/.config/autostart/kb2xb.desktop:
#   Exec=python ~/.local/share/kb2xb/kb2xb_gui.py
# The window auto-hides to tray on startup if started minimized.
```

Or use a systemd user unit for the CLI (no GUI, always-on):

```bash
# AUR install — the unit is already installed, just enable it:
systemctl --user enable --now kb2xb

# Source install — create the unit manually:
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/kb2xb.service << 'EOF'
[Unit]
Description=kb2xb keyboard-to-gamepad emulator
After=graphical-session.target

[Service]
ExecStart=python %h/.local/share/kb2xb/kb2xb.py --profile bg3
Restart=on-failure
RestartSec=3

[Install]
WantedBy=graphical-session.target
EOF

systemctl --user enable --now kb2xb.service
systemctl --user status kb2xb.service
```

---

## Publishing a new release (AUR)

This section is for maintainers. The PKGBUILD and .SRCINFO live exclusively in the [AUR repository](https://aur.archlinux.org/packages/kb2xb) and are **not** tracked here.

### Release checklist

**1 — Bump the version**

In `kb2xb.py`:

```python
__version__ = "x.y.z"
```

Version scheme (SemVer):

| Change                                | Bump                      |
| ------------------------------------- | ------------------------- |
| Bug fix, string tweak, visual patch   | `PATCH` — `1.0.0 → 1.0.1` |
| New feature, no breaking change       | `MINOR` — `1.0.1 → 1.1.0` |
| Breaking change (e.g. profile format) | `MAJOR` — `1.1.0 → 2.0.0` |

**2 — Commit and push to GitHub**

```bash
git add kb2xb.py kb2xb_gui.py   # (and any other changed files)
git commit -m "feat: short description"
git push
```

**3 — Create the GitHub release**

Go to `github.com/janyel-lima/kb2xb` → **Releases** → **Draft a new release**:

- Tag: `vx.y.z` (create new)
- Title: `Kb2Xb vx.y.z — Short title`
- Description: release notes
- ✅ Set as latest release

**4 — Update the AUR package**

```bash
cd kb2xb   # repo root

# Edit PKGBUILD: bump pkgver=x.y.z and reset pkgrel=1
nano PKGBUILD

# Fetch new tarball and regenerate sha256
updpkgsums

# Regenerate .SRCINFO
makepkg --printsrcinfo > .SRCINFO

# Push to AUR (PKGBUILD and .SRCINFO live only in the AUR repo)
cp PKGBUILD .SRCINFO ../aur-kb2xb/
cd ../aur-kb2xb
git add PKGBUILD .SRCINFO
git commit -m "upgpkg: kb2xb x.y.z-1 — short description"
git push
```

> **pkgrel** only: if you fix the PKGBUILD itself without bumping the software version, increment `pkgrel` (`1 → 2`) and keep `pkgver` unchanged.

---

## Troubleshooting

### "Permission denied" / uinput not writable

```bash
# Verify group membership (re-login if missing)
groups | grep -E 'input|uinput'

# Verify udev rule is loaded
ls -la /dev/uinput

# Test as root first
sudo python ~/.local/share/kb2xb/kb2xb.py
```

### No keyboard found

```bash
# List all input devices
python -c "import evdev; [print(d.path, evdev.InputDevice(d).name) for d in evdev.list_devices()]"

# Run with a specific path
kb2xb --keyboard /dev/input/event3
```

### Virtual pad not seen by game

Some games check device vendor/product IDs. The default mimics an Xbox One pad (`045E:02D1`). If your game refuses it, try changing the `device` block in the profile to match a pad it already supports, or set `vendor: 0` and `product: 0` for a generic HID gamepad.

Also verify the virtual device appears:

```bash
cat /proc/bus/input/devices | grep -A8 "Xbox"
```

### Wayland — keys not captured

The evdev reader bypasses Wayland's input capture. It reads directly from `/dev/input/event*`, so it works regardless of compositor. If you have issues, make sure your user is in the `input` group and the device path is accessible.

### Steam / Proton sees two controllers

Disable Steam's built-in keyboard-to-gamepad mapping in **Steam → Settings → Controller → Desktop configuration** (set it to "None").

### AUR install fails — conflicting files from pip

If you previously ran `kb2xb.py` directly before installing via the AUR, the bootstrap may have installed `python-uinput` via pip into the system site-packages. Pacman cannot overwrite those files. Remove them first:

```bash
sudo rm -rf \
  /usr/lib/python3*/site-packages/uinput \
  /usr/lib/python3*/site-packages/_libsuinput*.so \
  /usr/lib/python3*/site-packages/python_uinput-*.dist-info
```

Then retry `paru -S kb2xb`.

### Icon not updating in KDE launcher

KDE caches app icons separately from GTK. If the old icon persists after reinstalling:

```bash
rm -f ~/.local/share/icons/hicolor/icon-theme.cache
touch ~/.local/share/icons/hicolor
gtk-update-icon-cache --force --ignore-theme-index ~/.local/share/icons/hicolor/
kbuildsycoca6 --noincremental
```

The `install.sh` script runs these automatically, but if you installed manually or the launcher still shows the old icon, run the commands above.

---

## File layout

```
kb2xb/                          ← project source
    kb2xb.py
    kb2xb_gui.py
    icon.svg                    ← source icon (installed as kb2xb.svg)
    kb2xb.desktop
    kb2xb.install               ← pacman post-install hooks
    install.sh
    uninstall.sh
    completions/
        kb2xb.bash
        _kb2xb
        kb2xb.fish

~/.local/share/kb2xb/           ← source install only
    kb2xb.py                    ← CLI engine (standalone)
    kb2xb_gui.py                ← PySide6 GUI

/usr/share/kb2xb/               ← AUR install
    kb2xb.py
    kb2xb_gui.py

~/.config/kb2xb/
    settings.json               ← last profile, preferred keyboards
    profiles/
        bg3.json
        elden_ring.json
        ...

~/.local/share/icons/hicolor/scalable/apps/
    kb2xb.svg                   ← installed icon (Icon=kb2xb in .desktop)

~/.local/share/applications/
    kb2xb.desktop               ← Name=Kb2Xb

~/.local/bin/                   ← source install
    kb2xb                       ← CLI launcher
    kb2xb-gui                   ← GUI launcher

/usr/bin/                       ← AUR install
    kb2xb
    kb2xb-gui
```

---

## Uninstall

### AUR install

```bash
paru -R kb2xb
# Profiles at ~/.config/kb2xb/ are NOT removed — delete manually if needed:
rm -rf ~/.config/kb2xb
```

### Source install

```bash
chmod +x uninstall.sh
./uninstall.sh          # interactive (keeps profiles)
./uninstall.sh --purge  # removes everything including profiles
```

Or manually:

```bash
rm -rf ~/.local/share/kb2xb
rm -f  ~/.local/share/applications/kb2xb.desktop
rm -f  ~/.local/share/icons/hicolor/scalable/apps/kb2xb.svg
rm -f  ~/.local/bin/kb2xb ~/.local/bin/kb2xb-gui
rm -rf ~/.config/kb2xb          # ← removes all profiles; skip to keep them

# Rebuild caches after manual removal
update-desktop-database ~/.local/share/applications/
gtk-update-icon-cache --force --ignore-theme-index ~/.local/share/icons/hicolor/
kbuildsycoca6 --noincremental

# Remove system files (optional)
sudo rm -f /etc/udev/rules.d/99-uinput.rules
sudo rm -f /etc/modules-load.d/uinput.conf
```

---

## License

MIT
