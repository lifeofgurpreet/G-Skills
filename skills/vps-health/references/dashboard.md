# Workbench: from observation to the next useful action

The agent performs the investigation. The human sees the evidence and makes the
access or consequential-action decisions. The interface is a local instrument,
not a promotional page, a provider-fault classifier or a browser terminal.

## 1. Start with the selected investigation

Select a configured node in the table, its selector or the local search menu.
The main heading and next step come from the same operator brief as the Attention
inbox. They do not use a second frontend decision rubric. A high mean with stale
or incomplete evidence stays HOLD; good accounting with workload pressure can
still require investigation.

The three compact counts describe only configured nodes: within accounting
tolerance, watch/investigation, and evidence on hold. They are not a provider-account
census or a service-health certificate. Coverage is the amount of the assessment
window actually observed, not confidence that a provider is responsible.

## 2. Read the measurements in context

The upper bundled uPlot pane compares accounted CPU time with recorded execution.
The lower pane shows CPU pressure and throttled-period fractions. All use explicit
axes and a synchronized timestamp; these quantities are not interchangeable.
Accounted time is not CPU utilization. The fraction of throttled periods is not
percent CPU time lost. Neither correlation nor a CPU model proves host-side fault.

Choose 6h, 24h, 72h, All history or drag a custom window. **The chart range is only
a view.** It cannot rewrite the full assessment mean, erase a HOLD or turn a short
bad interval into a full-day conclusion. Refresh retains the chosen node and range.
Use channel toggles, exact sample values and the numeric table rather than relying
on colour alone.

Up to 600 display points preserve extrema and explicit missing intervals. The
raw captures and aggregate calculations are not downsampled. The evidence ribbon
uses full normalized intervals, retaining per-cell minimum, mean and coverage;
it is not a second decimation of the chart. Arrow keys move through cells and
Enter selects an interval. Missing and partially covered cells remain distinct.
Guest diagnostics show the latest retained storage/memory/network context, with
its own currentness and uncertainty; old or unsupported context stays missing.

The contextual mean captions now include their own measured duration, coverage
and current/sparse/stale status. **Evidence** adds the full source window, observed
preference-band durations, missing versus invalid time, and optional shortfall-run
and recorded-execution details. Its node selector stays aligned with Overview.
These are the CLI's existing values, not numbers recomputed from chart pixels.
Legacy snapshots lacking a temporal profile show missing coverage explicitly.

## 3. Review a pinned next step

**Review next step** opens the selected finding, full assessment window, accounted
mean, observed coverage and remaining limitations together. It is pinned to the
snapshot from when it opened. Automatic refresh may update the background, but
it cannot silently rewrite what is being reviewed. Close and reopen for new data.

The exact agent task is available to inspect before copying. It includes the
selected subject, full window, relevant observations, canonical next check and
limits. It does not confer permission to change a host, run probes, connect an
account or contact a provider. Copying is local preparation, not agent execution.
If the browser denies clipboard access, the same text is selected inside the
review for manual copying; no external fallback or upload is attempted.

The agent that already owns the workspace should obtain the same current context
from `brief`, `doctor`, the retained workspace and its native tools. Do not assign
the human routine CLI/config work just because a copy button exists. Copying is
an optional handoff between sessions or tools, not the only operating path.

## 4. Pause the view, not the collector

**Pause updates** freezes displayed readings and stops automatic polling in this
tab. The worker and approved collection continue independently. A visible pause
label and snapshot timestamp keep that distinction clear. Pausing during an
in-flight request prevents the late response from replacing the chosen snapshot.

**Refresh** while paused reads once and leaves the view paused. **Resume updates**
starts the view's normal read cycle again; it does not start or restart a collector.
If the viewer disconnects or receives invalid data, the last accepted values remain
visible with a warning. A screenshot or refreshing tab is never proof that new
measurements are being collected.

## 5. Navigate without losing the investigation

Use **Find anything**, Cmd+K or Ctrl+K to search configured node names and local
views/actions. Arrow keys choose a result, Enter opens it, and Escape closes the
menu and restores focus. It is local search, not a shell, chatbot or internet
search. Offline views do not offer live-only pause or support-fetch actions.

On smaller screens, **Menu** reveals the same navigation without a compressed
horizontal strip. Selecting a view closes it and moves focus to the content.
Provider reference disclosures, selected range and evidence limitations stay open
through background refresh instead of collapsing during reading. These controls
operate through native buttons, inputs and dialogs, with reduced-motion behavior.
Physical-device and assistive-technology qualification remain separate from the
simulated phone-size and keyboard browser checks.

## 6. Choose the right export

**Export snapshot** saves the currently retained derived JSON locally. It contains
node identifiers and observations and is private by default. It is not a complete
raw database archive. Chart PNG/CSV are view-level exports: the PNG includes the
displayed UTC window and synthetic label where applicable; CSV includes only
actual displayed observations in that window. Alignment placeholders are not data.

**Support report** is separate. It requests the minimal versions/categories/counts
report from the live local viewer and excludes raw investigation details. Review
it before sharing. An offline HTML snapshot has no live support endpoint. Use the
CLI export, integrity/replay and private archival procedures for deeper evidence;
never substitute a screenshot for the retained source records.

## 7. Agent, providers and external actions

Agent activity reports actual owned worker identity, time budget, recorded cycles
and capability needs. It cannot prove that a model session is online or that a
multi-day pilot is complete. HOST_REPORTED_AVAILABLE is a recorded claim requiring
rechecking of the host's actual tools, not independent OAuth proof.

Setup explains routes the executing agent can take; its commands are recipes for
that agent, not homework. Provider cards contain dated references and verified
scope distinctions, not an inferred purchase or universal CPU promise. Following
a primary-source link is the user's explicit action. No browser control installs
a connector, runs a command or sends a message. Provider contact, host changes
and active probes need their own current authorization.

## For agents changing the interface

Keep a single evidence authority and distinguish viewer state from collector
state. Avoid cinematic scenery, glass effects, invented scores or unsupported
“host fault detected” copy that makes uncertain evidence appear conclusive.
Progressive disclosure should remove repetition, not hide missing data.

Verify the actual local server, offline exported HTML, mobile navigation, zero/
single/dense inventories, malformed/disconnected states and private exports.
Exercise every visible action with real user input. Read rendered screenshots
separately from functional tests. The installed user still needs no chart CDN,
Node build, remote font service or new monitoring stack.

For an integrity-checked multi-file review, the agent runs `export` then `verify`.
The browser snapshot alone is not a raw replay archive or a directory manifest.
See [the export workflow](exports.md) for exact result semantics.
