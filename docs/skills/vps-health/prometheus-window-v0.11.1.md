# Prometheus window coverage — source correction and actual archive proof

Owning source task: `gs-2uh.20`. This pass repairs an observation-duration defect
in the existing stock Prometheus adapter, its retained-data interpretation and
the next action shown to the agent/user. It does not introduce a new collector,
change a running cadence or alter the existing CPU tolerance preferences.

## The old result was reproducibly overstated

The shipped v0.11.0 adapter evaluates `rate(...[5m])` but previously stored the
HTTP query step as each sample's duration. An hourly evaluation therefore counted
five minutes of source support as an hour. The actual prior release, queried
through a bounded synthetic HTTP endpoint, created a retained 72-hour workspace
reporting 72 observed hours, 100% coverage and WITHIN_TOLERANCE at a 96% mean.

The candidate reads that exact workspace as six supported hours and 66 unobserved
hours: about 8.33% coverage, HOLD, with the same 96% subset mean. Every original
workspace file remains byte-identical. The stored old durations and sample hashes
are preserved; no data migration or raw-capture rewrite is used to repair display.

New collection caps represented duration at the fixed 300-second query window,
and the existing raw assessment and workspace read paths apply the same rule to
legacy Prometheus records. Default/finer evaluation cadences remain bounded by
their actual step; passive Linux intervals are unaffected. Daily rollups, temporal
profiles, shortfall episodes, chart discontinuities and exports all consume the
same corrected intervals. Gaps are never filled by repeating a query result.

## Test the expression as well as the API wrapper

A separate installed-promtool test evaluates the actual stock adapter expression
against synthetic raw CPU-mode counters. For the first 55 minutes of each hour,
accounted time is 50%; for its final five minutes, 93.75%. The hourly query returns
93.75% at each evaluated timestamp, while the known synthetic hour-wide average
is about 53.65%. This demonstrates why the returned point cannot represent all
60 minutes. The three engine expressions passed in promtool 3.10.0.

The engine test uses binary-exact increments to avoid an exact-floating-point
fixture mismatch, not looser product thresholds. It runs no Prometheus service,
exporter or network probe. The shaped local HTTP tests are explicitly separate:
they validate transport, parsing, retention and the UI, not query-engine semantics.

## A usable next action, not endless waiting

Inspecting the rendered workbench exposed a second issue in the same workflow:
the corrected HOLD still told the user to keep waiting for more days. A deliberate
hourly step cannot fill its fixed 55-minute gaps simply by running longer.

The single existing operator brief now recognizes a known coarse query plan and
asks the agent to review the approved monitoring interval. It does not change
that plan, launch another collector or imply that an existing cadence is permission
to increase API traffic. Source conflicts and collection failures still take
priority. The CLI finding, workbench heading and copied private handoff use the
same next action; no frontend scoring rule or extra dashboard was introduced.

## Bound malformed responses without dropping subjects

Range parsing now validates the entire single float-series matrix and evaluation
grid before adding a channel's values. Empty valid matrices and non-finite values
remain missing. Wrong result types, duplicate series, histogram-only results,
bad pairs, booleans, off-grid/descending/duplicate timestamps and finite ratios
outside the supported domain are recorded as channel errors. Previously malformed
pair unpacking could escape the channel handler, and boolean true could become a
plausible 1.0 value.

A bad optional pressure channel does not erase valid accounting or silently drop
the expected node. The existing collection-wide time budget still leaves all
100 declared subjects represented when requests cannot run. This is not an
unbounded retry or a claim that malformed data is a valid measurement.

## Actual package and UI acceptance

The v0.11.1 candidate was built from an immutable commit and extracted. Its owning
package checks exercise retained coarse-window data and real local HTTP. A separate
old/new archive comparison created data with the published v0.11.0 code, then ran
the new report, export and verification without altering the source workspace.
Python site-packages were disabled for those actual CLI calls.

Browser scenarios use a temporary local endpoint and the actual read-only viewer.
They verify HOLD, six-hour duration, per-channel coverage, discontinuous charts,
pinned handoff, the cadence-review action, private download, time report and
verified offline summary. Their synthetic window is aligned within five minutes
of the test clock so an unrelated rolling-window edge does not invalidate the
comparison. Cross-version rolling exports are checked against the exact numeric
window bounds; formatted UTC labels round seconds and are not precise integration
bounds. These fixture corrections do not change production expectations.

One subsequent full-collection attempt failed in the unchanged Reset Boost panel
HTTP read. Its failure log was retained; that skill and its tests were not edited
to make this patch pass. The adjacent final receipt records the actual later
full-suite, browser and exact-commit hosted results. Earlier passing source checks
are not substituted for the final tree.

## Limits and release scope

Supported rate-window time is not proof of complete raw scrapes: rate extrapolation
and missed scrapes remain relevant. Existing minimum-sample, reset, up and CPU-mode
checks are not hypervisor-clock calibration or provider guarantees. A high subset
mean and an insufficient-coverage HOLD can both be correct. No change here assigns
provider responsibility, guest innocence or permission to migrate.

The long-running original passive v0.8.0 pilot is unchanged; it is not a test of
this new Prometheus code or a completed second field route. Fresh native agent
behavior remains unqualified while the recorded client is signed out. Runtime
and API fixtures do not become native-model scores or completed 72-hour trials.

Pstack's direct-artifact and subtraction principles were applied by fixing the
existing duration owner, preserving source data, and correcting the canonical
next action rather than adding another monitoring framework. Shared Agent Mail
discovery failed, so only a host-local advisory reservation was used; no shared
reservation, account change or policy bypass is claimed. The raw private pilot,
other skills, provider messages and public announcements were not changed.

Installed method and primary documentation:
[Prometheus query-window coverage](../../../skills/vps-health/references/prometheus-windows.md).
The machine receipt beside this file binds tests, engine evidence and actual
archive hashes to the source that was exercised.
