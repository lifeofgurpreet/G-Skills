# Adapter boundary

An adapter returns a JSON object with a `sessions` array for one box. Configure
it in `~/.config/model-fleet-observatory/config.json`:

```json
{
  "refresh_interval_s": 600,
  "boxes": [
    {
      "id": "example-box",
      "label": "Example box",
      "command": ["/usr/local/bin/my-model-observer", "--json"],
      "timeout_s": 8
    }
  ]
}
```

The command is an argv array, never a shell string. Its stdout is parsed as
untrusted JSON. It may return either `{"sessions": [...]}` or a full box object.
stderr is retained only as a short diagnostic; it is never shown as a prompt or
credential source. A timeout, invalid JSON or non-zero exit produces a visible
`UNKNOWN` box.

The skill treats these surfaces as separate adapters:

| Surface | Safe evidence | Live claim |
| --- | --- | --- |
| Codex process argv | model/config flags and PID | launch-plane only |
| tmux or Herdr wrapper | wrapper-reported session rows | depends on wrapper readback |
| NTM template | configured model/effort | does not prove held sessions |
| Hermes | adapter output only | `UNKNOWN` without a read API |
| Native desktop task | native footer/API output | `UNKNOWN` until read back |

Do not make the dashboard execute provider login, switch accounts, restart a
session, inject a prompt or scrape private conversation content. A missing
adapter is an evidence gap, not permission to guess.
