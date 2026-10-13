# Provider context without invented guarantees

The Providers view and `providers` command read the same packaged
[typed catalog](../assets/provider-catalog.json). It contains original summaries
and links to primary product documentation, reviewed on 2026-10-13 UTC. References
ask for rechecking after 90 days; they never update themselves or fetch websites
from the viewer. Review the live linked page before making a consequential claim.

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
| Other or unknown | Exact supplier, plan and dated primary source first | That another provider's rule can be borrowed |

The catalog classifies claims as allocation, usage allowance, credit model or
billing behavior. None sets a `guaranteed_ratio`. The skill's 90%/80% bands remain
the user's investigation preferences, not a contractual interpretation. Uptime
commitments, performance expectations and compute allocation are not equivalent.

## References and scope

- [Contabo VPS](https://docs.contabo.com/docs/servers-hosting/vps/) and [Max Performance VPS / VDS](https://docs.contabo.com/docs/servers-hosting/max-performance-vps/).
- [Hetzner Cloud server FAQ](https://docs.hetzner.com/cloud/servers/faq/).
- [DigitalOcean CPU plan guide](https://docs.digitalocean.com/products/droplets/concepts/choosing-a-plan/).
- [Akamai shared/dedicated comparison](https://techdocs.akamai.com/cloud-computing/docs/choosing-between-shared-and-dedicated-cpus).
- [EC2 credit/baseline concepts](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-credits-baseline-concepts.html) and [Unlimited mode](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-performance-instances-unlimited-mode-concepts.html).

These are product/support references, not a complete review of a customer's legal
agreement. Product names and terms can change. Contabo product summaries were
checked against indexed official documentation; direct page retrieval was not
reliable during this review. Do not describe the whole contract as inspected.

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
