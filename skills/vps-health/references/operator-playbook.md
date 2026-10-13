# Operator playbook

This is a private investigation workspace, not an automatic host controller.
It can tell you what evidence exists, where it is weak and what to examine next.
It cannot prove every cause of slowness from CPU accounting alone.

## The repeatable loop

**Diagnose setup → collect → inspect attention → compare context → retain a report → choose an authorized next step.**

Use `doctor --workspace PATH` after setup, an upgrade or an unexplained failure.
It reads configuration, checks chart-file integrity, performs a bounded read-only
SQLite quick check, reports platform suitability and named credential presence,
and explains evidence/retention gaps. It neither contacts endpoints nor repairs
files. Never treat a fresh sample as proof that a daemon is running.

Use `brief --workspace PATH` for the same prioritized findings as the dashboard.
The command prints structured JSON and does not send a notification. Its output
is suitable for an already approved agent or scheduler, but printing a command
never authorizes that command's side effects.

| Finding | What it establishes | Useful next check |
|---|---|---|
| Collection gap | Recent evidence is absent, stale or failed | Check doctor, the configured collector and the latest error; avoid starting a duplicate collector |
| Identity/conflict | Different epochs or conflicting values cannot be combined safely | Inspect the inventory binding and retained captures before restarting the comparison window |
| Collect history | The window is too short or insufficiently covered | Keep gathering observations; do not extrapolate a snapshot into a day |
| Performance review | The full-window accounting result is below the chosen level | Compare service impact, workload concurrency, limits, pressure and the purchased plan |
| Workload pressure | The accounting screen can look acceptable while pressure remains high | Inspect the affected application's latency/errors and resource limits |
| Watch | Between the chosen watch and investigation levels | Observe service impact before making a support decision |

No finding proves provider responsibility. High demand and reduced supply can
both create pressure. A quiet host can still contain a quota-limited workload.
Do not describe a throttled-period fraction as percent CPU time lost.

## Use the dashboard as an investigation tool

The selected node has linked accounting/execution and workload-context charts.
The evidence ribbon is calculated from full normalized intervals, not the reduced
chart dots: each cell retains minimum, mean and observed coverage. It highlights
short dips even when the average looks good. Missing and partial time remain
visually distinct. Select a cell or drag the chart to inspect the same interval.
The assessment always uses its full retained window, not the zoomed view.

Use the keyboard sample inspector or numeric table when a pointer or colour
cannot communicate the values. PNG and CSV exports are local; displayed CSV is
not the full raw replay archive. A failed refresh preserves the last valid view
with a warning. A busy refresh is visibly disabled until the request completes.

## Notifications and acknowledgment

The Attention inbox exists without permission prompts. Desktop alerts are optional:
click Enable desktop alerts and approve the browser prompt. They apply to new
urgent/review findings while this viewer is open. Current items are not replayed
as a startup alarm storm, and an unchanged finding is not repeated on every poll.
Browser/platform support varies; the inbox remains the fallback. There is no
background service worker, email sender, webhook or closed-tab guarantee.

Acknowledgment is local to the tab session. It changes unread state only; the
finding, measurements and HOLD stay intact. A condition that disappears and later
returns is unread again. Acknowledgment does not acknowledge a provider ticket or
permit a migration. Desktop text avoids node names and raw measurements.

## Provider context and correspondence

Run `providers --provider NAME` or use the Providers view. These are dated
primary-source references, not live contractual verification. At 90 days the
reference requests a recheck; it does not fetch or rewrite itself. Distinguish
shared/dedicated allocation, sustained-use allowances, burst/credit models and
billing behavior. Match the exact plan rather than the brand alone.

A plan question is different from a complaint. `draft-email --purpose plan-question`
requires an exact owner-provided plan and explicit drafting approval, but makes
no claim that the system is defective. The default `performance-review` purpose
retains its fresh, sufficiently covered, >=48h sub-threshold evidence gate and
requires the user's observed service impact. See [correspondence.md](correspondence.md).
There is no send command. Neither draft grants authority for a reboot or migration.

## The next evidence to collect—not a forced diagnosis

CPU accounting does not establish storage latency, network loss, application
errors or availability. When CPU evidence does not explain a symptom, use the
owner's existing application and infrastructure instruments, with a matching UTC
window. Record the metric, baseline, workload, change and error count. Do not
invent a healthy default for a missing instrument.

For a controlled experiment, specify target, workload, budget, duration, stop
conditions and rollback before seeking authorization. Change one factor at a
time and retain rejected/failed runs. This package does not provide an automatic
stress runner or cloud mutation client. On burstable EC2, authorized CloudWatch
credit evidence is a separate required input; it is not collected by this skill.

## Handoff to another coding agent

Give the installed skill path, private workspace path, selected collection mode,
exact expected subjects and known exclusions, last accepted observation, active
process/scheduler and stop command. Include the current brief, unresolved evidence
gaps and the next approved task. Do not pass token values or a public copy of the
private database. The dashboard's Copy agent task gives a small task with these
authority limits; it does not spawn an agent or execute a terminal command.

## When to stop claiming more

A configured timer is not a verified running timer. A browser test is not a
physical-device test. A synthetic three-day demo is not a multi-day field trial.
A local integrity hash detects changes; it is not independent attestation.
Provider policy references are not provider API integrations. Preserve these
boundaries in the human handoff and in any learning proposal.
