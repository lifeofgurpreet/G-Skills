---
name: reset-boost
description: Turn every Codex coding-agent session in a fleet up for a provider usage reset (a stronger model, more reasoning, fast mode, or a named preset) and back down when the reset lands, from a local live control panel built around each session's own status line, with a credit guard, readback of launch configs and live Herdr/tmux/NTM sessions, and agent hand-off for what the buttons could not fix. Use when a usage-limit reset is coming or has landed, when the user says boost, crank up, turn down, done, or fast mode, when a fleet session will not switch, or when sessions disagree about model or effort.
license: MIT
compatibility: Python 3.11+ on the controlling machine and on each Linux/macOS host (3.10 runs the lifecycle, panel and dashboard but cannot read TOML). SSH aliases with key auth for remote hosts. Live switching needs Herdr or tmux and the Codex terminal UI. Windows hosts are config-only. No dependencies to install.
metadata:
  version: "0.2.0"
  author: lifeofgurpreet
---

# Reset Boost

Providers periodically reset usage limits. Quota that is about to be reset is
free to spend, so before a reset you turn every Codex session up (stronger
model, more reasoning, fast mode); once the reset lands you turn back down so
the fresh quota lasts. With many sessions across Herdr, tmux, NTM and several
machines, doing that by hand misses some. This skill does it as one lever, and
a live panel shows each session's own reading so a person can see it happened.

The tool is `scripts/reset_boost.py` in this folder (call it with its full
path, or link it onto `PATH`). Everything runs from the machine that drives
the estate; remote hosts receive the same source over SSH and install nothing.

## Authority

You are changing what someone else's accounts spend. Turning up raises cost,
so **propose the exact change and run it only on the user's instruction** (or
let them press the button in the panel). `observe`, `status`, `signals` and
`--dry-run` are always fine. Turning down (`done`) is the safe direction and is
always allowed. Never edit credentials, switch accounts, restart sessions,
read transcripts or send prompts to make a switch "work"; report what is held.

## The control panel

```sh
scripts/reset_boost.py serve --open      # http://127.0.0.1:8786/ ; the link with its key is in <state>/serve-url
scripts/install-watch.sh --serve         # keep it running (LaunchAgent or systemd user service)
```

Give the user the link from `serve-url`. The panel is built around **live
sessions**: every row is a running Codex session read from its own status line
(model, reasoning, fast mode, working/idle, the account's 5-hour and weekly
quota left, credits spent, folder), re-read about every minute. Rows flash
when a reading changes, so a human confirms a switch with their own eyes.

- **Live**: a one-line headline ("All systems go.", "Cranked up.", "2 things
  need you."), the session/host count and when they were read, and an alert
  for sessions whose account is out of quota or spending credits.
- **Set all to**: model, reasoning and Normal/Fast pills, then the round
  button, labelled with its effect ("Crank up 17"). The confirm says how many
  switch, how many are skipped and why. **Come back down**: when the reset
  lands, after a time, or only when I say. "Bring everything back down (N)"
  returns every session to the baseline.
- **Sessions card**: Sessions, Hosts and Models tabs, search and filters
  (working, idle, not on plan, out of quota). Select rows (or a whole host or
  model group) and the dock sets them when idle, interrupts and sets now
  (confirmed), or sends them back to the fleet setting. A row's menu retries
  one switch or asks an agent. Outside a boost a session without its own
  setting shows no plan: its model is the person's choice.
- **Right column**: a ring of live sessions by model family, host and model
  dots, the come-back-down rule as a quote, the accounts with the most
  sessions (usage bar, reset countdown), and the agent card.
- **Accounts**: usage and reset timing per account; lock an account to keep
  all its sessions at normal, even during a boost. **Models**: what is running
  and quick picks for "Set all to". **Settings**: what needs attention, the
  agent, auto-down tuning, the credit guard, read and re-apply intervals,
  theme and activity.

**Credit guard (on by default).** Nothing is ever turned *up* on a session
whose status line shows credits spent or no quota left (at or below the floor
set in Settings), or whose account is at 100% in the usage feed; such accounts
also keep baseline launch configs during a boost. Turning down is never
blocked. These sessions show as "skipped: out of quota".

**Agents handle what buttons can't.** Problems the buttons could not fix
(unreachable host, failed or held switch, still boosted after turn-down, usage
feed down) appear under Needs attention. In "Ask me" mode each offers "Send to
agent"; in "Send it" mode one that persists past the hand-over delay goes by
itself, rate limited. The agent gets a brief with settings-only evidence, the
plan, the allowed verbs and the rules (never turn anything up, no restarts, no
transcripts, interrupt only if allowed) and its FOUND / CHANGED / VERIFIED /
NEEDS HUMAN reply appears in the panel. The hand-off command is `agent.steps`
in the config; none is configured by default, and then the agent buttons are
off. See [configuration.md](references/configuration.md).

The panel binds `127.0.0.1`, needs its 0600 key and a local Host header, and
runs one fleet job at a time (a background read waits for a click, never the
reverse). Its loop reads sessions every minute and re-applies the plan every
10 minutes; while it runs, the timer-driven `watch` skips itself.

## The lever and auto-down

```sh
reset_boost.py presets                                   # what you can turn up to
reset_boost.py boost --preset astra-ultra-fast --dry-run # show the plan, change nothing
reset_boost.py boost --preset astra-ultra-fast --note "reset tonight"
reset_boost.py boost --preset sol-high --until 6h --ceiling 90
reset_boost.py boost astra xhigh --tier fast --exclude pro-1
reset_boost.py status --refresh                          # phase, targets, per-account reset progress
reset_boost.py done                                      # turn everything back down now
```

`boost` snapshots usage, rewrites launch configs on every host, pins excluded,
locked and out-of-quota accounts at the baseline, and switches idle live
sessions. Re-running it retunes an active boost and keeps the original
snapshot. `done` returns to the config's `baseline` preset (default `normal`,
fast mode off) and clears per-session settings. `--tier fast` is Codex fast
mode (service tier `priority`).

Each tick turns the whole fleet down when, on at least `quorum` (default 50%)
of counted accounts, the main usage window rolled over or usage fell by
`drop_points` (default 15). `--until 6h|90m|2d|ISO` adds a deadline;
`--ceiling 90` backs one account down by itself; `--no-auto-down` leaves only
`done` and `--until`. A failed usage read never changes a model: it pauses
detection and says so. After the end, ticks keep re-applying the baseline
("cooling") until every reachable live session reads back at it or
`cooling_hours` (default 12) pass. Without the panel, install the tick with
`scripts/install-watch.sh` (every 15 minutes).

## Agent verbs

The panel's buttons call the same code. Use these when working a problem:

```sh
reset_boost.py signals --json                  # what needs fixing, worst first
reset_boost.py pane build-1 %3 [--interrupt]   # retry one session at its planned target
reset_boost.py converge --hosts build-1        # re-apply the current plan on one host
reset_boost.py channel team-a pin              # follow | pin | <preset> | <model> <effort> [--tier fast]
reset_boost.py rules --ceiling 90 --until 6h   # tune auto-down during a boost
reset_boost.py agent "why won't build-1 switch?"  # hand a request to the configured agent
```

`--interrupt` cancels the running turn before switching and is only for the
user's instruction or a brief that allows it. A solo channel or session
setting above the fleet target is turning up, so it needs the user's
instruction too.

## Observe and per-session settings

```sh
reset_boost.py observe [--hosts build-1] [--json]   # every live session's status line; changes nothing
reset_boost.py session astra 'build-1|%7' 'laptop|w2:p1' --effort high --tier fast
reset_boost.py session follow 'build-1|%7'          # back to the fleet setting
```

Sessions are `HOST|PANE` as `observe` prints them. A session setting wins over
its account's and the fleet's until `follow` or a turn-down clears it. A busy
session is held; during a boost or cool-down a later tick switches it once
idle, otherwise retry it (`pane`) or pass `--interrupt`.

## Audit, set and dashboard

```sh
reset_boost.py audit                                  # read-only against `normal`
reset_boost.py set --preset normal --apply --live     # write + switch idle sessions
reset_boost.py set luna high --hosts laptop,build-1 --apply
reset_boost.py dashboard --open                       # static HTML snapshot for offline viewing
```

Without `--apply`, `set` previews. Exit codes: `0` everything inspected
matches, `1` an error or unreachable host, `2` a pending change or a live
session not at target.

## Setup

Without a config only this machine is managed. For several machines, a usage
source, exclusions, the credit guard, the agent hand-off or the optional CAAM
account-manager layouts, read [configuration.md](references/configuration.md)
and write `~/.config/reset-boost/config.json` (resolved from the account's real
home, not `$HOME`). The usage contract is in
[usage-source.md](references/usage-source.md). Read
[live-sessions.md](references/live-sessions.md) before changing how sessions
are found, read or switched.

## What is and is not verified

- Launch configs are rewritten with a timestamped sidecar backup and read back.
- A live session counts as switched only on a fresh status-line readback of
  model, reasoning and (when the target sets it) fast mode. Busy sessions,
  drafts and unrecognized composers are held, never interrupted unless
  explicitly allowed. While any account is pinned or solo, a session whose
  account cannot be identified is held.
- Fast mode is toggled live with `/fast` and read back from the status line.
  The status-line fields (quota left, credits, run state, folder) appear only
  when the user's Codex status line shows them; missing fields read as
  unknown, never as "has quota".
- **Unverified or unsupported:** desktop-app tasks (always reported
  unverified), Windows terminals (config only), and any harness without a
  readable status line. Never report those as switched.
- The agent rules are instructions in a brief, not a sandbox; the agent has
  whatever permissions its command runs with.
- Tests are provider-free (synthetic status lines, a fake fleet and a fake
  agent command). The status-line parsing follows the Codex terminal UI as
  observed on the author's machines; this draft has not been qualified on
  another person's estate.
