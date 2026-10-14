#!/usr/bin/env bash
# Install (or remove) the reset-boost watch tick: every 15 minutes it reads
# usage, turns a boost down when the reset lands, converges sessions that were
# busy, and rewrites the dashboard. macOS uses a LaunchAgent; Linux a systemd
# user timer. Run one watcher per estate, on the machine that drives it.
set -euo pipefail

usage() { echo "usage: $0 [--interval SECONDS] [--python PATH] [--uninstall]" >&2; exit 2; }

interval=900
python=''
uninstall=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --interval) interval="${2:?}"; shift 2 ;;
    --python) python="${2:?}"; shift 2 ;;
    --uninstall) uninstall=1; shift ;;
    *) usage ;;
  esac
done
case "$interval" in ''|*[!0-9]*) usage ;; esac

script="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)/reset_boost.py"
real_home="$(python3 -c 'import os, pwd; print(pwd.getpwuid(os.getuid()).pw_dir)')"
state="$real_home/.local/state/reset-boost"
label='io.github.reset-boost.watch'

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

if [ "$(uname)" = Darwin ]; then
  plist="$real_home/Library/LaunchAgents/$label.plist"
  launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
  if [ "$uninstall" -eq 1 ]; then
    [ -e "$plist" ] && mv "$plist" "$state/$label.plist.removed-$(date -u +%Y%m%dT%H%M%SZ)"
    echo "removed $label"
    exit 0
  fi
  cat >"$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key><array>
    <string>$python</string><string>$script</string><string>watch</string><string>--quiet</string>
  </array>
  <key>StartInterval</key><integer>$interval</integer>
  <key>RunAtLoad</key><true/>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>$state/watch.log</string>
  <key>StandardErrorPath</key><string>$state/watch.log</string>
</dict></plist>
EOF
  plutil -lint "$plist" >/dev/null
  launchctl bootstrap "gui/$(id -u)" "$plist"
  echo "installed $plist (every ${interval}s, $python)"
else
  units="$real_home/.config/systemd/user"
  if [ "$uninstall" -eq 1 ]; then
    systemctl --user disable --now reset-boost-watch.timer 2>/dev/null || true
    for unit in reset-boost-watch.service reset-boost-watch.timer; do
      [ -e "$units/$unit" ] && mv "$units/$unit" "$state/$unit.removed-$(date -u +%Y%m%dT%H%M%SZ)"
    done
    systemctl --user daemon-reload
    echo "removed reset-boost-watch.timer"
    exit 0
  fi
  mkdir -p "$units"
  cat >"$units/reset-boost-watch.service" <<EOF
[Unit]
Description=reset-boost watch tick (boost auto-down, convergence, dashboard)

[Service]
Type=oneshot
ExecStart=$python $script watch --quiet
EOF
  cat >"$units/reset-boost-watch.timer" <<EOF
[Unit]
Description=reset-boost watch every ${interval}s

[Timer]
OnBootSec=2min
OnUnitActiveSec=${interval}s

[Install]
WantedBy=timers.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable --now reset-boost-watch.timer
  echo "installed reset-boost-watch.timer (every ${interval}s, $python)"
fi
