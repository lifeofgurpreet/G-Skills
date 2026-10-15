#!/usr/bin/env bash
# Install (or remove) the reset-boost background services.
#   default  the watch tick every 15 minutes: read usage, auto-down, converge, render
#   --serve  the live control panel (web UI + loop + autopilot), kept alive; the watch
#            tick then skips itself while the panel's loop is running
# macOS uses LaunchAgents; Linux systemd user units. Run one estate driver per estate.
set -euo pipefail

usage() { echo "usage: $0 [--serve [--port N]] [--interval SECONDS] [--python PATH] [--uninstall]" >&2; exit 2; }

interval=900
port=8786
python=''
uninstall=0
mode=watch
while [ "$#" -gt 0 ]; do
  case "$1" in
    --serve) mode=serve; shift ;;
    --port) port="${2:?}"; shift 2 ;;
    --interval) interval="${2:?}"; shift 2 ;;
    --python) python="${2:?}"; shift 2 ;;
    --uninstall) uninstall=1; shift ;;
    *) usage ;;
  esac
done
case "$interval$port" in ''|*[!0-9]*) usage ;; esac

script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/reset_boost.py"
real_home="$(python3 -c 'import os, pwd; print(pwd.getpwuid(os.getuid()).pw_dir)')"
state="$real_home/.local/state/reset-boost"
label="io.github.reset-boost.$mode"
unit="reset-boost-$mode"
# Agents (claude, codex) usually live in ~/.local/bin or Homebrew.
path_env="$real_home/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

# tomllib needs Python 3.11+; launchd and systemd do not see a login shell's PATH.
if [ -z "$python" ]; then
  for candidate in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3 "$(command -v python3 || true)"; do
    [ -x "$candidate" ] || continue
    if "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' 2>/dev/null; then
      python="$candidate"
      break
    fi
  done
fi
[ "$uninstall" -eq 1 ] || [ -n "$python" ] || { echo "no Python 3.11+ found; pass --python" >&2; exit 1; }
mkdir -p "$state"

if [ "$mode" = serve ]; then
  args=("$script" serve --port "$port")
else
  args=("$script" watch --quiet)
fi

if [ "$(uname)" = Darwin ]; then
  plist="$real_home/Library/LaunchAgents/$label.plist"
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  if [ "$uninstall" -eq 1 ]; then
    [ -e "$plist" ] && mv "$plist" "$state/$label.plist.removed-$(date -u +%Y%m%dT%H%M%SZ)"
    echo "removed $label"
    exit 0
  fi
  {
    printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?>' \
      '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">' \
      '<plist version="1.0"><dict>' "  <key>Label</key><string>$label</string>" '  <key>ProgramArguments</key><array>' \
      "    <string>$python</string>"
    for arg in "${args[@]}"; do printf '    <string>%s</string>\n' "$arg"; done
    printf '%s\n' '  </array>' '  <key>EnvironmentVariables</key><dict>' "    <key>PATH</key><string>$path_env</string>" '  </dict>'
    if [ "$mode" = serve ]; then
      printf '%s\n' '  <key>KeepAlive</key><true/>' '  <key>ThrottleInterval</key><integer>30</integer>'
    else
      printf '%s\n' "  <key>StartInterval</key><integer>$interval</integer>"
    fi
    # The panel answers clicks, so it runs at normal priority: under heavy load macOS starves a
    # Background job so badly it may not even finish starting. The watch tick stays Background.
    if [ "$mode" = serve ]; then process_type=Standard; else process_type=Background; fi
    printf '%s\n' '  <key>RunAtLoad</key><true/>' "  <key>ProcessType</key><string>$process_type</string>" \
      "  <key>StandardOutPath</key><string>$state/$mode.log</string>" "  <key>StandardErrorPath</key><string>$state/$mode.log</string>" \
      '</dict></plist>'
  } >"$plist"
  plutil -lint "$plist" >/dev/null
  launchctl bootstrap "gui/$(id -u)" "$plist"
  echo "installed $plist ($mode, $python)"
else
  units="$real_home/.config/systemd/user"
  if [ "$uninstall" -eq 1 ]; then
    systemctl --user disable --now "$unit.timer" "$unit.service" 2>/dev/null || true
    for file in "$unit.service" "$unit.timer"; do
      [ -e "$units/$file" ] && mv "$units/$file" "$state/$file.removed-$(date -u +%Y%m%dT%H%M%SZ)"
    done
    systemctl --user daemon-reload
    echo "removed $unit"
    exit 0
  fi
  mkdir -p "$units"
  command_line="$python"
  for arg in "${args[@]}"; do command_line="$command_line $arg"; done
  if [ "$mode" = serve ]; then
    printf '%s\n' '[Unit]' 'Description=reset-boost control panel' '' '[Service]' "Environment=PATH=$path_env" \
      "ExecStart=$command_line" 'Restart=always' 'RestartSec=30' '' '[Install]' 'WantedBy=default.target' >"$units/$unit.service"
    systemctl --user daemon-reload
    systemctl --user enable --now "$unit.service"
  else
    printf '%s\n' '[Unit]' 'Description=reset-boost watch tick' '' '[Service]' 'Type=oneshot' "Environment=PATH=$path_env" \
      "ExecStart=$command_line" >"$units/$unit.service"
    printf '%s\n' '[Unit]' "Description=reset-boost watch every ${interval}s" '' '[Timer]' 'OnBootSec=2min' "OnUnitActiveSec=${interval}s" \
      '' '[Install]' 'WantedBy=timers.target' >"$units/$unit.timer"
    systemctl --user daemon-reload
    systemctl --user enable --now "$unit.timer"
  fi
  echo "installed $unit ($mode, $python)"
fi
if [ "$mode" = serve ]; then
  echo "panel: $(cat "$state/serve-url" 2>/dev/null || echo "starts in a moment; the URL is written to $state/serve-url")"
fi
