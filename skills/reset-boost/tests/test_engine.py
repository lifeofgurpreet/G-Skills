"""Provider-free tests for config transforms, profile pins and live-pane safety."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import reset_boost as rb  # noqa: E402

try:
    import tomllib
except ModuleNotFoundError:
    tomllib = None

needs_toml = unittest.skipIf(tomllib is None, "TOML transforms need Python 3.11+ (tomllib)")
ASTRA = {"model": "gpt-6-astra", "effort": "ultra", "tier": "fast"}
SOL = {"model": "gpt-6.1-sol", "effort": "medium", "tier": "default"}


def target_args(model, effort, apply=False, **extra):
    return dict({"target": {"model": model, "effort": effort, "tier": None}, "model": model, "effort": effort, "apply": apply}, **extra)


class PresetTests(unittest.TestCase):
    def test_named_presets_and_arbitrary_provider_target(self):
        self.assertEqual(rb.resolve_target(None, None, "drain"), {"model": "gpt-6.1-sol", "effort": "low", "tier": "default"})
        self.assertEqual(rb.resolve_target("vendor/other-model", "medium", None), {"model": "vendor/other-model", "effort": "medium", "tier": None})
        self.assertEqual(rb.resolve_target(None, None, "astra-ultra-fast")["tier"], "priority")
        self.assertEqual(rb.resolve_target(None, None, "sol-high", "fast")["tier"], "priority")
        with self.assertRaises(ValueError):
            rb.resolve_target(None, None, "missing-preset")

    def test_shipped_catalog_matches_the_builtin_fallback(self):
        self.assertEqual(json.loads((SCRIPTS / "presets.json").read_text()), rb.DEFAULT_PRESETS)

    def test_config_defaults_to_this_machine_only(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"RESET_BOOST_CONFIG": str(Path(directory) / "missing.json")}):
                self.assertEqual(list(rb.load_config()["hosts"]), ["local"])
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"hosts": {"box": {"type": "telnet"}}}))
            with patch.dict(os.environ, {"RESET_BOOST_CONFIG": str(path)}), self.assertRaises(ValueError):
                rb.load_config()
            path.write_text(json.dumps({"hosts": {"box": {"type": "ssh", "project_roots": ["relative/path"]}}}))
            with patch.dict(os.environ, {"RESET_BOOST_CONFIG": str(path)}), self.assertRaises(ValueError):
                rb.load_config()

    def test_state_lives_under_the_password_database_home(self):
        with patch.dict(os.environ, {"HOME": "/nonexistent-redirected-home"}):
            os.environ.pop("RESET_BOOST_STATE_DIR", None)
            self.assertEqual(rb.state_dir(), rb.real_home() / ".local/state/reset-boost")


@needs_toml
class CodexTransformTests(unittest.TestCase):
    def test_codex_profiles_and_unrelated_settings(self):
        old = '''model = "gpt-6-astra"
model_reasoning_effort = "ultra"
[mcp_servers.example]
url = "https://example.invalid/mcp"
model = "do-not-touch"
[profiles.fast]
model = "gpt-6-luna"
model_reasoning_effort = "low"
'''
        result = tomllib.loads(rb.transform(old, "codex", "gpt-6.1-sol", "medium"))
        self.assertEqual(result["model_reasoning_effort"], "medium")
        self.assertEqual(result["profiles"]["fast"]["model"], "gpt-6.1-sol")
        self.assertEqual(result["profiles"]["fast"]["model_reasoning_effort"], "medium")
        self.assertEqual(result["mcp_servers"]["example"]["model"], "do-not-touch")

    def test_empty_codex_adds_root_defaults_before_tables(self):
        result = tomllib.loads(rb.transform('[tui]\nstatus_line = ["model-with-reasoning"]\n', "codex", "gpt-6.1-sol", "high"))
        self.assertEqual(result["model"], "gpt-6.1-sol")
        self.assertEqual(result["model_reasoning_effort"], "high")
        self.assertIn("status_line", result["tui"])

    def test_service_tier_is_set_only_when_requested(self):
        old = 'model = "gpt-6.1-sol"\nservice_tier = "default"\n[profiles.x]\nservice_tier = "flex"\n'
        fast = tomllib.loads(rb.transform(old, "codex", "gpt-6-astra", "ultra", "fast"))
        self.assertEqual(fast["service_tier"], "fast")
        self.assertEqual(fast["profiles"]["x"]["service_tier"], "flex")
        untouched = tomllib.loads(rb.transform(old, "codex", "gpt-6-astra", "ultra"))
        self.assertEqual(untouched["service_tier"], "default")
        added = tomllib.loads(rb.transform('model = "x"\n', "codex", "gpt-6-astra", "high", "ultrafast"))
        self.assertEqual(added["service_tier"], "ultrafast")
        self.assertNotIn("service_tier", tomllib.loads(rb.transform('model = "x"\n', "codex", "gpt-6.1-sol", "medium", "default")))
        back = tomllib.loads(rb.transform('service_tier = "fast"\n', "codex", "gpt-6.1-sol", "medium", "default"))
        self.assertEqual(back["service_tier"], "default")

    def test_ntm_template_shapes_preserve_identity_and_other_providers(self):
        templates = [
            'codex -m {{shellQuote (.Model | default "gpt-5.6-sol")}} -c model_reasoning_effort="high" --search',
            'exec codex ${NTM_CODEX_PROFILE:-team-a} -m {{if .Model}}{{shellQuote .Model}}{{else}}gpt-5.6-terra{{end}} -c model_reasoning_effort={{if eq .Model "gpt-6-astra"}}low{{else}}{{if .ReasoningEffort}}{{.ReasoningEffort}}{{else}}high{{end}}{{end}} -c mcp_servers.mail.url=https://mail.example.test/mcp/',
            "exec zsh -lic 'exec codex team-a -m {{if .Model}}gpt-6.1-sol{{else}}gpt-6.1-sol{{end}} -c model_reasoning_effort={{if .ReasoningEffort}}high{{else}}high{{end}} --search'",
        ]
        for command in templates:
            with self.subTest(command=command):
                old = '[agents]\ncodex = ' + json.dumps(command) + '\nclaude = "claude --model opus"\n[models]\ndefault_codex = "gpt-6-astra"\n[models.codex]\nmax = "gpt-6-astra"\n'
                new = rb.transform(old, "ntm", "gpt-6-luna", "medium")
                result = tomllib.loads(new)
                pinned = result["agents"]["codex"]
                self.assertIn('{{if .Model}}gpt-6-luna{{else}}gpt-6-luna{{end}}', pinned)
                self.assertIn('{{if .ReasoningEffort}}medium{{else}}medium{{end}}', pinned)
                self.assertEqual(result["agents"]["claude"], "claude --model opus")
                self.assertEqual(result["models"]["codex"]["max"], "gpt-6-luna")
                self.assertEqual(rb.transform(new, "ntm", "gpt-6-luna", "medium"), new)
                if "NTM_CODEX_PROFILE" in command:
                    self.assertIn('${NTM_CODEX_PROFILE:-team-a}', pinned)
                    self.assertIn('mcp_servers.mail.url=https://mail.example.test/mcp/', pinned)

    def test_unrecognized_template_is_not_written(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            original = '[agents]\ncodex = "my-custom-command"\n'
            path.write_text(original)
            with self.assertRaises(ValueError):
                rb.change_file(path, "ntm", target_args("gpt-6.1-sol", "high", True))
            self.assertEqual(path.read_text(), original)

    def test_backup_symlink_and_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "real.toml"
            link = Path(directory) / "linked.toml"
            old = 'model = "gpt-6-astra"\n'
            path.write_text(old)
            path.chmod(0o640)
            link.symlink_to(path)
            inode = path.stat().st_ino
            row = rb.change_file(link.resolve(), "codex", target_args("gpt-6.1-sol", "high", True))
            self.assertTrue(link.is_symlink())
            self.assertEqual(path.stat().st_ino, inode)
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)
            self.assertEqual(Path(row["backup"]).read_text(), old)
            second = rb.change_file(path, "codex", target_args("gpt-6.1-sol", "high", True))
            self.assertEqual(second["status"], "matches")
            self.assertEqual(len(list(Path(directory).glob("*.reset-boost-*"))), 1)

    def test_preview_leaves_file_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            old = 'model = "gpt-6-astra"\n'
            path.write_text(old)
            row = rb.change_file(path, "codex", target_args("gpt-6.1-sol", "high", False))
            self.assertEqual(row["status"], "would_change")
            self.assertEqual(path.read_text(), old)
            self.assertEqual(list(Path(directory).glob("*.reset-boost-*")), [])

    def test_project_roots_are_configurable_and_nothing_else_is_assumed(self):
        with tempfile.TemporaryDirectory() as directory:
            home, root = Path(directory) / "home", Path(directory) / "work"
            (home / ".codex").mkdir(parents=True)
            (home / ".codex/config.toml").write_text('model = "x"\n')
            (root / "repo/.codex").mkdir(parents=True)
            (root / "repo/.codex/config.toml").write_text('model = "x"\n')
            with patch.object(rb, "homes", return_value=[home]):
                without = rb.config_paths({})
                with_root = rb.config_paths({}, [str(root)])
            self.assertEqual(set(without.values()), {"codex"})
            self.assertNotIn((root / "repo/.codex/config.toml").resolve(), without)
            self.assertIn((root / "repo/.codex/config.toml").resolve(), with_root)
            self.assertFalse(any(kind == "policy" for kind in with_root.values()))


class CaamAdapterTests(unittest.TestCase):
    def test_policy_file_is_data_only_and_tunable(self):
        self.assertEqual(
            rb.transform_policy("# preserved\nCAAM_CODEX_MODEL=gpt-6-astra\n", "gpt-6.1-sol", "medium"),
            "# preserved\nCAAM_CODEX_MODEL=gpt-6.1-sol\nCAAM_CODEX_REASONING_EFFORT=medium\n",
        )

    def test_profile_paths_and_overrides(self):
        self.assertEqual(rb.profile_of(Path("/home/u/orch-homes/codex-pro-1_example.test/.codex/config.toml")), "pro-1_example.test")
        self.assertEqual(rb.profile_of(Path("/home/u/.local/share/caam/profiles/codex/pro-1@example.test/codex_home/config.toml")), "pro-1_example.test")
        self.assertEqual(rb.profile_of(Path("/home/u/.config/caam/model-policy.d/team-a.env")), "team-a")
        self.assertIsNone(rb.profile_of(Path("/home/u/.codex/config.toml")))
        args = {"target": ASTRA, "profiles": {"pro-1@example.test": SOL}}
        self.assertEqual(rb.target_for(Path("/h/orch-homes/codex-pro-1_example.test/.codex/config.toml"), args)["model"], "gpt-6.1-sol")
        self.assertEqual(rb.target_for(Path("/h/orch-homes/codex-team-b/.codex/config.toml"), args)["model"], "gpt-6-astra")

    def test_per_profile_policy_files_are_written_without_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / ".config/caam").mkdir(parents=True)
            (home / ".config/caam/model-policy.env").write_text("CAAM_CODEX_MODEL=gpt-6.1-sol\nCAAM_CODEX_REASONING_EFFORT=medium\n")
            with patch.object(rb, "homes", return_value=[home]):
                paths = rb.config_paths({"team-a": SOL, "../bad": SOL})
            policy_d = (home / ".config/caam/model-policy.d").resolve()
            self.assertIn(policy_d / "team-a.env", paths)
            self.assertFalse(any(".." in str(path) for path in paths))
            args = {"target": ASTRA, "profiles": {"team-a": SOL}, "apply": True}
            for path, kind in paths.items():
                rb.change_file(path, kind, args)
            self.assertIn("CAAM_CODEX_MODEL=gpt-6-astra", (home / ".config/caam/model-policy.env").read_text())
            self.assertIn("CAAM_CODEX_MODEL=gpt-6.1-sol", (policy_d / "team-a.env").read_text())
            self.assertEqual(list(policy_d.glob("*.reset-boost-*")), [])
            # A later run without the pin converges the leftover file to the host target.
            with patch.object(rb, "homes", return_value=[home]):
                for path, kind in rb.config_paths({}).items():
                    rb.change_file(path, kind, {"target": SOL, "profiles": {}, "apply": True})
            self.assertIn("CAAM_CODEX_MODEL=gpt-6.1-sol", (policy_d / "team-a.env").read_text())


class LiveSessionSafetyTests(unittest.TestCase):
    def test_ui_returns_only_settings_and_holds_a_draft(self):
        state = rb.ui_state('private conversation text\n› my unfinished private draft\n GPT-6.1-Sol high · /work/path\n')
        self.assertEqual(state["footer"], ("gpt-6.1-sol", "high"))
        self.assertFalse(state["empty_composer"])
        self.assertNotIn("private", json.dumps(state))
        terminal = {"backend": "herdr", "user": "someone", "pane": "w1:p1", "state": "idle"}
        with patch.object(rb, "screen", return_value='› unfinished draft\n GPT-6-Astra ultra · /work/path\n'), patch.object(rb, "send") as send:
            row = rb.live_setting(terminal, target_args("gpt-6.1-sol", "high", True, live=True, interrupt=False))
            self.assertEqual(row["status"], "held_unrecognized_or_occupied_composer")
            send.assert_not_called()

    def test_busy_pane_is_held_without_interrupt(self):
        terminal = {"backend": "tmux", "user": "u", "pane": "%2", "state": "working"}
        with patch.object(rb, "screen", return_value='working… esc to interrupt\n› Explain this codebase\n GPT-6.1-Sol medium · /x\n'), patch.object(rb, "send") as send:
            row = rb.live_setting(terminal, target_args("gpt-6-astra", "ultra", True, live=True, interrupt=False))
            self.assertEqual(row["status"], "held_working")
            send.assert_not_called()

    def test_preview_never_sends_keys(self):
        terminal = {"backend": "tmux", "user": "u", "pane": "%2"}
        with patch.object(rb, "screen", return_value='› \n GPT-6.1-Sol medium · /x\n'), patch.object(rb, "send") as send:
            row = rb.live_setting(terminal, target_args("gpt-6-astra", "ultra", False, live=True, interrupt=False))
            self.assertEqual(row["status"], "live_mismatch")
            send.assert_not_called()

    def test_credit_guard_never_turns_up_a_session_on_credits(self):
        terminal = {"backend": "tmux", "user": "u", "pane": "%3"}
        screen = '› \n  GPT-6.1-Sol medium · Idle · 5h 40% left · weekly 0% left\n'
        base = {"model": "gpt-6.1-sol", "effort": "medium", "tier": "default"}
        with patch.object(rb, "screen", return_value=screen), patch.object(rb, "send") as send:
            row = rb.live_setting(terminal, target_args("gpt-6-astra", "ultra", True, live=True, interrupt=False, baseline=base))
            self.assertEqual(row["status"], "held_credits")
            # Turning down is never blocked by the guard (preview here, so nothing is sent).
            down = dict(target_args("gpt-6.1-sol", "low", False, live=True, interrupt=False, baseline=base))
            self.assertEqual(rb.live_setting(terminal, down)["status"], "live_mismatch")
            send.assert_not_called()
        self.assertFalse(rb.is_up({"model": "gpt-6.1-sol", "effort": "low", "tier": "default"}, base))
        self.assertTrue(rb.is_up({"model": "gpt-6.1-sol", "effort": "medium", "tier": "priority"}, base))

    def test_status_line_telemetry_reads_quota_credits_and_folder(self):
        info = rb.telemetry("  GPT-6-Astra high fast · Working · 5h 12% left · weekly 55% left · $1.20 credits · /work/repo\n")
        self.assertEqual((info["model"], info["effort"], info["fast"], info["run_state"]), ("gpt-6-astra", "high", True, "working"))
        self.assertEqual((info["five_hour_left"], info["weekly_left"], info["cwd"]), (12.0, 55.0, "/work/repo"))
        self.assertTrue(rb.on_credits(info))

    def test_subprocesses_use_an_absolute_executable_for_posix_spawn(self):
        self.assertTrue(os.path.isabs(rb.spawnable([Path(sys.executable).name, "-c", "pass"])[0]))
        with self.assertRaises(FileNotFoundError):
            rb.spawnable(["no-such-reset-boost-binary"])

    def test_current_placeholder_counts_as_an_empty_composer(self):
        state = rb.ui_state('› Ask Codex to do anything\n\n  GPT-6.1-Sol high fast · Idle · weekly 0% left\n  ? for shortcuts\n')
        self.assertTrue(state["empty_composer"])
        self.assertTrue(state["telemetry"]["fast"])
        self.assertTrue(rb.on_credits(state["telemetry"]))

    def test_narrow_pane_truncated_effort_is_still_read(self):
        self.assertEqual(rb.telemetry("  GPT-6.1-Sol me…\n")["effort"], "medium")
        self.assertIsNone(rb.telemetry("  GPT-6.1-Sol m…\n")["effort"])  # medium or max: ambiguous

    def test_wrapped_picker_and_advanced_effort_parsing(self):
        text = 'private conversation\n Select Reasoning Level for\n GPT-6.1-Sol\n 1. Low\n 2. Medium (default)\n› 3. High (current)\n enter default · s session · esc back\n'
        state = rb.ui_state(text)
        self.assertNotIn("private", state["modal"])
        self.assertEqual(rb.menu_rows(state["modal"])[-1], (3, "High (current)", True))

    def test_advanced_reasoning_screen_is_a_picker(self):
        text = ('private conversation\n  Advanced Reasoning\n  \u26a0 Consumes usage limits faster\n'
                '\u203a 1. Max    For difficult problems when quality matters more than speed \u00b7 higher\n            usage\n'
                '  2. Ultra  For demanding work using multiple agents \u00b7 highest usage\n  enter default \u00b7 s session \u00b7 esc back\n')
        state = rb.ui_state(text)
        self.assertNotIn("private", state["modal"])
        self.assertEqual([row[1].split()[0] for row in rb.menu_rows(state["modal"])], ["Max", "Ultra"])

    def test_old_visible_model_text_is_not_current_footer_proof(self):
        text = 'GPT-6.1-Sol high\n' + 'old output\n' * 20 + '› unfinished draft\nGPT-6.1-Sol …\n'
        self.assertIsNone(rb.ui_state(text)["footer"])

    def test_pane_targets_hold_unknown_accounts_when_some_are_pinned(self):
        args = {"target": ASTRA, "profiles": {"team-a": SOL}, "hold_unknown": True, "live": True, "apply": True, "interrupt": False}
        self.assertEqual(rb.pane_target({"profile": "team-a"}, args), SOL)
        self.assertEqual(rb.pane_target({"profile": "team-b"}, args), ASTRA)
        self.assertIsNone(rb.pane_target({"profile": None}, args))
        self.assertEqual(rb.pane_target({"profile": None}, dict(args, hold_unknown=False)), ASTRA)
        terminal = {"backend": "tmux", "user": "u", "pane": "%1", "profile": None}
        with patch.object(rb, "screen", return_value=" GPT-6.1-Sol medium · /x\n"), patch.object(rb, "send") as send:
            self.assertEqual(rb.live_setting(terminal, args)["status"], "held_profile_unknown")
            send.assert_not_called()

    def test_failed_control_command_never_echoes_its_output(self):
        with self.assertRaises(RuntimeError) as caught:
            rb.execute([sys.executable, "-c", "import sys; print('secret draft'); sys.exit(3)"])
        self.assertNotIn("secret", str(caught.exception))

    def test_report_exit_codes(self):
        clean = {"hosts": {"a": {"errors": [], "configs": [{"status": "matches"}], "terminals": [{"status": "verified"}], "launch_overrides": []}}}
        held = {"hosts": {"a": {"errors": [], "configs": [], "terminals": [{"status": "held_working"}], "launch_overrides": []}}}
        broken = {"hosts": {"a": {"errors": [{"error": "unreachable"}], "configs": [], "terminals": [], "launch_overrides": []}}}
        self.assertEqual([rb.report_exit(r) for r in (clean, held, broken)], [0, 2, 1])


class LaunchGuardTests(unittest.TestCase):
    script = SCRIPTS / "model-policy-guard.py"

    def guard(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("guard", self.script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_rewrites_explicit_flags_and_preserves_prompt(self):
        guard = self.guard()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("RESET_BOOST_MODEL", None)
            os.environ.pop("RESET_BOOST_REASONING_EFFORT", None)
            self.assertEqual(guard.rewrite(["resume", "thread", "-m", "gpt-6-astra", "-c", "model_reasoning_effort=ultra"]),
                             ["resume", "thread", "-m", "gpt-6.1-sol", "-c", "model_reasoning_effort=medium"])
            self.assertEqual(guard.rewrite(["--model=gpt-6-astra", "-c", "model=old", "--config=model_reasoning_effort=ultra"]),
                             ["--model=gpt-6.1-sol", "-c", "model=gpt-6.1-sol", "--config=model_reasoning_effort=medium"])
            self.assertEqual(guard.rewrite(["resume", "thread", "--", "say", "--model=gpt-6-astra"]),
                             ["resume", "thread", "-m", "gpt-6.1-sol", "-c", "model_reasoning_effort=medium", "--", "say", "--model=gpt-6-astra"])
            self.assertEqual(guard.rewrite(["run", "-c"]), ["run", "-c", "model_reasoning_effort=medium", "-m", "gpt-6.1-sol"])
            argv = ["resume", "thread", "-m", "gpt-6.1-sol", "-c", "model_reasoning_effort=medium"]
            self.assertEqual(guard.rewrite(guard.rewrite(argv)), argv)

    def test_environment_selects_target_and_invalid_values_fail_closed(self):
        guard = self.guard()
        with patch.dict(os.environ, {"RESET_BOOST_MODEL": "gpt-6-astra;rm", "RESET_BOOST_REASONING_EFFORT": "bogus"}):
            self.assertEqual(guard.policy(), ("gpt-6.1-sol", "medium"))
        with patch.dict(os.environ, {"RESET_BOOST_MODEL": "vendor/other-model@2026", "RESET_BOOST_REASONING_EFFORT": "ultra"}):
            self.assertEqual(guard.policy(), ("vendor/other-model@2026", "ultra"))

    def test_exec_boundary_keeps_provider_argv_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory) / "argv.json"
            stub = Path(directory) / "provider"
            stub.write_text("#!" + sys.executable + "\nimport json, os, pathlib, sys\npathlib.Path(os.environ['CAPTURE']).write_text(json.dumps(sys.argv))\n")
            stub.chmod(0o700)
            env = dict(os.environ, CAPTURE=str(capture))
            env.pop("RESET_BOOST_MODEL", None)
            env.pop("RESET_BOOST_REASONING_EFFORT", None)
            subprocess.run([sys.executable, str(self.script), "--", str(stub), "resume", "x", "-m", "gpt-6-astra"], env=env, check=True)
            argv = json.loads(capture.read_text())
            self.assertEqual(argv[0], str(stub))
            self.assertIn("gpt-6.1-sol", argv)
            self.assertIn("model_reasoning_effort=medium", argv)


THREAD = "0199a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b"
IDLE = "› Ask Codex to do anything\n\n  GPT-6.1-Sol medium · Pursuing goal · weekly 0% left\n"


class RehomeEngineTests(unittest.TestCase):
    def test_thread_id_comes_from_argv_or_the_rollout_file_name_only(self):
        self.assertEqual(rb.thread_from(["codex", "resume", THREAD.upper(), "--search"]), THREAD)
        self.assertEqual(rb.thread_from(["codex", "resume", "--dangerously-bypass-approvals-and-sandbox", THREAD]), THREAD)
        rollout = "/home/u/orch-homes/codex-team-c/.codex/sessions/2026/10/15/rollout-2026-10-15T09-12-44-" + THREAD + ".jsonl"
        self.assertEqual(rb.thread_from(["codex", "--search"], ["/dev/pts/3", "socket:[1234]", rollout]), THREAD)
        self.assertIsNone(rb.thread_from(["codex", "resume", "--last"], ["/tmp/notes-" + THREAD + ".txt"]))
        self.assertEqual(rb.home_profile("/home/u/orch-homes/codex-ops_example.test/.codex"), "ops_example.test")
        self.assertIsNone(rb.home_profile("/home/u/.codex"))

    def test_launch_command_quotes_and_keeps_the_bypass_only_when_present(self):
        settings = {"launch": "MY_WRAPPER=1 codex {profile} resume {thread}", "shell": "zsh"}
        line = rb.launch_command(settings, "ops@example.test", THREAD, "--dangerously-bypass-approvals-and-sandbox")
        self.assertEqual(line, "zsh -lic 'MY_WRAPPER=1 codex ops@example.test resume " + THREAD +
                         " --dangerously-bypass-approvals-and-sandbox; exec zsh -l'")
        self.assertNotIn("dangerously", rb.launch_command(settings, "pro-a", THREAD))
        for bad in (("pro-a; rm x", THREAD), ("pro-a", "not-a-thread")):
            with self.assertRaises(ValueError):
                rb.launch_command(settings, *bad)
        with self.assertRaises(ValueError):
            rb.launch_command({"launch": "codex resume {thread}"}, "pro-a", THREAD)

    def test_resume_and_goal_screens(self):
        self.assertEqual(rb.resume_state("This conversation is open in another app", probe=True), "ok")
        self.assertIsNone(rb.resume_state("This conversation is open in another app"))
        self.assertEqual(rb.resume_state("Error: thread/resume failed: missing source rollout", probe=True), "failed")
        self.assertEqual(rb.resume_state("Do you trust the contents of this directory?\n› 1. Yes, Trust this folder"), "trust")
        self.assertEqual(rb.resume_state(IDLE), "ok")
        self.assertEqual(rb.goal_state(IDLE), "active")
        self.assertEqual(rb.goal_state("  GPT-6.1-Sol medium · Goal paused (/goal resume)\n"), "paused")
        self.assertIsNone(rb.goal_state("› Ask Codex to do anything\n  GPT-6.1-Sol medium · Idle\n"))
        self.assertTrue(rb.ui_state("» Ask Codex to do anything\n  GPT-6.1-Sol medium\n")["empty_composer"])

    def test_a_session_on_credits_is_never_cranked_in_place(self):
        terminal = {"backend": "tmux", "user": "u", "pane": "%3", "profile": "pro-b"}
        args = target_args("gpt-6-astra", "ultra", True, live=True, interrupt=True, baseline={"model": "gpt-6.1-sol", "effort": "medium", "tier": "default"},
                           credit_guard={"enabled": True, "floor": 0.0})
        for rehome, status in ((True, "move_suggested"), (False, "held_credits")):
            with patch.object(rb, "screen", return_value=IDLE), patch.object(rb, "send") as send, patch.object(rb, "execute") as execute:
                self.assertEqual(rb.live_setting(terminal, dict(args, rehome=rehome))["status"], status)
                send.assert_not_called()
                execute.assert_not_called()


class MoveSessionTests(unittest.TestCase):
    """The move sequence against a fake tmux: verify first, respawn in place, resume the goal, read back."""

    def setUp(self):
        self.calls, self.keys, self.respawned = [], [], False
        self.probe_screen = "This conversation is open in another app"
        self.original = IDLE
        self.terminal = {"backend": "tmux", "user": "u", "socket": "/tmp/tmux-1/default", "pane": "%3", "profile": "pro-b", "pid": 4242}
        self.settings = {"launch": "codex {profile} resume {thread}", "shell": "zsh", "boot_seconds": 0.3}
        facts = {"thread": THREAD, "cwd": "/srv/work/x", "profile": "pro-b", "bypass": "--dangerously-bypass-approvals-and-sandbox"}
        self.patches = [patch.object(rb, "codex_facts", return_value=facts), patch.object(rb, "screen", side_effect=self.screen),
                        patch.object(rb, "send", side_effect=self.send), patch.object(rb, "execute", side_effect=self.execute),
                        patch.object(rb, "pane_account", side_effect=lambda terminal: ("pro-a", THREAD) if self.respawned else ("pro-b", THREAD)),
                        patch.object(rb, "proc_available", return_value=True), patch.object(rb.time, "sleep")]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()

    def screen(self, terminal):
        if terminal["pane"] == "%99":
            return self.probe_screen
        return "› Ask Codex to do anything\n  GPT-6.1-Sol medium · Goal paused · weekly 46% left\n" if self.respawned else self.original

    def send(self, terminal, text=None, keys=()):
        self.keys.append((terminal["pane"], text, tuple(keys)))

    def execute(self, argv, user=None, timeout=15, env=None):
        self.calls.append(argv)
        if "respawn-pane" in argv:
            self.respawned = True
        if "#{session_name}" in argv:
            return "main\n"
        if "new-window" in argv:
            return "%99\n"
        return ""

    def verbs(self):
        return [argv[3] for argv in self.calls]

    def test_verified_move_respawns_in_place_and_resumes_the_goal(self):
        row = rb.move_session(self.terminal, {"pane": "%3", "to": "pro-a"}, self.settings)
        self.assertEqual(row["status"], "moved")
        self.assertTrue(row["goal_resumed"])
        self.assertEqual(self.verbs(), ["display-message", "new-window", "kill-pane", "respawn-pane"])
        respawn = self.calls[3]
        self.assertEqual(respawn[respawn.index("-t") + 1], "%3")
        self.assertIn("codex pro-a resume " + THREAD + " --dangerously-bypass-approvals-and-sandbox", respawn[-1])
        self.assertIn(("%3", "/goal resume", ()), self.keys)
        self.assertNotIn(THREAD, json.dumps(row))  # only a short prefix is reported

    def test_a_thread_that_does_not_resume_is_left_untouched(self):
        self.probe_screen = "Error: thread/resume failed: missing source rollout"
        row = rb.move_session(self.terminal, {"pane": "%3", "to": "pro-a"}, self.settings)
        self.assertEqual(row["status"], "move_not_resumable")
        self.assertNotIn("respawn-pane", self.verbs())
        self.assertIn("kill-pane", self.verbs())  # the probe is closed
        self.assertFalse([key for key in self.keys if key[0] == "%3"])

    def test_busy_and_draft_sessions_are_held_before_any_probe(self):
        self.original = "working\n• Working (12s • esc to interrupt)\n› Ask Codex to do anything\n  GPT-6.1-Sol medium · weekly 0% left\n"
        self.assertEqual(rb.move_session(self.terminal, {"pane": "%3", "to": "pro-a"}, self.settings)["status"], "move_held_working")
        self.original = "› my private draft\n  GPT-6.1-Sol medium · weekly 0% left\n"
        row = rb.move_session(self.terminal, {"pane": "%3", "to": "pro-a"}, self.settings)
        self.assertEqual(row["status"], "move_held_draft")
        self.assertNotIn("private", json.dumps(row))
        self.assertEqual(self.calls, [])

    def test_herdr_and_same_account_are_not_moved(self):
        self.assertEqual(rb.move_session(dict(self.terminal, backend="herdr"), {"pane": "w1:p2", "to": "pro-a"}, self.settings)["status"], "move_manual")
        self.assertEqual(rb.move_session(self.terminal, {"pane": "%3", "to": "pro-b"}, self.settings)["status"], "move_same_account")
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
