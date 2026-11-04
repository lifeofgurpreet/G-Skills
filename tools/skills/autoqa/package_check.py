#!/usr/bin/env python3
"""Export acceptance: only standard-library code and the supplied skill folder."""
import argparse
import ast
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile

REQUIRED = {
    "SKILL.md", "skill.json", "THIRD_PARTY_NOTICES.txt",
    "scripts/autoqa.py", "tests/test_autoqa.py",
    "assets/example-plan.json", "references/ledger-schema.md",
    "references/evidence-contract.md", "references/journey-profiles.md",
    "references/repository-contract.md", "references/upstream-review.md",
}


def validate_files(files, require_license=True):
    missing = REQUIRED - set(files)
    if require_license:
        missing |= {"LICENSE"} - set(files)
    if missing:
        raise ValueError("AutoQA package is missing: " + ", ".join(sorted(missing)))
    for name in files:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise ValueError("Unsafe package path: " + name)
        if name.startswith(("skills/", "tools/", ".github/", ".beads/")):
            raise ValueError("Repository scaffolding is nested in the exported skill.")
        if "__pycache__" in path.parts or path.suffix == ".pyc" or path.name == "run.json":
            raise ValueError("Generated/private run content is not an export input.")
    meta = json.loads(files["skill.json"])
    if meta["name"] != "autoqa" or meta["version"] != "0.1.0":
        raise ValueError("Unexpected AutoQA package identity/version.")
    source = files["scripts/autoqa.py"].decode("utf-8")
    ast.parse(source)
    if 'VERSION = "' + meta["version"] + '"' not in source:
        raise ValueError("Manifest/helper versions differ.")
    if json.loads(files["assets/example-plan.json"])["schema"] != "autoqa.plan.v1":
        raise ValueError("Synthetic example plan is missing or has an unsupported schema.")


def cold_check(target):
    """Run the actual exported entry point; never import repository/helper modules."""
    target = Path(target).resolve()
    entry = target / "scripts" / "autoqa.py"
    with tempfile.TemporaryDirectory(prefix="autoqa-cold-") as temp:
        work = Path(temp)
        def command(*args, expect=0):
            result = subprocess.run([sys.executable, "-I", "-B", str(entry), *map(str, args)],
                                    cwd=work, capture_output=True, text=True, timeout=20)
            if result.returncode != expect or "Traceback" in result.stdout + result.stderr:
                raise ValueError("Exported CLI acceptance failed: " + result.stdout + result.stderr)
            return result.stdout
        plan = work / "plan.json"
        plan.write_bytes((target / "assets" / "example-plan.json").read_bytes())
        run = work / "run"
        initial = json.loads(command("init", run, "--plan", plan, "--run-id", "cold-run"))
        if initial["candidate_ready"]:
            raise ValueError("A new run defaulted to ready.")
        incomplete = json.loads(command("validate", run, expect=1))
        if incomplete["candidate_ready"] or incomplete["counts"]["results"]["NOT_RUN"] != 1:
            raise ValueError("Incomplete run was not gated.")
        report = work / "incomplete.md"
        command("report", run, "--output", report, expect=1)
        if "candidate_ready: false" not in report.read_text():
            raise ValueError("Incomplete report did not render honestly.")
        ledger = json.loads((run / "run.json").read_text())
        ledger["cases"][0].update(result="PASS", outcome="completed", depth="e2e",
                                  observation="Synthetic create/read fixture reached its terminal state.")
        ledger.update(cleanup_reviewed=True, cleanup_summary="No external resources; only synthetic files.")
        (run / "run.json").write_text(json.dumps(ledger))
        artifact = run / "evidence" / "witness.txt"
        artifact.write_text("Synthetic create/read fixture terminal observation.\n")
        command("attach", run, "--case", "CASE-1", "--id", "witness", "--path", "evidence/witness.txt")
        ready = json.loads(command("validate", run))
        if not ready["candidate_ready"] or ready["counts"]["verified_evidence"] != 1:
            raise ValueError("Complete synthetic ledger did not validate.")
        rendered = command("report", run)
        if "## Verified evidence" not in rendered or "caller attestations" not in rendered:
            raise ValueError("Report lost witness detail or limitations.")
        artifact.write_text("Changed synthetic witness.\n")
        invalid = json.loads(command("validate", run, expect=2))
        if invalid["candidate_ready"] or invalid["issues"][0]["code"] != "EVIDENCE_TAMPERED":
            raise ValueError("Tampered evidence was accepted.")
        command("attach", run, "--case", "CASE-1", "--id", "replacement",
                "--path", "evidence/witness.txt", expect=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-dir", required=True, type=Path)
    args = parser.parse_args()
    files = {}
    for path in args.skill_dir.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlink is not an export input: " + str(path))
        if path.is_file():
            files[path.relative_to(args.skill_dir).as_posix()] = path.read_bytes()
    validate_files(files)
    cold_check(args.skill_dir)
    print("PASS: isolated AutoQA CLI init, incomplete report, sealed ready ledger, tamper rejection, no reseal")


if __name__ == "__main__":
    main()
