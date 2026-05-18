#!/usr/bin/env bash
set -euo pipefail

# PRC Tray — macOS Installer
# By default: creates a .dmg with drag-to-install .app
# With --pkg: creates a .pkg with LaunchAgent auto-start

APP_NAME="prc-tray"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Resolve version: env var > pyproject.toml
VERSION="${PRC_TRAY_VERSION:-}"
if [[ -z "${VERSION}" ]]; then
    VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('${PROJECT_DIR}/pyproject.toml', 'rb'))['project']['version'])" 2>/dev/null || echo "0.0.0-dev")
fi

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

INSTALL_DIR="/Applications/PRC Tray.app"
LAUNCH_AGENT_PLIST="com.endersonvizc.prc-tray.plist"
LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
DIST_BINARY="${PROJECT_DIR}/dist/prc-tray"
APP_BUNDLE="/tmp/PRC Tray.app"
DMG_OUTPUT="${SCRIPT_DIR}/PRC-Tray-${VERSION}-macos.dmg"
PKG_OUTPUT="${SCRIPT_DIR}/PRC-Tray-${VERSION}-macos.pkg"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== PRC Tray — macOS Installer Builder ===${NC}"
echo ""

# --- Pre-flight ---
if [ ! -f "${DIST_BINARY}" ]; then
    echo -e "${RED}Error: Binary not found at ${DIST_BINARY}${NC}"
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

# Copy single-file binary
cp "${DIST_BINARY}" "${APP_BUNDLE}/Contents/MacOS/prc-tray"
chmod +x "${APP_BUNDLE}/Contents/MacOS/prc-tray"

# Copy icon if available
if [ -f "${PROJECT_DIR}/assets/logo.png" ]; then
    cp "${PROJECT_DIR}/assets/logo.png" "${APP_BUNDLE}/Contents/Resources/AppIcon.png"
fi

# Create Info.plist — LSUIElement=true hides from Dock (daemon mode)
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
    <string>${VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>${VERSION}</string>
    <key>CFBundleExecutable</key>
    <string>prc-tray</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
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
        --version "${VERSION}" \
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
    echo "  - Uninstall: launchctl unload ~/Library/LaunchAgents/${LAUNCH_AGENT_PLIST} && rm -rf '${INSTALL_DIR}'"

else
    # --- .dmg mode: drag-to-install (default) ---
    command -v create-dmg >/dev/null 2>&1 || {
        echo -e "${RED}Error: create-dmg not found. Install: brew install create-dmg${NC}"
        exit 1
    }

    echo "Creating DMG with create-dmg..."

    DMG_VOLUME="PRC Tray"
    BACKGROUND_IMG="/tmp/${APP_NAME}-dmg-bg.png"
    rm -f "${DMG_OUTPUT}"

    # Generate DMG background image (logo centered on light gradient)
    uv run python -c "
from PIL import Image, ImageDraw
logo = Image.open('${PROJECT_DIR}/assets/logo.png').convert('RGBA')
w, h = 660, 400
bg = Image.new('RGBA', (w, h), (245, 245, 245, 255))
draw = ImageDraw.Draw(bg)
for y in range(h):
    r = int(245 - 8 * (y / h))
    draw.line([(0, y), (w, y)], fill=(r, r, r + 3, 255))
logo_resized = logo.resize((128, 128), Image.LANCZOS)
bg.paste(logo_resized, (72, (h - 128) // 2), logo_resized)
bg.save('${BACKGROUND_IMG}')
"

    # Detach any stale mounts
    hdiutil detach "/Volumes/${DMG_VOLUME}" -quiet 2>/dev/null || true

    create-dmg \
        --volname "${DMG_VOLUME}" \
        --background "${BACKGROUND_IMG}" \
        --window-pos 200 120 \
        --window-size 660 400 \
        --icon-size 80 \
        --icon "PRC Tray.app" 200 208 \
        --hide-extension "PRC Tray.app" \
        --app-drop-link 460 208 \
        "${DMG_OUTPUT}" \
        "${APP_BUNDLE}"

    rm -f "${BACKGROUND_IMG}"

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
