# VPS Health 0.9.2 — complete, dated provider context

Owning existing Bead: `gs-8cq.5`. This tranche delivers the additional supplier
playbooks requested in the two previously reviewed Gemini proposals, without
importing their unsupported fault, migration or downtime-consent claims.
G-Skills remains an independent-skill collection; Reset Boost is not changed.

## What is implemented

Vultr, OVHcloud and netcup now work through the offline provider command, private
asset profile validation, bootstrap, managed planning and Providers view. A single
Python provider registry drives command choices and profile validation, rather
than separately maintained lists that accept different names. The workbench has
eight named suppliers plus one explicit unknown/other route.

The addition preserves product scope. Vultr's shared High Frequency/High
Performance categories are separate from Optimized Dedicated CPU. OVHcloud VPS
and Public Cloud Discovery references are not interchangeable, and availability
is not a CPU-accounting floor. netcup Root Servers are virtualized even when their
CPU cores are dedicated. No universal benchmark baseline, price or CPU percentage
guarantee is invented, and no provider account is queried.

Every fact and support-diagnostic reference now carries its own review date and
computed freshness state. A new catalog date or current diagnostic source cannot
make an old allocation fact appear reviewed recently. The provider card shows
its oldest dated source, or a clear recheck/unknown state. Missing, malformed,
future and stale dates require rechecking. Filtering another current provider does
not inherit a stale provider's warning.

Existing Contabo support diagnostics were already present in the backend but were
not rendered by the workbench. They now appear with their date and explicit
active-probe approval boundary. Backend and frontend both reject a reference link
that does not belong to that provider's reviewed source domains. No automatic
probe, external fetch, email, connector grant or migration is introduced.

## Primary-source scope and research

The five additional source pages were retrieved and reviewed on 2026-10-15:

| Supplier | Source | Supported distinction |
|---|---|---|
| Vultr | [Cloud Compute provisioning](https://docs.vultr.com/products/compute/instances/cloud-compute/provisioning) | Shared CPU selection and Cloud Compute / High Frequency / High Performance categories |
| Vultr | [Optimized provisioning](https://docs.vultr.com/products/compute/instances/optimized-cloud-compute/provisioning) | Dedicated CPU selection and workload-oriented categories |
| OVHcloud | [VPS product](https://www.ovhcloud.com/en/vps/) | Isolated VPS environment and an availability SLA; not a numeric guest-accounting commitment |
| OVHcloud | [Public Cloud virtual instances](https://www.ovhcloud.com/en/public-cloud/virtual-instances/) | Discovery is specifically described as shared resources; not every OVH product |
| netcup | [Server overview](https://www.netcup.com/en/helpcenter/documentation/server) | VPS shares physical hardware; virtualized Root Servers provide dedicated CPU cores |

Earlier facts retain their original 2026-10-13 review date, and the existing
Contabo diagnostic retains 2026-10-15. This pass does not claim to have re-reviewed
every old source, region, SLA or customer contract. The selected web sources inform
the catalog; the user's actual purchase still has to be established through their
approved records. These source facts are not conclusions about this user's fleet.

## Acceptance

Seventeen focused Python tests exercise source age, provider identity/URL scope,
unknown suppliers, non-mutating output, offline access and actual CLI parsing.
The previous implementation failed missing-provider and per-source-age contracts.
The browser tests exercise the actual viewer: all new filters, the shared/dedicated
and virtualized distinctions, source dates, existing diagnostics, stale-source
warnings, retained disclosure state and refusal of mismatched diagnostic payloads.
They do not claim a provider API or native-client field test.

The existing in-flight pause test had a timing ambiguity: automatic polling could
be intercepted before its intended clicked request. The fixture now establishes
one request using the actual Pause/Resume controls before asserting that pausing
prevents a late response from replacing the pinned view. Application timers and
asserted behavior are unchanged; a failed old fixture is not presented as passed.

The actual selected ZIP must pass its own cold check: all three provider commands,
provider-labelled unmeasured bootstrap, retained HOLD states, demo rendering,
private support output and existing runtime/stop/recovery tests. Exact-head hosted
CI remains the merge and publication gate. Counts and artifact receipts are recorded
after completion, not inferred from the number of files or a successful build.

## Separately discovered, not fixed in this tranche

`gs-2uh.15` retains a failure-first test: one quiet five-minute pressure/CFS interval
among three days of accounting can produce a reassuring context label despite
inadequate context coverage. Three of four focused integration cases failed before
the proposed correction. The implementation write was blocked and was not retried
through another route. Its test-only branch is retained, the task remains blocked,
and the limitation is visible in the preview/installed instructions. Provider
reference freshness and workload-metric coverage are different problems; this
release fixes only the former.

Remote-viewer draft PR #22 also remains separate and unmerged. Its unpublished
0.9.1 version is not included by this 0.9.2 patch. The running v0.8.0 passive pilot
is left on its original code and time budget. No provider contact, host setting,
personal installation, active probe or social announcement was performed.


### Frozen-source result

The complete collection run passed **489 Python tests**, including the 17 new
provider contracts. The selected VPS browser run passed **43 scenario groups**
and its **27 JavaScript contracts**. The actual rendered reference cards were
inspected independently of those assertions. The selected immutable archive and
exact-head hosted CI remain the publication gates; no external supplier account
or live VPS was exercised by these synthetic tests.
