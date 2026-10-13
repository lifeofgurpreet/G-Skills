# Correspondence: useful drafts, no automatic sending

The monitoring loop does not contact providers. A percentage is not an instruction to send a message, and provider guidance is not a contractual guarantee unless the applicable terms actually say so. This package has no SMTP, Gmail or provider-ticket sender.

## Try a clearly labelled template

```bash
python3 skills/vps-health/scripts/vps_health.py draft-email \
  --workspace /tmp/vps-demo --node example-contended \
  --impact "slower synthetic build completion in the demo" \
  --approve-draft --example --out /tmp/vps-example-email.txt
```

This produces **EXAMPLE ONLY — SYNTHETIC OR INCOMPLETE; DO NOT SEND**. It helps the agent and owner inspect the communication shape without misrepresenting the demo as a real incident.

## A real private review draft

The user must explicitly request the draft. The command also requires their observed service impact, a known configured alias, at least 48 hours of sufficiently covered fresh observations, and the current `INVESTIGATE` decision. The default means below 80%, not 85–87%. These are drafting safeguards, not a proof that contacting the provider is appropriate.

```bash
python3 skills/vps-health/scripts/vps_health.py draft-email \
  --workspace "$HOME/vps-health" --node my-vps \
  --impact "higher measured request latency during the reviewed period" \
  --approve-draft --out "$HOME/vps-review-draft.txt"
```

The private output names the actual UTC range, accounted mean, coverage and whether contention is present or context is incomplete. It states that these are guest-accounting observations, not physical-host attribution or a contractual floor. It asks for host-side review and explicitly withholds reboot/migration consent. It leaves the provider VM reference as a human-reviewed placeholder.

A draft is never sent by these tools. Check that the symptoms in `--impact` were actually observed, not filled in by an agent. Review all identities, plan terms, other workload changes and evidence limitations. Missing, short, stale or contradictory data blocks the real template; an earlier example remains non-sendable.

## Compact message structure

A useful message has four parts: verified symptom; measured range with uncertainty; relevant workload/limit context; one requested provider investigation. Avoid a long node dump, unsupported “full CPU owed” statements or repeated requests driven only by80–90% readings. Attach only the reviewed evidence needed for the affected VM, not account-wide credentials or private logs.

Different situations can need different human communication. An active outage may warrant support without waiting 48 hours; this measurement template is not an incident-response gate and does not authorize or forbid the owner's independent decision.

## Replies and learning

Privately classify replies as request for evidence, offer, scheduling acknowledgment, start notice or completion notice. Only the latter can support a conservative completion upper bound; it does not establish the exact hypervisor transition time. Do not let quoted old approval authorize a new host action.

Reusable lessons should describe the failure pattern with synthetic examples—for example, “a scheduling acknowledgment must not end settling”—not copy a customer's message, name, ticket, VM identifier or support-agent details into the public repository. The learning proposal still needs review and regression tests before publication.
