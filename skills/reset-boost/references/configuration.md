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

## State

`~/.local/state/reset-boost/` (override `RESET_BOOST_STATE_DIR`) holds
`boost.json` (phase and targets), `boost-events.jsonl` (timeline), one JSON
report per run, `usage-latest.json` and the dashboard. They contain settings,
account labels and verification outcomes, never terminal conversations or
credentials. Keep the directory private.

## Presets

`scripts/presets.json` is the catalog (`model`, `effort`, `tier`,
`description`). Presets are convenience names, not provider capability checks;
edit them when a provider renames models. Any model ID and effort
(`low medium high xhigh max ultra`) can also be given directly, with
`--tier default|fast|ultrafast|flex|priority`.

## Launch guard

Launchers that pass explicit `-m`/`--model` or `-c model_reasoning_effort=`
flags (some NTM templates, restores, resumes) override config defaults.
`scripts/model-policy-guard.py -- codex ARGS...` rewrites those flags to
`RESET_BOOST_MODEL` / `RESET_BOOST_REASONING_EFFORT` (invalid values fall back
to `gpt-6.1-sol` / `medium`) and leaves everything after `--` untouched. It
governs only processes launched through it.
