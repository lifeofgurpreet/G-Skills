# Measurement and interpretation

Visible vCPU count, CPU time accounted by the guest and application throughput are different quantities. Compare the quantity you actually measured. A shared vCPU is not automatically an exclusive physical core; a container's affinity or quota is not a provider invoice.

The local reader sums the first eight `/proc/stat` modes and does not add guest/guest_nice twice. Non-steal accounting excludes the steal mode. It compares counter deltas to a bracketed monotonic interval and checks wall-clock consistency, boot/CPU-set changes, counter decreases and read overhead. CPU, I/O and memory pressure are reported separately. It does not clamp an impossible ratio into a believable one. `SC_CLK_TCK` is read from the actual runtime.

The Prometheus adapter uses stock counter rates normalized by observed CPU count. Minimum sample, reset, target-up and mode-count checks screen obvious observer faults. It does not claim that exporter and hypervisor clocks, kernel accounting, collection boundaries or arbitrary missing series are perfectly calibrated. Native query extrapolation and sparse retention can affect estimates. Reconcile multiple exporter jobs before use. A rendered point is not proof of continuous coverage.

Report coverage counts represented elapsed intervals, capped by the requested cadence. Many points concentrated in a short burst cannot manufacture a full day. Values with explicit quality failures do not support the aggregate. Missing pressure and workload-limit context remain limitations, not zeros.

The default 0.90 threshold sorts investigation, not blame or contractual acceptance. Values within tolerance still require application/service checks. A lower value with contention means mixed evidence: high demand, restricted supply, quotas or several factors may coexist. The script never produces `provider_cause_proven=true` or authorizes contact.

For controlled tests, compare raw guard values before display rounding. Record the spinner's actual cgroup and relevant ancestors, per-thread scheduling waits, errors, sample counts, image/build, kernel, elapsed bounds, warm-up and stop behavior. Do not automatically set limits or sysctls to clear a guard. Retain every rejected run; repeatedly scraping a result is not repeating the experiment.

Do not pool migration epochs or describe an acknowledgment as a completed move. A fixed completion notice may establish an upper bound, while a date-only notice requires conservative end-of-day treatment. Current-host history and explicit authorization live in the user's adapter, not this public repository.

## Primary references

- [Linux /proc](https://docs.kernel.org/filesystems/proc.html): CPU modes and counter caveats, including iowait.
- [Linux pressure stall information](https://docs.kernel.org/accounting/psi.html): stalled time, not root-cause attribution.
- [CFS bandwidth control](https://docs.kernel.org/scheduler/sched-bwc.html): quota periods and hierarchy.
- [cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html): process/resource-control scope.
- [Prometheus query API](https://prometheus.io/docs/prometheus/latest/querying/api/): response status, range requests and warnings.
- [Prometheus query functions](https://prometheus.io/docs/prometheus/latest/querying/functions/): counter/gauge semantics and extrapolation.
- [Pushgateway lifecycle](https://prometheus.io/docs/practices/pushing/): retained series are not fresh executions.
- [Loki HTTP API](https://grafana.com/docs/loki/latest/reference/loki-http-api/): bounded range and log requests.

These references were reviewed on 2026-10-13. Verify the deployed version and product-specific behavior before consequential decisions.
