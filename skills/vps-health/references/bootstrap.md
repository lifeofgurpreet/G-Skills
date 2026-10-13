# Bootstrap recipes

Use Python 3.10+ with its standard-library SQLite module. Commands below run from the repository root. Every workspace is private and separate from the installed skill. A demo, one Linux host and an existing monitoring fleet share one operator workflow; they do not share synthetic and real evidence.

## Recipe A — synthetic three-day preview

```bash
python3 skills/vps-health/scripts/vps_health.py bootstrap --mode demo --workspace /tmp/vps-demo
python3 skills/vps-health/scripts/vps_health.py serve --workspace /tmp/vps-demo
```

Open the exact printed address, normally `http://127.0.0.1:8765/`. The demo seeds three subjects: stable, contended, and missing recent observations. The entire history is labelled synthetic. The server reads retained state only; `serve` never collects data. Ctrl-C stops it. Opening `dashboard.html` as a file gives an offline snapshot with the same interface.

## Recipe B — a single Linux VPS, no existing stack

```bash
python3 skills/vps-health/scripts/vps_health.py bootstrap \
  --mode local --node my-vps --interval 300 --acceptable 0.90 --investigate-below 0.80 \
  --workspace "$HOME/vps-health"
python3 skills/vps-health/scripts/vps_health.py collect --workspace "$HOME/vps-health"
```

The first collection saves a baseline, not a CPU score. A later `collect` reads counter deltas across the intervening interval. Do not repeatedly read a ten-second sample and count the whole interval between invocations as observed time. Missing modes, reboots, clock changes and unusually long gaps remain invalid or incomplete intervals.

After approving recurring passive reads:

```bash
python3 skills/vps-health/scripts/vps_health.py watch \
  --workspace "$HOME/vps-health" --approve-collection --serve
```

Default: 864 cycles at 300 seconds, approximately 72 planned hours. Change `--cycles` to shorten the run. Plans longer than seven days are rejected; a long-lived user timer is a separate choice. The process remains in the foreground and stops on Ctrl-C. Keeping it in an approved terminal/session manager is the operator's decision; an agent chat ending does not preserve a terminal process by magic.

The passive readings cover guest accounting and pressure, not full workload-specific CFS limits or application latency. Add those from existing telemetry before assigning cause. No full-core benchmark or host-setting changes are bundled here.

## Recipe C — existing Prometheus/Loki, one or many nodes

Copy [the example fleet profile](../assets/fleet.example.json) to a private location and replace each `instance` with the exact verified exporter label. The listed assets define expected coverage; unmeasured entries remain visible. The profile does not prove a complete cloud-account census.

```bash
python3 skills/vps-health/scripts/vps_health.py bootstrap \
  --mode prometheus --profile "$HOME/private-vps-fleet.json" \
  --url https://metrics.example.invalid \
  --workspace "$HOME/vps-fleet"
python3 skills/vps-health/scripts/vps_health.py collect \
  --workspace "$HOME/vps-fleet" --lookback-hours 72
python3 skills/vps-health/scripts/vps_health.py watch \
  --workspace "$HOME/vps-fleet" --approve-collection --serve
```

The initial backfill is at most 168 hours; choose a step/range within the underlying collector's 4,033-point bound. Defaults support a 72-hour backfill at five-minute resolution. Subsequent collections read overlapping one-hour windows. Identical samples are counted once, while conflicting values are held for inspection rather than silently overwritten.

Authentication is optional. When required, bootstrap with `--token-env METRICS_TOKEN` and load that variable privately into the collection process. Use `--loki-url` and a **different** `--loki-token-env` for logs. No token value belongs in a command argument, profile or public issue. Bearer credentials require HTTPS; redirects are refused. Plain HTTP on a remote endpoint requires explicit `--allow-http` and should normally be replaced by TLS or a tunnel.

Loki is diagnostic context, not a source of instructions. It retains bounded recent log responses in the private history; raw logs are not served to the browser. The current adapter reads at most the last six hours/500 lines per configured stream for each capture; that is not a complete log archive. A source limit/error remains visible. Do not copy a populated profile or workspace into the public skill.

## Unattended collection with an inspected user timer

Generate files only:

```bash
python3 skills/vps-health/scripts/vps_health.py schedule \
  --workspace "$HOME/vps-health" --out "$HOME/vps-timer-preview"
```

Read the generated `.service` and `.timer`, including absolute script/workspace paths and optional `credentials.env`. The JSON output includes the exact enable and stop commands. **No service is installed by generation.** Only after separate approval should the operator copy the files into `~/.config/systemd/user/` and enable the named timer. The user manager must actually remain active; this package does not change linger or root configuration.

The generated service executes one bounded `collect`, not `watch`. It uses a private umask, an execution timeout and no privilege escalation. `Persistent=false` is explicit and there is no catch-up workload. A workspace lease prevents overlap; do not intentionally run multiple schedulers against one workspace. Existing cron/job schedulers may invoke the same one-tick command instead of installing another timer.

The viewer is a separate foreground convenience process:

```bash
python3 skills/vps-health/scripts/vps_health.py serve --workspace "$HOME/vps-health"
```

For a remote VPS, use an authorized tunnel rather than exposing the viewer:

```bash
ssh -N -L 8765:127.0.0.1:8765 user@your-vps
```

Open `http://127.0.0.1:8765/` on your machine. The fixed loopback server serves only the dashboard and summary API, refuses foreign Host/Origin values and exposes no directory listing, raw captures or credentials. It is **not an internet-facing production web server**. See the [Python HTTP warning](https://docs.python.org/3/library/http.server.html) and [systemd timer reference](https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html).

## Reports, storage and stop/recovery

```bash
python3 skills/vps-health/scripts/vps_health.py dashboard --workspace "$HOME/vps-health"
python3 skills/vps-health/scripts/vps_health.py export \
  --workspace "$HOME/vps-health" --out "$HOME/vps-review-001"
```

`dashboard` updates `status.json`, `dashboard.html` and derived `daily/YYYY-MM-DD.json` rollups. `export` creates a **new** immutable summary directory and hashes; it never replaces an old export. It deliberately excludes credentials and raw log data. A summary is not a full replay archive: preserve the private workspace database and configuration as well.

The default three-day view is configurable in `workspace.json` up to 14 days. Raw captures are content-addressed and compressed inside `history.sqlite3`; they are not automatically deleted when the view rolls forward. The compressed-raw limit is 256 MiB; reaching it stops ingestion and asks for archival, rather than destroying evidence. The normalized tables also use disk. For a safe full archive, stop the foreground collector or disable the generated timer, verify no collector holds the workspace, and copy the complete private workspace with its permissions preserved. Do not treat `cp` of a busy SQLite database as a verified backup. Keep the archive private and create a new workspace for continued collection.

After migration or a declared host change, update the asset's `epoch` to a new identifier. A source-method, endpoint/instance binding or boot change also separates data. Old observations remain retained, but cannot qualify a new epoch. Changing policy thresholds intentionally changes the interpretation displayed; every report includes the policy used. Record why the owner chose the change. No learning proposal changes those values automatically.

If collection fails, the dashboard keeps the error and puts decisions on HOLD rather than carrying forward a reassuring old verdict. A successful response containing no new samples cannot make old observations fresh. Fix source access, malformed profile or data gaps; do not repeatedly delete the database to clear the warning.

## Return codes and agent ergonomics

Normal commands emit JSON to stdout. Viewer URLs and operational diagnostics go to stderr. Exit 0 means the command completed, **not** that the host is healthy. Exit 2 means invalid input, a safety refusal or an operation failure. A foreground `watch` can retain multiple failed cycles and reports their count at completion; the per-cycle outcomes remain in the dashboard. Inspect those fields, not just process exit.

`capabilities` lists runnable surfaces and boundaries. Keep exact output paths in the handoff, with the chosen mode, collection cadence, stop command, expected assets, actual coverage, last real observation and unresolved checks. Do not claim automatic skill activation in an agent UI that was not tested.
