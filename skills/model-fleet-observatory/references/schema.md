# Snapshot schema

The dashboard consumes one JSON document with schema
`g-skills.model-fleet-observatory.snapshot.v1`:

```json
{
  "schema": "g-skills.model-fleet-observatory.snapshot.v1",
  "generated_at": "2026-01-01T00:00:00+00:00",
  "refresh_interval_s": 600,
  "boxes": [
    {
      "id": "box-a",
      "label": "Example box",
      "status": "ok",
      "source": {"kind": "adapter", "status": "observed"},
      "sessions": [
        {
          "id": "session-1",
          "account": "pro-1",
          "profile": "default",
          "model": "gpt-6.1-sol",
          "reasoning": "high",
          "backend": "codex",
          "status": "observed",
          "evidence": {"kind": "process-argv", "checked_at": "..."}
        }
      ]
    }
  ]
}
```

`account`, `profile`, `model` and `reasoning` are optional evidence fields. An
empty value is rendered as `UNKNOWN`, never inferred from an email, token path
or provider subscription. `status` is one of `observed`, `stale`, `error` or
`unknown`; a box `status` of `error` or `unknown` remains visible in the table.

The collector derives `session_count` from rows and `account_count` from
non-empty account/profile aliases. These counters are observations in the
selected scope, not billing or quota totals.
