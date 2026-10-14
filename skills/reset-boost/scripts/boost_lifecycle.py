"""Boost lifecycle: turn every account up for a provider reset window, then back down.

A boost records a usage snapshot, applies the boost target everywhere except
excluded profiles, and keeps converging idle sessions on each watch tick. It
ends on `done`, or automatically when the usage source shows the reset has
landed (usage fell or the window rolled over on enough accounts), when a
deadline passes, or per account when usage climbs past a ceiling. After the
end, watch keeps re-applying the baseline until every reachable live session
reads back at the baseline or the cooling period expires.
"""
import argparse
import contextlib
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

PHASES = ("idle", "boosted", "cooling")
DEFAULT_AUTO_DOWN = {"reset": True, "quorum": 0.5, "drop_points": 15.0, "ceiling": None, "until": None}
COOLING_HOURS = 12
IDLE_AUDIT_HOURS = 6


def now():
    return dt.datetime.now(dt.timezone.utc)


def iso(value):
    return value.isoformat().replace("+00:00", "Z") if value else None


def parse_time(value):
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_until(text, start):
    """'6h', '90m', '2d' or an ISO timestamp."""
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([mhd])", text or "")
    if match:
        unit = {"m": "minutes", "h": "hours", "d": "days"}[match[2]]
        return start + dt.timedelta(**{unit: float(match[1])})
    value = parse_time(text)
    if value is None:
        raise ValueError("--until takes 6h, 90m, 2d or an ISO timestamp")
    return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)


# ---------------------------------------------------------------- usage


def fetch_usage(config):
    """Return (accounts, error). The source is optional; without one, auto-down is time/manual only."""
    source = config.get("usage")
    if not source:
        return None, "no usage source configured"
    try:
        kind = source.get("type")
        if kind == "url":
            request = urllib.request.Request(source["url"], headers={"Accept": "application/json", "User-Agent": "reset-boost"})
            with urllib.request.urlopen(request, timeout=source.get("timeout", 30)) as response:
                raw = json.load(response)
        elif kind == "command":
            result = subprocess.run(source["argv"], capture_output=True, text=True, timeout=source.get("timeout", 60))
            if result.returncode:
                raise RuntimeError("usage command exit " + str(result.returncode))
            raw = json.loads(result.stdout)
        elif kind == "file":
            raw = json.loads(Path(source["path"]).expanduser().read_text())
        else:
            raise ValueError("usage.type must be url, command or file")
        return normalize_usage(raw, source.get("provider")), None
    except Exception as error:  # A failed read must never change models; it only pauses auto-down.
        return None, type(error).__name__ + ": " + str(error)[:200]


def normalize_usage(raw, provider=None):
    """Accept the generic {accounts:[{id, profile, windows:[{key, used_percent, resets_at}]}]} shape.

    A bare list of accounts is also accepted. Extra fields that some account
    managers emit (account_id, display_name, observed_by_profile, fleet_cells,
    usage_status, execution_status, enabled, plan) are read when present.
    """
    rows = raw if isinstance(raw, list) else raw.get("accounts", [])
    accounts = {}
    for row in rows:
        if provider and row.get("provider") and row["provider"] != provider:
            continue
        cells = row.get("fleet_cells") or []
        profile = row.get("profile") or row.get("observed_by_profile") or next((cell.get("profile") for cell in cells if cell.get("profile")), None)
        key = str(row.get("account_id") or row.get("id") or profile or row.get("display_name") or row.get("email"))
        disabled = row.get("enabled") is False or row.get("usage_status") == "policy_disabled" or row.get("execution_status") == "disabled"
        windows = {}
        for window in row.get("windows") or []:
            if window.get("key") and window.get("used_percent") is not None:
                windows[window["key"]] = {"used": float(window["used_percent"]), "resets_at": window.get("resets_at"),
                                          "seconds": window.get("window_seconds")}
        accounts[key] = {"id": key, "label": row.get("display_name") or row.get("email") or profile or key, "profile": profile,
                         "plan": row.get("plan"), "disabled": disabled, "status": row.get("usage_status"), "windows": windows}
    return accounts


def primary_window(account):
    """The weekly window when present, else the longest one: that is the window a reset refills."""
    windows = account.get("windows") or {}
    if "weekly" in windows:
        return "weekly", windows["weekly"]
    if not windows:
        return None, None
    key = max(windows, key=lambda name: windows[name].get("seconds") or 0)
    return key, windows[key]


def snapshot(accounts):
    result = {}
    for key, account in (accounts or {}).items():
        name, window = primary_window(account)
        result[key] = {"label": account["label"], "profile": account["profile"], "plan": account["plan"], "disabled": account["disabled"],
                       "window": name, "used": window["used"] if window else None, "resets_at": window["resets_at"] if window else None}
    return result


def reset_signal(before, current, drop_points):
    """Has this account's reset landed since the boost began? Returns a reason or None."""
    if not before or before.get("used") is None or not current:
        return None
    window = (current.get("windows") or {}).get(before["window"])
    if not window:
        return None
    old, new = parse_time(before.get("resets_at")), parse_time(window.get("resets_at"))
    if old and new and (new - old) > dt.timedelta(hours=1):
        return "window rolled over"
    if before["used"] - window["used"] >= drop_points:
        return f"usage fell {before['used']:.0f}% -> {window['used']:.0f}%"
    return None


def evaluate(state, accounts):
    """Decide auto-down actions. Returns (fleet_reason or None, {profile: reason} to back down, per-account rows)."""
    rules = state["auto_down"]
    excluded = set(state.get("exclude") or [])
    rows, landed, considered, backs = [], 0, 0, {}
    for key, before in (state.get("snapshot") or {}).items():
        current = (accounts or {}).get(key)
        signal = reset_signal(before, current, rules["drop_points"]) if current else None
        name, window = primary_window(current) if current else (None, None)
        counted = before.get("used") is not None and not before.get("disabled") and before.get("profile") not in excluded
        if counted:
            considered += 1
            landed += bool(signal)
        row = {"id": key, "label": before["label"], "profile": before["profile"], "plan": before["plan"], "before": before.get("used"),
               "now": window["used"] if window else None, "resets_at": window["resets_at"] if window else before.get("resets_at"),
               "reset": signal, "counted": counted, "excluded": before.get("profile") in excluded, "disabled": before.get("disabled")}
        ceiling = rules.get("ceiling")
        if ceiling is not None and counted and not signal and window and window["used"] >= ceiling and before.get("profile"):
            backs[before["profile"]] = f"usage {window['used']:.0f}% reached the {ceiling:.0f}% ceiling"
        rows.append(row)
    reason = None
    if rules.get("until") and now() >= parse_time(rules["until"]):
        reason = "boost deadline reached"
    elif rules.get("reset") and considered and landed / considered >= rules["quorum"]:
        reason = f"reset detected on {landed}/{considered} accounts"
    return reason, backs, rows


# ---------------------------------------------------------------- state


class Store:
    def __init__(self, fm):
        self.dir = fm.state_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / "boost.json"
        self.events_path = self.dir / "boost-events.jsonl"
        self.usage_path = self.dir / "usage-latest.json"

    def load(self):
        if self.state_path.exists():
            return json.loads(self.state_path.read_text())
        return {"phase": "idle"}

    def save(self, state):
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2) + "\n")
        os.replace(temporary, self.state_path)

    def event(self, kind, **detail):
        with self.events_path.open("a") as handle:
            handle.write(json.dumps({"at": iso(now()), "event": kind, **detail}) + "\n")

    def events(self, limit=200):
        if not self.events_path.exists():
            return []
        lines = self.events_path.read_text().splitlines()[-limit:]
        return [json.loads(line) for line in lines if line.strip()]

    @contextlib.contextmanager
    def lock(self, wait):
        handle = (self.dir / "boost.lock").open("w")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except BlockingIOError:
            handle.close()
            yield False
            return
        try:
            yield True
        finally:
            handle.close()


# ---------------------------------------------------------------- apply


def boost_plan(state):
    """Host target plus per-profile pins for excluded and backed-down accounts."""
    baseline = state["baseline_target"]
    pins = {profile: baseline for profile in list(state.get("exclude") or []) + list(state.get("backed_down") or {})}
    return state["boost_target"], pins, bool(pins)


def converge(fm, config, state, store, quiet=True):
    if state["phase"] == "boosted":
        target, pins, hold = boost_plan(state)
        label = "boost " + state["boost_name"]
    else:
        target, pins, hold = state["baseline_target"], {}, False
        label = "baseline " + state["baseline_name"]
    report = fm.run_fleet(config, state["hosts"], target, apply=True, live=state.get("live", True), interrupt=state.get("interrupt", False),
                          profiles=pins, hold_unknown=hold, quiet=quiet, label=label)
    state["last_report"], state["last_report_at"] = report["_path"], report["created_at"]
    state["last_exit"] = fm.report_exit(report)
    return report


def resolve(fm, options, config):
    target = fm.resolve_target(options.model, options.effort, options.preset, options.tier)
    if not fm.MODEL_ID_RE.fullmatch(target["model"]):
        raise ValueError("model must contain only safe provider ID characters")
    name = options.preset or f"{target['model']}/{target['effort']}" + (f"/{target['tier']}" if target.get("tier") else "")
    return name, target


def baseline(fm, config):
    name = config.get("baseline", "normal")
    return name, fm.resolve_target(None, None, name)


def hosts_option(options, config):
    hosts = options.hosts.split(",") if options.hosts else list(config["hosts"])
    unknown = [host for host in hosts if host not in config["hosts"]]
    if unknown or len(set(hosts)) != len(hosts):
        raise ValueError("--hosts must contain unique names from " + ",".join(config["hosts"]))
    return hosts


# ---------------------------------------------------------------- commands


def cmd_boost(fm, options, config, store):
    if options.preset is None and options.model is None:
        raise ValueError("name a preset (--preset astra-ultra-fast) or a model and effort")
    name, target = resolve(fm, options, config)
    base_name, base_target = baseline(fm, config)
    state = store.load()
    started = now()
    rules = dict(DEFAULT_AUTO_DOWN, **(config.get("auto_down") or {}))
    if options.no_auto_down:
        rules["reset"] = False
    if options.quorum is not None:
        rules["quorum"] = options.quorum
    if options.ceiling is not None:
        rules["ceiling"] = options.ceiling
    rules["until"] = iso(parse_until(options.until, started)) if options.until else None
    accounts, usage_error = fetch_usage(config)
    if state.get("phase") == "boosted" and state.get("snapshot"):
        # Retuning an active boost keeps the original before-reset snapshot.
        snap, started = state["snapshot"], parse_time(state["started_at"])
    else:
        snap = snapshot(accounts)
    exclude = sorted(set(config.get("exclude_profiles") or []) | set(options.exclude or []))
    state = {"phase": "boosted", "boost_name": name, "boost_target": target, "baseline_name": base_name, "baseline_target": base_target,
             "started_at": iso(started), "hosts": hosts_option(options, config), "exclude": exclude, "auto_down": rules,
             "snapshot": snap, "backed_down": {}, "live": not options.no_live, "interrupt": options.interrupt_current_turn,
             "usage_error": usage_error, "note": options.note}
    if options.dry_run:
        print(json.dumps({key: state[key] for key in ("boost_name", "boost_target", "baseline_name", "hosts", "exclude", "auto_down")}, indent=2))
        print(f"usage accounts in snapshot: {len(snap)}" + (f" (usage source: {usage_error})" if usage_error else ""))
        return 0
    store.event("boost", target=target, name=name, hosts=state["hosts"], exclude=exclude, auto_down=rules, note=options.note,
                accounts=len(snap), usage_error=usage_error)
    store.save(state)
    report = converge(fm, config, state, store, quiet=False)
    store.save(state)
    store.event("applied", phase="boosted", report=report["_path"], exit=state["last_exit"])
    print_auto_down(state, usage_error)
    return state["last_exit"]


def print_auto_down(state, usage_error):
    rules = state["auto_down"]
    parts = []
    if rules["reset"] and state["snapshot"]:
        parts.append(f"when the reset lands on {rules['quorum']:.0%} of {len(state['snapshot'])} accounts")
    if rules.get("ceiling") is not None:
        parts.append(f"per account at {rules['ceiling']:.0f}% usage")
    if rules.get("until"):
        parts.append("at " + rules["until"])
    print("Auto-down: " + ("; ".join(parts) if parts else "off - run `reset_boost.py done` to turn down"))
    if usage_error:
        print("Usage source unavailable (" + usage_error + "); reset detection is paused until it answers.")


def end_boost(fm, config, state, store, reason, quiet):
    state.update(phase="cooling", ended_at=iso(now()), end_reason=reason,
                 cooling_until=iso(now() + dt.timedelta(hours=config.get("cooling_hours", COOLING_HOURS))))
    store.event("done", reason=reason, baseline=state["baseline_target"])
    store.save(state)
    report = converge(fm, config, state, store, quiet=quiet)
    store.save(state)
    store.event("applied", phase="cooling", report=report["_path"], exit=state["last_exit"])
    return state["last_exit"]


def cmd_done(fm, options, config, store):
    state = store.load()
    if state.get("phase") != "boosted":
        # Turning down is always allowed, even with no recorded boost: it is the safe direction.
        base_name, base_target = baseline(fm, config)
        state = {"phase": "boosted", "boost_name": None, "boost_target": base_target, "baseline_name": base_name, "baseline_target": base_target,
                 "started_at": None, "hosts": hosts_option(options, config), "exclude": [], "auto_down": DEFAULT_AUTO_DOWN, "snapshot": {},
                 "backed_down": {}, "live": True, "interrupt": False}
    elif options.hosts:
        state["hosts"] = hosts_option(options, config)
    if options.dry_run:
        print(f"would turn down to {state['baseline_name']} on {','.join(state['hosts'])}")
        return 0
    return end_boost(fm, config, state, store, options.reason or "operator: done", quiet=False)


def cmd_watch(fm, options, config, store):
    state = store.load()
    accounts, usage_error = fetch_usage(config)
    if accounts is not None:
        store.usage_path.write_text(json.dumps({"at": iso(now()), "accounts": accounts}, indent=2) + "\n")
    phase = state.get("phase", "idle")
    state["usage_error"] = usage_error
    state["last_watch_at"] = iso(now())
    if phase == "boosted":
        reason, backs, _ = evaluate(state, accounts) if accounts is not None else (None, {}, [])
        if reason is None and state["auto_down"].get("until") and now() >= parse_time(state["auto_down"]["until"]):
            reason = "boost deadline reached"
        if reason:
            exit_code = end_boost(fm, config, state, store, "auto: " + reason, quiet=options.quiet)
            render(fm, config, store)
            return exit_code
        new = {profile: why for profile, why in backs.items() if profile not in state["backed_down"]}
        for profile, why in new.items():
            state["backed_down"][profile] = why
            store.event("backed_down", profile=profile, reason=why)
        if options.converge:
            converge(fm, config, state, store, quiet=options.quiet)
            store.event("converged", phase="boosted", report=state["last_report"], exit=state["last_exit"])
    elif phase == "cooling":
        if options.converge:
            converge(fm, config, state, store, quiet=options.quiet)
            store.event("converged", phase="cooling", report=state["last_report"], exit=state["last_exit"])
        if state.get("last_exit") == 0 or now() >= parse_time(state["cooling_until"]):
            outcome = "verified at baseline everywhere reachable" if state.get("last_exit") == 0 else "cooling period ended with gaps; see dashboard"
            state["phase"] = "idle"
            store.event("idle", outcome=outcome)
    else:
        last = parse_time(state.get("last_report_at"))
        if options.converge and (last is None or now() - last > dt.timedelta(hours=IDLE_AUDIT_HOURS)):
            # Read-only drift audit against the baseline; never changes anything while idle.
            base_name, base_target = baseline(fm, config)
            report = fm.run_fleet(config, list(config["hosts"]), base_target, quiet=True, label="idle audit " + base_name)
            state.update(last_report=report["_path"], last_report_at=report["created_at"], last_exit=fm.report_exit(report),
                         baseline_name=base_name, baseline_target=base_target)
            store.event("audited", report=report["_path"], exit=state["last_exit"])
    store.save(state)
    render(fm, config, store)
    return 0


def cmd_status(fm, options, config, store):
    state = store.load()
    usage = json.loads(store.usage_path.read_text()) if store.usage_path.exists() else {}
    accounts = usage.get("accounts")
    if options.refresh or accounts is None:
        accounts, error = fetch_usage(config)
        if error:
            print("usage source: " + error)
    if options.json:
        print(json.dumps({"state": state, "accounts": accounts}, indent=2))
        return 0
    phase = state.get("phase", "idle")
    print(f"phase: {phase.upper()}")
    if phase != "idle":
        print(f"boost: {state.get('boost_name')}  {json.dumps(state.get('boost_target'))}  since {state.get('started_at')}")
        print(f"baseline: {state.get('baseline_name')}  exclude: {', '.join(state.get('exclude') or []) or '-'}")
    if phase == "cooling":
        print(f"ended: {state.get('ended_at')} ({state.get('end_reason')}); verifying baseline until {state.get('cooling_until')}")
    if state.get("last_report"):
        print(f"last apply/audit: {state.get('last_report_at')} exit {state.get('last_exit')}  {state['last_report']}")
    if phase == "boosted" and accounts is not None:
        reason, backs, rows = evaluate(state, accounts)
        for row in rows:
            flag = "excluded" if row["excluded"] else ("RESET " + row["reset"]) if row["reset"] else ""
            print(f"  {row['label'][:30]:30} {str(row['profile'])[:18]:18} {fmt_pct(row['before']):>5} -> {fmt_pct(row['now']):>5}  {flag}")
        print("auto-down: " + (reason or "not yet"))
    elif accounts:
        for account in sorted(accounts.values(), key=lambda item: item["label"]):
            name, window = primary_window(account)
            if window and not account["disabled"]:
                resets = parse_time(window.get("resets_at"))
                left = f"resets in {(resets - now()).total_seconds() / 3600:.0f}h" if resets else ""
                print(f"  {account['label'][:30]:30} {str(account['profile'])[:18]:18} {name or '':7} {fmt_pct(window['used']):>5}  {left}")
    return 0


def fmt_pct(value):
    return "-" if value is None else f"{value:.0f}%"


def render(fm, config, store):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import boost_dashboard
    state = store.load()
    usage = json.loads(store.usage_path.read_text()) if store.usage_path.exists() else {}
    report = None
    if state.get("last_report") and Path(state["last_report"]).exists():
        report = json.loads(Path(state["last_report"]).read_text())
    rows = evaluate(state, usage.get("accounts") or {})[2] if state.get("phase") == "boosted" and state.get("snapshot") else None
    html = boost_dashboard.render(state, usage, report, store.events(), rows, fm.presets(), config)
    path = Path(config.get("dashboard") or store.dir / "dashboard.html").expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(html)
    os.replace(temporary, path)
    return path


def cmd_dashboard(fm, options, config, store):
    if options.refresh:
        accounts, error = fetch_usage(config)
        if accounts is not None:
            store.usage_path.write_text(json.dumps({"at": iso(now()), "accounts": accounts}, indent=2) + "\n")
    path = render(fm, config, store)
    print(path)
    if options.open:
        opener = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
        subprocess.run(opener, check=False)
    return 0


def target_arguments(parser):
    parser.add_argument("model", nargs="?", help="alias (astra, sol, luna) or exact model ID")
    parser.add_argument("effort", nargs="?", choices=("low", "medium", "high", "xhigh", "max", "ultra"))
    parser.add_argument("--preset", help="named preset, e.g. astra-ultra-fast, sol-high, luna-high")
    parser.add_argument("--tier", choices=("default", "fast", "ultrafast", "flex", "priority"), help="Codex service tier (fast mode)")


def main(argv, fm):
    parser = argparse.ArgumentParser(prog="reset_boost.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    boost = commands.add_parser("boost", help="turn every account up for a reset window")
    target_arguments(boost)
    boost.add_argument("--hosts", help="comma-separated hosts (default: all configured)")
    boost.add_argument("--exclude", action="append", help="profile to keep at the baseline (repeatable; adds to config exclude_profiles)")
    boost.add_argument("--until", help="auto-down deadline: 6h, 90m, 2d or ISO time")
    boost.add_argument("--ceiling", type=float, help="per-account auto-down when its usage reaches this percent")
    boost.add_argument("--quorum", type=float, help="fraction of accounts whose reset must land before auto-down (default 0.5)")
    boost.add_argument("--no-auto-down", action="store_true", help="only `done` or --until ends the boost")
    boost.add_argument("--no-live", action="store_true", help="change launch defaults only; leave running sessions")
    boost.add_argument("--interrupt-current-turn", action="store_true", help="allow cancelling a running turn to switch it")
    boost.add_argument("--note", help="why (shown on the dashboard)")
    boost.add_argument("--dry-run", action="store_true")
    done = commands.add_parser("done", help="turn everything back down to the baseline")
    done.add_argument("--reason")
    done.add_argument("--hosts")
    done.add_argument("--dry-run", action="store_true")
    watch = commands.add_parser("watch", help="one tick: read usage, auto-down, converge, refresh dashboard (run from a timer)")
    watch.add_argument("--no-converge", dest="converge", action="store_false", help="read usage and render only")
    watch.add_argument("--quiet", action="store_true")
    status = commands.add_parser("status", help="show phase, targets and per-account reset progress")
    status.add_argument("--json", action="store_true")
    status.add_argument("--refresh", action="store_true", help="read the usage source now")
    dashboard = commands.add_parser("dashboard", help="write the HTML dashboard")
    dashboard.add_argument("--open", action="store_true", help="open it in the browser")
    dashboard.add_argument("--refresh", action="store_true", help="read the usage source first")
    options = parser.parse_args(argv)
    config = fm.load_config()
    store = Store(fm)
    handler = {"boost": cmd_boost, "done": cmd_done, "watch": cmd_watch, "status": cmd_status, "dashboard": cmd_dashboard}[options.command]
    if options.command in ("status", "dashboard"):
        try:
            return handler(fm, options, config, store)
        except ValueError as error:
            parser.error(str(error))
    # One writer at a time: a manual boost/done waits for a running tick; a tick never waits.
    with store.lock(wait=options.command != "watch") as held:
        if not held:
            print("another reset-boost run holds the lock; skipping this tick")
            return 0
        try:
            code = handler(fm, options, config, store)
        except ValueError as error:
            parser.error(str(error))
        if options.command in ("boost", "done"):
            print("Dashboard: " + str(render(fm, config, store)))
        return code
