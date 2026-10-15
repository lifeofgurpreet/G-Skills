# Review of both supplied Gemini VPS proposals

## Receipt correction and scope

Both supplied documents were present. Earlier assistant statements that no Gemini
output had been supplied were incorrect. This review reads both complete inputs,
including the proposed shell script and replacement SKILL.md. We retain useful
ideas, test the mechanisms and separate the proposals from verified findings.
Neither document had inspected the current repository: each says its browser
could not fetch it. Therefore claims that the proposal is drop-in or production
ready are not code-review evidence.

Source A is organized around six lettered forensic areas (under a heading saying
seven), migration verification, support-ticket generation and fleet scoring.
Source B adds six low-level ideas, a shell/Python probe and a replacement rubric.
The tables below follow those groupings. No supplied script was executed on a
production host, and the full input texts are not republished as skill instructions.

## A. Forensics, migration and fleet proposals

| Source proposal | Disposition | Implementation / remaining gate |
|---|---|---|
| Hidden CPU throttling: steal plus short hashing baseline | **Modify/defer active part.** Retain guest accounting and workload context; a SHA256 score is throughput, not IPC, and not a universal host-throttle detector. | Existing CPU measurements remain. Any active baseline must bind CPU features, OpenSSL version/provider, buffer size, wall-time divisor, workload and an approved budget. No unverified CPU-model score table is shipped. |
| I/O PSI correlated with local IOPS | **Adopt measurement; reject exclusive causality.** Resource stalls and low completions are useful context, not mathematical proof of another tenant. | Passive PSI totals, per-device disk counters, request means and same-window comparison are implemented. Device layers are not summed into a fake guest total. |
| Storage tail latency rather than bandwidth | **Adopt research direction; defer writes.** A small fsync trial can reveal observed latency but cannot identify NVMe/Ceph from its minimum or prove who queued it. | No active storage writes are enabled. A scoped test must identify the chosen mount/filesystem, bound bytes/operations/duration and report sample count/quantile uncertainty. |
| Clocksource fallback as immediate migration trigger | **Retain observable trait; reject automatic trigger.** The selected clock alone is not a host diagnosis. | Capture guest clocksource and compare it without changing system settings or labeling HPET/ACPI as proof of provider failure. |
| Silicon-lottery fingerprint and letter grade | **Retain guest-visible model/features/mitigation state; reject invented grading.** | CPU traits are recorded with `physical_cpu_verified=false` and no performance baseline. No S/F hardware score or universal mitigation penalty. |
| First-hop loss and interface drops prove host vhost saturation | **Adopt passive counters; defer traffic; reject cause claim.** | Interface errors/drops and hexadecimal softnet deltas are retained. No implicit ping, MTR or third-party IP lookup. Path tests need destination/rate approval and transport/control-plane caveats. |
| Before/after migration verification | **Adopt comparison; reject physical-host attestation.** | `forensic-snapshot` and `forensic-compare` show observed guest changes, missing fields and boot boundaries. Identical traits do not prove a fake migration; changed traits do not uniquely prove a new physical host. |
| Provider detection and ready-to-send ticket | **Modify.** DMI/vendor strings are hints, not a purchased-plan record; IP lookups disclose data. | Keep owner-provided plan/source documentation and explicit read/draft/send permissions. No automatically generated reboot/downtime authorization. |
| SSH fleet scorecard / golden-node preservation | **Adopt comparative evidence and explicit inventory; defer autonomous SSH expansion.** | Existing declared-fleet workflow remains. An SSH agent must verify authorized targets, bound concurrency and retain inaccessible/unknown rows. No scan-all-SSH-config or automatic migration verdict. |

## B. Deep-metal ideas and replacement rubric

| Source proposal | Disposition | Why / corresponding implementation |
|---|---|---|
| 64 MiB memory touch detects host swap/EPT/KSM | **Reject proof; defer active allocation.** | That timing includes guest allocation, zeroing, faults, runtime overhead and descheduling. Passive memory PSI, swap/fault/balloon counter deltas are added, explicitly not host-swap measurements. |
| fsync P95/min proves neighbor contention | **Reject proof; preserve as future experiment.** | Small-sample distribution, filesystem, caching, barriers, storage topology and workload need qualification. A minimum is not physical-medium identification. |
| SoftIRQ time_squeeze means vCPU preemption | **Correct semantics.** | Parse hexadecimal counters and retain `time_squeeze` as a guest networking-budget observation, not a preemption count. Kernel polling can exhaust packet/time budgets for several reasons. |
| Missing cache/features proves fake CPU topology and a fixed performance loss | **Retain visible features; reject fixed loss.** | QEMU explicitly supports named/masked CPU models for compatibility and migration. Guest model exposure is not physical-host identity or a universal percent penalty. |
| Vulnerability mitigation tax | **Retain configuration, not a score.** | Record selected readable mitigation files and missing states. Workload-specific measured comparisons are needed before quantifying a penalty. |
| Gateway MAC plus exact TSC frequency detects a fake move | **Reject attestation.** | Virtual clocks and CPU presentation can be preserved or adjusted across migration. The guest cannot uniquely identify a physical machine from these fields. No dishonesty allegation is generated. |
| Default audit automatically performs all probes and emits tickets | **Reject implicit side effects.** | Passive context is included in the existing local observation loop. Active CPU, RAM, disk and network tests remain separate approved tasks; support actions remain separate from monitoring. |
| Overall KEEP / MIGRATE NOW node grade | **Modify to evidence state and next check.** | Keep measured values, coverage, quality, source and uncertainty. Do not collapse mixed causes into an authoritative provider verdict. |

## Concrete defects in the proposed drop-in script

These observations come from the supplied code, not from running it:

- `grep -m1` with many alternative CPU fields returns one matching line, not the
  complete model/stepping/microcode record. The replacement parses each field.
- Removing trailing digits from the root device can corrupt a bare NVMe device
  name and cannot resolve overlay, mapper or layered storage. The replacement
  matches mount major:minor identity and keeps distinct devices separate.
- A fixed divisor of ten assumes the requested sleep equalled elapsed time.
  We retain monotonic acquisition bounds and check clock/read overhead.
- No completed I/O is reported as zero latency in the proposed script. It is
  unknown latency in the implementation; counter resets also invalidate rates.
- `/proc/net/softnet_stat` fields are hexadecimal. Plain numeric awk accumulation
  does not reliably decode them, and the source labels time_squeeze as preemptions.
- Busy-device milliseconds are not a per-request latency distribution. Request
  means use read/write time deltas divided by their completed operation counts.
  They are neither exact physical latency nor P95/P99.
- OpenSSL speed is an active workload. Its default divisor is CPU user time;
  `-elapsed` changes that to wall time. Buffer/algorithm loops and unbounded
  external commands do not support the claimed universal twelve-second budget.
- The Python section allocates/zeros memory and writes/syncs a temporary file.
  `/tmp` may be tmpfs, overlay or another storage class. These are not passive
  measurements merely because no packages were installed.
- Missing tools, restricted dmesg and unsupported proc/sys fields need explicit
  states. Bash, awk, OpenSSL and Python are dependencies, even when preinstalled.
- The suggested ticket pre-authorizes cold migration and downtime. That consent
  cannot be manufactured from a diagnostic reading or a model-provided template.

## What is shipped in this pass

A standard-library Python guest-context collector; correct per-device/PSI/network
counter interpretation; retained raw inputs; bounded private snapshot/observe/compare
commands; integration with the existing local capture/database; and a diagnostic
panel that never changes the CPU decision. Tests cover hex parsing, NVMe/mapper/
overlay identity, resets, missing fields, unknown idle latency, double-counting,
clock/boot boundaries and both changed and unchanged migration traits.

The contribution is not a copy of the proposed script with softer prose. It is
an executable implementation of the useful observation ideas with counterexamples
that prevent the unsupported conclusions. Active experiments, broader SSH fleet
collection and additional provider-specific playbooks are tracked as follow-ups.

## Primary technical checks

- [Linux pressure interface](https://docs.kernel.org/accounting/psi.html): stall semantics, cumulative microseconds and system-wide CPU full being undefined.
- [Linux disk statistics](https://docs.kernel.org/admin-guide/iostats.html): per-device fields, resets, request time and busy-time distinctions.
- [Linux networking budgets](https://docs.kernel.org/admin-guide/sysctl/net.html): NAPI packet/time limits.
- [Linux softnet output source](https://raw.githubusercontent.com/torvalds/linux/master/net/core/net-procfs.c): hexadecimal fields and time_squeeze position.
- [Linux interface statistics](https://docs.kernel.org/networking/statistics.html): dropped/error field meanings and proc aggregation.
- [QEMU CPU model configuration](https://www.qemu.org/docs/master/system/qemu-cpu-models.html): guest model masking and migration compatibility.
- [KVM virtual time](https://docs.kernel.org/virt/kvm/devices/vcpu.html): guest TSC offsets and migration adjustment.
- [OpenSSL speed](https://docs.openssl.org/3.6/man1/openssl-speed/): benchmark options, CPU-time versus wall-time divisor.

Reviewed 2026-10-14. These sources support the measurement semantics; they do not
establish a particular customer's contract, provider behavior or current incident.


## Input integrity

The reviewed inputs were the two complete user-supplied Gemini texts. Source A SHA-256: `30d0346293fc7f752b48b5459083f43591a9d6254864fdf8254d05de29f2578e`. Source B SHA-256: `c56f4018330a20d4a20998f19384290c43584e8ceb58c21f266d1591b456e330`. These bind what was reviewed; they are not independent validation of its claims.


## Provider expansion delivered after the initial review

The requested additional supplier scope now has original, dated reference entries
for Vultr, OVHcloud and netcup, with CLI/profile/workbench acceptance. Each source
has its own review state, so adding these entries does not falsely renew older
Contabo or other references. Existing Contabo diagnostics are also rendered rather
than silently omitted by the frontend. The input proposals' automatic provider
identification, universal CPU floors, guaranteed migration and implicit downtime
consent remain rejected; adding brand coverage does not validate those claims.
