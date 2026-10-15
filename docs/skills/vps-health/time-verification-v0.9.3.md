# Time-qualified context: correction, report and retained-data acceptance

Owning task: `gs-2uh.15`. This pass corrects the source classification and adds
private temporal reports. The additional inline coverage/duration renderer was
blocked and is not included. The task therefore retains its remaining UI acceptance;
the broad-promotion gate and draft remote-viewer PR #22 are not closed by this pass.

## The reproduced error and correction

The retained failure-first tests at `6d930af` showed one quiet 300-second pressure/
throttling interval describing three days of context as
`NO_HIGH_PRESSURE_IN_RECORDED_CONTEXT`. The context actually covered only 0.116%
of that window. A separate stale-context case borrowed currentness from ongoing
CPU observations. Both now produce `CONTEXT_INCOMPLETE`. The existing CPU-accounting
mean and WITHIN_TOLERANCE result remain unchanged.

Observed high pressure in a small subset is not discarded: it retains the existing
CONTENTION_PRESENT result alongside the sparse-context limitation. This is not
proof of a provider cause, complete context or measured absence of guest limits.

Each channel now carries a mean, observed seconds, coverage, last sample, age and
qualification. Coverage/freshness are based on that channel's contributing time.
The original union-weighting order is shared with the new analyzer. Randomized
comparisons to the previous implementation preserve valid means and represented
duration, including overlap, duplicates, missing intervals and quality failures.

The time profile partitions observed duration under existing 90%/80% preferences,
counts gap-separated runs of below-investigation interval averages, retains five
longest runs, groups accounting by recorded execution and compares the latest two
qualified full one-hour windows. It uses original normalized observations, not
downsampled chart pixels. Recorded execution is not runnable demand; CFS period
fractions are not CPU time lost.

## An actual installable, read-only workflow

The selected archive contains `evidence-report`, using an explicit subject and
at-most-fourteen-day UTC window. The requested range does not shrink to available
data. Summary and sample-payload hashes are read from one database snapshot; a
configuration change is refused. Active epochs are not pooled, and old-epoch
hashes cannot accompany an empty new-epoch profile. Stored sample-payload hashes
are correctly identified as distinct from raw capture-batch hashes.

The published v0.9.2 archive created the legacy acceptance workspace. The candidate
archive then analyzed it without altering its configuration, stored capture hashes,
three subjects or 2,288 observations. A separately seeded synthetic sparse case
was classified by the actual old code and re-analyzed by the candidate: the context
changed to incomplete, while the accounting decision/mean and retained files did
not change. A read-only SQLite snapshot of the existing private pilot was also
analyzed; no original code, configuration, process, schedule or deadline was changed.
Its missing CFS channel remains unmeasured. That is not a completed 72-hour pilot.

The existing workbench receives the corrected canonical finding and its private
snapshot includes the complete temporal profile. Two additional real-browser
cases verify sparse quiet context and elevated partial pressure against an actual
synthetic-history server. No new frontend coverage widgets are claimed. The
blocked renderer script was not written or applied through another tool.

## Regression and qualification boundaries

The source includes 27 temporal/report tests. An initial full-suite run exposed a
separate existing private-status retry race: all three immediate attempts could
occur during one cooperating atomic replacement. A failing scheduling regression
and two negative controls now accompany a 2ms yield. There are still three attempts;
unlinked state is never accepted, persistent churn fails and hardlinks are refused
without retry. No privacy criterion, permission or HTTP rule was relaxed.

Final full-suite counts, browser results and artifact hashes are recorded in
`time-proof-v0.9.3.json` after actual validation. Exact-head hosted CI remains a
separate merge/release gate. Test totals are not claims of native client execution,
provider integration, full estate coverage or completed multi-day field trials.

Selected installed pstack actual-artifact, subtraction and structural-regression
principles and JSM conformance guidance informed the work. This does not claim a
full external rubric or an independent reviewer. The running field pilot, Reset
Boost, account credentials, provider communications and draft remote-viewer code
are outside this patch. No social announcement or production rollout is included.
