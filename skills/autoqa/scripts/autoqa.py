#!/usr/bin/env python3
"""Offline AutoQA evidence ledger. No commands, plans, or artifact content execute."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import uuid

VERSION = "0.1.0"
RESULTS = ("PASS", "FAIL", "BLOCKED", "NOT_RUN", "OUT_OF_SCOPE")
OUTCOMES = ("completed", "partial", "safely_unavailable", "unknown", "not_applicable")
DEPTHS = ("e2e", "smoke", "contract", "static")
DISPOSITIONS = ("removed", "restored", "retained", "failed", "pending")
ID = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")
HEX = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
LIMITATION = ("This helper checks ledger consistency and local artifact integrity. "
              "Source/runtime identities and observations are caller attestations. "
              "It does not independently prove artifact truth, live provenance, "
              "inventory completeness, or release safety.")


class Invalid(Exception):
    def __init__(self, code, path, message):
        self.issue = dict(code=code, path=path, message=message, category="invalid")
        super().__init__(message)


def need(ok, path, message, code="SCHEMA"):
    if not ok:
        raise Invalid(code, path, message)


def fields(value, names, path):
    need(type(value) is dict, path, "Expected an object.")
    need(set(value) == set(names.split()), path,
         "Expected exactly these fields: " + names)
    return value


def string(value, path, nonempty=True):
    need(type(value) is str, path, "Expected a string.")
    need(not nonempty or bool(value.strip()), path, "Expected a nonempty string.")
    return value


def enum(value, choices, path):
    string(value, path)
    need(value in choices, path, "Expected one of: " + ", ".join(choices))


def identifier(value, path):
    string(value, path)
    need(bool(ID.fullmatch(value)), path, "Invalid ID (ASCII letter, then letters/digits/._-, max 64).")


def digest(value, path, pattern=SHA, nullable=False):
    if nullable and value is None:
        return
    string(value, path)
    need(bool(pattern.fullmatch(value)), path, "Invalid lowercase hexadecimal digest.")


def array(value, path):
    need(type(value) is list, path, "Expected an array.")
    return value


def unique_rows(value, path, opaque=False):
    rows = {}
    for i, row in enumerate(array(value, path)):
        p = f"{path}[{i}]"
        need(type(row) is dict and "id" in row, p, "Expected object with id.")
        if opaque:
            string(row["id"], p + ".id")
            need(len(row["id"]) <= 256 and not any(ord(c) < 32 for c in row["id"]), p + ".id", "Invalid opaque resource ID.")
        else:
            identifier(row["id"], p + ".id")
        need(row["id"] not in rows, p + ".id", "Duplicate ID.", "DUPLICATE_ID")
        rows[row["id"]] = row
    return rows


def id_list(value, path, known=None, scoped=False):
    values = array(value, path)
    seen = set()
    for i, item in enumerate(values):
        p = f"{path}[{i}]"
        if scoped:
            string(item, p)
            parts = item.split(":")
            need(len(parts) == 2, p, "Expected run_id:token.")
            for part in parts:
                identifier(part, p)
        else:
            identifier(item, p)
        need(item not in seen, p, "Duplicate reference.", "DUPLICATE_ID")
        need(known is None or item in known, p, "Unknown reference.")
        seen.add(item)
    return values


def timestamp(value, path):
    string(value, path)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        need(dt.tzinfo is not None, path, "Timestamp must include a timezone.")
    except ValueError:
        raise Invalid("SCHEMA", path, "Invalid ISO timestamp.")


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def pairs(items):
    obj = {}
    for key, value in items:
        need(key not in obj, key, "Duplicate JSON key.", "DUPLICATE_KEY")
        obj[key] = value
    return obj


def load(path):
    try:
        need(path.is_file() and not path.is_symlink(), str(path), "Expected a regular JSON file.", "IO")
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                          parse_constant=lambda x: need(False, str(path), "Nonfinite number.", "JSON"))
    except (ValueError, UnicodeError) as exc:
        raise Invalid("JSON", str(path), "Invalid JSON: " + str(exc))


def validate_plan(plan):
    fields(plan, "schema source runtime inventory cases", "plan")
    need(plan["schema"] == "autoqa.plan.v1", "plan.schema", "Unsupported plan schema.")
    source = fields(plan["source"], "commit tree worktree dirty_summary dirty_digest", "source")
    for name in ("commit", "tree"):
        digest(source[name], "source." + name, HEX, True)
    enum(source["worktree"], ("clean", "dirty", "unknown"), "source.worktree")
    string(source["dirty_summary"], "source.dirty_summary", False)
    digest(source["dirty_digest"], "source.dirty_digest", nullable=True)
    runtime = fields(plan["runtime"],
                     "instance build source_commit source_tree dirty_digest observation", "runtime")
    for name in ("instance", "build"):
        if runtime[name] is not None:
            string(runtime[name], "runtime." + name)
    for name in ("source_commit", "source_tree"):
        digest(runtime[name], "runtime." + name, HEX, True)
    digest(runtime["dirty_digest"], "runtime.dirty_digest", nullable=True)
    string(runtime["observation"], "runtime.observation", False)
    inventory = unique_rows(plan["inventory"], "inventory")
    for key, item in inventory.items():
        p = "inventory." + key
        fields(item, "id title selected required kind required_depth", p)
        string(item["title"], p + ".title")
        for name in ("selected", "required"):
            need(type(item[name]) is bool, p + "." + name, "Expected a boolean.")
        enum(item["kind"], ("journey", "safety", "health"), p + ".kind")
        enum(item["required_depth"], DEPTHS, p + ".required_depth")
    cases = unique_rows(plan["cases"], "plan.cases")
    for key, case in cases.items():
        p = "plan.cases." + key
        fields(case, "id inventory_id title purpose entry_point expected", p)
        need(case["inventory_id"] in inventory, p + ".inventory_id", "Unknown inventory ID.")
        for name in ("title", "entry_point", "expected"):
            string(case[name], p + "." + name)
        enum(case["purpose"], ("journey", "guardrail"), p + ".purpose")
    return inventory, cases


def local_path(root, relative, evidence=False):
    string(relative, "path")
    parts = relative.split("/")
    need(not any(p in ("", ".", "..") for p in parts) and "\\" not in relative
         and ":" not in relative and not PurePosixPath(relative).is_absolute(),
         "path", "Expected a normalized relative local path.", "UNSAFE_PATH")
    need(not evidence or (len(parts) > 1 and parts[0] == "evidence"),
         "path", "Artifacts must be beneath evidence/.", "UNSAFE_PATH")
    path = root
    for part in parts:
        path = path / part
        need(not path.is_symlink(), relative, "Symlinks are forbidden.", "UNSAFE_PATH")
    need(path.resolve().is_relative_to(root), relative, "Path escapes run.", "UNSAFE_PATH")
    return path


def file_hash(path):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode), str(path), "Expected a regular file.", "EVIDENCE")
        need(before.st_size > 0, str(path), "Empty evidence cannot witness a result.", "EVIDENCE")
        h = hashlib.sha256()
        for block in iter(lambda: stream.read(65536), b""):
            h.update(block)
        after = os.fstat(stream.fileno())
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
             (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
             str(path), "Artifact changed during hashing.", "EVIDENCE")
        return h.hexdigest(), after.st_size


def snapshot(case):
    return sha({key: value for key, value in case.items() if key != "evidence"})


def read_run(directory):
    root = Path(directory).absolute()
    need(not root.is_symlink() and root.is_dir(), "run", "Expected a real run directory.")
    root = root.resolve()
    plan = load(local_path(root, "plan.json"))
    inventory, planned = validate_plan(plan)
    run = load(local_path(root, "run.json"))
    fields(run, "schema run_id run_nonce created_at plan_sha256 cases evidence resources "
           "cleanup_reviewed cleanup_summary findings", "run")
    need(run["schema"] == "autoqa.run.v1", "run.schema", "Unsupported run schema.")
    identifier(run["run_id"], "run.run_id")
    need(type(run["run_nonce"]) is str and bool(re.fullmatch(r"[0-9a-f]{32}", run["run_nonce"])),
         "run.run_nonce", "Expected a 32 digit lowercase nonce.")
    timestamp(run["created_at"], "run.created_at")
    digest(run["plan_sha256"], "run.plan_sha256")
    need(run["plan_sha256"] == sha(plan), "run.plan_sha256", "Frozen plan changed.", "PLAN_CHANGED")
    cases = unique_rows(run["cases"], "run.cases")
    for key, case in cases.items():
        p = "run.cases." + key
        fields(case, "id result outcome depth observation evidence", p)
        need(key in planned, p, "Case is absent from frozen plan.")
        enum(case["result"], RESULTS, p + ".result")
        enum(case["outcome"], OUTCOMES, p + ".outcome")
        enum(case["depth"], DEPTHS, p + ".depth")
        string(case["observation"], p + ".observation", False)
        id_list(case["evidence"], p + ".evidence", scoped=True)
    need(type(run["cleanup_reviewed"]) is bool, "cleanup_reviewed", "Expected a boolean.")
    string(run["cleanup_summary"], "cleanup_summary", False)
    for key, resource in unique_rows(run["resources"], "resources", opaque=True).items():
        p = "resources." + key
        fields(resource, "id case_id description disposition observation", p)
        need(resource["case_id"] in planned, p + ".case_id", "Unknown case ID.")
        string(resource["description"], p + ".description")
        enum(resource["disposition"], DISPOSITIONS, p + ".disposition")
        string(resource["observation"], p + ".observation", False)
    for key, finding in unique_rows(run["findings"], "findings").items():
        p = "findings." + key
        fields(finding, "id case_ids severity description task_ids", p)
        need(bool(id_list(finding["case_ids"], p + ".case_ids", planned)), p, "Finding needs a case.")
        enum(finding["severity"], ("critical", "high", "medium", "low", "info"), p + ".severity")
        string(finding["description"], p + ".description")
        tasks = array(finding["task_ids"], p + ".task_ids")
        for task in tasks:
            string(task, p + ".task_ids")
        need(len(tasks) == len(set(tasks)), p + ".task_ids", "Duplicate task reference.")
    array(run["evidence"], "evidence")
    return root, plan, run, inventory, planned, cases


def verify_evidence(root, plan, run, cases, require_witness=True):
    seals, paths, referenced = {}, set(), set()
    for i, seal in enumerate(run["evidence"]):
        p = f"evidence[{i}]"
        fields(seal, "id run_id run_nonce case_id path sha256 bytes plan_sha256 runtime_sha256 "
               "case_sha256 sealed_at", p)
        id_list([seal["id"]], p + ".id", scoped=True)
        need(seal["id"].startswith(run["run_id"] + ":") and seal["run_id"] == run["run_id"]
             and seal["run_nonce"] == run["run_nonce"], p, "Cross-run evidence.", "EVIDENCE_BINDING")
        need(seal["id"] not in seals and seal["path"] not in paths,
             p, "Duplicate evidence ID or path.", "DUPLICATE_ID")
        need(seal["case_id"] in cases, p + ".case_id", "Evidence has no result row.")
        for name in ("sha256", "plan_sha256", "runtime_sha256", "case_sha256"):
            digest(seal[name], p + "." + name)
        need(type(seal["bytes"]) is int and seal["bytes"] > 0, p + ".bytes", "Expected positive integer.")
        timestamp(seal["sealed_at"], p + ".sealed_at")
        need(seal["plan_sha256"] == run["plan_sha256"]
             and seal["runtime_sha256"] == sha(plan["runtime"])
             and seal["case_sha256"] == snapshot(cases[seal["case_id"]]),
             p, "Stale plan, runtime, or case snapshot.", "EVIDENCE_BINDING")
        path = local_path(root, seal["path"], evidence=True)
        actual, length = file_hash(path)
        need(actual == seal["sha256"] and length == seal["bytes"],
             p, "Artifact digest or size mismatch.", "EVIDENCE_TAMPERED")
        seals[seal["id"]] = seal
        paths.add(seal["path"])
    for key, case in cases.items():
        for ref in case["evidence"]:
            need(ref in seals and seals[ref]["case_id"] == key,
                 "cases." + key, "Missing or wrong-case evidence.", "EVIDENCE_BINDING")
            referenced.add(ref)
        if case["result"] in ("PASS", "FAIL"):
            need(bool(case["observation"].strip()), "cases." + key,
                 "PASS/FAIL requires an actual stated observation.", "OBSERVATION_REQUIRED")
            if require_witness:
                need(bool(case["evidence"]), "cases." + key,
                     "PASS/FAIL requires sealed nonempty evidence.", "WITNESS_REQUIRED")
    need(referenced == set(seals), "evidence", "Unreferenced evidence seal.", "EVIDENCE_BINDING")


def evaluate(directory, require_witness=True):
    root, plan, run, inventory, planned, cases = read_run(directory)
    verify_evidence(root, plan, run, cases, require_witness)
    issues = []
    def issue(code, path, message, category="incomplete"):
        issues.append(dict(code=code, path=path, message=message, category=category))
    selected = {key for key, case in planned.items() if inventory[case["inventory_id"]]["selected"]}
    required = {key: item for key, item in inventory.items() if item["selected"] and item["required"]}
    for key, item in inventory.items():
        if item["required"] and not item["selected"]:
            issue("REQUIRED_UNSELECTED", "inventory." + key, "Required item was excluded from selection.")
        if item["selected"] and not any(c["inventory_id"] == key for c in planned.values()):
            issue("SELECTED_UNCOVERED", "inventory." + key, "Selected inventory item has no planned case.")
    result_counts = Counter(cases[key]["result"] if key in cases else "MISSING" for key in planned)
    selected_counts = Counter(cases[key]["result"] if key in cases else "MISSING" for key in selected)
    for key in sorted(selected):
        case = cases.get(key)
        result = case["result"] if case else "MISSING"
        if result in ("MISSING", "NOT_RUN", "BLOCKED", "OUT_OF_SCOPE"):
            issue(result, "cases." + key, "Selected case is " + result,
                  "blocked" if result == "BLOCKED" else "incomplete")
    for key, case in cases.items():
        if case["result"] == "FAIL":
            issue("PRODUCT_FAILURE", "cases." + key, "Observed product case failed.", "failed")
    represented = satisfied = completed = e2e = safety = 0
    for key, item in inventory.items():
        if not item["selected"]:
            continue
        keys = [k for k, c in planned.items() if c["inventory_id"] == key]
        present = bool(keys) and all(k in cases for k in keys)
        represented += int(present and item["required"])
        ok = present
        for case_id in keys:
            row = cases.get(case_id)
            if not row:
                continue
            purpose = planned[case_id]["purpose"]
            terminal = (row["outcome"] == "completed" and purpose == "journey"
                        if item["kind"] == "journey" else
                        row["outcome"] in ("completed", "safely_unavailable", "not_applicable")
                        and purpose == "guardrail")
            ok = ok and row["result"] == "PASS" and terminal and row["depth"] == item["required_depth"]
        if not ok:
            unavailable = any(cases.get(k, {}).get("outcome") == "safely_unavailable" for k in keys)
            issue("REQUIRED_UNSATISFIED" if item["required"] else "SELECTED_UNSATISFIED", "inventory." + key,
                  "Selected item lacks all planned PASS outcomes at its declared depth.",
                  "blocked" if unavailable else "incomplete")
        satisfied += int(ok and item["required"])
        completed += int(ok and item["required"] and item["kind"] == "journey")
        e2e += int(ok and item["required"] and item["kind"] == "journey" and item["required_depth"] == "e2e")
        safety += int(ok and item["required"] and item["kind"] == "safety")
    if not e2e:
        issue("NO_E2E_JOURNEY", "inventory", "At least one required completed e2e user journey is needed.")
    source, runtime = plan["source"], plan["runtime"]
    known = lambda x: isinstance(x, str) and bool(x.strip()) and x.strip().lower() not in (
        "unknown", "none", "n/a", "unset", "?")
    provenance = (source["commit"] is not None and source["tree"] is not None
                  and all(known(runtime[n]) for n in ("instance", "build", "observation"))
                  and source["commit"] == runtime["source_commit"]
                  and source["tree"] == runtime["source_tree"]
                  and source["worktree"] in ("clean", "dirty"))
    if source["worktree"] == "dirty":
        provenance = provenance and bool(source["dirty_summary"].strip()) and source["dirty_digest"] is not None
    elif source["worktree"] == "clean":
        provenance = provenance and source["dirty_digest"] is None
    provenance = provenance and source["dirty_digest"] == runtime["dirty_digest"]
    if not provenance:
        issue("PROVENANCE_UNKNOWN_OR_MISMATCH", "plan",
              "Source/runtime attestations are unknown, incomplete, or mismatched; instance-only scope.", "provenance")
    if not run["cleanup_reviewed"] or not run["cleanup_summary"].strip():
        issue("CLEANUP_UNREVIEWED", "cleanup_reviewed", "Explicit cleanup review and summary required.")
    for resource in run["resources"]:
        if resource["disposition"] not in ("removed", "restored") or not resource["observation"].strip():
            issue("CLEANUP_UNRESOLVED", "resources." + resource["id"],
                  "Resource remains or cleanup is unverified.", "blocked")
    for finding in run["findings"]:
        if finding["severity"] in ("critical", "high"):
            issue("OPEN_FINDING", "findings." + finding["id"], "High/critical finding prevents readiness.", "blocked")
    categories = {i["category"] for i in issues}
    status = next((label for category, label in (("failed", "FAILED"), ("blocked", "BLOCKED"),
                  ("incomplete", "INCOMPLETE"), ("provenance", "INSTANCE_ONLY")) if category in categories), "READY")
    counts = {
        "planned_cases": len(planned), "selected_cases": len(selected), "represented_cases": len(cases),
        "results": {k: result_counts[k] for k in RESULTS + ("MISSING",)},
        "selected_results": {k: selected_counts[k] for k in RESULTS + ("MISSING",)},
        "executed_depths": {d: sum(c["depth"] == d and c["result"] in ("PASS", "FAIL") for c in cases.values()) for d in DEPTHS},
        "outcomes": {o: sum(c["outcome"] == o for c in cases.values()) for o in OUTCOMES},
        "inventory": {"total": len(inventory), "selected": sum(i["selected"] for i in inventory.values()),
                      "selected_required": len(required), "required_represented": represented, "required_satisfied": satisfied,
                      "required_unselected": sum(i["required"] and not i["selected"] for i in inventory.values()),
                      "selected_without_cases": sum(i["selected"] and not any(c["inventory_id"] == k for c in planned.values()) for k, i in inventory.items())},
        "journeys": {"required": sum(i["kind"] == "journey" for i in required.values()),
                     "completed": completed, "e2e_completed": e2e},
        "safety": {"required": sum(i["kind"] == "safety" for i in required.values()), "satisfied": safety,
                   "guardrail_passes": sum(c["result"] == "PASS" and planned[k]["purpose"] == "guardrail" for k, c in cases.items())},
        "resources": {d: sum(r["disposition"] == d for r in run["resources"]) for d in DISPOSITIONS},
        "verified_evidence": len(run["evidence"]),
    }
    return dict(schema="autoqa.validation.v1", version=VERSION, valid=True, run_id=run["run_id"],
                status=status, candidate_ready=status == "READY",
                provenance_scope="candidate_attestation" if provenance else "instance_only",
                counts=counts, issues=issues, limitation=LIMITATION), plan, run


def cell(value):
    escaped = html.escape(str(value), quote=False).replace("\\", "\\\\")
    for char in chr(96) + "*_{}[]()#+-.!|:@~=":
        escaped = escaped.replace(char, "\\" + char)
    return escaped.replace("\r", "").replace("\n", "<br>")


def report_text(result, plan, run):
    lines = ["# AutoQA evidence report", "", f"**{result['status']}** — candidate_ready: "
             + str(result["candidate_ready"]).lower(), "", "Run: " + cell(run["run_id"]), "",
             "Provenance scope: " + result["provenance_scope"], "", LIMITATION, "",
             "## Coverage", "", "Journey completion and safety satisfaction counts describe required obligations; guardrail passes include all cases.", "", "| Measure | Count |", "| --- | --- |"]
    counts = result["counts"]
    for group in ("results", "executed_depths", "journeys", "safety", "inventory", "resources"):
        for name, count in counts[group].items():
            lines.append(f"| {cell(group + '.' + name)} | {count} |")
    rows = {r["id"]: r for r in run["cases"]}
    lines += ["", "## Frozen inventory", "", "| Item | Title | Selected | Required | Kind | Required depth | Planned / represented |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for item in plan["inventory"]:
        keys = [c["id"] for c in plan["cases"] if c["inventory_id"] == item["id"]]
        values = (item["id"], item["title"], item["selected"], item["required"], item["kind"],
                  item["required_depth"], f"{len(keys)} / {sum(k in rows for k in keys)}")
        lines.append("| " + " | ".join(cell(v) for v in values) + " |")
    lines += ["", "## Frozen acceptance", "", "| Case | Inventory | Entry point | Expected observation |",
              "| --- | --- | --- | --- |"]
    for case in plan["cases"]:
        lines.append("| " + " | ".join(cell(case[k]) for k in ("id", "inventory_id", "entry_point", "expected")) + " |")
    lines += ["", "## Case ledger", "", "| Case | Purpose | Result | Outcome | Depth | Observation | Evidence |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    rows = {r["id"]: r for r in run["cases"]}
    for case in plan["cases"]:
        row = rows.get(case["id"], dict(result="MISSING", outcome="unknown", depth="—", observation="", evidence=[]))
        values = (case["id"], case["purpose"], row["result"], row["outcome"], row["depth"],
                  row["observation"], ", ".join(row["evidence"]))
        lines.append("| " + " | ".join(cell(v) for v in values) + " |")
    lines += ["", "## Verified evidence", "", "| Evidence ID | Case | Relative path | SHA256 | Bytes |",
              "| --- | --- | --- | --- | --- |"]
    for seal in run["evidence"]:
        lines.append("| " + " | ".join(cell(seal[k]) for k in ("id", "case_id", "path", "sha256", "bytes")) + " |")
    lines += ["", "## Readiness constraints", ""]
    lines += ["- " + cell(i["code"] + ": " + i["message"]) for i in result["issues"]] or ["No ledger constraints remain."]
    lines += ["", "## Source and runtime attestations", "",
              "| Field | Attested value |", "| --- | --- |"]
    for group in ("source", "runtime"):
        for key, value in plan[group].items():
            lines.append("| " + cell(group + "." + key) + " | " + cell(value) + " |")
    lines += ["", "## Cleanup", "", cell(run["cleanup_summary"] or "Not reviewed."), "",
              "| Resource | Case | Description | Disposition | Observation |", "| --- | --- | --- | --- | --- |"]
    for r in run["resources"]:
        lines.append("| " + " | ".join(cell(r[k]) for k in ("id", "case_id", "description", "disposition", "observation")) + " |")
    lines += ["", "## Findings", "", "| Finding | Cases | Severity | Description | Existing tasks |",
              "| --- | --- | --- | --- | --- |"]
    for f in run["findings"]:
        values = (f["id"], ", ".join(f["case_ids"]), f["severity"], f["description"], ", ".join(f["task_ids"]))
        lines.append("| " + " | ".join(cell(v) for v in values) + " |")
    return "\n".join(lines) + "\n"


def write_new(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(content)


def encoded(value):
    return json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n"


def initialize(args):
    plan = load(Path(args.plan))
    validate_plan(plan)
    run_id = args.run_id or "run-" + uuid.uuid4().hex
    identifier(run_id, "run_id")
    root = Path(args.directory).absolute()
    root.mkdir(mode=0o700)
    (root / "evidence").mkdir(mode=0o700)
    run = dict(schema="autoqa.run.v1", run_id=run_id, run_nonce=uuid.uuid4().hex,
               created_at=now(), plan_sha256=sha(plan),
               cases=[dict(id=c["id"], result="NOT_RUN", outcome="unknown", depth="static",
                           observation="Not executed.", evidence=[]) for c in plan["cases"]],
               evidence=[], resources=[], cleanup_reviewed=False, cleanup_summary="", findings=[])
    write_new(root / "plan.json", encoded(plan))
    write_new(root / "run.json", encoded(run))
    return dict(run_id=run_id, directory=str(root), candidate_ready=False, status="INCOMPLETE")


def attach(args):
    root = Path(args.directory).absolute()
    lock = root / ".autoqa-lock"
    write_new(lock, "single-writer attachment\n")
    try:
        _, plan, run = evaluate(root, require_witness=False)
        identifier(args.case, "case")
        identifier(args.id, "id")
        rows = {row["id"]: row for row in run["cases"]}
        need(args.case in rows, "case", "Unknown case result row.")
        row = rows[args.case]
        need(row["result"] not in ("NOT_RUN", "OUT_OF_SCOPE"), "case", "Record the observation before sealing.")
        path = local_path(root.resolve(), args.path, evidence=True)
        evidence_id = run["run_id"] + ":" + args.id
        need(not any(s["id"] == evidence_id or s["path"] == args.path for s in run["evidence"]),
             "evidence", "ID/path already sealed; create a new run or a new artifact.", "ALREADY_SEALED")
        checksum, size = file_hash(path)
        seal = dict(id=evidence_id, run_id=run["run_id"], run_nonce=run["run_nonce"], case_id=args.case,
                    path=args.path, sha256=checksum, bytes=size, plan_sha256=run["plan_sha256"],
                    runtime_sha256=sha(plan["runtime"]), case_sha256=snapshot(row), sealed_at=now())
        run["evidence"].append(seal)
        row["evidence"].append(evidence_id)
        fd, temporary = tempfile.mkstemp(prefix=".run-", dir=root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(encoded(run))
            os.replace(temporary, root / "run.json")
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return seal
    finally:
        lock.unlink()


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Invalid("CLI", "arguments", message)


def main(argv=None):
    parser = Parser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    commands = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    init = commands.add_parser("init")
    init.add_argument("directory"); init.add_argument("--plan", required=True); init.add_argument("--run-id")
    seal = commands.add_parser("attach")
    seal.add_argument("directory"); seal.add_argument("--case", required=True)
    seal.add_argument("--id", required=True); seal.add_argument("--path", required=True)
    check = commands.add_parser("validate"); check.add_argument("directory")
    report = commands.add_parser("report"); report.add_argument("directory"); report.add_argument("--output")
    try:
        args = parser.parse_args(argv)
        if args.command in ("init", "attach"):
            print(encoded(initialize(args) if args.command == "init" else attach(args)), end="")
            return 0
        result, plan, run = evaluate(args.directory)
        if args.command == "report":
            content = report_text(result, plan, run)
            if args.output:
                write_new(Path(args.output), content)
                print(encoded(dict(report=args.output, status=result["status"], candidate_ready=result["candidate_ready"])), end="")
            else:
                print(content, end="")
        else:
            print(encoded(result), end="")
        return 0 if result["candidate_ready"] else 1
    except (Invalid, OSError, UnicodeError, RecursionError, TypeError, ValueError) as exc:
        item = exc.issue if isinstance(exc, Invalid) else dict(
            code="IO" if isinstance(exc, OSError) else "SCHEMA", path="input", message=str(exc), category="invalid")
        print(encoded(dict(schema="autoqa.validation.v1", version=VERSION, valid=False,
                           status="INVALID", candidate_ready=False, issues=[item], limitation=LIMITATION)), end="")
        return 2


if __name__ == "__main__":
    sys.exit(main())
