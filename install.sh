#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  kb2xb — ultimate installer for Arch Linux / CachyOS
#
#  Usage:
#    chmod +x install.sh
#    ./install.sh            # interactive (GUI + CLI)
#    ./install.sh --no-gui   # engine only (no PySide6)
#    ./install.sh --yes      # non-interactive (accept all prompts)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
C_RESET='\033[0m'
C_BOLD='\033[1m'
C_CYAN='\033[36m'
C_GREEN='\033[32m'
C_YELLOW='\033[33m'
C_RED='\033[31m'
C_DIM='\033[2m'

info()    { echo -e "${C_CYAN}${C_BOLD}  →${C_RESET} $*"; }
ok()      { echo -e "${C_GREEN}${C_BOLD}  ✓${C_RESET} $*"; }
warn()    { echo -e "${C_YELLOW}${C_BOLD}  !${C_RESET} $*"; }
die()     { echo -e "${C_RED}${C_BOLD}  ✗${C_RESET} $*" >&2; exit 1; }
dim()     { echo -e "${C_DIM}    $*${C_RESET}"; }
section() { echo; echo -e "${C_BOLD}${C_CYAN}── $* ──${C_RESET}"; echo; }

# ── Args ──────────────────────────────────────────────────────────────────────
INSTALL_GUI=true
AUTO_YES=false
for arg in "$@"; do
    [[ "$arg" == "--no-gui" ]] && INSTALL_GUI=false
    [[ "$arg" == "--yes"   ]] && AUTO_YES=true
done

confirm() {
    if $AUTO_YES; then return 0; fi
    local ans
    read -rp "    $1 [Y/n] " ans
    [[ "${ans,,}" != "n" ]]
}

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/share/kb2xb"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
APPS_DIR="$HOME/.local/share/applications"
BIN_DIR="$HOME/.local/bin"
SYSTEMD_DIR="$HOME/.config/systemd/user"
SERVICE_NAME="kb2xb"

# ── Header ────────────────────────────────────────────────────────────────────
echo
echo -e "${C_BOLD}${C_CYAN}"
echo "  ██╗  ██╗██████╗ ██████╗ ██╗  ██╗██████╗  ██████╗ ██╗  ██╗"
echo "  ██║ ██╔╝██╔══██╗╚════██╗╚██╗██╔╝██╔══██╗██╔═══██╗╚██╗██╔╝"
echo "  █████╔╝ ██████╔╝ █████╔╝ ╚███╔╝ ██████╔╝██║   ██║ ╚███╔╝ "
echo "  ██╔═██╗ ██╔══██╗██╔═══╝  ██╔██╗ ██╔══██╗██║   ██║ ██╔██╗ "
echo "  ██║  ██╗██████╔╝███████╗██╔╝ ██╗██████╔╝╚██████╔╝██╔╝ ██╗"
echo "  ╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝"
echo -e "${C_RESET}"
echo "  Keyboard + Mouse → Xbox One virtual gamepad"
echo "  Installer v2 — Arch / CachyOS"
echo

# ── Sanity checks ─────────────────────────────────────────────────────────────
section "Checking environment"

[[ "$EUID" -eq 0 ]] && die "Do not run as root. The script uses sudo where needed."
command -v pacman &>/dev/null || die "pacman not found — Arch / CachyOS only."
command -v python &>/dev/null || die "python not found.  Install: sudo pacman -S python"
command -v pip    &>/dev/null || die "pip not found.     Install: sudo pacman -S python-pip"
command -v git    &>/dev/null || die "git not found.     Install: sudo pacman -S git"

[[ -f "$SCRIPT_DIR/kb2xb.py"     ]] || die "kb2xb.py not found in $SCRIPT_DIR"
[[ -f "$SCRIPT_DIR/kb2xb_gui.py" ]] || die "kb2xb_gui.py not found in $SCRIPT_DIR"
[[ -f "$SCRIPT_DIR/icon.svg"      ]] || warn "icon.svg not found — app icon will be missing"

PYTHON_VERSION=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
ok "Python $PYTHON_VERSION found"
ok "Running as user: $USER"
ok "Source directory: $SCRIPT_DIR"

# ── System dependencies via pacman ────────────────────────────────────────────
section "Installing system packages (pacman)"

info "Running: sudo pacman -S --needed --noconfirm python-evdev"
sudo pacman -S --needed --noconfirm python-evdev
ok "python-evdev installed"

# ── PySide6 via pip ───────────────────────────────────────────────────────────
if $INSTALL_GUI; then
    section "Installing PySide6 (pip)"

    if python -c "import PySide6" 2>/dev/null; then
        ok "PySide6 already installed — skipping"
    else
        info "Installing PySide6 via pip (this may take a minute)…"
        # --break-system-packages needed on Arch (PEP 668 externally-managed env)
        pip install --break-system-packages --quiet PySide6
        if python -c "import PySide6" 2>/dev/null; then
            ok "PySide6 installed successfully"
        else
            die "PySide6 installation failed. Try manually: pip install --break-system-packages PySide6"
        fi
    fi
fi

# ── python-uinput (AUR) ───────────────────────────────────────────────────────
section "Installing python-uinput (AUR)"

if python -c "import uinput" 2>/dev/null; then
    ok "python-uinput already available — skipping"
else
    AUR_SUCCESS=false

    if [ "$AUR_SUCCESS" = false ] && command -v yay &>/dev/null; then
        info "Trying via yay..."
        yay -S --needed --noconfirm python-uinput && AUR_SUCCESS=true \
            || warn "yay could not install python-uinput"
    fi

    if [ "$AUR_SUCCESS" = false ] && command -v paru &>/dev/null; then
        info "Trying via paru..."
        paru -S --needed --noconfirm python-uinput && AUR_SUCCESS=true \
            || warn "paru could not install python-uinput"
    fi

    if [ "$AUR_SUCCESS" = false ]; then
        warn "No AUR helper succeeded — attempting manual git clone…"
        _tmp=$(mktemp -d)
        trap 'rm -rf "$_tmp"' EXIT
        if git clone https://aur.archlinux.org/python-uinput.git "$_tmp/python-uinput" 2>/dev/null; then
            pushd "$_tmp/python-uinput" >/dev/null
            makepkg -si --noconfirm && AUR_SUCCESS=true || warn "makepkg failed"
            popd >/dev/null
        else
            warn "Git clone of AUR package failed"
        fi
        trap - EXIT
        rm -rf "$_tmp"
    fi

    if [ "$AUR_SUCCESS" = true ]; then
        ok "python-uinput installed"
    else
        die "Could not install python-uinput. Install it manually and re-run."
    fi
fi

# ── uinput kernel module ──────────────────────────────────────────────────────
section "Configuring uinput kernel module"

MODLOAD_CONF="/etc/modules-load.d/uinput.conf"
if [[ -f "$MODLOAD_CONF" ]] && grep -q "^uinput" "$MODLOAD_CONF" 2>/dev/null; then
    ok "uinput already in $MODLOAD_CONF"
else
    info "Writing $MODLOAD_CONF"
    echo "uinput" | sudo tee "$MODLOAD_CONF" > /dev/null
    ok "Created $MODLOAD_CONF"
fi

sudo modprobe uinput 2>/dev/null && ok "uinput module loaded now" \
    || warn "Could not modprobe uinput (may need reboot)"

# ── udev rule ─────────────────────────────────────────────────────────────────
UDEV_RULE="/etc/udev/rules.d/99-uinput.rules"
if [[ -f "$UDEV_RULE" ]]; then
    ok "udev rule already exists: $UDEV_RULE"
else
    info "Writing udev rule: $UDEV_RULE"
    echo 'KERNEL=="uinput", GROUP="uinput", MODE="0660"' \
        | sudo tee "$UDEV_RULE" > /dev/null
    ok "udev rule created"
fi

info "Reloading udev rules"
sudo udevadm control --reload-rules
sudo udevadm trigger
ok "udev reloaded"

# ── Groups ────────────────────────────────────────────────────────────────────
section "Configuring user groups"

GROUPS_ADDED=()
for g in input uinput; do
    getent group "$g" &>/dev/null || { info "Creating group: $g"; sudo groupadd -f "$g"; }
    if id -nG "$USER" | grep -qw "$g"; then
        ok "Already in group: $g"
    else
        info "Adding $USER to group: $g"
        sudo usermod -aG "$g" "$USER"
        GROUPS_ADDED+=("$g")
    fi
done

# ── Install application files ─────────────────────────────────────────────────
section "Installing application files"

if [[ -d "$INSTALL_DIR" ]]; then
    BACKUP="$INSTALL_DIR.bak.$(date +%s)"
    info "Backing up existing install → $BACKUP"
    cp -r "$INSTALL_DIR" "$BACKUP"
fi

mkdir -p "$INSTALL_DIR"

install -Dm644 "$SCRIPT_DIR/kb2xb.py" "$INSTALL_DIR/kb2xb.py"
ok "Installed: kb2xb.py"

if $INSTALL_GUI; then
    install -Dm644 "$SCRIPT_DIR/kb2xb_gui.py" "$INSTALL_DIR/kb2xb_gui.py"
    ok "Installed: kb2xb_gui.py"
fi

# ── Icon ──────────────────────────────────────────────────────────────────────
if [[ -f "$SCRIPT_DIR/icon.svg" ]]; then
    mkdir -p "$ICON_DIR"
    # Source is icon.svg; installed as kb2xb.svg so Icon=kb2xb in the .desktop resolves correctly
    install -Dm644 "$SCRIPT_DIR/icon.svg" "$ICON_DIR/kb2xb.svg"
    # Force icon theme cache rebuild (touch forces timestamp update)
    touch "$HOME/.local/share/icons/hicolor"
    gtk-update-icon-cache --force --ignore-theme-index \
        "$HOME/.local/share/icons/hicolor/" 2>/dev/null || true
    ok "Icon installed: $ICON_DIR/kb2xb.svg"
fi

# ── Desktop entry ─────────────────────────────────────────────────────────────
if $INSTALL_GUI; then
    section "Installing desktop entry"
    mkdir -p "$APPS_DIR"

    # Remove any stale entry first to avoid the launcher showing a cached name
    rm -f "$APPS_DIR/kb2xb.desktop"

    cat > "$APPS_DIR/kb2xb.desktop" << EOF
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

    # Validate the entry and rebuild the desktop database
    if command -v desktop-file-validate &>/dev/null; then
        desktop-file-validate "$APPS_DIR/kb2xb.desktop" \
            && ok "Desktop entry validated" \
            || warn "Desktop entry validation warning (non-fatal)"
    fi
    update-desktop-database "$APPS_DIR"
    ok "Desktop entry: $APPS_DIR/kb2xb.desktop  (Name=Kb2Xb)"
fi

# ── Launchers ─────────────────────────────────────────────────────────────────
section "Creating launchers"
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/kb2xb" << EOF
#!/usr/bin/env bash
exec python "$INSTALL_DIR/kb2xb.py" "\$@"
EOF
chmod +x "$BIN_DIR/kb2xb"
ok "CLI launcher: $BIN_DIR/kb2xb"

if $INSTALL_GUI; then
    cat > "$BIN_DIR/kb2xb-gui" << EOF
#!/usr/bin/env bash
exec python "$INSTALL_DIR/kb2xb_gui.py" "\$@"
EOF
    chmod +x "$BIN_DIR/kb2xb-gui"
    ok "GUI launcher: $BIN_DIR/kb2xb-gui"
fi

if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    warn "~/.local/bin is not in your PATH."
    warn "Add to ~/.bashrc or ~/.zshrc:"
    warn '  export PATH="$HOME/.local/bin:$PATH"'
fi

# ── systemd user service ──────────────────────────────────────────────────────
section "systemd user service (optional autostart)"

if confirm "Install systemd user service for CLI autostart on login?"; then
    mkdir -p "$SYSTEMD_DIR"
    cat > "$SYSTEMD_DIR/${SERVICE_NAME}.service" << EOF
[Unit]
Description=kb2xb — keyboard/mouse to Xbox gamepad
After=network.target

[Service]
Type=simple
ExecStart=python $INSTALL_DIR/kb2xb.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    ok "Service installed: $SYSTEMD_DIR/${SERVICE_NAME}.service"
    dim "To enable autostart: systemctl --user enable --now ${SERVICE_NAME}"
    dim "To start now:        systemctl --user start ${SERVICE_NAME}"
    dim "To view logs:        journalctl --user -u ${SERVICE_NAME} -f"
else
    info "Skipping systemd service"
fi

# ── Verify installation ───────────────────────────────────────────────────────
section "Verifying installation"

ERRORS=0
check_file() {
    if [[ -f "$1" ]]; then
        ok "Found: $1"
    else
        warn "Missing: $1"
        (( ERRORS++ )) || true
    fi
}

check_file "$INSTALL_DIR/kb2xb.py"
$INSTALL_GUI && check_file "$INSTALL_DIR/kb2xb_gui.py"
check_file "$BIN_DIR/kb2xb"
$INSTALL_GUI && check_file "$BIN_DIR/kb2xb-gui"
$INSTALL_GUI && check_file "$APPS_DIR/kb2xb.desktop"

# Confirm the Name field is correct in the installed .desktop
if $INSTALL_GUI && [[ -f "$APPS_DIR/kb2xb.desktop" ]]; then
    INSTALLED_NAME=$(grep "^Name=" "$APPS_DIR/kb2xb.desktop" | cut -d= -f2)
    if [[ "$INSTALLED_NAME" == "Kb2Xb" ]]; then
        ok "Desktop entry Name field: '$INSTALLED_NAME' ✓"
    else
        warn "Desktop entry Name field is '$INSTALLED_NAME', expected 'Kb2Xb'"
        (( ERRORS++ )) || true
    fi
fi

python -c "import evdev"  2>/dev/null && ok "python-evdev importable" \
    || warn "python-evdev not importable"
python -c "import uinput" 2>/dev/null && ok "python-uinput importable" \
    || warn "python-uinput not importable (may need re-login)"
if $INSTALL_GUI; then
    python -c "import PySide6" 2>/dev/null && ok "PySide6 importable" \
        || warn "PySide6 not importable"
fi

[[ $ERRORS -eq 0 ]] && ok "All checks passed" || warn "$ERRORS issue(s) found — review above"

# ── Summary ───────────────────────────────────────────────────────────────────
section "Installation complete"

echo "  Installed to   : $INSTALL_DIR"
echo "  Config/profiles: ~/.config/kb2xb/profiles/"
echo
$INSTALL_GUI && echo "  Launch GUI     : kb2xb-gui"
$INSTALL_GUI && echo "                   or search 'Kb2Xb' in your app launcher"
echo "  Launch CLI     : kb2xb [--profile <id>]"
echo

if [[ ${#GROUPS_ADDED[@]} -gt 0 ]]; then
    echo -e "  ${C_YELLOW}${C_BOLD}ACTION REQUIRED:${C_RESET} You were added to groups: ${GROUPS_ADDED[*]}"
    echo "  Re-login or reboot for group membership to take effect."
    echo "  Until then you can run: sudo kb2xb"
    echo
fi

ok "Done. Enjoy Kb2Xb!"
