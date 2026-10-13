#!/usr/bin/env python3
"""Guest evidence is useful without being unique physical-host attestation."""
from pathlib import Path
import copy
import json
import os
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import vps_forensics as f
import vps_health as core


def fixture(at=1_000_000_000,wall=1_790_000_000_000_000_000):
    sources={p:{'state':'unavailable','text':None} for p in f.COUNTERS}
    def add(path,text):sources[path]={'state':'observed','text':text}
    add('/proc/diskstats','259 0 nvme0n1 100 0 1000 500 200 0 2000 1000 0 50 150\n253 0 dm-0 10 0 100 20 20 0 200 40 0 5 10')
    add('/proc/net/softnet_stat','0000000a 0000000f 00000010 0 0 0 0 0 0 0 0 0 00000000')
    add('/proc/net/dev','eth0: 100 10 0 2 0 0 0 0 200 20 0 1 0 0 0 0')
    for resource in ('cpu','memory','io'):add('/proc/pressure/'+resource,'some avg10=99.99 avg60=0.00 avg300=0.00 total=100000\nfull avg10=99.99 avg60=0.00 avg300=0.00 total=50000')
    add('/proc/vmstat','pgmajfault 10\npswpin 5\npswpout 3\nballoon_inflate 30')
    add('/proc/meminfo','MemTotal: 1000000 kB\nMemAvailable: 500000 kB\nSwapTotal: 10000 kB\nSwapFree: 9000 kB')
    return {'schema':f.SCHEMA,'subject':'example-node','tool_sha256':'same-source','wall_ns':wall,'start_ns':at,'end_ns':at+1_000_000,
            'boot_fingerprint':'same-boot','sources':sources,'environment':{'cpu':{'models':['Example virtual CPU']},'clocksource':'kvm-clock','dmi_vendor':'Example','dmi_product':'VM'},
            'root_mount':{'state':'observed','device_id':'253:0','filesystem':'ext4'},'physical_host_verified':False}


def pair():
    a=fixture();b=fixture(11_000_000_000,1_790_000_010_000_000_000)
    return a,b

class ParserTest(unittest.TestCase):
    def test_cpu_parser_keeps_each_field_not_first_grep_match(self):
        d=f.cpu_identity('processor : 0\nvendor_id : Example\nmodel name : Example CPU\nstepping : 3\nmicrocode : 0x42\nflags : aes avx2\n')
        self.assertEqual(d['guest_fields']['model name'],'Example CPU');self.assertEqual(d['guest_fields']['microcode'],'0x42')
        self.assertFalse(d['physical_cpu_verified']);self.assertIsNone(d['performance_baseline'])

    def test_root_device_is_mapped_by_major_minor_not_trailing_digits(self):
        d=f.root_mount('25 1 259:0 / / rw - ext4 /dev/nvme0n1 rw')
        self.assertEqual(d['device_id'],'259:0')
        d=f.root_mount('25 1 253:0 / / rw - ext4 /dev/mapper/vg-root rw')
        self.assertEqual(d['device_id'],'253:0')
        d=f.root_mount('25 1 0:22 / / rw - overlay overlay rw')
        self.assertEqual(d['filesystem'],'overlay');self.assertEqual(d['device_id'],'0:22')

    def test_softnet_fields_are_hexadecimal(self):
        d=f.parse_softnet('0000000a 0000000f 00000010 0 0 0 0 0 0 0 0 0 00000002')
        self.assertEqual(d['2'],{'processed':10,'dropped':15,'time_squeeze':16})

    def test_malformed_duplicate_negative_counters_fail(self):
        for parser,text in [(f.parse_softnet,'abc nope 0'),(f.parse_diskstats,'1 0 x -1 0 0 0 0 0 0 0 0 0 0'),(f.parse_psi,'some total=1\nsome total=2')]:
            with self.subTest(text=text),self.assertRaises(ValueError):parser(text)

    def test_permission_failure_is_not_zero(self):
        with mock.patch('builtins.open',side_effect=PermissionError):d=f.read_source('/proc/pressure/io')
        self.assertEqual(d,{'state':'permission_denied','text':None})

    def test_snapshot_is_only_bounded_file_reads(self):
        paths=[]
        def read(path):paths.append(path);return {'state':'unavailable','text':None}
        with mock.patch.object(f.sys,'platform','linux'),mock.patch.object(f.time,'sleep') as sleep:
            d=f.snapshot('example',reader=read)
        self.assertLess(len(paths),24);self.assertFalse(d['network_probes_run']);self.assertFalse(d['active_benchmarks_run']);sleep.assert_not_called()
        self.assertFalse(any('secret' in p or '/dev/shm' in p for p in paths))

    def test_no_external_commands_in_collector(self):
        source=Path(f.__file__).read_text();self.assertNotIn('subprocess.',source);self.assertNotIn('os.system(',source)

class CounterTest(unittest.TestCase):
    def test_disk_await_uses_read_write_ticks_not_busy_ticks(self):
        a,b=pair();b['sources']['/proc/diskstats']['text']='259 0 nvme0n1 102 0 1010 520 201 0 2008 1030 0 55 155\n253 0 dm-0 10 0 100 20 20 0 200 40 0 5 10'
        d=next(x for x in f.interval(a,b)['storage'] if x['device_id']=='259:0')
        self.assertEqual(d['read_await_ms'],10);self.assertEqual(d['write_await_ms'],30);self.assertAlmostEqual(d['iops'],.3)
        self.assertNotIn('p95',d);self.assertNotIn('physical_medium',d)

    def test_zero_completed_io_is_unknown_latency(self):
        a,b=pair();d=f.interval(a,b)['storage'][0]
        self.assertIsNone(d['read_await_ms']);self.assertIsNone(d['write_await_ms']);self.assertEqual(d['iops'],0)

    def test_reset_does_not_become_fast_or_negative_io(self):
        a,b=pair();b['sources']['/proc/diskstats']['text']=b['sources']['/proc/diskstats']['text'].replace('100 0 1000','1 0 1000')
        d=next(x for x in f.interval(a,b)['storage'] if x['device_id']=='259:0')
        self.assertEqual(d['state'],'counter_reset');self.assertIsNone(d['iops'])

    def test_disk_layers_are_not_summed_into_fake_guest_totals(self):
        a,b=pair();d=f.interval(a,b)
        self.assertEqual(len(d['storage']),2);self.assertNotIn('total_iops',d)
        self.assertEqual(d['root_mount']['device_id'],'253:0')

    def test_pressure_uses_total_delta_not_an_unrelated_avg10_window(self):
        a,b=pair();b['sources']['/proc/pressure/io']['text']='some avg10=0 total=2100000\nfull avg10=0 total=1050000'
        d=f.interval(a,b)['pressure']['io'];self.assertEqual(d['some'],.2);self.assertEqual(d['full'],.1)
        self.assertFalse(f.interval(a,b)['provider_cause_proven'])

    def test_system_cpu_full_does_not_claim_useful_pressure(self):
        a,b=pair();self.assertIsNone(f.interval(a,b)['pressure']['cpu']['full'])

    def test_unsupported_pressure_stays_missing(self):
        a,b=pair();b['sources']['/proc/pressure/io']={'state':'permission_denied','text':None}
        d=f.interval(a,b)['pressure']['io'];self.assertIsNone(d['some']);self.assertNotEqual(d['state'],'observed')

    def test_softnet_increase_is_guest_budget_context_not_vcpu_preemptions(self):
        a,b=pair();b['sources']['/proc/net/softnet_stat']['text']='0000000c 00000010 00000012 0 0 0 0 0 0 0 0 0 00000000'
        d=f.interval(a,b)['network']['softnet']['rows'][0]['delta'];self.assertEqual(d['time_squeeze'],2)
        self.assertNotIn('preemptions',d)

    def test_network_interface_changes_are_visible(self):
        a,b=pair();b['sources']['/proc/net/dev']['text']=b['sources']['/proc/net/dev']['text'].replace('eth0','eth1')
        d=f.interval(a,b)['network']['interfaces']['rows'];self.assertEqual(len(d),2)
        self.assertTrue(all(x['delta'] is None for x in d))

    def test_vmstat_reports_delta_not_lifetime_balloon_activity(self):
        a,b=pair();d=f.interval(a,b)['memory'];self.assertEqual(d['counter_deltas']['balloon_inflate'],0);self.assertFalse(d['host_swap_verified'])

    def test_boot_and_clock_bounds_invalidate_rates(self):
        a,b=pair()
        for change in ({'boot_fingerprint':'new'},{'wall_ns':b['wall_ns']+9_000_000_000},{'start_ns':a['start_ns'],'end_ns':a['end_ns']}):
            d=f.interval(a,{**b,**change});self.assertTrue(d['quality']);self.assertEqual(d['storage'],[])

    def test_different_nodes_refuse_comparison(self):
        a,b=pair();b['subject']='other-node'
        with self.assertRaises(core.InvalidEvidence):f.compare(a,b)

class MigrationTest(unittest.TestCase):
    def test_identical_traits_do_not_prove_fake_migration(self):
        a,b=pair();b['boot_fingerprint']='new-boot';d=f.compare(a,b)
        self.assertEqual(d['guest_traits'],'NO_VISIBLE_CHANGE');self.assertFalse(d['physical_host_verified'])
        self.assertEqual(d['migration_verdict'],'NOT_ESTABLISHED_FROM_GUEST_EVIDENCE')

    def test_changed_cpu_is_not_physical_host_attestation(self):
        a,b=pair();b['environment']['cpu']={'models':['Different virtual model']};d=f.compare(a,b)
        self.assertEqual(d['guest_traits'],'CHANGED');self.assertIn('cpu',d['changed_fields']);self.assertFalse(d['physical_host_verified'])

    def test_missing_traits_do_not_become_verified_identity(self):
        a,b=pair();b['environment']['cpu']=None;self.assertEqual(f.compare(a,b)['guest_traits'],'INCOMPLETE')

    def test_counter_context_and_json_roundtrip_are_deterministic(self):
        a,b=pair();d=f.compare(a,b);self.assertEqual(d,f.compare(json.loads(core.canonical(a)),json.loads(core.canonical(b))))

    def test_input_does_not_mutate(self):
        a,b=pair();before=copy.deepcopy((a,b));f.compare(a,b);self.assertEqual((a,b),before)

    def test_private_outputs_do_not_overwrite_or_relax_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'snapshot.json';f.save_private(path,fixture())
            if os.name=='posix':self.assertEqual(path.stat().st_mode&0o777,0o600)
            with self.assertRaises(FileExistsError):f.save_private(path,fixture())

if __name__=='__main__':unittest.main()
