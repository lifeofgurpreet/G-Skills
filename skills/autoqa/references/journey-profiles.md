# Select relevant journey boundaries

These are synthetic product archetypes, not requirements to add to every app.
Select the boundary changed by the diff or requested by the user. Preserve the
product's own acceptance criteria and expected data model.

## Metered tools and programme access

Trace invitation or sign-in, role/programme assignment, allowance, permitted
capability selection, request execution, saved output and usage reconciliation.

Separate eligibility from successful consumption. Exercise one eligible user
completing an authorized request and the relevant rejection: wrong programme,
revoked access, exhausted allowance or disallowed capability. A disabled-provider
notice can be correct and still leave the user journey incomplete.

When billing or async execution changed, inspect reservation/charge reconciliation,
duplicate submission, cancel, partial output, reconnect and reload. Use synthetic
providers or the approved sandbox for faults. Do not spend external credits just
to satisfy an invented matrix, and do not infer accounting correctness from text
appearing in the browser.

## Mobile content and galleries

Trace discovery, content detail, prominent media, navigation to the next item,
return/back and the user's final action. Test the narrow viewport actually
affected, plus a representative wider one where layout changes.

For a carousel, verify the first item is visible, navigation works with touch and
keyboard, position is announced accessibly, focus remains sensible, and ordinary
vertical scrolling still works. Check one-item, many-item, missing-image and
loading/error cases where relevant. Avoid making a carousel mandatory: choose
the component that makes the content usable.

For Next.js/React applications, inspect server/client boundaries, hydration,
route transitions, suspense/error states, form pending/error behavior and
stale cached data only when relevant to the changed journey. Read installed
versions and the repository's official-docs policy; do not assume an API from a
remembered version. Component snapshots do not establish browser integration.

## Multi-role service booking

Trace selection, booking, confirmation, assignment, fulfilment and cancellation
through the roles the actual product supports. Verify actors can access only
their own permitted records, including server enforcement on state-changing
calls. Use the product's role names rather than imposing this archetype.

Check double-submit/idempotency and stale availability when these boundaries
changed. Separate sandbox payment/notification evidence from real provider
delivery. Never send real messages, charge a card or cancel a real booking as an
unapproved test.

## Worker and data pipelines

Trace the documented submission surface, enqueue, worker execution, durable result
and the client's retrieval of that result. A queue ACK proves acceptance, not
completion. Derive expected transitions and cardinalities from this system.

Exercise a relevant retry or interruption without causing uncontrolled work.
Verify provenance, duplicate prevention, partial failure and authorized cleanup.
A test time budget expiring is not a product timeout unless the contract says so.

## Cross-cutting cases

- Use relevant positive and negative role paths when access changes.
- Pair a clean session with pre-change persisted state when a returning-user bug
  or cache/session migration is involved.
- Verify keyboard reachability and focus order for changed controls.
- Check empty/loading/error states alongside the happy path when they changed.
- Keep mobile emulation, real-device proof, local fixtures and live-provider proof
  distinct in the report.
- Measure a stated performance criterion when performance is in scope; do not
  turn an arbitrary slow sample into a universal performance claim.
