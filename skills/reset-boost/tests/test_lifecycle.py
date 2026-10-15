"""Provider-free tests for usage normalisation, reset detection, the boost lifecycle and the dashboard."""
import datetime as dt
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
import reset_boost as rb  # noqa: E402
import boost_lifecycle  # noqa: E402
import boost_dashboard  # noqa: E402

ASTRA = {"model": "gpt-6-astra", "effort": "ultra", "tier": "priority"}
SOL = {"model": "gpt-6.1-sol", "effort": "medium", "tier": "default"}


def account(profile, used, resets_at, provider="codex", status="current"):
    """One account in the generic usage contract, plus optional account-manager fields."""
    return {"account_id": "acct-" + profile, "display_name": profile, "provider": provider, "plan": "team",
            "observed_by_profile": profile, "usage_status": status, "execution_status": "ready",
            "fleet_cells": [{"provider": provider, "profile": profile, "host_id": "build-1"}],
            "windows": [{"key": "session", "used_percent": 5, "window_seconds": 18000, "resets_at": "2026-10-15T03:00:00Z"},
                        {"key": "weekly", "used_percent": used, "window_seconds": 604800, "resets_at": resets_at}]}


class UsageContractTests(unittest.TestCase):
    def test_documented_example_file_normalizes(self):
        raw = json.loads((SKILL / "assets/usage.example.json").read_text())
        accounts = boost_lifecycle.normalize_usage(raw)
        self.assertGreaterEqual(len(accounts), 3)
        for value in accounts.values():
            self.assertEqual(boost_lifecycle.primary_window(value)[0], "weekly")
            self.assertIsNotNone(value["profile"])

    def test_minimal_shape_and_extra_fields(self):
        minimal = {"accounts": [{"id": "a1", "profile": "team-a", "windows": [{"key": "monthly", "used_percent": 40, "resets_at": None, "window_seconds": 2592000},
                                                                              {"key": "session", "used_percent": 90, "window_seconds": 18000}]}]}
        accounts = boost_lifecycle.normalize_usage(minimal)
        self.assertEqual(boost_lifecycle.primary_window(accounts["a1"])[0], "monthly")
        self.assertEqual(boost_lifecycle.normalize_usage(minimal["accounts"]).keys(), accounts.keys())
        raw = {"accounts": [account("team-b", 40, "2026-10-20T00:00:00Z"), account("x", 10, None, provider="other"),
                            account("off", 0, None, status="policy_disabled")]}
        accounts = boost_lifecycle.normalize_usage(raw, "codex")
        self.assertEqual(sorted(accounts), ["acct-off", "acct-team-b"])
        self.assertEqual(accounts["acct-team-b"]["profile"], "team-b")
        self.assertTrue(accounts["acct-off"]["disabled"])

    def test_reset_signals(self):
        before = {"window": "weekly", "used": 70.0, "resets_at": "2026-10-20T00:00:00Z"}
        same = {"windows": {"weekly": {"used": 75.0, "resets_at": "2026-10-20T00:00:00Z"}}}
        rolled = {"windows": {"weekly": {"used": 72.0, "resets_at": "2026-10-27T00:00:00Z"}}}
        dropped = {"windows": {"weekly": {"used": 3.0, "resets_at": "2026-10-20T00:00:00Z"}}}
        self.assertIsNone(boost_lifecycle.reset_signal(before, same, 15))
        self.assertEqual(boost_lifecycle.reset_signal(before, rolled, 15), "window rolled over")
        self.assertIn("fell", boost_lifecycle.reset_signal(before, dropped, 15))

    def test_quorum_exclusions_ceiling_and_deadline(self):
        snap = {f"a{i}": {"label": f"a{i}", "profile": f"p{i}", "plan": "team", "disabled": False, "window": "weekly", "used": 60.0,
                          "resets_at": "2026-10-20T00:00:00Z"} for i in range(4)}
        state = {"snapshot": snap, "exclude": ["p3"], "auto_down": dict(boost_lifecycle.DEFAULT_AUTO_DOWN, ceiling=90.0)}

        def usage(values):
            return {f"a{i}": {"windows": {"weekly": {"used": value, "resets_at": "2026-10-20T00:00:00Z"}}} for i, value in enumerate(values)}

        reason, backs, rows = boost_lifecycle.evaluate(state, usage([65, 70, 95, 0]))
        self.assertIsNone(reason)  # the excluded account's drop does not count
        self.assertEqual(backs, {"p2": "usage 95% reached the 90% ceiling"})
        self.assertTrue(rows[3]["excluded"])
        reason, _, _ = boost_lifecycle.evaluate(state, usage([1, 2, 80, 80]))
        self.assertEqual(reason, "reset detected on 2/3 accounts")
        state["auto_down"]["until"] = "2000-01-01T00:00:00Z"
        self.assertEqual(boost_lifecycle.evaluate(state, usage([65, 70, 80, 80]))[0], "boost deadline reached")

    def test_until_parsing(self):
        start = dt.datetime(2026, 10, 15, tzinfo=dt.timezone.utc)
        self.assertEqual(boost_lifecycle.parse_until("6h", start), start + dt.timedelta(hours=6))
        self.assertEqual(boost_lifecycle.parse_until("2026-10-16T00:00:00Z", start), start + dt.timedelta(days=1))
        with self.assertRaises(ValueError):
            boost_lifecycle.parse_until("soon", start)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.usage = root / "usage.json"
        self.write_usage(60)
        config = {"hosts": {"local": {"type": "local"}, "build-1": {"type": "ssh"}}, "baseline": "normal", "exclude_profiles": ["team-a"],
                  "usage": {"type": "file", "path": str(self.usage), "provider": "codex"}, "dashboard": str(root / "dash/index.html")}
        (root / "config.json").write_text(json.dumps(config))
        self.env = patch.dict(os.environ, {"RESET_BOOST_CONFIG": str(root / "config.json"), "RESET_BOOST_STATE_DIR": str(root / "state")})
        self.env.start()
        self.calls = []
        self.exit = 2
        fake = types.SimpleNamespace(**{name: getattr(rb, name) for name in dir(rb) if not name.startswith("__")})
        fake.run_fleet = self.run_fleet
        fake.report_exit = lambda report: self.exit
        self.fm = fake
        self.stdout = patch("sys.stdout")
        self.stdout.start()

    def tearDown(self):
        self.stdout.stop()
        self.env.stop()
        self.directory.cleanup()

    def write_usage(self, used, resets="2026-10-20T00:00:00Z"):
        self.usage.write_text(json.dumps({"accounts": [account(p, used, resets) for p in ("team-a", "team-b", "pro-1")]}))

    def run_fleet(self, config, hosts, target, **options):
        self.calls.append({"hosts": hosts, "target": target, **options})
        path = Path(self.directory.name) / f"report-{len(self.calls)}.json"
        report = {"created_at": boost_lifecycle.iso(boost_lifecycle.now()), "hosts": {"local": {"configs": [], "errors": [], "launch_overrides": [], "terminals": [
            {"backend": "tmux", "user": "u", "pane": "%3", "profile": "team-b", "observed": ["gpt-6-astra", "ultra"], "status": "held_working"}]}}}
        path.write_text(json.dumps(report))
        report["_path"] = str(path)
        return report

    def cli(self, *argv):
        return boost_lifecycle.main(list(argv), self.fm)

    def state(self):
        return json.loads((Path(self.directory.name) / "state/boost.json").read_text())

    def test_boost_watch_autodown_and_cool(self):
        self.cli("boost", "--preset", "astra-ultra-fast", "--note", "reset window")
        state = self.state()
        self.assertEqual(state["phase"], "boosted")
        self.assertEqual(self.calls[-1]["target"], ASTRA)
        self.assertEqual(self.calls[-1]["profiles"], {"team-a": SOL})
        self.assertTrue(self.calls[-1]["hold_unknown"])
        self.assertEqual(len(state["snapshot"]), 3)

        self.cli("watch", "--quiet")  # nothing reset yet: converge the boost again
        self.assertEqual(self.state()["phase"], "boosted")
        self.assertEqual(self.calls[-1]["target"], ASTRA)

        self.write_usage(2)  # the provider reset landed
        self.cli("watch", "--quiet")
        state = self.state()
        self.assertEqual(state["phase"], "cooling")
        self.assertIn("reset detected", state["end_reason"])
        self.assertEqual(self.calls[-1]["target"], SOL)
        self.assertEqual(self.calls[-1]["profiles"], {})
        page = Path(self.directory.name, "dash/index.html").read_text()
        self.assertIn("STILL BOOSTED", page)

        self.exit = 0  # everything reachable now reads back at the baseline
        self.cli("watch", "--quiet")
        self.assertEqual(self.state()["phase"], "idle")
        events = [event["event"] for event in boost_lifecycle.Store(self.fm).events()]
        self.assertEqual(events[0], "boost")
        self.assertIn("done", events)
        self.assertEqual(events[-1], "idle")

    def test_dry_run_changes_nothing(self):
        self.cli("boost", "--preset", "astra-ultra-fast", "--dry-run")
        self.assertEqual(self.calls, [])
        self.assertFalse((Path(self.directory.name) / "state/boost.json").exists())

    def test_done_is_always_allowed_and_retune_keeps_snapshot(self):
        self.cli("done")
        self.assertEqual(self.state()["phase"], "cooling")
        self.assertEqual(self.calls[-1]["target"], SOL)
        self.cli("boost", "--preset", "sol-high")
        first = self.state()["snapshot"]
        self.write_usage(80)
        self.cli("boost", "--preset", "astra-high", "--exclude", "pro-1", "--until", "6h")
        state = self.state()
        self.assertEqual(state["snapshot"], first)
        self.assertEqual(state["exclude"], ["pro-1", "team-a"])
        self.assertIsNotNone(state["auto_down"]["until"])

    def test_dashboard_renders_without_any_run(self):
        self.cli("dashboard")
        page = Path(self.directory.name, "dash/index.html").read_text()
        self.assertIn("At baseline", page)
        self.assertIn("No run recorded yet", page)

    def test_dashboard_defaults_to_the_state_directory(self):
        config = json.loads(Path(os.environ["RESET_BOOST_CONFIG"]).read_text())
        del config["dashboard"]
        Path(os.environ["RESET_BOOST_CONFIG"]).write_text(json.dumps(config))
        self.cli("dashboard")
        self.assertTrue((Path(self.directory.name) / "state/dashboard.html").is_file())

    def test_unavailable_usage_never_changes_models(self):
        self.cli("boost", "--preset", "astra-ultra")
        self.usage.write_text("not json")
        calls = len(self.calls)
        self.cli("watch", "--quiet")
        state = self.state()
        self.assertEqual(state["phase"], "boosted")
        self.assertIn("JSONDecodeError", state["usage_error"])
        self.assertEqual(self.calls[-1]["target"]["model"], "gpt-6-astra")
        self.assertEqual(len(self.calls), calls + 1)

    def test_idle_watch_only_audits_read_only(self):
        self.cli("watch", "--quiet")
        self.assertEqual(len(self.calls), 1)
        self.assertNotIn("apply", self.calls[0])  # run_fleet's default is a preview
        self.assertEqual(self.calls[0]["target"], {"model": SOL["model"], "effort": SOL["effort"], "tier": SOL["tier"]})


class DashboardTests(unittest.TestCase):
    def test_cooling_flags_a_pane_still_on_the_boost_model(self):
        state = {"phase": "cooling", "boost_target": ASTRA, "baseline_target": SOL, "baseline_name": "normal"}
        report = {"hosts": {"build-1": {"errors": [], "configs": [], "launch_overrides": [], "terminals": [
            {"backend": "herdr", "pane": "w1:p2", "profile": "team-b", "observed": ["gpt-6-astra", "ultra"], "status": "held_working"},
            {"backend": "herdr", "pane": "w1:p3", "profile": "team-c", "observed": ["gpt-6.1-sol", "medium"], "status": "verified"}]}}}
        items = boost_dashboard.attention(state, report)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0][0], "bad")
        self.assertIn("STILL BOOSTED", items[0][3])
        page = boost_dashboard.render(state, {}, report, [], None, rb.presets(), {})
        self.assertIn("1/2", page)
        self.assertNotIn("<script src", page)
        self.assertNotIn("http://", page.replace("http://www.w3.org", ""))

    def test_values_are_escaped(self):
        state = {"phase": "boosted", "boost_target": ASTRA, "baseline_target": SOL, "note": "<img src=x onerror=alert(1)>", "snapshot": {}}
        page = boost_dashboard.render(state, {}, None, [], None, rb.presets(), {})
        self.assertNotIn("<img src=x", page)
        self.assertIn("&lt;img src=x", page)


class ExhaustedTests(unittest.TestCase):
    def test_a_full_window_past_its_reset_time_is_not_exhausted(self):
        past = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)).isoformat()
        future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)).isoformat()
        accounts = {"a": {"profile": "stale", "windows": {"session": {"used": 100, "resets_at": past}}},
                    "b": {"profile": "full", "windows": {"session": {"used": 100, "resets_at": future}}},
                    "c": {"profile": "undated", "windows": {"weekly": {"used": 100}}}}
        self.assertEqual(boost_lifecycle.exhausted_profiles(accounts), {"full", "undated"})


class RehomeTests(unittest.TestCase):
    """Sessions on credits move to an account with quota (Pro first) before a boost reaches them."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        future = "2026-12-20T00:00:00Z"

        def acct(profile, plan, used, **extra):
            return dict({"account_id": "acct-" + profile, "display_name": profile, "provider": "codex", "plan": plan, "observed_by_profile": profile,
                         "windows": [{"key": "weekly", "used_percent": used, "window_seconds": 604800, "resets_at": future}]}, **extra)
        (self.root / "usage.json").write_text(json.dumps({"accounts": [
            acct("pro-a", "pro", 54), acct("pro-b", "pro", 100), acct("ops@example.test", "team", 30), acct("team-b", "team", 90),
            acct("off", "pro", 0, usage_status="policy_disabled")]}))
        self.config = {"hosts": {"box": {"type": "ssh"}, "win": {"type": "windows"}}, "baseline": "normal",
                       "usage": {"type": "file", "path": str(self.root / "usage.json"), "provider": "codex"}, "dashboard": str(self.root / "dash.html"),
                       "rehome": {"auto": True, "prefer": ["pro-a"], "launch": "codex {profile} resume {thread}"}}
        (self.root / "config.json").write_text(json.dumps(self.config))
        self.env = patch.dict(os.environ, {"RESET_BOOST_CONFIG": str(self.root / "config.json"), "RESET_BOOST_STATE_DIR": str(self.root / "state")})
        self.env.start()
        self.order, self.move_status = [], "moved"
        fake = types.SimpleNamespace(**{name: getattr(rb, name) for name in dir(rb) if not name.startswith("__")})
        fake.run_fleet, fake.run_moves, fake.report_exit = self.run_fleet, self.run_moves, (lambda report: 0)
        self.fm = fake
        self.store = boost_lifecycle.Store(fake)
        self.write_sessions()
        with patch("sys.stdout"):
            boost_lifecycle.main(["status", "--refresh"], fake)
        self.store.usage_path.write_text(json.dumps({"at": boost_lifecycle.iso(boost_lifecycle.now()), "accounts": boost_lifecycle.fetch_usage(rb.load_config())[0]}))

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def write_sessions(self):
        rows = [{"backend": "tmux", "pane": "%1", "profile": "pro-b", "activity": "idle", "telemetry": {"model": "gpt-6.1-sol", "effort": "medium", "weekly_left": 0.0}},
                {"backend": "tmux", "pane": "%2", "profile": "ops_example.test", "activity": "idle", "telemetry": {"model": "gpt-6.1-sol", "effort": "medium", "weekly_left": 70.0}},
                {"backend": "herdr", "pane": "w1:p2", "profile": "pro-b", "activity": "idle", "telemetry": {"model": "gpt-6.1-sol", "effort": "medium", "credits": "$3.10 credits"}}]
        self.store.dir.mkdir(parents=True, exist_ok=True)
        boost_lifecycle.sessions_path(self.store).write_text(json.dumps({"at": boost_lifecycle.iso(boost_lifecycle.now()), "hosts": {"box": {"at": boost_lifecycle.iso(boost_lifecycle.now()), "rows": rows}}}))

    def run_fleet(self, config, hosts, target, **options):
        self.order.append(("fleet", target["model"], options.get("rehome")))
        self.live_at_apply = json.loads(boost_lifecycle.sessions_path(self.store).read_text())
        path = self.root / f"report-{len(self.order)}.json"
        report = {"created_at": boost_lifecycle.iso(boost_lifecycle.now()), "hosts": {host: {"configs": [], "errors": [], "terminals": []} for host in hosts}}
        path.write_text(json.dumps(report))
        return dict(report, _path=str(path))

    def run_moves(self, config, moves, settings, progress=None):
        self.order.append(("moves", json.loads(json.dumps(moves))))
        return {host: [dict(item, status=self.move_status, **{"from": "pro-b"}) for item in items] for host, items in moves.items()}

    def cli(self, *argv):
        with patch("sys.stdout") as out:
            code = boost_lifecycle.main(list(argv), self.fm)
        return code, "".join(str(call.args[0]) for call in out.write.call_args_list if call.args)

    def accounts(self):
        return json.loads(self.store.usage_path.read_text())["accounts"]

    def test_profile_names_resolve_to_the_account_managers_spelling_or_are_refused(self):
        accounts = self.accounts()
        self.assertEqual(boost_lifecycle.resolve_profile(rb, "ops_example.test", accounts), "ops@example.test")
        self.assertEqual(boost_lifecycle.resolve_profile(rb, "ops", accounts), "ops@example.test")
        self.assertEqual(boost_lifecycle.resolve_profile(rb, "pro-a", accounts), "pro-a")
        self.assertIsNone(boost_lifecycle.resolve_profile(rb, "codex-ops_example.test", accounts))
        self.assertIsNone(boost_lifecycle.resolve_profile(rb, "nobody", accounts))
        with self.assertRaises(SystemExit), patch("sys.stderr"):
            self.cli("move", "box", "%1", "--to", "codex-pro-a")
        self.assertEqual(self.order, [])

    def test_destinations_put_pro_first_and_skip_exhausted_low_and_disabled(self):
        accounts = self.accounts()
        settings = boost_lifecycle.rehome_settings(self.config)
        exhausted = boost_lifecycle.exhausted_profiles(accounts)
        self.assertEqual([row["profile"] for row in boost_lifecycle.destinations(rb, accounts, dict(settings, prefer=[]), exhausted)], ["pro-a", "ops@example.test"])
        self.assertEqual([row["profile"] for row in boost_lifecycle.destinations(rb, accounts, dict(settings, prefer=["ops"]), exhausted)], ["pro-a", "ops@example.test"])
        self.assertEqual([row["profile"] for row in boost_lifecycle.destinations(rb, accounts, dict(settings, prefer=["ops@example.test"]), exhausted)],
                         ["ops@example.test", "pro-a"])
        dests = boost_lifecycle.destinations(rb, accounts, settings, exhausted)
        many = boost_lifecycle.assign([{"from": "pro-b"} for _ in range(9)], dests, settings, rb)
        self.assertEqual([item["to"] for item in many].count("pro-a"), 7)  # 46% left, 5 points each, floor 15%
        self.assertEqual([item["to"] for item in many].count("ops@example.test"), 2)
        capped = boost_lifecycle.assign([{"from": "pro-b"} for _ in range(3)], dests, dict(settings, max_per_account=1), rb)
        self.assertEqual([item["to"] for item in capped], ["pro-a", "ops@example.test", None])

    def test_dry_run_plan_lists_moves_and_changes_nothing(self):
        code, text = self.cli("rehome")
        self.assertEqual(code, 0)
        self.assertIn("%1", text)
        self.assertIn("move_suggested", text)
        self.assertIn("move_manual", text)  # herdr
        self.assertNotIn("%2 ", text)  # has quota
        plan = boost_lifecycle.rehome_plan(self.fm, rb.load_config(), self.store, {})
        self.assertEqual({item["pane"]: (item["to"], item["status"]) for item in plan["moves"]},
                         {"%1": ("pro-a", "move_suggested"), "w1:p2": ("pro-a", "move_manual")})
        self.assertEqual(self.order, [])

    def test_boost_moves_credit_sessions_first_then_applies(self):
        self.cli("boost", "--preset", "astra-ultra-fast")
        self.assertEqual(self.order[0], ("moves", {"box": [{"pane": "%1", "to": "pro-a", "interrupt": False}]}))
        self.assertEqual(self.order[1], ("fleet", "gpt-6-astra", True))
        state = json.loads(self.store.state_path.read_text())
        self.assertEqual(state["moves"]["box|%1"]["to"], "pro-a")
        self.assertEqual(self.live_at_apply["hosts"]["box"]["rows"][0]["profile"], "pro-a")  # shown on its new account before the apply
        events = [event["event"] for event in self.store.events()]
        self.assertIn("moved", events)
        self.assertLess(events.index("moved"), events.index("applied"))

    def test_no_rehome_holds_for_the_whole_boost(self):
        self.cli("boost", "--preset", "astra-high", "--no-rehome")
        self.cli("converge")
        self.assertEqual([step[0] for step in self.order], ["fleet", "fleet"])
        self.assertTrue(all(step[2] for step in self.order))  # held sessions are reported as move_suggested

    def test_a_thread_that_will_not_resume_is_not_retried_every_tick(self):
        self.move_status = "move_not_resumable"
        self.cli("boost", "--preset", "astra-high")
        self.cli("converge")
        self.assertEqual([step[0] for step in self.order], ["moves", "fleet", "fleet"])
        events = self.store.events()
        self.assertEqual([event["status"] for event in events if event["event"] == "move"], ["move_not_resumable"])


if __name__ == "__main__":
    unittest.main()
