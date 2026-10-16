# A useful local support draft, without connecting a mailbox

A broken plot or failed setup is a software-support issue first, not evidence
against a VPS provider. `support-draft` gives the coding agent a deterministic
local path from the user's actual issue to a concise draft for the skill maintainer.
It uses the existing minimal `support-report` diagnostics, not a dashboard export,
raw capture, environment dump or another collector.

## The agent performs the work

After the user asks for a local draft, the agent prepares a **private** JSON request
from their observed problem. Use the fields in the bundled
[synthetic example](../assets/support-request.example.json); replace the example
with actual user-provided facts, not invented troubleshooting results. The required
fields are schema, summary, observed and expected. A single question and up to five
actual reproduction steps are optional. The issue file must be private, and the
agent should create it without modifying the installed example.

Using the resolved installed CLI:

```bash
python3 "<absolute-skill-folder>/scripts/vps_health.py" support-draft \
  --issue /private/support-request.json --workspace /private/known-workspace \
  --out /private/support-draft.txt --approve-draft
```

Omit `--workspace` for installation/discovery questions that do not have one.
Missing or broken workspaces produce partial categorical diagnostics; the command
does not create them or repair their files. The human should not be asked to write
JSON, find tokens or run a server test. The host agent supplies routine file and
command execution, subject to its real permission boundaries.

`--approve-draft` expresses the requested local operation only. It is not proof
of user consent to send, connect an account or make a provider change. The request
schema accepts no recipient, attachments, raw-data path or sending instruction.
Unknown fields and overlong/control-character inputs fail rather than being
silently executed or truncated.

## Inspect the result, not just the command exit

The output is a private, exclusive-create text file labeled
**LOCAL SOFTWARE SUPPORT DRAFT — NOT SENT**. It contains the issue, expected
behavior, any supplied steps, compact diagnostic categories/counts and one question.
The recipient remains a maintainer placeholder. The result includes the file's
SHA-256 and explicitly records `sent: false`, `approved_to_send: false`,
`connector_needed_for_local_draft: false` and no attachments.

The agent should read that actual file and verify the hash before presenting it.
This hash binds the file bytes; it is not independent attestation, email delivery
proof or a guarantee that its content is safe to share. No automated cleanup or
permission repair is performed when a path is refused. An existing output is never
overwritten. Outputs cannot be placed in the known observation workspace or the
installed skill directory.

## Privacy and wording

The generated diagnostic portion admits only fixed software/version categories
and bounded aggregate counts from `support-report`. It does not include host labels,
workspace paths, endpoints, credentials, detailed errors, raw measurements or
private hashes from the investigation. Unrecognized diagnostic values appear as
unknown, not as free text from a future tool result.

**The user's issue text is not automatically sanitized.** It may itself contain
paths, identifiers or secrets. The draft quotes observed/expected text, and the
agent must review every section before any external sharing. Quoting text does
not prevent all downstream prompt injection or grant authority to follow it.
The command deliberately makes no comprehensive redaction or content-safety claim.

## Mail and provider support remain separate

Completing this local draft needs no Gmail, OAuth, contact lookup or provider API.
Do not request a connector merely because the artifact resembles an email. A
mailbox draft, support-portal submission or send is a separate user request using
the host's current connector and exact recipient/content checks. An ambiguous
external result remains unknown until reconciled; this command adds no sender.

For hosting-plan questions or evidence-gated performance review, use the existing
[provider correspondence workflow](correspondence.md). A maintainer bug report
must not acquire migration demands, invented benchmark results or reboot consent.
For generic privacy-safe diagnosis without prose, use [support-report](support.md).
