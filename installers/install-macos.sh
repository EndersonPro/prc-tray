#!/usr/bin/env bash
set -euo pipefail

# PRC Tray — macOS Installer
# By default: creates a .dmg with drag-to-install .app
# With --pkg: creates a .pkg with LaunchAgent auto-start

APP_NAME="prc-tray"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Parse args
NON_INTERACTIVE=false
BUILD_PKG=false
for arg in "$@"; do
    case "$arg" in
        --non-interactive) NON_INTERACTIVE=true ;;
        --pkg) BUILD_PKG=true ;;
    esac
done

# Load signing config
ENV_FILE="${PROJECT_DIR}/.env.local"
if [[ -f "${ENV_FILE}" ]]; then
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
fi

INSTALL_DIR="/Applications/${APP_NAME}.app"
LAUNCH_AGENT_PLIST="com.endersonvizc.prc-tray.plist"
LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
DIST_DIR="${PROJECT_DIR}/dist/prc-tray"
APP_BUNDLE="/tmp/${APP_NAME}.app"
DMG_OUTPUT="${SCRIPT_DIR}/${APP_NAME}-macos.dmg"
PKG_OUTPUT="${SCRIPT_DIR}/${APP_NAME}-macos.pkg"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== PRC Tray — macOS Installer Builder ===${NC}"
echo ""

# --- Pre-flight ---
if [ ! -f "${DIST_DIR}/prc-tray" ]; then
    echo -e "${RED}Error: Binary not found at ${DIST_DIR}/prc-tray${NC}"
    echo "Run first: uv run pyinstaller daemon.spec --noconfirm --clean"
    exit 1
fi

# --- Prompt for API key (only for .pkg mode) ---
if [[ "${BUILD_PKG}" == "true" ]]; then
    if [[ -z "${YTDLP_API_KEY:-}" ]]; then
        if [[ "${NON_INTERACTIVE}" == "true" ]]; then
            echo -e "${YELLOW}Non-interactive mode: skipping API key prompt (using default)${NC}"
        else
            echo -e "${YELLOW}Enter your API key for prod mode (or press Enter to skip — users can set it later):${NC}"
            read -r -s YTDLP_API_KEY
            echo ""
        fi
    fi
    API_KEY_VALUE="${YTDLP_API_KEY:-CHANGE_ME_TO_YOUR_API_KEY}"
fi

# --- Create .app bundle ---
echo "Creating .app bundle..."
rm -rf "${APP_BUNDLE}"
mkdir -p "${APP_BUNDLE}/Contents/MacOS"
mkdir -p "${APP_BUNDLE}/Contents/Resources"

# Copy binary and libs
cp -R "${DIST_DIR}/"* "${APP_BUNDLE}/Contents/MacOS/"

# Create Info.plist
cat > "${APP_BUNDLE}/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>PRC Tray</string>
    <key>CFBundleDisplayName</key>
    <string>PRC Tray</string>
    <key>CFBundleIdentifier</key>
    <string>com.endersonvizc.prc-tray</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleExecutable</key>
    <string>prc-tray</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
PLIST

if [[ "${BUILD_PKG}" == "true" ]]; then
    # --- .pkg mode: with LaunchAgent auto-start ---
    command -v pkgbuild >/dev/null 2>&1 || {
        echo -e "${RED}Error: pkgbuild not found. Install Xcode CLI Tools: xcode-select --install${NC}"
        exit 1
    }

    PKG_ROOT="/tmp/${APP_NAME}-pkg-root"
    rm -rf "${PKG_ROOT}"
    mkdir -p "${PKG_ROOT}/Applications"
    mv "${APP_BUNDLE}" "${PKG_ROOT}/Applications/"

    # Create LaunchAgent plist
    echo "Creating LaunchAgent..."
    mkdir -p "${PKG_ROOT}${LAUNCH_AGENT_DIR}"
    cat > "${PKG_ROOT}${LAUNCH_AGENT_DIR}/${LAUNCH_AGENT_PLIST}" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.endersonvizc.prc-tray</string>
    <key>ProgramArguments</key>
    <array>
        <string>${INSTALL_DIR}/Contents/MacOS/prc-tray</string>
        <string>--no-tray</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/tmp/prc-tray.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/prc-tray.err</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>YTDLP_DAEMON_MODE</key>
        <string>prod</string>
        <key>YTDLP_API_KEY</key>
        <string>${API_KEY_VALUE}</string>
    </dict>
</dict>
</plist>
PLIST

    # Preinstall script (stop existing instance)
    mkdir -p "${PKG_ROOT}/scripts"
    cat > "${PKG_ROOT}/scripts/preinstall" << 'PREINSTALL'
#!/bin/bash
pkill -f "prc-tray" 2>/dev/null || true
launchctl unload "$HOME/Library/LaunchAgents/com.endersonvizc.prc-tray.plist" 2>/dev/null || true
PREINSTALL
    chmod +x "${PKG_ROOT}/scripts/preinstall"

    # Postinstall script (load LaunchAgent)
    cat > "${PKG_ROOT}/scripts/postinstall" << 'POSTINSTALL'
#!/bin/bash
launchctl load -w ~/Library/LaunchAgents/com.endersonvizc.prc-tray.plist 2>/dev/null || true
echo "PRC Tray installed and started."
POSTINSTALL
    chmod +x "${PKG_ROOT}/scripts/postinstall"

    # Build .pkg
    echo "Building .pkg..."
    rm -f "${PKG_OUTPUT}"

    pkgbuild \
        --root "${PKG_ROOT}" \
        --identifier "com.endersonvizc.prc-tray" \
        --version "1.0.0" \
        --install-location "/" \
        --scripts "${PKG_ROOT}/scripts" \
        "${PKG_OUTPUT}"

    # Sign the .pkg
    SIGNING_IDENTITY="${SIGNING_IDENTITY:--}"
    echo "Signing with identity: ${SIGNING_IDENTITY}"
    codesign --force --sign "${SIGNING_IDENTITY}" "${PKG_OUTPUT}"

    # Cleanup
    rm -rf "${PKG_ROOT}"

    echo ""
    echo -e "${GREEN}=== Build complete ===${NC}"
    echo "Output: ${PKG_OUTPUT}"
    echo "Size: $(du -h "${PKG_OUTPUT}" | cut -f1)"
    echo "Signed: ${SIGNING_IDENTITY}"
    echo ""
    echo -e "${YELLOW}For users:${NC}"
    echo "  - Double-click .pkg to install"
    echo "  - Daemon auto-starts on login (no Terminal window)"
    echo "  - Logs: /tmp/prc-tray.log and /tmp/prc-tray.err"
    echo "  - Stop:  launchctl unload ~/Library/LaunchAgents/${LAUNCH_AGENT_PLIST}"
    echo "  - Start: launchctl load ~/Library/LaunchAgents/${LAUNCH_AGENT_PLIST}"
    echo "  - Uninstall: launchctl unload ~/Library/LaunchAgents/${LAUNCH_AGENT_PLIST} && rm -rf ${INSTALL_DIR}"

else
    # --- .dmg mode: drag-to-install (default) ---
    echo "Creating DMG..."
    rm -f "${DMG_OUTPUT}"

    hdiutil create -volname "PRC Tray" \
        -srcfolder "${APP_BUNDLE}" \
        -ov -format UDZO \
        "${DMG_OUTPUT}"

    # Cleanup
    rm -rf "${APP_BUNDLE}"

    echo ""
    echo -e "${GREEN}=== Build complete ===${NC}"
    echo "Output: ${DMG_OUTPUT}"
    echo "Size: $(du -h "${DMG_OUTPUT}" | cut -f1)"
    echo ""
    echo -e "${YELLOW}For users:${NC}"
    echo "  - Open .dmg and drag PRC Tray to Applications"
    echo "  - Double-click PRC Tray in Applications to start"
    echo "  - Logs: /tmp/prc-tray.log and /tmp/prc-tray.err"
fi
