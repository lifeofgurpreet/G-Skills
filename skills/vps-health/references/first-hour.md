# First-hour recipes for the executing agent

The coding agent should perform these steps, not ask the user to type them. Prefer the managed [agent workflow](agent-workflow.md); these foreground recipes remain useful for demonstrations, diagnosis and unsupported lifecycle platforms. Start with a demonstration, choose an authorized collection route, verify it, and leave a usable handoff. Commands are relative to the installed skill directory. Python 3.10+ is required.

## See the workflow without connecting a server

```bash
python3 scripts/vps_health.py bootstrap --mode demo --workspace /tmp/vps-demo
python3 scripts/vps_health.py serve --workspace /tmp/vps-demo
```

The printed loopback URL opens synthetic stable, contended and missing-data examples. Try the linked charts, interval ribbon, Attention inbox, Setup routes and provider guide. The demonstration does not measure your machine. Ctrl-C stops the viewer.

## Choose the real route

For one authorized Linux VPS, run the local route on that VPS, not on a different laptop. For an existing monitoring stack, use a private expected-node profile and explicit final Prometheus/Loki endpoints. Windows and macOS can use offline demonstrations or an existing monitoring source; Linux counters cannot be collected locally there.

Bootstrap creates configuration only. Doctor reads local configuration, chart integrity, database state and evidence readiness. It does not inspect the whole computer, make a remote request or repair anything. Exit 1 means findings or unavailable evidence, not a broken command.

```bash
python3 scripts/vps_health.py doctor --workspace /private/vps-health
python3 scripts/vps_health.py brief --workspace /private/vps-health
```

Replace the example path with the actual private workspace. Choose one explicitly approved collection process. A local baseline needs a second tick before it represents elapsed CPU time. Watch runs in the foreground; a systemd timer is generated as files for separate review and installation. Do not run both against the same workspace. See [bootstrap recipes](bootstrap.md) for the exact commands, credential handling and stopping instructions.

## Check what really happened

Inspect the latest capture, measured hours, coverage and HOLD reasons. A refreshing viewer is not a running collector. Do not convert ten seconds of observation into a day of proof. A new host, exporter or collector version is a comparison boundary; preserve earlier workspaces rather than overwriting them.

Finish by giving the user the chosen mode, exact private path and commands, the active process or scheduler, current evidence state, next useful check and stop procedure. Summary exports are useful reports, not substitutes for the retained private database. The [operator playbook](operator-playbook.md) covers the daily loop and failure recovery.
