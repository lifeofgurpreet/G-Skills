# VPS Health

**One skill in the [G-Skills collection](../../README.md).** Give the complete
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

[Skill roadmap](../../docs/skills/vps-health/ROADMAP.md) ·
[Review of both Gemini proposals](../../docs/skills/vps-health/GEMINI-REVIEW.md) ·
[Changelog](CHANGELOG.md) · [Contributor guidance](AGENTS.md).

The collection's Beads graph is a development tool; users need neither Beads nor
a GitHub account to run this skill. Real client/OAuth trials, additional platforms,
complete estate coverage and multi-day field acceptance remain explicit tasks.
