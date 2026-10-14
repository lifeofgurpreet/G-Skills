# VPS Health 0.8.0 — usable support and verified project discovery

This pass removes first-use/publication friction rather than expanding the
roadmap. G-Skills remains an independent-skill collection; the new diagnostic
command and viewer operation belong only to VPS Health.

## What is implemented

`support-report` constructs an offline, opt-in projection for getting help. It
contains installed software/source identifiers, coarse platform information,
categorical readability/asset/runtime checks and aggregate record counts. It
does not redact a copy of the workspace or search logs for possible secrets.
Paths, node/host identities, provider/plan/account details, endpoints and hashes,
credential-variable names/values, measurements, raw errors, observation timestamps
and run identifiers are absent by construction.

The workspace argument is optional. Broken config, an absent database or malformed
runtime state produces explicit partial/unavailable fields rather than fabricated
healthy defaults or a private traceback. The operation performs no collection,
network request or mutation of the observation directory. Optional output uses a
private exclusive-create file outside that directory. It never sends anything.
Counts and software identifiers still require user review before sharing.

The live viewer offers a Support report download through a fixed read-only
same-origin route. Host/Origin restrictions and no-store headers remain enforced;
query parameters cannot request raw data. A failed download does not fall back to
logs or upload anything. The normal Save summary operation is clearly distinguished
from a public support report because it retains node context.

Seventeen new Python cases exercise all of these boundaries, including deliberately
injected private values, missing/corrupt state, unchanged on-disk files, endpoint
hash exclusion, strict output location and actual HTTP readback. Browser checks
exercise the real download and failed-response path. The added header action
initially overflowed the 320-pixel viewport; the existing layout test caught it.
The corrected mobile header wraps and uses the same icon/label treatment as its
other actions. No contrast, touch-target or layout assertion was relaxed.

## Native discovery — what actually ran

Four real Claude Code 2.1.300 sessions used the same existing protected account
route and private project-local `.claude/skills` installation. Personal skill
folders were not edited. The installed release began at v0.7.3 and was later
upgraded to the actual v0.8.0 candidate archive.

1. A fresh session listed and invoked `vps-health` through its native Skill tool.
   Its first shell attempt then hit an unavailable required sandbox dependency
   (`socat`). No workspace or monitor was created. This is discovery success and
   **execution blocked**, not a successful setup trial.
2. After the collection installer removed that private installation, a fresh
   native session no longer listed the skill. Its retained recovery copy was not
   discovered as a second active skill.
3. After installer restoration, another native session found and loaded the skill,
   read its version as 0.7.3 and preserved the no-physical-host-attestation boundary.
4. After upgrading to the actual 0.8.0 candidate, a new native session loaded that
   version and accurately described `support-report` and its sharing exclusions.
   It was a read-only upgrade-discovery check, not runtime execution.

The command requested dontAsk; the host's effective policy reported default.
That effective policy was retained. No sandbox exception, blanket bypass, account
switch, host dependency installation or copied credential was used to obtain a
passing result. The earlier model suggestion to disable the sandbox was not acted
on. A model result labelled success is not used as an execution verdict; the
native tool outcomes, absence of a workspace and independent installation state
provide the evidence.

The sanitized [project-discovery receipt](../../project-discovery-2026-10-15.json)
records trace hashes, source versions and these distinct outcomes. Full transcripts
and test paths remain private. The earlier v0.7.2 explicit-entry setup/stop trace
is separate evidence. It does not automatically certify the current sandbox or
all clients. Codex and completed sustained pilots remain open qualification work.

## Public-facing preparation

The collection has privacy-aware bug/feature forms and a support entry point.
`docs/preview.md` names the tested scope and outstanding client/field boundaries.
The installed skill has a self-contained support guide, and its README no longer
uses repository-relative links that break when distributed alone. A normal user
should ask the coding agent to do routine setup and gather the small support
report, not hand-edit config or upload an entire private workspace.

The work is suitable for a labelled technical preview. It is not a declaration
that the full `gs-2uh.13` wider-promotion gate has passed. The native discovery part
of `gs-nah.2` is qualified for the tested Claude/Linux project route; unsupported
clients are not silently added. `gs-nah.3` records delivered preview/support
materials, not permission to post or contact people.

## Release verification

The complete Python suite passed 370 tests (353 previous + 17 support cases).
The browser suite has 30 actual-loopback scenario groups, with 12 chart-adapter
contracts. Final acceptance requires the complete exact-source suite and both
Python 3.10/3.12 CI jobs to pass. The actual selected archive must be extracted and
exercised through the support operation and the existing owned runtime/recovery
checks. A previously passed source hash is not substituted for the published one.

A direct discovery check only read SKILL.md and the support reference. Their hashes
are compared with the final source separately from runtime/UI qualification. The
first candidate archive preceded the mobile layout correction; no claim is made
that that earlier archive alone proves the final page layout. The final archive
and browser receipt establish those other boundaries.

The current pass starts no long-running field pilot, sends no provider message,
posts no public promotion, changes no production settings and modifies no personal
skill installation. Disposable test workers are stopped by their owning fixtures.

## Applied references

Selected installed JSM release-preparation and README guidance plus pstack
actual-output verification and structural lessons informed the implementation.
Paid skill bodies are not included and no complete external scoring framework or
independent security audit is claimed.

Official [Claude Code skill discovery](https://code.claude.com/docs/en/skills),
[CLI options](https://code.claude.com/docs/en/cli-reference) and
[Codex skill documentation](https://developers.openai.com/codex/skills/) were checked
for the integration model. Actual local client behavior and its restrictions are
reported separately from documentation. The supplied Gemini reviews remain mapped
to implementations and open/rejected proposals in GEMINI-REVIEW.md; no unsupported
physical-host proof or automatic downtime authorization was reintroduced.
