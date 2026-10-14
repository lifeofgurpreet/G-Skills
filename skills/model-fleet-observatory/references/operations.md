# Operations

Run a read-only doctor first:

```sh
python3 scripts/model_fleet_dashboard.py doctor \
  --config ~/.config/model-fleet-observatory/config.json
```

Create a one-time snapshot and inspect it without starting a server:

```sh
python3 scripts/model_fleet_dashboard.py snapshot \
  --config ~/.config/model-fleet-observatory/config.json \
  --out /tmp/model-fleet-snapshot.json --discover-local
```

Start the private live view:

```sh
python3 scripts/model_fleet_dashboard.py serve \
  --config ~/.config/model-fleet-observatory/config.json \
  --bind 127.0.0.1 --port 8765 --interval 600 --discover-local
```

The server exposes `/`, `/api/snapshot`, `/api/refresh` and `/healthz`. A
wrapper or hotkey can call `/api/refresh` for an immediate event-style update;
the ten-minute timer remains the fallback. Refresh is event-safe:
the collector replaces a complete snapshot under a lock, so the browser never
sees half a box. `r` requests an immediate read; the interval loop continues
until the operator stops the foreground process. The runtime has no daemon
installer and no external notification sender.

For a new harness, add a small adapter command that emits the schema, then add
a synthetic fixture and a failure fixture to the owning tests. Verify the
adapter's real readback separately from the dashboard's rendering. Package only
from an immutable commit after `tools/validate.py --skill
model-fleet-observatory` and its browser check pass.
