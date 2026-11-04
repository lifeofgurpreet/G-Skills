# AutoQA 0.1.0 package and installation qualification

Date: 2026-11-05 (Pacific/Guadalcanal).

## Published source and immutable package

The implementation was committed and pushed to main as
[66bc2653e1e8de2ea7a200b7eb273973afe9e38f](https://github.com/lifeofgurpreet/G-Skills/commit/66bc2653e1e8de2ea7a200b7eb273973afe9e38f).
The archive was built from that exact committed tree using the collection's
selected-skill package builder.

| Property | Observed value |
| --- | --- |
| Skill | autoqa |
| Version | 0.1.0 |
| Archive | autoqa-v0.1.0.zip |
| Archive bytes | 41,952 |
| Packaged files | 16 |
| Archive SHA256 | 8ad323f0080efe4f71ce6cc8e984d9d1641327774ba558118d5b9dd4d2dbf901 |
| Source commit | 66bc2653e1e8de2ea7a200b7eb273973afe9e38f |
| Helper SHA256 | 4c67bb89849652f704de5b80d4c26b08cd361affac9a04eb5aa6914652644f06 |

The builder extracted the actual archive and ran the owning acceptance hook
from the same committed source. It exited 0 after exercising the shipped CLI:
init, valid incomplete reporting, artifact sealing, a complete synthetic ledger,
tamper rejection and refusal to reseal altered evidence. This is evidence about
the packaged helper, not a live product under test.

## Instruction and source qualification

The [bundled qualification record](../../../skills/autoqa/evals/RESULTS.md)
contains the methods and limitations:

- 54 AutoQA CLI regressions and 90 shared collection tests passed.
- Three supplied-record scenarios scored 17/17 for the original upstream and
  17/17 for the adaptation in separate fresh-agent runs with a blinded grader.
- Independent helper review found no unresolved blocker in its bounded scope.
- Gitleaks found no secrets in the scanned skill or hooks. UBS had zero critical
  findings; its remaining warnings were reviewed. The existing SkillSpector gate
  passed with four documented nonblocking findings.

## Managed installation

The reviewed archive was installed on one authorized Linux host in the existing
personal skill directories for Codex and Claude Code, using the collection
installer's plan, apply and status operations.

Both plans observed no existing AutoQA target. This was a fresh addition, with
no older AutoQA consumers to stop. Each apply used its exact reviewed plan hash.
Both independent status reads reported INSTALLED at version 0.1.0 with the same
source commit, archive hash and installed file hashes. Neither operation replaced
an unmanaged folder or changed another skill.

Installer receipts establish file installation and integrity. Their
native_client_verified field remains false by design; the separate check below
establishes the native discovery claim.

## Native Codex discovery

A fresh Codex CLI 0.166.0 app-server process was queried through its documented
local skills/list RPC for the authorized project, with forceReload enabled.

| Probe | Observed result |
| --- | --- |
| Before installation | No autoqa entry; no AutoQA loading errors |
| After installation | One autoqa entry |
| Discovered scope | user |
| Enabled | true |
| Entry | Installed AutoQA SKILL.md in the personal Codex skill directory |
| AutoQA loading errors | None |
| Model request sent | No |

Both negative and positive controls passed. The check's app-server process was
terminated after the response. This demonstrates actual native discovery, not
automatic selection quality or a model completing a real product QA task.

Claude Code installation was verified through the managed receipt and file
checks. Its native discovery and invocation were not separately exercised.

## Completion boundary

Implementation task gs-v0b is complete against its source, test, package,
publication and installation acceptance criteria. Real-project qualification
remains open as gs-05x: two authorized application runs with completed journeys,
a failure or interruption path, actual evidence, cleanup and a report of coverage
gaps and false positives.

No live-product success rate, sustained field outcome or measured tenfold
improvement is claimed. The installed skill files are unchanged from the
immutable package; this receipt lives outside that package.
