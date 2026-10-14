# VPS Health 0.7.3 — private-state and interruption recovery

Owning Bead: `gs-2uh.12`. This is a VPS Health implementation/acceptance pass, not
a new collection architecture or extension of the quarter plan. The code reuses
existing configuration, SQLite, worker and installer ownership.

## Concrete outcomes

First setup no longer publishes a half-initialized destination. It prepares the
configuration, history and dashboard in a private sibling stage, retains failed
attempts, and publishes only the complete directory. The same approved unused
target can be retried by the agent without deleting the failed attempt. Existing
user directories are never adopted. Four retained stages require explicit review
rather than unbounded retries or silent cleanup.

Private configuration/state reject exposed POSIX permissions, symlinks, hardlinks,
pipes and unexpected file types. Workspace containment is checked on the resolved
path, including parent aliases and traversal. General JSON/proc readers use bounded
regular-file reads without blocking on a FIFO, while genuine zero-size procfs
counter files continue to work. Standalone captures are created privately even
under a permissive umask.

SQLite sidecars are checked without deleting or manually replaying them. An actual
interrupted transaction test verifies that SQLite restores the prior observation
rows using its original rollback journal. A rejected linked journal leaves both
the link and external target untouched.

An owned run can be stopped without parsing a broken workspace configuration.
The exact run identity and actual kernel process identity still govern shutdown;
no arbitrary PID is signalled. A failed handoff refresh cannot prevent releasing
the owned lock. Workers started with this version bind installed Python files and
stop for review after code changes, before another collection cycle. Captures and
CPU decisions are not reclassified by that event.

## Failure-first evidence

The initial new suite ran 22 cases against the preceding source and reported 15
failures and five errors; subtest failures share causes and are not advertised as
20 independent production incidents. It exposed interrupted destinations, alias
containment, permissive output modes, linked/special state, blocked FIFO readers,
config-dependent stop and missing live-source checks. The implemented first set
passed all 22. Six additional cases cover the retained-stage bound, actual hot
journal recovery, complete publication failure handling, genuine procfs input,
existing empty directories and whole-agent retry after an interrupted renderer.

The 28 cases include real subprocess termination during initialization, a new
attempt preserving the previous stage byte-for-byte, concurrent initializers,
actual database rollback, actual worker source replacement in a disposable copy,
verified stop with corrupted config and live viewer verification after retry.
Only test-owned processes and synthetic/private fixtures are involved.

The full source suite passed 353 Python tests after these 28 additions to the
previous 325. Hosted Python 3.10/3.12 checks remain a separate exact-commit release
gate. The existing 12 chart
contracts and 29 actual-loopback browser groups are retained. A suite started
while source files were still being edited correctly refused mismatched child
launches; it is not reused as release proof. Stable-source checks supersede it.

The committed package owner also runs the actual exported crash/retry checks
from the extracted ZIP, in addition to its existing bootstrap, report, doctor,
agent start/verify and stop sequence. These do not turn artifact tests into native
Codex/Claude sessions or a multi-day field trial.

## Reviewed threat boundary

| Boundary | Required behavior | Tested evidence |
|---|---|---|
| First initialization fails or is killed | Requested target remains unused; failed files stay private and inspectable | Real killed child, renderer failure, bounded retained stages, approved retry |
| Target appears concurrently | Preserve the existing destination; one initializer publishes | Concurrent calls and a deliberate pre-publication target |
| A path aliases into the installed skill | Refuse before creating observations there | Symlink-parent and traversal counterexamples |
| JSON/state is a pipe, link, exposed file or device | Refuse quickly without repair or target mutation | FIFO subprocess timeout bounds, modes, hardlinks and sidecars |
| SQLite transaction is interrupted | Retain original database/journal; let SQLite roll back | Forced exit during an uncommitted delete, identical retained rows/hash |
| Runtime config is broken | Stop the verified owned run, preserve the bad config | Real worker and exact-identity stop |
| Installed Python changes while running | Stop for review without another collection cycle | Modified disposable installed copy and preserved captures |
| Viewer/HTTP and evidence | Keep existing fixed read routes, private capture exclusions and quality gates | Existing real browser/HTTP/counter suites |

## Limits that remain explicit

This is not a security boundary against root, a malicious process with the same
user identity, an attacker who can replace the interpreter or verifier, filesystem
corruption, unqualified network filesystems or exotic ACL behavior. Directory
publication is synchronized for cooperating initializers; not every platform's
crash/power-loss guarantees have been qualified. No root/service permission is
changed. The safety rules intentionally refuse suspicious existing files rather
than secretly fixing their permissions or adopting an unknown workspace.

Existing pre-0.7.3 workers must still be stopped before upgrading; they cannot
retroactively gain source-change detection. An in-flight bounded API read may
finish before a stop/source event is observed. Corrupted evidence is not rebuilt
from a status badge or removed to satisfy a test.

The prior real installer install/upgrade/restore/removal proof remains independent
collection evidence. This pass also exercised the new selected archive against a disposable retained
v0.7.2 workspace: install, upgrade, live worker/HTTP verification, stop, exact old
source restore and retained removal all passed. All three synthetic subjects and
2,288 observation points kept the same capture hashes. It does not modify
personal client installations, production hosts, provider messages or credentials.
Codex reauthentication, native discovery and sustained pilots stay separate tasks.

## Applied methods and references

Selected installed JSM doctor guidance (entry and ownership/reversibility concepts)
and pstack verification, domain modeling, subtraction and structural lessons
informed these changes. No full third-party rubric or independent-agent security
review is claimed, and paid skill bodies are not copied into the repository.
Agent Mail discovery was blocked in this session; no identity or reservation is
claimed from it and no permission workaround was attempted. The existing Git
hook remained in its configured advisory mode; GitHub/Beads carry the work receipt.

Technical references: Python's [resolved-path semantics](https://docs.python.org/3.12/library/pathlib.html#pathlib.Path.resolve),
[descriptor and rename operations](https://docs.python.org/3.12/library/os.html),
and SQLite's [atomic commit / rollback journal behavior](https://www.sqlite.org/atomiccommit.html).
These explain the implementation choices, not blanket guarantees about an arbitrary
host, filesystem or provider. Actual behavior is checked with the fixtures above.


The [machine receipt](recovery-verification-v0.7.3.json) records the verified source,
artifact and counts. The native source acceptance task `gs-2uh.12` is closed;
client, install-discovery and sustained-pilot gates are not closed by this pass.
