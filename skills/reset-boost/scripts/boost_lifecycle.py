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
import shutil
import subprocess
import sys
import threading
import urllib.request

PHASES = ("idle", "boosted", "cooling")
# The control panel sets this during a job to stream per-host and per-session progress.
progress_hook = None
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
            argv = list(source["argv"])
            argv[0] = argv[0] if os.path.isabs(argv[0]) else (shutil.which(argv[0]) or argv[0])
            result = subprocess.run(argv, close_fds=False, capture_output=True, text=True, timeout=source.get("timeout", 60))
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


def server_alive(store):
    try:
        beat = json.loads((store.dir / "serve.json").read_text())
    except (OSError, ValueError):
        return False
    return beat.get("loop") and (parse_time(beat.get("at")) or now() - dt.timedelta(days=1)) > now() - dt.timedelta(minutes=3)


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


def ensure_baseline(fm, config, state):
    if not state.get("baseline_target"):
        state["baseline_name"], state["baseline_target"] = baseline(fm, config)
    state.setdefault("hosts", list(config["hosts"]))
    state.setdefault("channels", {})
    return state


def pinned_profiles(state):
    channels = state.get("channels") or {}
    return sorted(set(state.get("exclude") or []) | set(state.get("backed_down") or {}) |
                  {profile for profile, channel in channels.items() if channel.get("mode") == "pin"})


def exhausted_profiles(accounts):
    """Accounts with no plan quota left in a window: anything more they spend is paid credits."""
    result, moment = set(), now()
    full = lambda window: (window or {}).get("used", 0) >= 100 and not (parse_time(window.get("resets_at")) or moment) < moment
    for account in (accounts or {}).values():
        if account.get("profile") and any(full(window) for window in (account.get("windows") or {}).values()):
            result.add(account["profile"])
    return result


def plan(state, exhausted=()):
    """(host target, per-profile targets, hold unknown panes, label) for the current phase.

    Boosted: every account follows the boost except pinned/backed-down ones, and accounts
    with no plan quota left (never boosted onto paid credits), which stay at baseline;
    solo channels keep their own target. Otherwise everything sits at the baseline except
    solo channels, which an operator set explicitly.
    """
    base = state["baseline_target"]
    customs = {profile: channel["target"] for profile, channel in (state.get("channels") or {}).items() if channel.get("mode") == "custom"}
    if state.get("phase") == "boosted":
        host, label = state["boost_target"], "boost " + str(state.get("boost_name"))
        profiles = {profile: base for profile in set(pinned_profiles(state)) | set(exhausted)}
    else:
        host, label, profiles = base, "baseline " + str(state.get("baseline_name")), {}
    profiles.update({profile: target for profile, target in customs.items() if profile not in exhausted or not is_up_target(target, base)})
    hold = any(target != host for target in profiles.values())
    return host, profiles, hold, label


def is_up_target(target, base):
    return target != base


def session_targets(state):
    """{host: {pane: target}} from per-session settings."""
    result = {}
    for key, value in (state.get("sessions") or {}).items():
        host, _, pane = key.partition("|")
        result.setdefault(host, {})[pane] = value["target"]
    return result


def sessions_path(store):
    return store.dir / "sessions.json"


RECORD_LOCK = threading.Lock()


def record_sessions(store, report):
    """Keep the freshest telemetry per host for the panel (observe passes and every apply)."""
    with RECORD_LOCK:
        return _record_sessions(store, report)


def _record_sessions(store, report):
    path = sessions_path(store)
    try:
        current = json.loads(path.read_text())
    except (OSError, ValueError):
        current = {"hosts": {}}
    at = report.get("created_at") or iso(now())
    for host, value in (report.get("hosts") or {}).items():
        if value.get("skipped"):
            continue
        rows = value.get("terminals") or []
        old = current["hosts"].get(host) or {}
        if value.get("errors") and not rows and not value.get("configs"):
            current["hosts"][host] = dict(old, error=value["errors"][0].get("error"), error_at=at)
            continue
        if isinstance(report.get("only_panes"), dict) or report.get("partial"):
            merged = {row["pane"]: row for row in old.get("rows") or []}
            merged.update({row["pane"]: row for row in rows})
            rows = list(merged.values())
        current["hosts"][host] = {"at": at, "rows": rows, "error": None}
    current["at"] = at
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(current, indent=1))
    os.replace(temporary, path)
    return current


def fleet_options(fm, config, store, state):
    """Common run_fleet inputs: baseline, credit guard, accounts on credits, session targets."""
    usage = json.loads(store.usage_path.read_text()) if store.usage_path.exists() else {}
    exhausted = exhausted_profiles(usage.get("accounts"))
    # The panel's Settings switch (state) overrides the config default.
    guard = dict({"enabled": True, "floor": 0.0}, **(config.get("credit_guard") or {}), **(state.get("credit_guard") or {}))
    return {"baseline": state["baseline_target"], "credit_guard": guard, "credit_profiles": {fm.safe_profile(p) for p in exhausted},
            "pane_targets": session_targets(state), "rehome": rehome_settings(config, state)["enabled"]}, exhausted


def boost_plan(state):
    host, profiles, hold, _ = plan(state)
    return host, profiles, hold


def converge(fm, config, state, store, quiet=True, hosts=None, rehome=None):
    if state.get("phase") == "boosted" and state.get("boost_target") != state.get("baseline_target"):
        # Sessions on credits are moved to an account with quota first; then they follow the boost.
        settings = rehome_settings(config, state)
        if rehome is None:
            rehome = state.get("rehome_boost")
        if settings["enabled"] and (settings["auto"] if rehome is None else rehome):
            auto_rehome(fm, config, store, state, hosts)
    extra, exhausted = fleet_options(fm, config, store, state)
    target, profiles, hold, label = plan(state, exhausted)
    report = fm.run_fleet(config, hosts or state["hosts"], target, apply=True, live=state.get("live", True), interrupt=state.get("interrupt", False),
                          profiles=profiles, hold_unknown=hold, quiet=quiet, label=label, progress=progress_hook, **extra)
    record_sessions(store, dict(report, partial=bool(hosts)))
    if hosts and state.get("last_report") and Path(state["last_report"]).exists():
        # A partial run updates only its hosts in the latest full picture.
        merged = json.loads(Path(state["last_report"]).read_text())
        merged["hosts"].update(report["hosts"])
        Path(report["_path"]).write_text(json.dumps(merged, indent=2) + "\n")
        report = dict(merged, _path=report["_path"])
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


# ---------------------------------------------------------------- rehome

DEFAULT_REHOME = {"enabled": None, "auto": False, "prefer": [], "min_left_percent": 15.0, "interrupt": False, "max_per_account": None,
                  "spread_points": 5.0, "launch": None, "shell": None, "boot_seconds": 45, "fresh_minutes": 15}
FINAL_MOVE_STATUSES = ("move_not_resumable", "move_no_thread", "move_manual", "move_refused")


def rehome_settings(config, state=None):
    """config `rehome` plus the panel's live overrides. Enabled by default once a launch template is set."""
    settings = dict(DEFAULT_REHOME, **(config.get("rehome") or {}), **((state or {}).get("rehome") or {}))
    if settings["enabled"] is None:
        settings["enabled"] = bool(settings.get("launch"))
    return settings


def headroom(account, moment=None):
    """Percent of plan quota left in the account's tightest window; a window past its reset counts as full."""
    moment = moment or now()
    left = []
    for window in (account.get("windows") or {}).values():
        resets = parse_time(window.get("resets_at"))
        left.append(100.0 if resets and resets < moment else 100.0 - float(window.get("used") or 0))
    return min(left) if left else None


def is_pro(account):
    return "pro" in str(account.get("plan") or "").lower()


def resolve_profile(fm, name, accounts):
    """The account manager's own profile name for NAME, or None.

    Accepts the exact name (`ops@example.test`), its folder spelling (`ops_example.test`) or an
    unambiguous short name (`ops`). Launching with a folder spelling makes the wrapper read it as a
    prompt and start a NEW empty session, so anything unresolved is refused."""
    names = sorted({account["profile"] for account in (accounts or {}).values() if account.get("profile")})
    if name in names:
        return name
    for match in ([item for item in names if fm.safe_profile(item) == fm.safe_profile(name)], [item for item in names if item.split("@")[0] == name]):
        if len(match) == 1:
            return match[0]
    return None


def destinations(fm, accounts, settings, exhausted=()):
    """Accounts that can take sessions now, best first: preferred, then Pro plans, then most quota left."""
    prefer = [fm.safe_profile(item) for item in settings.get("prefer") or []]
    rows = []
    for account in (accounts or {}).values():
        profile = account.get("profile")
        if not profile or account.get("disabled") or profile in exhausted:
            continue
        left = headroom(account)
        if left is None or left < settings["min_left_percent"]:
            continue
        safe = fm.safe_profile(profile)
        rows.append({"profile": profile, "label": account.get("label") or profile, "plan": account.get("plan"), "left": left, "pro": is_pro(account),
                     "rank": prefer.index(safe) if safe in prefer else len(prefer)})
    return sorted(rows, key=lambda row: (row["rank"], not row["pro"], -row["left"], row["profile"]))


def assign(candidates, dests, settings, fm):
    """Give each candidate a destination. Each assigned session counts `spread_points` against its
    account so a long list spreads once the preferred account nears `min_left_percent`."""
    taken = {}
    for item in candidates:
        source = item.get("from")
        best = None
        for dest in sorted(dests, key=lambda row: (row["rank"], not row["pro"], -(row["left"] - settings["spread_points"] * taken.get(row["profile"], 0)))):
            count = taken.get(dest["profile"], 0)
            if fm.safe_profile(dest["profile"]) == source:
                continue
            if settings.get("max_per_account") and count >= settings["max_per_account"]:
                continue
            if dest["left"] - settings["spread_points"] * count < settings["min_left_percent"]:
                continue
            best = dest
            break
        if best:
            taken[best["profile"]] = taken.get(best["profile"], 0) + 1
            item.update(to=best["profile"], to_label=best["label"])
        else:
            item.update(to=None, to_label=None)
    return candidates


def load_live(store):
    try:
        return json.loads(sessions_path(store).read_text())
    except (OSError, ValueError):
        return {"hosts": {}}


def rehome_plan(fm, config, store, state, include=(), hosts=None):
    """Which sessions are on credits and where each should go. `include` adds HOST|PANE keys regardless."""
    settings = rehome_settings(config, state)
    usage = json.loads(store.usage_path.read_text()) if store.usage_path.exists() else {}
    accounts = usage.get("accounts") or {}
    exhausted = exhausted_profiles(accounts)
    exhausted_safe = {fm.safe_profile(name) for name in exhausted}
    guard = dict({"enabled": True, "floor": 0.0}, **(config.get("credit_guard") or {}), **(state.get("credit_guard") or {}))
    live = load_live(store)
    candidates, seen = [], set()
    for host, value in (live.get("hosts") or {}).items():
        if hosts and host not in hosts:
            continue
        for row in value.get("rows") or []:
            key = host + "|" + row["pane"]
            seen.add(key)
            credits = fm.on_credits(row.get("telemetry"), guard.get("floor", 0.0)) or row.get("profile") in exhausted_safe
            if credits or key in include:
                candidates.append({"key": key, "host": host, "pane": row["pane"], "backend": row.get("backend"), "from": row.get("profile"),
                                   "activity": row.get("activity"), "on_credits": bool(credits), "observed_at": value.get("at")})
    for key in include:
        if key not in seen:
            host, _, pane = key.partition("|")
            candidates.append({"key": key, "host": host, "pane": pane, "backend": None, "from": None, "activity": None, "on_credits": False, "observed_at": None})
    dests = destinations(fm, accounts, settings, exhausted)
    assign(candidates, dests, settings, fm)
    local_proc = Path("/proc").is_dir()
    for item in candidates:
        kind = (config["hosts"].get(item["host"]) or {}).get("type")
        if item["backend"] == "herdr" or kind == "windows" or (kind == "local" and not local_proc):
            item["status"] = "move_manual"
        elif not item["to"]:
            item["status"] = "no_destination"
        else:
            item["status"] = "move_suggested"
    return {"settings": settings, "destinations": dests, "moves": candidates}


def perform_moves(fm, config, store, state, items, interrupt=False):
    """Run moves ({host, pane, to, from}) and record each one: event log, session table, state."""
    grouped = {}
    for item in items:
        grouped.setdefault(item["host"], []).append({"pane": item["pane"], "to": item["to"], "interrupt": bool(interrupt)})
    if not grouped:
        return []
    for item in items:
        store.event("move_started", host=item["host"], pane=item["pane"], to=item["to"], interrupt=bool(interrupt))
    results = fm.run_moves(config, grouped, rehome_settings(config, state), progress_hook)
    rows = []
    attempts = state.setdefault("move_attempts", {})
    moved = state.setdefault("moves", {})
    for host, host_rows in results.items():
        for row in host_rows:
            key = host + "|" + str(row.get("pane"))
            source = row.get("from") or next((item.get("from") for item in items if item["host"] == host and item["pane"] == row.get("pane")), None)
            record = {"from": source, "to": row.get("to"), "status": row.get("status"), "at": iso(now())}
            attempts[key] = record
            if row.get("status") == "moved":
                moved[key] = record
            store.event("moved" if row.get("status") == "moved" else "move", host=host, pane=row.get("pane"), from_profile=source, to=row.get("to"),
                        status=row.get("status"), thread=row.get("thread"), goal_resumed=row.get("goal_resumed"), detail=row.get("detail") or row.get("error"))
            rows.append(dict(row, host=host, from_profile=source))
    for key in list(moved)[:-200]:
        moved.pop(key, None)
    for key in list(attempts)[:-400]:
        attempts.pop(key, None)
    mark_moved(fm, store, [row for row in rows if row.get("status") == "moved"])
    return rows


def mark_moved(fm, store, rows):
    """Show a moved session on its new account right away (the next read confirms it)."""
    if not rows:
        return
    path = sessions_path(store)
    with RECORD_LOCK:
        live = load_live(store)
        for row in rows:
            for item in ((live.get("hosts") or {}).get(row["host"]) or {}).get("rows") or []:
                if item.get("pane") == row.get("pane"):
                    item.update(profile=fm.safe_profile(row["to"]), status="moved")
        temporary = path.with_suffix(".moved.tmp")
        temporary.write_text(json.dumps(live, indent=1))
        os.replace(temporary, path)


def auto_rehome(fm, config, store, state, hosts=None):
    """During a boost: move sessions on credits (from a fresh session read) before the boost is applied."""
    settings = rehome_settings(config, state)
    proposal = rehome_plan(fm, config, store, state, hosts=hosts)
    fresh = now() - dt.timedelta(minutes=settings["fresh_minutes"])
    attempts = state.get("move_attempts") or {}
    items = []
    for item in proposal["moves"]:
        if item["status"] != "move_suggested" or (parse_time(item.get("observed_at")) or fresh) < fresh:
            continue
        last = attempts.get(item["key"]) or {}
        if last.get("status") in FINAL_MOVE_STATUSES and (parse_time(last.get("at")) or fresh) > now() - dt.timedelta(hours=6):
            continue  # Its thread would not resume (or cannot be moved here); do not retry every tick.
        items.append(item)
    if not items:
        return []
    rows = perform_moves(fm, config, store, state, items, interrupt=settings["interrupt"])
    store.event("rehome", moved=sum(row.get("status") == "moved" for row in rows), tried=len(rows))
    return rows


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
    keep = {key: state[key] for key in ("channels", "sessions", "autopilot", "loop", "last_report", "last_report_at", "last_exit") if key in state}
    backed = state.get("backed_down", {}) if state.get("phase") == "boosted" else {}
    state = dict(keep, **{"phase": "boosted", "boost_name": name, "boost_target": target, "baseline_name": base_name, "baseline_target": base_target,
             "started_at": iso(started), "hosts": hosts_option(options, config), "exclude": exclude, "auto_down": rules,
             "snapshot": snap, "backed_down": backed, "live": not options.no_live, "interrupt": options.interrupt_current_turn,
             "usage_error": usage_error, "note": options.note, "rehome_boost": getattr(options, "rehome", None)})
    state.setdefault("channels", {})
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
    solos = [profile for profile, channel in (state.get("channels") or {}).items() if channel.get("mode") == "custom"]
    if state.get("sessions"):
        store.event("sessions_cleared", count=len(state["sessions"]))
    state["sessions"] = {}
    state["channels"] = {profile: channel for profile, channel in (state.get("channels") or {}).items() if channel.get("mode") != "custom"}
    state.update(phase="cooling", ended_at=iso(now()), end_reason=reason, backed_down={},
                 cooling_until=iso(now() + dt.timedelta(hours=config.get("cooling_hours", COOLING_HOURS))))
    if solos:
        store.event("channels_cleared", profiles=solos)
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
        keep = {key: state[key] for key in ("channels", "sessions", "autopilot", "loop", "last_report", "last_report_at", "last_exit") if key in state}
        state = dict(keep, **{"phase": "boosted", "boost_name": None, "boost_target": base_target, "baseline_name": base_name, "baseline_target": base_target,
                 "started_at": None, "hosts": hosts_option(options, config), "exclude": [], "auto_down": DEFAULT_AUTO_DOWN, "snapshot": {},
                 "backed_down": {}, "live": True, "interrupt": False})
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
    elif any(channel.get("mode") == "custom" for channel in (state.get("channels") or {}).values()):
        ensure_baseline(fm, config, state)
        if options.converge:
            converge(fm, config, state, store, quiet=options.quiet)
            store.event("converged", phase="idle", report=state["last_report"], exit=state["last_exit"])
    else:
        last = parse_time(state.get("last_report_at"))
        if options.converge and (options.force_audit or last is None or now() - last > dt.timedelta(hours=IDLE_AUDIT_HOURS)):
            # Read-only drift audit against the baseline; never changes anything while idle.
            base_name, base_target = baseline(fm, config)
            report = fm.run_fleet(config, list(config["hosts"]), base_target, quiet=True, label="idle audit " + base_name, progress=progress_hook)
            record_sessions(store, report)
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


def latest_report(state):
    path = state.get("last_report")
    if path and Path(path).exists():
        return json.loads(Path(path).read_text())
    return None


def cmd_converge(fm, options, config, store):
    """Re-apply the current plan now (all hosts, or --hosts)."""
    state = ensure_baseline(fm, config, store.load())
    hosts = hosts_option(options, config) if options.hosts else None
    converge(fm, config, state, store, quiet=options.quiet, hosts=hosts)
    store.save(state)
    store.event("converged", phase=state.get("phase", "idle"), hosts=hosts or "all", report=state["last_report"], exit=state["last_exit"])
    return state["last_exit"]


def cmd_channel(fm, options, config, store):
    """One account's channel: follow the fleet, pin at baseline, or solo at its own target."""
    if not fm.PROFILE_RE.fullmatch(options.profile):
        raise ValueError("profile must contain only letters, digits and ._@+-")
    state = ensure_baseline(fm, config, store.load())
    setting = options.setting
    if setting == "follow":
        state["channels"].pop(options.profile, None)
        (state.get("backed_down") or {}).pop(options.profile, None)
        if options.profile in (state.get("exclude") or []) and options.profile not in (config.get("exclude_profiles") or []):
            state["exclude"].remove(options.profile)
        channel = {"mode": "follow"}
    elif setting == "pin":
        channel = state["channels"][options.profile] = {"mode": "pin"}
    else:
        preset = options.preset or (setting if setting in fm.presets() else None)
        model = None if preset else setting
        target = fm.resolve_target(model, options.effort, preset, options.tier)
        if not fm.MODEL_ID_RE.fullmatch(target["model"]):
            raise ValueError("model must contain only safe provider ID characters")
        channel = state["channels"][options.profile] = {"mode": "custom", "name": preset or f"{target['model']}/{target['effort']}", "target": target}
    store.event("channel", profile=options.profile, **{key: value for key, value in channel.items() if key != "target"}, target=channel.get("target"))
    store.save(state)
    if not options.no_apply:
        converge(fm, config, state, store, quiet=options.quiet)
        store.save(state)
    return state.get("last_exit", 0)


def cmd_rules(fm, options, config, store):
    state = store.load()
    if state.get("phase") != "boosted":
        raise ValueError("no boost is running; pass these with `boost`")
    rules = state["auto_down"]
    if options.reset is not None:
        rules["reset"] = options.reset == "on"
    if options.quorum is not None:
        rules["quorum"] = max(0.05, min(1.0, options.quorum))
    if options.drop_points is not None:
        rules["drop_points"] = max(1.0, options.drop_points)
    if options.ceiling is not None:
        rules["ceiling"] = None if options.ceiling == "off" else float(options.ceiling)
    if options.until is not None:
        rules["until"] = None if options.until == "off" else iso(parse_until(options.until, now()))
    store.event("rules", **rules)
    store.save(state)
    print(json.dumps(rules))
    return 0


def cmd_pane(fm, options, config, store):
    """Retry one live session at its planned target; --interrupt cancels its running turn first."""
    if options.host not in config["hosts"]:
        raise ValueError("unknown host " + options.host)
    state = ensure_baseline(fm, config, store.load())
    extra, exhausted = fleet_options(fm, config, store, state)
    target, profiles, hold, label = plan(state, exhausted)
    report = fm.run_fleet(config, [options.host], target, apply=True, live=True, interrupt=options.interrupt, profiles=profiles, hold_unknown=hold,
                          quiet=True, label="pane " + options.pane, progress=progress_hook, only_panes={options.host: [options.pane]}, save=False, **extra)
    record_sessions(store, dict(report, partial=True))
    rows = report["hosts"][options.host].get("terminals") or []
    latest = latest_report(state)
    if latest and rows:
        panes = latest["hosts"].setdefault(options.host, {"configs": [], "terminals": [], "errors": []})["terminals"]
        for row in rows:
            match = next((index for index, old in enumerate(panes) if old.get("pane") == row.get("pane")), None)
            if match is None:
                panes.append(row)
            else:
                panes[match] = row
        Path(state["last_report"]).write_text(json.dumps(latest, indent=2) + "\n")
        state["last_exit"] = fm.report_exit(latest)
        store.save(state)
    status = rows[0]["status"] if rows else "pane not found (closed, or no Codex session there)"
    store.event("pane", host=options.host, pane=options.pane, interrupt=options.interrupt, status=status)
    print(f"{options.host} {options.pane}: {status}")
    return 0 if rows and rows[0]["status"] == "verified" else 2


def cmd_session(fm, options, config, store):
    """Set specific live sessions (HOST|PANE ...) to a target, or back to following the fleet."""
    state = ensure_baseline(fm, config, store.load())
    state.setdefault("sessions", {})
    keys = []
    for item in options.sessions:
        host, sep, pane = item.partition("|")
        if not sep or host not in config["hosts"] or not pane or len(pane) > 64:
            raise ValueError("sessions are HOST|PANE with a configured host: " + item)
        keys.append((host, pane))
    if options.setting == "follow":
        for host, pane in keys:
            state["sessions"].pop(host + "|" + pane, None)
        target = None
    else:
        preset = options.preset or (options.setting if options.setting in fm.presets() else None)
        target = fm.resolve_target(None if preset else options.setting, options.effort, preset, options.tier)
        if not fm.MODEL_ID_RE.fullmatch(target["model"]):
            raise ValueError("model must contain only safe provider ID characters")
        for host, pane in keys:
            state["sessions"][host + "|" + pane] = {"target": target, "set_at": iso(now()), "name": preset or f"{target['model']}/{target['effort']}"}
    store.event("session", sessions=[h + "|" + p for h, p in keys], setting=options.setting if target is None else (preset or target), interrupt=options.interrupt)
    store.save(state)
    extra, exhausted = fleet_options(fm, config, store, state)
    host_target, profiles, hold, label = plan(state, exhausted)
    only = {}
    for host, pane in keys:
        only.setdefault(host, []).append(pane)
    report = fm.run_fleet(config, list(only), host_target, apply=True, live=True, interrupt=options.interrupt, profiles=profiles, hold_unknown=hold,
                          quiet=True, label="sessions", progress=progress_hook, only_panes=only, save=False, **extra)
    record_sessions(store, dict(report, partial=True))
    rows = [dict(row, host=host) for host, value in report["hosts"].items() for row in value.get("terminals") or []]
    for row in rows:
        print(f"{row['host']} {row['pane']}: {row['status']}")
    return 0 if rows and all(row["status"] == "verified" for row in rows) else 2


def observe_hosts(fm, config, store, hosts):
    """One read-only pass over these hosts' live sessions, recorded for the panel."""
    state = ensure_baseline(fm, config, store.load())
    extra, exhausted = fleet_options(fm, config, store, state)
    target, profiles, hold, label = plan(state, exhausted)
    report = fm.run_fleet(config, hosts, target, profiles=profiles, hold_unknown=hold, quiet=True, label="observe",
                          observe=True, save=False, **extra)
    return record_sessions(store, report)


def cmd_move(fm, options, config, store):
    """Move one live session to another account (default: the best one with quota)."""
    if options.host not in config["hosts"]:
        raise ValueError("unknown host " + options.host)
    state = ensure_baseline(fm, config, store.load())
    settings = rehome_settings(config, state)
    if not settings.get("launch"):
        raise ValueError("rehome.launch is not configured (e.g. \"codex {profile} resume {thread}\")")
    key = options.host + "|" + options.pane
    proposal = rehome_plan(fm, config, store, state, include=[key])
    item = next(row for row in proposal["moves"] if row["key"] == key)
    usage = json.loads(store.usage_path.read_text()) if store.usage_path.exists() else {}
    if options.to:
        to = resolve_profile(fm, options.to, usage.get("accounts"))
        if not to:
            raise ValueError(f"cannot resolve the account manager's profile name for {options.to}; refusing to launch "
                             "(a folder spelling would start a new, empty session)")
        if to in exhausted_profiles(usage.get("accounts")):
            raise ValueError(to + " has no quota left; moving there would still spend credits")
        item.update(to=to, status="move_suggested" if item["status"] != "move_manual" else "move_manual")
    if item["status"] == "move_manual":
        print(f"{key}: move_manual (automatic moves need a tmux pane on a Linux host)")
        return 2
    if not item.get("to"):
        print(f"{key}: no account has at least {settings['min_left_percent']:.0f}% quota left")
        return 2
    if options.dry_run:
        print(f"{key}: would move {item.get('from') or '?'} -> {item['to']}")
        return 0
    rows = perform_moves(fm, config, store, state, [item], interrupt=options.interrupt)
    store.save(state)
    for row in rows:
        print(f"{row['host']} {row['pane']}: {row['status']} {row.get('from_profile') or '?'} -> {row.get('to')}" + (f" ({row['detail']})" if row.get("detail") else ""))
    return 0 if rows and rows[0]["status"] == "moved" else 2


def cmd_rehome(fm, options, config, store):
    """Sessions on credits and the account each should move to; --apply moves them."""
    state = ensure_baseline(fm, config, store.load())
    hosts = hosts_option(options, config) if options.hosts else None
    proposal = rehome_plan(fm, config, store, state, hosts=hosts)
    if options.json and not options.apply:
        print(json.dumps(proposal, indent=2))
        return 0
    if not options.apply:
        for item in proposal["moves"]:
            print(f"{item['host']:8} {item['pane']:10} {str(item['from'] or '?')[:18]:18} -> {str(item['to'] or '-')[:22]:22} {item['status']}")
        if not proposal["moves"]:
            print("no session is on credits")
        print("destinations: " + (", ".join(f"{row['profile']} ({row['plan']}, {row['left']:.0f}% left)" for row in proposal["destinations"]) or "none with quota"))
        return 0
    if not proposal["settings"].get("launch"):
        raise ValueError("rehome.launch is not configured (e.g. \"codex {profile} resume {thread}\")")
    items = [item for item in proposal["moves"] if item["status"] == "move_suggested"]
    rows = perform_moves(fm, config, store, state, items, interrupt=options.interrupt or proposal["settings"]["interrupt"])
    store.event("rehome", moved=sum(row.get("status") == "moved" for row in rows), tried=len(rows))
    store.save(state)
    for row in rows:
        print(f"{row['host']:8} {row['pane']:10} {row['status']:20} {row.get('from_profile') or '?'} -> {row.get('to')}")
    return 0 if all(row["status"] == "moved" for row in rows) else 2


def cmd_observe(fm, options, config, store):
    """Read every live session's status line (model, effort, fast, run state, quota, credits). Changes nothing."""
    state = ensure_baseline(fm, config, store.load())
    extra, exhausted = fleet_options(fm, config, store, state)
    target, profiles, hold, label = plan(state, exhausted)
    hosts = hosts_option(options, config) if getattr(options, "hosts", None) else list(config["hosts"])
    report = fm.run_fleet(config, hosts, target, profiles=profiles, hold_unknown=hold, quiet=True, label="observe", progress=progress_hook,
                          observe=True, save=False, **extra)
    current = record_sessions(store, report)
    if getattr(options, "json", False):
        print(json.dumps(current, indent=2))
    else:
        for host, value in current["hosts"].items():
            for row in value.get("rows") or []:
                info = row.get("telemetry") or {}
                print(f"{host:8} {row['pane']:10} {str(row.get('profile'))[:16]:16} {info.get('model') or '?':14} {info.get('effort') or '?':7} "
                      f"{'fast' if info.get('fast') else '    '} {row.get('activity') or '':8} 5h {info.get('five_hour_left')} wk {info.get('weekly_left')} {info.get('credits') or ''}")
    return 0


def cmd_signals(fm, options, config, store):
    import boost_agent
    state = store.load()
    items = boost_agent.track(store, boost_agent.signals(state, latest_report(state), state.get("usage_error")))
    if options.json:
        print(json.dumps(items, indent=2))
        return 0
    for item in items:
        print(f"{item['severity']:4} {item['code']:20} {item['host']:8} {item['subject'][:24]:24} {item['detail'][:90]}")
    if not items:
        print("no signals")
    return 0


def cmd_agent(fm, options, config, store):
    import boost_agent
    state = store.load()
    signal = None
    if options.signal:
        items = boost_agent.track(store, boost_agent.signals(state, latest_report(state), state.get("usage_error")))
        signal = next((item for item in items if item["id"] == options.signal), None)
        if signal is None:
            raise ValueError("no current signal with id " + options.signal)
    run = boost_agent.start(config, store, state, signal=signal, request=" ".join(options.request or []), wait=not options.background)
    finished = next((item for item in boost_agent.load_runs(store) if item["name"] == run["name"]), run)
    print(f"{finished['name']}: {finished['status']}")
    if finished.get("result"):
        print(finished["result"])
    return 0 if finished["status"] in ("done", "running") else 1


def cmd_serve(fm, options, config, store):
    import boost_server
    return boost_server.serve(fm, config, store, options)


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
    parser.add_argument("--tier", choices=("default", "fast", "priority", "flex"), help="Codex service tier: fast (= priority) or default")


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
    boost.add_argument("--rehome", dest="rehome", action="store_true", default=None, help="move sessions on credits to accounts with quota first")
    boost.add_argument("--no-rehome", dest="rehome", action="store_false", help="leave sessions on credits where they are (held at baseline)")
    boost.add_argument("--dry-run", action="store_true")
    done = commands.add_parser("done", help="turn everything back down to the baseline")
    done.add_argument("--reason")
    done.add_argument("--hosts")
    done.add_argument("--dry-run", action="store_true")
    watch = commands.add_parser("watch", help="one tick: read usage, auto-down, converge, refresh dashboard (run from a timer)")
    watch.add_argument("--no-converge", dest="converge", action="store_false", help="read usage and render only")
    watch.add_argument("--quiet", action="store_true")
    watch.add_argument("--audit", dest="force_audit", action="store_true", help="when idle, audit now instead of every 6 hours")
    watch.add_argument("--even-if-served", action="store_true", help="run even while the control panel's loop is alive")
    converge = commands.add_parser("converge", help="re-apply the current plan now")
    converge.add_argument("--hosts")
    converge.add_argument("--quiet", action="store_true")
    channel = commands.add_parser("channel", help="one account: follow the fleet, pin at baseline, or solo at its own target")
    channel.add_argument("profile")
    channel.add_argument("setting", help="follow | pin | a preset name | a model alias or ID (then effort)")
    channel.add_argument("effort", nargs="?", choices=("low", "medium", "high", "xhigh", "max", "ultra"))
    channel.add_argument("--preset")
    channel.add_argument("--tier", choices=("default", "fast", "priority", "flex"))
    channel.add_argument("--no-apply", action="store_true", help="record only; apply on the next tick")
    channel.add_argument("--quiet", action="store_true")
    rules = commands.add_parser("rules", help="tune auto-down while a boost runs")
    rules.add_argument("--reset", choices=("on", "off"))
    rules.add_argument("--quorum", type=float)
    rules.add_argument("--drop-points", type=float)
    rules.add_argument("--ceiling", help="percent, or off")
    rules.add_argument("--until", help="6h, ISO time, or off")
    pane = commands.add_parser("pane", help="retry one live session at its planned target")
    pane.add_argument("host")
    pane.add_argument("pane")
    pane.add_argument("--interrupt", action="store_true", help="cancel its running turn first (never restarts it)")
    session = commands.add_parser("session", help="set live sessions (HOST|PANE ...) to a target, or follow the fleet")
    session.add_argument("setting", help="follow | a preset | a model alias or ID (then --effort)")
    session.add_argument("sessions", nargs="+", help="HOST|PANE, as shown by `observe`")
    session.add_argument("--effort", choices=("low", "medium", "high", "xhigh", "max", "ultra"))
    session.add_argument("--preset")
    session.add_argument("--tier", choices=("default", "fast", "priority", "flex"))
    session.add_argument("--interrupt", action="store_true", help="cancel a running turn first instead of waiting for idle")
    move = commands.add_parser("move", help="move one live session to another account (verified first; keeps the conversation)")
    move.add_argument("host")
    move.add_argument("pane")
    move.add_argument("--to", help="destination profile (default: the best account with quota)")
    move.add_argument("--interrupt", action="store_true", help="cancel its running turn first instead of holding")
    move.add_argument("--dry-run", action="store_true")
    rehome = commands.add_parser("rehome", help="move sessions on credits to accounts with quota (dry run unless --apply)")
    rehome.add_argument("--apply", action="store_true")
    rehome.add_argument("--interrupt", action="store_true", help="cancel running turns first instead of holding")
    rehome.add_argument("--hosts")
    rehome.add_argument("--json", action="store_true")
    observe = commands.add_parser("observe", help="read every live session's status line; changes nothing")
    observe.add_argument("--hosts")
    observe.add_argument("--json", action="store_true")
    sig = commands.add_parser("signals", help="problems the buttons could not fix, worst first")
    sig.add_argument("--json", action="store_true")
    agent = commands.add_parser("agent", help="hand a signal or a request to the configured agent")
    agent.add_argument("request", nargs="*")
    agent.add_argument("--signal", help="signal id from `signals`")
    agent.add_argument("--background", action="store_true")
    serve = commands.add_parser("serve", help="run the live control panel (local web UI + loop)")
    serve.add_argument("--port", type=int, default=8786)
    serve.add_argument("--bind", default="127.0.0.1")
    serve.add_argument("--open", action="store_true")
    serve.add_argument("--no-loop", action="store_true", help="UI only; leave ticks to the watcher")
    status = commands.add_parser("status", help="show phase, targets and per-account reset progress")
    status.add_argument("--json", action="store_true")
    status.add_argument("--refresh", action="store_true", help="read the usage source now")
    dashboard = commands.add_parser("dashboard", help="write the HTML dashboard")
    dashboard.add_argument("--open", action="store_true", help="open it in the browser")
    dashboard.add_argument("--refresh", action="store_true", help="read the usage source first")
    options = parser.parse_args(argv)
    config = fm.load_config()
    store = Store(fm)
    handler = {"boost": cmd_boost, "done": cmd_done, "watch": cmd_watch, "status": cmd_status, "dashboard": cmd_dashboard, "converge": cmd_converge,
               "channel": cmd_channel, "rules": cmd_rules, "pane": cmd_pane, "signals": cmd_signals, "agent": cmd_agent, "serve": cmd_serve,
               "session": cmd_session, "observe": cmd_observe, "move": cmd_move, "rehome": cmd_rehome}[options.command]
    if options.command == "watch" and not options.even_if_served and server_alive(store):
        print("the control panel's loop is running; it does the ticks")
        return 0
    if options.command in ("status", "dashboard", "signals", "agent", "serve", "observe") or (options.command == "rehome" and not options.apply):
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
