# Keep the investigation intact when setup or a session fails

The coding agent owns routine recovery. It should not ask the user to delete the
workspace or relax permissions just to make an error disappear. These safeguards
belong to VPS Health, not to every skill in the G-Skills collection.

## Interrupted first setup

Initialization now builds the configuration, SQLite history and first dashboard
inside a private sibling staging directory. The requested workspace is published
only when those files are ready. If rendering, storage or the setup process fails,
the unfinished stage remains private and the requested destination usually remains
unused. Repeating the same approved setup can create a complete workspace without
editing or deleting the retained stage. No monitor started merely because a stage
or configuration file exists.

A stage is named `.<workspace>.initializing-<random>` and contains a small origin
record. It is not added to the approved observation history of a later retry.
Retained stages are bounded to four for a target; reaching that limit requires
explicit inspection/archival rather than silent deletion. An existing destination,
even an empty user-created directory, is not adopted or overwritten. Concurrent
initializers cannot both publish the same workspace.

If directory synchronization fails after publication, the error identifies the
existing complete destination rather than inventing a retained stage. The agent
should inspect `doctor`, the database and runtime status before deciding what to
retry. This does not certify behavior under filesystem corruption or power loss.

## Private paths and files

Workspace containment is checked after resolving parent aliases and `..`, so an
innocent-looking external path cannot hide observations inside the installed skill.
Normal parent aliases outside the skill resolve to one canonical target; a final
workspace symlink remains refused. On POSIX systems, the owned workspace and state
must be private to the current user. Exposed modes are reported, not automatically
changed. Do not recursively chmod user folders or adopt a foreign installation.

Private state rejects symbolic links, hard links, pipes, devices and unexpected
file types. JSON/counter input reads are bounded and cannot wait on a FIFO writer.
Linux proc files remain supported even when their reported file size is zero.
Standalone JSON captures are created with private file permissions regardless
of the process umask, and existing outputs are never overwritten.

Keep SQLite's database and legitimate journal files together. A hot rollback
journal is recovery evidence, not junk. The skill neither deletes it nor manually
reconstructs its contents; SQLite owns transaction rollback. Suspicious linked or
non-private sidecar files are refused without modifying their targets. The tool
does not claim protection from a privileged or malicious process sharing the
same account, filesystem corruption, exotic ACL behavior or a hostile kernel.

## Stop even when the config is broken

Stopping requires the exact owned run identity, not a successfully parsed
workspace configuration. Read `agent-status`, then request `agent-stop` for that
run. The worker is still identified by its boot/process-start identity; no
arbitrary PID is signalled. A malformed configuration is preserved rather than
rewritten. If a handoff cannot be refreshed, that does not prevent releasing the
owned runtime lock or confirming the stopped process.

STOP_REQUESTED remains different from STOPPED. A bounded collection already in
progress can finish first. If metadata ownership or process identity is not
verifiable, the tool refuses rather than guessing which process to stop.

## Installed-code changes

Workers started with this version bind the installed Python script inventory as
well as their configuration. A later code change stops the worker for review
before another collection cycle instead of mixing code versions silently. Existing
observations are retained, and the next run needs its usual source-bound plan.
This is a guard against accidental replacement, not code-signing attestation.

Continue to stop consumers before upgrading. Earlier releases cannot retroactively
acquire this check, and an active bounded read may finish before a change is
noticed. Use the collection's reviewed installation/restore workflow; never patch
a live user's skill folder to satisfy a failing test.

## What this does not authorize

No provider messages, new connections, active benchmarks, new production targets,
permission changes, public listeners or filesystem cleanup are authorized by a
recovery error. Synthetic process/transaction crash tests verify the code paths;
they are not real-client, physical-device or multi-day field qualification.
