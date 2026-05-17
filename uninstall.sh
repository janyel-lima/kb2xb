#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  kb2xb — uninstaller for Arch Linux / CachyOS
#
#  Usage:
#    chmod +x uninstall.sh
#    ./uninstall.sh          # interactive
#    ./uninstall.sh --yes    # non-interactive (remove everything)
#    ./uninstall.sh --purge  # also remove user profiles/config
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
skip()    { echo -e "${C_DIM}  -  $*${C_RESET}"; }
die()     { echo -e "${C_RED}${C_BOLD}  ✗${C_RESET} $*" >&2; exit 1; }
section() { echo; echo -e "${C_BOLD}${C_CYAN}── $* ──${C_RESET}"; echo; }

# ── Args ──────────────────────────────────────────────────────────────────────
AUTO_YES=false
PURGE=false
for arg in "$@"; do
    [[ "$arg" == "--yes"   ]] && AUTO_YES=true
    [[ "$arg" == "--purge" ]] && PURGE=true && AUTO_YES=true
done

confirm() {
    if $AUTO_YES; then return 0; fi
    local ans
    read -rp "    $1 [y/N] " ans
    [[ "${ans,,}" == "y" ]]
}

safe_remove() {
    # safe_remove <path> <description>
    local path="$1" desc="$2"
    if [[ -e "$path" || -L "$path" ]]; then
        rm -rf "$path"
        ok "Removed: $desc"
    else
        skip "Not found (already clean): $desc"
    fi
}

# ── Paths (must match install.sh) ─────────────────────────────────────────────
INSTALL_DIR="$HOME/.local/share/kb2xb"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
APPS_DIR="$HOME/.local/share/applications"
BIN_DIR="$HOME/.local/bin"
SYSTEMD_DIR="$HOME/.config/systemd/user"
CONFIG_DIR="$HOME/.config/kb2xb"
SERVICE_NAME="kb2xb"

# ── Header ────────────────────────────────────────────────────────────────────
echo
echo -e "${C_BOLD}${C_RED}"
echo "  ██╗  ██╗██████╗ ██████╗ ██╗  ██╗██████╗  ██████╗ ██╗  ██╗"
echo "  ██║ ██╔╝██╔══██╗╚════██╗╚██╗██╔╝██╔══██╗██╔═══██╗╚██╗██╔╝"
echo "  █████╔╝ ██████╔╝ █████╔╝ ╚███╔╝ ██████╔╝██║   ██║ ╚███╔╝ "
echo "  ██╔═██╗ ██╔══██╗██╔═══╝  ██╔██╗ ██╔══██╗██║   ██║ ██╔██╗ "
echo "  ██║  ██╗██████╔╝███████╗██╔╝ ██╗██████╔╝╚██████╔╝██╔╝ ██╗"
echo "  ╚═╝  ╚═╝╚═════╝ ╚══════╝╚═╝  ╚═╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝"
echo -e "${C_RESET}"
echo "  Uninstaller — Arch / CachyOS"
echo

[[ "$EUID" -eq 0 ]] && die "Do not run as root."

if $PURGE; then
    echo -e "  ${C_RED}${C_BOLD}PURGE MODE:${C_RESET} All files including profiles/config will be deleted."
else
    echo "  Profiles and config in ~/.config/kb2xb will be preserved."
    echo "  Use --purge to also delete them."
fi
echo

confirm "Proceed with uninstallation?" || { echo "  Aborted."; exit 0; }

# ── Stop & disable systemd service ───────────────────────────────────────────
section "systemd user service"

SERVICE_FILE="$SYSTEMD_DIR/${SERVICE_NAME}.service"

if systemctl --user is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    info "Stopping service: $SERVICE_NAME"
    systemctl --user stop "$SERVICE_NAME" && ok "Service stopped" || warn "Could not stop service"
else
    skip "Service not running"
fi

if systemctl --user is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    info "Disabling service: $SERVICE_NAME"
    systemctl --user disable "$SERVICE_NAME" && ok "Service disabled" || warn "Could not disable service"
else
    skip "Service not enabled"
fi

safe_remove "$SERVICE_FILE" "systemd service file"

if [[ -d "$SYSTEMD_DIR" ]]; then
    systemctl --user daemon-reload 2>/dev/null && ok "systemd daemon reloaded" || true
fi

# ── Application files ─────────────────────────────────────────────────────────
section "Application files"

safe_remove "$INSTALL_DIR" "install directory ($INSTALL_DIR)"

# Stale backups created by installer
for bak in "$HOME/.local/share/kb2xb.bak."*; do
    [[ -d "$bak" ]] && safe_remove "$bak" "backup: $bak"
done

# ── Launchers ─────────────────────────────────────────────────────────────────
section "Launchers"

safe_remove "$BIN_DIR/kb2xb"     "CLI launcher"
safe_remove "$BIN_DIR/kb2xb-gui" "GUI launcher"

# ── Desktop entry & icon ──────────────────────────────────────────────────────
section "Desktop integration"

safe_remove "$APPS_DIR/kb2xb.desktop" "desktop entry"
safe_remove "$ICON_DIR/kb2xb.svg"     "application icon"

# Rebuild desktop and icon caches so the launcher forgets the old entry
info "Rebuilding desktop database and icon cache…"
update-desktop-database "$APPS_DIR" 2>/dev/null || true
# --force ensures the cache is rewritten even if timestamps look fresh
touch "$HOME/.local/share/icons/hicolor"
gtk-update-icon-cache --force --ignore-theme-index \
    "$HOME/.local/share/icons/hicolor/" 2>/dev/null || true
ok "Desktop database and icon cache updated"

# ── udev rule ─────────────────────────────────────────────────────────────────
section "System configuration (udev / kernel module)"

UDEV_RULE="/etc/udev/rules.d/99-uinput.rules"
MODLOAD_CONF="/etc/modules-load.d/uinput.conf"

if confirm "Remove udev rule $UDEV_RULE? (only if no other app needs it)"; then
    if [[ -f "$UDEV_RULE" ]]; then
        sudo rm -f "$UDEV_RULE"
        sudo udevadm control --reload-rules
        sudo udevadm trigger
        ok "udev rule removed and rules reloaded"
    else
        skip "udev rule not found"
    fi
else
    skip "Keeping udev rule"
fi

if confirm "Remove $MODLOAD_CONF? (prevents uinput from loading at boot)"; then
    if [[ -f "$MODLOAD_CONF" ]]; then
        sudo rm -f "$MODLOAD_CONF"
        ok "Removed $MODLOAD_CONF"
    else
        skip "$MODLOAD_CONF not found"
    fi
else
    skip "Keeping $MODLOAD_CONF"
fi

# ── Groups ────────────────────────────────────────────────────────────────────
section "User groups"

warn "Group memberships (input, uinput) are NOT removed automatically."
warn "To remove manually if desired:"
warn "  sudo gpasswd -d $USER input"
warn "  sudo gpasswd -d $USER uinput"

# ── Config / profiles ─────────────────────────────────────────────────────────
section "User configuration"

if $PURGE; then
    safe_remove "$CONFIG_DIR" "config + profiles ($CONFIG_DIR)"
else
    skip "Keeping profiles/config: $CONFIG_DIR  (use --purge to delete)"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
section "Uninstallation complete"

echo "  Removed: application files, launchers, desktop entry, icon"
echo "  Removed: systemd user service"
if $PURGE; then
    echo "  Removed: profiles and config ($CONFIG_DIR)"
else
    echo "  Kept:    profiles and config ($CONFIG_DIR)"
fi
echo
ok "Kb2Xb has been uninstalled."

if ! $PURGE && [[ -d "$CONFIG_DIR" ]]; then
    echo
    echo -e "  ${C_DIM}Your profiles are still at $CONFIG_DIR"
    echo -e "  Run with --purge to delete them.${C_RESET}"
fi
echo
