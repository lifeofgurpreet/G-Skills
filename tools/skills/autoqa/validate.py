#!/usr/bin/env python3
"""AutoQA source regression gate plus isolated exported-folder acceptance."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
from package_check import cold_check, validate_files

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills" / "autoqa"


def main():
    subprocess.run([sys.executable, "-B", "-m", "unittest", "discover",
                    "-s", str(SKILL / "tests"), "-v"], cwd=ROOT, check=True, timeout=180)
    with tempfile.TemporaryDirectory(prefix="autoqa-export-") as temp:
        exported = Path(temp) / "autoqa"
        shutil.copytree(SKILL, exported, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copyfile(ROOT / "LICENSE", exported / "LICENSE")
        files = {path.relative_to(exported).as_posix(): path.read_bytes()
                 for path in exported.rglob("*") if path.is_file()}
        validate_files(files, require_license=True)
        cold_check(exported)
    print("PASS: AutoQA regression suite and exported-folder cold CLI acceptance")


if __name__ == "__main__":
    main()
