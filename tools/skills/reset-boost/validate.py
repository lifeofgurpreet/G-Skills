#!/usr/bin/env python3
"""Reset Boost acceptance: provider-free unit tests plus a cold copy of the exported folder."""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills/reset-boost"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import package_check  # noqa: E402

# Public fixtures are synthetic: no personal home paths and no real mail addresses.
PRIVATE = re.compile(r"/Users/[A-Za-z]|/home/(?!u/)[a-z][a-z0-9_-]*/|[A-Za-z0-9._%+-]+@(?!example\.(?:test|invalid)\b)[A-Za-z0-9-]+\.[A-Za-z]{2,}")


def main():
    for path in sorted(SKILL.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            match = PRIVATE.search(path.read_text())
            if match:
                raise SystemExit(f"FAIL: private-looking path or address {match.group(0)!r} in {path.relative_to(ROOT)}")
    subprocess.run(["bash", "-n", str(SKILL / "scripts/install-watch.sh")], check=True)
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(SKILL / "tests"), "-p", "test_*.py"], check=True)
    with tempfile.TemporaryDirectory() as directory:
        # Exercise the actual exported folder, not imports from this repository.
        target = Path(directory) / "reset-boost"
        shutil.copytree(SKILL, target, ignore=shutil.ignore_patterns("__pycache__"))
        files = {f.relative_to(target).as_posix(): f.read_bytes() for f in target.rglob("*") if f.is_file()}
        package_check.validate_files(files, require_license=False)
        package_check.cold_check(target)
    print("PASS: reset-boost unit tests, privacy scan and cold exported-folder lifecycle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
