"""Signals and autopilot: telemetry becomes signals, signals become agent briefs.

The human works the control panel; anything a button could not fix shows up as a
signal (a held or failed session, an unreachable host, a session still boosted
after `done`, a dead usage feed). In `suggest` mode each signal offers "send to
agent"; in `auto` mode a signal that persists past `after_minutes` is handed to a
headless agent (Claude Code, Codex, or any command) with a brief that carries the
evidence, the allowed reset_boost.py commands and the safety rules. Runs are rate
limited, recorded in agent-runs.json, and their final message comes back to the UI.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading

SEVERITY = {"bad": 0, "warn": 1, "info": 2}
TITLES = {
    "HOST_UNREACHABLE": "Host unreachable", "CONFIG_ERROR": "Config could not be changed", "CONFIG_PENDING": "Launch configs not at target",
    "STILL_BOOSTED": "Session still boosted after turn-down", "PANE_SWITCH_FAILED": "Session switch failed", "PANE_BUSY": "Session busy, waiting to switch",
    "PANE_DRAFT": "Session has a draft in its composer", "PANE_ACCOUNT_UNKNOWN": "Session account unknown", "USAGE_DOWN": "Usage feed unavailable",
    "DRIFT": "Sessions differ from baseline",
}
DEFAULT_AUTOPILOT = {"mode": "suggest", "after_minutes": 10, "max_per_hour": 3, "allow_interrupt": False,
                     "codes": ["STILL_BOOSTED", "PANE_SWITCH_FAILED", "HOST_UNREACHABLE", "CONFIG_ERROR", "USAGE_DOWN"]}
CLI = Path(__file__).resolve().with_name("reset_boost.py")
_runs_lock = threading.Lock()


def now():
    return dt.datetime.now(dt.timezone.utc)


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def parse(value):
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None
    except ValueError:
        return None


def signal_id(code, host, subject):
    return hashlib.sha1(f"{code}|{host}|{subject}".encode()).hexdigest()[:10]


def signals(state, report, usage_error=None):
    """Derive actionable signals from the latest run; ordered worst first."""
    items = []
    phase = state.get("phase", "idle")
    boost_model = ((state.get("boost_target") or {}).get("model") or "").lower()
    base_model = ((state.get("baseline_target") or {}).get("model") or "").lower()

    def add(code, severity, host, subject, detail, actions, evidence=None):
        items.append({"id": signal_id(code, host, subject), "code": code, "title": TITLES[code], "severity": severity, "host": host,
                      "subject": subject, "detail": detail, "actions": actions, "evidence": evidence or {}})

    for host, value in ((report or {}).get("hosts") or {}).items():
        errors = value.get("errors") or []
        if errors and not value.get("configs") and not value.get("terminals"):
            add("HOST_UNREACHABLE", "bad", host, "host", errors[0].get("error", "error"), ["retry_host", "agent"], {"errors": errors})
            continue
        for error in errors:
            add("CONFIG_ERROR", "bad", host, error.get("path") or error.get("backend") or "host", error.get("error", ""), ["retry_host", "agent"], error)
        pending = [row for row in value.get("configs") or [] if row["status"] == "would_change"]
        if pending and phase != "idle":
            add("CONFIG_PENDING", "warn", host, "configs", f"{len(pending)} launch configs not at target", ["retry_host", "agent"],
                {"paths": [row["path"] for row in pending[:20]]})
        drift = []
        for row in value.get("terminals") or []:
            status = row.get("status")
            if status == "verified":
                continue
            observed = row.get("observed") or []
            footer = " ".join(observed) if observed else "unreadable footer"
            subject = f"{row.get('backend')} {row.get('pane')}"
            who = row.get("profile") or "unknown account"
            if phase == "idle" and status in ("live_mismatch", "live_unknown"):
                drift.append(row)
                continue
            if phase != "boosted" and observed and boost_model and observed[0].lower() == boost_model and boost_model != base_model:
                add("STILL_BOOSTED", "bad", host, subject, f"{who}: footer {footer}", ["retry_pane", "interrupt_pane", "agent"], row)
            elif status == "held_working":
                add("PANE_BUSY", "info", host, subject, f"{who}: busy at {footer}; switches when idle", ["retry_pane", "interrupt_pane", "agent"], row)
            elif status == "held_unrecognized_or_occupied_composer":
                add("PANE_DRAFT", "warn", host, subject, f"{who}: unsent text in the composer, left alone ({footer})", ["retry_pane", "agent"], row)
            elif status == "held_profile_unknown":
                add("PANE_ACCOUNT_UNKNOWN", "warn", host, subject, f"cannot tell which account runs here ({footer}); held while pins are active", ["agent"], row)
            else:
                add("PANE_SWITCH_FAILED", "bad", host, subject, f"{who}: {status} ({footer}) {row.get('error') or ''}".strip(), ["retry_pane", "agent"], row)
        if drift:
            footers = sorted({" ".join(row.get("observed") or []) or "unreadable" for row in drift})
            add("DRIFT", "info", host, "sessions", f"{len(drift)} sessions differ from the baseline: {', '.join(footers[:4])}", ["agent"],
                {"panes": [row.get("pane") for row in drift]})
    if usage_error and phase == "boosted":
        add("USAGE_DOWN", "warn", "usage", "feed", "reset detection paused: " + usage_error, ["agent"])
    items.sort(key=lambda item: (SEVERITY[item["severity"]], item["host"], item["subject"]))
    return items


def track(store, items):
    """Remember when each signal was first seen (own file) so age and autopilot timing survive restarts."""
    path = store.dir / "signals-seen.json"
    with _runs_lock:
        try:
            seen = json.loads(path.read_text())
        except (OSError, ValueError):
            seen = {}
        current = {item["id"] for item in items}
        fresh = {key: value for key, value in seen.items() if key in current}
        for item in items:
            fresh.setdefault(item["id"], iso(now()))
            item["first_seen"] = fresh[item["id"]]
        if fresh != seen:
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(fresh))
            os.replace(temporary, path)
    return items


def settings(state, config):
    value = dict(DEFAULT_AUTOPILOT, **((config.get("agent") or {}).get("autopilot") or {}))
    value.update(state.get("autopilot") or {})
    value["configured"] = bool((config.get("agent") or {}).get("steps"))
    return value


# ---------------------------------------------------------------- runs


def runs_path(store):
    return store.dir / "agent-runs.json"


def load_runs(store):
    try:
        return json.loads(runs_path(store).read_text())
    except (OSError, ValueError):
        return []


def save_runs(store, runs):
    path = runs_path(store)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(runs[-40:], indent=2) + "\n")
    os.replace(temporary, path)


def update_run(store, name, **changes):
    with _runs_lock:
        runs = load_runs(store)
        for run in runs:
            if run["name"] == name:
                run.update(changes)
        save_runs(store, runs)


def due(state, config, items, runs):
    """Signals the autopilot should hand over now."""
    rules = settings(state, config)
    if rules["mode"] != "auto" or not rules["configured"]:
        return []
    hour_ago = now() - dt.timedelta(hours=1)
    recent = [run for run in runs if (parse(run.get("started_at")) or hour_ago) > hour_ago]
    budget = rules["max_per_hour"] - len(recent)
    busy = {run.get("signal") for run in runs if run.get("status") == "running"}
    retried = {run.get("signal") for run in recent}
    picked = []
    for item in items:
        if budget <= 0:
            break
        age = now() - (parse(item.get("first_seen")) or now())
        if item["code"] in rules["codes"] and item["id"] not in busy and item["id"] not in retried and age >= dt.timedelta(minutes=rules["after_minutes"]):
            picked.append(item)
            budget -= 1
    return picked


def brief(state, config, signal=None, request=None, allow_interrupt=False):
    host, profiles, hold, label = None, {}, False, ""
    try:
        import boost_lifecycle
        host, profiles, hold, label = boost_lifecycle.plan(state)
    except Exception:
        pass
    lines = ["# Reset Boost control panel: agent task", "",
             "You are the back-end agent behind the Reset Boost control panel. A human operates the panel's buttons",
             "(boost, turn down, per-account channels); you handle what the buttons could not fix. Work through the",
             f"Reset Boost CLI (`python3 {CLI}`, written `reset_boost.py` below), which runs from this machine and reaches",
             "every host over SSH itself.", ""]
    if signal:
        lines += ["## Signal", "", "```json", json.dumps({key: signal[key] for key in ("id", "code", "title", "severity", "host", "subject", "detail", "first_seen") if key in signal}, indent=2),
                  "```", "", "Evidence (settings metadata only, no conversation text):", "", "```json", json.dumps(signal.get("evidence"), indent=2)[:6000], "```", ""]
    if request:
        lines += ["## Operator request", "", request.strip(), ""]
    lines += ["## Current plan", "",
              f"- Phase: {state.get('phase', 'idle')} ({label})",
              f"- Fleet target: {json.dumps(host)}",
              f"- Per-account targets: {json.dumps(profiles)}",
              f"- Pinned at baseline: {', '.join(sorted(name for name, value in profiles.items() if value == state.get('baseline_target'))) or '-'}; "
              f"baseline {json.dumps(state.get('baseline_target'))}",
              "", "## Commands you may use", "",
              "- `reset_boost.py signals --json` and `reset_boost.py status --json` to read state",
              "- `reset_boost.py pane HOST PANE` to retry one live session at its planned target",
              "- `reset_boost.py converge --hosts HOST` to re-apply the current plan on one host",
              "- `reset_boost.py channel PROFILE follow|pin` to change one account's channel",
              "- `reset_boost.py done` to turn everything down (always safe)",
              "- read-only inspection over `ssh HOST`: process lists, `tmux list-panes`, `herdr agent list`, config file metadata",
              ]
    if allow_interrupt:
        lines.append("- `reset_boost.py pane HOST PANE --interrupt` (cancels that session's current turn; allowed for this task)")
    lines += ["", "## Rules", "",
              "- Never read conversation transcripts or pane text beyond the model/settings footer the tool already reads.",
              "- Never restart sessions or kill processes; never change credentials, accounts, SSH, networking or file permissions.",
              "- Never turn anything UP (no boost, no new solo channel); you converge to the current plan or turn down.",
              "" if allow_interrupt else "- Do not interrupt a running turn.",
              "- If the fix needs a human, say exactly what and stop.", "",
              "## Finish with", "",
              "FOUND: what was wrong. CHANGED: what you did. VERIFIED: re-run `reset_boost.py signals --json` and say whether",
              "this signal is gone. NEEDS HUMAN: anything left, or 'nothing'."]
    return "\n".join(line for line in lines if line is not None)


def start(config, store, state, signal=None, request=None, wait=False, on_change=None):
    """Hand a signal or an operator request to the configured agent. Returns the run record."""
    agent = config.get("agent") or {}
    steps = agent.get("steps")
    if not steps:
        raise ValueError("no agent configured: add agent.steps to the reset-boost config")
    if not signal and not (request or "").strip():
        raise ValueError("give a signal or a request")
    rules = settings(state, config)
    stamp = now().strftime("%Y%m%dT%H%M%SZ")
    name = f"reset-boost-{(signal or {}).get('code', 'ask').replace('_', '-')}-{stamp}".lower()
    folder = store.dir / "agent"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (name + ".md")
    text = brief(state, config, signal, request, rules["allow_interrupt"])
    path.write_text(text)
    run = {"name": name, "signal": (signal or {}).get("id"), "code": (signal or {}).get("code"), "title": (signal or {}).get("title") or "Operator request",
           "subject": f"{signal['host']} {signal['subject']}" if signal else (request or "")[:120], "started_at": iso(now()), "status": "running",
           "brief": str(path), "result": None}
    with _runs_lock:
        runs = load_runs(store)
        runs.append(run)
        save_runs(store, runs)
    store.event("agent_started", name=name, code=run["code"], subject=run["subject"])

    def execute():
        output, status = "", "done"
        try:
            for step in steps:
                argv = [str(part).replace("{name}", name).replace("{brief}", str(path)) for part in step]
                stdin = None if any("{brief}" in str(part) for part in step) else text
                executable = argv[0] if os.path.isabs(argv[0]) else shutil.which(argv[0])
                if not executable:
                    raise FileNotFoundError(argv[0])
                # posix_spawn (absolute path, close_fds=False): fork from the threaded panel can hang on macOS.
                result = subprocess.run([executable] + argv[1:], close_fds=False, input=stdin, capture_output=True, text=True,
                                        timeout=int(agent.get("timeout_minutes", 60)) * 60)
                output = (result.stdout or "") + ("\n" + result.stderr if result.returncode and result.stderr else "")
                if result.returncode:
                    status = "failed"
                    break
        except Exception as error:  # A failed hand-off is reported, never retried blindly.
            status, output = "failed", type(error).__name__ + ": " + str(error)
        update_run(store, name, status=status, finished_at=iso(now()), result=output.strip()[-4000:])
        store.event("agent_finished", name=name, status=status, code=run["code"])
        if on_change:
            on_change()

    if wait:
        execute()
    else:
        threading.Thread(target=execute, daemon=True, name=name).start()
    return run
