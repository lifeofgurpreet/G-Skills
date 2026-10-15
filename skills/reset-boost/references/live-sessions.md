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

## Reading a session

Only the Codex status line (the `GPT-… <effort> [fast] · …` line in the last
eight lines of the screen), the settings modal and the composer state are
read; the conversation is never stored or printed. The status line yields the
session's telemetry: model, reasoning effort, fast mode, run state, the
account's `5h` and `weekly` quota left, credits spent by the thread (shown by
Codex only once credits are spent) and the folder. Which fields appear depends
on the user's Codex status-line settings (`run-state` and `thread-credits`
are separate items); a missing field is unknown, never "has quota". A narrow
pane truncates the effort ("me…"); an unambiguous prefix is accepted.

`observe` (and the panel's loop, about every minute) does only this read on
every session and records it in `<state>/sessions.json`. It changes nothing.

## Switching a session

1. Already at target (model, effort and, when the target sets it, fast
   mode): `verified`.
2. Turning up a session on credits or out of quota: `held_credits`, or
   `move_suggested` when rehome is configured (see the credit guard in
   [configuration.md](configuration.md)). It is never cranked in place.
   Turning down is never held for this.
3. Preview (`audit`, `observe`, or `set` without `--apply --live`):
   `live_mismatch` or `live_unknown`.
4. The composer holds a draft or unknown text: `held_unrecognized_or_occupied_composer`.
   An empty composer and Codex's built-in placeholders ("Ask Codex to do
   anything" and the older suggestions) count as empty.
5. The session is working (`esc to interrupt`, a working run state, or Herdr
   says `working`): `held_working`, unless `--interrupt-current-turn` (or a
   session/pane `--interrupt`) allows one Ctrl-C.
6. Otherwise type `/model`, pick the model, pick the effort (opening "More
   reasoning" when needed), wait for the status line to read back, then type
   `/fast` if fast mode differs and read that back too: `verified` or
   `live_readback_unknown`. When only fast mode differs, just `/fast` is sent.
7. Escape is sent only to dismiss a recognized settings modal.

A session's target is its own setting (`session`), else its account's
(channel, pin, exclusion, out of quota), else the fleet's. While any account
is pinned or solo, a session whose account cannot be identified is
`held_profile_unknown`: a pinned account is never boosted by guesswork.

## Moving a session to another account (rehome)

Only tmux panes on Linux hosts are moved automatically; Herdr panes, macOS and
Windows report `move_manual`.

1. The pane's Codex process gives the account (`CODEX_HOME`), the folder
   (`/proc/<pid>/cwd`) and the thread: the id after `resume` in its arguments,
   else the id in the **file name** of its open `rollout-*.jsonl` (file
   descriptors are listed by name; transcript contents are never opened).
   No id: `move_no_thread`. Already on the destination: `move_same_account`.
2. Working (`esc to interrupt`) or a draft in the composer: `move_held_working`
   / `move_held_draft` before anything is opened. `--interrupt` allows one
   Ctrl-C; a composer that is not empty afterwards still holds.
3. Verify first: a hidden window in the same tmux session runs the new launch
   in the same folder while the original keeps running. "This conversation is
   open in another app" or a Codex status line means the thread resumes on the
   new account; "thread/resume failed", "missing source rollout" or "No saved
   session" (broken history lineage) means it does not, and the session is
   left untouched (`move_not_resumable`, not retried for 6 hours). A folder
   trust prompt is accepted with Enter. The probe is stopped with Ctrl-C and
   its window closed.
4. The state is checked again, then `tmux respawn-pane -k` runs the launch in
   the same pane (the pane id is kept). Once its status line shows, a goal
   that was running before (`Pursuing goal`, `Goal paused`, `Goal hit usage
   limits`) is resumed with `/goal resume` if it now reads paused, typed with
   the paste-safe slash-command helper.
5. The new process's `CODEX_HOME` and thread are read back: `moved`, else
   `move_unverified`.

## Reported, not switched

- Explicit launch flags: every `codex` process's `-m` / `-c model…` flags are
  compared with the target (`explicit-mismatch` takes effect at its next
  launch). On macOS, privacy controls can hide process arguments; that is
  reported as unknown, not as a match.
- Desktop apps: no supported model-control API, always `unverified`.

## Process spawning

Every subprocess (local control commands, `ssh` to hosts, the usage command,
agent steps) starts with an absolute executable and `close_fds=False`, which
lets Python use `posix_spawn`. A `fork()` from the panel's threaded server was
observed to hang on macOS while holding the interpreter lock, freezing every
thread. On macOS the panel's LaunchAgent runs as `ProcessType` Standard: as a
Background job it was starved under heavy load before it finished starting.

## Adding a harness

Answer three questions with evidence before adding one: how to enumerate its
agents, how to read the current model without reading the conversation, and
whether its own UI or API can change the model without submitting work. Until
all three hold, report its sessions as unknown. Never inject a prompt, read a
transcript or restart a process to find out.
