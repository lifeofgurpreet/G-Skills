"""The live control panel: a local web UI, its JSON/SSE API, and the loop behind it.

Standard library only. Binds to 127.0.0.1 by default; every API call needs the
panel token (kept in the state directory, mode 0600) and a local Host header.
Buttons run the same functions as the CLI, one fleet job at a time, and stream
per-host and per-session progress. The loop polls usage, runs the watch tick,
and lets the autopilot hand persistent signals to an agent.
"""
import argparse
import contextlib
import datetime as dt
import faulthandler
import hmac
import http.server
import json
import os
from pathlib import Path
import queue
import secrets
import signal
import socketserver
import subprocess
import sys
import threading
import time
import traceback
from urllib.parse import parse_qs, urlparse

import boost_agent
import boost_lifecycle
import boost_dashboard

CONSOLE = Path(__file__).resolve().parent.parent / "assets" / "console.html"
STYLES = CONSOLE.with_name("operator-ui.css")


def write_private(path, text):
    """Create or replace a file readable only by this account (never briefly wider)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with contextlib.suppress(FileNotFoundError):
        temporary.unlink()
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as handle:
        handle.write(text)
    os.replace(temporary, path)


def token_for(store):
    path = store.dir / "serve-token"
    if not path.exists():
        write_private(path, secrets.token_urlsafe(24))
    path.chmod(0o600)
    return path.read_text().strip()


class Hub:
    """Fan-out of server-sent events to every open panel."""

    def __init__(self):
        self.lock = threading.Lock()
        self.listeners = []

    def subscribe(self):
        channel = queue.Queue(maxsize=500)
        with self.lock:
            self.listeners.append(channel)
        return channel

    def unsubscribe(self, channel):
        with self.lock:
            if channel in self.listeners:
                self.listeners.remove(channel)

    def publish(self, kind, data):
        message = f"event: {kind}\ndata: {json.dumps(data, default=str)}\n\n"
        with self.lock:
            for channel in list(self.listeners):
                try:
                    channel.put_nowait(message)
                except queue.Full:
                    self.listeners.remove(channel)


class Panel:
    def __init__(self, fm, config, store, options):
        self.fm, self.config, self.store, self.options = fm, config, store, options
        self.hub = Hub()
        self.job = None
        self.last_job = None
        self.job_lock = threading.Lock()
        self.signature = None
        self.token = token_for(store)
        self.loop = not getattr(options, "no_loop", False)
        self.next_tick = time.time() + 60

    # ------------------------------------------------------------ state

    def snapshot(self):
        fm, config, store = self.fm, self.config, self.store
        state = store.load()
        boost_lifecycle.ensure_baseline(fm, config, state)
        usage = json.loads(store.usage_path.read_text()) if store.usage_path.exists() else {}
        report = boost_lifecycle.latest_report(state)
        items = boost_agent.track(self.store, boost_agent.signals(state, report, state.get("usage_error")))
        runs = boost_agent.load_runs(store)
        target, profiles, hold, label = boost_lifecycle.plan(state, boost_lifecycle.exhausted_profiles(usage.get("accounts")))
        evaluated = {row["id"]: row for row in boost_lifecycle.evaluate(state, usage.get("accounts") or {})[2]} if state.get("phase") == "boosted" else {}
        panes_by_profile = {}
        for host, value in ((report or {}).get("hosts") or {}).items():
            for row in value.get("terminals") or []:
                if row.get("profile"):
                    panes_by_profile.setdefault(row["profile"], []).append(dict(row, host=host))
        pinned = set(boost_lifecycle.pinned_profiles(state)) | set(config.get("exclude_profiles") or [])
        accounts = []
        for key, account in sorted((usage.get("accounts") or {}).items(), key=lambda item: (item[1].get("disabled"), item[1]["label"])):
            profile = account.get("profile")
            channel = (state.get("channels") or {}).get(profile) or {}
            if channel.get("mode") == "custom":
                mode = "solo"
            elif profile in (config.get("exclude_profiles") or []):
                mode = "locked"
            elif profile in pinned:
                mode = "pin"
            else:
                mode = "follow"
            safe = fm.safe_profile(profile) if profile else None
            effective = {fm.safe_profile(name): value for name, value in profiles.items()}.get(safe, target) if profile else target
            windows = account.get("windows") or {}
            row = evaluated.get(key) or {}
            accounts.append({"id": key, "label": account["label"], "profile": profile, "plan": account.get("plan"), "disabled": account.get("disabled"),
                             "weekly": windows.get("weekly"), "session": windows.get("session"), "before": row.get("before"), "reset": row.get("reset"),
                             "mode": mode, "solo": channel.get("name"), "backed_down": (state.get("backed_down") or {}).get(profile),
                             "target": effective, "panes": panes_by_profile.get(safe, [])})
        proposal = boost_lifecycle.rehome_plan(fm, config, store, state)
        rehome = dict(proposal, **{key: proposal["settings"][key] for key in ("enabled", "auto", "interrupt", "min_left_percent")})
        hosts = []
        for row in boost_dashboard.host_rows(report):
            hosts.append(dict(row, panes=row["panes"], errors_detail=((report or {}).get("hosts") or {}).get(row["host"], {}).get("errors", [])))
        return {
            "server_time": boost_lifecycle.iso(boost_lifecycle.now()),
            "phase": state.get("phase", "idle"), "label": label, "target": target, "profiles": profiles,
            "boost": {key: state.get(key) for key in ("boost_name", "boost_target", "started_at", "note", "ended_at", "end_reason", "cooling_until")},
            "baseline": {"name": state.get("baseline_name"), "target": state.get("baseline_target")},
            "auto_down": state.get("auto_down") or dict(boost_lifecycle.DEFAULT_AUTO_DOWN, **(config.get("auto_down") or {})),
            "snapshot_size": len(state.get("snapshot") or {}),
            "accounts": accounts, "hosts": hosts, "configured_hosts": list(config["hosts"]),
            "exclude_profiles": config.get("exclude_profiles") or [],
            "signals": items, "agent_runs": list(reversed(runs[-15:])), "autopilot": boost_agent.settings(state, config),
            "loop": {"enabled": self.loop, "tick_minutes": (state.get("loop") or {}).get("tick_minutes", self.config.get("tick_minutes", 10)),
                     "next_tick_at": boost_lifecycle.iso(dt.datetime.fromtimestamp(self.next_tick, dt.timezone.utc)) if self.loop else None},
            "usage": {"at": usage.get("at"), "error": state.get("usage_error")},
            "report": {"at": state.get("last_report_at"), "exit": state.get("last_exit"), "label": (report or {}).get("label")},
            "job": self.job or self.last_job,
            "events": list(reversed(store.events(80))),
            "presets": fm.presets(),
            "sessions": self.sessions(state, usage, profiles, target, rehome),
            "rehome": {key: rehome[key] for key in ("enabled", "auto", "interrupt", "min_left_percent")} | {
                "launch": bool(rehome["settings"].get("launch")), "destinations": rehome["destinations"],
                "best": rehome["destinations"][0] if rehome["destinations"] else None},
            "credit_guard": dict({"enabled": True, "floor": 0.0}, **(config.get("credit_guard") or {}), **(state.get("credit_guard") or {})),
            "observe_seconds": (state.get("loop") or {}).get("observe_seconds", config.get("observe_seconds", 60)),
        }

    def sessions(self, state, usage, profiles, host_target, rehome=None):
        """Every live session with what it reports right now and what the plan wants for it."""
        fm = self.fm
        live = json.loads(boost_lifecycle.sessions_path(self.store).read_text()) if boost_lifecycle.sessions_path(self.store).exists() else {"hosts": {}}
        accounts = {fm.safe_profile(account["profile"]): account for account in (usage.get("accounts") or {}).values() if account.get("profile")}
        exhausted = {fm.safe_profile(name) for name in boost_lifecycle.exhausted_profiles(usage.get("accounts"))}
        by_profile = {fm.safe_profile(name): value for name, value in profiles.items()}
        overrides = state.get("sessions") or {}
        guard = dict({"enabled": True, "floor": 0.0}, **(self.config.get("credit_guard") or {}), **(state.get("credit_guard") or {}))
        suggested = {item["key"]: item for item in (rehome or {}).get("moves") or []}
        moved = state.get("moves") or {}
        rows = []
        for host, value in (live.get("hosts") or {}).items():
            for row in value.get("rows") or []:
                info = row.get("telemetry") or {}
                key = f"{host}|{row['pane']}"
                own = overrides.get(key)
                profile = row.get("profile")
                planned = (own or {}).get("target") or by_profile.get(profile) or host_target
                if state.get("phase", "idle") == "idle" and not own and profile not in by_profile:
                    # Outside a boost nothing is re-applied: a session's own model is the user's choice.
                    planned = None
                account = accounts.get(profile) or {}
                credits = fm.on_credits(info, guard.get("floor", 0.0)) or profile in exhausted
                matches = planned is None or (bool(info) and info.get("model") == planned["model"] and info.get("effort") == planned["effort"] and
                                              (planned.get("tier") is None or info.get("fast") == (planned.get("tier") == "priority")))
                cwd = info.get("cwd") or ""
                rows.append({"key": key, "host": host, "pane": row["pane"], "backend": row.get("backend"), "profile": profile,
                             "account": account.get("label"), "plan": account.get("plan"), "folder": cwd.rstrip("/").rsplit("/", 1)[-1] if cwd else None, "cwd": cwd or None,
                             "model": info.get("model"), "effort": info.get("effort"), "fast": info.get("fast"), "readable": bool(info),
                             "activity": row.get("activity"), "run_state": info.get("run_state"), "five_hour_left": info.get("five_hour_left"),
                             "weekly_left": info.get("weekly_left"), "credits": info.get("credits"), "on_credits": credits,
                             "status": row.get("status"), "planned": planned, "own": (own or {}).get("name"), "matches": matches,
                             "observed_at": value.get("at"), "move_to": (suggested.get(key) or {}).get("to"),
                             "move_to_label": (suggested.get(key) or {}).get("to_label"), "move_status": (suggested.get(key) or {}).get("status"),
                             "moved": moved[key] if key in moved and fm.safe_profile(moved[key].get("to") or "") == profile else None,
                             "last_move": (state.get("move_attempts") or {}).get(key)})
        return {"at": live.get("at"), "rows": rows, "errors": {host: value.get("error") for host, value in (live.get("hosts") or {}).items() if value.get("error")}}

    def publish_snapshot(self, force=False):
        files = [self.store.state_path, self.store.events_path, self.store.usage_path, boost_agent.runs_path(self.store), boost_lifecycle.sessions_path(self.store)]
        signature = tuple(path.stat().st_mtime_ns if path.exists() else 0 for path in files)
        if force or signature != self.signature:
            self.signature = signature
            try:
                self.hub.publish("snapshot", self.snapshot())
            except Exception:
                traceback.print_exc()

    # ------------------------------------------------------------ jobs

    def run_job(self, kind, label, work, quiet=False):
        # A background read never blocks a human's click: wait up to 30 s for it to finish.
        for _ in range(120):
            current = self.job
            if not (current and current.get("quiet") and not quiet):
                break
            time.sleep(0.25)
        with self.job_lock:
            if self.job:
                raise ValueError(f"busy: {self.job['label']} is running")
            self.job = {"id": secrets.token_hex(4), "kind": kind, "label": label, "status": "running", "started_at": boost_lifecycle.iso(boost_lifecycle.now()),
                        "hosts": {}, "quiet": quiet}
        self.hub.publish("job", self.job)

        def progress(host, event):
            entry = self.job["hosts"].setdefault(host, {"stage": "start", "panes": 0, "done": 0})
            stage = event.get("stage")
            if stage == "panes":
                entry["panes"] = event.get("count", 0)
            elif stage == "pane":
                entry["done"] += 1
            if stage != "pane":
                entry["stage"] = stage
            if stage == "done":
                entry["summary"] = event.get("summary")
            if stage == "error":
                entry["error"] = event.get("error")
            self.hub.publish("progress", {"job": self.job["id"], "host": host, "event": event})

        def body():
            boost_lifecycle.progress_hook = progress
            status, detail = "done", None
            try:
                with self.store.lock(wait=True):
                    detail = work()
            except Exception as error:
                status, detail = "failed", type(error).__name__ + ": " + str(error)[:300]
                traceback.print_exc()
            finally:
                boost_lifecycle.progress_hook = None
                self.job.update(status=status, finished_at=boost_lifecycle.iso(boost_lifecycle.now()), detail=detail)
                self.last_job, self.job = self.job, None
                self.hub.publish("job", self.last_job)
                if not quiet:
                    boost_lifecycle.render(self.fm, self.config, self.store)
                self.publish_snapshot(force=True)

        threading.Thread(target=body, daemon=True, name="reset-boost-job-" + kind).start()
        return self.job

    def call(self, handler, **fields):
        """Run a CLI command function with an argparse-like namespace."""
        defaults = {"quiet": True, "hosts": None, "dry_run": False, "converge": True, "force_audit": False, "even_if_served": True}
        return handler(self.fm, argparse.Namespace(**dict(defaults, **fields)), self.config, self.store)

    # ------------------------------------------------------------ actions

    def action(self, name, body):
        fb = boost_lifecycle
        if name == "boost":
            fields = {"preset": body.get("preset") or None, "model": body.get("model") or None, "effort": body.get("effort") or None,
                      "tier": body.get("tier") or None, "exclude": body.get("exclude") or [], "until": body.get("until") or None,
                      "ceiling": body.get("ceiling"), "quorum": body.get("quorum"), "no_auto_down": body.get("down") in ("manual", "until") or not body.get("auto_reset", True),
                      "no_live": False, "interrupt_current_turn": False, "note": body.get("note") or None,
                      "rehome": None if body.get("rehome") is None else bool(body.get("rehome"))}
            if fields["preset"]:
                fields["model"] = fields["effort"] = None
            name_ = fields["preset"] or f"{fields['model']} {fields['effort']}"
            return self.run_job("boost", "Boost to " + name_, lambda: self.call(fb.cmd_boost, **fields))
        if name == "done":
            return self.run_job("done", "Turn down", lambda: self.call(fb.cmd_done, reason=body.get("reason") or "operator: done (panel)"))
        if name == "tick":
            return self.run_job("tick", "Tick", lambda: self.call(fb.cmd_watch))
        if name == "audit":
            return self.run_job("audit", "Check every host", lambda: self.call(fb.cmd_watch, force_audit=True) if self.store.load().get("phase", "idle") == "idle"
                                else self.call(fb.cmd_converge))
        if name == "converge":
            hosts = body.get("hosts")
            return self.run_job("converge", "Converge " + (hosts or "all hosts"), lambda: self.call(fb.cmd_converge, hosts=hosts))
        if name == "pane":
            host, pane, interrupt = body["host"], body["pane"], bool(body.get("interrupt"))
            label = ("Interrupt and switch " if interrupt else "Retry ") + f"{host} {pane}"
            return self.run_job("pane", label, lambda: self.call(fb.cmd_pane, host=host, pane=pane, interrupt=interrupt))
        if name == "move":
            host, pane, interrupt = body["host"], body["pane"], bool(body.get("interrupt"))
            to = body.get("to") or None
            label = f"Move {host} {pane}" + (f" to {to}" if to else "")
            return self.run_job("move", label, lambda: self.call(fb.cmd_move, host=host, pane=pane, to=to, interrupt=interrupt))
        if name == "rehome":
            interrupt = bool(body.get("interrupt"))
            return self.run_job("rehome", "Move sessions on credits", lambda: self.call(fb.cmd_rehome, apply=True, interrupt=interrupt, json=False))
        if name == "channel":
            fields = {"profile": body["profile"], "setting": body["setting"], "effort": body.get("effort"), "preset": body.get("preset"),
                      "tier": body.get("tier"), "no_apply": False}
            return self.run_job("channel", f"{body['profile']}: {body.get('preset') or body['setting']}", lambda: self.call(fb.cmd_channel, **fields))
        if name == "rules":
            fields = {key: body.get(key) for key in ("reset", "quorum", "drop_points", "ceiling", "until")}
            with self.store.lock(wait=True):
                self.call(fb.cmd_rules, **fields)
            return {"ok": True}
        if name == "autopilot":
            with self.store.lock(wait=True):
                state = self.store.load()
                current = state.get("autopilot") or {}
                for key in ("mode", "after_minutes", "max_per_hour", "allow_interrupt"):
                    if key in body:
                        current[key] = body[key]
                if current.get("mode") not in (None, "off", "suggest", "auto"):
                    raise ValueError("mode must be off, suggest or auto")
                state["autopilot"] = current
                self.store.save(state)
                self.store.event("autopilot", **current)
            return {"ok": True}
        if name == "loop":
            with self.store.lock(wait=True):
                state = self.store.load()
                loop = state.get("loop") or {}
                if "tick_minutes" in body:
                    loop["tick_minutes"] = max(2, min(120, int(body["tick_minutes"])))
                if "observe_seconds" in body:
                    loop["observe_seconds"] = max(20, min(900, int(body["observe_seconds"])))
                state["loop"] = loop
                self.store.save(state)
            self.next_tick = min(self.next_tick, time.time() + loop.get("tick_minutes", 10) * 60)
            return {"ok": True}
        if name == "agent":
            state = self.store.load()
            signal = None
            if body.get("signal"):
                items = boost_agent.track(self.store, boost_agent.signals(state, boost_lifecycle.latest_report(state), state.get("usage_error")))
                signal = next((item for item in items if item["id"] == body["signal"]), None)
                if signal is None:
                    raise ValueError("that signal has already cleared")
            return boost_agent.start(self.config, self.store, state, signal=signal, request=body.get("request"), on_change=self.publish_snapshot)
        if name == "usage":
            self.refresh_usage()
            return {"ok": True}
        if name == "observe":
            return self.run_job("observe", "Read every session", lambda: self.call(fb.cmd_observe))
        if name == "session":
            keys = [str(key) for key in body.get("sessions") or []]
            if not keys or len(keys) > 200:
                raise ValueError("choose 1-200 sessions")
            fields = {"sessions": keys, "setting": body.get("setting") or body.get("model") or "follow", "effort": body.get("effort"),
                      "preset": body.get("preset"), "tier": body.get("tier"), "interrupt": bool(body.get("interrupt"))}
            verb = "Follow fleet" if fields["setting"] == "follow" else ("Interrupt and set " if fields["interrupt"] else "Set ")
            return self.run_job("session", f"{verb}{'' if fields['setting'] == 'follow' else ''} {len(keys)} session(s)", lambda: self.call(fb.cmd_session, **fields))
        if name == "guard":
            with self.store.lock(wait=True):
                state = self.store.load()
                guard = state.get("credit_guard") or {}
                if "enabled" in body:
                    guard["enabled"] = bool(body["enabled"])
                if "floor" in body:
                    guard["floor"] = max(0.0, min(50.0, float(body["floor"])))
                state["credit_guard"] = guard
                if "rehome_auto" in body:
                    state["rehome"] = dict(state.get("rehome") or {}, auto=bool(body["rehome_auto"]))
                    self.store.event("rehome_setting", auto=bool(body["rehome_auto"]))
                self.store.save(state)
                self.store.event("credit_guard", **guard)
            return {"ok": True}
        raise ValueError("unknown action " + name)

    # ------------------------------------------------------------ loops

    def refresh_usage(self):
        accounts, error = boost_lifecycle.fetch_usage(self.config)
        if accounts is not None:
            self.store.usage_path.write_text(json.dumps({"at": boost_lifecycle.iso(boost_lifecycle.now()), "accounts": accounts}, indent=2) + "\n")
            # The reset is the event: come down on the read that shows it, not on the next scheduled tick.
            state = self.store.load()
            if self.loop and state.get("phase") == "boosted" and state.get("auto_down", {}).get("reset", True):
                reason, _, _ = boost_lifecycle.evaluate(state, accounts)
                if reason:
                    self.store.event("reset_seen", reason=reason)
                    self.next_tick = time.time()

    def watch_host(self, host):
        """Re-read one host's sessions continuously; each read reaches the page as soon as it lands."""
        while True:
            live = (self.store.load().get("loop") or {}).get("live_seconds", self.config.get("live_seconds", 5))
            if self.loop and live:
                try:
                    boost_lifecycle.observe_hosts(self.fm, self.config, self.store, [host])
                except Exception:
                    traceback.print_exc()
            time.sleep(max(2, live or 30))

    def background(self):
        last_usage = 0
        last_autopilot = 0
        last_observe = 0
        for host in self.config["hosts"]:
            threading.Thread(target=self.watch_host, args=(host,), name="live-" + host, daemon=True).start()
        while True:
            try:
                self.publish_snapshot()
                stamp = time.time()
                (self.store.dir / "serve.json").write_text(json.dumps({"pid": os.getpid(), "port": self.options.port, "loop": self.loop,
                                                                       "at": boost_lifecycle.iso(boost_lifecycle.now())}))
                observe_every = (self.store.load().get("loop") or {}).get("observe_seconds", self.config.get("observe_seconds", 60))
                live = (self.store.load().get("loop") or {}).get("live_seconds", self.config.get("live_seconds", 5))
                if not live and self.loop and not self.job and stamp - last_observe > observe_every and stamp < self.next_tick - 30:
                    last_observe = stamp
                    try:
                        self.run_job("observe", "Reading sessions", lambda: self.call(boost_lifecycle.cmd_observe), quiet=True)
                    except ValueError:
                        pass
                if stamp - last_usage > self.config.get("usage_poll_seconds", 60):
                    last_usage = stamp
                    threading.Thread(target=self.refresh_usage, daemon=True).start()
                if self.loop and stamp >= self.next_tick and not self.job:
                    minutes = (self.store.load().get("loop") or {}).get("tick_minutes", self.config.get("tick_minutes", 10))
                    self.next_tick = stamp + minutes * 60
                    try:
                        self.run_job("tick", "Scheduled tick", lambda: self.call(boost_lifecycle.cmd_watch))
                    except ValueError:
                        pass
                if self.loop and stamp - last_autopilot > 30:
                    last_autopilot = stamp
                    self.autopilot()
            except Exception:
                traceback.print_exc()
            time.sleep(1)

    def autopilot(self):
        state = self.store.load()
        items = boost_agent.track(self.store, boost_agent.signals(state, boost_lifecycle.latest_report(state), state.get("usage_error")))
        for item in boost_agent.due(state, self.config, items, boost_agent.load_runs(self.store)):
            try:
                boost_agent.start(self.config, self.store, state, signal=item, on_change=self.publish_snapshot)
            except ValueError:
                return


def make_handler(panel, allowed_hosts):
    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "reset-boost"

        def log_message(self, *args):
            pass

        def local(self):
            return self.headers.get("Host", "") in allowed_hosts

        def authorized(self, query=None):
            supplied = self.headers.get("X-Reset-Boost-Token") or ((query or {}).get("t") or [""])[0]
            return self.local() and hmac.compare_digest(supplied, panel.token)

        def send_json(self, code, value):
            body = json.dumps(value, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            query = parse_qs(url.query)
            if not self.local():
                return self.send_json(403, {"error": "local access only"})
            if url.path in ("/", "/index.html"):
                body = CONSOLE.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            if url.path == "/operator-ui.css":
                body = STYLES.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/css; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            if not self.authorized(query):
                return self.send_json(401, {"error": "token required"})
            if url.path == "/api/state":
                return self.send_json(200, panel.snapshot())
            if url.path == "/api/stream":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                channel = panel.hub.subscribe()
                try:
                    self.wfile.write(f"event: snapshot\ndata: {json.dumps(panel.snapshot(), default=str)}\n\n".encode())
                    self.wfile.flush()
                    while True:
                        try:
                            message = channel.get(timeout=15)
                        except queue.Empty:
                            message = ": keepalive\n\n"
                        self.wfile.write(message.encode())
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    panel.hub.unsubscribe(channel)
                return None
            return self.send_json(404, {"error": "not found"})

        def do_POST(self):
            url = urlparse(self.path)
            if not self.authorized():
                return self.send_json(401, {"error": "token required"})
            if not url.path.startswith("/api/"):
                return self.send_json(404, {"error": "not found"})
            try:
                length = min(int(self.headers.get("Content-Length") or 0), 65536)
                body = json.loads(self.rfile.read(length) or b"{}")
                result = panel.action(url.path[len("/api/"):], body)
                panel.publish_snapshot(force=True)
                return self.send_json(200, {"ok": True, "result": result})
            except (ValueError, KeyError) as error:
                return self.send_json(400, {"error": str(error)})
    return Handler


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        # A browser closing a tab mid-response is normal; log only real failures.
        if not isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError, TimeoutError)):
            super().handle_error(request, client_address)


def serve(fm, config, store, options):
    # `kill -USR1 <pid>` writes every thread's stack to the log: enough to diagnose a hang.
    if hasattr(signal, "SIGUSR1"):
        faulthandler.register(signal.SIGUSR1, all_threads=True)
    panel = Panel(fm, config, store, options)
    server = ThreadingServer((options.bind, options.port), None)
    # Port 0 asks the OS for a free port; the Host check and the link use the bound one.
    port = options.port = server.server_address[1]
    server.RequestHandlerClass = make_handler(panel, {f"{name}:{port}" for name in ("127.0.0.1", "localhost", options.bind)})
    url = f"http://127.0.0.1:{port}/#t={panel.token}"
    write_private(store.dir / "serve-url", url + "\n")
    print("Control panel: " + url, flush=True)
    threading.Thread(target=panel.background, daemon=True, name="reset-boost-loop").start()
    if getattr(options, "open", False):
        opener = ["open", url] if sys.platform == "darwin" else ["xdg-open", url]
        try:
            # The loop thread is running: posix_spawn, never fork (see fm.spawnable).
            fm.run_process(opener, check=False)
        except OSError:
            print("Open the link above in a browser.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
