# What was measured, for how long, and how recently?

A mean describes the samples that contributed to it. It cannot describe missing
time just because another channel has a long history. VPS Health now retains a
separate duration, coverage, last observation and qualification for accounted CPU,
recorded execution, CPU pressure and throttled-period fractions.

This fixes the case where five quiet minutes of pressure/throttling appeared to
clear three days of workload context. A quiet but sparse/stale channel remains
incomplete. An elevated value over a short observed subset remains visible, with
its inadequate coverage preserved. Accounting decisions keep the existing chosen
90%/80% preferences; workload-context qualification does not invent a provider
CPU floor or turn a good accounting result into verified service health.

## Agent-owned use

Read `brief` and the current workspace first. `evidence_profile` in the retained
status contains the temporal detail. For a particular private investigation:

```bash
python3 scripts/vps_health.py evidence-report --workspace /private/investigation \
  --node owner-confirmed-node --start 2026-10-14T00:00:00Z \
  --end 2026-10-15T00:00:00Z --out /private/report.json
```

The coding agent resolves these actual arguments and runs the command. The human
does not have to edit profiles or copy recipes. Omit `--out` to read structured
JSON directly through the host tool. With a file output, use a new private path
outside both the installation and the observation workspace. Existing files are
not overwritten. No collector, API request, email draft or host change is started.

Reports allow at most fourteen days in one explicit timezone-aware interval. The
requested window is not shortened to the first convenient observation. A day
before data collection started is unobserved, not silently excluded. Values are
based on the active retained epoch; earlier migration/method epochs are not pooled.
Current ingestion/identity holds are not a historical reconstruction of the
monitor's exact state at some past moment. A changed configuration during the
read is refused; summary and stored sample-payload hashes share a read transaction.

The output is private investigation material. It includes the subject label,
window, contextual summaries and bounded observation hashes. It is not the minimal
support report and does not replace the raw database or its capture batches.
Sample-payload hashes are not raw capture hashes or signatures; effective stored
durations and conflict flags are needed for replay. Large hash lists are explicitly
marked truncated, never described as complete raw provenance.

## Duration and coverage

The same ordered, clipped interval traversal feeds the existing workspace means
and the new temporal profile. The first retained interval owns overlapping time,
including invalid time. Repeated windows add no extra hours. Quality failures,
conflicts and intervals lacking usable accounting are kept apart from time with
no observed interval. Their union remains missing evidence, not healthy time.

Each channel's mean uses its own observed duration. Qualification reuses the
existing evidence preferences: at least 75% of the assessment window represented,
with its last contributing observation no older than the greater of 120 seconds
or 2.5 configured collection intervals. These are measurement-quality preferences,
not uncertainty bounds or contractual performance promises. Sparse zero is still a
measured zero for that subset, not proof of zero across the entire window.

Interval averages can be clipped at a requested window edge. That attributes the
recorded average to its represented portion; it does not claim the original
sub-interval was measured separately. Never interpret this as millisecond tracing.

## Shortfall duration, runs and changes

`bands` partitions usable observed time under the existing accounting preferences.
It counts duration, not sample count. `episodes` reports uninterrupted runs of
below-investigation interval averages, including total run count and the five
longest runs. Gaps and invalid intervals split runs; the tool does not connect
shortfalls across an outage to manufacture sustained trouble.

`execution_bands` separates below-25%, 25–75%, at-least-75% and unmeasured recorded
execution. Those are descriptive buckets, not classifications of actual demand.
A starved vCPU can record little execution despite substantial runnable demand.
Pressure means within a bucket retain their own represented time. Do not mistake
missing context, conditional averages or throttled-period counts for proof that
the guest was innocent or the provider responsible.

`recent_change` compares the latest two full one-hour windows only when both have
qualified accounting coverage/currentness. The difference is in ratio units
(0.1 is ten percentage points), not percent improvement. Otherwise the difference
is null and the state is INSUFFICIENT_EVIDENCE. It is not a migration verdict.

## Viewer and sharing boundary

The existing workbench now receives the corrected contextual classification and
canonical next-action finding. Private JSON snapshots carry the full profile;
Markdown exports include per-channel means, observed coverage and qualification.
The additional inline coverage table and duration widgets are not yet implemented:
the renderer write was blocked. Do not claim that every metric card now shows its
denominator. Until that follow-up lands, the agent should inspect the structured
profile or this report before interpreting the compact context values.

No chart zoom changes a full-window assessment, and decimation is never an input
to temporal analysis. No change here permits active probes, account discovery,
provider messages, public uploads, weakened safety checks or a new collector.
The original passive field pilot must stay on its own approved source/deadline.

Primary semantics checked against Linux [PSI](https://docs.kernel.org/accounting/psi.html)
and [CPU bandwidth statistics](https://docs.kernel.org/scheduler/sched-bwc.html):
pressure is stalled time, while throttled periods and throttled time are distinct
quantities. The code's descriptive thresholds and coverage rules are our stated
analysis choices, not statements made by those kernel documents or a provider.
