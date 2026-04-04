#!/bin/bash
# Creates "IDJLM Pro.app" — a clickable macOS app launcher.
# Run this once on your Mac from inside the idlm-pro folder:
#   bash create-mac-app.sh
# Then drag "IDJLM Pro.app" to your Dock or Applications folder.

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="IDJLM Pro"
APP_PATH="$PROJECT_DIR/$APP_NAME.app"
CONTENTS="$APP_PATH/Contents"
MACOS="$CONTENTS/MacOS"

echo "Building $APP_NAME.app..."

# Clean any previous build
rm -rf "$APP_PATH"
mkdir -p "$MACOS"
mkdir -p "$CONTENTS/Resources"

# ── Info.plist ────────────────────────────────────────────────────────────────
cat > "$CONTENTS/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>         <string>IDJLM Pro</string>
  <key>CFBundleDisplayName</key>  <string>IDJLM Pro</string>
  <key>CFBundleIdentifier</key>   <string>com.poy.idlm-pro</string>
  <key>CFBundleVersion</key>      <string>1.0</string>
  <key>CFBundleExecutable</key>   <string>launcher</string>
  <key>CFBundlePackageType</key>  <string>APPL</string>
  <key>LSMinimumSystemVersion</key> <string>12.0</string>
  <key>LSUIElement</key>          <false/>
</dict>
</plist>
PLIST

# ── Launcher script ───────────────────────────────────────────────────────────
# PROJECT_DIR is embedded at creation time so the .app works from anywhere.
cat > "$MACOS/launcher" << LAUNCHER
#!/bin/bash
PROJECT_DIR="$PROJECT_DIR"
PORT=5050

# Load port override from .env if present
if [ -f "\$PROJECT_DIR/.env" ]; then
  OVERRIDE=\$(grep -E '^FLASK_PORT=' "\$PROJECT_DIR/.env" | cut -d= -f2 | tr -d '[:space:]')
  [ -n "\$OVERRIDE" ] && PORT=\$OVERRIDE
fi

URL="http://localhost:\$PORT"

# If server already running, just open browser
if curl -s --max-time 1 "\$URL" > /dev/null 2>&1; then
  open "\$URL"
  exit 0
fi

# Launch server in a Terminal window
osascript << EOF
tell application "Terminal"
  activate
  set newTab to do script "cd '\$PROJECT_DIR' && ./start.sh"
  set custom title of front window to "IDJLM Pro"
end tell
EOF

# Wait for server to become ready (up to 30s)
echo "Waiting for server..."
for i in \$(seq 1 30); do
  if curl -s --max-time 1 "\$URL" > /dev/null 2>&1; then
    break
  fi
  sleep 1
done

open "\$URL"
LAUNCHER

chmod +x "$MACOS/launcher"

echo ""
echo "✓ Created: $APP_PATH"
echo ""
echo "Next steps:"
echo "  • Double-click '$APP_NAME.app' to launch"
echo "  • Or drag it to your Dock / Applications folder"
echo ""
echo "The app remembers this folder location — don't move idlm-pro/ after creating the .app."
