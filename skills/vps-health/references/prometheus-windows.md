# Query spacing is not observation duration

The stock Prometheus adapter evaluates fixed `rate(...[5m])` expressions. The
HTTP `step` controls how often those expressions are evaluated; it does not turn
the five-minute range into an hour. A query returning one value per hour therefore
leaves up to 55 minutes between supported windows. It cannot establish continuous
observation merely because all returned values look good.

## The corrected rule

The supported duration of a sample is capped by its recorded interval, requested
evaluation step and the stock adapter's **300-second rate window**. Existing
non-overlapping interval weighting still prevents repeated/overlapping requests
from adding time. Window-edge clipping excludes time before the requested capture.

At the ordinary 300-second cadence, this correction does not reduce nominal
window coverage. Finer steps do not multiply overlapping five-minute windows;
coarser steps preserve their unobserved gaps. For example, three days of hourly
query values represent at most six hours of five-minute windows—not 72 measured
hours. Missing context, reset/quality failures and invalid results remain unknown.

New captures explicitly record the rate-window and evaluation-step metadata.
Reports and workspaces created by older releases are also read conservatively:
stored Prometheus durations are capped when analyzed, without rewriting the old
database rows, sample hashes or raw capture batches. Original reports remain
historical outputs; re-analyze their retained data to obtain the corrected result.
Source/method epochs still stay separate. Linux passive intervals are unaffected.

The same effective duration feeds the assessment, daily rollups, Evidence tables,
gap-separated shortfall runs, chart break markers and agent handoffs. Hourly
five-minute shortfalls cannot be connected into an uninterrupted 72-hour episode.
A high mean over the available subset can stay numerically high while the decision
becomes HOLD because time coverage is insufficient. This is an evidence decision,
not an accusation against a provider or a change to the user's 90%/80% preferences.

## What the agent should do

Inspect the declared profile and interval before collecting. Reuse the existing
approved monitoring endpoint; do not discover credentials, scan unrelated targets
or deploy another exporter. The default 300-second cadence is suitable for the
fixed stock query window. If an existing plan deliberately samples more slowly,
retain its gaps. To change cadence, obtain any necessary new bounded-plan approval
instead of silently modifying a running investigation.

Use `evidence-report` for an explicit private UTC window, or the existing workbench
and verified export path. Read observed duration and coverage, not just the number
of graph points. Preserve all configured missing/inaccessible subjects. A malformed
optional channel is recorded as an error for that channel instead of crashing away
the rest of the expected-node list. Empty valid matrices and non-finite values
remain missing, not zero. Ambiguous series, malformed pairs, off-grid/duplicate/
unordered times and out-of-domain ratios are refused with raw source context retained.

The agent performs the queries and interpretation through the installed skill;
the user should not have to rewrite PromQL or configure a second monitoring system.
No version upgrade or query success grants permission for host changes, active
benchmarks, external messages or private-data publication.

## Limits still matter

**Supported rate-window time is not verified raw-scrape completeness.** Prometheus
can extrapolate rates and accommodate missed scrapes. The stock minimum-sample,
reset, target-up and mode-count checks screen obvious problems; they do not attest
the hypervisor clock or reconstruct every raw scrape. Inspect the actual deployment
and exporter freshness when consequential conclusions depend on those details.

These rules apply to the skill's fixed stock node-exporter query adapter, not to
an arbitrary user-written expression. No parser infers the effective lookback of
unknown PromQL. The read correction does not recover the unqueried 55 minutes,
prove that an interpolated rate was physical CPU delivery or certify service health.
Existing users can retain their data; no cleanup, database migration, schema rewrite
or private pilot restart is required.

## Primary semantics and verification

Prometheus documents [`step` as query resolution](https://prometheus.io/docs/prometheus/latest/querying/api/#range-queries),
[range queries as repeated instant evaluations](https://prometheus.io/docs/prometheus/latest/querying/basics/),
and [`rate` extrapolation](https://prometheus.io/docs/prometheus/latest/querying/functions/#rate).
The distinction was additionally checked with an installed promtool against the
actual adapter expression and synthetic counters that changed within each hour.
That engine test is separate from the shaped local HTTP endpoint used to test
transport, parsing, retention and the browser. Neither is a production-pilot claim.
