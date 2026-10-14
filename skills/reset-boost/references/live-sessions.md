# Live sessions

A config change reaches only new launches. Running Codex sessions are switched
through the same `/model` picker a person would use, and only when that is
provably safe.

## Finding panes

- **tmux** (Linux): interactive Codex processes (a terminal on stdin, not
  `exec` or `app-server`) are found through `/proc`; the `TMUX` variable names
  the server socket, and a pane owns a process when the pane's PID is its
  ancestor. On macOS process environments are not readable, so tmux panes are
  not discovered; Herdr panes are.
- **Herdr**: `herdr agent list` per session socket (`~/.config/herdr` and
  `~/.config/herdr/sessions/*`), then `herdr agent read <pane> --source
  visible`. A stale socket of a stopped session is skipped, never started.
- **NTM** is launcher configuration over tmux; its templates are rewritten as
  config, and its panes are switched as tmux panes.

Only routing metadata is read from a process (`TMUX`, `CODEX_HOME`); the
environment is never dumped.

## Switching a pane

1. Read the visible screen. Only the footer (`GPT-… <effort>` in the last
   eight lines), the settings modal and the composer state are retained; the
   conversation is never stored or printed.
2. Already at target: `verified`.
3. Preview (`audit`, or `set` without `--apply --live`): `live_mismatch` or
   `live_unknown`.
4. The composer holds a draft or unknown text: `held_unrecognized_or_occupied_composer`.
   Codex's built-in placeholder suggestions count as empty.
5. The pane is working (`esc to interrupt`, or Herdr says `working`):
   `held_working`, unless `--interrupt-current-turn` allows one Ctrl-C.
6. Otherwise type `/model`, pick the model, pick the effort (opening "More
   reasoning" when needed), and wait for the footer to read back:
   `verified` or `live_readback_unknown`.
7. Escape is sent only to dismiss a recognized settings modal.

While any account is pinned (exclusions or ceiling back-downs), a pane whose
account cannot be identified is `held_profile_unknown`: a pinned account is
never boosted by guesswork.

## Reported, not switched

- Explicit launch flags: every `codex` process's `-m` / `-c model…` flags are
  compared with the target (`explicit-mismatch` takes effect at its next
  launch). On macOS, privacy controls can hide process arguments; that is
  reported as unknown, not as a match.
- Desktop apps: no supported model-control API, always `unverified`.
- `service_tier` (fast mode) is a launch setting. Running sessions keep theirs
  until relaunch; the footer does not show it.

## Adding a harness

Answer three questions with evidence before adding one: how to enumerate its
agents, how to read the current model without reading the conversation, and
whether its own UI or API can change the model without submitting work. Until
all three hold, report its sessions as unknown. Never inject a prompt, read a
transcript or restart a process to find out.
