# Reset Boost

**One skill in the [G-Skills collection](https://github.com/lifeofgurpreet/G-Skills).**
Give this folder to your coding agent to run a fleet of Codex accounts through
a provider usage reset: turn every account up while quota that is about to be
reset is free to spend, and back down once the reset lands, manually (`done`)
or automatically from your usage data. A self-contained HTML dashboard shows
any session that did not switch, or fast mode left on.

Read [SKILL.md](SKILL.md) for the agent workflow. Requirements: Python 3.11+
(3.10 runs the lifecycle and dashboard only), SSH aliases for remote hosts,
and Herdr or tmux for live switching. Nothing to install on remote hosts.

## What it does

- `boost` / `done`: one lever across launch configs (Codex `config.toml`
  model, reasoning effort and service tier; NTM defaults and templates) and
  idle live Herdr/tmux sessions, with footer readback and per-account pins.
- `watch` (a 15-minute LaunchAgent or systemd user timer): turns down when the
  reset lands on a quorum of accounts, at a deadline, or per account at a
  usage ceiling, then keeps converging until every reachable session reads
  back at the baseline.
- `dashboard`: phase, targets, per-account usage, every host and session, and
  a "needs attention" list.
- `audit` / `set`: one-off read-only check or change of the whole fleet.

It never sends an inference prompt, reads a transcript, restarts a session or
touches credentials. Busy panes and unsent drafts are held, not interrupted.
CAAM account-manager layouts are supported when present and ignored otherwise.

## Preview status

Draft 0.1.0. Ported from a working private deployment; the tests are
provider-free and synthetic. It has not been qualified on another person's
estate. Desktop apps and Windows terminals are not switched, and service tier
changes reach running sessions only at their next launch.
