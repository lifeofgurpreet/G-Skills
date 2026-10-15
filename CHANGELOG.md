# Collection changes

## Independent skill ownership

G-Skills now discovers per-skill metadata, scaffolds unreleased drafts, dispatches owned validation and packages independently versioned skill archives. VPS Health code, documentation, maintenance and roadmap are scoped to that skill. Historical `v0.x` releases are retained unchanged; see [its changelog](skills/vps-health/CHANGELOG.md).


## Reversible installation source preview

Shared plan/apply/status tooling handles one reviewed selected archive without
executing its scripts. Prior installations are retained outside discovery; modified
or unowned folders, unsafe archive paths and stale approvals are refused. An
interrupted update has an explicit recovery path. Native-client qualification and
full real-artifact acceptance remain open; the independently released VPS Health
0.7.1 archive is not changed by this collection-only feature.


## Reset Boost draft skill

Add [Reset Boost](skills/reset-boost/README.md) 0.1.0 as a draft: one lever to
turn a coding-agent fleet up for a provider usage reset and back down, with
usage-driven auto-down, live-session readback and an HTML dashboard. It has its
own checks under `tools/skills/reset-boost/` and is not released; see
[its changelog](skills/reset-boost/CHANGELOG.md).


## Reset Boost 0.2.1 preview

[Reset Boost](skills/reset-boost/README.md) is marked ready for an independent
preview release: out-of-quota accounts show at the baseline they stay at,
the panel's credit-guard setting wins over the config, and switching to Max or
Ultra works through Codex's new Advanced Reasoning screen. See
[its changelog](skills/reset-boost/CHANGELOG.md).


## Reset Boost 0.2.0 draft and the operator-ui design kit

[Reset Boost](skills/reset-boost/README.md) gains a session-first live control
panel: every Codex session read from its own status line, one "Set all to"
lever, a credit guard that never turns up a session on paid credits or out of
quota, per-session settings, read-only `observe`, and optional agent hand-off.
Still a draft and unreleased; see [its changelog](skills/reset-boost/CHANGELOG.md).

The collection now has a shared look for operator pages:
[docs/design/operator-ui.css](docs/design/operator-ui.css) and
[its guide](docs/design/guide.md). Using it is optional; a skill that does
ships an identical copy, and `tools/validate.py` checks that every copy matches
and that pages linking it add no raw colours. VPS Health keeps its own design.
