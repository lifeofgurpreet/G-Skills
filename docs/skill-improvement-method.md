# Improving a runnable skill

A larger instruction file is not necessarily a better skill. Each improvement must make an actual user task easier or make a false conclusion harder to produce.

## 1. Discover, select and read

Inventory an explicitly authorized local library before selecting guidance. The repository's helper works offline:

```bash
python3 tools/study_local_skills.py \
  --root /path/to/installed/skills \
  --query 'usability verification' \
  --select ux-audit --limit 8 \
  --out /private/existing-directory/study-plan.json
```

The output is private metadata. `INDEXED_NOT_READ` is deliberate: finding a title does not mean its instructions were read, applied or verified. Installed editions may differ; preserve their hashes. Do not publish paid skill text, local paths, subscription inventories or private examples.

Read the selected entry points, then only the references needed for the task. Record which guidance fits and which does not. For example, a cinematic React visualization recipe is not a reason to add a frontend framework to a dependency-free operations viewer. A polish method is not a substitute for repairing a fundamentally weak layout.

## 2. Define the task before judging the surface

Write the questions a user needs answered in order. For VPS health: What needs attention? Is the evidence usable? What changed? What should I inspect next? Keep service health, accounting observations and provider responsibility separate.

Choose concrete checks rather than subjective claims such as “world class” or an unsupported numerical score. A command must work from an exported skill folder; a state change must be visible; a failed collector must not look healthy.

## 3. Compare alternatives, then implement a focused pass

For a substantial interface decision, compare two small working layouts using the same synthetic state. State what was rejected and why. Keep the winning implementation, not multiple half-maintained design systems.

Run focused sequential passes: evidence semantics, layout and interaction, then cold-start and failure verification. Each pass has one mission, a relevant source decision and a commit or an explicit no-change finding. A second reader is useful when available, but never label a self-review as independent review.

## 4. Convert the observation into a regression

Reproduce the failure against the prior source first. Add the smallest case that would fail if the defect returned. Fix the owning implementation rather than duplicating a rule in another report mode. A visualization is part of the evidence path: reducing points must not conceal a deficit or bridge invalid time.

Source tests are not visual approval. After they pass, exercise actual controls, inspect screenshots and test failure/recovery states. Use ordinary keyboard, pointer and touch APIs; direct DOM mutation is not evidence that a user can perform the action.

## 5. Verify and retain a bounded receipt

For this repository:

```bash
python3 tools/validate.py
# Developer-only dependency, not needed by skill users:
python3 -m pip install playwright==1.57.0
python3 -m playwright install chromium
python3 tools/test_dashboard.py --out /private/new-browser-proof
```

The browser suite runs the real loopback handler with synthetic workspaces. It covers navigation, subject selection, search, filtering, keyboard inspection, downloads, refresh, failure/recovery and desktop/mobile viewports. Screenshots remain separate from assertions: inspect both the initial viewport and the dense/error states. Simulated phone dimensions are not a physical-device test.

Keep a release receipt mapping the changed user claims to executable checks. Record exact source, what was and was not tested, and known limitations. Ship only after the actual release tree passes CI. Do not claim a multi-day field trial, universal agent activation or provider cause from a short smoke test.

## 6. Learn without changing authority

An observed failure can produce a sanitized proposal, a synthetic regression and a reviewed release. It cannot authorize external messages, new monitoring, host changes, private-data publication or threshold weakening. Maintainer review is the boundary between learning from experience and silently rewriting the rules.

Public design influences: [Jeffrey's Skills](https://www.jeffreys-skills.md/), [pstack](https://github.com/cursor/plugins/tree/main/pstack), and [W3C table accessibility guidance](https://www.w3.org/WAI/tutorials/tables/). This document is an original project method, not a redistribution or claimed completion of another author's full audit framework.


## Chart and release extension

Read selected deeper testing/release guidance, not only the UI entry points.
For a renderer change, define invariants for every channel, prove transformations
against known synthetic values, and run the actual server/browser integration.
Test range selection, refresh, missing context, independent gap boundaries,
keyboard/touch controls and downloads separately from visual appearance.

A library is an upstream dependency: pin its source, preserve its license and
verify bytes before embedding it. A framework's published benchmark is not our
observed performance. Keep the smallest fitting integration rather than carrying
multiple libraries for prestige. Actual uploaded ZIP shape and extracted startup
are release requirements; a copied source directory is only an earlier check.
