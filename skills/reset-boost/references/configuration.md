# Configuration

The config lives at `~/.config/reset-boost/config.json`, where `~` is the
account's real home from the password database (agent sessions often redirect
`$HOME`). `RESET_BOOST_CONFIG` overrides the path. Without a file, only this
machine is managed. A full synthetic example is
[`assets/config.example.json`](../assets/config.example.json).

| Key | Default | Meaning |
|---|---|---|
| `hosts` | `{"local": {"type": "local"}}` | Machines to manage, by name. |
| `baseline` | `normal` | Preset that `done` and cooling return to. |
| `exclude_profiles` | `[]` | Profiles always pinned at the baseline during a boost. |
| `auto_down` | `{"reset": true, "quorum": 0.5, "drop_points": 15, "ceiling": null}` | Defaults for auto-down; `boost` flags override per boost. |
| `cooling_hours` | `12` | How long to keep re-applying the baseline after a boost ends. |
| `usage` | none | Usage source; see [usage-source.md](usage-source.md). |
| `dashboard` | `<state>/dashboard.html` | Where to write the HTML page. |
| `agent` | none | Hand-off command for the control panel's agent; see below. |
| `tick_minutes` | `10` | The panel loop's tick interval (adjustable live in the panel). |
| `usage_poll_seconds` | `60` | How often the panel re-reads the usage source. |
| `observe_seconds` | `60` | How often the panel re-reads every session's status line (adjustable live, 20-900). |
| `credit_guard` | `{"enabled": true, "floor": 0}` | Never turn up a session on credits or at/below `floor`% quota left; the panel's Settings switch overrides it. |

## Hosts

```json
"laptop":  {"type": "local"},
"build-1": {"type": "ssh", "ssh": "build-1", "sudo": true, "project_roots": ["/srv/projects"]},
"win-1":   {"type": "windows", "ssh": "win-1"}
```

- `local` runs in this process.
- `ssh` pipes this exact `reset_boost.py` source to `python3 -` on the host
  (BatchMode, 8 s connect timeout). Nothing is installed there. The host needs
  Python 3.11+. With `"sudo": true` the worker runs as root through
  `sudo -n` and covers every account under `/home`; otherwise only the SSH
  user's own home. Default is `false`.
- `windows` rewrites `%USERPROFILE%\.codex\config.toml` through PowerShell over
  SSH. Terminals are not enumerated or switched.
- `project_roots` adds absolute directories whose immediate children may hold
  `.codex/config.toml` or `.ntm/config.toml`. `~/projects/*` and `~/*` are
  always searched.

## What gets rewritten

In every home the worker covers:

- Codex: `~/.codex/config.toml` and per-project `.codex/config.toml`. `model`
  and `model_reasoning_effort` at the root and in `[profiles.*]`, and the root
  `service_tier` when the target names one. Everything else is preserved
  byte for byte.
- NTM: `~/.config/ntm/*.toml`, `~/.ntm/config.toml` and project `.ntm` files.
  `[models] default_codex`, `[models.codex]` entries, and the `-m` and
  `model_reasoning_effort=` arguments inside the `[agents] codex` template. A
  template without recognizable arguments is left alone and reported.

Each changed file keeps a sidecar backup `<name>.reset-boost-<UTC stamp>`; the
write preserves the inode, so symlinks, permissions and ownership survive. A
concurrent edit detected during the write is refused.

## Optional: CAAM account-manager layouts

[CAAM](https://github.com/Dicklesworthstone/coding_agent_account_manager) keeps
one shallow Codex home per account. When those directories exist, Reset Boost
also covers them; when they do not, nothing CAAM-specific happens.

- Per-account homes `~/orch-homes/codex-<profile>/.codex/config.toml` and
  `~/.local/share/caam/profiles/codex/<profile>/codex_home/config.toml` are
  rewritten, and the profile name comes from the path.
- If `~/.config/caam/` exists, `model-policy.env` receives
  `CAAM_CODEX_MODEL` / `CAAM_CODEX_REASONING_EFFORT`, and pinned accounts get
  `model-policy.d/<profile>.env` (regenerated each run, no backups).
- On Linux a Codex process's `CODEX_HOME` under `orch-homes/codex-<profile>`
  names the account of its tmux pane; a CAAM Herdr session map at
  `~/.local/state/caam/herdr-codex-session-profiles.json`, when present, names
  Herdr panes.

Profile names are compared in a filesystem-safe spelling: every character
outside `A-Za-z0-9._-` becomes `_` (so `pro-1@example.test` and
`pro-1_example.test` are the same profile).

## Control panel and agents

`reset_boost.py serve` binds `127.0.0.1:8786` (`--port`, `--port 0` for any
free port, `--no-loop` for the UI without ticks). Every API call needs the
token in `<state>/serve-token` (mode 0600, sent as `X-Reset-Boost-Token`) and a
`127.0.0.1`/`localhost` Host header, which keeps other local pages and
DNS-rebinding sites out. The full link with the token is written to
`<state>/serve-url` (0600). One fleet job runs at a time; a second button press
while a job runs is refused, except that a background session read gives way
to a click (the click waits up to 30 s for it). `GET /operator-ui.css` serves
the panel's stylesheet without the token; it holds no data. While the panel's loop is alive it writes
`<state>/serve.json` every second, and a `watch` tick from the timer skips
itself.

`agent` hands signals to a headless agent:

```json
"agent": {
  "steps": [["claude", "-p", "--output-format", "text"]],
  "timeout_minutes": 60,
  "autopilot": {"mode": "suggest", "after_minutes": 10, "max_per_hour": 3, "allow_interrupt": false,
                "codes": ["STILL_BOOSTED", "PANE_SWITCH_FAILED", "HOST_UNREACHABLE", "CONFIG_ERROR", "USAGE_DOWN"]}
}
```

`steps` is a list of argv lists run in order, without a shell; the run fails at
the first non-zero exit. `{name}` becomes the run name and `{brief}` the brief's
file path; a step without `{brief}` receives the brief on stdin (for example
`["claude", "-p"]` or `["codex", "exec", "-"]`). Each step's executable is
resolved to an absolute path and started with `posix_spawn`, never `fork`. The last step's output is shown in the panel. With no
`steps`, the agent buttons are disabled and autopilot does nothing.
`autopilot` sets defaults the panel can change: `mode` `off`, `suggest` (each
signal offers "Send to agent") or `auto` (a signal in `codes` that persists
past `after_minutes` is handed over by itself, at most `max_per_hour` runs and
never twice per hour for the same signal). `allow_interrupt` adds the
interrupt verb to the brief; otherwise the brief forbids interrupting turns.

The brief carries the signal, its settings-only evidence, the current plan,
the allowed verbs and the rules: never turn anything up, never restart
sessions or kill processes, never read transcripts, never change credentials,
SSH, networking or permissions, and stop with a NEEDS HUMAN line when a person
must act. Those are instructions to the agent, not a sandbox: run it with the
permissions you would give any agent on this machine.

## Credit guard

`credit_guard.enabled` (default `true`) blocks every change that turns a
session *up* (anything above the baseline except a pure reasoning step down on
the same model without fast mode) when the session's status line shows credits
spent or a quota window at or below `floor` percent left, or its account is at
100% in the usage feed. Out-of-quota accounts also keep baseline launch configs
during a boost. Turning down is never blocked. Such sessions report
`held_credits`.

## State

`~/.local/state/reset-boost/` (override `RESET_BOOST_STATE_DIR`) holds
`boost.json` (phase, targets, channels, per-session settings, credit guard,
autopilot settings), `sessions.json` (the latest status-line reading per
session),
`boost-events.jsonl` (timeline), one JSON report per run, `usage-latest.json`,
the dashboard, the panel's `serve-token`, `serve-url` and `serve.json`,
`signals-seen.json` (when each signal was first seen), `agent-runs.json` and
the agent briefs under `agent/`. They contain settings,
account labels and verification outcomes, never terminal conversations or
credentials (the panel token is the exception: it is the panel's own key). Keep the directory private.

## Presets

`scripts/presets.json` is the catalog (`model`, `effort`, `tier`,
`description`). Presets are convenience names, not provider capability checks;
edit them when a provider renames models. Any model ID and effort
(`low medium high xhigh max ultra`) can also be given directly, with
`--tier fast|default` (`fast` is Codex fast mode, service tier `priority`;
`flex` is passed through to launch configs only).

## Launch guard

Launchers that pass explicit `-m`/`--model` or `-c model_reasoning_effort=`
flags (some NTM templates, restores, resumes) override config defaults.
`scripts/model-policy-guard.py -- codex ARGS...` rewrites those flags to
`RESET_BOOST_MODEL` / `RESET_BOOST_REASONING_EFFORT` (invalid values fall back
to `gpt-6.1-sol` / `medium`) and leaves everything after `--` untouched. It
governs only processes launched through it.
