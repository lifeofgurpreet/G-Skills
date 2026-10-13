# Guest context: investigate more, claim only what was observed

This is a passive Linux diagnostic extension inside VPS Health, not a new skill,
provider API or hypervisor-access tool. The normal local observation loop retains
its context with existing captures. No package installation, CPU benchmark,
allocation test, synchronous write, ping/MTR, gateway lookup or external request
is part of the passive collector.

## Agent-owned collection

Run on the already authorized Linux target. Do not assume the coding agent's
laptop is that target. For a one-off private capture or before/after record:

```bash
python3 scripts/vps_health.py forensic-snapshot --node owner-confirmed-node --out /private/before.json
python3 scripts/vps_health.py forensic-observe --node owner-confirmed-node --seconds 2 --out /private/observation.json
python3 scripts/vps_health.py forensic-compare --before /private/before.json --after /private/after.json --out /private/comparison.json
```

These commands are for the agent to execute, not homework for the human. Replace
example paths/labels with the approved scope. Outputs are exclusive-create and
private. Observing sleeps for a bounded interval between two captures; it cannot
establish a day of evidence. A snapshot can contain revealing guest environment
and interface/device names, so do not publish it by default.

The managed local collector adds the same optional context to each retained
interval. Older captures and Prometheus-only sources may not have these fields;
that remains missing context, not zeros. Raw sources are retained for offline
replay in the existing database. The CPU assessment is not changed by a separate
diagnostic card or a particular selected chart window.

## Correct quantities

**Storage:** each device is identified by kernel major:minor numbers, not by
stripping digits from a filename. NVMe, partitions, device mapper and overlay roots
must not be guessed into a physical disk. Mean read/write request time is the
respective accumulated time delta divided by completed operations. No completions
means latency is unmeasured. Busy-device time is a different quantity. Keep layers
separate; do not sum disk, partition and mapper counters into duplicate IOPS.
These counters are not P95/P99 and cannot identify local NVMe versus network storage.

**Pressure:** compute aligned ratios from the `total` counters, rather than mixing
an unrelated avg10 window with the sampled IOPS interval. Keep some/full distinct.
System-wide CPU full is undefined and displayed as unavailable. Missing files,
invalid totals and resets are explicit. Pressure measures stalls, not their cause.

**Memory:** retain guest available/swap gauges and changes in faults, guest swap
and supported balloon counters. A lifetime balloon count is not current activity.
Neither these values nor a page-touch timing directly measure host swapping,
KSM or nested-page-table behavior.

**Network:** parse softnet counters as hexadecimal; `time_squeeze` is a guest
network-processing budget observation, not a count of hypervisor preemptions.
Interface errors/drops are useful context but not proof of physical-host vhost
saturation. Missing/new interfaces are separate from counter resets. No default
traffic is sent to an external service to identify the provider.

**Identity and clocks:** record guest-configured CPU/model/features, clocksource,
selected mitigation states and DMI hints. These can be masked, virtualized or
preserved across migration. No silicon-lottery grade, universal CPU-model baseline,
fixed mitigation percentage or immediate migration trigger is derived from them.

## Migration comparison is not host attestation

`forensic-compare` returns CHANGED, NO_VISIBLE_CHANGE or INCOMPLETE for guest traits.
It always retains `physical_host_verified=false`. Identical guest traits do not
prove that a provider only rebooted the same host. Changed traits can reflect
virtual CPU configuration, a reboot, updates or migration, so they do not uniquely
identify a new physical machine either.

Record a provider's actual offer, acknowledgment, start and completion separately.
Combine verified completion evidence with comparable workload measurements and
changed-epoch boundaries. Do not call a provider dishonest because guest-visible
clock or MAC values are unchanged. No automatic epoch or provider-ticket mutation
is performed by this comparison.

## Active investigations remain separate

Short hashing, RAM-touch, fsync or network experiments can be useful with explicit
scope, a selected filesystem/destination, bounded operations/bytes/time, versioned
workloads and stop conditions. They are not passive and are not automatically safe
on a production host. Small quantile samples and throughput baselines need honest
uncertainty. A short OpenSSL speed result is not IPC; its default CPU-time divisor
is not elapsed delivery. These active probes are tracked follow-ups, not secretly
run under the name audit.

The maintainer review of both external proposals is in
`docs/skills/vps-health/GEMINI-REVIEW.md` in the collection repository. The installed
skill contains this self-contained method and its executable tests, not the full
external review or a paid author corpus.
