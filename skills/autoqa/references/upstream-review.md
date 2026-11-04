# Upstream review and adaptation

Reviewed source: Parcha-ai/parcha-skills, commit
c82883b15e5e8f02483bee513b3c8dcac48e3c9e, retrieved 2026-11-05
(Pacific/Guadalcanal). This implementation is an attributed adaptation with an
original workflow and helper; it does not track upstream automatically.

Primary sources:

- [Skill](https://github.com/Parcha-ai/parcha-skills/blob/c82883b15e5e8f02483bee513b3c8dcac48e3c9e/autoqa/skills/autoqa/SKILL.md)
- [Discovery](https://github.com/Parcha-ai/parcha-skills/blob/c82883b15e5e8f02483bee513b3c8dcac48e3c9e/autoqa/skills/autoqa/references/discovery.md)
- [Report template](https://github.com/Parcha-ai/parcha-skills/blob/c82883b15e5e8f02483bee513b3c8dcac48e3c9e/autoqa/skills/autoqa/references/report-template.md)
- [Package tests](https://github.com/Parcha-ai/parcha-skills/blob/c82883b15e5e8f02483bee513b3c8dcac48e3c9e/autoqa/tests/test_package.py)
- [MIT license](https://github.com/Parcha-ai/parcha-skills/blob/c82883b15e5e8f02483bee513b3c8dcac48e3c9e/autoqa/LICENSE)

## Assessment

The upstream is a useful, serious starting point. It requires live witnesses,
diff-derived cases, explicit entry points, budgets, bounded polling, resource
accounting and scoped coverage. Its seven package tests check instructional
structure and key phrases; they do not establish behavioral reliability.

| Disposition | Upstream idea | Adaptation and reason |
| --- | --- | --- |
| Retain | No witness, no verdict | Require observations plus integrity-checked local artifacts; keep semantic limits explicit. |
| Retain | Current diffs add cases to the baseline | Keep stable inventory-to-case mapping and visible missing coverage. |
| Retain | Use the real entry point | Preserve UI/API/CLI distinctions and browser proof for UI claims. |
| Retain | Budgets, polling and cleanup | Add machine-visible incomplete/cleanup states; no unbounded loops. |
| Modify | AUTOQA.md skips discovery | Re-read governing instructions and verify config against current source/runtime every run. |
| Modify | Untraceable entry point is skipped/dead code | Preserve a promised journey as failed, blocked or not run; lack of a link can be the defect. |
| Modify | Exact zero/one/two turns and child sessions | Derive transitions and counts from each product's contract. |
| Modify | Scope question when not preselected | Infer a bounded default and proceed with authorized work; ask for consequential ambiguity. |
| Modify | Report carries a local head SHA | Bind observations to source and observed runtime, including unknown or mismatched builds. |
| Add | Human witness contract | Provide offline validation for coverage, hashes, provenance and false-green traps. |
| Add | Pass/fail alone | Separate journey completion, guardrail success and proof depth. |
| Add | Report-only app failure | Carry authorized repair through re-execution and existing task ownership. |
| Defer | PR sticky-comment publication | Leave publishing and landing to explicit authorization and repository policy. |
| Reject as a general rule | A QA pass reporting only greens has failed | Honest all-pass runs are possible; never manufacture failures. |

Do not describe this adaptation as empirically ten times better. The qualification
record states measured tests and comparisons. A larger prompt, more rules or
more tests alone cannot prove an improvement multiplier.

## Attribution

Parcha AutoQA is MIT-licensed, copyright (c) 2026 Parcha Labs, Inc.
Retain THIRD_PARTY_NOTICES.txt with this skill. Optional installed skills were
consulted for workflow boundaries only; their bodies are not redistributed.
