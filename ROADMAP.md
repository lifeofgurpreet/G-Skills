# G-Skills collection roadmap

This repository hosts independent public skills. Root work is catalog/distribution/quality infrastructure, not the roadmap of the first skill. Canonical task state is `.beads/issues.jsonl`; regenerate with `python3 tools/roadmap.py --write`.

[Three-month execution plan and sharing gates](docs/plans/2026-10-14-quarter.md). Owners and targets below come from Beads; a target date is not a scheduled job or release authorization.

## Collection infrastructure

| Task | State | Priority | Owner role | Target | Blocking prerequisites |
|---|---|---:|---|---|---|
| `gs-ekd` Independent public skill collection and distribution | closed | 1 | Unassigned | — | — |
| `gs-nah` October to January: sustainable public skill collection readiness | in_progress | 1 | Gurpreet | 2027-01-14 | — |
| `gs-ekd.1` Discover and scaffold independent draft skills | closed | 1 | Unassigned | — | — |
| `gs-ekd.2` Dispatch validation and immutable releases to the selected skill | closed | 1 | Unassigned | — | `gs-ekd.1` |
| `gs-ekd.3` Separate collection identity, documentation and task ownership | closed | 1 | Unassigned | — | `gs-ekd.1` |
| `gs-nah.1` Publish the quarter plan with explicit owners and launch gates | closed | 1 | collection-maintainer | 2026-10-21 | — |
| `gs-nah.2` Qualify clean skill installation, upgrade and removal | closed | 1 | distribution-verifier | 2026-11-07 | `gs-nah.5` |
| `gs-nah.3` Prepare a bounded community preview and maintainer feedback loop | closed | 1 | Gurpreet-and-community-maintainer | 2026-12-21 | `gs-nah.2` |
| `gs-nah.4` Select the next independent skill from repeated real work | open | 1 | Gurpreet-and-product-agent | 2027-01-07 | — |
| `gs-nah.5` Implement reversible selected-skill installation with preserved recovery state | closed | 1 | distribution-agent | 2026-10-28 | — |
| `gs-nah.6` Produce verified community launch video and share-ready assets | closed | 1 | community-media-agent | 2026-10-16 | — |
| `gs-nah.7` Validate actual skill discovery YAML before a public release | closed | 1 | skill-quality-agent | 2026-11-07 | — |
| `gs-ss8` Check publishable source without scanning ignored tracker and linter caches | closed | 2 | collection-maintainer | 2026-10-21 | — |

## Skill programmes

- [Codex Clanker Cranker](docs/skills/reset-boost/ROADMAP.md): 2 open implementation/acceptance tasks; independent version 0.3.0.
- [VPS Health](docs/skills/vps-health/ROADMAP.md): 9 open implementation/acceptance tasks; independent version 0.11.3.

## Collection acceptance

### gs-ekd — Independent public skill collection and distribution

G-Skills hosts independently useful skills. Remove the first VPS skill from root identity, hard-coded tests, versions and roadmap. Shared tooling discovers reviewed manifests; another unrelated skill need not inherit a dashboard, Linux runtime or CPU policy.

**Acceptance:** Temporary unrelated skills can be scaffolded, selected, tested and packaged separately; catalog/CI/roadmap discover owners and no default VPS version or dependency leaks into the other package.

**Receipt:** Source accepted: collection/selected-skill validation passes 255 Python tests, 12 chart contracts and 29 real-loopback browser groups. Two unrelated temporary skills prove independent version/check/package ownership, including a failing-before large-unrelated-skill budget regression. Actual selected VPS ZIP extracted and exercised; passive Linux context/retention/compare smoke completed without active tests. See docs/collection-design.md and docs/skills/vps-health/verification-v0.7.0.md. Hosted exact-source CI remains the release gate.

### gs-nah — October to January: sustainable public skill collection readiness

Three-calendar-month programme, 2026-10-14 to 2027-01-14. Keep G-Skills an independent-skill collection. Owners are accountable roles, not active automated workers. Release dates are target windows; a human decides when to announce. Prefer qualified small previews over unsupported universal claims.

**Acceptance:** Versioned calendar roadmap maps every open leaf to an owner, target and acceptance signal; independent installation/update and contribution quality are qualified; next-skill selection is evidence-led; no public announcement is sent without a distinct owner decision.

### gs-ekd.1 — Discover and scaffold independent draft skills

Add manifest-driven catalog and a no-overwrite draft scaffold. A new skill remains draft until real implementation and acceptance exist.

**Acceptance:** Catalog drift, invalid names, owner-hook escape, missing hooks and draft release attempts fail. Two unrelated synthetic skills demonstrate version and dependency independence.

**Receipt:** Source accepted: collection/selected-skill validation passes 255 Python tests, 12 chart contracts and 29 real-loopback browser groups. Two unrelated temporary skills prove independent version/check/package ownership, including a failing-before large-unrelated-skill budget regression. Actual selected VPS ZIP extracted and exercised; passive Linux context/retention/compare smoke completed without active tests. See docs/collection-design.md and docs/skills/vps-health/verification-v0.7.0.md. Hosted exact-source CI remains the release gate.

### gs-ekd.2 — Dispatch validation and immutable releases to the selected skill

Move VPS maintenance behind its owning hooks; package only selected committed skill files. Release tags use skill/vVersion without rewriting legacy tags.

**Acceptance:** Per-skill acceptance runs from the same committed tree on the actual extracted ZIP; unrelated files and uncommitted changes cannot enter. Dynamic browser CI only uses declared owners.

**Receipt:** Source accepted: collection/selected-skill validation passes 255 Python tests, 12 chart contracts and 29 real-loopback browser groups. Two unrelated temporary skills prove independent version/check/package ownership, including a failing-before large-unrelated-skill budget regression. Actual selected VPS ZIP extracted and exercised; passive Linux context/retention/compare smoke completed without active tests. See docs/collection-design.md and docs/skills/vps-health/verification-v0.7.0.md. Hosted exact-source CI remains the release gate.

### gs-ekd.3 — Separate collection identity, documentation and task ownership

Root README/AGENTS/roadmap describe the collection; VPS details and research live under its owning skill/docs path. Preserve task IDs and states while adding scopes.

**Acceptance:** One scope per native task, no cross-scope parent relationship, generated root summary and per-skill roadmaps match. Legacy references are relocated or explicitly corrected, not silently erased.

**Receipt:** Source accepted: collection/selected-skill validation passes 255 Python tests, 12 chart contracts and 29 real-loopback browser groups. Two unrelated temporary skills prove independent version/check/package ownership, including a failing-before large-unrelated-skill budget regression. Actual selected VPS ZIP extracted and exercised; passive Linux context/retention/compare smoke completed without active tests. See docs/collection-design.md and docs/skills/vps-health/verification-v0.7.0.md. Hosted exact-source CI remains the release gate.

### gs-nah.1 — Publish the quarter plan with explicit owners and launch gates

Turn the existing scoped Beads graph into an actionable October-January delivery plan without duplicating task state. Name monthly outcomes, per-task owners/targets, beta gates, exclusions, work-in-progress limits and what happens when a gate fails.

**Acceptance:** Every current nonclosed leaf has a responsible role and target. Root and VPS roadmaps display the native fields. The three-month document distinguishes target dates, evidence and authorization; no checkbox or test count alone grants announcement permission.

**Receipt:** Quarter plan delivered at docs/plans/2026-10-14-quarter.md. Native owners, dates and phase labels cover all current open leaf tasks; six scoped roadmap tests pass. The narrow VPS preview has its own dependency gate gs-2uh.13; source completion does not authorize publication.

### gs-nah.2 — Qualify clean skill installation, upgrade and removal

Verify selected-skill distribution from actual release archives in supported client skill locations. Do not overwrite another skill, user-edited installation, private captures or credentials. Detect missing dependencies and blocked discovery truthfully.

**Acceptance:** Two independent skill fixtures keep versions and files separate. A clean install, interrupted upgrade, rollback and removal preserve user evidence and untouched other skills. Actual supported-client discovery gets a separate receipt; archive validity does not prove discovery.

**Receipt:** Qualified the supported Linux/Claude Code project-local installation route: actual native discovery/loading of installed v0.7.3, disappearance after managed removal, restoration/loading and a separate session loading the v0.8.0 candidate entry/support reference. Previous actual archive install/update/recovery/restore/removal and two-skill isolation evidence is retained. Current model-driven execution was BLOCKED by a required sandbox dependency, so runtime/Codex qualification remains separately open in gs-2uh.6. No sandbox bypass or personal skill-directory mutation. See docs/project-discovery-2026-10-15.json.

### gs-nah.3 — Prepare a bounded community preview and maintainer feedback loop

Prepare concise supported-scope documentation, sanitized issue/report templates, known limitations, contributor expectations and a release checklist. A public repository already exists; social announcements, invitations and any email remain a separate owner decision.

**Acceptance:** Preview candidates have reproducible install/stop/export routes, public synthetic examples and private-data warnings. Support intake never asks for tokens or raw private data publicly. All claimed compatibility and evidence scopes have receipts; Gurpreet separately approves wider sharing.

**Receipt:** Preview preparation delivered: current supported-scope matrix, self-contained agent entry/support guide, privacy-aware public issue forms, and an implemented offline minimal-support command plus real viewer download. 17 new Python support contracts; 370 complete Python tests, 12 chart contracts and 30 browser groups pass. Native discovery and current execution blockers are explicit rather than marketing claims. This closes preparation only: wider publicity remains an owner decision and gs-2uh.13 stays open for native-client and sustained-pilot acceptance. No social post, invitation, provider message or upload was sent.

### gs-nah.4 — Select the next independent skill from repeated real work

By the final month, propose at most three high-value repeated user workflows, compare their generality and effort, and let Gurpreet choose one. Reuse collection scaffolding only after selection. Do not invent a second live product to fill the catalog.

**Acceptance:** Record user-selected problem, intended agent-owned outcome, authority limits and cold-use acceptance; create a draft-only entry for that choice. If no choice is made, record a waiting decision rather than release a placeholder.

### gs-nah.5 — Implement reversible selected-skill installation with preserved recovery state

Build the shared agent-callable offline plan/apply/status path for one selected reviewed skill archive. Preserve modified or unmanaged folders, other skills and user evidence; stage and journal replacements outside discovery; never run packaged hooks, connect accounts or override client permissions. This is implementation/fixture acceptance, not native-client discovery.

**Acceptance:** Fresh install, idempotent repeat, update, retained removal and prior-version restore pass with unrelated synthetic skills and the real VPS archive. Wrong hash/destination, source edits, symlinks and concurrent writers refuse. Actual process interruption has recoverable old files; a removed installation cannot reuse its old approval. Native Codex/Claude installation/discovery remains under gs-nah.2.

**Receipt:** Actual published 0.7.0/0.7.1 archive installation, update, runtime start/stop, byte-identical restore and retained removal pass; three subjects and 2288 observation points unchanged. Shared source tests and interruption/security regressions pass. Exact entry handoff added from native-client findings. See docs/execution-2026-10-14.json. Automatic client discovery is still gs-nah.2, not inferred from filesystem acceptance.

### gs-nah.6 — Produce verified community launch video and share-ready assets

Create an actual short launch film for the selected VPS Health preview using real synthetic product captures, claim-safe editorial copy and an actual requested Opus 5.5 creative pass. Keep other collection entries independent. Prepare social copy, do not post it.

**Acceptance:** Landscape/feed MP4s have visible demo/preview labels, captions, original or licensed audio, verified encoding and complete decode. Real product capture actions are checked and model contribution is precisely attributed. Original render source and reproduction are retained. No customer data, fake native chat, completed-field-trial claim or automatic public post.

**Receipt:** Delivered two 53-second caption-first H.264/AAC launch films with persistent demo/preview labels, caption sidecar, original synthetic instrumental audio and poster. Actual Opus 5.5 creative response verified; renderer/operator work is separate. GitHub media run 38661868521 rendered from a tree identical to merged e4c6b73, verified encodings/streaming metadata and fully decoded both files. Output hashes independently checked after download and keyframes visually inspected. Share-ready short copy and interactive synthetic demo are included. No social/public announcement, provider contact, private capture or fake native-agent trace. Source and repro: docs/skills/vps-health/launch.md and tools/skills/vps-health/launch_media.py.

### gs-nah.7 — Validate actual skill discovery YAML before a public release

Anthropic skill-creator quick_validate and a real YAML parser reject the published VPS description because its unquoted colon forms invalid mapping syntax. Runtime tests alone had not caught this. Add a collection-wide development-only metadata check, preserve independent skill ownership and check the actual exported VPS header.

**Acceptance:** Failure-first malformed/duplicate/type/version cases pass; all current skills parse without modifying unrelated skill code; CI installs a pinned development-only YAML parser and the extracted VPS package header passes. No end-user YAML dependency is introduced.

**Receipt:** Actual public v0.9.3 header rejected by Anthropic quick_validate; candidate exported archive passes. Ten metadata regressions, collection checks and isolated no-site-packages bootstrap pass. Dev-only YAML dependency does not enter user runtime. Exact-head hosted checks remain the release gate; other client triggering is not inferred.

### gs-ss8 — Check publishable source without scanning ignored tracker and linter caches

Native br and UBS create ignored SQLite/WAL/recovery and Ruff binary cache files in the shared checkout. The privacy walker treated these local artifacts as publishable source. Use the actual Git index plus unignored new work in a checkout; extracted no-Git archives still scan every file. Forced tracked and unignored private files remain checked.

**Acceptance:** Ignored tracker/linter runtime does not fail source validation. Force-added/unignored private files are still refused, and extracted archives cannot use gitignore to hide artifacts. Failing-before Beads regression, observed Ruff cache failure, and shared structure acceptance pass.

**Receipt:** Falling-before native Beads regression and observed Ruff cache failure corrected with a Git publication inventory. All19 collection tests and shared structure acceptance pass in the actual shared checkout containing its ignored runtime. Force-added/unignored private files and no-Git archives remain refused. Installed skill and vendor files unchanged.

A second unrelated skill must be discoverable, independently validated and packaged without inheriting another skill's browser, runtime or safety policy. Draft scaffolds are not completed products.

Beads is a development tool. Users of an installed skill need only that skill's declared requirements. No private user workspace becomes part of this graph.
