#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
py="$(command -v python3)"
action="${1:-install}"
label="com.token-lab.weekly-report"
plist="$HOME/Library/LaunchAgents/$label.plist"

if [ "$(uname)" != "Darwin" ]; then
  line="0 9 * * 1 \"$py\" \"$here/lab.py\" report --save >/dev/null 2>&1"
  if [ "$action" = "remove" ]; then
    crontab -l 2>/dev/null | grep -vF "$here/lab.py" | crontab -
    echo "removed the cron entry"
  else
    { crontab -l 2>/dev/null | grep -vF "$here/lab.py"; echo "$line"; } | crontab -
    echo "cron: Mondays 09:00 -> ~/.claude/token-lab/reports/"
  fi
  exit 0
fi

if [ "$action" = "remove" ]; then
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  rm -f "$plist"
  echo "removed $label"
  exit 0
fi

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/.claude/token-lab/reports"
cat >"$plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array><string>$py</string><string>$here/lab.py</string><string>report</string><string>--save</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardErrorPath</key><string>$HOME/.claude/token-lab/reports/schedule.err</string>
</dict>
</plist>
PLIST
launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$plist"
echo "launchd: Mondays 09:00 -> ~/.claude/token-lab/reports/ (runs on wake if the Mac was asleep)"
