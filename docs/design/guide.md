# Operator UI

The shared look and UX rules for operator pages that a G-Skills skill serves
locally: control panels, live consoles and dashboards. One stylesheet
([operator-ui.css](operator-ui.css)) and this guide keep those pages looking
and behaving like one product. The reference page is the Reset Boost control
panel (`skills/reset-boost/assets/console.html`).

Using the kit is a choice a skill makes. A skill with its own established
visual design (VPS Health) keeps it; nothing here is imposed on it.

## Use it

1. Copy `docs/design/operator-ui.css` into the skill (for example
   `assets/operator-ui.css`) and link it from the page. Skills stay
   self-contained, so the copy ships with the skill. `tools/validate.py`
   fails when a skill's copy differs from this file.
2. Build from its classes: `ui-shell` / `ui-rail` / `ui-nav` / `ui-main`,
   `eyebrow`, `display`, `lede`, `card`, `pill`, `round-action`, `tabs`,
   `table`, `status` + `dot`, `bar`, `ring`, `segmented`, `switch`, `check`,
   `dock`, `menu`, `modal`, `toast`, `moon`.
3. Colours only through `--ui-*` tokens. A page's own `<style>` may add
   layout; it must not add colours, fonts or new component looks.
   `tools/validate.py` rejects raw hex, `rgb()` and `hsl()` colours in the
   `<style>` of any skill page that links the kit. Light and dark both come
   from the tokens.
4. Before shipping, screenshot the page at desktop width and at 390 px and
   look at both. No sideways scroll at 390 px.

## What the screen is for

- **Lead with the live truth.** The first thing on screen is what is
  happening now, read from the thing itself (a session's own status line, a
  host's own answer). Never lead with configuration, intentions or a draft.
  If a value is a plan rather than an observation, label it as a plan.
- **One headline that states the situation** in words: "All systems go.",
  "Cranked up.", "3 things need you." A status dot next to it carries the
  colour.
- **The thing the user manages is the main list.** For an agent fleet that is
  sessions, not accounts. Context (quota, accounts, hosts) goes in a side
  column or another view.
- **A human must be able to confirm a change with their own eyes.** Rows
  update from live readings and briefly highlight when something actually
  changed.

## Actions

- **One primary action per screen**, labelled with its effect and count:
  "Crank up 17", "Bring everything back down (23)". Never "Apply".
- **A draft never looks like the current state.** Controls that choose a
  future action sit inside the action's own card, next to the button that
  commits them.
- **Every confirm says exactly what will change, what will be skipped and
  why** (out of quota, locked, unreadable), and how it ends.
- **Costly or destructive choices are explicit**: interrupting work,
  spending paid credits. The safe direction (turning down) is never blocked.
- **Bulk actions** appear only when something is selected, in a dock at the
  bottom.

## Words

- Plain language, never parameter names: "Come back down when the reset
  lands", not "quorum 0.5". Numbers carry units ("6h", "42% left").
- Short labels in tables; full values on hover or in a details view.

## Layout

- Sidebar navigation (Live first, Settings last). The main view answers
  "what is happening and what can I do"; everything else is one click away.
- Tuning knobs (thresholds, intervals, agent behaviour) live in Settings,
  never on the main screen.
- Generous space. Cards hold one idea each. Tables are quiet: no zebra
  stripes, no borders except row separators.

## Look

- Tokens only (`--ui-*`). One accent (lavender) for primary actions and
  selection; status colours only for status (green ok, amber waiting, red
  needs you). Model families have their own quiet colours.
- Type: thin display headline, 11 px letter-spaced eyebrow labels, 14 px
  body. Numbers tabular.
- Motion: one pulsing dot at most; row highlight on real change; nothing
  that loops forever on many elements.

## Lessons from the first panel

The Reset Boost panel went through three designs in one day. The first two
were rejected as counterintuitive; the causes were UX decisions, not CSS,
which is why most of this guide is about what goes on the screen.

- Check page class names against the kit. A layout class `.live` once
  collided with the dot modifier `.live` and broke the page.
- Render only when data changed, and only the visible view; a panel that
  stays open for days must not grow memory.
