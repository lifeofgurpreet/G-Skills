# AutoQA qualification

Version: 0.1.0. Date: 2026-11-05 (Pacific/Guadalcanal).

## Qualification scope

This record separates instruction behavior, deterministic helper correctness,
exported-folder operation and real-product outcomes. None substitutes for another.
The collection's ready status means this skill is implemented and reviewed for
distribution; it is not approval to release a product tested with it.

## Instruction comparison

Two fresh agents received the same three synthetic task records in
[requests.md](requests.md). Run A used the original Parcha skill at
c82883b15e5e8f02483bee513b3c8dcac48e3c9e; run B used this adaptation.
Neither received the answer key. A separate grader received labels A/B without
the source mapping and graded the answers against the 17 expectations in
[evals.json](evals.json).

| Supplied-record scenario | Upstream A | Adaptation B |
| --- | --- | --- |
| Metered-tool readiness, mismatched runtime and missing navigation | 6/6 | 6/6 |
| Worker cardinality, replay, deadline and cleanup | 5/5 | 5/5 |
| Returning-user mobile regression without live browser access | 6/6 | 6/6 |
| Total | 17/17 | 17/17 |

This is an honest tie. Both agents reached appropriate bounded conclusions,
preserved the observed failures and avoided inventing runtime evidence.
The grader found no failed expectation or critical factual error. Minor precision
differences did not change a rubric result.

These are three reasoning tasks using supplied records, not live browser runs.
There was one response per version and no statistical replication or automatic
trigger test. The task packet deliberately probes known failure boundaries; it
does not estimate general QA quality. Token usage and end-to-end agent timing
were not captured. The comparison establishes no improvement multiplier.

[trigger-cases.json](trigger-cases.json) contains routing examples for future
evaluation; their presence is not a measured trigger-accuracy result.

## Executable acceptance

The final selected-skill integration command was:

    TMPDIR=/data/tmp python3 tools/validate.py --skill autoqa

On Linux with Python 3.12.3 it exited 0:

- 54 AutoQA CLI regression tests passed.
- 90 shared collection tests passed across study, catalog, package, roadmap,
  installer and native-frontmatter checks.
- The exported-folder cold check passed using isolated Python subprocesses and
  only the shipped skill files plus the license. It exercised init, an incomplete
  report, attachment, a complete synthetic ledger, tamper rejection and refusal
  to reseal altered evidence.

Regressions cover missing cases and selected inventory, required deselection,
selected optional outcomes/depth, no-witness passes, health-only and guardrail-only
runs, safely unavailable journeys, wrong run/runtime/case bindings, altered files,
duplicate input, nonregular files, unsafe paths, cleanup, source/runtime mismatch,
Markdown output safety and bounded structured CLI failures. Tests execute the
actual command-line entry point; they do not merely search instructional phrases.

An independent reader reviewed the helper and reproduced rejection of a FIFO
plan input. No unresolved blocker was found in that bounded review. The reviewed
helper SHA256 was
4c67bb89849652f704de5b80d4c26b08cd361affac9a04eb5aa6914652644f06.
This was source review plus one synthetic I/O reproduction, not a live-product test.

## Static review

- Gitleaks scans of the skill and its collection hooks both exited 0 with no findings.
- UBS exited 0 with zero critical findings, 31 warnings and 233 informational
  diagnostics. The warnings were reviewed: 16 fail-fast JSON reads in tests and
  package checks, 14 duplicated rules about deliberate exact JSON type checks,
  and one low-level open immediately owned by an fdopen context manager.
  A missing test-suite timeout was fixed; a fixture parameter was renamed to make
  clear that it denotes an evidence ID rather than a credential.
- SkillSpector 2.13.1 with no LLM passed its existing gate with no blocking
  findings. Four nonblocking findings remained: a prohibition on storing access
  tokens; no tool-permission declaration; bounded local subprocesses in tests;
  and standard MIT warranty wording. The permission-declaration finding is an
  explicit portability choice: this skill grants no tool preapproval and follows
  the invoking host's permissions. No scanner rules were suppressed or weakened.

A passing scanner is not a guarantee that all defects or secrets were found.

## Package, installation and remaining limits

The actual immutable archive and native-client discovery have their own
[collection qualification receipt](https://github.com/lifeofgurpreet/G-Skills/blob/main/docs/skills/autoqa/QUALIFICATION.md).
An exported-folder test is not, by itself, proof of native discovery.

Artifact hashes establish consistency with recorded hashes, not authenticity,
freshness or semantic sufficiency. Source/runtime identities and cleanup statements
remain attestations that must be supported by actual observations.

Two real-project trials remain open as gs-05x in the owning roadmap. They must
include completed journeys, a failure or interruption, actual evidence, cleanup,
coverage gaps and false positives. This version makes no live-product outcome,
cross-platform certification, automatic-trigger accuracy or tenfold improvement claim.

## Selected guidance

The pinned Parcha source supplied the starting workflow and is attributed in
[upstream-review.md](../references/upstream-review.md). The G-Skills improvement
method informed artifact checks and distinct outcome claims. Selected entry-point
sections of reality-check-for-project, browser-testing-with-ntm and
browser-proof-standard informed workflow boundaries. Their complete frameworks
were not executed and their bodies are not bundled.
