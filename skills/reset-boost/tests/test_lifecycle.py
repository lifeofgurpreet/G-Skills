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

ASTRA = {"model": "gpt-6-astra", "effort": "ultra", "tier": "fast"}
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


if __name__ == "__main__":
    unittest.main()
