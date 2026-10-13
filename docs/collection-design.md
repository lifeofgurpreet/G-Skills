# Collection boundaries

G-Skills is a collection of independently useful public skills. VPS Health is the
first member. A user who installs a future writing, project or other skill must
not acquire the VPS worker, chart dependencies, infrastructure procedures or
performance policy unless that chosen skill deliberately requires them.

## Ownership and single sources

Each `skills/<name>/skill.json` owns its name, version, summary, status and
maintenance entry points. `catalog.json` is generated, not a separately edited
registry. Shared discovery has no built-in list of skill names. `SKILL.md` remains
the agent's conventional entry; scripts and deeper references remain optional.

Maintenance hooks live in `tools/skills/<name>/`. Python acceptance is required as
a thin repository test entry point, not a required end-user runtime language.
Browser and JavaScript checks are optional per skill. Their presence drives the
CI matrix, so adding a non-browser skill requires no change to another skill's
workflow. Skill-owned research and roadmap files live in `docs/skills/<name>/`.

One native Beads graph can serve the repository, but each task has exactly one
`scope:collection` or `skill:<name>` label. Root ROADMAP.md summarizes collection
infrastructure and links the skill programmes. Generated per-skill roadmaps retain
all existing IDs, dependencies and open acceptance gates. A task scope is not a
new independent tracker or a copy of the same work.

## Scaffolding without false completeness

`tools/collection.py --new NAME --title TITLE` creates a draft entry, metadata and
small verification/package hooks. It does not create a pretend live product,
publish a release, install dependencies or claim functional acceptance. Existing
destinations and unsafe paths are refused. Implement the actual workflow and
cold-use test, then review an explicit change to `status: ready`.

A second unrelated temporary skill is created during tests. Its catalog entry,
version and package do not contain VPS assets or require a browser. This proves
the variable part of the design instead of merely documenting that it is generic.

## Independent release contract

`tools/package_release.py --skill NAME --ref COMMIT --out PRIVATE_NEW_DIRECTORY`
reads one immutable Git tree. It includes only the selected skill and its license,
checks path/member integrity, then invokes the selected skill's package check
from that same committed tree against the actual extracted ZIP. Uncommitted source
and another skill's runtime cannot enter by accident.

Tags are `<skill>/v<version>` and ZIPs are `<skill>-v<version>.zip`. There is no
shared application version. Old `v0.1.0` through `v0.6.0` tags remain historical;
they are not retagged or made into collection-wide compatibility promises. A
collection source snapshot can still be obtained from GitHub separately.

No package or test hook can be inferred from untrusted user input. The maintenance
hooks are reviewed repository code, explicitly owned by the selected skill. Runtime
users receive that skill folder; developer tools outside it are not installed.

## Shared principles, not one product design

Shared policy covers privacy, licensing, clear authority, tested artifacts,
original reusable work and agent-owned execution. Domain-specific measurement,
provider, UI or runtime rules belong to the skill that needs them. Applicable
JSM/pstack guidance informs extraction, planning and proof, without copying paid
materials or claiming that a large external framework was completed.

External review proposals should have an explicit disposition and evidence. The
Gemini VPS review belongs under VPS Health, not the root identity of G-Skills.
