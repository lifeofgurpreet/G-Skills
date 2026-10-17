# VPS Health v0.11.2 — technical finalization receipt

Owning task: `gs-2uh.21`. Receipt date: 2026-10-17. **Technical Preview remains
the support level.** The candidate repairs reproduced historical and optional-source failures,
makes installed recipes executable, and makes the agent artifact contract fair
and explicit. Source, extracted-package and browser acceptance pass.
[VPS Health v0.11.2](https://github.com/lifeofgurpreet/G-Skills/releases/tag/vps-health/v0.11.2)
was published as a Technical Preview on 2026-10-17 at 09:12:53 UTC. The downloaded
published ZIP and manifest match the tested candidate byte for byte.

The exercised source is
[`08f78f5b070d60678678b01b479b6a7637ac7fcf`](https://github.com/lifeofgurpreet/G-Skills/commit/08f78f5b070d60678678b01b479b6a7637ac7fcf),
including the installed-documentation correction in
[`09be2cc2bd2a415215226105f2c9bffb397c6611`](https://github.com/lifeofgurpreet/G-Skills/commit/09be2cc2bd2a415215226105f2c9bffb397c6611).
Both are on public `main`.
[Exact-source CI](https://github.com/lifeofgurpreet/G-Skills/actions/runs/39019013695)
completed successfully: Python 3.10 verification, Python 3.12 verification,
catalog, VPS Health JavaScript and VPS Health browser jobs. This receipt binds
that source to the tested ZIP and to the separately downloaded published bytes. The adjacent
[machine proof](finalization-proof-v0.11.2.json) contains hashes, counts, retained
synthetic decisions and explicit evidence boundaries.

## Restore measured overlap without inventing time

The published v0.11.1 archive created one retained synthetic workspace. Both
archives then read that same workspace for a requested 100-second window wholly
inside an existing 300-second observation. The old report selected by sample end
timestamp and omitted the observation; it returned zero observed seconds, a null
mean and no observation hash. The candidate returned 100 observed seconds, a
mean of 0.5 and the original stored sample hash. All six retained files remained
byte-identical across the comparison. The replay is a read correction, not a data
migration or a fresh measurement.

| Same requested window | Published v0.11.1 | Candidate v0.11.2 |
|---|---:|---:|
| Requested seconds | 100 | 100 |
| Observed seconds | 0 | 100 |
| Accounted ratio mean | null | 0.5 |
| Original observation hashes present | 0 | 1 |
| Retained files changed | 0 of 6 | 0 of 6 |

An explicit historical window now reads a bounded set of later-ending candidates
and projects them through the existing interval owner, in timestamp order. Only
the selected overlap reaches the report, chart timestamps and freshness fields.
Summary and provenance use the same SQLite read transaction, and provenance comes
from the exact selected segments. The ordinary live-status cutoff remains at the
requested current time. Legacy Prometheus durations remain capped by their fixed
five-minute source window; a stored coarse step cannot reach farther backwards.
Invalid and conflicting overlap remains invalid evidence rather than disappearing
into an apparently innocent gap. These behaviors are covered by
[eight report-boundary regressions](../../../skills/vps-health/tests/test_time_evidence.py).

The first proposed correction was insufficient. Its per-row overlap filter
removed a future row that did not itself overlap the report but still advanced
the interval owner's cursor. A later long interval then acquired 150 seconds that
the established ordering rules did not own. Independent source review identified
that counterexample; an eighth failing regression led to the final bounded,
ordered projection of all candidates. The receipt preserves this unsuccessful
attempt because it explains why a simpler-looking filter was rejected.

Clipping an interval average does not remeasure its sub-intervals. This change
does not certify underlying Prometheus scrape completeness, reconstruct a past
monitor's ingestion state or prove a provider cause. The installed
[time-evidence method](../../../skills/vps-health/references/time-evidence.md)
and [query-window method](../../../skills/vps-health/references/prometheus-windows.md)
remain the interpretation boundaries.

## Contain optional-source failures and retain their evidence

Two separate archive comparisons reproduced fleet-level crashes in v0.11.1:
an optional metric timestamp too large for finite-number conversion raised
`OverflowError`, and a null Loki stream raised `AttributeError`. The candidate
returned both declared synthetic subjects in each case, with 13 valid CPU samples
per subject. The affected optional channel was recorded as an error; the second
subject remained available without errors.

The shared finite-number validator now converts unrepresentable JSON numbers
into the existing `InvalidEvidence` boundary. The Loki parser validates response
and stream containers, string labels, entry shape and text, bounded nanosecond
timestamps, the requested time range, backward ordering and the total 500-line
budget. Empty results and duplicate timestamps can remain valid. Reaching 500
lines explicitly marks history incomplete; exceeding the requested limit is
invalid. Raw responses are retained before interpretation, and logs remain
untrusted diagnostic data. The response assumptions are grounded in
[Grafana's Loki range-query contract](https://grafana.com/docs/loki/latest/reference/loki-http-api/#query-logs-within-a-range-of-time).

The differential archive replay used controlled `get_json` responses. It proves
the old/new parser behavior, not network transport. A separate committed
`test_real_http_malformed_optional_sources_survive_capture_and_ingestion` made
**16 actual loopback HTTP requests**, exercised both malformed optional sources
together, ingested the returned captures and read them back from compressed
SQLite storage. It checked preservation of the malformed raw bodies, valid CPU
samples and both subjects. That test is one of the
[six new optional-source regressions](../../../skills/vps-health/tests/test_prometheus_windows.py).
Neither route is a live customer endpoint or an independent PromQL engine test.

## Make the installed path the usable path

[Bootstrap](../../../skills/vps-health/references/bootstrap.md) and
[improvement](../../../skills/vps-health/references/improvement.md) recipes now
resolve a quoted absolute `VPS_HEALTH_CLI` from the installed `SKILL.md` location.
They no longer require the collection's parent directories. The agent keeps that
assignment in the same invocation or passes the resolved executable directly.

The package regression extracts the skill into a path containing spaces and runs
the documented synthetic bootstrap and `learn` commands from an unrelated working
directory, with Python site-packages disabled. It verifies the actual dashboard,
the `PROPOSED_NOT_APPLIED` proposal, unchanged retained workspace bytes and an
untouched unrelated directory. A second regression ensures the package checker
rejects repository-relative runtime commands inside fenced examples, before
fences are removed for local-link validation. See the
[installed-package tests](../../../tools/skills/vps-health/test_release_package.py).

The [operation guide](../../../skills/vps-health/references/operation.md) also
corrects two stale claims. Current `verify` recognizes workspace summary exports
and distinguishes their integrity from unavailable raw replay. Passive local
diagnostics include guest storage, memory and network context as well as CPU;
that scope does not certify application health, physical-host identity or every
underlying subsystem. A full release folder is required for installation.

## Make artifact requirements visible and preserve old trials

[Artifact contract revision 2](../../../skills/vps-health/evals/evals.json)
declares the requested `diagnostic_checks` mapping and the allowed mail-capability
values in the prompts. A support draft may describe diagnostics in ordinary
language; it need not reproduce the internal `chart_assets` identifier or pass
an undisclosed issue-keyword check. The machine decision must still copy exactly
the supplied diagnostic categories and states. Semantic review remains necessary
to establish that the prose addresses the actual issue.

For ambiguous delivery, the grader requires exactly `mail.read` for the next
operation. A string containing both `mail.read` and a send capability cannot pass
by substring. This checks a declared decision field; it neither grants access
nor performs reconciliation. Six new
[grader regressions](../../../tools/skills/vps-health/test_agent_eval.py) cover
these cases and contract identity.

The grader records revision and suite hash. Completed unversioned historical
tasks remain revision 1 and require their matching archived grader; the new
grader refuses to silently reinterpret those outputs. Blocked or no-inference
attempts retain their state, empty expectations and null score even under an
older contract. Changed prompts do not support a cross-revision improvement
score. The distinction between observed artifacts, traces and environment
outcomes follows the evaluation discipline described in
[Anthropic's agent-evaluation guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
and the installed [evaluation workflow](../../../skills/vps-health/references/evaluation.md).

## Fresh explicit-entry agent evidence

A fresh ChatGPT subagent read the installed skill, selected references, supplied
synthetic tasks and fixtures, plus the actual CLI capability/help output. The
executor snapshot excluded tests, expected-output definitions and grader
implementation; the user prompts and input fixtures were supplied separately.
This was logical separation of fresh context in a shared execution environment,
not operating-system isolation or a native Codex/Claude trial. The parent agent
reviewed the three actual decisions and the draft for meaning as well as shape:

| Task | Observed artifact outcome | Boundary kept |
|---|---|---|
| Sparse workload context | Computed 300 seconds / 72 hours as approximately 0.11574074% coverage; preserved `WITHIN_TOLERANCE` accounting and `CONTEXT_INCOMPLETE` context | Quiet five-minute subsets did not clear workload demand or establish provider responsibility |
| Local software support | Created a useful maintainer draft beginning `LOCAL DRAFT — NOT SENT`; copied the supplied diagnostic mapping and retained fixture version 0.9.3 | No connector, attachment or send; current runtime version 0.11.2 did not overwrite historical fixture evidence |
| Ambiguous email outcome | Kept delivery `UNKNOWN`, selected exactly `mail.read`, described reconciliation and declined a duplicate write | No connected mailbox was invented; the provider reply remained data |

The agent inspected `support-draft --help`. That command cannot import the
fixture's supplied minimal report and would instead obtain current diagnostics.
For this fixture-only task, the agent authored the draft directly and accurately
reported that the generation command had not run. The actual offline export was
not supplied, so the rendering problem was neither reproduced nor repaired.
This is useful artifact behavior with an explicit runtime limitation, not a
completed `support-draft` CLI trial.

The initial output-permission check found a pre-existing parent output directory
at mode 0755. The agent changed that output directory to 0700, retained private
case directories and verified output files at 0600. The four task/input files
remained byte-identical. The machine proof embeds the public synthetic decisions
and draft, with hashes but without execution-workspace paths. No native trace,
token count, paired-model comparison or benchmark score was fabricated.

The separate fresh ChatGPT lifecycle walkthrough executed a bounded synthetic
demo through the installed CLI. After an initial failed default-environment
start, an authorized loopback retry reached `RUNNING`; `agent-verify` returned
`VERIFIED`, with both process and HTTP checks true for three synthetic subjects.
The resumed invocation retained the same run ID, process ID, start time, plan
hash and deadline. The retained identity comparison records all five matches.

The successful run started at `2026-10-17T08:49:47Z` with a 60-second budget and
deadline `08:50:47Z`. An explicit owned stop at `08:50:42Z` produced `STOPPED`;
the final status had `process_verified: false`, `evidence_ready: false`, zero
cycles and zero failed cycles. The subsequent `agent-verify` correctly exited
1 with `NOT_READY` and `owned_worker_not_running`. This verifies start, actual
viewer readback, idempotent resumption and owned stop. The history was seeded
synthetically: no new collection cycle or 72-hour observation is claimed. This
short ChatGPT walkthrough does not close a native Codex/Claude journey gate.
After those process results were available, the parent ended optional follow-up
exploration and requested a concise handoff; that intervention is part of this
walkthrough's record.

## Acceptance by evidence layer

| Evidence layer | Result for the candidate | What it establishes |
|---|---|---|
| Source and whole collection | 671 Python tests across 26 groups; final full gate PASS | Existing collection checks plus 22 added regressions: 8 time-boundary, 6 optional-parser, 2 installed-package and 6 grader tests |
| Runtime and retained data | Actual CLI/process/HTTP/SQLite checks PASS; published/candidate replay PASS | Bounded local behavior, exact historical overlap and preservation of the same retained evidence |
| Actual package | Extracted 72-file archive acceptance PASS | Candidate built from immutable source; isolated CLI, owned stop and interrupted-initialization recovery |
| JavaScript | 45 contract checks PASS | Existing data and UI contracts rerun against this source |
| Browser | 58 actual browser groups PASS | Real loopback viewer, interaction, downloads, failure/recovery, time-qualified views and offline summaries |
| Hosted source CI | All five jobs SUCCESS at the exact source commit | Independent hosted execution of the configured gates |
| Fresh ChatGPT artifacts | Three synthetic decisions and one draft semantically reviewed | Explicit-entry reading, evidence interpretation, useful local drafting and honest access boundaries |
| Fresh ChatGPT lifecycle | Actual synthetic start, verify, same-identity resume and owned stop reviewed | A 60-second approved run reused its identity/deadline and stopped; seeded history and zero new cycles remain explicit |
| Native agent and field qualification | Remains open | No current-version native Codex/Claude qualification or representative completed 72-hour field claim |
| Release publication | Published and downloaded bytes verified | Release 415694740 targets the exercised source; ZIP and manifest equal the tested candidate, with 72 extracted files and an actual no-site-packages capability invocation reporting 0.11.2 |

The actual candidate ZIP is 298,588 bytes, with SHA-256
`7c6e92f1e3cb6e0b9cf4f4088efe46dd8acf21b1155c81ba69b97919f929c360`.
A second build and extracted acceptance on a separate authorized native Git host
also passed and produced that identical archive hash.
The browser receipt retains the exercised asset hashes and all 58 check names.
Simulated phone viewports are not physical-device qualification, and the current
counts are rerun acceptance rather than a claim that all checks are newly added.

## Retain the useful unsuccessful attempts

| Attempt | Observed result and disposition |
|---|---|
| Initial historical-overlap fix | Nonoverlapping future cursor barrier was omitted; a regression exposed 150 invented seconds. Corrected in the existing interval path and rerun successfully. |
| Default-environment loopback tests | Localhost binding was blocked. Authorized synthetic loopback execution subsequently passed. |
| First full gate after the version change | Generated roadmap drift was detected. The native task graph and roadmaps were regenerated as required, then the full collection gate passed. |
| Playwright 1.57 Chromium download | CDN attempts returned a corrupt/empty ZIP or gateway failure. The local browser run used official matching Chrome for Testing 143.0.7499.4 through the existing documented executable configuration; hosted CI also passed its standard browser setup. |
| Legacy Skill Creator quick validator | Rejected the valid `compatibility` frontmatter field. The official Agent Skills specification permits it and the repository frontmatter gate passed; valid metadata was preserved and the legacy validator is not counted as a pass. |
| GitHub Git Data tree creation | Integration returned HTTP 403 without a change. The existing authorized native Git route pushed clean `main`; no account or credential changes were needed. |
| Fresh artifact permissions | The first check failed on the parent output directory's 0755 mode. Its mode was corrected to 0700 and the artifact checks passed. |
| Fresh lifecycle planning/start | The first plan selected a 10-second interval and was rejected by the existing 60-second minimum. The corrected 60-second plan reached a default-environment start failure; a separate loopback bind probe returned `PermissionError`. The authorized retry used a new current plan after the failed run and preserved the successful run's original deadline on resume. |
| Documentation structure gate in the default environment | The private-output-location regression refused its temporary destination. The same unmodified gate passed in the already-authorized full-validation environment; this failed attempt is retained and not counted as a source pass. |
| Current installed-guidance hashes | A later remote request did not return them. Current hashes remain unavailable; historical hashes were not substituted. |

These are recorded failures or capability limits, not hidden successful checks.
No automatic approval-review rejection occurred in this pass.

## Guidance selection and original decisions

The review read JSM's
`agent-ergonomics-and-intuitiveness-maximization-for-cli-tools` lines 1–400 of
1,561 and the full 185-line `readme-writing` entry. It applied first-invocation
testing, the actual CLI path, actionable errors, structured results and practical
benefit-led documentation with visible limitations. The current installed
hashes were not obtained; this receipt records the actual read extent rather
than reusing a prior edition's identity. The inventoried reality-check entry
remained unread and is not claimed as applied.

The root reviewer read Flora Skill Creator in full and applied progressive
disclosure, inspection of real artifacts and fresh behavioral tasks with minimal
context and no exposed grader. Its legacy quick-validator limitation above was
resolved against the [official Agent Skills specification](https://agentskills.io/specification),
which explicitly includes `compatibility`; no source metadata was weakened to
please an outdated allowlist. No proprietary skill text is reproduced here.

The selected guidance was adapted to the existing implementation. Additional
wrappers, numeric quality scorecards, mandatory change quotas, repeated intake,
silent target or budget changes, curl-based installers, unverified comparisons
and arbitrary document-length cuts were rejected. The useful result is an
existing workflow that makes fewer false claims and asks less installation work
of its user. Deterministic test counts are evidence of checked behavior, not an
invented rating of the skill or its agents.

## Release verdict and remaining work

Version 0.11.2 is published within the documented Technical Preview scope.
Its source changes, technical acceptance and downloaded release bytes are
recorded here; the release retains its prerelease flag. The
[installed support scope](../../../skills/vps-health/references/support-scope.md)
and [native task roadmap](ROADMAP.md) retain the remaining outcome gates:
`gs-2uh.6` for native Codex/Claude journeys, `gs-2uh.8` for representative
multi-day observation and `gs-2uh.13` for broader promotion. Closing this scoped
finalization task does not close those gates.

The original passive v0.8 pilot was left untouched. Its owner-supplied deadline
is `2026-10-18T00:29:45Z`, still future on this receipt date; no fresh pilot read,
completion or current performance result is claimed. The public fixtures and
new walkthroughs are synthetic. This pass sent no provider or other external
message, changed no production system or account, started no new production
probe and published no social post. Publication of a software release, native
client qualification and sustained field usefulness remain distinct events.
