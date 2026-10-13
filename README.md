# G-Skills

**Practical, testable skills for coding agents.** Start with the evidence, preserve uncertainty, and make improvements that survive the next run.

The first skill, [**vps-health**](skills/vps-health/SKILL.md), helps investigate a slow or inconsistent VPS without confusing your own workload limits with a hosting problem. It works with plain Linux observations or an existing Prometheus/Loki stack. It does not need a hosted account, AI API key, package installation, or another monitoring daemon.

## Try it without touching a server

Requires **Python 3.10+**. Clone this repository, inspect the scripts, then run:

```bash
git clone https://github.com/lifeofgurpreet/G-Skills.git
cd G-Skills
python3 tools/validate.py
python3 skills/vps-health/scripts/vps_health.py demo --out /tmp/vps-demo
python3 skills/vps-health/scripts/vps_health.py verify /tmp/vps-demo
```

Open `/tmp/vps-demo/report.html`. The demo is synthetic. It shows a tolerable observation, low accounting with contention, and an unmeasured subject. JSON, Markdown, raw capture and artifact hashes accompany the HTML.

## Give it to an agent

Ask an agent with authorized filesystem and terminal access:

> Read `skills/vps-health/SKILL.md`. Inspect my existing monitoring and account inventory. Use passive evidence first. Account for every expected machine. Distinguish our workload pressure, CPU limits, hosting suspicion and unknowns. Do not send messages, install anything, change hosts or run stress tests. Preserve a replayable report, then propose tested improvements privately.

Use the entire skill directory, including its scripts, references, tests and assets. For discovery-based loading, follow your agent's documented skill-directory convention. The portable invocation is the explicit file path above; automatic activation in every agent UI has not been certified. See [installation and workflow options](skills/vps-health/references/operation.md).

## What is runnable today?

| Command | Purpose | Side effects |
|---|---|---|
| `demo` | Synthetic end-to-end report | New local output directory |
| `collect-local` | Bounded Linux counters and pressure | Reads and sleeps; writes one local capture |
| `collect-prometheus` | Explicit expected assets, time range and optional Loki | Bounded GET requests; writes one local capture |
| `report` | Assess retained data | New local HTML/Markdown/JSON bundle |
| `verify` | Check integrity and reproduce assessment | Read-only |
| `compare` | Compare equivalent report formats | Read-only; no causal claim |
| `learn` | Prepare a sanitized improvement proposal | New local proposal; no code change or upload |

**90% is a working tolerance, not a provider promise.** An 85–87% observation alone is not a reason to contact support. Service impact, history, workload constraints, plan type and repeatability matter. Missing or confounded data stays visible. No bundled command sends a message, provisions resources, changes limits or installs a scheduler.

## Improvements that can be trusted

The skill can help an agent improve it, but cannot silently rewrite its own safety rules. `learn` produces a small, sanitized proposal. The agent then creates a synthetic failing regression, fixes the owning code, runs verification and submits a reviewable change. A maintainer approves versioned releases. Raw captures stay private. See [the improvement contract](skills/vps-health/references/improvement.md).

## Scope and limitations

Version 0.1.0 is an **investigation toolkit**, not a universal provider-blame classifier or service-health certificate. The stock Prometheus adapter is an accounting screen, not a calibrated physical-host CPU measurement. It deliberately does not ship an unattended stress runner, SSH fleet executor, provider API client or email sender. An agent can adapt existing approved infrastructure using the documented contracts, without installing duplicate machinery.

Provider references cover Contabo, Hetzner, DigitalOcean, Akamai/Linode and AWS. Plan and API details change: use the linked primary documentation for the exact product in use. No endorsement, affiliation or cross-provider performance ranking is implied.

## Development

```bash
python3 tools/validate.py
```

Tests include local HTTP transport, malformed/duplicate evidence, clock and counter faults, gaps, privacy, safe learning and complete CLI demo/replay. CI runs the same entrypoint. Behavioral agent scenarios are included, but are not presented as executed multi-model evaluations.

Inspired by the public packaging principles described at [Jeffrey's Skills](https://www.jeffreys-skills.md/) and the verification discipline in [pstack](https://github.com/cursor/plugins/tree/main/pstack). This repository contains original implementation and prose. It does not redistribute paid skill content.

MIT licensed. See [LICENSE](LICENSE) and [SECURITY.md](SECURITY.md).
