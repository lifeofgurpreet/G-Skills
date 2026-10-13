# Chart investigation, not decorative telemetry

## Decision and scope

The operator needs to compare accounting with workload context at the same time,
inspect a troublesome interval, see what is unknown, and retain what they saw.
A library upgrade is useful only if those actions work without weakening the
assessment. This release extends the current private workspace rather than
adding another collector, frontend framework or cloud service.

Use one pinned **uPlot 1.6.32** distribution for the synchronized time-series
panes. Its JavaScript and CSS add about 53 kB before compression and are served
inline from the reviewed package. The exact commit, hashes and MIT notice live
in `skills/vps-health/assets/vendor/uplot/manifest.json`. A browser never needs
an external chart CDN. Package size is not a target; reproducible operation is.

The existing SVG renderer was examined as the zero-dependency alternative. It
would require maintaining selection, synchronization and image export ourselves.
Apache ECharts was also considered through its primary documentation: it offers
broader chart types, but that broader integration is not needed for these four
aligned channels. No comparative speedup or upstream benchmark figure is claimed.

## Interaction contract

Accounting and recorded execution occupy the upper pane. CPU pressure and the
fraction of throttled periods occupy the lower pane. They share UTC coordinates
and cursor position, not an invented causal relationship or interchangeable unit.
A 6h/24h/72h/all-history control and horizontal drag inspect the view. They do NOT
recompute the full-window assessment, change its policy or clear a HOLD.

Keyboard sample controls and a numeric observation table provide alternatives
to pointer/canvas inspection. Channel buttons carry text, state and line patterns;
colour alone is not the meaning. Touch controls have 44px minimum targets. PNG
and CSV exports are explicit local actions. A display CSV is the bounded displayed
projection, not a full raw evidence archive, and the PNG is not attestation.

Use immediate response for repetitive inspection. Emil Kowalski's public guidance
on interaction frequency and purposeful motion informs this choice: chart data
does not tween between values, keyboard navigation does not wait on transitions,
and reduced-motion preferences are respected. Press feedback must not shift the
layout. This is an application of design reasoning, not an assertion that the
entire external design-audit framework has been performed.

## Evidence invariants

The backend retains independent minima, maxima and invalid markers for all four
channels in a bounded projection. Breaks derive from every original observation,
not only the selected points. Missing workload context never becomes zero. A gap
in one channel does not needlessly erase a valid different channel. Small histories
are kept intact rather than downsampled merely because reduction is available.

The uPlot adapter uses `null` for an intentional missing span and `undefined` for
an alignment-only placeholder. Placeholder timestamps are not measurements: they
never enter the inspector or exported CSV. No smoothing, interpolation, stacked
percentages or chart-side health verdict is introduced. Weighted policy continues
to run over the original observations.

Live refresh keeps the user's selection and view. Invalid responses preserve the
last valid data with a visible warning. Summary values, proof age and chart range
remain distinguishable. Two chart instances are reused, resized and destroyed;
a refresh must not grow a hidden pile of canvases or listeners.

## Packaging is part of the user journey

The previous release required a manual correction to the standalone ZIP root.
`tools/package_release.py` encodes the fix: archive one committed tree, include
licenses and the pinned vendor payload, verify `vps-health/SKILL.md` at the root,
extract the actual ZIP, run its demo bootstrap and export, and record hashes.
The command neither creates a release nor uploads anything. CI must pass before
an operator publishes the immutable source and those verified artifacts.

## Primary sources

- [uPlot source and design](https://github.com/leeoniya/uPlot)
- [Pinned uPlot release](https://github.com/leeoniya/uPlot/tree/1.6.32)
- [Apache ECharts modular usage](https://echarts.apache.org/handbook/en/basics/import/)
- [Emil design-engineering skill](https://github.com/emilkowalski/skills/tree/main/skills/emil-design-eng)
- [You don't need animations](https://emilkowal.ski/ui/you-dont-need-animations)
- [W3C complex-image alternatives](https://www.w3.org/WAI/tutorials/images/complex/)

These references are method inputs, not endorsements. Local JSM editions, selected
sections and test consequences are documented in the original improvement receipt;
paid skill bodies and private library paths are not redistributed.

Verification and boundaries: [0.4.0 receipt](verification-v0.4.0.md).
