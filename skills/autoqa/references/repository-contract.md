# Repository and execution contract

## Discovery order

Read applicable instructions before AUTOQA.md, even on a familiar repo.
Use source and runtime observations to establish current behavior; use acceptance
criteria and specifications to establish intended behavior. Record disagreement
as a gap rather than letting current code erase the requirement.

1. Parent/repository AGENTS.md and the selected skill's local guidance.
2. User acceptance criteria, product journeys and existing issue/task graph.
3. AUTOQA.md or docs/AUTOQA.md, README and operational runbooks.
4. Package scripts, service definitions, CI/verification contracts and fixtures.
5. Changed routes, handlers, background jobs, schemas and tests.

Use rg/rg --files for bounded discovery. Read environment samples for variable
names only. Do not dump process environments, auth files, cookies or secrets.

## Scope and source identity

Resolve the base from the user-specified range or existing change record.
Otherwise use the default-branch merge base when it produces a meaningful diff.
On main, an empty diff does not mean nothing needs QA: use the requested recent
range if known, or a critical-journey pass with an explicitly stated scope.

Record the exact candidate commit, reviewed base, relevant dirty state and a
digest of the scoped source snapshot when uncommitted work is included. Do not
label a dirty runtime as the clean commit. Hash relevant non-secret files only;
raw patches can contain secrets and do not belong in public evidence.

Compare source fingerprints at start and finish in a shared checkout. If another
agent changes a tested path, determine affected cases and capture a new run.
Keep unaffected observations with their original provenance. Do not switch
branches, stash another agent's work or create a second checkout unless the
repository explicitly requires isolated verification.

## Runtime identity

Capture identity from the target instance or its existing deployment record.
Distinguish a commit, built artifact/image digest, deployment ID and environment.
A URL, timestamp or local branch name does not prove all four.

A production instance at commit A cannot qualify candidate B. The report can
describe A while candidate readiness stays blocked. Unknown build identity is
an explicit limit; do useful observational QA without inventing an identity.
Do not expose a new production version endpoint merely to satisfy this skill.

## Local configuration

For repeat work, propose or update AUTOQA.md in the authorized repository. Keep
mutable host facts there, not in this public skill. A useful config records:

- run and health commands from the actual runbook;
- target environment and a method to observe build identity;
- supported roles and approved synthetic fixture creation/cleanup;
- critical user journeys and their source;
- native test commands and browser/API/CLI adapters available;
- time, provider-job and resource limits;
- private evidence destination and publication policy.

Use placeholders for credentials. Do not store access tokens, real user records,
saved browser state, private host topology or signed URLs in the config.

## Work with existing skills

| Need | Delegate or refer to |
| --- | --- |
| Strategic gap against project vision | reality-check-for-project, if installed |
| Several coordinated browser testers | browser-testing-with-ntm, if installed |
| Browser acceptance standard | browser-proof-standard or the repo's own rule |
| Project-specific QA or incident recovery | The owning project's skill/runbook |
| Issue ownership and shared files | Existing Beads/Agent Mail or equivalent |
| Landing and promotion | The repository's delivery contract |

These are optional integrations, not installation dependencies. Read only the
relevant installed guidance. Do not copy third-party skill bodies or recreate
their orchestration and deployment machinery.

## Findings and task graph

Give each finding a stable local ID and affected case IDs. Record observed result,
expected outcome, reproduction, impact, severity, evidence and next action.
Distinguish observed facts from suspected causes.

Deduplicate against existing tasks by affected journey and root cause. Add a
regression criterion to the owning task. Close a runtime outcome only after that
outcome is witnessed on the relevant version; code presence and a source test
are different receipts.

Use existing task commands when writes are part of the authorized work.
Publication to people, issues or PR comments is a separate action unless the task
already authorizes it. Never publish raw captures by default.
