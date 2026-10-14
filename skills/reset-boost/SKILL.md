---
name: reset-boost
description: Turn every Codex coding-agent account in a fleet up for a provider usage reset (a stronger model, more reasoning, fast mode, or a named preset) and back down when the reset lands, with readback of launch configs and live Herdr/tmux/NTM sessions and an HTML dashboard a human can check. Use when a usage-limit reset is coming or has landed, when the user says boost, crank up, turn down, done, or fast mode, or when sessions disagree about model or effort.
license: MIT
compatibility: Python 3.11+ on the controlling machine and on each Linux/macOS host (3.10 runs the lifecycle and dashboard but cannot read TOML). SSH aliases with key auth for remote hosts. Live switching needs Herdr or tmux and the Codex terminal UI. Windows hosts are config-only. No dependencies to install.
metadata:
  version: "0.1.0"
  author: lifeofgurpreet
---

# Reset Boost

Providers periodically reset usage limits. Quota that is about to be reset is
free to spend, so before a reset you turn every account up; once the reset has
landed you turn back down so the fresh quota lasts. With many accounts across
Herdr, tmux, NTM and several machines, doing that by hand misses sessions. This
skill is one lever with readback, plus a dashboard that shows whatever did not
follow.

The tool is `scripts/reset_boost.py` in this folder (call it with its full
path, or link it onto `PATH`). Everything below runs from the machine that
drives the estate.

## Authority

You are changing what someone else's accounts spend. Boosting raises cost, so
**propose the exact `boost` command and run it only on the user's instruction**.
`--dry-run` and `status` are always fine. `done` (turning down) is the safe
direction and is always allowed. Never edit credentials, switch accounts,
restart sessions or send prompts to make a switch "work"; report what is held.

## The lever

```sh
reset_boost.py presets                                   # what you can turn up to
reset_boost.py boost --preset astra-ultra-fast --dry-run # show the plan, change nothing
reset_boost.py boost --preset astra-ultra-fast --note "reset tonight"
reset_boost.py boost --preset sol-high --until 6h --ceiling 90
reset_boost.py boost astra xhigh --tier fast --exclude pro-1
reset_boost.py status --refresh                          # phase, targets, per-account reset progress
reset_boost.py done                                      # turn everything back down now
```

`boost` snapshots usage, applies the target to every configured host, pins
excluded accounts at the baseline, and switches idle live sessions. Re-running
`boost` with another target retunes an active boost and keeps the original
snapshot. The baseline is the config's `baseline` preset (default `normal`);
`done` returns to it, including `service_tier`.

## Auto-down

`boost` records each account's main usage window (weekly, else the longest).
Each `watch` tick turns the whole fleet down when, on at least `quorum`
(default 50%) of counted accounts, that window rolled over or usage fell by
`drop_points` (default 15). `--until 6h|90m|2d|ISO` adds a deadline;
`--ceiling 90` backs one account down by itself at 90%; `--no-auto-down`
leaves only `done` and `--until`. A failed usage read never changes a model:
it pauses detection and the dashboard says so. Without a usage source,
auto-down is deadline/manual only.

After the end, ticks keep re-applying the baseline ("cooling") until every
reachable live session reads back at the baseline or `cooling_hours`
(default 12) pass. Sessions that were busy at the switch converge on later
ticks. Install the tick once, on the controlling machine:

```sh
scripts/install-watch.sh                 # every 15 min: LaunchAgent or systemd user timer
scripts/install-watch.sh --uninstall
```

## Dashboard

`reset_boost.py dashboard --open` writes and opens a self-contained HTML page
(default `~/.local/state/reset-boost/dashboard.html`, refreshed by each tick
and reloading every minute). It shows the phase and targets, per-account usage
at boost time against now, every host's launch configs and live sessions, and
**Needs attention**: unreachable hosts, busy sessions still waiting, accounts
it could not identify, and in red any session still on the boost model after
`done`. Point the user at it after every boost and done.

## Audit and one-off set

```sh
reset_boost.py audit                                  # read-only against `normal`
reset_boost.py set --preset normal --apply --live     # write + switch idle sessions
reset_boost.py set luna high --hosts laptop,build-1 --apply
```

Without `--apply`, `set` previews. Exit codes: `0` everything inspected
matches, `1` an error or unreachable host, `2` a pending change or a live
session not at target.

## Setup

Without a config only this machine is managed. For several machines, a usage
source, exclusions or the optional CAAM account-manager layouts, read
[configuration.md](references/configuration.md) and write
`~/.config/reset-boost/config.json` (resolved from the account's real home, not
`$HOME`). The usage contract and a synthetic example are in
[usage-source.md](references/usage-source.md). Read
[live-sessions.md](references/live-sessions.md) before changing how panes are
found or switched.

## What is and is not verified

- Launch configs are rewritten with a timestamped sidecar backup and read back.
- Live sessions count as switched only on a fresh footer readback. Busy panes,
  drafts and unrecognized composers are held, never interrupted unless
  `--interrupt-current-turn` is given. While any account is pinned, a pane
  whose account cannot be identified is held.
- **Unverified or unsupported:** desktop-app tasks (always reported
  unverified), Windows terminals (Windows hosts get config changes only),
  `service_tier` on running sessions (it applies at the next launch), and any
  harness without a readable footer. Never report those as switched.
- Tests are provider-free; this draft has not been qualified on another
  person's estate.
