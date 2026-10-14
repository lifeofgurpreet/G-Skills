#!/usr/bin/env python3
"""Native graph state and scoped calendar displays remain one authority."""
from pathlib import Path
import datetime as dt
import json
import tempfile
import unittest
from unittest import mock
import roadmap


def item(key,scope='scope:collection',**extra):
    return {'id':key,'title':'Example task','description':'A concrete scope','acceptance_criteria':'Observable completion',
            'status':'open','issue_type':'task','priority':1,'labels':[scope],**extra}

class RoadmapTest(unittest.TestCase):
    def fixture(self,rows):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        (root/'.beads').mkdir();(root/'.beads/issues.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
        return root

    def test_owner_target_and_state_come_from_native_record(self):
        row=item('gs-one',assignee='verification-role',due_at='2026-11-07T12:00:00Z',status='in_progress')
        text='\n'.join(roadmap.table([row]))
        self.assertIn('verification-role',text);self.assertIn('2026-11-07',text);self.assertIn('in_progress',text)

    def test_legacy_unassigned_record_does_not_invent_owner_or_schedule(self):
        text='\n'.join(roadmap.table([item('gs-one')]))
        self.assertIn('Unassigned',text);self.assertIn('—',text)

    def test_root_and_skill_task_details_are_not_mixed(self):
        rows=[item('gs-shared',title='Collection-only acceptance'),item('gs-vps','skill:vps-health',title='VPS-only acceptance')]
        root=self.fixture(rows)
        with mock.patch.object(roadmap.collection,'discover',return_value=[{'name':'vps-health','title':'VPS Health','version':'0.7.1'}]):
            output=roadmap.render(root)
        self.assertNotIn('VPS-only acceptance',output[root/'ROADMAP.md'])
        self.assertNotIn('Collection-only acceptance',output[root/'docs/skills/vps-health/ROADMAP.md'])

    def test_cross_scope_parent_cannot_redefine_the_collection(self):
        rows=[item('gs-parent'),item('gs-child','skill:vps-health',dependencies=[{'type':'parent-child','depends_on_id':'gs-parent'}])]
        root=self.fixture(rows)
        with mock.patch.object(roadmap.collection,'discover',return_value=[{'name':'vps-health'}]):
            with self.assertRaises(ValueError):roadmap.load(root)

    def test_closed_dependent_cannot_hide_an_open_blocker(self):
        rows=[item('gs-before'),item('gs-after',status='closed',close_reason='Source only',dependencies=[{'type':'blocks','depends_on_id':'gs-before'}])]
        root=self.fixture(rows)
        with mock.patch.object(roadmap.collection,'discover',return_value=[]):
            with self.assertRaises(ValueError):roadmap.load(root)

    def test_current_quarter_open_work_has_an_owner_and_target(self):
        rows=roadmap.load()
        for row in rows:
            if row['issue_type']=='epic' or row['status'] in ('closed','deferred'):continue
            with self.subTest(task=row['id']):
                self.assertTrue(row.get('assignee'))
                due=dt.date.fromisoformat(row['due_at'][:10])
                self.assertLessEqual(dt.date(2026,10,14),due);self.assertLessEqual(due,dt.date(2027,1,14))
                self.assertEqual(len([x for x in row['labels'] if x.startswith('phase:')]),1)

if __name__=='__main__':unittest.main()
