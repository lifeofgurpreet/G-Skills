# Publication readiness: a bounded preview, not an airtightness claim

The released v0.9.4 ZIP was compared with its published GitHub asset digest. Its
60 files matched the release manifest; all 39 authored local inline Markdown
targets resolved. Its CLI capabilities command worked with site-packages disabled.
This was an audit of the actual distribution, not just a source-tree inspection.

## A concrete first-use gap

The 235-line SKILL.md named `capabilities`, `agent-plan` and other operations but
never identified `scripts/vps_health.py`. That is an avoidable ambiguity for a
client working outside the installed folder. Version 0.9.5 identifies that owned
executable before giving subcommands and shows two read-only first calls using
the absolute installation path. This does not claim a measured behavioral uplift;
native paired evaluations remain uncompleted after the recorded authentication
failures.

The support scope now ships inside the independent skill folder. Users and agents
need not infer a version's compatibility from a changing main-branch web page.
This is a release-local boundary, not another source of live task state. The
native graph remains authoritative for unfinished work.

Six added acceptance cases cover the explicit entry, bundled support scope,
missing and escaping local links, document-relative reference resolution and a
real CLI invocation through an installation path containing spaces from an
unrelated working directory. The actual capabilities/help reads use no site
packages and create no files in that working directory. Four cases failed before
the corresponding changes. Inline-reference checks do not claim to validate
remote URL availability, heading anchors or every possible Markdown extension.

## No expansion of runtime authority or support claims

The collector/runtime implementation changed only its version constants. No
workbench assets, metric formulas, provider thresholds, mail flow, credentials,
host settings, private pilot or other skill changed. The package still runs
without the maintainer-only YAML dependency. Existing release tags are untouched.

Completed implementation and a valid discovery header are useful evidence; they
are not interchangeable with completed fresh-client task runs, reliable trigger
selection, actual connector reconciliation or representative 72-hour pilots.
The inline temporal UI, draft remote-viewer path and real-client/field gates remain
open. Optional mail sending and every platform need not block a clearly scoped
technical preview, but they cannot be advertised as universally supported.

## Publication position

Share this as a technical preview of agent-owned private VPS investigation:
retained observations, a real workbench, workload context and useful next actions.
Do not promise guaranteed migrations, conclusive neighbour identification, fake
migration detection, guest innocence or future adoption. The supplied speculative
proposals were not repository reviews; their useful mechanisms and unsupported
claims are already separated in [the Gemini review](GEMINI-REVIEW.md).

An early user should be able to identify the correct installed entry, demonstrate
the interface, authorize a target, preserve the observations and stop/resume the
owned workflow without author-written configuration. That outcome still needs
fresh-client and independent-user acceptance. No publicity post, provider message
or invitation was sent by this audit.

The standard's [format and progressive-disclosure guidance](https://agentskills.io/specification)
and Anthropic's [skill-creator evaluation loop](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md)
were checked as separate references. The official validator addresses file format;
the behavior loop requires actual task outputs. The installed support-scope file
is explicit about that distinction. Exact test totals and artifact hashes are
recorded in the adjacent machine receipt, not inferred from this prose.
