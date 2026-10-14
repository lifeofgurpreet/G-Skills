#!/usr/bin/env python3
"""Portable acceptance for the model fleet observatory skill."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills/model-fleet-observatory"
SCRIPT = SKILL / "scripts/model_fleet_dashboard.py"


def main():
    assert (SKILL / "SKILL.md").is_file()
    manifest = json.loads((SKILL / "skill.json").read_text())
    assert manifest["status"] == "ready" and manifest["version"] == "0.1.0"
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        config = root / "config.json"
        config.write_text(json.dumps({
            "refresh_interval_s": 600,
            "boxes": [
                {"id": "alpha", "label": "Alpha", "payload": {"sessions": [{"id": "a-1", "account": "pro-1", "profile": "g1", "model": "gpt-6.1-sol", "reasoning": "high", "backend": "codex"}]}},
                {"id": "beta", "label": "Beta", "command": [sys.executable, "-c", "import json; print(json.dumps({'sessions':[{'id':'b-1','profile':'g2','model':'gpt-6-luna','reasoning':'low','backend':'herdr'}]}))"]}
            ]
        }))
        out = root / "snapshot.json"
        subprocess.run([sys.executable, str(SCRIPT), "doctor", "--config", str(config)], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable, str(SCRIPT), "snapshot", "--config", str(config), "--out", str(out)], check=True, stdout=subprocess.DEVNULL)
        snapshot = json.loads(out.read_text())
        assert snapshot["schema"].endswith("snapshot.v1") and len(snapshot["boxes"]) == 2
        assert snapshot["boxes"][0]["sessions"][0]["model"] == "gpt-6.1-sol"
        assert "UNKNOWN" not in snapshot["boxes"][1]["sessions"][0]["model"]
    print("PASS: model fleet observatory structure, adapter snapshot and doctor")


if __name__ == "__main__":
    main()
