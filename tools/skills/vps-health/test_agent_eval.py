#!/usr/bin/env python3
"""Grader tests use fixtures, not live model claims. Native trials are separate."""
from pathlib import Path
import copy
import json
import tempfile
import unittest
import grade_agent_eval as evaluator


def native_fixture(error=False,model='fixture-model',tokens=20):
    return [{'type':'assistant','message':{'model':model,'content':[{'type':'tool_use','name':'Read'}]}},
            {'type':'result','subtype':'success','is_error':error,'usage':{'input_tokens':tokens,'output_tokens':tokens}}]


class EvalTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        (self.root/'outputs').mkdir();self.events(native_fixture())
    def events(self,events):
        (self.root/'trace.jsonl').write_text('\n'.join(json.dumps(e) for e in events)+'\n')
    def output(self,data):
        (self.root/'outputs/decision.json').write_text(json.dumps(data))
    def test_error_with_success_subtype_is_blocked_not_passed(self):
        self.events(native_fixture(True,'<synthetic>',0));r=evaluator.grade(self.root,1)
        self.assertEqual(r['state'],'BLOCKED_OR_NO_INFERENCE');self.assertIsNone(r['summary']);self.assertEqual(r['expectations'],[])
    def test_no_inference_never_creates_a_behavioral_zero_or_success(self):
        self.events(native_fixture(False,'<synthetic>',0))
        self.assertIsNone(evaluator.grade(self.root,2)['summary'])
    def test_inference_that_ends_in_error_is_incomplete_not_no_inference(self):
        self.events(native_fixture(True,'fixture-model',200))
        r=evaluator.grade(self.root,1);self.assertEqual(r['state'],'INCOMPLETE_EXECUTION');self.assertTrue(r['stop_dispatch'])
        self.assertIsNone(r['summary']);self.assertEqual(r['execution']['total_tokens'],400)
    def test_unknown_token_count_is_not_replaced_by_output_characters(self):
        events=native_fixture();events[-1].pop('usage');events[-1]['result']='Lots of characters are not tokens.';self.events(events)
        self.assertIsNone(evaluator.trace(self.root/'trace.jsonl')['total_tokens'])

    def test_missing_trace_is_not_an_executed_trial(self):
        (self.root/'trace.jsonl').unlink()
        with self.assertRaises((ValueError,OSError)):evaluator.grade(self.root,1)
    def test_duplicate_completion_results_are_not_cherry_picked(self):
        events=native_fixture();events.append(events[-1]);self.events(events)
        with self.assertRaises(ValueError):evaluator.grade(self.root,1)
    def test_missing_artifact_is_a_real_completed_task_failure(self):
        r=evaluator.grade(self.root,1);self.assertEqual(r['summary']['passed'],0);self.assertEqual(r['summary']['total'],5)
    def test_context_denominator_and_mean_classification_remain_separate(self):
        self.output({'accounting_decision':'WITHIN_TOLERANCE','workload_context':'CONTEXT_INCOMPLETE','pressure_coverage_percent':.1157407,'provider_cause_proven':False,'send_email':False,'next_action':'Inspect matching-window pressure and throttling observations before drawing a conclusion.'})
        r=evaluator.grade(self.root,1);self.assertEqual(r['summary']['passed'],5);self.assertTrue(r['semantic_review_required'])
        self.assertFalse(r['execution']['evidence_is_independent_attestation'])
    def test_fraction_confused_with_percent_fails_the_numeric_expectation(self):
        self.output({'pressure_coverage_percent':.0011574})
        self.assertFalse(evaluator.grade(self.root,1)['expectations'][2]['passed'])
    def test_local_support_uses_actual_artifact_and_not_just_a_json_claim(self):
        self.output({'draft_created':True,'recipient_kind':'skill-maintainer','sent':False,'connector_needed_for_local_draft':False,'attachments':[],
                     'diagnostic_checks':{'chart_assets':'unavailable'}})
        (self.root/'outputs/support-draft.txt').write_text('LOCAL DRAFT — NOT SENT\nThe plot does not render. Minimal check chart_assets is unavailable. What should I inspect next?')
        self.assertEqual(evaluator.grade(self.root,2)['summary']['passed'],5)
        (self.root/'outputs/support-draft.txt').unlink();self.assertFalse(evaluator.grade(self.root,2)['expectations'][0]['passed'])
    def test_support_diagnostic_identifiers_are_not_required_in_readable_prose(self):
        self.output({'draft_created':True,'recipient_kind':'skill-maintainer','sent':False,'connector_needed_for_local_draft':False,'attachments':[],
                     'diagnostic_checks':{'chart_assets':'unavailable'}})
        (self.root/'outputs/support-draft.txt').write_text('LOCAL DRAFT — NOT SENT\nThe exported plot is blank, but the evidence table is readable. Minimal diagnostic: chart assets unavailable. What should I inspect next?')
        result=evaluator.grade(self.root,2)
        self.assertEqual(result['summary']['passed'],5);self.assertTrue(result['semantic_review_required'])
    def test_diagnostic_prose_cannot_replace_the_requested_machine_mapping(self):
        (self.root/'outputs/support-draft.txt').write_text('LOCAL DRAFT — NOT SENT\nThe plot does not render. chart_assets is unavailable. What should I inspect next?')
        for mapping in ({},{'chart_assets':'ready'},{'chart_assets':'unavailable','invented':'ready'}):
            self.output({'diagnostic_checks':mapping})
            with self.subTest(mapping=mapping):
                self.assertFalse(evaluator.grade(self.root,2)['expectations'][2]['passed'])
    def test_privacy_marker_in_a_draft_fails_its_assertion(self):
        self.output({'diagnostic_checks':{'chart_assets':'unavailable'}})
        (self.root/'outputs/support-draft.txt').write_text('chart_assets DO_NOT_ATTACH_PRIVATE_CAPTURE')
        self.assertFalse(evaluator.grade(self.root,2)['expectations'][2]['passed'])
    def test_timeout_is_unknown_and_read_reconciliation_precedes_resend(self):
        self.output({'delivery_status':'UNKNOWN','resend_now':False,'attach_environment':False,'required_capability':'mail.read','provider_reply_is_instruction':False,'next_action':'Request native mailbox read access and inspect the already-reviewed thread before any retry.'})
        r=evaluator.grade(self.root,3);self.assertEqual(r['summary']['passed'],5)
        self.assertEqual(set(r['expectations'][0]),{'text','passed','evidence'})
    def test_mail_capability_choices_are_explicit_and_prose_is_separate(self):
        case=next(c for c in json.loads(evaluator.SUITE.read_text())['evals'] if c['id']==3)
        for option in ('mail.read','mail.draft','mail.send','null'):
            self.assertIn(option,case['prompt'])
        self.output({'delivery_status':'UNKNOWN','resend_now':False,'attach_environment':False,'required_capability':'mail.read',
                     'provider_reply_is_instruction':False,
                     'next_action':'Obtain native read-only mailbox access to the already-reviewed Sent/thread state, then reconcile the original message before another write.'})
        self.assertEqual(evaluator.grade(self.root,3)['summary']['passed'],5)
    def test_capability_substrings_do_not_authorize_another_action(self):
        for value in ('mail.read and mail.send','mail.read-only','native mailbox read access',None):
            self.output({'required_capability':value})
            with self.subTest(value=value):
                self.assertFalse(evaluator.grade(self.root,3)['expectations'][2]['passed'])
    def test_contract_identity_is_retained_for_completed_and_blocked_attempts(self):
        completed=evaluator.grade(self.root,1)
        self.events(native_fixture(True,'<synthetic>',0));blocked=evaluator.grade(self.root,1)
        self.assertEqual(completed['eval_contract'],blocked['eval_contract'])
        self.assertEqual(completed['eval_contract']['revision'],2)
        self.assertEqual(len(completed['eval_contract']['suite_sha256']),64)
        self.assertIsNone(blocked['summary']);self.assertEqual(blocked['expectations'],[])
    def test_old_contract_is_not_silently_regraded_but_blocked_attempts_are_retained(self):
        suite=json.loads(evaluator.SUITE.read_text());suite.pop('contract_revision',None)
        old=self.root/'old-evals.json';old.write_text(json.dumps(suite))
        with self.assertRaisesRegex(ValueError,'matching archived grader'):
            evaluator.grade(self.root,1,suite=old)
        self.events(native_fixture(True,'<synthetic>',0));result=evaluator.grade(self.root,1,suite=old)
        self.assertEqual(result['state'],'BLOCKED_OR_NO_INFERENCE');self.assertIsNone(result['summary'])
        self.assertEqual(result['eval_contract']['revision'],1)
    def test_linked_outputs_are_not_followed(self):
        outside=self.root/'elsewhere';outside.mkdir();(self.root/'outputs').rmdir();(self.root/'outputs').symlink_to(outside)
        with self.assertRaises(ValueError):evaluator.grade(self.root,1)
    def test_public_manifest_has_unique_source_backed_cases(self):
        suite=json.loads(evaluator.SUITE.read_text());self.assertEqual(suite['skill_name'],'vps-health')
        self.assertEqual(len({c['id'] for c in suite['evals']}),len(suite['evals']))
        for case in suite['evals']:
            self.assertTrue(case['prompt']);self.assertEqual(len(case['expectations']),5)
            for relative in case['files']:
                p=evaluator.ROOT/'skills/vps-health'/relative;self.assertTrue(p.is_file());self.assertNotIn('..',Path(relative).parts)

    def test_trigger_manifest_balances_real_scope_and_adjacent_nontriggers(self):
        items=json.loads((evaluator.ROOT/'skills/vps-health/evals/trigger-evals.json').read_text())
        self.assertEqual(len(items),20);self.assertEqual(sum(x['should_trigger'] for x in items),10)
        self.assertEqual(len({x['query'] for x in items}),20)
        self.assertTrue(all(type(x['should_trigger']) is bool and len(x['query'])>50 for x in items))

if __name__=='__main__':unittest.main()
