"""Regression tests exercise the exported CLI, using only synthetic local evidence."""
import copy
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1]
CLI = SKILL / "scripts" / "autoqa.py"


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="autoqa-test-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.plan = json.loads((SKILL / "assets" / "example-plan.json").read_text())
        self.number = 0
        self.new_run()

    def cli(self, *args, code=None):
        result = subprocess.run([sys.executable, "-B", str(CLI), *map(str, args)],
                                capture_output=True, text=True, timeout=15)
        self.assertNotIn("Traceback", result.stderr + result.stdout)
        if code is not None:
            self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def new_run(self):
        self.number += 1
        self.run = self.base / ("run-" + str(self.number))
        plan_file = self.base / "input.json"
        plan_file.write_text(json.dumps(self.plan))
        self.cli("init", self.run, "--plan", plan_file, "--run-id", "synthetic-run", code=0)

    def edit(self, mutate):
        path = self.run / "run.json"
        data = json.loads(path.read_text())
        mutate(data)
        path.write_text(json.dumps(data))

    def observe(self, result="PASS", outcome="completed", depth="e2e"):
        def change(data):
            for row in data["cases"]:
                row.update(result=result, outcome=outcome, depth=depth,
                           observation="Synthetic record was created and read back at its terminal state.")
            data.update(cleanup_reviewed=True, cleanup_summary="Synthetic run created no external resources.")
        self.edit(change)

    def witness(self, case="CASE-1", evidence_id="artifact-1", text="Synthetic observed terminal record.\n"):
        path = "evidence/" + evidence_id + ".txt"
        (self.run / path).write_text(text)
        return self.cli("attach", self.run, "--case", case, "--id", evidence_id, "--path", path)

    def ready(self):
        self.observe()
        for i, case in enumerate(self.plan["cases"]):
            self.assertEqual(self.witness(case["id"], "artifact-" + str(i)).returncode, 0)

    def validation(self, code=0):
        return json.loads(self.cli("validate", self.run, code=code).stdout)

    def invalid(self, code=None):
        data = self.validation(2)
        self.assertFalse(data["valid"])
        self.assertFalse(data["candidate_ready"])
        if code:
            self.assertEqual(data["issues"][0]["code"], code)
        return data

    def test_init_never_passes_and_is_private(self):
        data = self.validation(1)
        self.assertEqual(data["counts"]["results"]["NOT_RUN"], 1)
        self.assertEqual(data["status"], "INCOMPLETE")
        self.assertFalse(data["candidate_ready"])
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(self.run.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((self.run / "run.json").stat().st_mode), 0o600)

    def test_complete_attested_journey_can_be_ready(self):
        self.ready()
        data = self.validation()
        self.assertTrue(data["candidate_ready"])
        self.assertEqual(data["counts"]["journeys"]["e2e_completed"], 1)
        self.assertEqual(data["counts"]["safety"]["guardrail_passes"], 0)
        self.assertIn("caller attestations", data["limitation"])

    def test_missing_row_keeps_denominator(self):
        self.edit(lambda data: data.update(cases=[]))
        data = self.validation(1)
        self.assertEqual(data["counts"]["results"]["MISSING"], 1)
        self.assertEqual(data["counts"]["inventory"]["selected_required"], 1)
        self.assertEqual(data["counts"]["inventory"]["required_represented"], 0)

    def test_missing_required_item_cases_keeps_denominator(self):
        item = copy.deepcopy(self.plan["inventory"][0])
        item["id"] = "JOURNEY-2"
        self.plan["inventory"].append(item)
        self.new_run()
        self.ready()
        data = self.validation(1)
        self.assertEqual(data["counts"]["inventory"]["selected_required"], 2)
        self.assertEqual(data["counts"]["inventory"]["required_satisfied"], 1)

    def test_pass_requires_stated_observation(self):
        self.observe()
        self.edit(lambda data: data["cases"][0].update(observation="  "))
        self.invalid("OBSERVATION_REQUIRED")

    def test_pass_requires_witness(self):
        self.observe()
        self.invalid("WITNESS_REQUIRED")

    def test_empty_artifact_rejected(self):
        self.observe()
        result = self.witness(text="")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["issues"][0]["code"], "EVIDENCE")

    def test_tampered_artifact_rejected(self):
        self.ready()
        (self.run / "evidence" / "artifact-0.txt").write_text("Altered synthetic content")
        self.invalid("EVIDENCE_TAMPERED")

    def test_artifact_size_mismatch_rejected(self):
        self.ready()
        self.edit(lambda data: data["evidence"][0].update(bytes=1))
        self.invalid("EVIDENCE_TAMPERED")

    def test_unsafe_paths_rejected(self):
        self.observe()
        for value in ("../outside.txt", "/absolute.txt", "https://example.invalid/evidence",
                      "evidence/../run.json", "evidence//a", "evidence\\a", "evidence/./a"):
            with self.subTest(path=value):
                result = self.cli("attach", self.run, "--case", "CASE-1", "--id", "bad",
                                  "--path", value, code=2)
                self.assertEqual(json.loads(result.stdout)["issues"][0]["code"], "UNSAFE_PATH")

    def test_file_and_directory_symlinks_rejected(self):
        self.observe()
        outside = self.base / "outside.txt"
        outside.write_text("Synthetic external content")
        (self.run / "evidence" / "linked.txt").symlink_to(outside)
        self.cli("attach", self.run, "--case", "CASE-1", "--id", "bad",
                 "--path", "evidence/linked.txt", code=2)
        (self.run / "evidence" / "linked-dir").symlink_to(self.base, target_is_directory=True)
        self.cli("attach", self.run, "--case", "CASE-1", "--id", "bad",
                 "--path", "evidence/linked-dir/outside.txt", code=2)

    def test_artifact_replaced_by_symlink_rejected(self):
        self.ready()
        artifact = self.run / "evidence" / "artifact-0.txt"
        outside = self.base / "copy.txt"
        outside.write_bytes(artifact.read_bytes())
        artifact.unlink()
        artifact.symlink_to(outside)
        self.invalid("UNSAFE_PATH")

    def test_plan_changes_invalidate_seals(self):
        self.ready()
        plan = json.loads((self.run / "plan.json").read_text())
        plan["runtime"]["build"] = "changed-build"
        (self.run / "plan.json").write_text(json.dumps(plan))
        self.invalid("PLAN_CHANGED")

    def test_cross_run_nonce_rejected_even_same_run_id(self):
        self.ready()
        self.edit(lambda data: data["evidence"][0].update(run_nonce="f" * 32))
        self.invalid("EVIDENCE_BINDING")

    def test_cross_run_id_rejected(self):
        self.ready()
        self.edit(lambda data: data["evidence"][0].update(run_id="another-run"))
        self.invalid("EVIDENCE_BINDING")

    def test_wrong_runtime_hash_rejected(self):
        self.ready()
        self.edit(lambda data: data["evidence"][0].update(runtime_sha256="f" * 64))
        self.invalid("EVIDENCE_BINDING")

    def test_changed_observation_requires_new_evidence(self):
        self.ready()
        self.edit(lambda data: data["cases"][0].update(observation="Different observation"))
        self.invalid("EVIDENCE_BINDING")

    def test_second_attachment_keeps_first_valid(self):
        self.ready()
        self.assertEqual(self.witness(evidence_id="additional").returncode, 0)
        self.assertEqual(self.validation()["counts"]["verified_evidence"], 2)

    def test_no_implicit_reseal(self):
        self.ready()
        self.cli("attach", self.run, "--case", "CASE-1", "--id", "artifact-0",
                 "--path", "evidence/artifact-0.txt", code=2)
        original = (self.run / "evidence" / "artifact-0.txt").read_bytes()
        self.assertIn(b"Synthetic", original)
        (self.run / "evidence" / "artifact-0.txt").write_bytes(b"Tampered")
        self.cli("attach", self.run, "--case", "CASE-1", "--id", "replacement",
                 "--path", "evidence/artifact-0.txt", code=2)
        self.invalid("EVIDENCE_TAMPERED")

    def test_wrong_case_reference_rejected(self):
        other = copy.deepcopy(self.plan["cases"][0])
        other["id"] = "CASE-2"
        self.plan["cases"].append(other)
        self.new_run()
        self.ready()
        def change(data):
            data["cases"][0]["evidence"] = data["cases"][1]["evidence"]
        self.edit(change)
        self.invalid("EVIDENCE_BINDING")

    def test_duplicate_case_ids_rejected(self):
        self.edit(lambda data: data["cases"].append(copy.deepcopy(data["cases"][0])))
        self.invalid("DUPLICATE_ID")

    def test_duplicate_evidence_ids_rejected(self):
        self.ready()
        self.edit(lambda data: data["evidence"].append(copy.deepcopy(data["evidence"][0])))
        self.invalid("DUPLICATE_ID")

    def test_duplicate_json_keys_rejected(self):
        path = self.run / "run.json"
        path.write_text(path.read_text().replace('"cleanup_reviewed": false',
                                                '"cleanup_reviewed": false, "cleanup_reviewed": true'))
        self.invalid("DUPLICATE_KEY")

    def test_nonfinite_numbers_rejected(self):
        path = self.run / "run.json"
        path.write_text(path.read_text().replace('"cleanup_reviewed": false', '"cleanup_reviewed": NaN'))
        self.invalid("JSON")

    def test_malformed_types_have_structured_errors(self):
        self.edit(lambda data: data.update(cases="not an array"))
        self.invalid("SCHEMA")

    def test_malformed_ids_rejected(self):
        self.edit(lambda data: data["cases"][0].update(id="../case"))
        self.invalid("SCHEMA")

    def test_health_only_smoke_is_not_ready(self):
        self.plan["inventory"][0].update(kind="health", required_depth="smoke")
        self.plan["cases"][0].update(purpose="guardrail")
        self.new_run()
        self.observe(depth="smoke")
        self.assertEqual(self.witness().returncode, 0)
        data = self.validation(1)
        self.assertEqual(data["counts"]["journeys"]["completed"], 0)
        self.assertFalse(data["candidate_ready"])

    def test_guardrail_only_pass_does_not_complete_journey(self):
        self.plan["cases"][0].update(purpose="guardrail")
        self.new_run()
        self.ready()
        data = self.validation(1)
        self.assertEqual(data["counts"]["journeys"]["completed"], 0)
        self.assertEqual(data["counts"]["safety"]["guardrail_passes"], 1)

    def test_safely_unavailable_journey_blocks_readiness(self):
        self.observe(outcome="safely_unavailable")
        self.assertEqual(self.witness().returncode, 0)
        data = self.validation(1)
        self.assertEqual(data["status"], "BLOCKED")
        self.assertEqual(data["counts"]["journeys"]["completed"], 0)

    def test_blocked_infrastructure_is_distinct_from_failure(self):
        self.observe(result="BLOCKED", outcome="unknown", depth="smoke")
        data = self.validation(1)
        self.assertEqual(data["status"], "BLOCKED")
        self.assertEqual(data["counts"]["results"]["FAIL"], 0)

    def test_observed_product_failure_prevents_readiness(self):
        self.observe(result="FAIL", outcome="partial")
        self.assertEqual(self.witness().returncode, 0)
        self.assertEqual(self.validation(1)["status"], "FAILED")

    def test_unknown_provenance_is_instance_only(self):
        self.plan["source"]["commit"] = None
        self.new_run()
        self.ready()
        data = self.validation(1)
        self.assertEqual(data["status"], "INSTANCE_ONLY")
        self.assertEqual(data["provenance_scope"], "instance_only")

    def test_runtime_mismatch_is_instance_only(self):
        self.plan["runtime"]["source_tree"] = "3" * 40
        self.new_run()
        self.ready()
        self.assertEqual(self.validation(1)["status"], "INSTANCE_ONLY")

    def test_dirty_source_requires_summary_and_matching_digest(self):
        self.plan["source"].update(worktree="dirty", dirty_summary="", dirty_digest="4" * 64)
        self.plan["runtime"]["dirty_digest"] = "4" * 64
        self.new_run()
        self.ready()
        self.assertEqual(self.validation(1)["status"], "INSTANCE_ONLY")

    def test_cleanup_leftovers_and_failed_cleanup_block(self):
        self.ready()
        for disposition in ("retained", "failed", "pending"):
            with self.subTest(disposition=disposition):
                resource = dict(id="RESOURCE-1", case_id="CASE-1", description="Synthetic item",
                                disposition=disposition, observation="Synthetic cleanup still unresolved")
                self.edit(lambda data: data.update(resources=[resource]))
                self.assertEqual(self.validation(1)["status"], "BLOCKED")

    def test_cleanup_requires_explicit_review(self):
        self.ready()
        self.edit(lambda data: data.update(cleanup_reviewed=False))
        self.validation(1)

    def test_high_finding_blocks_and_maps_existing_task(self):
        self.ready()
        finding = dict(id="FINDING-1", case_ids=["CASE-1"], severity="high",
                       description="Synthetic unresolved defect", task_ids=["TASK-123"])
        self.edit(lambda data: data.update(findings=[finding]))
        self.assertEqual(self.validation(1)["status"], "BLOCKED")

    def test_finding_unknown_case_rejected(self):
        finding = dict(id="FINDING-1", case_ids=["UNKNOWN"], severity="low",
                       description="Synthetic defect", task_ids=[])
        self.edit(lambda data: data.update(findings=[finding]))
        self.invalid("SCHEMA")

    def test_incomplete_report_renders_and_escapes_table_cells(self):
        self.edit(lambda data: data["cases"][0].update(observation="a | b\n<script>literal</script>"))
        result = self.cli("report", self.run, code=1)
        self.assertIn("**INCOMPLETE**", result.stdout)
        self.assertIn("candidate_ready: false", result.stdout)
        self.assertIn("a \\| b<br>&lt;script&gt;", result.stdout)
        self.assertNotIn("<script>", result.stdout)

    def test_report_refuses_overwrite(self):
        target = self.base / "report.md"
        self.cli("report", self.run, "--output", target, code=1)
        original = target.read_bytes()
        self.cli("report", self.run, "--output", target, code=2)
        self.assertEqual(target.read_bytes(), original)

    def test_init_refuses_existing_directory(self):
        before = (self.run / "run.json").read_bytes()
        self.cli("init", self.run, "--plan", self.base / "input.json", code=2)
        self.assertEqual((self.run / "run.json").read_bytes(), before)

    def test_commands_in_plan_and_artifact_are_never_executed(self):
        marker = self.base / "must-not-exist"
        text = "$(touch " + str(marker) + ")"
        self.plan["cases"][0]["entry_point"] = text
        self.new_run()
        self.observe()
        self.assertEqual(self.witness(text=text).returncode, 0)
        self.validation()
        self.assertFalse(marker.exists())

    def test_empty_inventory_and_zero_checks_never_ready(self):
        self.plan.update(inventory=[], cases=[])
        self.new_run()
        self.edit(lambda data: data.update(cleanup_reviewed=True, cleanup_summary="No resources."))
        data = self.validation(1)
        self.assertEqual(data["counts"]["planned_cases"], 0)
        self.assertFalse(data["candidate_ready"])

    def test_selected_required_out_of_scope_cannot_disappear(self):
        self.observe(result="OUT_OF_SCOPE", outcome="not_applicable")
        data = self.validation(1)
        self.assertEqual(data["counts"]["results"]["OUT_OF_SCOPE"], 1)
        self.assertEqual(data["counts"]["inventory"]["required_satisfied"], 0)

    def test_lower_depth_does_not_satisfy_e2e(self):
        self.observe(depth="contract")
        self.assertEqual(self.witness().returncode, 0)
        data = self.validation(1)
        self.assertEqual(data["counts"]["executed_depths"]["contract"], 1)
        self.assertEqual(data["counts"]["journeys"]["e2e_completed"], 0)


    def test_optional_selected_inventory_without_case_is_uncovered(self):
        item = copy.deepcopy(self.plan["inventory"][0])
        item.update(id="OPTIONAL-1", required=False)
        self.plan["inventory"].append(item)
        self.new_run()
        self.ready()
        data = self.validation(1)
        self.assertEqual(data["counts"]["inventory"]["selected_without_cases"], 1)
        self.assertIn("SELECTED_UNCOVERED", {i["code"] for i in data["issues"]})

    def test_required_unselected_inventory_remains_visible(self):
        item = copy.deepcopy(self.plan["inventory"][0])
        item.update(id="EXCLUDED-1", selected=False)
        self.plan["inventory"].append(item)
        self.new_run()
        self.ready()
        data = self.validation(1)
        self.assertEqual(data["counts"]["inventory"]["required_unselected"], 1)
        self.assertIn("REQUIRED_UNSELECTED", {i["code"] for i in data["issues"]})

    def test_optional_selected_out_of_scope_still_prevents_readiness(self):
        item = copy.deepcopy(self.plan["inventory"][0])
        item.update(id="OPTIONAL-1", required=False)
        other = copy.deepcopy(self.plan["cases"][0])
        other.update(id="OPTIONAL-CASE", inventory_id="OPTIONAL-1")
        self.plan["inventory"].append(item)
        self.plan["cases"].append(other)
        self.new_run()
        self.observe()
        self.edit(lambda data: data["cases"][1].update(result="OUT_OF_SCOPE", outcome="not_applicable"))
        self.assertEqual(self.witness().returncode, 0)
        data = self.validation(1)
        self.assertIn("OUT_OF_SCOPE", {i["code"] for i in data["issues"]})

    def test_report_neutralizes_markdown_images_links_and_urls(self):
        observation = "![x](https://example.invalid/i) [x](https://example.invalid/) https://example.invalid"
        self.edit(lambda data: data["cases"][0].update(observation=observation))
        report = self.cli("report", self.run, code=1).stdout
        self.assertNotIn("![x](", report)
        self.assertNotIn("[x](", report)
        self.assertNotIn("https://", report)
        self.assertIn("\\!\\[x\\]\\(", report)

    def test_report_contains_acceptance_inventory_and_evidence_hash(self):
        self.ready()
        report = self.cli("report", self.run, code=0).stdout
        self.assertIn("## Frozen inventory", report)
        self.assertIn("## Frozen acceptance", report)
        self.assertIn("## Verified evidence", report)
        self.assertIn("evidence/artifact\\-0\\.txt", report)
        data = json.loads((self.run / "run.json").read_text())
        self.assertIn(data["evidence"][0]["sha256"], report)

    def test_numeric_resource_id_is_valid_and_duplicates_are_rejected(self):
        self.ready()
        resource = dict(id="42", case_id="CASE-1", description="Synthetic provider resource",
                        disposition="removed", observation="Read-back confirmed the synthetic item is gone.")
        self.edit(lambda data: data.update(resources=[resource]))
        self.validation()
        self.edit(lambda data: data["resources"].append(copy.deepcopy(resource)))
        self.invalid("DUPLICATE_ID")

    def test_missing_acceptance_criteria_rejected(self):
        self.plan["cases"][0]["expected"] = ""
        plan = self.base / "invalid-plan.json"
        plan.write_text(json.dumps(self.plan))
        result = self.cli("init", self.base / "invalid-run", "--plan", plan, code=2)
        self.assertEqual(json.loads(result.stdout)["issues"][0]["code"], "SCHEMA")

    def test_unknown_cli_option_returns_structured_error(self):
        result = self.cli("validate", self.run, "--invented-option", code=2)
        self.assertEqual(json.loads(result.stdout)["issues"][0]["code"], "CLI")


    def test_all_selected_items_must_meet_outcome_and_depth(self):
        item = copy.deepcopy(self.plan["inventory"][0])
        item.update(id="OPTIONAL-1", required=False)
        other = copy.deepcopy(self.plan["cases"][0])
        other.update(id="OPTIONAL-CASE", inventory_id="OPTIONAL-1")
        self.plan["inventory"].append(item)
        self.plan["cases"].append(other)
        for change in (dict(outcome="partial"), dict(outcome="unknown"), dict(depth="smoke")):
            with self.subTest(change=change):
                self.new_run()
                self.observe()
                self.edit(lambda data: data["cases"][1].update(change))
                self.assertEqual(self.witness("CASE-1", "required").returncode, 0)
                self.assertEqual(self.witness("OPTIONAL-CASE", "optional").returncode, 0)
                data = self.validation(1)
                self.assertEqual(data["counts"]["inventory"]["required_satisfied"], 1)
                self.assertEqual(data["counts"]["journeys"]["e2e_completed"], 1)
                self.assertIn("SELECTED_UNSATISFIED", {i["code"] for i in data["issues"]})


if __name__ == "__main__":
    unittest.main()
