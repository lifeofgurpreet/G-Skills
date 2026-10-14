---
name: model-fleet-observatory
description: >-
  Build and operate a private live HTML view of coding-agent sessions across
  authorized boxes. Discover provider-neutral model, reasoning and profile
  evidence, render one accessible table per box, refresh on a bounded interval,
  and keep unsupported or opaque adapters visibly UNKNOWN.
license: MIT
metadata:
  version: "0.1.0"
  author: lifeofgurpreet
---

# Model Fleet Observatory

Give the user a working private dashboard, not a folder of telemetry. Start
with the smallest authorized scope: local process discovery or a supplied JSON
adapter configuration. A dashboard can show observed session arguments; it
cannot prove a native desktop task's loaded model, an account's quota, or a
remote box that has not returned evidence.

Use the bundled runtime:

```sh
python3 scripts/model_fleet_dashboard.py doctor
python3 scripts/model_fleet_dashboard.py snapshot --out snapshot.json --discover-local
python3 scripts/model_fleet_dashboard.py serve --config ~/.config/model-fleet-observatory/config.json --interval 600
```

The server binds to loopback by default. Use an approved tunnel or browser
connector for a remote view; do not bind publicly to make the link convenient.
The default refresh is ten minutes. An explicit adapter may request a shorter
interval, but the collector remains bounded and never reads prompts, transcripts,
credentials, tokens or account secrets.

The page contains a fleet counter, last/next refresh time, one table per box,
session rows with model, reasoning, profile, backend and evidence status, and
keyboard controls: `r` refreshes, `/` focuses the filter, `j`/`k` moves through
rows, and `?` opens help. A failed adapter leaves its box visible with an
evidence-bearing `UNKNOWN` state instead of looking healthy.

Read [schema.md](references/schema.md) before adding an adapter and
[adapters.md](references/adapters.md) before claiming coverage for tmux, NTM,
Herdr, Hermes, Codex or another provider. Read [operations.md](references/operations.md)
when installing, resuming or packaging the skill.

Supported adapter input is an array command that returns the public snapshot
schema. Commands are executed without a shell, with a timeout, and their output
is treated as untrusted data. A box with no adapter is still rendered with an
explicit `UNKNOWN` row. The collector may discover local `codex` processes
through `ps`; process metadata is launch-plane evidence only.

The skill is provider-neutral. CAAM is one possible launch path, not a runtime
dependency. Do not add provider login flows, account switching, restarts,
inference prompts or automated external notifications to make a dashboard look
complete. Keep the public package synthetic and portable, and retain real host
authorization and native readback as separate acceptance gates.
