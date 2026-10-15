"""Provider-free tests for the control panel: channels, pane retry, signals, the agent hand-off and the local server."""
import http.client
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
import reset_boost as fm  # noqa: E402
import boost_agent  # noqa: E402
import boost_lifecycle  # noqa: E402
import boost_server  # noqa: E402

SOL = {"model": "gpt-6.1-sol", "effort": "medium", "tier": "default"}
ASTRA_HIGH = {"model": "gpt-6-astra", "effort": "high", "tier": "default"}


def account(profile, used):
    return {"account_id": "acct-" + profile, "display_name": profile + "@example.test", "provider": "codex", "plan": "team",
            "observed_by_profile": profile, "windows": [{"key": "weekly", "used_percent": used, "window_seconds": 604800, "resets_at": "2026-10-20T00:00:00Z"}]}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "usage.json").write_text(json.dumps({"accounts": [account(p, 40) for p in ("pro-1", "team-a", "team-b")]}))
        self.config = {"hosts": {"local": {"type": "local"}, "box": {"type": "ssh"}}, "baseline": "normal", "exclude_profiles": ["pro-1"],
                       "usage": {"type": "file", "path": str(self.root / "usage.json"), "provider": "codex"}, "dashboard": str(self.root / "dash.html"),
                       "agent": {"steps": [[sys.executable, "-c", "import sys; print('FOUND: brief has', len(sys.stdin.read()), 'chars')"]]}}
        (self.root / "config.json").write_text(json.dumps(self.config))
        self.env = patch.dict(os.environ, {"RESET_BOOST_CONFIG": str(self.root / "config.json"), "RESET_BOOST_STATE_DIR": str(self.root / "state")})
        self.env.start()
        self.calls = []
        fake = types.SimpleNamespace(**{name: getattr(fm, name) for name in dir(fm) if not name.startswith("__")})
        fake.run_fleet = self.run_fleet
        self.fm = fake

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def run_fleet(self, config, hosts, target, **options):
        self.calls.append(dict(options, hosts=hosts, target=target))
        progress = options.get("progress") or (lambda host, event: None)
        report = {"created_at": boost_lifecycle.iso(boost_lifecycle.now()), "label": options.get("label"), "hosts": {}}
        for host in hosts:
            progress(host, {"stage": "start"})
            rows = [{"backend": "tmux", "user": "u", "pane": "%1", "profile": "team-a", "observed": ["gpt-6-astra", "high"], "status": "held_working"},
                    {"backend": "tmux", "user": "u", "pane": "%2", "profile": "team-b", "observed": ["gpt-6.1-sol", "medium"], "status": "verified"}]
            only = options.get("only_panes")
            if isinstance(only, dict):
                only = only.get(host, [])
            if only:
                rows = [dict(row, status="verified", observed=["gpt-6.1-sol", "medium"]) for row in rows if row["pane"] in only]
            for row in rows:
                progress(host, {"stage": "pane", "row": row})
            report["hosts"][host] = {"configs": [], "errors": [], "launch_overrides": [], "terminals": rows}
            progress(host, {"stage": "done", "summary": fm.host_summary(report["hosts"][host])})
        if options.get("save") is False:
            return report
        path = self.root / f"report-{len(self.calls)}.json"
        path.write_text(json.dumps(report))
        return dict(report, _path=str(path))

    def cli(self, *argv):
        with patch("sys.stdout"):
            return boost_lifecycle.main(list(argv), self.fm)

    def state(self):
        return json.loads((self.root / "state/boost.json").read_text())


@unittest.skipIf(fm.tomllib is None, "the worker needs Python 3.11+ (tomllib)")
class WorkerProgressTests(unittest.TestCase):
    def test_only_panes_skips_configs_and_streams_each_session(self):
        found = [{"backend": "tmux", "pane": "%1"}, {"backend": "tmux", "pane": "%2"}]
        events = []
        with patch.object(fm, "terminals", return_value=(found, [])), patch.object(fm, "config_paths", side_effect=AssertionError("configs read")), \
                patch.object(fm, "live_setting", side_effect=lambda terminal, args: {"pane": terminal["pane"], "status": "verified"}):
            result = fm.worker({"model": "m", "effort": "high", "only_panes": ["%2"]}, events.append)
        self.assertEqual([row["pane"] for row in result["terminals"]], ["%2"])
        self.assertEqual(result["configs"], [])
        self.assertEqual([event["stage"] for event in events], ["panes", "pane"])

    def test_remote_progress_lines_go_to_stderr_only(self):
        with patch("sys.stderr") as stderr:
            fm.stderr_emit({"stage": "panes", "count": 2})
        line = stderr.write.call_args[0][0]
        self.assertTrue(line.startswith(fm.PROGRESS_PREFIX))
        self.assertEqual(json.loads(line[len(fm.PROGRESS_PREFIX):]), {"stage": "panes", "count": 2})


class ChannelTests(Fixture):
    def test_solo_pin_and_follow(self):
        self.cli("channel", "team-a", "astra-high")
        state = self.state()
        self.assertEqual(state["channels"]["team-a"]["mode"], "custom")
        self.assertEqual(self.calls[-1]["profiles"], {"team-a": ASTRA_HIGH})  # idle: only the solo account moves
        self.assertEqual(self.calls[-1]["target"], SOL)
        self.cli("channel", "team-b", "pin")
        self.cli("boost", "--preset", "astra-ultra")
        profiles = self.calls[-1]["profiles"]
        self.assertEqual(profiles["team-a"], ASTRA_HIGH)
        self.assertEqual(profiles["team-b"], SOL)
        self.assertEqual(profiles["pro-1"], SOL)
        self.cli("done")
        state = self.state()
        self.assertNotIn("team-a", state["channels"])  # solo cleared on turn-down
        self.assertEqual(state["channels"]["team-b"], {"mode": "pin"})  # pins stay
        self.assertEqual(self.calls[-1]["profiles"], {})
        self.cli("channel", "team-b", "follow")
        self.assertNotIn("team-b", self.state()["channels"])

    def test_bad_profile_rejected(self):
        with self.assertRaises(SystemExit):
            with patch("sys.stderr"):
                self.cli("channel", "../x", "pin")


class PaneAndSignalTests(Fixture):
    def test_pane_retry_merges_into_latest_report(self):
        self.cli("boost", "--preset", "astra-high")
        code = self.cli("pane", "local", "%1")
        self.assertEqual(code, 0)
        self.assertEqual(self.calls[-1]["only_panes"], {"local": ["%1"]})
        report = json.loads(Path(self.state()["last_report"]).read_text())
        statuses = {row["pane"]: row["status"] for row in report["hosts"]["local"]["terminals"]}
        self.assertEqual(statuses, {"%1": "verified", "%2": "verified"})

    def test_signals_from_a_cooling_report(self):
        state = {"phase": "cooling", "boost_target": ASTRA_HIGH, "baseline_target": SOL}
        report = {"hosts": {
            "a": {"configs": [], "terminals": [], "errors": [{"error": "unreachable: timed out after 300s"}]},
            "b": {"configs": [{"path": "/x", "status": "would_change"}], "errors": [], "terminals": [
                {"pane": "%1", "backend": "tmux", "profile": "team-a", "observed": ["gpt-6-astra", "high"], "status": "held_working"},
                {"pane": "%2", "backend": "tmux", "profile": None, "observed": None, "status": "held_profile_unknown"},
                {"pane": "%3", "backend": "tmux", "profile": "team-b", "observed": ["gpt-6.1-sol", "high"], "status": "held_picker_unavailable"}]}}}
        codes = [item["code"] for item in boost_agent.signals(state, report)]
        self.assertEqual(codes[0], "HOST_UNREACHABLE")
        self.assertEqual(set(codes[1:3]), {"PANE_SWITCH_FAILED", "STILL_BOOSTED"})
        self.assertIn("CONFIG_PENDING", codes)
        self.assertIn("PANE_ACCOUNT_UNKNOWN", codes)
        idle = boost_agent.signals(dict(state, phase="idle"), {"hosts": {"b": {"configs": [], "errors": [], "terminals": [
            {"pane": "%9", "backend": "tmux", "profile": "x", "observed": ["gpt-6.1-sol", "high"], "status": "live_mismatch"}]}}})
        self.assertEqual([item["code"] for item in idle], ["DRIFT"])


class AgentTests(Fixture):
    def test_agent_run_records_result_and_brief(self):
        store = boost_lifecycle.Store(self.fm)
        state = {"phase": "boosted", "boost_target": ASTRA_HIGH, "baseline_target": SOL, "exclude": ["pro-1"], "channels": {}}
        signal = {"id": "abc", "code": "STILL_BOOSTED", "title": "t", "severity": "bad", "host": "build-1", "subject": "tmux %1", "detail": "d", "evidence": {"pane": "%1"}}
        run = boost_agent.start(self.config, store, state, signal=signal, wait=True)
        runs = boost_agent.load_runs(store)
        self.assertEqual(runs[-1]["status"], "done")
        self.assertIn("FOUND: brief has", runs[-1]["result"])
        text = Path(run["brief"]).read_text()
        self.assertIn("Never turn anything UP", text)
        self.assertIn("Do not interrupt a running turn", text)
        self.assertIn("STILL_BOOSTED", text)

    def test_autopilot_due_respects_mode_age_and_budget(self):
        old = "2000-01-01T00:00:00Z"
        items = [{"id": str(i), "code": "PANE_SWITCH_FAILED", "first_seen": old} for i in range(5)] + [{"id": "x", "code": "PANE_BUSY", "first_seen": old}]
        state = {"autopilot": {"mode": "suggest"}}
        self.assertEqual(boost_agent.due(state, self.config, items, []), [])
        state["autopilot"]["mode"] = "auto"
        picked = boost_agent.due(state, self.config, items, [])
        self.assertEqual(len(picked), 3)  # max_per_hour default
        self.assertNotIn("x", [item["id"] for item in picked])  # busy sessions are not agent work by default
        fresh = [dict(items[0], first_seen=boost_agent.iso(boost_agent.now()))]
        self.assertEqual(boost_agent.due(state, self.config, fresh, []), [])
        self.assertEqual(boost_agent.due(state, dict(self.config, agent={}), items, []), [])

    def test_failed_agent_command_is_reported(self):
        store = boost_lifecycle.Store(self.fm)
        config = dict(self.config, agent={"steps": [[sys.executable, "-c", "import sys; sys.exit(3)"]]})
        boost_agent.start(config, store, {"phase": "idle", "baseline_target": SOL}, request="look at build-1", wait=True)
        self.assertEqual(boost_agent.load_runs(store)[-1]["status"], "failed")


class ServerTests(Fixture):
    def setUp(self):
        super().setUp()
        self.quiet = patch("sys.stdout", new=io.StringIO())  # job threads print CLI summaries
        self.quiet.start()
        self.addCleanup(self.quiet.stop)
        self.store = boost_lifecycle.Store(self.fm)
        options = types.SimpleNamespace(port=0, bind="127.0.0.1", no_loop=True, open=False)
        self.panel = boost_server.Panel(self.fm, fm.load_config(), self.store, options)
        self.server = boost_server.ThreadingServer(("127.0.0.1", 0), None)
        port = self.server.server_address[1]
        self.server.RequestHandlerClass = boost_server.make_handler(self.panel, {f"127.0.0.1:{port}", f"localhost:{port}"})
        self.port = port
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        super().tearDown()

    def request(self, method, path, body=None, token=True, host=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Content-Type": "application/json", "Host": host or f"127.0.0.1:{self.port}"}
        if token:
            headers["X-Reset-Boost-Token"] = self.panel.token
        connection.request(method, path, json.dumps(body) if body is not None else None, headers)
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response.status, data

    def wait_idle(self):
        for _ in range(100):
            if not self.panel.job:
                return
            time.sleep(0.05)
        self.fail("job did not finish")

    def test_security_boundaries(self):
        self.assertEqual(self.request("GET", "/")[0], 200)
        self.assertEqual(self.request("GET", "/api/state", token=False)[0], 401)
        self.assertEqual(self.request("GET", "/api/state", host="evil.example:80")[0], 403)
        self.assertEqual(self.request("POST", "/api/done", {}, token=False)[0], 401)
        self.assertEqual((self.store.dir / "serve-token").stat().st_mode & 0o777, 0o600)

    def test_state_boost_and_turn_down_through_the_api(self):
        status, data = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        snapshot = json.loads(data)
        self.assertEqual(snapshot["phase"], "idle")
        self.panel.refresh_usage()
        snapshot = json.loads(self.request("GET", "/api/state")[1])
        modes = {row["profile"]: row["mode"] for row in snapshot["accounts"]}
        self.assertEqual(modes["pro-1"], "locked")
        status, data = self.request("POST", "/api/boost", {"preset": "astra-high", "note": "test", "auto_reset": True, "quorum": 0.5})
        self.assertEqual(status, 200, data)
        self.wait_idle()
        self.assertEqual(self.store.load()["phase"], "boosted")
        self.assertEqual(self.panel.last_job["status"], "done")
        self.assertEqual(self.panel.last_job["hosts"]["local"]["stage"], "done")
        signals = json.loads(self.request("GET", "/api/state")[1])["signals"]
        self.assertTrue(any(item["code"] == "PANE_BUSY" for item in signals))
        self.assertEqual(self.request("POST", "/api/rules", {"ceiling": "90", "until": "2h"})[0], 200)
        self.assertEqual(self.store.load()["auto_down"]["ceiling"], 90.0)
        self.assertEqual(self.request("POST", "/api/autopilot", {"mode": "auto", "max_per_hour": 2})[0], 200)
        self.assertEqual(self.store.load()["autopilot"]["mode"], "auto")
        self.assertEqual(self.request("POST", "/api/autopilot", {"mode": "wild"})[0], 400)
        self.assertEqual(self.request("POST", "/api/done", {})[0], 200)
        self.wait_idle()
        self.assertEqual(self.store.load()["phase"], "cooling")
        self.assertEqual(self.request("POST", "/api/nonsense", {})[0], 400)

    def test_stream_starts_with_a_snapshot(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        connection.request("GET", "/api/stream?t=" + self.panel.token, headers={"Host": f"127.0.0.1:{self.port}"})
        response = connection.getresponse()
        self.assertEqual(response.getheader("Content-Type"), "text/event-stream")
        first = response.fp.readline().decode()
        self.assertEqual(first.strip(), "event: snapshot")
        self.assertIn('"phase"', response.fp.readline().decode())
        connection.close()


class SessionTests(Fixture):
    def test_session_override_targets_only_that_pane_and_follow_undoes_it(self):
        code = self.cli("session", "astra", "local|%1", "--effort", "high", "--tier", "fast")
        self.assertEqual(code, 0)
        want = {"model": "gpt-6-astra", "effort": "high", "tier": "priority"}
        self.assertEqual(self.state()["sessions"]["local|%1"]["target"], want)
        call = self.calls[-1]
        self.assertEqual(call["only_panes"], {"local": ["%1"]})
        self.assertEqual(call["pane_targets"], {"local": {"%1": want}})
        self.assertEqual(call["hosts"], ["local"])
        self.cli("session", "follow", "local|%1")
        self.assertEqual(self.state()["sessions"], {})
        with self.assertRaises(SystemExit), patch("sys.stderr"):
            self.cli("session", "astra", "nowhere|%1", "--effort", "high")

    def test_turning_down_clears_session_overrides(self):
        self.cli("boost", "--preset", "astra-high")
        self.cli("session", "luna", "local|%2", "--effort", "high")
        self.assertIn("local|%2", self.state()["sessions"])
        self.cli("done")
        self.assertEqual(self.state()["sessions"], {})

    def test_observe_changes_nothing_and_records_telemetry(self):
        self.assertEqual(self.cli("observe"), 0)
        call = self.calls[-1]
        self.assertTrue(call["observe"])
        self.assertFalse(call.get("apply"))
        recorded = json.loads((self.root / "state/sessions.json").read_text())
        self.assertEqual(sorted(recorded["hosts"]), ["box", "local"])

    def test_exhausted_accounts_stay_at_baseline_and_the_panel_switch_wins(self):
        state = {"phase": "boosted", "boost_target": ASTRA_HIGH, "baseline_target": SOL, "boost_name": "astra-high", "exclude": []}
        _, profiles, hold, _ = boost_lifecycle.plan(state, {"team-a"})
        self.assertEqual(profiles["team-a"], SOL)
        self.assertTrue(hold)
        store = boost_lifecycle.Store(self.fm)
        extra, _ = boost_lifecycle.fleet_options(self.fm, self.config, store, dict(state, credit_guard={"enabled": False}))
        self.assertFalse(extra["credit_guard"]["enabled"])


class StyleTests(unittest.TestCase):
    def test_stylesheet_matches_the_collection_kit(self):
        kit = SKILL.parents[1] / "docs/design/operator-ui.css"
        if kit.exists():  # absent in an exported skill folder
            self.assertEqual((SKILL / "assets/operator-ui.css").read_text(), kit.read_text())

    def test_console_uses_tokens_not_raw_colours(self):
        import re
        page = (SKILL / "assets/console.html").read_text()
        style = page.split("<style>")[1].split("</style>")[0]
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", style), [])
        self.assertNotRegex(style, r"rgba?\(|hsla?\(")

    def test_server_serves_the_stylesheet_beside_the_console(self):
        self.assertEqual(boost_server.STYLES.name, "operator-ui.css")
        self.assertTrue(boost_server.STYLES.is_file())
        self.assertIn('href="/operator-ui.css"', boost_server.CONSOLE.read_text())


if __name__ == "__main__":
    unittest.main()
