# Correspondence: a question is not a verdict

No monitor, percentage, log, provider reply or historic approval authorizes a new
message. These commands only create a local text file after an explicit drafting
request. They have no sender. Review identifiers, claims and attachments before
a human decides whether to send. Existing files are never overwritten.

## Ask what the plan provides

Use a plan question when the allocation model or sustained-use policy is unclear.
This purpose makes no performance allegation and needs no fabricated measurements.
The exact plan must be supplied by the owner or already recorded in the workspace.

```bash
python3 scripts/vps_health.py draft-email --workspace /private/vps-health \
  --node my-vps --purpose plan-question --plan 'Exact purchased plan' \
  --approve-draft --out /private/plan-question.txt
```

The short template asks for allocation, sustained-use/burst limits and the primary
product documentation. It explicitly requests no reboot, migration or other change.
Do not substitute a CPU count, hostname or competitor's policy for the plan name.

## Request a performance review

The default performance-review purpose requires an INVESTIGATE accounting result,
current sufficiently covered history of at least 48 hours, and a concrete service
impact supplied by the user. These gates permit a review draft, not a proven fault
claim. Workload confounds and provider responsibility remain separate questions.

```bash
python3 scripts/vps_health.py draft-email --workspace /private/vps-health \
  --node my-vps --purpose performance-review \
  --impact 'our measured build completion time increased during the recorded interval' \
  --approve-draft --out /private/performance-review.txt
```

Replace the example impact with something actually observed and quantified in
the user's monitoring. The draft states the UTC window, accounting mean, observed
coverage, workload context and uncertainty. It asks one host-side question and
withholds reboot/migration authorization. It does not invent a contractual floor.

An 85–87% result alone is not a reason to complain. A shared plan's permitted
utilization is not a delivered-CPU minimum. A good accounting number also does
not prove that the application is healthy.

## Demonstrate safely

Synthetic or earlier incomplete examples need `--example` and are marked
**EXAMPLE ONLY — DO NOT SEND**. No real performance draft is generated from a demo
without that conspicuous label. Plan questions against a demo are examples too.

## Receiving replies

Keep correspondence in the owner's private workflow. Record the provider's claim,
time and target scope. An offer, scheduling acknowledgment, start notice and
completion notice are distinct events. Do not update a host epoch from an offer
or infer restart authority from a recommendation. A new action needs new explicit
authorization from the user.

## Communication checklist

One affected scope, one UTC range, verified observations and one concise question.
Separate observed facts from inference. Do not attach raw captures, instance
identifiers or endpoint information unless the user specifically approves that
material. A generated file is not a sent message; report that distinction clearly.
