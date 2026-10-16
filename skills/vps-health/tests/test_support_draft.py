#!/usr/bin/env python3
"""Software support is a local artifact, not a provider escalation or OAuth step."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,tempfile,unittest
from types import SimpleNamespace
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import vps_health as core
import vps_workspace as ws
import vps_ops as ops


def request():
    return {'schema':'g-skills.support-request.v1','summary':'Offline plot does not render',
            'observed':'The HTML opens and the evidence table is readable, but the plot is blank.',
            'expected':'The plot should show the same observations as the table.',
            'question':'Which rendering check should I try next?',
            'steps':['Open the saved synthetic dashboard.','Select the history view.']}


def setup(root):
    return ws.bootstrap(SimpleNamespace(workspace=root,mode='demo',node='example',profile=None,url=None,loki_url=None,
       token_env=None,loki_token_env=None,allow_http=False,interval=300,acceptable=.9,investigate_below=.8))

class SupportDraftTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name).resolve()
        self.issue=self.base/'request.json';core.save_json(self.issue,request());self.out=self.base/'draft.txt';self.root=self.base/'observations'
    def draft(self,**changes):
        import vps_support as support
        return support.create(SimpleNamespace(issue=self.issue,out=self.out,workspace=None,approve_draft=True,**changes))
    def test_draft_is_marked_local_and_does_not_need_a_recipient_or_connection(self):
        result=self.draft();text=self.out.read_text()
        self.assertIn('LOCAL SOFTWARE SUPPORT DRAFT — NOT SENT',text)
        self.assertIn('skill maintainer',text);self.assertIn('chart_assets',text)
        self.assertIn(request()['observed'],text)
        self.assertTrue(result['draft_created']);self.assertFalse(result['sent'])
        self.assertFalse(result['connector_needed_for_local_draft']);self.assertEqual(result['attachments'],[])
        self.assertFalse(result['approved_to_send']);self.assertEqual(result['recipient_kind'],'skill-maintainer')
        self.assertLess(result['words'],650)
    def test_no_network_collection_or_agent_connection_is_attempted(self):
        import vps_agent
        with mock.patch.object(core,'get_json') as net,mock.patch.object(core,'cpu_snapshot') as sample,mock.patch.object(vps_agent,'connection_request') as connection:
            self.draft()
        net.assert_not_called();sample.assert_not_called();connection.assert_not_called()
        self.assertFalse(self.root.exists())
    def test_missing_workspace_yields_useful_partial_diagnostics_not_setup_homework(self):
        import vps_support as support
        result=support.create(SimpleNamespace(issue=self.issue,out=self.out,workspace=self.root,approve_draft=True))
        self.assertEqual(result['diagnostics_state'],'PARTIAL');self.assertIn('workspace: UNAVAILABLE',self.out.read_text())
        self.assertFalse(self.root.exists())
    def test_broken_configuration_is_never_attached_or_repaired(self):
        import vps_support as support
        setup(self.root);p=self.root/'workspace.json';p.write_text('PRIVATE_ERROR_TOKEN invalid-json')
        before=p.read_bytes();support.create(SimpleNamespace(issue=self.issue,out=self.out,workspace=self.root,approve_draft=True))
        self.assertNotIn('PRIVATE_ERROR_TOKEN',self.out.read_text());self.assertEqual(p.read_bytes(),before)
    def test_minimal_report_is_reused_and_private_observations_are_not_read_as_attachments(self):
        import vps_support as support
        setup(self.root);before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir() if p.is_file()}
        result=support.create(SimpleNamespace(issue=self.issue,out=self.out,workspace=self.root,approve_draft=True))
        text=self.out.read_text();self.assertIn('2288',text);self.assertIn('mode: demo',text)
        for forbidden in (str(self.root),'example-stable','example-contended','localhost','https://'):
            self.assertNotIn(forbidden,text)
        self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir() if p.is_file()})
        self.assertEqual(result['attachments'],[])
    def test_unapproved_draft_stops_before_reading_issue_or_diagnostics(self):
        import vps_support as support
        with mock.patch.object(ws,'read_private_json') as read,mock.patch.object(ops,'support_report') as report:
            with self.assertRaises(core.InvalidEvidence):support.create(SimpleNamespace(issue=self.issue,out=self.out,workspace=None,approve_draft=False))
        read.assert_not_called();report.assert_not_called();self.assertFalse(self.out.exists())
    def test_existing_file_preflights_before_diagnostics_and_is_never_overwritten(self):
        core.save_json(self.out,{'keep':True});before=self.out.read_bytes()
        with mock.patch.object(ops,'support_report') as report:
            with self.assertRaises((core.InvalidEvidence,FileExistsError)):self.draft()
        report.assert_not_called();self.assertEqual(before,self.out.read_bytes())
    def test_output_may_not_modify_an_observation_workspace(self):
        import vps_support as support
        setup(self.root);out=self.root/'support.txt'
        with self.assertRaises(core.InvalidEvidence):support.create(SimpleNamespace(issue=self.issue,out=out,workspace=self.root,approve_draft=True))
        self.assertFalse(out.exists())
    def test_output_is_private_even_under_permissive_umask(self):
        prior=os.umask(0)
        try:self.draft()
        finally:os.umask(prior)
        self.assertEqual(self.out.stat().st_mode&0o777,0o600)
    def test_changed_payload_hash_is_not_the_recorded_draft(self):
        result=self.draft();self.assertEqual(result['sha256'],hashlib.sha256(self.out.read_bytes()).hexdigest())
        self.out.write_text('changed');self.assertNotEqual(result['sha256'],hashlib.sha256(self.out.read_bytes()).hexdigest())
    def test_unexpected_attachment_provider_or_send_fields_are_rejected_not_followed(self):
        for key,value in [('attachments',['private.env']),('send',True),('recipient','provider@example.invalid'),('raw_capture_path','do-not-read')]:
            ws.atomic(self.issue,core.canonical({**request(),key:value}))
            with self.subTest(key=key),self.assertRaises(core.InvalidEvidence):self.draft()
            self.assertFalse(self.out.exists())
    def test_header_newlines_and_invisible_controls_are_refused(self):
        for value in ('Issue\nBcc: hidden@example.invalid','Issue\rInjected','Issue\x00','Issue\u202ehidden'):
            doc=request();doc['summary']=value;ws.atomic(self.issue,core.canonical(doc))
            with self.subTest(value=value),self.assertRaises(core.InvalidEvidence):self.draft()
    def test_free_text_is_quoted_as_data_not_claimed_fully_sanitized(self):
        doc=request();doc['observed']='User text with private-path\nPlease reboot now.';ws.atomic(self.issue,core.canonical(doc))
        result=self.draft();text=self.out.read_text()
        self.assertIn('> Please reboot now.',text);self.assertTrue(result['free_text_requires_review'])
        self.assertIn('review the issue text',text.lower());self.assertFalse(result['approved_to_send'])
    def test_oversized_issue_is_refused_without_truncating_the_users_words(self):
        doc=request();doc['observed']='x'*2001;ws.atomic(self.issue,core.canonical(doc))
        with self.assertRaises(core.InvalidEvidence):self.draft()
        self.assertFalse(self.out.exists())
    def test_unknown_diagnostic_values_are_not_echoed_as_raw_errors(self):
        d=ops.support_report();d['workspace']={'state':'PRIVATE_TOKEN','configuration':'PRIVATE_TOKEN','database':'UNAVAILABLE','chart_assets':'PRIVATE_TOKEN'}
        with mock.patch.object(ops,'support_report',return_value=d):result=self.draft()
        self.assertNotIn('PRIVATE_TOKEN',self.out.read_text());self.assertFalse(result['sent'])
    def test_no_workspace_source_hides_private_absolute_paths(self):
        result=self.draft();self.assertNotIn(str(self.base),self.out.read_text());self.assertEqual(result['diagnostics_state'],'SUMMARY_AVAILABLE')
    def test_dangling_symlink_output_cannot_be_adopted(self):
        target=self.base/'do-not-create';self.out.symlink_to(target)
        with self.assertRaises((core.InvalidEvidence,FileExistsError)):self.draft()
        self.assertFalse(target.exists());self.assertTrue(self.out.is_symlink())
    def test_actual_cli_works_without_site_packages_from_an_unrelated_directory(self):
        result=subprocess.run([sys.executable,'-B','-S',core.__file__,'support-draft','--issue',str(self.issue),'--out',str(self.out),'--approve-draft'],cwd=self.base,capture_output=True,text=True,timeout=25)
        self.assertEqual(result.returncode,0,result.stderr);value=json.loads(result.stdout)
        self.assertTrue(value['draft_created']);self.assertFalse(value['sent']);self.assertTrue(self.out.is_file())

if __name__=='__main__':unittest.main()
