# Remote viewer completion — the real link, not an SSH success message

Owning programme task: `gs-2uh.7`; incorporates the source work from draft PR #22.
This finishes that draft's source/Linux-browser blocker without reverting later
provider, temporal-evidence, verified-export or local-support changes. Broader
platform/estate qualification remains separate; the programme task is not closed
as universal macOS/Windows or fleet support.

## The failure was rechecked before implementation

The preserved original draft installation returned 200 for same-origin status,
403 for cross-site API access, and incorrectly 403 for a legitimate user-activated
root-page navigation. Its previous native SSH/HTTP proof could not clear the
browser case. The new allowance is exact: a GET of `/`, document navigation and
user activation. It does not permit iframe embedding, query-bearing URLs,
cross-site API reads or a foreign Origin. Duplicate Host/Origin/Fetch Metadata
headers are refused. Native-client requests without browser metadata still obey
the literal approved loopback Host restriction.

An optional planned laptop port works without binding a public interface or
accepting arbitrary origins. Existing runs without the option retain same-port
behavior. An identical active retry preserves its viewing port and deadline;
changing that port cannot silently replace the active run. The handoff is private,
bounded and short-lived, excludes raw node names and cannot be written inside the
observation workspace. Exact response identity and complete inventory are required.
An expired, redirected, malformed, stopped or different service cannot pass.

`viewer-plan` still executes no SSH or credential lookup. The host agent uses its
existing authorized native route. The generated foreground arguments explicitly
preserve strict host-key checking and disable after-authentication forking,
agent/X11 forwarding, local commands and unrelated control-session attachment.
Existing SSH configuration still applies and requires scope inspection. No new
supervisor, root service, public listener, provider action or connector is added.

## What actually ran

Twenty-nine protocol, handoff and owned-runtime tests pass. They reuse the draft's
22 cases and add navigation, duplicate metadata, digest-type, response-integrity
and output-location checks. The entire frozen source passes the collection suite;
the machine receipt records the exact totals rather than treating all of them as
new remote-viewer tests.

The Linux Chromium test uses real user input on a link from a separate local
origin. The browser itself emits cross-site / navigate / document / user-activation
headers; no request interception spoofs that proof. The link opens the forwarded
workbench, chart, pinned review and support download. Cross-site data navigation
and iframe requests return 403, while a cross-site script cannot read support
JSON. Closing and reopening the byte-preserving relay restores the same runtime
and retained evidence. Stopping the source makes portable verification fail.

The same browser path was exercised from the actual extracted candidate archive,
not only imports from the repository. Two initial test-harness issues were fixed:
the support button's exact accessible name was wrong, and Chromium suppressed an
image response at its browser security boundary rather than exposing it to the
response-event observer. The latter test now checks an actual blocked script read;
independent protocol tests still assert the server's 403. No product expectation
was weakened to turn missing data into success.

Separately, the same archive was used on the authorized Mac and development Linux
host. Native OpenSSH bound only the selected Mac loopback port, reached the exact
run/configuration/inventory and retained CSP/CORP. Disconnecting did not stop the
remote collector; reconnecting matched the same run; stopping the source failed
verification. All three synthetic subjects and 2,288 points kept their capture
hashes. Both owned test processes were stopped. No credentials or personal SSH
configuration were changed.

## Claims kept distinct

The relay/browser check is not an SSH authentication test. The native Mac/Linux
SSH proof is not a macOS browser test: that machine has neither an isolated
Chromium binary nor system Chrome. No browser was installed and no personal
profile was opened. Current scope is tested Linux Chromium interaction plus
portable/native Mac HTTP attachment, not blanket browser/OS certification.

A matching handoff is not a bearer token, independent kernel attestation, proof
of service health or provider attribution. Fetch Metadata protects ordinary
browser access; a process that can connect locally can forge headers. A verifier
hash cannot replace native SSH trust, and handoff expiry does not itself revoke
an existing tunnel. No native coding-model session or completed field pilot is
claimed by these deterministic and transport fixtures.

The single shared checkout on main was used with scoped commits. Shared Agent
Mail discovery returned an HTTP error; a host-local advisory reservation was
recorded, not presented as cross-host coordination. No service or permission
repair was attempted. The original field pilot and other skills were untouched.

Primary references reviewed on 2026-10-16: the W3C
[Fetch Metadata request-header draft](https://www.w3.org/TR/fetch-metadata/)
and [OpenSSH forwarding configuration](https://man.openbsd.org/ssh_config).
User-activated navigation and cross-site data reads are distinct contexts;
ExitOnForwardFailure does not establish that the ultimate service responds.
The installed [remote workflow](../../../skills/vps-health/references/remote-viewer.md)
and adjacent machine receipt retain these limits for future agents.
