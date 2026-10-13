# Provider-specific context

Start with the actual product/plan and current primary documentation. Do not carry one supplier's terminology or another product's performance guidance into a contract claim. No percentage below is a universal CPU-delivery promise. These links were reviewed on 2026-10-13; versions, products and policies can change.

| Provider | Inspect before drawing a conclusion | Primary documentation |
|---|---|---|
| Contabo | Shared VPS versus dedicated-resource/VDS product, current plan, region, migration history. VDS benchmark advice is not a shared-VPS floor. | [VDS benchmark guidance](https://contabo.com/blog/benchmark-vds-cpu-performance/), [support](https://help.contabo.com/) |
| Hetzner | Shared CX/CPX/CAX versus dedicated CCX, CPU thread semantics, generation and baseline/burst behavior. | [Cloud server FAQ](https://docs.hetzner.com/cloud/servers/faq/), [server overview](https://docs.hetzner.com/cloud/servers/overview/) |
| DigitalOcean | Shared versus dedicated CPU Droplet class; premium hardware is not identical to dedicated allocation. Match plan and generation. | [Choosing a CPU Droplet plan](https://docs.digitalocean.com/products/droplets/concepts/choosing-a-plan/) |
| Akamai/Linode | Shared versus dedicated plan and applicable sustained-usage policy. Allowed utilization is not the same as observed delivered time. | [Shared and dedicated CPUs](https://techdocs.akamai.com/cloud-computing/docs/choosing-between-shared-and-dedicated-cpus) |
| AWS EC2 | Burstable versus non-burstable, credit balance, standard/unlimited mode, baseline and potential surplus-credit costs. A depleted credit balance is not evidence of a noisy neighbor. | [Credits and baseline concepts](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/burstable-credits-baseline-concepts.html) |
| Other providers | CPU allocation model, fair-use/burst policy, plan identity, relevant limits, migration and restart semantics. Leave unknowns explicit. | Use that provider's primary product/support documentation. |

## Assembly contract

The coding agent adapts the user's existing tools, not this provider list into automatic actions. A provider adapter should supply current expected asset identities, plan evidence, read-only monitoring selectors, known host epochs and the authority for any future controlled experiment. Keep credentials out of profile files. Use provider APIs only when the user authorizes the specific account/scope and a compatible tool is available.

Provider-support replies remain private evidence. Summarize their claim, time and scope. Do not assume an offered move occurred; do not infer permission to restart from a recommendation. If the user expressly requests a message later, one affected scope, one time window, verified observations and one question are usually more useful than pages of guessed CPU entitlement.
