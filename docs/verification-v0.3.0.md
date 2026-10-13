# v0.3.0 verification and research receipt

## Research scope

The authorized local JSM catalogue contained **125 installed entries**; the
broader local skills directory contained **352 entry points**, including other
sources. These are catalogue counts, not claims that every instruction was read.
Seven relevant JSM skills were selected and studied, with applicable references:
UX audit, UI polish, interactive visualization, web-app end-to-end testing,
operationalizing expertise, repeated skill application and agent CLI ergonomics.
Installed editions, hashes and original applicability decisions are recorded in
`improvement-v0.3.0.json`. Private paths, catalogue bodies and paid text are not
included in this repository.

Pstack's design-space and prove-it-works leaves were read from installed release
`997ffc7fe26bdaa6478a14e7f5b8d5f9ed747102`. The method was applied selectively: the
UI-polish entry explicitly does not fit a fundamentally wrong visual structure,
and a cinematic visualization stack does not fit this dependency-free viewer.
No independent reviewers, model triangulation, universal installation check or
numerical “Jeffrey-level” quality score is claimed.

## Design comparison

Two original working layouts were compared with the same synthetic status:
a table-first inventory and a chart-first workbench. The table-first option
favoured dense scanning but displaced the explanation below the initial view.
The selected workbench places retained history, uncertainty and the next check
side by side. Search/filter inventory remains below; Evidence and Collection
are actual navigable views. The palette is neutral stone, paper and graphite;
state text and patterns carry meaning rather than a colourful status-card wall.
Desktop and phone layouts were reviewed separately.

## Reproduced defects and implementation

The old display selected every Nth point. Two status-level tests proved that it
could erase a short 42% observation and an invalid interval from an otherwise
95% line. The new bounded projection retains bucket boundaries, minima, maxima
and an invalid point, with break markers derived from all original intervals.
A further test proved that one missing interval must produce a break, not only
long gaps. Aggregate policy, raw evidence and coverage calculations are unchanged.

The real loopback browser test initially passed seven interaction groups, then
failed because malformed history was accepted as a refresh. The complete display
contract is now checked before replacing state. Disconnects and malformed data
retain the last valid view with an explicit warning. This is not a silent retry
or a promotion of old values to fresh evidence.

## Executable validation

`python3 tools/validate.py` passes **113 tests**: 46 collector/report, 56 workspace
and 11 private study-tool tests. It also exports only the skill folder and runs
its real CLI bootstrap, dashboard, export, learning and original report/replay
paths. The private study-tool test uses a temporary directory outside Git; this
host's default temporary root was itself a Git repository, so the normal temp
root was set explicitly rather than weakening the privacy check.

`python3 tools/test_dashboard.py` runs **13 browser scenario groups** against the
actual read-only loopback HTTP handler, using synthetic workspaces. It covers
state counts, selection, pointer/keyboard inspection, search/filter reset, real
navigation, retained controls on refresh, JSON download, disconnect/recovery,
malformed payloads, phone/tablet/desktop layouts, keyboard focus, main text/status
contrast, a 100-subject fixture and absence of external asset requests or
JavaScript errors. The GitHub workflow runs this suite and retains its synthetic
screenshots and exact-template receipt. Browser tools are developer dependencies,
not new dependencies for an installed skill.

The first browser source revision was `7e080f8f1cf6797049ec663d110470ea3a885da9`;
its failure is retained in Actions run `38379314252`. The corrective revision
`d7ff152477559476051ef0c892d734871c694e0b` passed the corresponding browser suite
in run `38379733326`. Final release-tree Python and browser checks must both pass
before merging/tagging. An earlier passing commit is not substituted for them.

## Boundaries

This release changes the user workflow, chart display and contributor method.
It does not alter VPS thresholds, install timers, collect from the private fleet,
contact a provider or publish paid/local operational data. No permanent viewer
or collector is left running by verification.

Phone-size browser checks are not physical-phone testing. Colour-contrast and
keyboard assertions are not a complete accessibility certification. Synthetic
multi-day examples are not real multi-day performance qualification. A clean
chart or passed software test cannot establish provider responsibility.
