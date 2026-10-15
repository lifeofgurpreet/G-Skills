#!/usr/bin/env python3
"""Turn a coding-agent fleet up for a usage reset and back down, with readback.

Changes Codex launch defaults (model, reasoning effort, service tier), NTM
templates and idle live Herdr/tmux sessions. Never sends an inference prompt,
reads a transcript, restarts a session or changes accounts or credentials.

Control panel:   reset_boost.py serve --help
Agent verbs:     reset_boost.py {signals,pane,converge,channel,rules,move,rehome,agent} --help
Boost lifecycle: reset_boost.py {boost,done,watch,status,dashboard} --help
One-off policy:  reset_boost.py {audit,set,presets} --help
"""
import argparse
import base64
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10: the boost lifecycle and dashboard still work.
    tomllib = None

VERSION = "0.3.0"
ALIASES = {"sol61": "gpt-6.1-sol", "sol": "gpt-6.1-sol", "luna": "gpt-6-luna", "terra": "gpt-5.6-terra", "astra": "gpt-6-astra"}
EFFORTS = ("low", "medium", "high", "xhigh", "max", "ultra")
TIERS = ("default", "priority", "flex")
TIER_ALIASES = {"fast": "priority", "off": "default"}
MODEL_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]*")
PROFILE_RE = re.compile(r"[A-Za-z0-9._@+-]+")
LOCAL_ONLY = {"local": {"type": "local"}}
BACKUP_TAG = ".reset-boost-"


def real_home():
    # Agent sessions often redirect HOME; the account's password-database home is the real one.
    return Path(pwd.getpwuid(os.getuid()).pw_dir)


def state_dir():
    return Path(os.environ.get("RESET_BOOST_STATE_DIR") or real_home() / ".local/state/reset-boost")


def load_config():
    """Read the estate description; without one, only this machine is managed."""
    path = Path(os.environ.get("RESET_BOOST_CONFIG") or real_home() / ".config/reset-boost/config.json")
    config = json.loads(path.read_text()) if path.exists() else {}
    config.setdefault("hosts", LOCAL_ONLY)
    config.setdefault("baseline", "normal")
    config.setdefault("exclude_profiles", [])
    config["_path"] = str(path)
    for name, host in config["hosts"].items():
        if host.get("type") not in ("local", "ssh", "windows"):
            raise ValueError("host " + name + ": type must be local, ssh or windows")
        roots = host.get("project_roots", [])
        if not isinstance(roots, list) or any(not isinstance(root, str) or not root.startswith("/") for root in roots):
            raise ValueError("host " + name + ": project_roots must be a list of absolute paths")
    return config


def require_toml():
    if tomllib is None:
        raise RuntimeError("reading Codex/NTM TOML needs Python 3.11+ (tomllib)")


def safe_profile(profile):
    """The account-manager (CAAM) shallow-home spelling of a profile name."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", profile)


DEFAULT_PRESETS = {
    "normal": {"model": "gpt-6.1-sol", "effort": "medium", "tier": "default", "description": "Cost-balanced everyday work; the usual baseline."},
    "reset": {"model": "gpt-6.1-sol", "effort": "high", "tier": "default", "description": "More reasoning for a reset window."},
    "drain": {"model": "gpt-6.1-sol", "effort": "low", "tier": "default", "description": "Lower-cost queue draining."},
    "sol-medium": {"model": "gpt-6.1-sol", "effort": "medium", "tier": "default", "description": "Sol with standard reasoning."},
    "sol-high": {"model": "gpt-6.1-sol", "effort": "high", "tier": "default", "description": "Sol with high reasoning."},
    "sol-high-fast": {"model": "gpt-6.1-sol", "effort": "high", "tier": "priority", "description": "Sol high with fast mode."},
    "luna-fast": {"model": "gpt-6-luna", "effort": "low", "tier": "default", "description": "Fast, economical work."},
    "luna-standard": {"model": "gpt-6-luna", "effort": "medium", "tier": "default", "description": "Luna with standard reasoning."},
    "luna-high": {"model": "gpt-6-luna", "effort": "high", "tier": "default", "description": "Luna with high reasoning."},
    "astra-medium": {"model": "gpt-6-astra", "effort": "medium", "tier": "default", "description": "Astra, standard reasoning."},
    "astra-high": {"model": "gpt-6-astra", "effort": "high", "tier": "default", "description": "Astra, high reasoning."},
    "astra-ultra": {"model": "gpt-6-astra", "effort": "ultra", "tier": "default", "description": "Astra, maximum reasoning."},
    "astra-ultra-fast": {"model": "gpt-6-astra", "effort": "ultra", "tier": "priority", "description": "Everything up: Astra ultra with fast mode."},
}


def presets():
    path = Path(__file__).resolve().with_name("presets.json")
    if path.exists():
        try:
            value = json.loads(path.read_text())
            if isinstance(value, dict) and value:
                return value
        except (OSError, ValueError):
            pass
    return DEFAULT_PRESETS


def resolve_target(model, effort, preset, tier=None):
    """Return {model, effort, tier}; tier None leaves the service tier untouched ("fast" means priority)."""
    tier = TIER_ALIASES.get(tier, tier)
    if preset:
        catalog = presets()
        if preset not in catalog:
            raise ValueError("unknown preset: " + preset)
        selected = catalog[preset]
        if not isinstance(selected, dict) or not MODEL_ID_RE.fullmatch(str(selected.get("model", ""))) or selected.get("effort") not in EFFORTS \
                or selected.get("tier", "default") not in TIERS:
            raise ValueError("invalid preset definition: " + preset)
        return {"model": selected["model"], "effort": selected["effort"], "tier": tier or selected.get("tier")}
    if tier is not None and tier not in TIERS:
        raise ValueError("tier must be one of " + ", ".join(TIERS))
    return {"model": ALIASES.get(model or "sol61", model or "gpt-6.1-sol"), "effort": effort or "medium", "tier": tier}


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def replace_token(command, start, value):
    """Replace one shell/Go-template value, including a complete if/else block."""
    if command.startswith("{{", start):
        close = command.index("}}", start) + 2
        if command[start + 2:close - 2].strip().startswith("if "):
            depth = 1
            for match in re.finditer(r"{{(.*?)}}", command[close:], re.S):
                tag = match[1].strip()
                if tag.startswith("if "):
                    depth += 1
                elif tag == "end":
                    depth -= 1
                if depth == 0:
                    close += match.end()
                    break
            else:
                raise ValueError("unbalanced NTM template")
        end = close
    elif command[start:start + 1] in ("'", '"'):
        quote = command[start]
        end = start + 1
        while end < len(command):
            if command[end] == quote and command[end - 1] != "\\":
                end += 1
                break
            end += 1
        else:
            raise ValueError("unterminated NTM argument")
    else:
        match = re.match(r"\S+", command[start:])
        if not match:
            raise ValueError("missing NTM argument")
        end = start + match.end()
    return command[:start] + value + command[end:]


def pin_command(command, model, effort):
    match = re.search(r"(?:^|\s)(?:-m|--model)\s+", command)
    if not match:
        raise ValueError("NTM Codex template has no recognized model argument; preserved")
    command = replace_token(command, match.end(), "{{if .Model}}" + model + "{{else}}" + model + "{{end}}")
    match = re.search(r"model_reasoning_effort=", command)
    if not match:
        raise ValueError("NTM Codex template has no recognized effort argument; preserved")
    return replace_token(command, match.end(), "{{if .ReasoningEffort}}" + effort + "{{else}}" + effort + "{{end}}")


def transform(text, kind, model, effort, tier=None):
    """Pin model/effort (and the service tier when given); everything else is preserved."""
    require_toml()
    parsed = tomllib.loads(text)
    lines, section = [], ""
    seen = set()
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("["):
            section = line.strip().split("#", 1)[0].strip()
        match = re.match(r"\s*([\w-]+)\s*=", line)
        key = match[1] if match else None
        if kind == "codex" and (not section or section.startswith("[profiles.")):
            if key in ("model", "model_reasoning_effort") or (key == "service_tier" and tier is not None and not section):
                value = {"model": model, "model_reasoning_effort": effort, "service_tier": tier}[key]
                line = line[:match.end()] + " " + json.dumps(value) + "\n"
                if not section:
                    seen.add(key)
        elif kind == "ntm":
            if (section == "[models]" and key == "default_codex") or (section == "[models.codex]" and key):
                line = line[:match.end()] + " " + json.dumps(model) + "\n"
            elif section == "[agents]" and key == "codex":
                command = pin_command(parsed["agents"]["codex"], model, effort)
                line = line[:match.end()] + " " + json.dumps(command, ensure_ascii=False) + "\n"
        lines.append(line)
    new = "".join(lines)
    if kind == "codex":
        prefix = ""
        # A missing service_tier already means the provider default; only add it to change it.
        for key, value in (("model", model), ("model_reasoning_effort", effort), ("service_tier", None if tier == "default" else tier)):
            if key not in seen and value is not None:
                prefix += key + " = " + json.dumps(value) + "\n"
        new = prefix + new
    check = tomllib.loads(new)
    if kind == "codex" and (check.get("model"), check.get("model_reasoning_effort")) != (model, effort):
        raise ValueError("Codex setting readback failed")
    if kind == "codex" and tier is not None and check.get("service_tier", "default") != tier:
        raise ValueError("Codex service tier readback failed")
    if kind == "ntm":
        if "default_codex" in parsed.get("models", {}) and check["models"]["default_codex"] != model:
            raise ValueError("NTM default readback failed")
        if "codex" in parsed.get("agents", {}):
            if check["agents"]["codex"] != pin_command(parsed["agents"]["codex"], model, effort):
                raise ValueError("NTM template readback failed")
    return new


def transform_policy(text, model, effort):
    """CAAM adapter: the data-only launch policy its Codex wrapper reads."""
    values = {"CAAM_CODEX_MODEL": model, "CAAM_CODEX_REASONING_EFFORT": effort}
    seen = set()
    lines = []
    for line in text.splitlines():
        key, sep, _ = line.partition("=")
        if sep and key in values:
            lines.append(key + "=" + values[key])
            seen.add(key)
        else:
            lines.append(line)
    for key, value in values.items():
        if key not in seen:
            lines.append(key + "=" + value)
    return "\n".join(lines).rstrip() + "\n"


def homes():
    # A root worker (sudo over SSH) covers every account on the host; otherwise only our own.
    if os.getuid() == 0 and Path("/home").is_dir():
        return [p for p in Path("/home").iterdir() if p.is_dir()] + [Path("/root")]
    return [real_home()]


def profile_of(path):
    """The account-manager profile a config belongs to (CAAM layouts), in safe spelling."""
    text = str(path)
    match = re.search(r"/orch-homes/codex-([^/]+)/\.codex/config\.toml$", text) or \
        re.search(r"/\.local/share/caam/profiles/codex/([^/]+)/codex_home/config\.toml$", text) or \
        re.search(r"/\.config/caam/model-policy\.d/([^/]+)\.env$", text)
    return safe_profile(match[1]) if match else None


def config_paths(profiles=(), project_roots=()):
    files = {}
    patterns = {"codex": (".codex/config.toml", "orch-homes/codex-*/.codex/config.toml", ".local/share/caam/profiles/codex/*/codex_home/config.toml", "projects/*/.codex/config.toml"),
                "ntm": (".config/ntm/*.toml", ".ntm/config.toml", "projects/*/.ntm/config.toml")}
    for home in homes():
        for kind, globs in patterns.items():
            for glob in globs:
                for path in home.glob(glob):
                    files[path.resolve()] = kind
    for base in [Path(root) for root in project_roots] + homes():
        for glob, kind in (("*/.codex/config.toml", "codex"), ("*/.ntm/config.toml", "ntm")):
            for path in base.glob(glob):
                files[path.resolve()] = kind
    for home in homes():
        # Optional CAAM adapter: only when CAAM's config directory already exists.
        policy = home / ".config/caam/model-policy.env"
        if policy.exists() or (home / ".config/caam").is_dir():
            files[policy.resolve()] = "policy"
            # Per-profile launch policy: every profile with a target plus any stale leftovers.
            for name in profiles:
                if PROFILE_RE.fullmatch(name) and name not in (".", ".."):
                    files[(home / ".config/caam/model-policy.d" / (name + ".env")).resolve()] = "policy"
            for path in (home / ".config/caam/model-policy.d").glob("*.env"):
                files[path.resolve()] = "policy"
    return files


def target_for(path, args):
    """Host target unless this path belongs to a profile with its own target."""
    profile = profile_of(path)
    overrides = {safe_profile(name): value for name, value in (args.get("profiles") or {}).items()}
    return dict(overrides.get(profile) or args["target"], profile=profile)


def change_file(path, kind, args):
    target = target_for(path, args)
    model, effort, tier = target["model"], target["effort"], target.get("tier")
    old = path.read_text() if path.exists() else ""
    if kind == "policy":
        new = transform_policy(old, model, effort)
    elif kind == "codex":
        new = transform(old, kind, model, effort, tier)
    else:
        new = transform(old, kind, model, effort)
    row = {"path": str(path), "kind": kind, "profile": target["profile"], "status": "matches" if new == old else "would_change",
           "target": {"model": model, "effort": effort, "tier": tier if kind == "codex" else None}}
    if kind == "codex":
        parsed = tomllib.loads(old)
        row["observed"] = {"model": parsed.get("model"), "effort": parsed.get("model_reasoning_effort"), "tier": parsed.get("service_tier")}
    elif kind == "ntm":
        row["observed"] = {"default_codex": tomllib.loads(old).get("models", {}).get("default_codex")}
    if new != old and args["apply"]:
        # Sidecar backups plus an inode-preserving write keep shared links and ownership.
        # Refuse a detected concurrent edit instead of overwriting it.
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        backup = path.with_name(path.name + BACKUP_TAG + stamp)
        # model-policy.d holds data this tool regenerates on every switch; no backups there.
        keep_backup = path.parent.name != "model-policy.d"
        existed = path.exists()
        if existed:
            with path.open("r+") as handle:
                if handle.read() != old:
                    raise ValueError("concurrent edit; preserved")
                if keep_backup:
                    shutil.copy2(path, backup)
                if keep_backup and os.getuid() == 0:
                    owner = path.stat()
                    os.chown(backup, owner.st_uid, owner.st_gid)
                handle.seek(0)
                handle.write(new)
                handle.truncate()
                handle.flush()
                os.fsync(handle.fileno())
        else:
            created_dir = not path.parent.exists()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(new)
            if os.getuid() == 0:
                # New per-profile policy files belong to the home's owner, not root.
                owner = path.parent.parent.stat()
                for item in ([path.parent] if created_dir else []) + [path]:
                    os.chown(item, owner.st_uid, owner.st_gid)
        if path.read_text() != new:
            raise ValueError("file readback failed; backup retained")
        row.update(status="changed", backup=str(backup) if existed and keep_backup else None,
                   created=not existed, before_sha256=digest(old), after_sha256=digest(new))
    return row


def spawnable(argv):
    """Absolute executable plus close_fds=False lets Python use posix_spawn instead of fork.

    fork() from a multi-threaded process (parallel hosts, the panel's web threads) can hang
    on macOS while holding the interpreter lock, freezing every thread. Python's own file
    descriptors are non-inheritable by default, so not closing them in the child is safe.
    """
    executable = argv[0] if os.path.isabs(argv[0]) else shutil.which(argv[0])
    if not executable:
        raise FileNotFoundError(argv[0])
    return [executable] + list(argv[1:])


def run_process(argv, **options):
    return subprocess.run(spawnable(argv), close_fds=False, **options)


def execute(argv, user=None, timeout=15, env=None):
    if user and os.getuid() == 0 and user != "root":
        argv = ["sudo", "-n", "-u", user] + argv
    result = run_process(argv, capture_output=True, text=True, timeout=timeout, env=env)
    if result.returncode:
        # Terminal text and command output may contain private material. Never echo it.
        raise RuntimeError("control command failed (exit " + str(result.returncode) + ")")
    return result.stdout


def processes():
    try:
        raw = execute(["ps", "-axo", "pid=,ppid=,comm="])
    except (OSError, RuntimeError):
        return {}
    return {int(row[0]): (int(row[1]), row[2]) for line in raw.splitlines() if len(row := line.strip().split(None, 2)) == 3}


def launch_overrides(target_model="gpt-6.1-sol", target_effort="medium"):
    """Read only model flags from Codex argv; never retain complete argv text."""
    rows = []
    if Path("/proc").is_dir():
        candidates = []
        for proc in Path("/proc").glob("[0-9]*"):
            try:
                comm = proc.joinpath("comm").read_text().strip()
                if comm != "codex":
                    continue
                argv = [part.decode(errors="replace") for part in proc.joinpath("cmdline").read_bytes().split(b"\0") if part]
                user = pwd.getpwuid(proc.stat().st_uid).pw_name
                candidates.append((int(proc.name), user, argv))
            except (PermissionError, FileNotFoundError, ProcessLookupError, ValueError, KeyError):
                continue
    else:
        try:
            raw = execute(["ps", "-axo", "pid=,user=,comm=,args="])
        except (OSError, RuntimeError):
            # macOS privacy controls can hide process arguments. That is an
            # observability gap, not a reason to fail a settings audit.
            return None
        candidates = []
        for line in raw.splitlines():
            fields = line.strip().split(None, 3)
            if len(fields) != 4 or (fields[2] != "codex" and not fields[2].endswith("/codex")):
                continue
            try:
                candidates.append((int(fields[0]), fields[1], fields[3].split()))
            except ValueError:
                continue
    for pid, user, argv in candidates:
        model = effort = None
        mode = "native"
        i = 0
        while i < len(argv):
            arg = argv[i]
            if arg == "--":
                break
            if arg in ("-m", "--model") and i + 1 < len(argv):
                model = argv[i + 1]
                i += 2
                continue
            if arg.startswith("--model="):
                model = arg.split("=", 1)[1]
            elif arg in ("-c", "--config") and i + 1 < len(argv):
                key, _, value = argv[i + 1].partition("=")
                if key == "model":
                    model = value
                elif key == "model_reasoning_effort":
                    effort = value.strip('"')
                i += 1
            elif arg.startswith("--config="):
                key, _, value = arg[len("--config="):].partition("=")
                if key == "model":
                    model = value
                elif key == "model_reasoning_effort":
                    effort = value.strip('"')
            i += 1
        if any(item in argv for item in ("app-server", "exec")):
            mode = "app-server-or-exec"
        status = "no-explicit-override" if model is None and effort is None else (
            "explicit-match" if (model, effort) == (target_model, target_effort) else "explicit-mismatch")
        rows.append({"pid": pid, "user": user, "mode": mode, "model": model,
                     "effort": effort, "status": status})
    return rows


def terminals():
    found, issues = [], []
    ps = processes()
    native = {pid for pid, (_, command) in ps.items() if command == "codex" or command.endswith("/codex")}
    sockets = set()
    pid_profiles = {}
    if Path("/proc").is_dir():
        interactive = set()
        for pid in native:
            try:
                proc = Path("/proc") / str(pid)
                command = proc.joinpath("cmdline").read_bytes().split(b"\0")
                if any(mode in command for mode in (b"app-server", b"exec")):
                    continue
                if not str(proc.joinpath("fd/0").readlink()).startswith(("/dev/pts/", "/dev/tty")):
                    continue
                interactive.add(pid)
                # Only route metadata is selected; no environment dump or auth access.
                for entry in proc.joinpath("environ").read_bytes().split(b"\0"):
                    if entry.startswith(b"TMUX="):
                        sock = entry.split(b"=", 1)[1].split(b",", 1)[0].decode()
                        sockets.add((pwd.getpwuid(proc.stat().st_uid).pw_name, sock))
                    elif entry.startswith(b"CODEX_HOME="):
                        home_match = re.search(r"/orch-homes/codex-([^/]+)/\.codex/?$", entry[11:].decode(errors="replace"))
                        if home_match:
                            pid_profiles[pid] = safe_profile(home_match[1])
            except (PermissionError, FileNotFoundError, ProcessLookupError, KeyError):
                continue
        native = interactive
    for user, socket in sorted(sockets):
        try:
            raw = execute(["tmux", "-S", socket, "list-panes", "-a", "-F", "#{pane_id}\t#{pane_pid}"], user)
            for line in raw.splitlines():
                pane, root_pid = line.split("\t")
                root_pid = int(root_pid)
                owns_codex = False
                for codex_pid in native:
                    pid, seen = codex_pid, set()
                    while pid in ps and pid not in seen:
                        if pid == root_pid:
                            owns_codex = True
                            break
                        seen.add(pid)
                        pid = ps[pid][0]
                    if owns_codex:
                        break
                if owns_codex:
                    found.append({"backend": "tmux", "user": user, "socket": socket, "pane": pane, "profile": pid_profiles.get(codex_pid), "pid": codex_pid})
        except Exception as error:
            issues.append({"backend": "tmux", "user": user, "error": str(error)})
    for home in homes():
        user = pwd.getpwuid(home.stat().st_uid).pw_name
        candidates = [home / ".local/bin/herdr", home / "bin/herdr"]
        if user == pwd.getpwuid(os.getuid()).pw_name and shutil.which("herdr"):
            candidates.append(Path(shutil.which("herdr")))
        binary = next((path for path in candidates if path.exists()), None)
        if binary is None:
            continue
        configs = [home / ".config/herdr"] + list((home / ".config/herdr/sessions").glob("*"))
        # Optional CAAM adapter: it records which profile launched each Codex session Herdr restores.
        try:
            session_profiles = json.loads((home / ".local/state/caam/herdr-codex-session-profiles.json").read_text()).get("sessions", {})
        except (OSError, ValueError, AttributeError):
            session_profiles = {}
        for config in configs:
            if not (config / "herdr.sock").exists():
                continue
            prefix = [str(binary)]
            if config != home / ".config/herdr":
                prefix += ["--session", config.name]
            try:
                data = json.loads(execute(prefix + ["agent", "list"], user))
                if data.get("error"):
                    continue  # Stale socket of a stopped session, never start it.
                for agent in data.get("result", {}).get("agents", []):
                    if agent.get("agent") == "codex":
                        session = (agent.get("agent_session") or {}).get("value")
                        profile = (session_profiles.get(session) or {}).get("profile") if session else None
                        found.append({"backend": "herdr", "user": user, "prefix": prefix, "pane": agent["pane_id"], "state": agent.get("agent_status", "unknown"),
                                      "profile": safe_profile(profile) if profile else None})
            except Exception:
                continue
    return found, issues


def screen(terminal):
    if terminal["backend"] == "tmux":
        return execute(["tmux", "-S", terminal["socket"], "capture-pane", "-p", "-t", terminal["pane"], "-S", "0", "-E", "200"], terminal["user"])
    raw = execute(terminal["prefix"] + ["agent", "read", terminal["pane"], "--source", "visible"], terminal["user"])
    try:
        return json.loads(raw).get("result", {}).get("text", "")
    except json.JSONDecodeError:
        return raw


RUN_STATES = ("working", "idle", "starting", "thinking", "waiting", "running", "ready")


def telemetry(text):
    """Parse the Codex status line (bottom of the screen) into session telemetry.

    It carries what the session itself reports: model, effort, fast mode, run state,
    the account's 5-hour/weekly quota left, credits spent by the thread, and folder.
    Only this line is read; conversation text is never kept.
    """
    for line in reversed(text.splitlines()[-8:]):
        match = re.match(r"^\s*(GPT-[\w.\-]+)\s+([\w…]+)((?:\s+fast)?)\s*(?:·\s*(.*))?$", line, re.I)
        if not match:
            continue
        effort = match[2].lower()
        if effort.endswith("…"):
            # A narrow pane truncates the status line ("me…"); accept an unambiguous prefix.
            candidates = [name for name in EFFORTS if name.startswith(effort[:-1])] if len(effort) > 1 else []
            effort = candidates[0] if len(candidates) == 1 else effort
        result = {"model": match[1].lower(), "effort": effort if effort in EFFORTS else None, "fast": bool(match[3].strip()),
                  "run_state": None, "five_hour_left": None, "weekly_left": None, "credits": None, "cwd": None}
        for part in (match[4] or "").split("·"):
            part = part.strip()
            quota = re.match(r"^(5h|weekly)\s+(\d+(?:\.\d+)?)%\s+left$", part, re.I)
            if quota:
                result["five_hour_left" if quota[1].lower() == "5h" else "weekly_left"] = float(quota[2])
            elif "credit" in part.lower() or re.match(r"^\$\d", part):
                result["credits"] = part[:40]
            elif part.startswith(("/", "~")):
                result["cwd"] = part[:200]
            elif part.lower() in RUN_STATES:
                result["run_state"] = part.lower()
        return result
    return None


def on_credits(info, floor=0.0):
    """Is this session spending (or about to spend) paid credits instead of plan quota?"""
    if not info:
        return False
    if info.get("credits"):
        return True
    return any(value is not None and value <= floor for value in (info.get("five_hour_left"), info.get("weekly_left")))


def ui_state(text):
    """Retain settings UI only; visible conversations and drafts are never emitted."""
    footer_area = "\n".join(text.splitlines()[-8:])
    footers = re.findall(r"^\s*(GPT-[\w.\-]+)\s+(high|xhigh|low|medium|ultra|max)\b", footer_area, re.M | re.I)
    info = telemetry(text)
    modal = re.search(r"(?ms)^\s*(?:Select (?:Model(?: and Effort)?|[^\n]*Reasoning[^\n]*)|Advanced Reasoning)\n.*?^\s*enter [^\n]*esc [^\n]*", text)
    # Never append /model to an existing user draft. Known built-in placeholders
    # are safe to replace; unrecognized composers are held for manual control.
    composer = re.findall(r"^\s*[›»]\s*(.*)$", text, re.M)
    empty = any(not line.strip() or re.fullmatch(r"(?:Ask Codex to do anything|Implement \{feature\}|Explain this codebase|Write tests for @filename|Find and fix a bug in @filename|Improve documentation in @filename|Summarize recent commits|Use /skills to list available skills)", line.strip()) for line in composer)
    busy = "esc to interrupt" in text.lower() or bool(info and info.get("run_state") in ("working", "thinking", "running"))
    return {"footer": tuple(part.lower() for part in footers[-1]) if footers else None, "modal": modal[0] if modal else "", "empty_composer": empty,
            "busy": busy, "telemetry": info}


def send(terminal, text=None, keys=()):
    if terminal["backend"] == "tmux":
        prefix = ["tmux", "-S", terminal["socket"], "send-keys", "-t", terminal["pane"]]
        if text is not None:
            execute(prefix + ["-l", text], terminal["user"])
        if keys:
            execute(prefix + list(keys), terminal["user"])
    else:
        if text is not None:
            execute(terminal["prefix"] + ["pane", "send-text", terminal["pane"], text], terminal["user"])
        if keys:
            key_names = [{"Escape": "esc", "Enter": "enter", "Up": "up", "Down": "down", "C-c": "ctrl+c", "BSpace": "backspace"}.get(key, key) for key in keys]
            execute(terminal["prefix"] + ["agent", "send-keys", terminal["pane"]] + key_names, terminal["user"])


def menu_rows(modal):
    return [(int(match[2]), match[3].strip(), bool(match[1].strip())) for match in re.finditer(r"^\s*([›❯>]?)\s*(\d+)\.\s+([^\n]+)", modal, re.M)]


def wait_ui(terminal, predicate, seconds=3):
    end = time.monotonic() + seconds
    while True:
        state = ui_state(screen(terminal))
        if predicate(state) or time.monotonic() >= end:
            return state
        time.sleep(0.15)


def choose(terminal, modal, predicate):
    rows = menu_rows(modal)
    target = next((row[0] for row in rows if predicate(row[1])), None)
    current = next((row[0] for row in rows if row[2]), None)
    if target is None or current is None:
        raise ValueError("requested setting absent or picker selection unrecognized")
    delta = target - current
    if delta:
        send(terminal, keys=["Down" if delta > 0 else "Up"] * abs(delta))
    send(terminal, keys=["Enter"])


def pane_target(terminal, args):
    """The target for this session: its own setting, else its account's, else the fleet's.

    None means the account must not be guessed (an unknown session while pins exist).
    """
    own = (args.get("pane_targets") or {}).get(terminal.get("pane"))
    if own:
        return own
    overrides = {safe_profile(name): value for name, value in (args.get("profiles") or {}).items()}
    profile = terminal.get("profile")
    if profile in overrides:
        return overrides[profile]
    if profile is None and args.get("hold_unknown"):
        return None
    return args["target"]


def is_up(target, baseline):
    """Does moving to `target` spend more than the baseline? Anything not at baseline counts as up,
    except a pure step down in reasoning on the same model without fast mode."""
    if not baseline or target == baseline:
        return False
    order = list(EFFORTS)
    same_model = target["model"] == baseline["model"]
    no_fast = (target.get("tier") or "default") != "priority"
    if same_model and no_fast and target["effort"] in order and baseline["effort"] in order:
        return order.index(target["effort"]) > order.index(baseline["effort"])
    return True


def wants_fast(target):
    tier = (target or {}).get("tier")
    return None if tier is None else tier == "priority"


def leftover(terminal, text):
    """What remains of our typed command in the composer (it may have lost its first keystrokes)."""
    found = re.findall(r"^\s*[›»]\s*(\S+)\s*$", screen(terminal), re.M)
    return found[-1] if found and len(found[-1]) >= 2 and text.endswith(found[-1]) else ""


def command(terminal, text):
    """Type a slash command and submit it. Codex reads fast keystrokes as a paste and can
    swallow the Enter, so pause first, retry once, and erase our text if it still sits there."""
    send(terminal, text=text)
    time.sleep(.35)
    send(terminal, keys=["Enter"])
    time.sleep(.5)
    rest = leftover(terminal, text)
    if rest == text:
        # Only the whole command is retried: Enter on a fragment would send it to the agent.
        send(terminal, keys=["Enter"])
        time.sleep(.6)
        rest = leftover(terminal, text)
    if rest:
        send(terminal, keys=["BSpace"] * (len(rest) + 1))
        return False
    return True


def toggle_fast(terminal, desired):
    if not command(terminal, "/fast"):
        return False
    state = wait_ui(terminal, lambda value: bool(value["telemetry"]) and value["telemetry"]["fast"] == desired)
    return bool(state["telemetry"]) and state["telemetry"]["fast"] == desired


def live_setting(terminal, args):
    row = {key: terminal[key] for key in ("backend", "user", "pane")}
    row["profile"] = terminal.get("profile")
    row["activity_hint"] = terminal.get("state")
    chosen = pane_target(terminal, args)
    state = ui_state(screen(terminal))
    info = state["telemetry"]
    row["observed"] = state["footer"]
    row["telemetry"] = info
    row["activity"] = "working" if state["busy"] or terminal.get("state") == "working" else ("draft" if not state["empty_composer"] else "idle")
    if chosen is None:
        # A pinned account may be running here and its pane cannot name it.
        return dict(row, status="held_profile_unknown")
    args = dict(args, model=chosen["model"], effort=chosen["effort"])
    row["target"] = {"model": chosen["model"], "effort": chosen["effort"], "tier": chosen.get("tier")}
    target = (args["model"], args["effort"])
    fast = wants_fast(chosen)
    fast_ok = fast is None or (info is not None and info["fast"] == fast)
    if state["footer"] == target and fast_ok:
        return dict(row, status="verified")
    # Never turn UP a session that spends paid credits (or has no plan quota left): that is the user's money.
    guard = args.get("credit_guard") or {}
    if guard.get("enabled", True) and is_up(chosen, args.get("baseline")) and \
            (on_credits(info, guard.get("floor", 0.0)) or terminal.get("profile") in set(args.get("credit_profiles") or [])):
        # It is moved to an account with quota (rehome) and only then follows the boost.
        return dict(row, status="move_suggested" if args.get("rehome") else "held_credits")
    if not args["live"] or not args["apply"]:
        return dict(row, status="live_mismatch" if state["footer"] else "live_unknown")
    if state["footer"] == target and not fast_ok:
        if state["modal"] or not state["empty_composer"]:
            return dict(row, status="held_unrecognized_or_occupied_composer")
        if state["busy"] and not args["interrupt"]:
            return dict(row, status="held_working")
        if state["busy"]:
            send(terminal, keys=["C-c"])
            time.sleep(.5)
        ok = toggle_fast(terminal, fast)
        fresh = ui_state(screen(terminal))
        return dict(row, status="verified" if ok else "live_readback_unknown", observed=fresh["footer"], telemetry=fresh["telemetry"])
    if not state["modal"]:
        if not state["empty_composer"]:
            return dict(row, status="held_unrecognized_or_occupied_composer")
        if terminal.get("state") == "working" or state["busy"]:
            if not args["interrupt"]:
                return dict(row, status="held_working")
            send(terminal, keys=["C-c"])
            time.sleep(.5)
        zoomed = zoom(terminal)
        command(terminal, "/model")
        state = wait_ui(terminal, lambda value: bool(value["modal"]))
    else:
        zoomed = False
    opened = bool(state["modal"])
    try:
        if not opened:
            # Take back our own "/model" so the session is left exactly as we found it.
            rest = leftover(terminal, "/model")
            if rest:
                send(terminal, keys=["BSpace"] * (len(rest) + 1))
            return dict(row, status="held_picker_unavailable")
        normalize = lambda value: re.sub(r"[^a-z0-9]", "", value.lower())
        if "Select Model" in state["modal"]:
            choose(terminal, state["modal"], lambda label: normalize(label.split()[0]) == normalize(args["model"]))
            state = wait_ui(terminal, lambda value: "Reasoning" in value["modal"])
        if "Reasoning" not in state["modal"] or normalize(args["model"]) not in normalize(state["modal"].split("\n", 3)[0] + " ".join(state["modal"].splitlines()[1:3])):
            raise ValueError("reasoning picker does not identify the requested model")
        label = {"xhigh": "Extra high", "max": "Max", "ultra": "Ultra"}.get(args["effort"], args["effort"].capitalize())
        if not any(item[1].startswith(label) for item in menu_rows(state["modal"])):
            choose(terminal, state["modal"], lambda text: text.startswith("More reasoning"))
            state = wait_ui(terminal, lambda value: any(item[1].startswith(label) for item in menu_rows(value["modal"])))
        choose(terminal, state["modal"], lambda text: text.startswith(label))
        state = wait_ui(terminal, lambda value: value["footer"] == target)
        if state["footer"] == target and fast is not None and not (state["telemetry"] and state["telemetry"]["fast"] == fast):
            toggle_fast(terminal, fast)
            state = ui_state(screen(terminal))
        done = state["footer"] == target and (fast is None or bool(state["telemetry"]) and state["telemetry"]["fast"] == fast)
        return dict(row, status="verified" if done else "live_readback_unknown", observed=state["footer"], telemetry=state["telemetry"])
    finally:
        # Dismiss only recognized settings modals, never send Escape blindly to work.
        for _ in range(2):
            if not ui_state(screen(terminal))["modal"]:
                break
            send(terminal, keys=["Escape"])
            time.sleep(.15)
        if zoomed:
            execute(["tmux", "-S", terminal["socket"], "resize-pane", "-Z", "-t", terminal["pane"]], terminal["user"])


def zoom(terminal, rows=16):
    """Zoom a tmux pane too short to show the model picker; True when we zoomed it (caller unzooms)."""
    if terminal["backend"] != "tmux":
        return False
    try:
        height, zoomed = execute(["tmux", "-S", terminal["socket"], "display-message", "-p", "-t", terminal["pane"],
                                  "#{pane_height} #{window_zoomed_flag}"], terminal["user"]).split()
        if int(height) >= rows or zoomed == "1":
            return False
        execute(["tmux", "-S", terminal["socket"], "resize-pane", "-Z", "-t", terminal["pane"]], terminal["user"])
        time.sleep(.4)
        return True
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError):
        return False


# ---------------------------------------------------------------- rehome: move a session to another account

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
BYPASS_FLAGS = ("--dangerously-bypass-approvals-and-sandbox", "--yolo")
SHELL_RE = re.compile(r"/?[A-Za-z0-9._/-]+")


def thread_from(argv, fd_targets=()):
    """The Codex thread a process runs: the id after `resume` in its argv, else the id in the
    file NAME of its open rollout-*.jsonl. File contents are never read (they are transcripts)."""
    if "resume" in argv:
        for arg in argv[argv.index("resume") + 1:]:
            if UUID_RE.fullmatch(arg):
                return arg.lower()
    for target in fd_targets:
        name = os.path.basename(str(target))
        if name.startswith("rollout-") and name.endswith(".jsonl"):
            found = UUID_RE.findall(name)
            if found:
                return found[-1].lower()
    return None


def home_profile(codex_home):
    """The profile a CODEX_HOME belongs to, in folder (safe) spelling."""
    match = re.search(r"/orch-homes/codex-([^/]+)/\.codex/?$", codex_home or "")
    return safe_profile(match[1]) if match else None


def codex_facts(pid):
    """Thread, folder, account and bypass flag of one Codex process (Linux /proc only).

    Reads argv, cwd, CODEX_HOME and fd link NAMES; argv is never returned (it may hold a prompt).
    Descendant processes are searched for the rollout file when the process itself has none."""
    ps = processes()
    family = [pid] + [child for child in ps if child != pid and descends(child, pid, ps)]
    proc = Path("/proc") / str(pid)
    argv = [part.decode(errors="replace") for part in proc.joinpath("cmdline").read_bytes().split(b"\0") if part]
    targets = []
    for member in family:
        try:
            for fd in (Path("/proc") / str(member) / "fd").iterdir():
                try:
                    targets.append(os.readlink(fd))
                except OSError:
                    continue
        except OSError:
            continue
    home = None
    for entry in proc.joinpath("environ").read_bytes().split(b"\0"):
        if entry.startswith(b"CODEX_HOME="):
            home = entry[11:].decode(errors="replace")
    return {"thread": thread_from(argv, targets), "cwd": os.readlink(proc / "cwd"), "profile": home_profile(home),
            "bypass": next((flag for flag in BYPASS_FLAGS if flag in argv), None)}


def proc_available():
    return Path("/proc").is_dir()


def descends(pid, ancestor, ps):
    seen = set()
    while pid in ps and pid not in seen:
        if pid == ancestor:
            return True
        seen.add(pid)
        pid = ps[pid][0]
    return False


def launch_command(settings, profile, thread, bypass=None, shell=None):
    """The pane command that resumes THREAD on PROFILE, from the configured template.

    `rehome.launch` holds `{profile}` and `{thread}`, e.g. "codex {profile} resume {thread}".
    PROFILE must be the account manager's own name (a folder spelling starts a new, empty session)."""
    template = settings.get("launch") or ""
    if "{profile}" not in template or "{thread}" not in template:
        raise ValueError("rehome.launch must contain {profile} and {thread}")
    if not PROFILE_RE.fullmatch(profile or "") or not UUID_RE.fullmatch(thread or ""):
        raise ValueError("refusing to launch: unsafe profile or thread id")
    shell = settings.get("shell") or shell or "/bin/bash"
    if not SHELL_RE.fullmatch(shell):
        raise ValueError("rehome.shell must be a plain shell path")
    inner = template.replace("{profile}", shlex.quote(profile)).replace("{thread}", shlex.quote(thread))
    if bypass in BYPASS_FLAGS:
        inner += " " + bypass
    return shell + " -lic " + shlex.quote(inner + "; exec " + shell + " -l")


def resume_state(text, probe=False):
    """ok / failed / trust (a folder-trust prompt to accept) / None (still starting).

    A probe opened beside the running original sees "open in another app": that proves the
    thread resumes. Broken history lineage shows a resume failure; such threads stay put."""
    if re.search(r"thread/resume failed|missing source rollout|No saved session", text, re.I):
        return "failed"
    if re.search(r"Trust this folder|Do you trust", text):
        return "trust"
    if probe and "open in another app" in text:
        return "ok"
    if re.search(r"GPT-[A-Za-z0-9.\-]+ [a-z]", "\n".join(text.splitlines()[-6:])):
        return "ok"
    return None


def goal_state(text):
    """'active' / 'paused' / None from the Codex footer (last lines only)."""
    tail = "\n".join(text.splitlines()[-8:])
    if re.search(r"Goal paused|Goal hit usage limits|/goal resume", tail):
        return "paused"
    if "Pursuing goal" in tail:
        return "active"
    return None


def boot(terminal, seconds, probe=False):
    """Wait for a resumed Codex to come up; accepts a folder-trust prompt. Returns ok, failed or timeout."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        time.sleep(1)
        try:
            verdict = resume_state(screen(terminal), probe)
        except RuntimeError:
            continue
        if verdict == "trust":
            send(terminal, keys=["Enter"])
        elif verdict:
            return verdict
    return "timeout"


def pane_account(terminal):
    """Which account the Codex now running in a tmux pane uses (folder spelling), or None."""
    root = int(execute(["tmux", "-S", terminal["socket"], "display-message", "-p", "-t", terminal["pane"], "#{pane_pid}"], terminal["user"]).strip())
    ps = processes()
    for pid, (_, name) in ps.items():
        if (name == "codex" or name.endswith("/codex")) and descends(pid, root, ps):
            try:
                facts = codex_facts(pid)
            except OSError:
                continue
            if facts["profile"]:
                return facts["profile"], facts["thread"]
    return None, None


def move_session(terminal, move, settings):
    """Move one live Codex session to another account, keeping its pane, folder and conversation.

    Verify first: the new launch is proven in a hidden window while the original keeps running;
    a thread that does not resume there is left untouched. Busy sessions and drafts are held
    (a busy one is interrupted only with `interrupt`). The pane is respawned in place, a goal
    that was running is resumed, and the account is read back from the new process."""
    to = move["to"]
    row = {"backend": terminal["backend"], "pane": terminal["pane"], "from": terminal.get("profile"), "to": to}
    if terminal["backend"] != "tmux" or not terminal.get("pid") or not proc_available():
        return dict(row, status="move_manual", detail="automatic moves need a tmux pane on a Linux host")
    if not PROFILE_RE.fullmatch(to or ""):
        return dict(row, status="move_refused", detail="destination is not a profile name")
    if terminal.get("profile") == safe_profile(to):
        return dict(row, status="move_same_account")
    facts = codex_facts(terminal["pid"])
    if not facts["thread"]:
        return dict(row, status="move_no_thread", detail="no resumable thread id found")
    row["thread"] = facts["thread"][:8]
    user_shell = None
    try:
        user_shell = pwd.getpwnam(terminal["user"]).pw_shell
    except KeyError:
        pass
    launch = launch_command(settings, to, facts["thread"], facts["bypass"], user_shell)
    text = screen(terminal)
    state = ui_state(text)
    goal = goal_state(text)
    if state["modal"] or not state["empty_composer"]:
        return dict(row, status="move_held_draft")
    if state["busy"] and not move.get("interrupt"):
        return dict(row, status="move_held_working")
    seconds = float(settings.get("boot_seconds") or 45)
    tmux = ["tmux", "-S", terminal["socket"]]
    session = execute(tmux + ["display-message", "-p", "-t", terminal["pane"], "#{session_name}"], terminal["user"]).strip()
    probe = execute(tmux + ["new-window", "-d", "-P", "-F", "#{pane_id}", "-t", session + ":", "-c", facts["cwd"], launch], terminal["user"]).strip()
    try:
        verdict = boot(dict(terminal, pane=probe), seconds, probe=True)
    finally:
        # Leave the probe's thread untouched: stop it as a user would, then close the window.
        for key, pause in (("C-c", .4), ("C-c", 1.5)):
            try:
                send(dict(terminal, pane=probe), keys=[key])
            except RuntimeError:
                break
            time.sleep(pause)
        try:
            execute(tmux + ["kill-pane", "-t", probe], terminal["user"])
        except RuntimeError:
            pass
    if verdict != "ok":
        return dict(row, status="move_not_resumable", detail="resume on " + to + " " + verdict + "; original untouched")
    # The session may have started work while the probe ran: check again right before the swap.
    text = screen(terminal)
    state = ui_state(text)
    goal = goal or goal_state(text)
    if state["modal"] or not state["empty_composer"]:
        return dict(row, status="move_held_draft")
    if state["busy"]:
        if not move.get("interrupt"):
            return dict(row, status="move_held_working")
        send(terminal, keys=["C-c"])
        time.sleep(3)
        if not ui_state(screen(terminal))["empty_composer"]:
            return dict(row, status="move_held_draft", detail="interrupted; the composer is not empty")
    execute(tmux + ["respawn-pane", "-k", "-t", terminal["pane"], "-c", facts["cwd"], launch], terminal["user"])
    verdict = boot(terminal, seconds)
    row["goal_resumed"] = False
    if verdict == "ok" and goal and goal_state(screen(terminal)) == "paused":
        row["goal_resumed"] = command(terminal, "/goal resume")
    now_profile, now_thread = pane_account(terminal)
    moved = verdict == "ok" and now_profile == safe_profile(to) and now_thread in (None, facts["thread"])
    return dict(row, status="moved" if moved else "move_unverified", observed_profile=now_profile, boot=verdict)


def run_moves(config, moves, settings, progress=None):
    """Move sessions: moves = {host: [{"pane", "to", "interrupt"}]}. Returns {host: [row]}."""
    progress = progress or (lambda host, event: None)
    source = Path(__file__).resolve().read_text()

    def one(name):
        host, items = config["hosts"][name], moves[name]
        progress(name, {"stage": "start"})
        if host["type"] == "windows":
            rows = [dict(item, status="move_manual", detail="Windows hosts are moved by hand") for item in items]
        else:
            args = {"moves": items, "rehome": settings, "target": {}, "timeout": 120 + 150 * len(items)}
            try:
                rows = run_host(name, host, args, source, lambda event: progress(name, event)).get("moves") or []
            except Exception as error:
                message = f"unreachable: timed out after {error.timeout:.0f}s" if isinstance(error, subprocess.TimeoutExpired) else str(error)[:300]
                rows = [dict(item, status="move_error", error=message) for item in items]
        progress(name, {"stage": "done", "summary": {"moves": len(rows), "moved": sum(row.get("status") == "moved" for row in rows)}})
        return rows

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(moves))) as pool:
        return dict(zip(moves, pool.map(one, list(moves))))


PROGRESS_PREFIX = "RESET-BOOST-PROGRESS "


def stderr_emit(event):
    # Remote workers stream progress on stderr; stdout carries only the final JSON.
    sys.stderr.write(PROGRESS_PREFIX + json.dumps(event) + "\n")
    sys.stderr.flush()


def worker(args, emit=None):
    """One host's pass. `only_panes` limits it to those live panes and skips launch configs."""
    emit = emit or (stderr_emit if args.get("stream") else (lambda event: None))
    only = set(args.get("only_panes") or [])
    observe = bool(args.get("observe"))
    result = {"configs": [], "terminals": [], "launch_overrides": [], "process_launch_readback": "readable", "errors": [],
              "desktop_task_overrides": "unverified: no supported desktop model-control API"}
    if tomllib is None:
        result["errors"].append({"backend": "python", "error": "Python 3.11+ (tomllib) is required on this host; nothing was read or changed"})
        return result
    if args.get("moves"):
        # Rehome: move the named sessions to other accounts; nothing else is touched.
        result["moves"] = []
        found, issues = terminals()
        result["errors"] += issues
        by_pane = {terminal["pane"]: terminal for terminal in found}
        for move in args["moves"]:
            terminal = by_pane.get(move.get("pane"))
            try:
                row = move_session(terminal, move, args.get("rehome") or {}) if terminal else \
                    {"pane": move.get("pane"), "to": move.get("to"), "status": "move_pane_gone", "detail": "no Codex session in that pane now"}
            except Exception as error:
                row = {"pane": move.get("pane"), "to": move.get("to"), "status": "move_error", "error": type(error).__name__ + ": " + str(error)[:200]}
            result["moves"].append(row)
            emit({"stage": "move", "row": row})
        return result
    if not only and not observe:
        for path, kind in sorted(config_paths(args.get("profiles") or {}, args.get("project_roots") or ()).items()):
            try:
                result["configs"].append(change_file(path, kind, args))
            except Exception as error:
                result["errors"].append({"path": str(path), "error": type(error).__name__ + ": " + str(error)})
        statuses = [row["status"] for row in result["configs"]]
        emit({"stage": "configs", "count": len(statuses), "changed": statuses.count("changed"), "pending": statuses.count("would_change"),
              "errors": len(result["errors"])})
    found, issues = terminals()
    result["errors"] += issues
    if only:
        found = [terminal for terminal in found if terminal["pane"] in only]
    elif not observe:
        try:
            result["launch_overrides"] = launch_overrides(args["model"], args["effort"])
            if result["launch_overrides"] is None:
                result["launch_overrides"] = []
                result["process_launch_readback"] = "unknown: process arguments hidden by host policy"
        except Exception as error:
            result["errors"].append({"backend": "process", "error": type(error).__name__ + ": " + str(error)})
    emit({"stage": "panes", "count": len(found)})
    for terminal in found:
        try:
            row = live_setting(terminal, args)
        except Exception as error:
            row = {"backend": terminal["backend"], "pane": terminal["pane"], "profile": terminal.get("profile"), "status": "error", "error": str(error)}
        result["terminals"].append(row)
        emit({"stage": "pane", "row": row})
    return result


def windows_worker(args, alias):
    # Config only: Windows terminals are not enumerated or switched.
    # PowerShell receives encoded code and data, not shell-interpolated values.
    payload = base64.b64encode(json.dumps(args).encode()).decode()
    script = r'''
$a = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('PAYLOAD')) | ConvertFrom-Json
$p = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex\config.toml'
$rows = @(); $errors = @()
if (Test-Path $p) {
 $old = [IO.File]::ReadAllText($p)
 $new = [regex]::Replace($old, '(?m)^model\s*=.*$', ('model = "' + $a.model + '"'))
 $new = [regex]::Replace($new, '(?m)^model_reasoning_effort\s*=.*$', ('model_reasoning_effort = "' + $a.effort + '"'))
 if ($old -notmatch '(?m)^model\s*=') { $new = 'model = "' + $a.model + '"' + "`n" + $new }
 if ($old -notmatch '(?m)^model_reasoning_effort\s*=') { $new = 'model_reasoning_effort = "' + $a.effort + '"' + "`n" + $new }
 if ($a.tier) {
  $new = [regex]::Replace($new, '(?m)^service_tier\s*=.*$', ('service_tier = "' + $a.tier + '"'))
  if ($old -notmatch '(?m)^service_tier\s*=') { $new = 'service_tier = "' + $a.tier + '"' + "`n" + $new }
 }
 $status = 'matches'; $backup = $null
 if ($new -cne $old) {
  $status = 'would_change'
  if ($a.apply) {
   $backup = $p + '.reset-boost-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ')
   Copy-Item $p $backup
   [IO.File]::WriteAllText($p, $new)
   if ([IO.File]::ReadAllText($p) -cne $new) { throw 'Windows config readback failed' }
   $status = 'changed'
  }
 }
 $rows += @{ path=$p; kind='codex'; status=$status; backup=$backup }
} else { $errors += @{error='Windows Codex config absent'} }
@{ configs=$rows; terminals=@(); errors=$errors; desktop_task_overrides='unverified: no supported desktop model-control API' } | ConvertTo-Json -Depth 8 -Compress
'''.replace("PAYLOAD", payload)
    encoded = base64.b64encode(script.encode("utf-16le")).decode()
    return json.loads(execute(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", alias, "powershell -NoProfile -EncodedCommand " + encoded], timeout=40))


def run_host(name, host, args, source, emit=None):
    emit = emit or (lambda event: None)
    kind = host["type"]
    args = dict(args, project_roots=host.get("project_roots", []))
    if kind == "local":
        return worker(args, emit)
    alias = host.get("ssh", name)
    if kind == "windows":
        if args.get("only_panes"):
            return {"configs": [], "terminals": [], "errors": [], "launch_overrides": []}
        return windows_worker(dict(args, model=args["target"]["model"], effort=args["target"]["effort"], tier=args["target"].get("tier")), alias)
    # This exact source runs remotely; no dependency install or stale helper cache.
    encoded = base64.b64encode(json.dumps(dict(args, stream=True)).encode()).decode()
    command = ("sudo -n " if host.get("sudo", False) else "") + "python3 - --worker " + shlex.quote(encoded)
    process = subprocess.Popen(spawnable(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", alias, command]), close_fds=False,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def feed():
        try:
            process.stdin.write(source)
            process.stdin.close()
        except OSError:
            pass

    def drain():
        for line in process.stderr:
            if line.startswith(PROGRESS_PREFIX):
                try:
                    emit(json.loads(line[len(PROGRESS_PREFIX):]))
                except ValueError:
                    pass

    threads = [threading.Thread(target=feed, daemon=True), threading.Thread(target=drain, daemon=True)]
    for thread in threads:
        thread.start()
    output = []
    reader = threading.Thread(target=lambda: output.append(process.stdout.read()), daemon=True)
    reader.start()
    limit = args.get("timeout", 300)
    reader.join(limit)
    if reader.is_alive():
        process.kill()
        raise subprocess.TimeoutExpired(alias, limit)
    process.wait(10)
    threads[1].join(5)
    if process.returncode:
        raise RuntimeError("remote worker failed (exit " + str(process.returncode) + ")")
    return json.loads(output[0])


def run_fleet(config, hosts, target, apply=False, live=False, interrupt=False, profiles=None, hold_unknown=False, quiet=False, label=None,
              progress=None, only_panes=None, save=True, pane_targets=None, observe=False, baseline=None, credit_guard=None, credit_profiles=None,
              rehome=False):
    """Apply or audit one target (plus per-profile targets) on every host in parallel; returns the saved report.

    progress(host, event) receives live events: start, configs, panes, pane (one per session), done, error.
    """
    progress = progress or (lambda host, event: None)
    args = {"target": target, "model": target["model"], "effort": target["effort"], "profiles": profiles or {},
            "apply": apply, "live": live, "interrupt": interrupt, "hold_unknown": hold_unknown, "observe": observe,
            "baseline": baseline, "credit_guard": credit_guard or {}, "credit_profiles": sorted(credit_profiles or []),
            "rehome": bool(rehome)}

    def host_args(name):
        # only_panes / pane_targets may be keyed by host: pane ids repeat across hosts.
        panes = only_panes.get(name, []) if isinstance(only_panes, dict) else (only_panes or [])
        return dict(args, only_panes=panes, pane_targets=(pane_targets or {}).get(name, {}))
    source = Path(__file__).resolve().read_text()
    report = {"created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "label": label, "model": target["model"], "effort": target["effort"],
              "tier": target.get("tier"), "profiles": profiles or {}, "apply": apply, "live": live, "source_sha256": digest(source), "hosts": {}}

    def one(name):
        progress(name, {"stage": "start"})
        try:
            if isinstance(only_panes, dict) and not only_panes.get(name):
                value = {"configs": [], "terminals": [], "errors": [], "launch_overrides": [], "skipped": True}
            else:
                value = run_host(name, config["hosts"][name], host_args(name), source, lambda event: progress(name, event))
        except Exception as error:
            # Never echo the command: it carries the encoded worker payload.
            message = f"unreachable: timed out after {error.timeout:.0f}s" if isinstance(error, subprocess.TimeoutExpired) else str(error)[:300]
            value = {"errors": [{"error": message}], "configs": [], "terminals": [], "launch_overrides": [], "process_launch_readback": "unknown"}
            progress(name, {"stage": "error", "error": message})
        progress(name, {"stage": "done", "summary": host_summary(value)})
        return value

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, len(hosts))) as pool:
        results = dict(zip(hosts, pool.map(one, hosts)))
    for name in hosts:
        report["hosts"][name] = value = results[name]
        if not quiet:
            summary = host_summary(value)
            print(f"{name:8} configs {summary['configs']:3}  changes {summary['changed'] or summary['pending']:3}  live verified {summary['verified']:3}/{summary['live']:3}  launch mismatches {summary['launch_mismatches']:2}  errors {summary['errors']}", flush=True)
    if not save:
        return report
    directory = state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + ".json")
    path.write_text(json.dumps(report, indent=2) + "\n")
    report["_path"] = str(path)
    return report


def host_summary(value):
    statuses = [row["status"] for row in value.get("configs", [])]
    live = [row["status"] for row in value.get("terminals", [])]
    return {"configs": len(statuses), "changed": statuses.count("changed"), "pending": statuses.count("would_change"),
            "live": len(live), "verified": live.count("verified"), "held": sum(status.startswith("held") for status in live),
            "launch_mismatches": sum(row.get("status") == "explicit-mismatch" for row in value.get("launch_overrides", []) or []),
            "errors": len(value.get("errors", []))}


def report_exit(report):
    hosts = report["hosts"].values()
    errors = any(value["errors"] for value in hosts)
    gaps = any(row["status"] != "verified" for value in hosts for row in value["terminals"])
    config_gaps = any(row["status"] == "would_change" for value in hosts for row in value["configs"])
    launch_gaps = any(row["status"] == "explicit-mismatch" for value in hosts for row in value.get("launch_overrides", []))
    return 1 if errors else 2 if gaps or config_gaps or launch_gaps else 0


BOOST_COMMANDS = ("boost", "done", "watch", "status", "dashboard", "serve", "converge", "channel", "rules", "pane", "signals", "agent", "session", "observe",
                  "move", "rehome")


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        print(json.dumps(worker(json.loads(base64.b64decode(sys.argv[2])))))
        return 0
    if len(sys.argv) > 1 and sys.argv[1] in BOOST_COMMANDS:
        # The boost lifecycle runs only on the controlling machine; workers never import it.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import boost_lifecycle
        return boost_lifecycle.main(sys.argv[1:], sys.modules[__name__])
    if len(sys.argv) > 1 and sys.argv[1] == "--version":
        print("reset-boost " + VERSION)
        return 0
    config = load_config()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("audit", "set", "presets"))
    parser.add_argument("model", nargs="?", default=None, help="alias or an exact provider model ID")
    parser.add_argument("effort", nargs="?", choices=EFFORTS, default=None)
    parser.add_argument("--preset", help="named policy from presets.json")
    parser.add_argument("--tier", choices=TIERS + tuple(TIER_ALIASES), help="fast (= priority) or default; omitted leaves it unless the preset sets one")
    parser.add_argument("--hosts", default=",".join(config["hosts"]), help="comma-separated host names from " + config["_path"])
    parser.add_argument("--apply", action="store_true", help="write defaults with backups; otherwise preview")
    parser.add_argument("--live", action="store_true", help="also change idle, empty-composer Codex terminals through /model")
    parser.add_argument("--interrupt-current-turn", action="store_true", help="allow cancellation before a live switch; never restart a session")
    parser.add_argument("--json", action="store_true", help="print report JSON")
    options = parser.parse_args()
    if options.command == "presets":
        if options.preset or options.model or options.effort or options.apply or options.live or options.interrupt_current_turn or options.tier:
            parser.error("presets is read-only and takes no target")
        catalog = presets()
        if options.json:
            print(json.dumps(catalog, indent=2))
        else:
            for name, value in catalog.items():
                print(f"{name:17} {value['model']:14} {value['effort']:7} {value.get('tier', 'default'):9} {value.get('description', '')}")
        return 0
    try:
        target = resolve_target(options.model, options.effort, options.preset, options.tier)
    except ValueError as error:
        parser.error(str(error))
    if not MODEL_ID_RE.fullmatch(target["model"]):
        parser.error("model must contain only safe provider ID characters")
    targets = [host for host in options.hosts.split(",") if host]
    if any(host not in config["hosts"] for host in targets) or len(set(targets)) != len(targets):
        parser.error("--hosts must contain unique names from " + ",".join(config["hosts"]))
    if options.command == "audit" and (options.apply or options.live or options.interrupt_current_turn or options.preset):
        parser.error("audit is read-only; use set for changes")
    if options.interrupt_current_turn and not (options.apply and options.live):
        parser.error("--interrupt-current-turn requires --apply --live")
    report = run_fleet(config, targets, target, apply=options.apply, live=options.live, interrupt=options.interrupt_current_turn,
                       quiet=options.json, label=options.command + (" --preset " + options.preset if options.preset else ""))
    if options.json:
        print(json.dumps(report, indent=2))
    else:
        print("Report: " + report["_path"])
        print("Desktop task overrides remain unverified; no inference test turns or session restarts.")
    return report_exit(report)


if __name__ == "__main__":
    raise SystemExit(main())
