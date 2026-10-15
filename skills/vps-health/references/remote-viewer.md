# Open the private workbench from the user's actual viewing machine

The server's `127.0.0.1` and the laptop's `127.0.0.1` are different places. A
working listener on the VPS is not a working link for the human. The coding agent
owns resolving that gap through an already authorized host-access route; do not
send a localhost link without checking it from the machine that will open it.

This workflow adds no daemon, public listener, credential store or SSH client
implementation. It uses the existing managed worker, native OpenSSH and a small
private matching record. These steps are for the agent to perform. The user
supplies missing scope or authentication decisions, not configuration homework.

## 1. Choose the browser-side port before a new run

Use an available unprivileged port on the viewing machine. The agent checks the
port through its native tools; availability can change, so SSH must still fail
rather than hide a binding conflict. When the local and server ports differ,
include the intended viewing port in the normal approved plan/start request:

```bash
python3 scripts/vps_health.py agent-plan --workspace /private/investigation \
  --mode demo --duration-seconds 600 --viewer-port 18844
# The agent obtains the exact required approval, parses plan_sha256, then runs:
python3 scripts/vps_health.py agent-start --workspace /private/investigation \
  --mode demo --duration-seconds 600 --viewer-port 18844 --approve-plan REVIEWED_HASH
```

The example is synthetic. Use the actual approved local/Prometheus route for a
real investigation. A plan hash binds settings; it is not proof of human consent.

`--viewer-port` does not bind another server socket, permit a public IP or allow
arbitrary origins. The server continues listening only on its own IPv4 loopback
port. It additionally accepts the single planned `http://127.0.0.1:PORT` browser
origin. The request's Origin, when present, must match its allowed Host. Different
sites, arbitrary forwarded-host headers, duplicate headers and unplanned ports
are refused. No CORS wildcard is added.

For an already-running worker without this option, use the same local port as its
reported server port. An occupied port or changed viewing origin is a planning
conflict, not permission to kill another process, expose the listener or silently
restart the collector. An omitted option on an identical active retry reuses its
existing approved viewing port and does not renew the run's deadline.

## 2. Export a matching record from the authorized source host

```bash
python3 scripts/vps_health.py viewer-handoff --workspace /private/investigation \
  --out /private/viewer-handoff.json
```

The source operation verifies its actual owned worker and HTTP response first.
It then writes a private exclusive-create JSON file containing the run/configuration/
inventory fingerprints, expected count, mode, ports and expiration. Raw node names,
private workspace paths, measurements and credentials are not in that file. It is
still a private coordination artifact—not a support attachment or a bearer token.

The default validity is at most 15 minutes and never beyond the run's deadline.
The explicit validity limit can be 30–3600 seconds. Expiration limits how long a
verification can rely on this record; it does not automatically end an existing
SSH connection or revoke browser access. A new verification session should request
a fresh handoff, not edit its timestamps to make an old one pass.

Transfer it through the existing approved SSH/file channel. Do not upload it,
raw observations or credentials to a public paste site. The viewing machine needs
the same reviewed skill version and Python 3.10+; it does not need Linux counters,
root privileges, a new collector or the remote SQLite database.

## 3. The agent plans and opens the existing SSH route

On the viewing machine:

```bash
python3 scripts/vps_health.py viewer-plan --handoff /private/viewer-handoff.json \
  --ssh-target owner-confirmed-host
```

The result supplies `ssh_argv` plus a POSIX display example. It runs no network or
process operation. Execute the argument vector with the host agent's permitted
terminal tool, not by evaluating data as a shell script. On Windows, the vector
is the contract; the POSIX shell rendering is not PowerShell syntax.

The generated foreground OpenSSH forward binds explicitly to `127.0.0.1`, uses
strict host-key checks, disables agent/X11/local-command forwarding and does not
attach to an unrelated control-master session. It uses the existing approved
configuration and account. Inspect the selected trusted host profile for other
configured forwards and proxy behavior before execution. Do not scan all saved
hosts or assume SSH configuration presence authorizes access. `ClearAllForwardings`
is deliberately not added: it would remove the requested `-L` too.

Missing keys, untrusted/changed host keys, denied port forwarding or a busy port
are real blockers. Ask for the necessary authentication/trust decision; never
weaken host-key checks, search for another account or silently install a root
service. The plan does not own a background supervisor. Keep the forwarding task
under the host agent's normal lifecycle and close only that task when finished.

## 4. Verify from the machine that will open the browser

```bash
python3 scripts/vps_health.py viewer-verify --handoff /private/viewer-handoff.json
```

This reads only the exact planned IPv4 loopback status route, with no proxy or
redirect. It matches run identity, current RUNNING state, configuration, expected
inventory, mode, source version and response time. It must see the configured
missing/held subjects too; the response cannot drop inconvenient nodes and pass.

Only `VIEWER_MATCHED` is success. A live SSH PID or a successful `ExitOnForwardFailure`
check is insufficient: that option does not prove that the forwarding destination
answers. A wrong service, changed run/configuration, expired handoff, malformed
response or closed tunnel remains NOT_VERIFIED. Do not show that as a usable link.

The result is an HTTP identity match, not independent remote-kernel inspection,
cryptographic attestation or proof that SSH authenticated the intended host. The
native transport and its trusted host configuration establish that separate
boundary. Fresh HTTP does not establish fresh measurement coverage, a healthy
service or provider responsibility. The workbench keeps its ordinary evidence
states unchanged.

## 5. Reconnect and finish without restarting the investigation

If the tunnel closes, the remote collector continues. Reopen the same approved
forward through the owning terminal workflow, obtain a fresh matching record when
needed, re-verify and return to the same investigation. Never create a second
collector just to reconnect a browser. Closing a viewing connection does not
change the remote observation budget, delete evidence or contact a provider.

When the source worker itself stops or changes generation, the previous handoff
cannot verify the new service. Inspect the source state and use its normal
approved recovery path. Windows client behavior, non-Linux managed persistence,
reboot recovery and arbitrary estate inventory are separate acceptance gates.

Primary references: [OpenSSH forwarding](https://man.openbsd.org/ssh),
[OpenSSH configuration and forwarding limits](https://man.openbsd.org/ssh_config),
and [the Web Origin model](https://www.rfc-editor.org/rfc/rfc6454).
These describe the protocol boundary; the actual release tests and cross-device
receipt establish which paths were exercised, not universal deployment support.
