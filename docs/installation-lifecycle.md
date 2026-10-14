# Agent-managed installation without overwriting the user

G-Skills is an independent-skill collection. The shared `tools/install_skill.py`
helps the executing agent install one reviewed local ZIP, update it, restore a
retained version or remove it from discovery while retaining its files. It starts
no runtime, executes no packaged script, installs no hooks and connects no account.
A client-specific plugin/import manager remains a separate ownership mechanism.

## The agent does the routine work

The agent first identifies the intended client, scope and authorized destination.
It obtains the selected release archive and manifest from a trusted source through
its existing tools, verifies the planned effects, stops consumers of an older
installation, applies the reviewed plan and checks actual client discovery.
Do not ask the human to construct JSON, copy a plan hash or edit configuration when
the agent has the appropriate tools. Ask for necessary scope/access decisions only.

The installer intentionally accepts an explicit skill directory rather than
choosing a global location. Current official documentation describes personal
and project directories under `.agents/skills` for Codex and `.claude/skills` for
Claude Code. That is a documented route, not proof that the current client has
loaded the files. Plugins, remote sessions, trust settings and other managers may
use different paths. Recheck the host's actual conventions and supported tools.

Sources reviewed 2026-10-14:
[Codex skill discovery](https://developers.openai.com/codex/skills/) and
[Claude Code skill locations](https://code.claude.com/docs/en/skills).
Both clients can support symlinked skills, but this manager deliberately refuses
to take ownership through symlinks. It must not replace another manager's link.
Use the owning manager or choose a separately approved plain-directory install.

## Read-only plan, then explicit mutation

The following commands are examples for the coding agent, using placeholder paths.
Keep the recovery store outside any discoverable skill directory and on the same
filesystem so directory moves are recoverable. The store is private and bounded;
old versions are not placed beside live skills where they could also be discovered.

```bash
python3 tools/install_skill.py plan --skill vps-health \
  --archive /private/release/vps-health-v0.7.1.zip \
  --manifest /private/release/manifest.json \
  --directory /private/chosen-client/skills --store /private/gskills-recovery
```

The plan binds the archive contents, selected skill/version, current installed
files, exact destination, tool source and recovery generation. It creates nothing.
The agent reviews that effect against the user's actual authorization, then uses
the returned plan hash in the same operation with `apply --approve-plan HASH`.
`--consumers-stopped` is required: the agent must actually stop affected workers
and avoid loading the skill mid-update. The flag is an assertion, not independently
verified process liveness or an authentication token. Installation does not prove
client discovery, which the agent must check separately afterward.

A matching completed install retry is unchanged rather than duplicated. Removal
changes the recovery generation, so its old install approval cannot recreate the
skill. A modified source, destination or prior state needs a new reviewed plan.
Manifest hashes detect changes; a manifest supplied by an untrusted party is not
publisher authenticity. Review the provenance and skill code before enabling it.

## Update, restore and remove

Use `--operation install` with the next reviewed release to update. The existing
folder must be owned by this manager and match its recorded contents. Modified,
missing or additional files block mutation; they are preserved rather than silently
overwritten. Ordinary Python cache files are ignored, but notes or other data—even
inside a cache directory—are not. Existing unmanaged installations are never adopted
implicitly. Reconcile them through a separately approved migration instead.

`status` lists the current installed version and retained revision identities.
Use `--operation restore --revision RETAINED_REVISION` to plan and restore a prior
snapshot. `--operation remove` moves the owned folder out of discovery into recovery
storage; it does not delete it. Private monitoring workspaces live elsewhere and
are not touched. A selected skill's removal cannot remove another skill.

There is no force-overwrite or automatic purge option. The bounded revision/staging
budget eventually requires the owner to archive old recovery material deliberately.
The installer does not decide that user evidence or old versions are disposable.

## Interrupted operations

A private transaction journal is written before the current folder moves. The
replacement is staged and checked first. During a two-directory swap there can
be a short interval with no discoverable folder; this is why consumers must be
stopped. Do not claim an uninterrupted atomic directory exchange on every OS.

A pending journal blocks normal updates. Use `--operation recover` to inspect a
read-only recovery plan, then apply it with its own approval. If the replacement
was already published and matches the journal, recovery confirms it. If the old
folder was retired but publication did not finish, recovery restores that prior
folder. An unpublished fresh install may be abandoned with its staging retained.
Changed or unowned replacement files are never overwritten to make recovery pass.

Locks serialize this manager's writes and release when its process exits. They do
not make the filesystem safe against a malicious same-user process modifying files
between checks. Old and staged files are retained rather than recursively deleted.
Local hashes and receipts are not independent attestation or a security boundary
against root. Corrupt or ambiguous recovery state is a stop-and-inspect condition.

## Supported evidence and remaining qualification

Source acceptance covers synthetic unrelated skills and real filesystem operations,
including a separate process exiting during an update and recovery of the prior
files. The published VPS archive smoke reached install, upgrade and verified
synthetic runtime stop; its full two-version rollback/removal path has not yet been
accepted. An early test confused one bundled capture row with three subject rows;
that was a verification assumption, not a demonstrated data-loss defect. A later
execution attempt was blocked and not rerouted or recorded as passed.

The manager currently requires POSIX locking and same-filesystem rename semantics.
This pass is Linux-qualified, not a Windows or physical macOS compatibility claim.
Native Codex/Claude discovery, interruption during an actual client's use and full
supported-install qualification remain open in `gs-nah.2`. The implementation task
`gs-nah.5` retains that artifact-completion gate. Neither unit tests nor a directory
appearing on disk close those outcomes automatically.
