# Operating the skill

## Installation

Clone the repository and explicitly ask the agent to read `skills/vps-health/SKILL.md`. This works without assuming a vendor-specific discovery directory. To use an agent's native skill menu, copy or link the entire `vps-health` folder into that agent's documented skill root. Do not place only the Markdown file there. Do not modify a package-managed installed copy while another agent is using it.

This is a standard skill directory, not an MCP server or an automatic permission grant. Consult the [Agent Skills specification](https://agentskills.io/specification) and your client documentation. Automatic invocation is not qualified for every client by this repository's tests.

## Read existing Prometheus

Copy `assets/profile.example.json` to a private workspace. Replace each synthetic `instance` with the exact exporter label for an expected machine. Use aliases that are meaningful locally; raw captures can contain real instance labels and therefore remain private.

```bash
python3 scripts/vps_health.py collect-prometheus \
  --profile /private/workspace/vps-profile.json \
  --url https://prometheus.example.org \
  --from 2026-10-01T00:00:00Z --to 2026-10-02T00:00:00Z \
  --out /private/workspace/capture.json
python3 scripts/vps_health.py report /private/workspace/capture.json \
  --out /private/workspace/report-2026-10-02
```

The example hostname and dates are placeholders. Choose a past range available in your retention window. Authentication is optional. Use `--token-env PROMETHEUS_READ_TOKEN` to read a preconfigured environment variable without printing it. The token must be read-only and sent over HTTPS. Do not write the token into a profile, command line, report or issue.

Default queries use stock node-exporter CPU and pressure metrics. The adapter is an **accounting screen**, not an exact physical-host measurement. Missing metric families remain missing. It does not synthesize workload CFS evidence. Use the raw queries and the existing application/cgroup monitoring to resolve that gap before attribution.

The profile can include an explicit `loki_selector` per asset. Add `--loki-url https://logs.example.org` to retrieve diagnostic logs. Loki uses a separate optional `--loki-token-env LOKI_READ_TOKEN`; the Prometheus token is never reused. The log request is capped at the last six hours and 500 lines per asset. Hitting the cap is recorded as incomplete. Logs are not parsed as instructions or trusted benchmark attestations.

## Limits and side effects

Collection permits 1–100 explicit assets, a 1-hour–14-day range, a 60–3600 second step and at most 4,033 points per metric. Each GET has a maximum 15-second timeout; the entire collection has a 120-second request budget. Remaining assets are preserved with collection errors after the budget is spent. The HTTP client refuses redirects, embedded URL credentials, remote plaintext HTTP without explicit opt-in and bearer credentials over plaintext. It never changes the server.

Local reads are limited to `/proc/stat`, pressure counters, boot fingerprint and process CPU affinity. No public IP discovery, process command-line capture, environment dump, stress workload, SSH connection or service installation occurs. A boot fingerprint is still local operational data; keep captures private.

New evidence files/directories must not already exist. Do not overwrite yesterday's report. CLI exit 0 means the command completed; inspect `state` and `holds` for interpretation. Exit 2 means invalid input or an execution failure. Collection errors are retained inside captures/reports even when the command produced a usable artifact. No exit code certifies the provider or service.

## Replay and compare

```bash
python3 scripts/vps_health.py report saved/capture.json --out /tmp/replayed
python3 scripts/vps_health.py verify /tmp/replayed
python3 scripts/vps_health.py compare /private/day-one /private/day-two
```

Comparison requires the same analyzer, policy and subject set. It still does not prove causality, matched hardware or identical workloads. Re-run both captures with one analyzer version before comparing across releases. Checksums detect artifact changes; a user who rewrites both evidence and hashes can replace them, so they are not independent attestation.

## Recurring operation

Keep the user's existing Prometheus alerts and collectors. Invoke this command from an already approved scheduler with explicit scope, a unique timestamped destination, retention policy and failure notification. This package does not install a scheduler. Avoid new collection during peak load just to produce a report. Prefer retained data; schedule active experiments separately.
