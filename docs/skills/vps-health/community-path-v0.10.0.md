# VPS Health 0.10.0 — complete two existing publication paths

Owning source tasks: `gs-2uh.15` (temporal context in the workbench) and
`gs-2uh.18` (coherent, verifiable workspace summaries). The original implementation
writes were blocked in earlier sessions. This continuation's direct writes were
accepted and applied; prior failures remain in the history, not counted as fixes.

## 1. Export now has a truthful verification route

The original nine tests from draft PR #27 were reused. All now pass. Sixteen
additional tests cover altered/missing files, path/link restrictions, private
permissions, old manifests, failed stages, retry bounds and honest verification
results. The actual capture-arrival fixture uses SQLite WAL in a disposable
workspace: a writer can commit while the export retains its original read
snapshot. Status and capture index no longer describe different capture counts.

The exporter stages complete private output before publication, refuses existing
or inside-workspace destinations, checks configuration consistency and retains
interrupted stages rather than deleting them. The existing initialization lock
coordinates cooperating writers. This is not protection against root, a hostile
same-account process, every filesystem failure or unqualified power-loss behavior.
No user workspace's journal mode or service configuration is changed.

The existing `verify` command recognizes the workspace-summary format and returns
integrity/snapshot results with `replay: NOT_AVAILABLE`. Raw-capture bundles keep
their original replay verification. A self-supplied manifest is not an independent
signature, and verifying bytes does not certify arbitrary HTML or authorize public
sharing. The verifier never executes the HTML or reconstructs absent raw captures.

## 2. The frontend displays the backend's contextual denominators

Execution, pressure and throttled-period captions now include their own observed
time, coverage and current/sparse/stale qualification. Evidence shows the full
source window, per-channel table, observed preference-band durations, missing and
invalid time, uninterrupted shortfall runs and recorded-execution groups. The
last two qualified hourly windows can display their existing mean difference;
otherwise that change remains unavailable. These are backend values, not a new
browser scoring system or a recalculation from downsampled chart pixels.

The pinned review and exact copied agent task retain the contextual denominators
while the background refreshes. A five-minute quiet sample is displayed as sparse
rather than inheriting three days of accounting coverage. New malformed temporal
payloads cannot replace the accepted view, and old snapshots without a profile
explicitly say coverage is absent. Node selection, disclosure state and keyboard/
mobile interactions remain part of the same workbench, not a second dashboard.

Eighteen new JavaScript contracts and six new browser groups exercise these
properties. The first browser pass exposed a test-only mismatch between paragraph
innerText and textContent. The assertion now compares the exact paragraph sequence;
it still fails if any pinned value changes. No runtime field or expectation was
weakened to hide that test mismatch.

## Actual distributed artifact and legacy evidence

The real published v0.9.5 archive created the legacy workspace and old summary.
Its old CLI rejects that summary at `verify`. The new extracted archive accepts
its intact files with snapshot receipt NOT_RECORDED, then exports a new coherent
summary and verifies a MATCHES_PAYLOAD receipt. The original workspace and old
summary stay byte-for-byte unchanged; all three subjects and 2,288 observations
remain. An old raw-capture bundle still replays under the new code.

The new archive's concurrent-arrival and failed-stage/retry tests were also run
from its extracted folder. Deliberately changed output is refused. The actual
verified summary opens the new temporal workbench offline. Its demo, screenshots
and browser inputs are synthetic, and no new collector was started by the export
workflow. Normal package lifecycle tests separately start and stop their own
bounded synthetic worker; those are not native model trials.

## Validation and outstanding scope

575 Python tests across the collection, 45 JavaScript contracts and 51 real-browser
scenario groups pass locally. The selected archive contains 63 files. The adjacent
machine receipt records the exact candidate source, archive hash, full suite
counts and old/new results. Final-main hosted CI and a byte-matching final archive
remain the separate publication gate; local green alone is not that gate.

The private original v0.8.0 field pilot is not upgraded, restarted or reclassified.
Fresh native-agent behavior/trigger qualification, the remote-viewer draft and
external mailbox acceptance remain separate. No provider, social network or user
mailbox was contacted. Other G-Skills entries and their runtimes are unchanged.

This host now uses the shared main checkout per the updated contributor contract.
The configured fleet Agent Mail endpoint was unavailable and its local mailbox
correctly refused fleet coordination; no local override, invented reservation or
registered identity is claimed. Edits are confined to named owning paths and
compared against current main before pushing. The existing hook remains in its
configured advisory mode. Prior draft PR #27 is superseded only after these fixes
land; its repro branch remains an auditable history rather than being merged over
the newer implementation.

Applied guidance: selected installed pstack actual-output verification and
subtraction principles. Primary reference for the concurrent snapshot model:
[SQLite isolation](https://sqlite.org/isolation.html). Directory publication uses
same-parent rename with the limitations described by [Python's OS interface](https://docs.python.org/3.12/library/os.html#os.rename).
These references describe primitives, not universal estate qualification.
