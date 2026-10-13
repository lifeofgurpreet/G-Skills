# Contributing

Use a synthetic fixture that demonstrates the issue. Preserve the failing output, make the smallest corrective change, and run `python3 tools/validate.py`. Describe the user-visible correction and any changed assumptions. Do not include real logs, endpoints, support tickets or benchmark reports.

Changes to evidence semantics, network behavior, default tolerances, active-load capabilities or provider contact require explicit maintainer review. Never delete a test just to increase the pass rate. The `learn` output is a starting point for review, not an automatic merge request.

For additional skills, use `skills/<lowercase-name>/SKILL.md` plus scripts, tests, assets and focused references. Keep the main skill readable. All dependencies, permissions, side effects and unsupported modes must be explicit. Prefer existing tools to new services.
