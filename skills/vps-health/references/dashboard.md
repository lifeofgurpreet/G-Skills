# Reading the workbench

## Start with the evidence state

The three counts describe the configured inventory: within accounting tolerance,
watch/investigation, and evidence on hold. They do not certify application health
or establish a complete provider-account census. A node with a high retained
mean can still be on HOLD because its measurements are stale or incomplete.

## Inspect one node

Select a node in the table or the history selector. Its accounting trend and
next useful check appear together. CPU execution, pressure and throttled-period
context remain distinct. Pressure does not identify its cause, and the fraction
of throttled periods is not a percentage of lost CPU time.

Use the sample slider with arrow keys, Home and End, or point to the chart to
inspect a retained UTC sample. The graph uses at most 600 display points. It
keeps bucket boundaries, minima, maxima and an invalid point when present.
Explicit breaks come from the original intervals, not from gaps in the reduced
plot. This prevents a short dip disappearing just because every second point
was dropped. Raw captures and aggregate calculations are not downsampled.

## Find the relevant evidence

Search by node alias or filter by evidence state. A no-match result is explicit
and does not change the configured inventory. The Evidence view shows UTC daily
rollups, including partial days. Collection shows observed attempts and failures.
Overview returns to the selected node; live refresh preserves selection and
expanded limitations.

Save summary downloads the current derived JSON locally. It does not send data,
include endpoint credentials, or produce a complete raw database backup. Use the
CLI export and archival procedure for the appropriate evidence package.

## When the viewer disconnects

The last valid values remain frozen with a visible warning. Invalid status data
is rejected before it can partly replace the screen. A refreshed browser is not
a refreshed measurement: the collector still needs to run separately. Do not
use a frozen screenshot as evidence that the node is currently healthy.

The viewer stays read-only and loopback-only. It loads no third-party fonts,
analytics, CDNs or scripts. Use the documented SSH tunnel for remote access;
do not expose the lightweight viewer as an internet-facing service.

## For agents changing this interface

Keep layout, evidence semantics and provenance aligned. Every visible control
needs an actual user-input check. Verify keyboard, phone-size layout, empty,
dense, malformed and disconnected states—not only a screenshot with three good
nodes. The repository's browser suite starts the real server with synthetic
workspaces; its developer dependencies are not required by skill users.


## Chart investigation in 0.4

The upper uPlot pane compares accounted CPU time with recorded CPU execution.
The lower pane shows CPU pressure and throttled-period fractions on their own
explicit axes. Cursor time and horizontal range are synchronized. These series
are context for an investigation, not interchangeable measures of lost CPU.

Use 6h, 24h, 72h or All history; drag horizontally for a custom view. Refresh
preserves the selected view and subject. The full-window mean and decision do
not change when zooming. This prevents a convenient crop from silently clearing
a HOLD or presenting a short bad period as the whole retained window.

Use the sample slider with keyboard arrows/Home/End, or open the displayed-data
table. A value that was not measured stays unknown. Independent gaps and extrema
are retained in the bounded display; a chart alignment placeholder is not a
sample and is never exported as one. Small histories are not reduced.

PNG captures the rendered chart panes. CSV exports only displayed observations
inside the selected view. Both are explicit local actions; neither is a provider
submission or an independently signed evidence bundle. Retain the private
workspace and normal export for deeper replay. The pinned MIT library, CSS and
license are bundled; there is no browser CDN or third-party Python dependency.


## Operator views in 0.5

The interval ribbon uses the full normalized observation intervals and preserves
minimum, mean and coverage per cell. Selecting it changes only the chart window.
Arrow keys navigate cells; Enter selects. The numeric sample inspector remains
an alternative to colour and pointer interaction.

Attention uses the same `brief` result as the CLI. Acknowledgment is tab-local and
never clears evidence; recovered findings lose the acknowledgment before a later
recurrence. Desktop alerts require an explicit click and browser permission, only
run while the viewer is open, and do not repeat unchanged findings. The operating
system API may be unavailable; use the inbox instead. No notification service is
installed. Browser checks simulate the OS permission boundary and separately
exercise the real loopback viewer, SQLite, actions and downloads.

Setup recipes describe effects and stop procedures but execute nothing in the
browser. Provider cards are bundled dated references and open primary sources
only when the user follows a link. They do not discover a plan or modify policy.
