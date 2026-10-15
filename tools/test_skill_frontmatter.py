#!/usr/bin/env python3
from pathlib import Path
import json
import tempfile
import unittest
import skill_frontmatter as header


def document(description='A useful independent workflow.',**fields):
    lines=['---','name: example-skill','description: '+description]
    lines += [key+': '+value for key,value in fields.items()]
    return '\n'.join(lines+['---','','# Example',''])


class FrontmatterTest(unittest.TestCase):
    def test_actual_unquoted_colon_failure_is_rejected(self):
        with self.assertRaises(ValueError):header.parse(document('Take ownership of a VPS investigation: discover targets.'))

    def test_folded_description_preserves_punctuation_and_meaning(self):
        text=document('>\n  Take ownership of a VPS investigation: discover targets.\n  Keep evidence private.')
        self.assertEqual(header.parse(text)['description'].strip(),'Take ownership of a VPS investigation: discover targets. Keep evidence private.')

    def test_duplicate_keys_cannot_hide_the_discovery_name(self):
        with self.assertRaises(ValueError):header.parse(document() .replace('---\n\n#','name: other\n---\n\n#'))

    def test_nonempty_string_name_and_description_are_required(self):
        for value in ('null','[]','true','123','""'):
            with self.subTest(value=value),self.assertRaises(ValueError):header.parse(document(value))

    def test_unknown_top_level_permissions_do_not_silently_enter_metadata(self):
        with self.assertRaises(ValueError):header.parse(document(approve_everything='true'))

    def test_nonportable_aliases_and_tags_are_not_expanded(self):
        for value in ('&description example','!!python/object/apply:os.system [echo]','*missing'):
            with self.subTest(value=value),self.assertRaises(ValueError):header.parse(document(value))

    def test_crlf_and_unicode_remain_supported(self):
        self.assertEqual(header.parse(document('Diagnose; don’t guess.').replace('\n','\r\n'))['description'],'Diagnose; don’t guess.')

    def test_discovery_name_matches_the_independent_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'skills/example-skill';folder.mkdir(parents=True)
            (folder/'SKILL.md').write_text(document(metadata='\n  version: "1.2.3"'))
            (folder/'skill.json').write_text(json.dumps({'name':'different','version':'1.2.3'}))
            with self.assertRaises(ValueError):header.validate_tree(temp)

    def test_version_drift_is_a_real_discovery_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'skills/example-skill';folder.mkdir(parents=True)
            (folder/'SKILL.md').write_text(document(metadata='\n  version: "1.2.3"'))
            (folder/'skill.json').write_text(json.dumps({'name':'example-skill','version':'1.2.4'}))
            with self.assertRaises(ValueError):header.validate_tree(temp)

    def test_actual_collection_frontmatter_parses(self):
        names=header.validate_tree(Path(__file__).resolve().parents[1])
        self.assertIn('vps-health',names);self.assertIn('reset-boost',names)

if __name__=='__main__':unittest.main()
