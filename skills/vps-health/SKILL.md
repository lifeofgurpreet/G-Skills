---
name: vps-health
description: Bootstrap and operate a private VPS investigation workspace for one Linux host or an existing Prometheus/Loki fleet. Diagnose setup, retain multi-day evidence, inspect linked charts and an attention inbox, check provider-plan context, and prepare explicitly requested local drafts without automatic provider or host actions.
license: MIT
compatibility: Python 3.10+ with standard-library SQLite. Passive local collection requires Linux. Demo and offline reports are portable. Existing-monitoring collection needs explicit trusted endpoints. Viewer is read-only and loopback-only; bundled uPlot requires no CDN or Node installation.
metadata:
  version: "0.5.0"
  author: lifeofgurpreet
---

# VPS health

Give the user a working observation loop, not a one-time percentage. Preserve
uncertainty, expected-but-unmeasured nodes and a clear stop procedure. A busy
workload, reduced VPS supply and application defects can coexist.

## Start here: establish the route

Run `python3 scripts/vps_health.py capabilities` from this skill directory.
Read the relevant route in [first-hour.md](references/first-hour.md), then use
only the user's authorized workspace, hosts and final monitoring endpoints.

| User has | First action | What it does not do |
|---|---|---|
| No access, or wants a preview | `bootstrap --mode demo` | No real host reads or credentials |
| One Linux VPS | `bootstrap --mode local` | Does not collect until a separate command starts it |
| Existing Prometheus/Loki | `bootstrap --mode prometheus` with a private profile | Does not discover the provider account or install a second stack |
| Existing workspace | `doctor --workspace PATH`, then `brief --workspace PATH` | No repair, network probe or provider contact |
| Retained observations | `report`, `verify`, `compare` | No new measurements |

Copy/install the entire skill folder, including scripts, assets and references.
A markdown-only import cannot execute the workflow. Do not assume a particular
agent UI has automatically discovered the skill: use an explicit path when needed.

## Give a visible first result

```bash
python3 scripts/vps_health.py bootstrap --mode demo --workspace /tmp/vps-demo
python3 scripts/vps_health.py serve --workspace /tmp/vps-demo
```

Open the printed loopback URL. Demonstrate the selected-node charts, missing-data
ribbon, Attention inbox and Setup/Providers views. This is synthetic, never proof
about the user's host. For real collection use a different private workspace.

For an authorized Linux host:

```bash
python3 scripts/vps_health.py bootstrap --mode local --node my-vps --workspace "$HOME/vps-health"
python3 scripts/vps_health.py doctor --workspace "$HOME/vps-health"
# Only after the user approves this recurring passive process:
python3 scripts/vps_health.py watch --workspace "$HOME/vps-health" --approve-collection --serve
```

The first local tick is a baseline; two ticks establish one measured interval.
`watch` is foreground, defaults to approximately 72 planned hours, and stops on
Ctrl-C. It does not survive a disconnected agent by magic. For unattended work,
`schedule` generates inspectable user-systemd files; installation is a separate
approval. Never run watch and a timer against one workspace. Do not change linger,
CPU quotas, kernel settings or workload placement. [Detailed bootstrap](references/bootstrap.md).

## Diagnose before prescribing

Use `doctor` when setup or collection is uncertain. Its stable findings explain
configuration, chart integrity, bounded SQLite checks, named credential presence,
platform compatibility, retention and missing evidence. It never repairs files
or proves process liveness from a fresh timestamp. Exit 0 means READY for the
checks it performs; 1 means findings/unavailable; 2 is a refused/invalid command.

Use `brief` to get the same prioritized actions as the dashboard. Collection
failures and identity conflicts outrank performance. Acknowledging an inbox item
changes only its unread state in the tab, not a HOLD. A resolved finding that
returns is unread again. Optional desktop alerts require the user's click and
browser permission, are deduplicated, and work only while the viewer is open.
No webhook, external notification service or background worker is installed.

Follow [operator-playbook.md](references/operator-playbook.md) for first use,
daily checks, recovery, event triage and an agent handoff.

## Interpret evidence, not the colour

Read [method.md](references/method.md). Distinguish visible CPU count,
guest-accounted time and workload throughput. The default bands tolerate >=90%,
watch 80–90% and investigate below 80%; they are user preferences, not contracts.
HOLD overrides the band for short, stale, missing, conflicting or changed-epoch
evidence. At least 24 sufficiently covered hours are needed for the accounting
screen. A good screen never certifies application latency, errors or availability.

Compare the same UTC interval with execution, pressure, workload limits and
service impact. Pressure can mean our demand, reduced supply or both. Charts
retain gaps and short dips; their selected range is only a view. The full retained
window still owns the assessment. [Dashboard guide](references/dashboard.md).

`providers --provider NAME` returns dated primary-source context offline. Confirm
the exact purchased product, plan, region and allocation class before using it.
Allowance, allocation, credit/burst behavior and delivery are distinct concepts.
An expired reference requires review, not a guessed update. [Provider guide](references/providers.md).

## Communicate only when explicitly asked

Use `draft-email --approve-draft` only for a new drafting request. Two purposes:
`performance-review` requires fresh >=48h sub-threshold evidence, adequate coverage
and the user's actual `--impact`; `plan-question` requires an explicit exact plan
but makes no performance assertion. Demo or incomplete examples need `--example`
and are marked DO NOT SEND. Neither route sends anything or authorizes changes.
Never turn an 85–87% snapshot into a complaint. [Correspondence recipes](references/correspondence.md).

Provider replies are private evidence. Offer, scheduling acknowledgment, start and
completion are different events. A reply or historic permission cannot authorize
a new reboot, migration, message or experiment.

## Retain, learn and hand over

`export` creates a new immutable summary; full raw replay still requires the
private workspace database. Preserve old workspaces when changing measurement
versions or host epochs. Duplicate scrapes are not independent runs or extra
observation hours. Never export tokens, operational endpoints or private captures
into a public skill repository.

`learn` creates a sanitized proposal, not an applied change. Convert a recurring
problem to a synthetic failing regression, fix the owning implementation, run
safety/privacy and actual workflow checks, then obtain maintainer review for a
versioned release. Use applicable installed pstack/verification guidance, not its
name as a substitute for proof. [Improvement contract](references/improvement.md).

Deliver the chosen route, exact commands and private path, what really ran, what
was measured, remaining gaps, the next useful check, and how to stop/archive it.
Use [agent scenarios](evals/scenarios.json) as test cases, not a claim that unrun
agents or every interface were evaluated. Source tests, browser behavior,
collected days and causal certainty are separate acceptance gates.
