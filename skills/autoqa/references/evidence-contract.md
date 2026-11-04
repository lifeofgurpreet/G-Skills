# Evidence contract and offline helper

Contents: [Commands](#four-commands) · [Plan](#frozen-plan) ·
[Observations](#editable-observations) · [Evidence](#evidence-lifecycle) ·
[Cleanup](#resources-and-cleanup) · [Limits](#limits-of-the-decision).

The helper uses Python's standard library and never executes a test command,
contacts a provider, changes the application or publishes a report. Reuse the
repository's native tools to perform QA. Use this helper to retain and check the
resulting evidence. The [exact ledger schema](ledger-schema.md) defines required
keys, accepted values and readiness rules; use it when constructing a plan or
updating observations. This guide explains the workflow.

## Four commands

Resolve AUTOQA_SKILL to the installed skill folder, QA_PLAN to a reviewed local
plan JSON file, and QA_RUN to a new private directory. Use the bundled
[example plan](../assets/example-plan.json) as a shape reference only: replace its
synthetic identities and cases with this task's actual contract.

```bash
python3 "$AUTOQA_SKILL/scripts/autoqa.py" init "$QA_RUN" --plan "$QA_PLAN"
python3 "$AUTOQA_SKILL/scripts/autoqa.py" attach "$QA_RUN" --case CASE-1 --id E01 --path evidence/CASE-1.txt
python3 "$AUTOQA_SKILL/scripts/autoqa.py" validate "$QA_RUN"
python3 "$AUTOQA_SKILL/scripts/autoqa.py" report "$QA_RUN" --output "$QA_RUN/report.md"
```

- **init:** Freeze the plan, create a fresh run identity and start cases untested.
  Use a new directory; do not overwrite a previous run.
- **attach:** Seal a nonempty artifact already captured inside the run directory.
  First record the case's current observation, result, outcome and depth in
  run.json. The seal binds the artifact bytes to the run, frozen plan, runtime
  identity and case snapshot. The command does not assign a passing result.
- **validate:** Check structure, inventory coverage, provenance consistency,
  evidence integrity, completion and cleanup; emit a machine-readable decision.
- **report:** Apply the same checks and render a Markdown report. A valid failed,
  blocked or incomplete run still gets a readable report.

For **validate and report**, exit codes are deliberate: **0 means candidate-ready
within the declared scope; 1 means a valid but nonready run; 2 means malformed
input or failed integrity.** For init and attach, exit 0 means that the creation
or sealing operation succeeded; it is not a product verdict. Do not suppress exit
1 in a release check or turn successful report generation into a product PASS.
A readiness recommendation never authorizes a deployment.

## Frozen plan

plan.json uses schema autoqa.plan.v1.

| Field | Required meaning |
| --- | --- |
| source | Candidate commit, tree identity and clean/dirty/unknown worktree state; dirty_summary and dirty_digest when dirty. |
| runtime | Target instance, build identity, its observed source_commit/source_tree/dirty_digest, and the observation establishing that mapping. |
| inventory | Stable id, title, selected/required booleans, kind and required_depth. |
| cases | Stable id, inventory_id, title, purpose, entry_point and expected outcome. |

Inventory kinds are journey, safety or health. Case purposes are journey or
guardrail. Required depth is static, contract, smoke or e2e. A health-only plan or
a successful safety check cannot establish a completed end-to-end journey.

Use identities from source and runtime evidence. Unknown identity stays unknown.
A local commit alone is not evidence of what a remote instance runs. The helper
checks consistency of the declarations; it cannot retrieve or independently
authenticate a deployment identity.

The frozen plan's digest makes accidental scope or runtime changes visible.
Changing the plan requires a new run. A person who controls the entire directory
can rewrite hashes too: this is an integrity aid, not tamper-proof attestation.

## Editable observations

run.json uses schema autoqa.run.v1. Preserve the generated run_id, run_nonce,
created_at and plan_sha256. Update case observations as tests execute.

| Case field | Values or purpose |
| --- | --- |
| result | PASS, FAIL, BLOCKED, NOT_RUN, OUT_OF_SCOPE |
| outcome | completed, partial, safely_unavailable, unknown, not_applicable |
| depth | static, contract, smoke, e2e |
| observation | What the evidence actually demonstrates, or the concrete nonexecution reason. |
| evidence | IDs returned by attach; never invented or copied across runs. |

Keep observed result and expected behavior separate. PASS requires evidence
showing the criterion. A safely unavailable required journey remains nonready
even when its rejection guardrail passes. Every selected item must meet its
declared outcome and proof depth, including optional items selected for this run.
Required items cannot be deselected; selected cases marked out of scope cannot
silently disappear from readiness.

Record findings with IDs, affected case_ids, severity, description and existing
task_ids where applicable. The helper records references only; it never creates
issues, sends messages or edits task systems.

## Evidence lifecycle

Capture through native tools to an evidence subdirectory in the private run.
Redact credentials, private identity data and sensitive URLs before sealing a
shareable witness; retain originals only in an authorized private location.

Artifact paths must be local and relative to the run directory. Traversal,
symlink escape, empty evidence, duplicate identifiers and digest mismatches are
invalid. A seal binds the current run nonce, plan/runtime and observation. Do not
reseal an old artifact to make a changed observation pass. A new observation
belongs in a new run, with the prior failure linked in the report or task.

Hashes prove byte consistency relative to the recorded digest. They cannot prove
capture freshness, authenticity, semantic sufficiency or that an agent performed
a claimed action. Inspect the actual response, screenshot, trace or state result.

## Resources and cleanup

Record each created resource with its exact id, owning case_id, description,
disposition and observation. Dispositions are removed, restored, retained,
failed or pending. Preserve the reason and owner when cleanup cannot complete.

Set cleanup_reviewed and a concrete cleanup_summary only after checking the
run's resources. If the run created none, state that. Outstanding or failed
cleanup remains visible and prevents candidate readiness. Never delete another
run's records or real customer data to satisfy this field.

## Limits of the decision

A valid ledger can describe a failed or incomplete product. Candidate readiness
requires completed selected obligations, sufficient proof depth, consistent
source/runtime identity and resolved cleanup. It says nothing about journeys
missing from the declared inventory, undiscovered risks, an untested platform,
future uptime or a different deployment.

Preserve source tests, fixture execution, live browser/API operation, deployed
behavior and sustained field outcomes as distinct claims.
