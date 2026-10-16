# Export a private summary, then verify what it actually contains

The coding agent runs this workflow through the installed CLI. The human does
not need to copy hashes, inspect database files or construct a new monitoring
stack. An export is still private evidence, not permission to send a provider
message or upload a support attachment.

## One operation pair for the actual result

Resolve the executable from SKILL.md, then use the known authorized workspace
and a new private destination outside it:

```bash
python3 /absolute/skill/scripts/vps_health.py export \
  --workspace /private/investigation --out /private/summary-review
python3 /absolute/skill/scripts/vps_health.py verify /private/summary-review
```

`export` prepares status.json, dashboard.html, report.md, capture-index.json and
manifest.json. Status and the capture index use one read transaction, so a new
capture arriving during export cannot make the saved summary and index disagree.
The source configuration binding is checked. Live worker metadata is an additional
observation, not a claim that a process remains running when the export is opened.

The operation stages a complete private directory before publishing the chosen
destination. Existing destinations are refused. An interrupted attempt retains
its private staging files; retrying the unused destination does not delete them.
Four retained interrupted stages require explicit inspection or archival rather
than an unbounded retry loop. File-size and capture-index limits remain bounded.
The cooperating writer lock and same-parent rename are not a security guarantee
against a privileged or malicious same-account process or filesystem corruption.

## Read the verification scope, not just PASS

For a workspace summary, `verify` returns:

- `integrity: PASS`: the four expected files match the supplied local manifest;
  the subject and indexed capture counts are consistent.
- `replay: NOT_AVAILABLE`: raw captures and the original database are absent.
  The verifier has not rerun the measurement analysis.
- `independent_attestation: false`: someone controlling both files and manifest
  can replace both. Matching hashes are not a trusted signature or provider proof.

The snapshot receipt reports whether the recorded metadata matches its payload.
Older summary formats without that receipt report NOT_RECORDED. Their intact
files can still be checked; a previously inconsistent capture index is refused,
not repaired automatically. Preserve the old output and re-export from the
original workspace when a fresh coherent summary is needed.

The original raw-capture `report`/`demo` bundles retain their existing replay path.
The same `verify` entry dispatches by the declared format; it never upgrades a
summary into replayable measurements. A single `evidence-report` JSON output or
browser-downloaded status snapshot is a different artifact, not this five-file
bundle. Do not pass either to the directory verifier and call it full evidence.

## Keep observation history and software support separate

The workbench's **Export snapshot** saves the currently displayed derived JSON,
including private node details and timestamps. The CLI `export` creates the
multi-file review bundle with a manifest. `support-report` is a smaller projection
intended for review before software-support sharing; it omits raw investigation
details. None of these operations sends, posts, authenticates or contacts anyone.

Verification reads bounded files and never executes exported HTML. It does not
certify that arbitrary HTML is safe or that an archive is safe to publish. Open
only a trusted export in the browser, and keep the original private database and
matching skill source for actual replay, archival and future investigation.

When explaining results, the agent should state the artifact type, integrity
result, missing raw-replay scope and next useful action. Do not turn a verified
summary into a declaration of good service, guest innocence or provider fault.
