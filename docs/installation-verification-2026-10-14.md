# Selected-skill lifecycle: verification and open gates

## Delivered source, not a universal installer claim

The collection has an offline agent-callable plan/apply/status helper for one
reviewed skill ZIP. It stages replacement files, retains prior installations
outside discovery and records interrupted operations before moving the current
folder. Removal retires files rather than deleting them. Restore uses an explicit
retained revision. The tool runs no package scripts, hooks, client processes,
network requests or authentication flow during installation.

The shared archive reader is reused by release checks and installation rather
than implementing a second extraction policy. It rejects unsafe path aliases,
case collisions, special/symlink members, file/directory collisions, oversized
archives and an archive trying to supply the manager's own receipt. Installer
plans bind the selected source and destination, current files and completed
recovery generation. A hash is not human consent or trusted publisher attestation.

## Failures reproduced during development

A dangling destination symlink was initially treated as an absent directory.
The failing test now requires explicit refusal before any overwrite. A second
regression showed that after removal, the original install approval could recreate
the skill. Completed recovery history now changes the next plan generation; a
stale approval cannot silently reverse a removal. An unchanged active installation
still supports idempotent repeated calls.

The archive-boundary fixtures contain complete valid bundles before introducing
one malformed element. This matters: a test must fail on the intended unsafe path
or collision, not merely because an unrelated required file was missing.

## Executable evidence

The new suite has 34 lifecycle/archive tests. It covers private read-only planning,
wrong approvals, unchanged retries, independent versions of unrelated skills,
user edits/additions/deletions, unknown ownership, source changes, symlinked paths,
separate discovery/recovery stores, bad metadata, concurrent manager locks and
retained old versions. Ordinary Python caches are allowed; arbitrary added notes
or customer data remain a refusal.

Interruption tests exercise each transaction boundary. One test starts a separate
process and exits that process after the old folder is retired. A new invocation
acquires the released lock and recovers the prior files. This tests actual process
interruption rather than only a simulated success return. No unrelated process is
terminated. The remaining tests verify recovery does not overwrite a manually
created replacement and that an unpublished installation can be abandoned safely.

Adding these 34 tests to the existing 282-test collection gives 316 Python checks.
The existing chart/browser verification is retained. Exact source CI is required
before merge; earlier green status is not borrowed for later edits. No new VPS
version is inferred from collection-tooling changes; the v0.7.1 skill files stay
unchanged.

## Published-archive smoke: precise status

Using the actual v0.7.0 and v0.7.1 ZIPs in a private disposable directory, the smoke
confirmed install, upgrade, current CLI version, synthetic demo startup and owned
worker stop. The observer then incorrectly asserted three capture rows for three
subjects; the database actually stores one bundled capture with all three expected
subjects. That assertion failure is a verification error, not evidence of data loss.

The remaining full released-archive restore/removal sequence was not accepted in
this pass. A subsequent execution attempt was blocked and was not retried through
another route. No success receipt was manufactured. Synthetic fixture coverage
for restore/removal passes, but it does not replace this remaining artifact gate.
Native Codex/Claude discovery was not exercised by these tests either.

## Remaining work and responsibility

`gs-nah.5` stays in progress for final artifact acceptance and source review.
`gs-nah.2` retains native-client installation/discovery and upgrade qualification;
the passive-preview gate still depends on it. Current fields and dates are in the
native Beads graph and generated roadmaps. No launch, invitation, public announcement
or provider message is scheduled by those dates.

This pass qualifies Linux filesystem behavior only. POSIX locks, same-filesystem
renames and stopped consumers are required; the manager cannot independently prove
that every consumer has stopped. It is not a security boundary against root or a
malicious process sharing the user identity. Plugin/symlink installations managed
by other tools are refused rather than adopted. Windows and actual macOS client
behavior remain unqualified.

## Methods applied

Selected installed JSM doctor guidance informed detect-before-mutate, retained
prior files, explicit inverse operations and testable interruption handling.
Pstack's subtraction and direct-output principles informed one archive reader and
actual filesystem/process checks. The private source edition hash for the studied
doctor entry was `c6cbc6cb351a028f02ecdbb08e4a238c6ddec0064aa27dc10f97124c4ab1f804`;
the applied scope was its entry/ownership/reversibility guidance, not its full
scoring framework. No paid skill text or private library paths are republished.

The operator-facing guide cites current official client discovery documentation.
Those pages establish documented locations, not actual success in a fresh agent
session. Preserving this distinction is part of readiness, not omitted work hidden
behind a test-count badge.
