#!/usr/bin/env python3
"""Media contracts, not a certificate for native clients or hosting quality."""
from pathlib import Path
import copy
import json
import unittest
import tempfile
import struct
import launch_media as film

class LaunchContractTest(unittest.TestCase):
    def test_short_story_has_fixed_reviewed_duration(self):
        self.assertEqual(film.validate_story(),53)
        self.assertLess(film.validate_story(),140)

    def test_every_instant_maps_to_one_scene_in_order(self):
        last=-1
        for tick in range(53*24):
            index,scene,fraction=film.scene_at(tick/24)
            self.assertGreaterEqual(index,last);self.assertGreaterEqual(fraction,0);self.assertLess(fraction,1)
            last=index
        self.assertEqual(last,len(film.SCENES)-1)

    def test_negative_and_end_seek_are_bounded(self):
        self.assertEqual(film.scene_at(-1)[1]['id'],'hook')
        self.assertEqual(film.scene_at(1000)[1]['id'],'end')

    def test_duplicate_or_excessive_story_refuses(self):
        with self.assertRaises(ValueError):film.validate_story(film.SCENES*2)
        bad=copy.deepcopy(film.SCENES);bad[0]['duration']=40
        with self.assertRaises(ValueError):film.validate_story(bad)

    def test_captions_span_the_whole_film_and_name_the_preview(self):
        text=film.srt()
        self.assertIn('00:00:00,000 --> 00:00:04,000',text)
        self.assertIn('00:00:42,000 --> 00:00:53,000',text)
        self.assertIn('technical preview',text)
        self.assertIn('You approve',text)

    def test_no_provider_guilt_or_fake_native_trace_in_story(self):
        text=json.dumps(film.SCENES).lower()
        for claim in ('fake migration detected','guaranteed','production-ready','proven provider fault','zero approval'):
            self.assertNotIn(claim,text)

    def test_streaming_metadata_must_precede_media_payload(self):
        def box(name):return struct.pack('>I4s',8,name)
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'synthetic.mp4'
            p.write_bytes(box(b'ftyp')+box(b'moov')+box(b'mdat'));self.assertTrue(film.front_loaded_metadata(p))
            p.write_bytes(box(b'ftyp')+box(b'mdat')+box(b'moov'));self.assertFalse(film.front_loaded_metadata(p))
            p.write_bytes(b'broken');self.assertFalse(film.front_loaded_metadata(p))

    def test_formats_use_even_social_dimensions(self):
        self.assertEqual(film.FORMATS['landscape'],(1920,1080))
        self.assertEqual(film.FORMATS['portrait'],(1080,1350))
        self.assertTrue(all(v%2==0 for size in film.FORMATS.values() for v in size))

    def test_capture_is_fixed_demo_not_a_private_workspace_export(self):
        import inspect
        source=inspect.getsource(film.capture_product)
        self.assertIn("mode='demo'",source)
        self.assertIn('TemporaryDirectory',source)
        self.assertIn("value['synthetic']",source)
        self.assertIn('server.shutdown()',source)
        self.assertNotIn('collect_local(',source)

if __name__=='__main__':unittest.main()
