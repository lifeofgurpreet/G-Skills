# Remote viewer attachment — draft implementation and actual device evidence

Owning task: `gs-2uh.7`. This is a bounded slice of heterogeneous-estate support,
not completion of that whole programme. The published v0.9.0 release and running
v0.8.0 passive qualification installation are unchanged.

## The reproduced user problem

The previous viewer returned HTTP 200 directly, but HTTP 403 through an ordinary
byte-preserving forward whose local port differed from the server's port. The
server compared the browser Host header against only its own listener port.
An agent could truthfully report a running monitor and still give the user an
unusable link on their laptop.

The draft adds one explicit plan-bound `--viewer-port`, rather than accepting
arbitrary Host values or exposing a public listener. Normal runs without that
option retain the original exact port restriction. Request Origin must match the
allowed incoming Host; duplicate headers, unrelated sites, arbitrary ports and
private-file routes remain refused. No CORS wildcard or token-bearing URL is used.

## Implemented agent workflow

`viewer-handoff` first checks the actual owned source worker and HTTP response,
then writes a private short-lived record. It contains run/configuration/inventory
fingerprints, count, mode, version, ports and expiration—not raw host aliases,
workspace paths, credentials or measurement history.

`viewer-plan` runs on the viewing machine and returns a foreground OpenSSH argument
vector for an explicitly supplied authorized target. It performs no network,
credential discovery, command execution or service installation. The host agent
reviews the existing selected SSH profile and executes the operation through its
ordinary permitted tools. Strict host-key checking and loopback binding remain;
local commands, agent/X11 forwarding and unrelated master-session attachment are
disabled. Existing user SSH configuration still applies and must be reviewed.

`viewer-verify` checks the exact planned local endpoint against the handoff's run,
configuration, full expected inventory, mode/version, running status and freshness.
A process claiming to be SSH is not enough. A closed tunnel, wrong service, changed
run, stale handoff or untrustworthy response remains NOT_VERIFIED. A matching
response is explicitly not independent SSH authentication or remote-kernel
attestation, nor proof of measurement quality or provider fault.

## Actual Mac → SSH → Linux acceptance

The same extracted 52-file candidate archive was used on both authorized devices.
A temporary synthetic workspace ran on the development Linux host; Python 3.14.5
and native OpenSSH 10.5p1 operated the viewing-side workflow on macOS. The selected
trusted host profile had no preconfigured forwards. No account was changed and
no host-key, sandbox or permission check was bypassed.

The actual different-port SSH route matched the intended investigation. Native
listener inspection found only the selected IPv4 loopback listener. The workbench
HTML and unchanged CSP/CORP protections were read through it, and a foreign Origin
was refused. Closing the owned SSH process made verification fail while the remote
worker continued. Reconnecting matched the same run. Stopping the owned remote
worker then caused verification to fail again. Both test processes were closed.
All three synthetic subjects and 2,288 observations retained the same capture hashes.

This is actual native SSH and HTTP evidence across two machines, not a mocked SSH
call. It is not a native Codex/Claude model session. The macOS Playwright package
was present but its browser binary was unavailable; actual macOS browser interaction
was not exercised and no personal browser or settings were changed. The machine
receipt is `remote-viewer-device-proof.json` in this directory.

## Why this remains a draft

The added request-site restriction currently rejects a legitimate user-activated
top-level root-page navigation from an external site as well as cross-site data
reads. A synthetic header-level reproduction returns 403 where the desired root
navigation should be allowed. Direct address-bar/navigation and same-origin API
use are different paths; a green direct HTTP test does not qualify clicking an
external link in a browser.

A tool blocked the final proposed request-handling correction. That edit was not
applied, retried through another execution route or hidden by changing the expected
outcome. This branch is not approved for merging or release until root navigation
is distinguished from embedded/cross-site API access, and the actual browser
interaction is verified. The existing release remains the usable published version.

The ordinary code tests cover the implemented boundaries, not that unresolved
user outcome. The private reproduction is preserved; passing test counts below
must not be described as complete remote-browser acceptance.

## Limits and sources

Native host trust and the user's SSH configuration remain separate from local
HTTP matching. Handoff expiration limits verification, not connection lifetime or
access revocation. An existing foreground tunnel is not a reboot-persistent service.
Windows control-host behavior, full inventory discovery, persistent restart and
unrelated estates remain open acceptance work. No provider contact, active benchmark,
production change, raw customer-data publication or private pilot upgrade occurred.

Read the [installed workflow](../../../skills/vps-health/references/remote-viewer.md).
Primary references reviewed: [OpenSSH local forwarding](https://man.openbsd.org/ssh),
[OpenSSH forwarding and host-key options](https://man.openbsd.org/ssh_config),
and the [W3C Fetch Metadata draft](https://www.w3.org/TR/fetch-metadata/).
The latter is a protocol reference, not a claim of final W3C recommendation status.
Installed pstack ownership/actual-artifact principles and selected agent-continuation
guidance informed one reused viewer workflow rather than another SSH/monitoring daemon.


## Current deterministic validation

The complete frozen-source suite passed 494 Python tests, including 22 new viewer
contracts. The selected 52-file archive was actually extracted and exercised
through owned runtime start, local viewer verification, private handoff, portable
planning/readback and stop. These passing paths do not satisfy the documented
external-link navigation gate or imply macOS browser interaction.
