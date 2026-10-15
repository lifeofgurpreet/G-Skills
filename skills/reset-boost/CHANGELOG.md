# Reset Boost changelog

## 0.2.1 — Preview

First releasable preview. The panel now plans accounts with no quota left at
the baseline they actually stay at, instead of showing the boost target and
then "skipped" (regression test added). Live switching follows Codex's new
"Advanced Reasoning" screen for Max and Ultra (before this every switch to
Ultra failed and left the picker open), and tmux panes shorter than 16 rows
are zoomed while the picker is used and unzoomed afterwards. Already in 0.2.0 and now covered by
this release: the panel's credit-guard switch and floor override the config
default when changes are applied, and on phones the sessions table drops the
account and quota columns so the state column is not clipped.

## 0.2.0 — Draft

Live control panel, session first. `serve` runs a local web UI and JSON/SSE
API (standard library, no build; binds 127.0.0.1, 0600 key, local Host check,
one fleet job at a time) whose main list is every live Codex session read from
its own status line: model, reasoning, fast mode, run state, 5-hour and weekly
quota left, credits, folder, re-read about every minute, with rows that flash
on a real change. "Set all to" with one round button, a come-back-down choice,
Sessions/Hosts/Models tabs with a bulk-actions dock, per-account lock,
Accounts/Models/Settings views and agent hand-off. The page is built on the
collection's operator-ui stylesheet (`assets/operator-ui.css`, identical to
`docs/design/operator-ui.css`).

Engine: status-line telemetry parsing (truncated effort accepted when
unambiguous; the "Ask Codex to do anything" placeholder counts as an empty
composer); fast mode is service tier `priority`, toggled live with `/fast` and
read back (`--tier fast`; `ultrafast` removed); a credit guard that never turns
up a session on credits or out of quota and keeps out-of-quota accounts at the
baseline (`held_credits`); per-session settings (`session`) that override the
account and fleet; read-only `observe`; subprocesses via `posix_spawn`
(absolute executable, `close_fds=False`) because `fork()` from the threaded
panel hung on macOS; the panel's LaunchAgent runs as `ProcessType` Standard.
Other new verbs: `signals`, `pane`, `converge`, `channel`, `rules`, `agent`.
Optional agent hand-off (`agent.steps`, none by default) with an autopilot
(off/ask/send, delay, hourly budget). `install-watch.sh --serve` keeps the
panel running; the timer tick skips itself while the panel's loop is alive.
Panel, telemetry, credit-guard and session tests; the cold exported-folder
check starts the panel and fetches the page, stylesheet and state.

## 0.1.0 — Draft

First public draft. `boost` / `done` / `watch` / `status` / `dashboard`
lifecycle with usage-driven auto-down (quorum, deadline, per-account ceiling)
and cooling convergence; `audit` / `set` / `presets` for one-off policy;
Codex, NTM and optional CAAM config rewriting with backups and readback; live
Herdr/tmux switching through the `/model` picker with footer readback; a
config-only Windows worker; a launch-flag guard; a LaunchAgent/systemd timer
installer; and a self-contained HTML dashboard. Provider-free tests and a cold
exported-folder check.
