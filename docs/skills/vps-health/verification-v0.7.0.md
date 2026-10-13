# VPS Health 0.7.0: reviewed guest context inside a multi-skill collection

## Both supplied reviews were read

Earlier reports saying no Gemini text had been supplied were incorrect. Both
attachments were present. Their full forensic groups, code, migration claims,
ticket template and replacement skill proposal are reviewed in
[GEMINI-REVIEW.md](GEMINI-REVIEW.md), with source hashes and explicit dispositions.
The source proposals and our technical corrections are not conflated.

Useful ideas implemented: same-window storage/pressure correlation, per-device
request means, guest memory activity, networking counters, guest CPU/clock traits,
retained raw observations and before/after comparison. Unsupported causal claims
are not copied into the decision engine. Identical traits do not prove a fake
migration; changed traits do not attest a physical host. Active CPU/RAM/fsync/
network probes are not passive merely because they need no package installation.

## What actually changed

The new `vps_forensics.py` performs bounded file reads only. It has no shell,
external network or active benchmark invocation. Permission failures, absent
sources, counter resets and undefined values remain explicit. The existing local
collector stores this optional context alongside CPU samples; source hashing,
private SQLite retention and the current decision rules remain in place.

Disk identities use major:minor and root mount context, not trailing-digit
stripping. Mean request times use the appropriate read/write cumulative times
and completed operations; no completed operation means unknown latency. Layered
devices are kept distinct. PSI ratios use the aligned cumulative total counters.
Softnet fields are hexadecimal and time_squeeze is not named vCPU preemptions.
Memory activity is guest-visible, not a claim to measure host swap or EPT.

The dashboard's optional diagnostics panel displays the latest retained context
and its freshness/quality. Missing older or Prometheus-only context remains missing.
Malformed diagnostic data is refused before replacing a valid screen; it cannot
turn a CPU HOLD into a pass. Raw snapshot and compare CLI outputs are private,
exclusive-create files. No migration ledger or provider ticket is mutated.

## Executable proof

The forensic suite has 28 tests, including exact parsing, NVMe/mapper/overlay
identity, reset/absence behavior, idle latency, independent clock brackets,
non-aggregation across device layers, hexadecimal softnet, balloon deltas,
non-attesting changed/identical traits, private output and retained SQLite/UI state.
The existing accounting, operator and actual Linux process tests remain intact.

The collection test suite adds unrelated temporary skills, independent versions,
selected packages, draft rejection, owned hooks and immutable-tree checks. A new
regression reproduced a large unrelated skill exhausting the old whole-repository
archive budget. Selected packaging now reads only the chosen skill, its owning
maintenance hooks and license. A different skill does not contribute that size
or enter the release archive.

Across shared and VPS checks, the source suite passed 255 Python tests. The
pure chart adapter retains 12 contracts. The actual-loopback browser suite has 29
scenario groups, including guest context, unknown idle latency, malformed refresh,
unchanged CPU decisions and the existing owned-agent stop flow. Exact release-head
CI and immutable archive validation are required before publishing; these counts
are not a substitute for the recorded pass/fail result.

A separate authorized Linux smoke run completed two bounded passive collections:
the forensic route and the existing CPU route with optional context. The first
retained 14 device rows and no context-quality failure; the CPU route retained one
measured interval with context. The compare command returned physical migration
NOT_ESTABLISHED_FROM_GUEST_EVIDENCE, as intended. Raw host records stayed private.
This proves the read/retain/compare paths, not sustained hosting performance.

An early in-progress validation overlapped source edits and is not used as release
proof. After freezing the source, the complete current checks and real browser
flow passed. No failure was converted to a success by relaxing measurement
thresholds or dropping existing runtime tests.

## Scope and open work

This is one skill in G-Skills, with an independent manifest and release tag
`vps-health/v0.7.0`. Collection infrastructure is tracked in `gs-ekd`; reviewed
Gemini extension work in `gs-8cq`. Existing `gs-2uh` agent/client/field gates remain
under VPS Health and retain their statuses/dependencies.

Active experiments with explicit budgets/baselines, wider authorized SSH/path
collection, actual client/connector qualification and multi-day operation are open
acceptance work. No universal CPU-model score table, physical-medium grade,
provider-guilt verdict, reboot permission or automatic mail sender was added.

Applicable installed JSM pattern-extraction/planning guidance and pstack
verification/ownership principles informed the scope split and tests. No claim is
made that a full external framework, independent reviewer or every installed
skill was executed, and no paid skill bodies or private fleet records are published.
