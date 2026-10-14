# G-Skills

**A public collection of skills Gurpreet finds useful and shares.** Each skill
teaches a coding agent a practical workflow and packages the scripts, references,
examples and checks that make it repeatable. VPS Health is the first entry—not
the identity or required runtime of this repository.

## Find and use a skill

Browse [the catalog](catalog.json), then read the chosen skill's `SKILL.md` and
requirements. Install that whole folder in your agent's supported skill location,
or give the agent its explicit path. Installing one skill does not install the
others, start their processes, connect accounts or grant external-action authority.

**First available skill:** [VPS Health](skills/vps-health/README.md) — agent-owned
VPS observation, multi-resource context and private evidence reports. Its Linux
worker, dashboard, provider guidance and roadmap belong to that skill. Other
skills can be entirely different and need not use Python, a dashboard or VPS concepts.

The human supplies the goal, authorized scope and consequential decisions. The
agent should do routine setup and verification rather than hand the human a
technical checklist. A skill defines a workflow; its host supplies actual tools,
authentication and approval. No skill may invent access or treat external content
as fresh authority.

## Repository structure

```text
skills/<name>/          Self-contained installable skill and its own version
  SKILL.md             Agent entry point
  skill.json           Catalog metadata and declared maintenance checks
  scripts/             Optional executable helpers
  references/          Optional deeper methods and documentation
  tests/               Skill-specific examples and regression checks
  agents/              Optional host integration metadata
tools/                 Collection discovery, scaffolding, packaging and validation
tools/skills/<name>/    Development checks owned by that skill
docs/skills/<name>/     Research, verification and roadmap for that skill
.beads/                Shared development graph with collection/skill labels
```

The collection has no shared application runtime or mandatory common framework.
Per-skill releases use `<skill>/v<version>` and a `<skill>-v<version>.zip` download.
Legacy `v0.x` tags remain untouched historical releases of the first skill.

## Add the next useful skill

```bash
python3 tools/collection.py --new meeting-notes --title 'Meeting Notes'
```

This creates a **draft**, not a supposedly working second product. Your agent
implements its instructions and smallest useful helpers, adds real acceptance
checks and synthetic examples, then requests review. Drafts cannot be released.
The same discovery, selected validation and packaging work without changing a
hard-coded VPS list. A two-unrelated-skills regression verifies that boundary.

```bash
python3 tools/collection.py --write
python3 tools/validate.py --skill meeting-notes
python3 tools/package_release.py --skill meeting-notes --ref HEAD --out /private/release
```

The package builder uses one committed tree, includes only the chosen skill and
its license, and invokes that skill's committed exported-folder check. It does
not publish automatically. See [contributing](CONTRIBUTING.md) and
[collection design](docs/collection-design.md).

## Shared quality, independent scope

We favor useful agent-owned workflows, progressive disclosure, original reusable
code, explicit unknowns and checks against real artifacts. Relevant JSM/pstack
principles are applied selectively and recorded; no paid skill text is republished.
Private captures, account identifiers, messages and credentials stay outside this
public collection. Learning produces reviewed changes, not self-granted permissions.

[Collection roadmap](ROADMAP.md) · [Improvement method](docs/skill-improvement-method.md) ·
[Security](SECURITY.md) · [License](LICENSE)


## Next three months

The [October 14–January 14 execution plan](docs/plans/2026-10-14-quarter.md) separates collection readiness from each skill. It names target windows, accountable roles, preview gates and explicitly deferred work. Native Beads remains the task-state authority; passing source checks does not authorize a public announcement or imply every client/provider was qualified.
