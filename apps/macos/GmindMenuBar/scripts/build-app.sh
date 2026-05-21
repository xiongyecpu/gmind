#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$(cd "$APP_DIR/../../.." && pwd)"
cd "$APP_DIR"

swift build -c release

BINARY="$APP_DIR/.build/release/GmindMenuBarApp"
OUTPUT_DIR="$APP_DIR/dist"
BUNDLE="$OUTPUT_DIR/gmind.app"
CONTENTS="$BUNDLE/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"
CLI_RESOURCES="$RESOURCES/cli"
PYINSTALLER_WORK="$APP_DIR/.build/pyinstaller"
CLI_ENTRY="$PYINSTALLER_WORK/gmind_cli_entry.py"
CLI_DIST="$PYINSTALLER_WORK/dist"
CLI_BUILD="$PYINSTALLER_WORK/build"

rm -rf "$BUNDLE"
mkdir -p "$MACOS" "$CLI_RESOURCES" "$PYINSTALLER_WORK"

cat > "$CLI_ENTRY" <<'PY'
from gmind.cli import main

raise SystemExit(main())
PY

uv run --with pyinstaller pyinstaller \
  --clean \
  --noconfirm \
  --onefile \
  --name gmind \
  --paths "$PROJECT_ROOT/src" \
  --add-data "$PROJECT_ROOT/src/gmind/schema.sql:gmind" \
  --specpath "$PYINSTALLER_WORK" \
  --distpath "$CLI_DIST" \
  --workpath "$CLI_BUILD" \
  "$CLI_ENTRY"

cp "$BINARY" "$MACOS/gmind"
cp "$CLI_DIST/gmind" "$CLI_RESOURCES/gmind"
cat > "$CONTENTS/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>gmind</string>
  <key>CFBundleIdentifier</key>
  <string>dev.gmind.menubar</string>
  <key>CFBundleName</key>
  <string>gmind</string>
  <key>CFBundleDisplayName</key>
  <string>gmind</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
  <key>LSUIElement</key>
  <true/>
</dict>
</plist>
PLIST

echo "Built $BUNDLE"
