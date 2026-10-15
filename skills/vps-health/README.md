# VPS Health

**One skill in the [G-Skills collection](https://github.com/lifeofgurpreet/G-Skills).** Give the complete
folder to your coding agent to set up and operate a private VPS investigation:
scoped collection, retained history, a live local dashboard, workload context and
honest next actions. The user supplies goals, access and consequential approvals;
the agent does routine configuration and verification.

Read [SKILL.md](SKILL.md) for the agent workflow. Runtime requirements: Python
3.10+ with SQLite; passive host diagnostics and managed execution are Linux-only.
Demo/offline paths are portable. No Node build, chart CDN or additional model
account is needed to view local evidence.

## What it does

- Plans and starts one bounded owned runtime, verifies actual process identity,
  retains a private handoff and stops only the intended run.
- Uses passive local observations or explicitly authorized existing Prometheus/
  Loki sources. It does not install another monitoring stack by default.
- Shows linked CPU/workload charts, observed coverage, missing data, attention
  items, runtime progress and dated provider-plan references.
- Retains passive storage, memory and network context alongside the CPU evidence:
  per-device request means, PSI total deltas, guest swap/fault activity and interface/
  softnet counters. Guest CPU/clock traits can be compared without pretending to
  attest the underlying physical host or detect a fake migration.
- Generates private reports, replay receipts and explicitly requested review
  drafts. Actual connectors belong to the host agent, with native authentication
  and separate read/draft/send authorization.

## The evidence workbench

Read the selected node's actual finding and next useful check beside its linked
measurements and coverage. **Review next step** pins the full assessment and exact
private agent task while the viewer can refresh behind it. **Pause updates** freezes
this tab, not the collector. Cmd/Ctrl+K searches local nodes and actions; mobile
navigation uses the same views without squeezing them into a horizontal strip.

A private derived snapshot is not a complete raw archive, and the minimal support
report is a separate export. Missing data, held evidence and synthetic examples
stay explicitly labeled. The [workbench guide](references/dashboard.md) describes
the real controls; routine investigation still belongs to the agent, not the human.

## Preview status

The Linux collector, retained evidence, local viewer and managed lifecycle have
source, real-process and extracted-release checks. Claude Code project discovery
has also been exercised. That is not certification of every client, sandbox,
provider or multi-day workload. Read the [current support scope](https://github.com/lifeofgurpreet/G-Skills/blob/main/docs/preview.md)
before relying on a feature that needs external access. Codex/native-client and
completed sustained-pilot gates remain explicit.

## Start through your agent

> Use this VPS Health skill to investigate the targets I authorize. Inspect what
> we already have, scaffold or resume the private workspace, start a bounded plan
> and show me the dashboard. Ask only for missing scope, authentication or
> consequential approvals. Preserve the evidence and do not contact a provider
> or change server settings without a new request.

The agent should use [agent-workflow.md](references/agent-workflow.md), not hand
you a list of commands to type. The following is only a safe demonstration or a
fallback debugging recipe, run from this skill folder:

```bash
python3 scripts/vps_health.py bootstrap --mode demo --workspace /tmp/vps-demo
python3 scripts/vps_health.py serve --workspace /tmp/vps-demo
```

The demonstration is synthetic. A refreshing browser is not an active collector,
a running worker is not three days of history, and a good CPU percentage is not
a certificate of application health. See [first-hour recipes](references/first-hour.md),
[operator playbook](references/operator-playbook.md) and [forensic context](references/forensics.md).

## Evidence and authority

The default accounting preferences tolerate >=90%, watch 80–90% and investigate
below 80%. They are not provider guarantees. Pressure and workload limits can
coexist with reduced supply; snapshots, CPU model labels, clocksource choices and
guest-visible fingerprints do not uniquely establish the cause.

No implicit active CPU/RAM/storage/network test, public IP lookup, provider message,
reboot or migration is performed. Missing evidence remains unknown. The existing
provider completion record and comparable workloads remain separate from guest
trait comparisons. [Method](references/method.md) · [Providers](references/providers.md) ·
[Correspondence](references/correspondence.md).

## Development and releases

VPS Health is independently versioned in `skill.json`. New release tags use
`vps-health/vX.Y.Z`; older collection-labelled `v0.x` tags remain historical.
Install this entire folder or its standalone ZIP, not only SKILL.md.

[Skill roadmap](https://github.com/lifeofgurpreet/G-Skills/blob/main/docs/skills/vps-health/ROADMAP.md) ·
[Review of both Gemini proposals](https://github.com/lifeofgurpreet/G-Skills/blob/main/docs/skills/vps-health/GEMINI-REVIEW.md) ·
[Changelog](CHANGELOG.md) · [Contributor guidance](AGENTS.md).

The collection's Beads graph is a development tool; users need neither Beads nor
a GitHub account to run this skill. Real client/OAuth trials, additional platforms,
complete estate coverage and multi-day field acceptance remain explicit tasks.


## Report a problem without exposing the workspace

Use **Support report** in the live viewer or ask the agent to run `support-report`.
It creates an offline minimal summary of versions, check categories and counts—not
an upload or a general redaction of your data. Review the small result before sharing.
Do not attach the normal summary, dashboard, database or raw agent trace to a
public issue. [Support workflow](references/support.md).
