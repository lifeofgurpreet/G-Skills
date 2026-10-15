# Public skill readiness: discovery, useful agent behavior and honest evals

This pass follows the user's request to make VPS Health usable by other people's
coding agents, with Anthropic skill-creator methods and a clearer UI/CLI/support
workflow. It does not turn the G-Skills collection into a VPS-only application.

## A real discovery bug, not another hypothetical roadmap

The published v0.9.3 SKILL.md description included an unquoted colon followed by
a space. Its YAML header failed both an actual YAML parser and Anthropic's
`skill-creator/scripts/quick_validate.py`, even though runtime tests passed.
The reproduced error was `mapping values are not allowed here` in the description.
This establishes a malformed artifact, not that every client necessarily handled
it the same way or that earlier explicit-path tool runs did not occur.

Version 0.9.4 fixes the header with folded YAML and describes useful trigger contexts
and adjacent exclusions. A new collection-wide parser validates actual metadata,
unique keys, allowed fields and the owning manifest's name/version. Ten tests cover
the original failure, duplicates, unexpected types and name/version drift. The
actual exported VPS folder is parsed too. PyYAML is pinned as a development check;
no extra package is required by users running the installed skill. Reset Boost's
source and version remain untouched.

## What we learned from Anthropic and actually used

The official skill-creator source was read at commit
`dbd4588f9e1033efb41dad4bef2f7947c8993d44` from `anthropics/skills`.
Relevant source areas were SKILL.md, references/schemas.md, agents/grader.md,
agents/analyzer.md, quick_validate.py, aggregate_benchmark.py and the static
review generator. The published agent-evaluation article informed the distinction
between a task, a trial, a trace and an actual outcome.

| Source method | Application here | Boundary |
|---|---|---|
| Evaluate the old and revised skill on the same tasks | Actual published v0.9.3 archive versus candidate instructions in separate private trial folders | Same restricted Read/Write tool set, input files and bounded native attempts; not a new collector or real mailbox |
| Define verifiable outcomes in evals/evals.json | Three synthetic tasks with expected artifacts and five explicit checks each | No hidden output path or unstated numerical target |
| Grade actual artifacts and inspect traces | A tested grader checks files and native completion evidence, then still requires semantic review | Local traces are not independently signed execution proof |
| Test where a skill should and should not trigger | Twenty realistic queries, ten positive and ten adjacent negatives | Defined, not executed or optimized into an invented trigger score |
| Present results with the upstream reviewer | Official static HTML generated for six sanitized blocked-attempt status cards | Harness status is prominently not model output; no fake benchmark |
| Keep incomplete and environment failures visible | No-inference failures and incomplete inference have separate states and no completed score | A result subtype of success cannot override is_error=true |
| Generalize and retain regressions | Discovery parser and grader failure cases are executable tests | No copying of a paid corpus or claim of Anthropic certification |

The upstream static reviewer references remote fonts and a spreadsheet library.
It is therefore not treated as the VPS runtime's no-network viewer. Only sanitized
status cards were supplied. Their text review was also checked in an isolated
browser with external requests refused. Rich-format or private-trace use has not
been qualified. We did not run its server/port-cleanup path or create a second
custom evaluation dashboard.

## Actual native attempts and their limit

Six native Claude Code 2.1.300 invocations were attempted: three tasks in both old
and new conditions. The executor saw the skill and relevant synthetic inputs,
not the grader or the tests/evals directories. Its only allowed tools were Read
and Write in an isolated folder. No provider, email, shell, host measurement or
production tool was available for these trials.

All six stopped before inference because the existing OAuth session had expired
and could not be refreshed. There were zero model tokens, tool calls and output
artifacts. The client emitted a result with subtype success but is_error=true and
a synthetic error message; the grader explicitly rejects that as a behavior pass.
These are attempted native sessions, not completed agent tasks. No baseline delta,
quality score or trigger success rate can be calculated from them.

The initial private driver continued the queued pairs after the shared auth failure;
that was not useful. The documented protocol and grader now signal stop_dispatch
on blocked/incomplete runs so a future orchestrating agent stops and resolves the
single shared issue rather than spending more attempts. The account was not
switched, credentials were not copied, and sandbox/permission settings were not
relaxed. The existing client needs native reauthentication before new authorized
behavioral comparisons can complete. Earlier unrelated client receipts remain
historical evidence, not substitute results for these new tasks.

## UI, CLI and support improvements delivered as agent instructions

The new references/agent-actions.md maps human goals to the actual existing CLI,
view state and host-native capability needed. The main entry routes the agent
there before loading every reference. It keeps the same evidence authority for
UI and CLI, insists on per-channel coverage when interpreting quiet means, and
separates private exports from minimal software support diagnostics.

A blank chart or installation failure initially belongs to the skill maintainer,
not the VPS provider. A local support draft needs no Gmail connection or recipient
lookup. The agent should produce the useful artifact from the observed issue and
minimal diagnostics, with a visible not-sent label. Actual mailbox drafts and sends
use the host's current connector schema and permissions. An uncertain send means
UNKNOWN until the intended mailbox/thread is reconciled; it is not an invitation
to duplicate the message or attach raw environment data.

A direct inline-evidence UI write and a proposed local correspondence-packet module
write were blocked. Neither file was created or applied through another route.
Those runtime/UI additions are not claimed by this release. The improved action
map and eval cases use only existing commands; no fictional send-email or
support-draft CLI is advertised. `gs-2uh.15`, live connector/action qualification,
remote-viewer PR #22 and the field-pilot gates remain open where they were open.

## Verification receipts

The source and actual archive checks, upstream validator result, native attempt
hashes and absence of behavioral scores are recorded in
`agent-eval-proof-v0.9.4.json`. Deterministic grader tests validate the evaluator;
they are not live model runs. The official static reviewer check uses sanitized
harness messages, not invented output examples.

An initial development test invocation used a private venv executable without
activating its PATH. Reset Boost's existing executable-resolution test correctly
could not locate the basename python. Validation was rerun with that venv's bin
on the process-local PATH; no other-skill source or global environment was changed.
Exact-head hosted CI and an extracted-archive metadata check remain release gates.

Primary references:
- https://github.com/anthropics/skills/tree/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/skill-creator
- https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- https://code.claude.com/docs/en/headless

No public promotion, provider communication, private pilot upgrade, account change
or production modification is part of this pass. Scoped collection tasks and VPS
tasks retain independent ownership and actual acceptance states.
