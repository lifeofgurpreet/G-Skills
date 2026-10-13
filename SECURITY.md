# Security and privacy

Review code before execution. Skills are instructions plus software, not a sandbox. The scripts use only the Python standard library and do not require root. Local collection is passive; network collection is explicit, GET-only, bounded and does not follow redirects. HTTPS tokens are supplied by environment-variable name and are never copied into artifacts. Use separate credentials for Prometheus and Loki.

Captures can contain private labels, instance addresses, boot fingerprints and logs. Keep them in a private workspace, not this repository. `.gitignore` is a convenience, not a data-loss prevention system. Audit both the working tree and Git history before publishing. The learning proposal whitelists aggregate categories; it does not publish itself.

Artifacts are checksummed for integrity and reproducibility, not independently signed or attested. An adversary who can alter captures and manifests can replace both. Do not use an untrusted report as authorization for provider communication or infrastructure changes.

Do not open a public issue with credentials or private captures. Use GitHub's private security reporting where available; otherwise contact the repository owner privately with a minimal description before sharing sensitive details. No telemetry or remote learning endpoint is present.


The workspace HTTP server binds only to 127.0.0.1 and exposes two fixed read-only
routes. It is a local convenience viewer, not a public deployment. Do not port-
forward it to the internet or add a wildcard bind. Foreign Host/Origin values
are rejected; raw databases, configuration, credentials and log content are not
served. There is no browser mutation API or provider-send endpoint.

Workspaces, local draft files and summary exports are private data. Their hashes
provide change detection, not a trusted signature or independent attestation.
No workspace should be committed into this repository. Back up a stopped full
workspace privately; summary export is not a complete raw database backup.
