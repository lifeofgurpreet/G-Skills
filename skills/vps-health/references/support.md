# Getting useful help without sharing private observations

The coding agent should reproduce the smallest failing operation and gather a
minimal support summary. Do not ask the user to upload their database, workspace,
full dashboard, host inventory, raw logs, model trace, credentials or provider mail
to a public issue. The ordinary Save summary export contains node context; it is
not the support report.

```bash
python3 scripts/vps_health.py support-report
python3 scripts/vps_health.py support-report --workspace /private/known-workspace
python3 scripts/vps_health.py support-report --workspace /private/known-workspace --out /private/support.json
```

These are operations for the agent. The workspace is optional, so a broken or
unstarted setup can still report installed software information. The command is
offline and does not collect a new sample. Existing workspace files are unchanged;
an explicitly requested output is private, outside the observation directory and
never overwrites an existing file. It sends nothing.

The live viewer's **Support report** button downloads the same small projection.
It makes only a same-origin loopback read. A failed download does not upload anything
or fall back to raw logs. Offline exported pages cannot request a new support report.

The report allows software version/source hashes, Python major/minor, coarse OS,
categorical readability/asset/runtime states and aggregate record counts. It
excludes workspace paths, subject names, provider/plan/account details, endpoint
values or hashes, credential-variable names/values, observation timestamps, run
identifiers, measurements, raw errors and environment variables by construction.
It is not a general-purpose redactor. Counts and software identifiers are still
information: the user must review them before choosing to share.

SUMMARY_AVAILABLE means the report was constructed, not that the VPS is healthy.
PARTIAL/UNAVAILABLE are valid support outcomes; a missing database must not be
reported as a healthy empty store. A runtime record never proves that the native
coding agent or a background model is still connected.

For a public bug report, include the skill/version, agent/version, operating route,
short expected/actual behavior and a synthetic reproduction when possible. Add the
reviewed minimal report only when useful. Use the collection's private-security
contact guidance for a sensitive issue; do not post an exploit with customer data.
No report or issue template authorizes a provider message, remote access or a
change to the host's permissions.


## A requested local draft

Use [support-draft](local-support-draft.md) to turn the actual issue and these minimal diagnostics into a private maintainer draft. The agent creates the small issue request, runs the command and inspects the output. No mailbox connection, raw attachment or provider complaint is created. User-supplied issue text still needs a privacy review.
