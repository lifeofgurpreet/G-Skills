# Evidence workbench: the design sprint implemented

Owning task: `gs-2uh.14`. This is the VPS Health interface, not a new visual
requirement for every skill in G-Skills. Reset Boost and the optional shared
operator-ui kit remain independent. We read the kit's current guide and retained
its useful ownership principles without forcing another skill's classes or theme.

## What the sprint changed

The user rejected scenic backgrounds, repeated concept-board dashboards and
visual decoration that made the product harder to understand. This release is
an implemented local interface, not another rendered concept. There is no scenery,
glass treatment, illustrative mountain, animated status theater or invented score.
A restrained surface, type hierarchy, actual chart axes and one selected finding
carry the investigation. No award, IDEO/frog review or designer endorsement is claimed.

The main question is: **What do these observations support, and what should the
agent check next?** The selected node, evidence state, canonical next action,
accounting/workload history and coverage appear together. The global attention
queue lives beside navigation instead of competing with the selected case.

The previous overview recommendation and inbox action differed. We reproduced
that mismatch and now project both from the existing operator brief. The new
`view-model.js` performs presentation only; it defines no threshold, causal score,
remote call or privileged action. Missing data and HOLD precedence stay in the
existing Python evidence authority.

## Implemented interactions

- **Pinned review:** preserves the full assessment window, exact next action,
  measured values and limitations while the live view can refresh behind it.
  Its local handoff text cannot confer host, provider or connection authority.
- **Pause updates:** stops automatic view polling, not the collector. A late
  in-flight response cannot overwrite the pinned view. Manual refresh reads once;
  resume restores polling without restarting anything.
- **Local search:** Cmd/Ctrl+K finds configured nodes, views and available local
  actions. No terminal or model runs inside the menu. Offline snapshots omit
  live-only operations.
- **Mobile navigation:** a disclosure menu replaces a squeezed desktop rail.
  Route events bind to navigation links, not every ancestor sharing a data attribute.
  Keyboard modal sequences stay inside visible controls and restore useful focus.
- **Private exports:** derived snapshot, chart PNG/CSV and minimal support report
  remain distinct. Chart PNGs carry the displayed UTC window and synthetic/private
  label. Opening or copying a review does not run the task.

Provider disclosures stay open across refresh/filter changes. Existing selected
node/range, evidence limitations, exact sample inspector, missing-data breaks,
export privacy and the two linked uPlot panes are preserved. The skill's walkthrough
now teaches the agent the real interface and its limits, rather than giving the
human a shell tutorial.

## Corrections caught by executable review

A broad `[data-view]` event selector also bound to the body. Clicks bubbled into it,
closing the mobile menu and sometimes selecting the wrong route. The regression
was reproduced and the listener was scoped to actual navigation anchors. The
selected navigation item is now checked through real mobile clicks.

A native dialog's edge tab sequence reached the document/browser boundary in the
tested Chromium build. Explicit modal-edge handling now wraps only visible controls;
the test exercises initial heading focus, reverse/forward edges, Escape and
focus restoration. This follows the [WAI modal interaction pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)
and [combobox pattern](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/). It is not
certification on every screen reader or physical phone.

Full release verification also exposed a transient private status-read failure.
A controlled atomic-replacement reproduction showed an unlinked inode being
rejected during metadata inspection. Reads now validate and read the same opened
private descriptor, with three bounded retries for concurrent replacement. Actual
hardlinks, exposed modes, over-size data and invalid JSON remain refused. Relevant
platform semantics: [Python descriptors](https://docs.python.org/3.12/library/os.html),
[Linux rename](https://man7.org/linux/man-pages/man2/rename.2.html) and
[stat](https://man7.org/linux/man-pages/man2/stat.2.html). This remains an owned-user
reliability boundary, not protection from a malicious privileged process.

## Research and acceptance boundaries

Selected sections of installed JSM `ux-audit` and `ui-polish`, plus pstack's
actual-artifact verification, subtraction, domain modeling and structural lessons,
were applied. The polish guide explicitly excludes fundamentally wrong layouts;
we therefore replaced the layout and stylesheet rather than piling on another
skin. Licensed skill text is not copied or shipped. Source hashes for the studied
entry points are recorded in the implementation receipt.

Functional checks are distinct from visual inspection. Acceptance covers actual
loopback server behavior, detached-worker identity, offline HTML, 320–1440-pixel
layouts, touch simulation, zero/three/100-node states, malformed/disconnected data,
private downloads, pinned reviews and clipboard-denied fallback. Screenshots use
synthetic observations only. Physical devices, independent design awards, native
client qualification and completed multi-day pilots are not inferred from these
checks. The running private qualification installation was not upgraded or reset.
