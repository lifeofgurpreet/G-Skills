# Reset Boost

**One skill in the [G-Skills collection](https://github.com/lifeofgurpreet/G-Skills).**
Give this folder to your coding agent to run a fleet of Codex sessions through
a provider usage reset: turn every session up while quota that is about to be
reset is free to spend, and back down once the reset lands, manually (`done`)
or automatically from your usage data. A local live control panel shows every
session's own status line, so you can see each change land, and an agent you
configure picks up what its buttons could not fix.

Read [SKILL.md](SKILL.md) for the agent workflow. Requirements: Python 3.11+
(3.10 runs the lifecycle and dashboard only), SSH aliases for remote hosts,
and Herdr or tmux for live switching. Nothing to install on remote hosts.

## What it does

- `serve`: a local web panel (standard library, no build) built around live
  sessions. Each row is a Codex session read from its own status line (model,
  reasoning, fast mode, working or idle, quota left, credits, folder). "Set all
  to" plus one round button cranks every session up; "Bring everything back
  down" returns them; selected sessions get their own setting from a dock. A
  credit guard never turns up a session that spends paid credits or has no
  quota left. Problems the buttons could not fix can go to a headless agent
  (any command, e.g. `claude -p` or `codex exec -`) with a brief that forbids
  turning anything up, restarts and transcript reads. The page uses the
  collection's shared operator-ui stylesheet, shipped inside this folder.
- `boost` / `done`: one lever across launch configs (Codex `config.toml`
  model, reasoning effort and service tier; NTM defaults and templates) and
  idle live Herdr/tmux sessions, with status-line readback, `/fast` for fast
  mode, and per-account pins.
- `watch` (a 15-minute LaunchAgent or systemd user timer when the panel is not
  running): turns down when the reset lands on a quorum of accounts, at a
  deadline, or per account at a usage ceiling, then keeps converging until
  every reachable session reads back at the baseline.
- `observe` / `session`: read every session without changing anything; set
  chosen sessions, or send them back to the fleet setting.
- `signals` / `pane` / `converge` / `channel` / `rules` / `agent`: the
  verbs behind the panel's buttons, for agents and scripts.
- `dashboard`: a static HTML snapshot for offline viewing.
- `audit` / `set`: one-off read-only check or change of the whole fleet.

It never sends an inference prompt, reads a transcript, restarts a session or
touches credentials. Busy panes and unsent drafts are held, not interrupted.
CAAM account-manager layouts are supported when present and ignored otherwise.

## Preview status

Draft 0.2.0. Ported from a working private deployment; the tests are
provider-free and synthetic (status lines, a fake fleet and a fake agent
command). It has not been qualified on another person's estate. Desktop apps
and Windows terminals are not switched, and status-line telemetry depends on
the fields the user's Codex status line shows.
