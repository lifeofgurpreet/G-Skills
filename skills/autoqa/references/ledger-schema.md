# AutoQA ledger schema v1

Contents: [Commands](#commands-and-exit-codes) · [Plan](#frozen-planjson) ·
[Observations](#editable-runjson) · [Evidence](#evidence-seals) ·
[Cleanup and findings](#resources-cleanup-and-findings) ·
[Validation and limits](#validation-and-report-semantics).

The dependency-free Python 3.10+ helper is an offline ledger validator, SHA256
artifact sealer, and Markdown reporter. It never executes plan fields, commands,
logs, or artifact content. Version: 0.1.0.

## Commands and exit codes

Run the script shipped inside the skill:

    python3 scripts/autoqa.py init RUN_DIR --plan PLAN [--run-id ID]
    python3 scripts/autoqa.py attach RUN_DIR --case CASE --id TOKEN --path evidence/FILE
    python3 scripts/autoqa.py validate RUN_DIR
    python3 scripts/autoqa.py report RUN_DIR [--output NEW_PATH]

init/attach return 0 on successful creation or attachment, 2 on invalid input.
validate/report return 0 only when candidate_ready is true, 1 for a valid
nonready ledger, and 2 for schema, integrity, or filesystem errors. report
renders valid incomplete, blocked, failed, and instance-only ledgers. With no
output argument it writes Markdown to stdout. With --output it exclusively
creates a new file and writes a small JSON status to stdout. It refuses overwrite.
Errors are structured JSON with valid=false and candidate_ready=false.

For a CI gate, use the exit code from validate directly. Do not convert exit 1 to
success. To retain a nonready report, run report and preserve its exit status;
the report file is still created on exit 1. Init's exit 0 means only that the
private run directory was created; a new run is always INCOMPLETE and NOT_RUN.

## Frozen plan.json

All listed object fields are required; unknown fields are rejected. Null is
permitted only where stated. Use assets/example-plan.json for a synthetic
starting shape, then replace its attestations and acceptance criteria for a real
run. The example's identifiers are fictional and establish no real product claim.

Top level: schema = "autoqa.plan.v1", source, runtime, inventory, cases.

source:

- commit and tree: lowercase 40- or 64-digit hexadecimal Git identities, or null.
- worktree: clean, dirty, or unknown.
- dirty_summary: string; a nonempty description is required for dirty readiness.
- dirty_digest: lowercase SHA256 string, or null. A dirty candidate requires a
  digest and a matching runtime dirty_digest; clean requires null.

runtime:

- instance and build: nonempty strings, or null.
- source_commit and source_tree: hexadecimal Git identities, or null.
- dirty_digest: SHA256 string, or null.
- observation: string describing the basis for the runtime/build attestation.

inventory is an array of objects:

- id: stable local ID.
- title: nonempty string.
- selected and required: booleans.
- kind: journey, safety, or health.
- required_depth: e2e, smoke, contract, or static.

cases is an array of objects:

- id: stable local case ID.
- inventory_id: an inventory ID.
- title, entry_point, expected: nonempty strings.
- purpose: journey or guardrail.

Local IDs match an ASCII letter followed by up to 63 letters, digits, periods,
underscores, or hyphens. IDs are unique within their inventory or case array.
An empty inventory or case array remains a valid plan but can never be ready.
Required-but-unselected inventory remains an explicit readiness constraint.
Any selected inventory item without a planned case is explicitly uncovered.

## Editable run.json

init writes schema = "autoqa.run.v1", run_id, random run_nonce, created_at,
plan_sha256, cases, evidence, resources, cleanup_reviewed, cleanup_summary,
and findings. The timestamp includes a timezone. The nonce is 32 lowercase hex
digits. plan_sha256 is the canonical sorted-key compact JSON SHA256 of plan.json.
Do not rewrite these identity fields or modify the frozen plan: start a new run.

Each case result contains:

- id: a case ID from the frozen plan.
- result: PASS, FAIL, BLOCKED, NOT_RUN, or OUT_OF_SCOPE.
- outcome: completed, partial, safely_unavailable, unknown, or not_applicable.
- depth: e2e, smoke, contract, or static.
- observation: string; PASS and FAIL require a nonempty stated observation.
- evidence: an array of unique run_id:token references.

Missing result rows remain in the denominator and are counted as MISSING.
Selected NOT_RUN, BLOCKED, MISSING, and OUT_OF_SCOPE prevent readiness.
Every selected inventory item must have planned cases, a result for every case,
and PASS outcomes at that item's exact required_depth. This includes selected
optional items; required=true additionally prevents deselection.
Depths are separate categories, not a numeric hierarchy.

Selected journey cases must have purpose=journey and outcome=completed.
Selected safety/health cases must have purpose=guardrail and a completed,
safely_unavailable, or not_applicable outcome. Guardrail PASS never counts as
journey completion. At least one required completed e2e journey is mandatory.
Health-only smoke, static checks, safely unavailable required journeys, and
zero checks cannot produce READY. Any observed FAIL prevents readiness.

## Evidence seals

Put a collected local artifact under the private run's evidence/ directory.
Record its case result, outcome, depth, and actual observation before attach.
attach reads and hashes the existing artifact; it never copies, overwrites,
executes, or implicitly reseals it. Multiple artifacts can witness one case.

Each seal contains id (run_id:token), run_id, run_nonce, case_id, path,
sha256, bytes, plan_sha256, runtime_sha256, case_sha256, and sealed_at.

The helper calculates the runtime hash from the frozen runtime object and the
case hash from the result object excluding only its evidence reference list.
Additional attachments do not stale earlier seals. Changing a result,
observation, outcome, depth, plan, or runtime invalidates prior seals. Reusing a
run label does not reuse its random nonce. Each artifact belongs to one case;
cross-case references, orphan seals, duplicate IDs, and duplicate paths fail.

Artifacts must be regular, nonempty files at normalized relative POSIX paths
beneath evidence/. Absolute paths, remote URLs, dot segments, backslashes, empty
path segments, traversal, and symlink components are rejected. Size and SHA256
are recomputed on every validation. A digest mismatch is invalid, not a warning.
Keep the run under one writer; this is not a hostile concurrent filesystem
security boundary. The helper's attachment lock prevents concurrent attachments.

## Resources, cleanup, and findings

resources is an array of objects with id, case_id, description, disposition,
observation. Resource id is an exact opaque, nonempty provider identifier up to
256 characters, without ASCII control characters; numeric strings and
digit-leading UUIDs are accepted. Duplicate resource IDs are rejected.
case_id must exist in the frozen plan. description is nonempty.
disposition is removed, restored, retained, failed, or pending. Only removed or
restored with a nonempty observation can satisfy cleanup.

cleanup_reviewed must explicitly become true, and cleanup_summary must be
nonempty, even when no resources were created. Retained resources and failed,
pending, or unverified cleanup prevent readiness.

findings is an array of objects with local id, nonempty case_ids, severity,
description, task_ids. Case IDs must exist in the plan. Severity is critical,
high, medium, low, or info. High/critical findings prevent readiness. task_ids is
a unique array of nonempty strings referencing existing tasks; the helper does
not verify external task existence, create tasks, send messages, or write to
external systems.

## Validation and report semantics

JSON validation includes exact field sets, types, enums, duplicate keys,
duplicate IDs/references, nonfinite constants, and malformed identifiers.
Counts include every planned case (including missing rows), selected results,
executed PASS/FAIL depth, outcomes, required inventory satisfaction, completed
required journeys, guardrail passes, evidence seals, and resource dispositions.
The journeys.completed/e2e_completed and safety.satisfied counters refer to
required obligations; safety.guardrail_passes includes all recorded cases.
Outcome and depth are reported independently of PASS/FAIL.

Status priority is INVALID, FAILED, BLOCKED, INCOMPLETE, INSTANCE_ONLY, READY.
The JSON candidate_ready boolean is true only for READY. provenance_scope is
candidate_attestation only if source/runtime identities are known and match;
otherwise it is instance_only, even when another status takes priority.
The Markdown report includes frozen inventory, acceptance criteria, observations,
relative evidence paths and hashes, provenance attestations, findings, cleanup,
and readiness constraints. Dynamic table content escapes Markdown and HTML.

A matching source/runtime attestation is necessary, not proof of deployment.
Known instance/build identifiers, a nonempty runtime observation, matching source
commit/tree, and matching dirty state are required for candidate readiness.
Unknown or mismatched provenance still permits an honest instance-only report.

The helper verifies consistency and local artifact integrity. It does not
independently establish artifact truth, live provenance, completeness of a
human-authored inventory, actual resource deletion, or release safety. Anyone
who can edit the whole ledger can author new attestations and hashes. Review
the witnesses and provenance basis; do not treat a synthetic fixture or READY
label as independent evidence of product quality.
