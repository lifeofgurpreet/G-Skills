# Local software-support draft acceptance

Owning task: `gs-2uh.19`. This follows the already-completed export and inline
context work in v0.10.0; those changes were inspected, not reimplemented. The
current shared-checkout convention was followed on `main` with scoped commits.
The public Agent Mail discovery call was blocked; no remote reservation or
registration is claimed. A host-local advisory file recorded the touched paths.
No coordination, authentication or host permission setting was changed.

## What is implemented

`support-draft` takes a bounded private issue request, optional existing workspace
and explicit local-draft request. It reuses the existing minimal support-report
rather than copying a full workspace status or creating another collector. It
writes an exclusive-create private text file addressed to a maintainer placeholder,
labeled NOT SENT, and returns its exact SHA-256 plus local-only result flags.

The output works when no workspace exists, and still supplies categorical partial
diagnostics when configuration or retained state cannot be read. It does not ask
for a node, email address or mailbox. The operation accepts no send, recipient,
attachment or raw-data path fields. The user-facing issue remains supplied prose:
it is quoted, bounded and explicitly requires review, not advertised as fully
sanitized or safe for public posting.

This closes a specific gap between the existing minimal diagnostics and a useful
agent-created support artifact. The SKILL.md entry, action map, support guide and
bundled example describe the same real CLI operation. There is no new browser
sender, provider escalation rule, OAuth proxy or automatic repair. Actual mail
writes and uncertain-result reconciliation still require the host's current tools
and a separate request; their broader acceptance tasks remain open.

## Failure-first and source verification

The real CLI initially rejected `support-draft` as an unknown command. Eighteen
focused tests now pass, including actual no-site-packages invocation from an
unrelated directory, no-workspace and corrupted-workspace behavior, private output,
no overwrite, unsupported action fields, hidden controls, bounded issue text and
exclusion of private diagnostic values. Tests verify that supplied issue prose
is NOT claimed to be a complete redaction of secrets.

The complete collection suite passed 593 Python tests. The existing VPS interface
passed 45 JavaScript contracts and 51 actual-loopback browser scenario groups.
No UI asset changed. Tests involving synthetic processes and classifiers are not
native Codex/Claude task scores. The current read-only Claude preflight still
reports signed out, so no new native model evaluation was dispatched and no
account was switched.

## Actual archive, not just imports

The selected 67-file candidate ZIP was built from commit
`9ebedc4023a6a872389e80ee221dfeecfefb57bd`. Its extracted skill passed the existing
cold runtime/recovery/export path and the new support operation. The pinned
Anthropic skill-creator format validator also passed on that extracted folder;
it is format evidence, not behavioral certification.

A separate extracted-archive test used an unrelated working directory with Python
site-packages disabled. It created a local draft with no workspace, then with the
three-subject synthetic workspace, then after introducing a synthetic malformed
configuration. The existing workspace bytes remained unchanged by each draft.
The 180-word sample identifies demo diagnostics, includes the 2,288-point aggregate
and omits node labels, private paths and raw error text. A fresh process verified
the exact draft hash; no collector, mailbox or external action was started.

The adjacent machine receipt records these results and includes only the synthetic
example text. The issue input is not used to discover recipients or connectors,
and an output hash never becomes proof that a message was sent. The original
passive pilot, remote-viewer draft, provider-contact permissions and Reset Boost
were left unchanged. Exact-source hosted CI and final artifact comparison remain
required before a new prerelease is published.
