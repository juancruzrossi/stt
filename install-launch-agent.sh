#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
PLIST="$HOME/Library/LaunchAgents/com.local.stt.plist"

mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.local.stt</string>
  <key>ProgramArguments</key>
  <array>
    <string>$ROOT_DIR/stt</string>
    <string>listen</string>
    <string>--model</string>
    <string>small</string>
    <string>--language</string>
    <string>es</string>
    <string>--mode</string>
    <string>double-tap</string>
    <string>--tap-key</string>
    <string>cmd</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$ROOT_DIR/stt.log</string>
  <key>StandardErrorPath</key>
  <string>$ROOT_DIR/stt.err.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST" >/dev/null 2>&1 || true
launchctl load "$PLIST"

echo "LaunchAgent installed: $PLIST"
echo "Logs:"
echo "  $ROOT_DIR/stt.log"
echo "  $ROOT_DIR/stt.err.log"
