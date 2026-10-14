# Qualify the user's coding-agent journey

The collection promises agent-owned work, not a list of commands handed back to
the human. Source tests and process fixtures alone cannot establish that a fresh
Codex, Claude Code or other client actually follows the skill successfully.

## Two independent evidence layers

**Artifact checks** verify what exists: reviewed installed bytes, actual bounded
worker identity, matching loopback HTTP state, a handoff, retained observations
and a stop of the same run without lost data. The developer tool
`tools/skills/vps-health/client_journey.py` prepares a private fixture from a
selected release ZIP and its manifest, then checks these observable outcomes.
It does not launch a model, copy authentication, weaken permissions or certify
a client from its reported name.

**Native-client and semantic review** verifies how it got there: the real client,
version, invocation/permission mode, actual private tool trace, questions asked,
commands/config work handed to the user, handling of denied access, and correctness
of the final explanation. That review is still required under `gs-2uh.6`. A Python
fixture that drives the same CLI is not a native coding-agent trial.

## Use the evaluator

The maintainer/verification agent runs these steps. They are not end-user setup
instructions and are not part of the installed skill's runtime requirements.

```bash
python3 tools/skills/vps-health/client_journey.py prepare \
  --archive /private/release/vps-health-v0.7.1.zip \
  --manifest /private/release/manifest.json --out /private/new-client-trial
```

Preparation performs no monitoring, model call or credential discovery. It writes
a sealed-source inventory and natural-language PROMPT.md/RESUME.md in the private
trial. Give PROMPT.md to the actual authorized terminal agent from that directory.
Keep the normal client sandbox, permission policy and approved account routing.
If the required tool or boundary is unavailable, record BLOCKED. Do not change
security settings or silently substitute another client/account to obtain a pass.

After the agent's claimed setup, run the check while its explicitly bounded demo
worker is still active:

```bash
python3 tools/skills/vps-health/client_journey.py check \
  --trial /private/new-client-trial --phase running --out /private/running-proof.json
```

Give RESUME.md to a separate session, then check the stopped state against the
first proof:

```bash
python3 tools/skills/vps-health/client_journey.py check \
  --trial /private/new-client-trial --phase stopped \
  --baseline /private/running-proof.json --out /private/stopped-proof.json
```

The reader refuses non-loopback URLs and redirects; it checks live state rather
than an HTML screenshot alone. A new run cannot stand in for continuation of the
old one. Modified installed source, a missing worker, an unverified stop or lost
observations cannot be replaced by an agent's success message. Successful output
says ARTIFACT_VERIFIED and still has `native_client_verified: false` and
`semantic_review_required: true`.

Hashes are local integrity checks, not independent attestation against an actor
who controls the whole machine and the evaluator's inputs. Retain the reviewed
release manifest and native trace privately. Never publish raw client traces,
workspace paths, account details, captures or credentials as a test badge.

## Required scenarios before a supported preview

Run each basic happy path in both intended clients on an authorized environment:
clean synthetic setup, known-workspace reuse, separate-session continuation and
verified stop. Also test missing target scope, unavailable execution capability,
and sparse/missing observations. The agent must not guess that its host is the
VPS, claim a missing capability exists, fabricate metrics or ask the human to write
configuration for routine work it could perform itself.

Report necessary user consent questions separately from avoidable manual work.
Record counts and actual actions; do not invent a numerical UX rating. A native
client that cannot start the required listener under its sandbox has a real
qualification gap, not permission to bypass the sandbox.

Email is optional for basic monitoring. An unavailable-connector scenario is
useful, but basic client qualification no longer waits on actual Gmail OAuth.
Actual authentication and external writes are `gs-2uh.4` / `gs-2uh.5` and require
their own approved test route and receipts.

## Status of this implementation pass

The deterministic evaluator and its real local subprocess fixtures are tested.
Fresh native model-driven journeys have **not** been qualified in this pass.
Available version/help output and a preflight that did not complete are not a
substitute. The native-client gate remains open; no account, hook, sandbox or
permission workaround was used to turn that boundary into a success.

Primary reference points reviewed on 2026-10-14 are the official
[Codex non-interactive guide](https://developers.openai.com/codex/noninteractive/),
[Codex CLI reference](https://developers.openai.com/codex/cli/reference/),
[Claude Code programmatic guide](https://code.claude.com/docs/en/headless) and
[Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference).
Their existence describes client capabilities, not successful use in this estate.
Recheck the installed client's actual help and allowed environment before each trial.
