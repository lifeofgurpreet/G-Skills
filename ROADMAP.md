# G-Skills collection roadmap

This repository hosts independent public skills. Root work is catalog/distribution/quality infrastructure, not the roadmap of the first skill. Canonical task state is `.beads/issues.jsonl`; regenerate with `python3 tools/roadmap.py --write`.

## Collection infrastructure

| Task | State | Priority | Blocking prerequisites |
|---|---|---:|---|
| `gs-ekd` Independent public skill collection and distribution | in_progress | 1 | — |
| `gs-ekd.1` Discover and scaffold independent draft skills | in_progress | 1 | — |
| `gs-ekd.2` Dispatch validation and immutable releases to the selected skill | open | 1 | `gs-ekd.1` |
| `gs-ekd.3` Separate collection identity, documentation and task ownership | open | 1 | `gs-ekd.1` |

## Skill programmes

- [VPS Health](docs/skills/vps-health/ROADMAP.md): 10 open implementation/acceptance tasks; independent version 0.7.0.

## Collection acceptance

### gs-ekd — Independent public skill collection and distribution

G-Skills hosts independently useful skills. Remove the first VPS skill from root identity, hard-coded tests, versions and roadmap. Shared tooling discovers reviewed manifests; another unrelated skill need not inherit a dashboard, Linux runtime or CPU policy.

**Acceptance:** Temporary unrelated skills can be scaffolded, selected, tested and packaged separately; catalog/CI/roadmap discover owners and no default VPS version or dependency leaks into the other package.

### gs-ekd.1 — Discover and scaffold independent draft skills

Add manifest-driven catalog and a no-overwrite draft scaffold. A new skill remains draft until real implementation and acceptance exist.

**Acceptance:** Catalog drift, invalid names, owner-hook escape, missing hooks and draft release attempts fail. Two unrelated synthetic skills demonstrate version and dependency independence.

### gs-ekd.2 — Dispatch validation and immutable releases to the selected skill

Move VPS maintenance behind its owning hooks; package only selected committed skill files. Release tags use skill/vVersion without rewriting legacy tags.

**Acceptance:** Per-skill acceptance runs from the same committed tree on the actual extracted ZIP; unrelated files and uncommitted changes cannot enter. Dynamic browser CI only uses declared owners.

### gs-ekd.3 — Separate collection identity, documentation and task ownership

Root README/AGENTS/roadmap describe the collection; VPS details and research live under its owning skill/docs path. Preserve task IDs and states while adding scopes.

**Acceptance:** One scope per native task, no cross-scope parent relationship, generated root summary and per-skill roadmaps match. Legacy references are relocated or explicitly corrected, not silently erased.

A second unrelated skill must be discoverable, independently validated and packaged without inheriting another skill's browser, runtime or safety policy. Draft scaffolds are not completed products.

Beads is a development tool. Users of an installed skill need only that skill's declared requirements. No private user workspace becomes part of this graph.
