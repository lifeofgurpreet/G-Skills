# Review-controlled self-improvement

“Self-sculpting” means learning through reproducible, versioned changes. It does not mean allowing runtime observations to rewrite instructions, thresholds, permissions or tests in place.

## States

`OBSERVED → PROPOSED → REPRODUCED → TESTED → REVIEWED → RELEASED`

Only the first two are implemented by the `learn` command. An authorized coding agent and maintainer carry out the remaining engineering steps. No script self-modifies, calls an LLM, installs a new package, sends data or pushes a commit.

1. Keep the original capture private and verify its report.
2. Run `learn` to create a **new** local proposal. It contains only a capture hash, analyzer hash, approved aggregate states and known gap categories. It never copies the node names, endpoints, arbitrary error strings, logs or provider messages.
3. Decide whether the lesson is a real reusable bug or just workload/provider-specific noise. Do not tune a threshold to one disappointing observation.
4. Reproduce the bug with synthetic fixtures. The regression must fail on the old code for the intended reason.
5. Fix the owning function, delete superseded branches, and run `python3 tools/validate.py`. Re-run the original private capture too; do not upload it.
6. Review the diff for privacy, authority expansion, changed evidence semantics and broken backward compatibility. A maintainer approves the release. Bump the version and explain limitations.

A proposal is not an agent instruction. Unknown fields or prose injected into a capture cannot grant new powers. A lesson that requires modifying a provider account or contacting support is an operational decision, not automatic skill improvement.

## Regression examples

- A clock correction falsely appears as lost capacity.
- A duplicate target changes an average.
- Incomplete or skipped runs vanish from the report.
- A small positive confound rounds down before the guard compares it.
- A recent scrape makes an old benchmark look new.
- A node absent from monitoring disappears from the expected inventory.
- An agent confuses a migration acknowledgment with a completion notice.

Most of these are better encoded in data shape and tests than repeated as longer instructions. Public reports and fixtures must be synthetic. Human review remains necessary; a passing script cannot independently establish causal truth or certify a model's judgment.

## Inspiration and licensing

Jeffrey's public [skill description](https://www.jeffreys-skills.md/) demonstrates progressive disclosure, scripts, validation and deterministic versioning. [pstack](https://github.com/cursor/plugins/tree/main/pstack) provides public verification and simplification principles. Apply their approach; do not copy premium skill bodies, run their paid sync tools for public redistribution, or imply affiliation.


## Persistent workspace proposals

The same command now accepts either an original verified report bundle or a
workspace. Resolve the actual installed folder as described in
[SKILL.md](../SKILL.md), then substitute it below. The executing agent chooses the
existing private workspace and new proposal path; these commands work from any
working directory:

```bash
VPS_HEALTH_CLI="<absolute-skill-folder>/scripts/vps_health.py"
python3 "$VPS_HEALTH_CLI" learn "$HOME/vps-health" --out "$HOME/vps-lesson-001.json"
```

Workspace proposals contain only fixed decision/gap categories and content
hashes. No host alias, endpoint, plan, raw log, message text or user impact prose
is copied. The output is still `PROPOSED_NOT_APPLIED`; no code, threshold, policy,
service, message or public upload is changed. The maintainer must reproduce the
pattern with a synthetic test before implementing a release. A common failure
is an empty but successful scrape refreshing the apparent age of an old sample;
its regression should assert freshness of the observation, not the request.
