# VPS Health 0.7.1 — retry correctness and honest client qualification

## User outcome

An agent repeating an unchanged existing-monitoring setup should reuse the approved
workspace rather than ask the human to rebuild configuration. A changed target is
a different case and must remain blocked. This patch changes that route handling;
it does not change CPU accounting, thresholds, workload interpretation or external
action permissions.

## Failure reproduced before implementation

Six regression cases were added against the released source. Two failed: repeating
the same profile/endpoints after bootstrap, and auto-resuming while explicitly
supplying the matching route. The previous implementation rejected the presence
of those flags, without checking whether the scope actually changed.

The fix compares validated asset content and normalized endpoints to the retained
configuration. Omitted inputs use the stored route and do not need the original
profile file. Different endpoint, inventory, credential-variable name or newly
enabled HTTP allowance remains a refusal. No saved config or credential is changed
by planning. Existing generation-bound budget/stop rules remain intact.

A further real loopback metrics fixture starts the actual managed worker, repeats
the same explicit route, confirms the same run identity and deadline, and verifies
that the endpoint's empty dataset is still HOLD. This is a synthetic metrics service,
not a production monitoring endpoint or provider-performance test.

## Client-journey artifact evaluator

The developer-only `client_journey.py` creates a private test directory from a
reviewed skill archive plus manifest. It starts no client, connects no account and
runs no monitoring during preparation. Its checks use the installed bytes, real
owned process state, matching loopback HTTP response, retained capture hashes and
same-run stop/continuation. A success message cannot substitute for those artifacts.

The evaluator refuses changed installed source, extra unrecorded scripts, mismatched
archive hashes, oversized archives, symlinked workspaces, non-loopback addresses,
HTTP redirects, missing stop evidence and replacing a continuation with a new run.
Receipts are exclusive-create/private. Its own successful result deliberately says
ARTIFACT_VERIFIED, `native_client_verified: false` and `semantic_review_required: true`.
A local integrity hash is not independent attestation against control of the
whole host or its trusted inputs.

Thirteen evaluator tests include actual bounded Linux workers and negative cases.
They prove the evaluator, not Codex/Claude behavior. Fresh native model-driven
client qualification was not completed this pass; available executable/version
information and incomplete preflight do not satisfy it. No alternate account or
permission/sandbox workaround was used. The dedicated native-client gate remains
open, with the artifact tool and [procedure](client-qualification.md) ready for it.

## Quarter plan and task graph

The collection's new programme is `gs-nah`; VPS work remains under `gs-2uh` and
`gs-8cq`. Seventeen scoped tasks have native owner roles, target dates and month
labels spanning 2026-10-14 to 2027-01-14. Root and VPS roadmaps render the live
native fields, not copied progress values in a second tracker. Six roadmap tests
check scoping, native owner/date display and complete scheduling of current open
work. The old dependency making basic client qualification wait on Gmail/OAuth
is removed; actual connector/action tests remain separately open. The narrow
passive-preview gate gs-2uh.13 depends on actual client, pilot, safety and clean
installation acceptance; it does not wait for all optional features.

The [quarter plan](../../plans/2026-10-14-quarter.md) distinguishes a narrow,
evidence-backed preview from completion of every optional feature. Install/upgrade,
real-client, safety and sustained-pilot acceptance are review gates. Target dates
create no automation or authority to post, email, announce or change a server.

## Verification boundaries

The initial full run passed 281 Python tests and 29 real-loopback browser scenario
groups, including the 12 chart contracts exercised by the browser entry. The added
live metrics-route case passed separately; final exact-head CI must run the complete
282-test Python suite before this source is accepted for release. A later source
hash cannot borrow an earlier green status.

Release acceptance also builds the actual selected skill archive and exercises
its cold startup/status/stop routes. The client evaluator is then run against that
artifact with deterministic fixtures, not relabelled as native model execution.
Existing user observations remain private; public examples and endpoint responses
used for these checks are synthetic. No managed test worker is intentionally left
running, no multi-day pilot was started, and no provider contact or host rollout
was performed.

## Applied research

Selected sections of installed JSM `testing-conformance-harnesses` informed the
separation of process/contract checks from client behavior and the coverage matrix.
Installed pstack actual-output verification, subtraction and structural lessons
informed a small owning fix instead of another monitoring or model-runner layer.
No paid skill text is republished and no full external rubric or independent-agent
review is claimed. Official client documentation is linked in the qualification
procedure and was treated as capability reference, not runtime success evidence.
