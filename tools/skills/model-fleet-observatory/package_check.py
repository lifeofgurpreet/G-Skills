#!/usr/bin/env python3
"""Cold acceptance for an extracted model-fleet-observatory package."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--skill-dir", required=True, type=Path); args = parser.parse_args()
    required = {"SKILL.md", "skill.json", "agents/openai.yaml", "scripts/model_fleet_dashboard.py", "references/schema.md", "references/adapters.md", "references/operations.md"}
    files = {p.relative_to(args.skill_dir).as_posix() for p in args.skill_dir.rglob("*") if p.is_file()}
    if not required <= files: raise SystemExit("package missing required runtime files")
    manifest = json.loads((args.skill_dir / "skill.json").read_text())
    if manifest["status"] != "ready": raise SystemExit("draft skill cannot be packaged")
    with tempfile.TemporaryDirectory() as directory:
        config = Path(directory) / "config.json"
        out = Path(directory) / "snapshot.json"
        config.write_text(json.dumps({"boxes": [{"id": "cold", "payload": {"sessions": [{"profile": "cold", "model": "gpt-6.1-sol", "reasoning": "medium", "backend": "codex"}]}}]}))
        entry = args.skill_dir / "scripts/model_fleet_dashboard.py"
        subprocess.run([sys.executable, str(entry), "snapshot", "--config", str(config), "--out", str(out)], check=True, stdout=subprocess.DEVNULL)
        assert json.loads(out.read_text())["boxes"][0]["sessions"][0]["model"] == "gpt-6.1-sol"
    print("PASS: extracted model-fleet-observatory package boots and snapshots")


if __name__ == "__main__": main()
