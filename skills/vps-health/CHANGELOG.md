# VPS Health changelog

## 0.9.3 — Qualify context by its own measured time

Sparse/stale quiet pressure or throttling averages no longer describe a long CPU
window as complete workload context. Expose independent channel durations and
freshness, time-weighted bands, gap-separated shortfall runs and recorded-execution
context in private status/report outputs. One existing interval-weighting owner is
shared; no new CPU threshold or provider attribution is introduced. The bounded
`evidence-report` operation and Markdown exports retain denominators. Extra inline
coverage widgets remain pending; the existing workbench uses the corrected finding.


## 0.9.2 — Dated, usable provider context

Add Vultr, OVHcloud and netcup across the offline provider command, private asset
profiles, managed planning and workbench. Reference age belongs to each fact or
diagnostic source; new catalog edits do not make older guidance current. The
workbench now displays existing support diagnostics and their dates, preserves
expanded readings and refuses mismatched provider links.

This release does not include the unpublished 0.9.1 remote-viewer draft. CPU
measurement, thresholds and action permissions are unchanged. Sparse workload-
context qualification remains an explicit open defect (`gs-2uh.15`), not a fix
claimed by this provider tranche.


## 0.9.0 — Evidence workbench (technical preview)

Rebuild the working viewer around the selected finding, one canonical next action,
linked accounting/workload charts and observed coverage. Add a pinned full-window
review, exact private agent handoff, local Cmd/Ctrl+K navigation and pause/resume
for the view alone. Provider disclosures persist across refresh. Mobile navigation,
modal focus, synthetic export labels and snapshot/support distinctions are tested.

Full artifact checks exposed a concurrent private status-read failure; validate and
read one opened inode with bounded atomic-replacement retries rather than weakening
privacy checks. No CPU threshold, provider-contact permission or collector schedule
changed. Existing field pilots remain independent installations and are not upgraded
by this source release. The separate provider-diagnostics guidance below is retained.


## Unreleased — Provider diagnostics guidance for support tickets

Add Contabo's primary diagnostics article (MTR and traceroute for a ticket, reviewed
2026-10-15) as a validated `diagnostics` catalog entry, and a short providers.md
section on peer-matrix interpretation and ticket contents. MTR and ping remain
active probes that need scoped approval; nothing runs or sends. Collection,
thresholds and permissions are unchanged. The opt-in network workflow, matrix
tests and ticket template are later slices (issue #20).

## 0.8.0 — Minimal support reports and a clearer preview boundary

Add `support-report` and a matching live-viewer download that include only software
identifiers, categorical checks and aggregate counts. No private paths, subjects,
endpoints, credentials, raw errors or observations are exported; nothing is sent.
Broken or absent workspaces still produce a truthful partial support summary.
Document native project discovery separately from current execution constraints,
and keep the installed README's repository links usable outside a checkout.


## 0.7.3 — Recoverable setup and private evidence boundaries

Initialize in a private retained stage and publish only complete workspaces. Retry
an interrupted first setup without deleting the original files. Refuse linked,
exposed or nonregular state; bounded JSON reads cannot hang on a FIFO, and new
captures ignore permissive umasks. Preserve SQLite rollback journals and verify
transaction recovery. Owned shutdown no longer requires valid configuration;
installed Python changes stop a worker for review before another collection cycle.
CPU decisions, provider permissions and collection-wide tooling are unchanged.


## 0.7.2 — Agent-owned viewer verification

Add `agent-verify`: bounded literal-loopback readback matched to the actual worker, configuration and declared subjects. No redirects, proxy routing or generic shell/curl permission is needed. Stopped, changed and mismatched runtimes remain NOT_READY. Collection and diagnostic thresholds are unchanged.

## 0.7.1 — Safe existing-monitoring retries

Repeated setup may supply the same approved Prometheus/Loki route and profile without being treated as a scope change. Actual endpoint/inventory/credential-variable mismatches remain refusals, and retained configurations work without the original profile file. Measurements, thresholds and action permissions are unchanged. A separate developer artifact evaluator supports cold/resumed client qualification but does not claim native-client completion.

## 0.7.0 — Reviewed guest diagnostics

Passive storage, memory, network and guest-trait evidence from the reviewed Gemini proposals; explicit snapshot/compare limitations and retained dashboard context. CPU thresholds and external-action authority are unchanged. Future releases use `vps-health/vX.Y.Z` within the G-Skills collection.

# Changelog


## 0.6.0 — Agent-owned execution

- Bounded, idempotent plan/start/status/stop workflow with a detached Linux worker,
  actual process identity checks, collection ownership and private agent handoff.
- A stopped/completed run cannot silently renew its original approval hash; a new
  run is a new scoped plan. Configuration changes stop for review.
- Agent activity and capability needs in the existing read-only dashboard.
- Host-native connector request/result contract; read, draft and send remain
  distinct, and a local receipt is never treated as OAuth or send permission.
- Native Beads epic and generated, validated dependency graph for remaining
  real-client, connector, platform, estate and multi-day qualification.



## 0.5.0 — The operator journey

- Read-only `doctor`, shared CLI/dashboard `brief`, and dated `providers` reference commands.
- A redesigned workbench with an interval evidence ribbon, prioritized attention inbox, setup routes and provider guide.
- Opt-in, current-viewer-only desktop notifications; stable findings deduplicate refreshes and resolved incidents can recur unread.
- Separate explicit plan-question and evidence-gated performance-review draft purposes. No sender or automatic host actions.
- Original first-hour and agent handoff playbooks; provider allocation, sustained-use allowance and credits remain distinct.
- Actual ZIP checks include operator assets and cold doctor/brief/provider routes. Existing CPU policy and raw measurements are unchanged.


## 0.3.0 — Operator workbench and repeatable skill research

- Replace the dark pastel card stack with a neutral, responsive workbench, selected-node history, next-check context, searchable/filterable inventory and actual evidence/activity navigation.
- Preserve chart bucket extrema and unknown-span breaks; the former stride sampler could hide short deficits and invalid intervals. Retained measurements and assessment thresholds remain unchanged.
- Keep the last valid view on malformed or failed refreshes; preserve selection, expanded limitations and keyboard focus. Add larger phone controls and local JSON summary downloads.
- Add a private-only local skill-study plan, an original applicability method and an explicit seven-source research receipt. Indexing is not a claim of reading or applying every installed skill.
- Add actual-loopback Playwright CI alongside the Python and standalone-folder checks. Browser tooling is developer-only; no new runtime stack, external assets, sender or deployment capability.

Compatibility: existing workspace format remains v1. A collector source/version
change is a measurement-epoch boundary; retain prior code and private history
instead of silently pooling different methods. Summary downloads are not raw
workspace backups. No automatic migration or timer installation occurs.


## 0.2.0 — Private monitoring workspaces

- Guided demo, one-node Linux and existing Prometheus/Loki bootstrap.
- Persistent private SQLite history, idempotent overlapping captures, method/host identity separation and measured-time coverage.
- Self-contained dashboard, read-only loopback live view, UTC daily summaries and immutable summary exports.
- Explicit bounded foreground watch; generated-only systemd user timer files.
- Concise opt-in human-review drafts with real UTC windows, evidence safeguards and non-sendable examples; no sender.
- Workspace learning proposals retain whitelisted categories only; no automatic code or policy changes.
- Regression coverage for stale/empty/failed observations, policy windows, capture boundaries, privacy and actual HTTP collection.


## 0.1.0 — 2026-10-13

First public VPS investigation skill. Includes passive Linux capture, bounded Prometheus/Loki reads, deterministic local reports, safe comparison, manifest verification and sanitized learning proposals. Includes provider documentation and explicit human-only contact/change boundaries. This is an investigation toolkit, not deployed multi-provider certification or an automatic attribution engine.


## 0.4.0 — Linked chart investigation

- Embed reviewed uPlot 1.6.32 locally with MIT attribution and integrity checks.
- Align accounting/execution and pressure/throttling charts with range buttons,
  drag zoom, synchronized inspection, keyboard data access and PNG/CSV export.
- Preserve independent channel extrema/unknowns; keep assessment policy unchanged.
- Add deeper JSM/Emil/pstack application receipts and invariant/adapter tests.
- Validate real standalone ZIP shape, dependency licenses and cold bootstrap.
