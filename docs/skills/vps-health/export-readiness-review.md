# Export readiness review — unresolved, not a release

Reviewed published source: `7dc945065fe488185cb625d2db3893a220f235b0`
(`vps-health/v0.9.5`). This branch contains failing reproductions and the task
receipt. It contains no runtime correction, release or production change.

## Actual user-visible mismatch

Using the real installed CLI with site-packages disabled, a synthetic workspace
bootstraps successfully and `export` successfully creates its five-file summary.
Passing that directory to the same CLI's `verify` returns exit 2 with
`InvalidEvidence: invalid manifest`. The verifier recognizes the raw-capture
bundle format, not the `g-skills.workspace-export.v1` format that `export` creates.

This does not mean the summary has no checksums. Its existing per-file checksums
match the files. The missing piece is an agent-callable verification route for
that summary type, explicitly distinct from full raw-measurement replay. The raw
capture bundle's existing replay verification still passes and must be preserved.

## Snapshot consistency reproduced

The exporter reads `status(root)` and subsequently opens another connection for
the capture index. In a disposable SQLite WAL fixture, an actual synthetic capture
arrives after the summary read and before the index read. The exported index then
has two capture batches while the exported status describes one. Both files have
valid checksums; hashing does not make them one coherent observation snapshot.

The test uses an instrumented call boundary to introduce the arrival, with real
SQLite reads and writes on synthetic data only. It is not an observed corruption
of the user's running pilot. The expected correction is a coherent read snapshot
for summary and index, without starting collection or reclassifying CPU evidence.

## Additional acceptance gaps

The other failure-first cases define the intended public workflow: reject an
already-existing destination before doing an expensive status read; keep a failed
render from publishing an incomplete destination that prevents an ordinary retry;
keep derived exports outside their observation workspace; and refuse a changed
configuration binding. These are explicit acceptance requirements, not seven
independent production incidents or claims that customer data was lost.

Run the focused reproduction suite from the repository:

```bash
python3 skills/vps-health/tests/test_workspace_export.py
```

The current result is **nine cases: seven failing acceptance cases and two passing
controls, with no execution errors**. The controls establish real existing summary
checksums, no network/collection in export, unchanged source observations, and
unchanged raw-capture replay. The suite deliberately remains separate from the
existing green validation entry until a complete implementation is available.
Passing the old suite or ordinary draft-PR CI cannot clear these new failures.

## Blocked work and guardrails

The proposed export implementation write was blocked by the tool before a file
was written or applied. It was not reapplied using another tool, device or source
location. The earlier inline-coverage baseline write was also blocked; that UI
remains unchanged. Do not infer source completion from the presence of tests.

The current native Claude Code preflight reported signed out (`loggedIn=false`,
`authMethod=none`). No additional model trials were dispatched, no account was
switched and no authentication settings were changed. A prepared evaluation is
not a behavioral score.

A usable summary verifier must keep integrity, consistency, replay availability
and independent attestation separate. It must not execute exported HTML, contact
services, authorize provider actions or claim that a self-supplied manifest proves
an adversary did not replace both the data and hashes. Preserve the original
workspace and existing release. Resolving this draft must not change the running
passive qualification pilot or merge the separate remote-viewer draft.

The adjacent machine receipt records the source, case names and outcomes. Only
synthetic tests and non-identifying status summaries are published. Raw private
logs, account state, credentials and observations remain outside the repository.
