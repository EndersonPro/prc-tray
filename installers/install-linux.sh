#!/usr/bin/env bash
set -euo pipefail

# PRC Tray — Linux Installer
# Creates a .deb package using dpkg-deb (no extra tools needed)
# Also supports raw install to ~/.local/bin with systemd user service

APP_NAME="prc-tray"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="${PROJECT_DIR}/dist/prc-tray"

# Resolve version: env var > pyproject.toml
VERSION="${PRC_TRAY_VERSION:-}"
if [[ -z "${VERSION}" ]]; then
    VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('${PROJECT_DIR}/pyproject.toml', 'rb'))['project']['version'])" 2>/dev/null || echo "0.0.0-dev")
fi

# Parse args
AUTO_DEB=false
for arg in "$@"; do
    case "$arg" in
        --deb) AUTO_DEB=true ;;
    esac
done

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== PRC Tray — Linux Installer ===${NC}"
echo ""

if [ ! -f "${DIST_DIR}/prc-tray" ]; then
    echo -e "${RED}Error: Binary not found at ${DIST_DIR}/prc-tray${NC}"
    echo "Run first: uv run pyinstaller daemon.spec --noconfirm --clean"
    exit 1
fi

if [[ "${AUTO_DEB}" == "true" ]]; then
    choice=3
else
    echo "Select install method:"
    echo "  1) System install (/usr/local/bin + systemd user service)"
    echo "  2) User install (~/.local/bin + systemd user service)"
    echo "  3) Build .deb package"
    echo ""
    read -p "Choice [1-3]: " choice
fi

install_systemd_service() {
    local install_path="$1"
    local service_dir="${HOME}/.config/systemd/user"
    mkdir -p "${service_dir}"

    cat > "${service_dir}/prc-tray.service" << SERVICE
[Unit]
Description=PRC Tray — YouTube streaming URL extractor
After=network.target

[Service]
Type=simple
ExecStart=${install_path}/prc-tray --no-tray
Restart=on-failure
RestartSec=10
Environment=YTDLP_DAEMON_MODE=prod
Environment=YTDLP_API_KEY=CHANGE_ME_TO_YOUR_API_KEY

[Install]
WantedBy=default.target
SERVICE

    systemctl --user daemon-reload
    systemctl --user enable prc-tray.service
    echo -e "${GREEN}Systemd service installed.${NC}"
    echo "  Start:   systemctl --user start prc-tray"
    echo "  Stop:    systemctl --user stop prc-tray"
    echo "  Status:  systemctl --user status prc-tray"
    echo "  Logs:    journalctl --user -u prc-tray -f"
    echo "  Disable: systemctl --user disable prc-tray"
}

case "${choice}" in
    1)
        echo "Installing to /usr/local/bin (requires sudo)..."
        sudo mkdir -p /usr/local/lib/prc-tray
        sudo cp -R "${DIST_DIR}/"* /usr/local/lib/prc-tray/
        sudo ln -sf /usr/local/lib/prc-tray/prc-tray /usr/local/bin/prc-tray
        install_systemd_service "/usr/local/lib/prc-tray"
        echo -e "${GREEN}Installed to /usr/local/bin/prc-tray${NC}"
        ;;
    2)
        echo "Installing to ~/.local/bin..."
        mkdir -p "${HOME}/.local/lib/prc-tray"
        mkdir -p "${HOME}/.local/bin"
        cp -R "${DIST_DIR}/"* "${HOME}/.local/lib/prc-tray/"
        ln -sf "${HOME}/.local/lib/prc-tray/prc-tray" "${HOME}/.local/bin/prc-tray"
        install_systemd_service "${HOME}/.local/lib/prc-tray"
        echo -e "${GREEN}Installed to ~/.local/bin/prc-tray${NC}"
        ;;
    3)
        echo "Building .deb package..."
        DEB_ROOT="/tmp/${APP_NAME}-deb"
        DEB_OUTPUT="${SCRIPT_DIR}/PRC-Tray-${VERSION}-linux-amd64.deb"
        rm -rf "${DEB_ROOT}"

        # Create package structure
        mkdir -p "${DEB_ROOT}/DEBIAN"
        mkdir -p "${DEB_ROOT}/usr/local/lib/prc-tray"
        mkdir -p "${DEB_ROOT}/usr/local/bin"

        # Copy binary
        cp -R "${DIST_DIR}/"* "${DEB_ROOT}/usr/local/lib/prc-tray/"

        # Symlink
        ln -sf /usr/local/lib/prc-tray/prc-tray "${DEB_ROOT}/usr/local/bin/prc-tray"

        # Control file
        cat > "${DEB_ROOT}/DEBIAN/control" << CONTROL
Package: prc-tray
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: amd64
Maintainer: endersonvizc
Description: Local daemon for YouTube streaming URL extraction
 Wraps yt-dlp into a local HTTP server at 127.0.0.1:17171.
 Used by music.endersonvizc.dev to extract streaming URLs.
CONTROL

        # Post-install script
        cat > "${DEB_ROOT}/DEBIAN/postinst" << 'POSTINST'
#!/bin/bash
echo "prc-tray installed to /usr/local/bin/prc-tray"
echo "Run with: prc-tray --no-tray"
echo "Or set up systemd user service (see README)"
POSTINST
        chmod 755 "${DEB_ROOT}/DEBIAN/postinst"

        dpkg-deb --build "${DEB_ROOT}" "${DEB_OUTPUT}"
        echo -e "${GREEN}Package built: ${DEB_OUTPUT}${NC}"
        echo "Install with: sudo dpkg -i ${DEB_OUTPUT}"
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo -e "${YELLOW}Don't forget to set your YTDLP_API_KEY in the service config!${NC}"
