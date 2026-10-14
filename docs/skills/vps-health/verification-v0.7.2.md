# VPS Health 0.7.2 — execution findings fixed

The change follows actual native Claude Code runs, not another roadmap.

The first session attempted unnecessary whole-host discovery and then treated
that denied command as a general lack of execution access. The installer now
returns the exact installed SKILL.md entry; the private client trial prompt does
the same. The agent can use the supplied path without asking for broad scans.
Existing permission rules remain intact.

The next native session successfully planned, created and started the demo, but
its ad-hoc curl options did not match the approved tool scope. `agent-verify` now
provides the intended operation directly: a three-second socket-timeout read of
the owned literal-loopback status endpoint, capped at 8 MiB, with no proxy or
redirect. It matches the response to the live run, saved configuration and expected
subjects and rechecks process identity afterward. Stopped, changed or mismatched
runtimes stay NOT_READY. Offline status/doctor and measurement thresholds are
unchanged. This checks the viewer, not provider fault or application health.

Seven tests cover real HTTP readback, stopped and changed runtimes, payload identity,
non-loopback URLs, redirects and oversized responses. Two installer tests ensure
an installed entry is explicit and a removed entry is not advertised. The actual
selected ZIP's cold acceptance also invokes agent-verify before stopping its worker.

Two further native Claude Code 2.1.299 sessions on the candidate artifact performed
setup and separate-session continuation: plan, start, agent-verify, status, then
agent-verify, exact-run stop and stopped readback. Independent artifact checks
confirmed the same run and unchanged 2,288 seeded observations. This used the
existing protected account route, dontAsk permission mode and the scoped skill
CLI; no blanket permission bypass or account switch. Explicit-entry invocation
is tested, not every automatic client discovery mode.

Native summaries incorrectly conflated zero real collection cycles with no demo
evidence. The verifier now states the retained capture count and explicitly says
that seeded observations exist; no real host was measured. That wording correction
is covered by the real-worker test, not claimed as another completed model trial.

Codex 0.162.1 could not enter the trial: its existing sign-in returned revoked-token
and routing-authorization 401 errors. It was not moved to another account or weaker
policy. The remaining Codex/client gate stays open.

`docs/execution-2026-10-14.json` holds sanitized source/trace hashes and outcomes.
Full native logs, filesystem paths, account details and test workspaces stay private.
The released-archive install/update/restore/removal check is now complete as well;
its previous missing acceptance is closed under gs-nah.5. No provider contact,
public promotion or multi-day real-host pilot occurred in this session.
