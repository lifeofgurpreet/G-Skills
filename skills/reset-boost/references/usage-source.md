# Usage source contract

Auto-down needs to know when the provider's reset has landed. Reset Boost does
not call any provider API itself; you point it at something that already knows
each account's usage. Configure it under `usage` in the config file:

```json
{"usage": {"type": "url", "url": "https://usage.example.test/v1/accounts", "provider": "codex", "timeout": 30}}
{"usage": {"type": "command", "argv": ["/opt/tools/usage-report", "--json"], "timeout": 60}}
{"usage": {"type": "file", "path": "/var/lib/usage/latest.json"}}
```

- `url`: HTTP GET with `Accept: application/json`. No credentials are added;
  use a source that is reachable without them, or a `command` that handles
  its own authentication.
- `command`: an argv list (no shell). Exit 0 and JSON on stdout.
- `file`: a JSON file some other job keeps fresh.
- `provider` (optional): keep only rows whose `provider` field matches.

## Shape

```json
{
  "accounts": [
    {
      "id": "acct-team-a",
      "profile": "team-a",
      "windows": [
        {"key": "session", "used_percent": 12, "resets_at": "2026-10-15T03:00:00Z", "window_seconds": 18000},
        {"key": "weekly", "used_percent": 64, "resets_at": "2026-10-20T00:00:00Z", "window_seconds": 604800}
      ]
    }
  ]
}
```

A bare top-level list of accounts is also accepted. Per account:

| Field | Required | Meaning |
|---|---|---|
| `id` | yes (or `account_id`) | Stable key; the snapshot compares by it. |
| `profile` | for pins/ceilings | The profile name used by `--exclude`, `exclude_profiles` and per-account back-down. Must match how the account's sessions are identified (see configuration). |
| `windows[].key` | yes | Window name. `weekly` is preferred; otherwise the window with the largest `window_seconds`. |
| `windows[].used_percent` | yes | 0-100. A window without it is ignored. |
| `windows[].resets_at` | recommended | ISO 8601. A move later by more than an hour counts as "rolled over". |
| `windows[].window_seconds` | recommended | Chooses the main window when there is no `weekly`. |

Optional fields read when present: `display_name` or `email` (label only, kept
in the private state directory), `plan`, `provider`, `enabled: false`,
`usage_status: "policy_disabled"` or `execution_status: "disabled"` (excluded
from the quorum), and `observed_by_profile` / `fleet_cells[].profile` as
fallbacks for `profile`.

[`assets/usage.example.json`](../assets/usage.example.json) is a complete
synthetic example. To try the lifecycle without touching any machine, use a
config with `"hosts": {}`, `"usage": {"type": "file", "path": ...}` pointing at
a copy of it, and set `RESET_BOOST_CONFIG` and `RESET_BOOST_STATE_DIR` to a
scratch directory.

## Reset detection

For each account in the boost snapshot that has usage, is not disabled and is
not excluded, the reset counts as landed when the main window's `resets_at`
moved later by more than an hour, or `used_percent` fell by at least
`drop_points` (default 15) since the snapshot. When `quorum` (default 0.5) of
those accounts have landed, the whole fleet turns down. A read that fails,
times out or returns malformed JSON changes nothing; it is recorded as
`usage_error` and shown on the dashboard.
