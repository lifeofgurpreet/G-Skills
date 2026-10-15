#!/usr/bin/env python3
"""Reset Boost package acceptance on an extracted skill folder; never imposed on other skills.

The cold check drives the real CLI from the exported folder against a synthetic
usage file and a zero-host estate, so it never reads or changes this machine's
agent configuration, terminals or processes.
"""
from pathlib import Path
import argparse
import http.client
import json
import os
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse

REQUIRED = {"SKILL.md", "skill.json", "README.md", "CHANGELOG.md", "scripts/reset_boost.py", "scripts/boost_lifecycle.py",
            "scripts/boost_dashboard.py", "scripts/boost_agent.py", "scripts/boost_server.py", "scripts/install-watch.sh", "scripts/model-policy-guard.py", "scripts/presets.json",
            "references/usage-source.md", "references/configuration.md", "references/live-sessions.md",
            "assets/usage.example.json", "assets/config.example.json", "assets/console.html", "assets/operator-ui.css",
            "tests/test_engine.py", "tests/test_lifecycle.py", "tests/test_panel.py"}


def validate_files(files, require_license=True):
    missing = REQUIRED - set(files) | ({"LICENSE"} - set(files) if require_license else set())
    if missing:
        raise ValueError("installable skill is missing required files: " + ", ".join(sorted(missing)))
    if any(name.startswith(("skills/", ".github/", "tools/", ".beads/")) for name in files):
        raise ValueError("repository content incorrectly nested inside the skill folder")
    meta = json.loads(files["skill.json"])
    if ('VERSION = "' + meta["version"] + '"') not in files["scripts/reset_boost.py"].decode():
        raise ValueError("skill manifest and runtime versions differ")
    if ('version: "' + meta["version"] + '"') not in files["SKILL.md"].decode():
        raise ValueError("SKILL.md metadata version differs from skill.json")


def run(entry, env, *argv, expect=0):
    result = subprocess.run([sys.executable, str(entry), *argv], env=env, capture_output=True, text=True, timeout=60)
    if result.returncode != expect:
        raise ValueError(f"{' '.join(argv)} exited {result.returncode}: {result.stderr[-2000:]}")
    return result.stdout


def panel_check(entry, env, state_dir):
    """Start the exported control panel on a free port, read /api/state with its token, then stop it."""
    process = subprocess.Popen([sys.executable, str(entry), "serve", "--port", "0", "--no-loop"], env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        link = state_dir / "serve-url"
        for _ in range(100):
            if link.exists() and link.read_text().strip() or process.poll() is not None:
                break
            time.sleep(0.1)
        if process.poll() is not None or not link.exists():
            raise ValueError("control panel did not start: " + (process.stderr.read()[-2000:] if process.poll() is not None else "no serve-url"))
        if (link.stat().st_mode & 0o777) != 0o600 or ((state_dir / "serve-token").stat().st_mode & 0o777) != 0o600:
            raise ValueError("panel link or token is readable by other accounts")
        url = urlparse(link.read_text().strip())
        token = url.fragment.split("t=", 1)[1]

        def get(path, **headers):
            connection = http.client.HTTPConnection("127.0.0.1", url.port, timeout=10)
            connection.request("GET", path, headers=dict({"Host": f"127.0.0.1:{url.port}"}, **headers))
            response = connection.getresponse()
            body = response.read()
            connection.close()
            return response.status, body

        if get("/api/state")[0] != 401:
            raise ValueError("control panel served state without its token")
        if get("/api/state", **{"X-Reset-Boost-Token": token, "Host": "attacker.example.test"})[0] != 403:
            raise ValueError("control panel accepted a non-local Host header")
        status, body = get("/api/state", **{"X-Reset-Boost-Token": token})
        snapshot = json.loads(body)
        if status != 200 or snapshot.get("phase") != "idle" or "astra-ultra-fast" not in snapshot.get("presets", {}):
            raise ValueError("control panel state is wrong: " + body[:300].decode(errors="replace"))
        if "rows" not in snapshot.get("sessions", {}) or snapshot.get("credit_guard", {}).get("enabled") is not True:
            raise ValueError("control panel state lacks session telemetry or the credit guard")
        status, body = get("/")
        if status != 200 or b"Reset Boost" not in body or b'href="/operator-ui.css"' not in body:
            raise ValueError("control panel page did not load")
        status, body = get("/operator-ui.css")
        if status != 200 or b"--ui-accent" not in body:
            raise ValueError("control panel stylesheet did not load")
    finally:
        process.terminate()
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(10)


def cold_check(target):
    entry = Path(target) / "scripts/reset_boost.py"
    example = json.loads((Path(target) / "assets/usage.example.json").read_text())
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        usage = temp / "usage.json"
        usage.write_text(json.dumps(example))
        config = temp / "config.json"
        config.write_text(json.dumps({"hosts": {}, "baseline": "normal", "exclude_profiles": ["pro-1"],
                                      "usage": {"type": "file", "path": str(usage)}}))
        env = dict(os.environ, RESET_BOOST_CONFIG=str(config), RESET_BOOST_STATE_DIR=str(temp / "state"))
        state = lambda: json.loads((temp / "state/boost.json").read_text())

        if "reset-boost" not in run(entry, env, "--version"):
            raise ValueError("exported CLI did not report its identity")
        catalog = json.loads(run(entry, env, "presets", "--json"))
        if "normal" not in catalog or "astra-ultra-fast" not in catalog:
            raise ValueError("exported preset catalog is incomplete")
        run(entry, env, "boost", "--preset", "astra-ultra-fast", "--dry-run")
        if (temp / "state/boost.json").exists():
            raise ValueError("a dry run recorded a boost")
        run(entry, env, "boost", "--preset", "astra-ultra-fast", "--note", "synthetic reset window")
        boosted = state()
        if boosted["phase"] != "boosted" or len(boosted["snapshot"]) != 3 or boosted["exclude"] != ["pro-1"]:
            raise ValueError("exported boost did not record its snapshot and exclusions")
        run(entry, env, "watch", "--quiet")
        if state()["phase"] != "boosted":
            raise ValueError("boost ended without a reset signal")

        usage.write_text("not json")  # a broken usage source must never change the phase
        run(entry, env, "watch", "--quiet")
        if state()["phase"] != "boosted" or not state().get("usage_error"):
            raise ValueError("a failed usage read changed the boost")

        for row in example["accounts"]:
            for window in row["windows"]:
                window["used_percent"] = 1
        usage.write_text(json.dumps(example))
        run(entry, env, "watch", "--quiet")
        cooled = state()
        if cooled["phase"] != "cooling" or "reset detected" not in cooled["end_reason"]:
            raise ValueError("exported watch did not turn down when the reset landed")
        run(entry, env, "watch", "--quiet")  # zero hosts: baseline verified everywhere reachable
        if state()["phase"] != "idle":
            raise ValueError("cooling did not finish after a clean baseline readback")
        status = json.loads(run(entry, env, "status", "--json"))
        if status["state"]["phase"] != "idle":
            raise ValueError("status disagrees with the recorded phase")
        page = Path(run(entry, env, "dashboard").strip())
        html = page.read_text()
        if page.parent != temp / "state" or "Reset Boost" not in html or "<script src" in html:
            raise ValueError("dashboard missing, outside the state directory or not self-contained")
        events = [json.loads(line)["event"] for line in (temp / "state/boost-events.jsonl").read_text().splitlines()]
        if events[0] != "boost" or "done" not in events or events[-1] != "idle":
            raise ValueError("event log does not record the lifecycle")
        run(entry, env, "done", "--dry-run")
        observed = json.loads(run(entry, env, "observe", "--json"))
        if observed.get("hosts") != {}:
            raise ValueError("observe on a zero-host estate reported sessions")
        panel_check(entry, env, temp / "state")
        result = subprocess.run([sys.executable, str(Path(target) / "scripts/model-policy-guard.py")], capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            raise ValueError("launch guard accepted a missing command")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-dir", required=True, type=Path)
    options = parser.parse_args()
    files = {f.relative_to(options.skill_dir).as_posix(): f.read_bytes() for f in options.skill_dir.rglob("*")
             if f.is_file() and "__pycache__" not in f.parts}
    validate_files(files)
    cold_check(options.skill_dir)
    print("PASS: isolated Reset Boost package: boost, failed-usage hold, reset auto-down, cooling, dashboard, event log, observe and control panel")


if __name__ == "__main__":
    main()
