# Provider context without invented guarantees

The Providers view and `providers` command read the same packaged
[typed catalog](../assets/provider-catalog.json). It contains original summaries
and links to primary product documentation. Each fact and support-diagnostic entry
has its own review date and computed state. Updating the catalog or adding a new
provider does not refresh older sources. Missing, malformed, future or more-than-
90-day-old dates require rechecking; the oldest applicable source is visible on
the provider card. These references never fetch websites or update themselves.
An unknown provider has no reviewed product reference. Before relying on a plan
claim, the executing agent checks its actual current primary source and the user's
purchased product rather than asking the human to research it from scratch.

```bash
python3 scripts/vps_health.py providers --provider hetzner
python3 scripts/vps_health.py providers --provider aws
```

A selected provider card is not proof that a node uses that provider or plan.
Record the exact purchased product, region and allocation model privately. The
workspace accepts an owner-provided provider and plan label; it does not infer
those from hostnames, CPU counts or a benchmark score.

| Provider | Distinction that matters | Do not conclude |
|---|---|---|
| Contabo | Shared VPS versus dedicated-resource VDS | That dedicated-product benchmark advice is a shared-VPS floor |
| Hetzner | Shared CX/CPX/CAX baseline/burst versus dedicated CCX | That a vCPU necessarily means an entire physical core |
| DigitalOcean | Shared/dedicated allocation versus hardware generation | That Premium hardware alone means reserved CPU access |
| Akamai / Linode | Sustained-usage allowance versus allocation/delivery | That the documented 80% shared usage allowance promises 80% delivered time |
| AWS EC2 | Instance family, Standard/Unlimited mode and CPU credits | That credit depletion proves a noisy neighbor |
| Vultr | Shared Cloud Compute/High Frequency/High Performance versus Dedicated CPU Optimized Cloud Compute | That a higher clock speed or newer hardware alone means dedicated allocation |
| OVHcloud | VPS versus exact Public Cloud flavor, including shared Discovery instances | That an availability SLA is a CPU-delivery floor or that one family's allocation applies to another |
| netcup | VPS shared resources versus virtualized Root Servers with dedicated cores | That Root Server means bare-metal ownership |
| Other or unknown | Exact supplier, plan and dated primary source first | That another provider's rule can be borrowed |

The catalog classifies claims as allocation, usage allowance, credit model or
billing behavior, product scope or support diagnostics. None sets a `guaranteed_ratio`. The skill's 90%/80% bands remain
the user's investigation preferences, not a contractual interpretation. Uptime
commitments, performance expectations and compute allocation are not equivalent.

## References and scope

- [Contabo VPS](https://docs.contabo.com/docs/servers-hosting/vps/) and [Max Performance VPS / VDS](https://docs.contabo.com/docs/servers-hosting/max-performance-vps/).
- [Hetzner Cloud server FAQ](https://docs.hetzner.com/cloud/servers/faq/).
- [DigitalOcean CPU plan guide](https://docs.digitalocean.com/products/droplets/concepts/choosing-a-plan/).
- [Akamai shared/dedicated comparison](https://techdocs.akamai.com/cloud-computing/docs/choosing-between-shared-and-dedicated-cpus).
- [EC2 credit/baseline concepts](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-credits-baseline-concepts.html) and [Unlimited mode](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances-unlimited-mode-concepts.html).

The additional sources checked on 2026-10-15 are [Vultr Cloud Compute provisioning](https://docs.vultr.com/products/compute/instances/cloud-compute/provisioning),
[Vultr Optimized provisioning](https://docs.vultr.com/products/compute/instances/optimized-cloud-compute/provisioning),
[OVHcloud VPS](https://www.ovhcloud.com/en/vps/), [OVHcloud Public Cloud instances](https://www.ovhcloud.com/en/public-cloud/virtual-instances/),
and [netcup's server overview](https://www.netcup.com/en/helpcenter/documentation/server).
The earlier sources retain their actual prior review dates; they were not all
newly reviewed by this addition. These are references to product descriptions,
not an automatic review of every regional or historical contract.

These are product/support references, not a complete review of a customer's legal
agreement. Product names and terms can change. Contabo product summaries were
checked against indexed official documentation; direct page retrieval was not
reliable during this review. Do not describe the whole contract as inspected.

## Provider diagnostics for a support ticket

Contabo's [diagnostics article](https://help.contabo.com/en/support/solutions/articles/103000271266-how-can-i-run-diagnostics-on-my-server-)
(reviewed 2026-10-15) says support may ask for an MTR toward the server's IP,
run about 10 minutes and exported, plus a traceroute, attached to the ticket. The
catalog carries this as a `diagnostics` entry, not a performance claim.

MTR and ping are active probes. The rule in SKILL.md holds: they need the user's
scoped approval and never run implicitly.

Reading the result:

- Probe a pairwise matrix of peers, including a control pair in the same location
  that does not involve the suspect VPS. If only pairs with that VPS are slow, it is
  one VPS; if the control pair is slow too, suspect the location or path.
- In an mtr report, a fast provider gateway with a slow last hop puts the delay
  between the gateway and the guest. Loss on a middle hop that does not carry
  through to the last hop is usually router rate-limiting, not path loss.

A ticket states measured numbers, UTC times, the control comparison, a clear ask
and no internal names, addresses of unrelated systems or tokens. Draft it for the
user's review; sending is a separate approval ([correspondence.md](correspondence.md)).

## Adapting to another environment

Use the owner's current expected assets, exact exporter labels, plan evidence and
known host epochs. Keep API access in already approved tools; this catalog is not
a cloud API integration. AWS credit metrics, application latency/errors, network
loss and storage latency may require instruments outside this package. Missing
context is unknown, not healthy. Another supplier can use `other` while its exact
policy is reviewed; the agent must not guess a brand-specific rule.

Support replies remain private. Summarize their actual scope and distinguish an
offer, acknowledgment, start and completion. A provider statement does not itself
authorize a new host action. See [correspondence.md](correspondence.md).
