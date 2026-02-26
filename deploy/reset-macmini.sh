#!/bin/bash
# Reset openclaw configuration files on Mac Mini for clean rebuild.
# Run this script with: sudo bash reset-macmini.sh

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root (use sudo)."
    exit 1
fi

echo "Stopping launchd services..."
launchctl unload /Library/LaunchDaemons/com.alhazen.litellm.plist 2>/dev/null || true
launchctl unload /Library/LaunchDaemons/com.alhazen.mcp.plist 2>/dev/null || true
launchctl unload /Library/LaunchDaemons/com.alhazen.openclaw.plist 2>/dev/null || true

echo "Removing launchd plists..."
rm -f /Library/LaunchDaemons/com.alhazen.litellm.plist
rm -f /Library/LaunchDaemons/com.alhazen.mcp.plist
rm -f /Library/LaunchDaemons/com.alhazen.openclaw.plist

echo "Removing openclaw config files..."
rm -f /Users/openclaw/secrets.env
rm -f /Users/openclaw/litellm-config.yaml
rm -f /Users/openclaw/litellm.env
rm -rf /Users/openclaw/.openclaw
rm -rf /Users/openclaw/logs
rm -rf /Users/openclaw/workspace

echo "Remaining files in /Users/openclaw:"
ls -la /Users/openclaw/

echo "Done. Ready for fresh deployment."
