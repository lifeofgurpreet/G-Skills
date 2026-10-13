# G-Skills

**Runnable skills that take a coding agent from a question to a working, inspectable system.**

The first package, [vps-health](skills/vps-health/SKILL.md), turns a VPS concern into a private operating loop: setup diagnostics, retained observations, linked charts, a prioritized attention inbox, dated provider guidance and reviewed reports. Use one Linux host or your existing Prometheus/Loki stack. No new hosted account, AI API key, Python dependencies or monitoring stack is required.

## See the complete workflow first

Requires **Python 3.10+**. Clone the repo, inspect it, then run:

```bash
git clone https://github.com/lifeofgurpreet/G-Skills.git
cd G-Skills
python3 skills/vps-health/scripts/vps_health.py bootstrap \
  --mode demo --workspace /tmp/vps-demo
python3 skills/vps-health/scripts/vps_health.py serve --workspace /tmp/vps-demo
```

Open **http://127.0.0.1:8765/**. The synthetic three-day example shows a stable node, a contended node, and a node with a collection gap. Try the attention filter, inspect the evidence limitations and compare daily coverage. It is a demonstration, not data from somebody else's servers. Stop the server with Ctrl-C.

The generated `dashboard.html` can also be opened offline. Live view polls derived state every five seconds; it does **not** invent new observations when collection stops.

## Give the work to your coding agent

Install the complete `vps-health` skill folder in your terminal agent's supported
skill location, or give it the explicit `SKILL.md` path. Then say:

> Set up and manage a private VPS investigation for the targets I authorize.
> Inspect what we already have, scaffold the workspace, start bounded monitoring,
> and show me the live dashboard. Ask me only for missing scope, authentication
> or consequential approvals—not to write config files or keep a terminal open.
> Do not contact a provider or change server settings without a new request.

The agent plans and executes; the human is not the shell operator. Version 0.6
adds `agent-plan`, `agent-start`, `agent-status` and `agent-stop`, plus a private
`HANDOFF.md` and visible Agent activity in the dashboard. The Linux worker survives
the launching terminal session, has a bounded lifetime and cannot renew a completed
run using its old approval hash. Matching starts reuse the same process and deadline.
Process liveness is checked independently from observation quality.

A Gmail or other service is connected only when the requested task actually needs
it. The agent should inspect its live tools, reuse a connection or use its host's
trusted discovery/OAuth flow. The capability request/result is recorded privately
for handoff, not mistaken for authentication or permission to send. The scripts
contain no mail sender; real external writes belong to the host's reviewed tools.

[Agent workflow](skills/vps-health/references/agent-workflow.md) ·
[Connector contract](skills/vps-health/references/agent-connectors.md) ·
[Dependency-aware roadmap](ROADMAP.md)

Managed execution currently qualifies Linux; it is not automatic reboot recovery
or universal Codex/Claude/OAuth compatibility. Those real-client and multi-day
acceptance gates remain visible in the new Beads epic `gs-2uh`. The user does not
need Beads or GitHub to use the installed skill. The command recipes below are
fallback/debugging instructions for an agent to execute, not homework for the user.

## From a chart to a useful next action

The workbench separates three questions: **is collection trustworthy, what changed,
and what should we inspect next?** Its evidence ribbon preserves short dips and
missing intervals. Linked uPlot panes align accounting with workload pressure.
The Attention inbox puts stale collection and identity conflicts before performance
claims; good accounting does not hide high workload pressure.

The Setup view provides single-host, existing-monitoring and demo recipes. The
Providers view explains allocation, usage allowances and credit models using dated
primary-source references. No screenshot, colour or selected time range certifies
a provider fault. The full retained evidence window owns the assessment.

```bash
python3 skills/vps-health/scripts/vps_health.py doctor --workspace /private/vps-health
python3 skills/vps-health/scripts/vps_health.py brief --workspace /private/vps-health
python3 skills/vps-health/scripts/vps_health.py providers --provider hetzner
```

Replace the example workspace path. **Doctor is read-only and offline**: it checks
local configuration, chart integrity, database readability, credential-variable
presence and evidence/retention gaps. It does not repair a machine or claim that
a process is running. Exit 0 means its checks are ready; 1 means findings; 2 is an
invalid/refused operation. The brief is the same action model as the dashboard.

Optional desktop alerts require a click and browser permission. Only new findings
are announced while the viewer is open; unchanged readings do not create an alarm
storm. Acknowledgment changes local unread state, never a HOLD. Recovery resets
that acknowledgment so a returning problem is visible again. The inbox works even
when desktop notification APIs are unavailable. No background notifier is installed.

[First-hour guide](skills/vps-health/references/first-hour.md) ·
[Operator playbook](skills/vps-health/references/operator-playbook.md) ·
[Provider reference](skills/vps-health/references/providers.md)

## Then choose your setup

| Your situation | First action | What runs |
|---|---|---|
| One Linux VPS, no monitoring stack | `bootstrap --mode local --node my-vps --workspace "$HOME/vps-health"` | Configuration only; no collection until you start it |
| One node or fleet already in Prometheus | Bootstrap with a private profile and the final trusted endpoint | Existing node-exporter metrics; optional bounded Loki context |
| Existing captures | Use `report`, `verify` and `compare` | Offline assessment; no network |
| Need a preview | `bootstrap --mode demo` | Synthetic multi-day history only |

For the single-node setup, start a bounded foreground collector and dashboard:

```bash
python3 skills/vps-health/scripts/vps_health.py bootstrap \
  --mode local --node my-vps --workspace "$HOME/vps-health"
python3 skills/vps-health/scripts/vps_health.py watch \
  --workspace "$HOME/vps-health" --approve-collection --serve
```

The default is **864 cycles at a five-minute cadence**, approximately 72 planned hours. Local mode reads cumulative counters between ticks; it does not turn ten seconds of sampling into five minutes of coverage. The first tick establishes a baseline. `watch` is foreground and stops on Ctrl-C; descheduling and slow endpoints can extend elapsed completion. There is no promise that a disconnected agent continues this work.

For unattended collection, `schedule` generates inspectable **systemd user** timer files. It does not install or enable them. Use that option only after approving the files, or invoke `collect` from an existing scheduler. Do not run both a timer and `watch` against the same workspace. See [the bootstrap recipes](skills/vps-health/references/bootstrap.md).

## The operator workbench

Defaults are **within tolerance at 90% or above**, **watch at 80–90%**, and **investigate below 80%**. These are configurable accounting-screen thresholds, not a hosting contract or automatic support trigger. **HOLD overrides them** when collection is stale, too short, incomplete, conflicted, or tied to a changed host/measurement identity.

The neutral workbench puts a selected node’s accounting history next to its next useful check. Search or filter the inventory, inspect samples by pointer or keyboard, and switch to daily evidence or collection activity. Save summary downloads the current JSON locally. Each subject retains observed time versus elapsed time, coverage, freshness, workload context and evidence limitations. High contention can reflect demand, reduced supply, or both. A low ratio does not establish who caused it; an above-threshold ratio does not certify your application's latency or error rate.

### Inspect changes, not just a score

Two locally bundled **uPlot** charts align accounting/execution with pressure and
CPU-limit context. Choose a time window, drag to zoom, inspect the same timestamp
by keyboard or pointer, and export a chart PNG or bounded display CSV. Missing
intervals stay gaps. Zoom changes the view, **not** the retained-window assessment.
The viewer makes no chart-CDN request and still needs no frontend build step.

## Give it to an agent

> Read `skills/vps-health/SKILL.md`. Discover my existing monitoring and expected nodes. Show the demo, then bootstrap the smallest useful private workspace. Ask for approval before recurring collection or installing generated timer files. Account for every configured node; show gaps, workload context and multi-day evidence. Keep reports local and explain uncertainty. Draft correspondence only when I explicitly ask; never send it or change a server automatically.

Copy or install the **entire** skill folder, not just `SKILL.md`. Automatic discovery depends on your agent's documented skill-directory convention; explicit file-path invocation works without relying on a particular UI. [Operation reference](skills/vps-health/references/operation.md) · [Bootstrap recipes](skills/vps-health/references/bootstrap.md)

## Commands and boundaries

| Command | Purpose | Side effect |
|---|---|---|
| `bootstrap` | Private workspace, policy and demo/configuration | New local directory only |
| `agent-plan` / `agent-start` | Read-only scoped plan / apply one approved bounded runtime | The host agent obtains scope approval; no external writes |
| `agent-status` / `agent-stop` | Verified process/readback / cooperative owned-run stop | No arbitrary PID signals or deletion |
| `agent-request` / `agent-resolve` | Private capability handoff and host-reported results | Not OAuth or send permission |
| `doctor` / `brief` | Read-only setup diagnosis / prioritized local action list | No network, repairs or notifications |
| `providers` | Dated plan-class references and official source links | Offline; no policy changes |
| `collect` / `watch` | One tick / bounded foreground recurrence | Passive reads or bounded approved API GETs |
| `dashboard` / `serve` | Refresh snapshot / live loopback view | Derived local files / read-only local port |
| `export` | Immutable summary package | New local directory; no raw database or credentials |
| `schedule` | Generate user timer files | Files only; no installation |
| `draft-email` | Concise human-review draft, explicitly requested | Private text file only; never sent |
| `demo`, `collect-local`, `collect-prometheus`, `report`, `verify`, `compare` | Original capture/report workflow | Local evidence and bounded optional reads |
| `learn` | Sanitized proposal from a workspace or verified report | Local proposal; no code change or upload |
| `capabilities` | Machine-readable workflow and safety contract | None |

A performance-review draft requires explicit approval, a stated service impact and sufficiently covered, fresh, at least 48-hour sub-threshold observations. The separate `--purpose plan-question` asks about the exact owner-provided plan without inventing a performance claim; it also requires explicit drafting approval. It includes the actual UTC window and uncertainty. A template can be generated earlier with `--example`, visibly marked **DO NOT SEND**. **85–87% alone is not a reason to message support.** No bundled command sends email, migrates a host or runs stress tests. See [correspondence examples](skills/vps-health/references/correspondence.md).

## Improvements that survive the next run

The skill is allowed to propose its own improvement, not authorize it. A maintainer reviews a sanitized proposal, synthetic failing regression, code change and safety/privacy results before a versioned release. Telemetry cannot rewrite policy, publish a capture or create a provider message. See [the improvement contract](skills/vps-health/references/improvement.md).

## Verification and limits

```bash
python3 tools/validate.py
```

The same command runs in CI on Python 3.10 and 3.12, including the original report contracts, persistent history, actual loopback server, consent gates and exported-folder CLI bootstrap. Agent-behavior scenarios are supplied separately; they are not claims that every agent UI or model was evaluated.

This is a **local investigation workspace**, not an internet-facing hosted dashboard, a universal provider-blame classifier, or a backup product. Keep the local viewer behind loopback and SSH tunnelling. Default views retain a three-day window (configurable to 14 days); raw captures remain private in SQLite until you archive the workspace. There is a 256 MiB compressed-raw budget: reaching it stops ingestion rather than deleting evidence. Normalized database storage is additional. Summary exports need the retained private database for full historical replay.

Provider references cover Contabo, Hetzner, DigitalOcean, Akamai/Linode and AWS; read the actual product terms rather than treating provider names as equivalent CPU guarantees. Those references are not integrations that provision or migrate instances.

Inspired by the public progressive-disclosure and self-testing principles at [Jeffrey's Skills](https://www.jeffreys-skills.md/) and the verification discipline in [pstack](https://github.com/cursor/plugins/tree/main/pstack). Original MIT-licensed implementation and prose; no paid skill content or private operational data is redistributed.


## How we improve the skill

The [improvement method](docs/skill-improvement-method.md) connects local skill
research to concrete changes and tests. A private indexing tool distinguishes
finding a skill from reading or applying it. The [0.3.0 applicability receipt](docs/improvement-v0.3.0.json)
records the seven selected local JSM skills, their versions/hashes, which guidance
fit, and which assumptions were rejected. Their licensed text is not redistributed.

Dashboard changes now have an actual-loopback browser suite in CI in addition to
the Python and exported-folder checks. The user runtime still has no browser-test
or third-party Python dependencies. A browser assertion, a screenshot, and a real
multi-day operational result are different kinds of evidence; none substitutes
for the others.

Release evidence: [v0.3.0 verification receipt](docs/verification-v0.3.0.md).


The [0.4.0 study receipt](docs/improvement-v0.4.0.json) adds nine more installed
JSM sources and Emil's public design guidance, with original application decisions
and test mappings. The [chart design](docs/chart-investigation-design.md) records
why one pinned library was selected and what remains outside the evidence claim.
`tools/package_release.py` tests the actual downloadable skill ZIP before release.
