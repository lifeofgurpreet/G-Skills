# 0.6.0 — Agent-owned execution and explicit unknowns

The product change is ownership, not the number of files. The human supplies the
goal, authorized target and consequential approvals. The coding agent executes
routine setup, verifies the actual process, retains a private handoff and reports
progress through the existing dashboard. The installed skill remains a folder of
original scripts, references and assets, not a second hosted monitoring system.

## Implemented boundary

`agent-plan` is read-only. New auto scope asks for the target instead of guessing
that the terminal host is the VPS. A plan binds configuration, code, destination,
port, duration and the preceding run generation. The returned hash is not proof
of human consent: the executing agent still must obtain or already possess actual
permission for those effects.

`agent-start` reuses a matching active run without duplicating collection or
renewing its deadline. On Linux it launches an owned detached worker with an
inherited lock, one loopback viewer and sequential existing collection calls.
The worker can outlive its launching terminal, not a reboot or a platform killing
its processes. No root service, restart supervisor or new agent/model loop is
installed. It performs no new collection cycle after the configured budget;
an already-running bounded API read may finish first.

`agent-status` compares the actual Linux boot/process-start identity, rather than
assuming that a recorded PID is still the same process. `agent-stop` writes a
cooperative request for the exact run; it does not signal arbitrary PIDs or delete
evidence. A stopped/completed run needs a new generation-bound plan. Configuration
changes stop for review rather than collecting from an unapproved target.

Private `HANDOFF.md` and machine state let a replacement coding agent continue.
The Agent view shows runtime state, deadline, counts, events and capability needs.
These worker events do not prove that an AI chat remains online or that sufficient
multi-day observations have accumulated. The viewer remains read-only.

`agent-request` and `agent-resolve` preserve host-native capability needs. A reported
available tool remains `HOST_REPORTED_AVAILABLE`, with `connected=false` and
`send_authorized=false`; the next agent must check the actual live tools. Read,
draft and send are separate. A declined request stays declined. This is a
workflow/handoff contract, not an OAuth implementation or an externally verified
permission grant. No sender or cloud-mutation client is shipped.

## Test-first failures and structural corrections

The v0.5 baseline had no managed-runtime module or agent-owned command surface.
The first contracts established that missing capability before implementation.
Follow-up regressions reproduced three concrete defects during development:

- A pending connector request disappeared from status when no worker had started.
  Requests are now read independently of worker state, not hidden by an early return.
- A stopped run's old approval hash could start another budget. The plan now binds
  the preceding run generation; a completed plan cannot silently renew itself.
- Simultaneous identical starts could mistake an absent first status write for a
  different active plan. The inherited ownership lock now admits one worker while
  the other start waits for and attaches to its matching launch record.

Actual collector locking also protects against overlap beyond the older SQLite
lease deadline. The existing collector, measurement policy and database remain
authoritative; no duplicate execution or reporting engine was introduced.

## Executable qualification

The new runtime suite has **35 tests**. They exercise actual processes, private
SQLite workspaces and loopback HTTP, including:

- a launching CLI exiting while its owned worker remains alive;
- a separate CLI reading the same run identity;
- repeated and concurrent starts, wrong plan hashes and expired generations;
- naturally completed short budgets and cooperative stop with retained history;
- an occupied requested port failing without a false running-viewer claim;
- a deliberately killed test-owned child, orphan detection and safe new-plan recovery;
- real local baseline collection and refusal of a competing manual collector;
- malformed/symlink state, foreign process IDs and secret-free private receipts;
- request/decline/result records without external calls or send permission.

The crash test sends a signal only to its newly spawned fixture after checking
its exact kernel identity. Product stop code never calls `kill`. All tests clean
up their own processes; no monitoring worker is intentionally left running.

Together with the existing suites this is **209 Python tests**. Twelve pure
JavaScript chart contracts remain unchanged. The actual-loopback browser suite
now has **28 scenario groups**, including a real managed synthetic worker, its
visible Agent state, a local synthetic capability report and a verified stop.
The OS desktop-notification boundary remains deliberately simulated; real Gmail,
OAuth, Codex/Claude sessions and physical devices are not inferred from it.

The release builder verifies the actual standalone ZIP, required runtime and
reference files, licenses and hashes. After extraction it exercises the existing
bootstrap/export/doctor/brief/provider commands, then actual Linux plan/start/status/
stop, and confirms that its worker is stopped before removing the private fixture.
A successful copied-folder test is not substituted for the release artifact.

## Native roadmap, not a prose wish list

The repository now uses native Beads epic `gs-2uh`, linked to GitHub issue #7.
`ROADMAP.md` is generated from `.beads/issues.jsonl`. Normal validation checks
unique IDs, acceptance criteria, dangling dependencies, cycles, closed prerequisites
and generated-document drift. The three delivered source/runtime/handoff tasks
are closed with native commands; the root remains in progress.

Remaining acceptance work is explicit: actual connector discovery/OAuth and
external-action result reconciliation; cold Codex and Claude Code user journeys;
remote estate and non-Linux persistence; multi-day field observation and usefulness;
and reviewed learning from those real trials. Their dependencies prevent closing
the programme merely because local Python and browser tests passed.

Beads is a maintainer workflow, not a required user installation or another task
graph inside every user's private monitoring workspace. Local user state stays
private and does not flow into this public development tracker.

## Research and limits

The selected installed guidance is recorded in `improvement-v0.6.0.json`. Applied
ideas include executable handoff, interchangeable continuation, one owner per
state and direct evidence checks. We did not import private skill bodies, prescribe
an unnecessary agent swarm, or claim every reference framework was executed.
Current primary Codex/Claude skill and MCP documentation grounds the distinction
between packaged instructions and actual live tool/authentication capability.

There was no supplied external model review text to incorporate in this pass.
No provider message, actual mailbox draft/send, new OAuth grant, private fleet
modification, production experiment or unapproved service installation occurred.
A plan, process or JSON receipt never establishes those actions by implication.
