#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "=== PRC Tray — Build ==="
echo ""

# Ensure uv is available
if ! command -v uv &>/dev/null; then
    echo "Error: uv is required. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Install pyinstaller into the venv if not present
if ! uv run python -c "import PyInstaller" 2>/dev/null; then
    echo "Adding PyInstaller..."
    uv add --dev pyinstaller
fi

# Clean previous builds
rm -rf build/ dist/

echo "Building..."
uv run pyinstaller daemon.spec --noconfirm --clean

echo ""
echo "=== Build complete ==="
echo "Output: dist/prc-tray/"

# Platform-specific notes
case "$(uname -s)" in
    Darwin*)
        echo ""
        echo "macOS notes:"
        echo "  To code-sign:  codesign --force --deep --sign 'Developer ID Application: ...' dist/prc-tray/prc-tray"
        echo "  To notarize:   xcrun notarytool submit dist/prc-tray.zip --apple-id ... --team-id ..."
        echo "  Quick bypass:  xattr -cr dist/prc-tray/"
        ;;
    Linux*)
        echo ""
        echo "Linux: Ready to distribute. No signing needed."
        ;;
    MINGW*|MSYS*|CYGWIN*)
        echo ""
        echo "Windows notes:"
        echo "  To sign: signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /n 'Your Name' dist/prc-tray/prc-tray.exe"
        echo "  Without signing: Users will see SmartScreen warning (click 'More info' → 'Run anyway')"
        ;;
esac
