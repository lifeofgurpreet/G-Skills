#!/usr/bin/env python3
"""Context-chart properties derived from observations, not from the renderer."""
from pathlib import Path
import copy
import random
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import vps_workspace as w

FIELDS={'value':'cpu_accounted_ratio','execution':'executing_ratio','pressure':'cpu_pressure_ratio','cfs':'cfs_throttled_periods_ratio'}

def points(count=4000,seed=21):
    rng=random.Random(seed)
    return [dict(timestamp=1800000000+i*300,duration_seconds=300,quality=[],conflict=False,
                 cpu_accounted_ratio=.95,executing_ratio=.2+rng.random()*.02,
                 cpu_pressure_ratio=.01,cfs_throttled_periods_ratio=0.) for i in range(count)]


class ContextChartTest(unittest.TestCase):
    def test_all_metric_extrema_survive_independent_of_accounting(self):
        for seed in range(12):
            data=points(seed=seed)
            rng=random.Random(seed)
            for key in list(FIELDS.values())[1:]:
                index=rng.randrange(100,len(data)-100);data[index][key]=.999
                result=w.chart_history(data,300)
                field=next(k for k,v in FIELDS.items() if v==key)
                self.assertIn(.999,[p.get(field) for p in result],(field,seed))
                self.assertLessEqual(len(result),600)

    def test_missing_context_is_not_zero_or_an_accounting_gap(self):
        data=points(60);data[20]['executing_ratio']=None
        result=w.chart_history(data,300)
        missing=next(p for p in result if p['t']==data[20]['timestamp'])
        after=next(p for p in result if p['t']==data[21]['timestamp'])
        self.assertIsNone(missing['execution']);self.assertEqual(missing['value'],.95)
        self.assertTrue(after['breaks']['execution']);self.assertFalse(after['breaks']['value'])

    def test_unseen_context_hole_still_breaks_next_display_segment(self):
        data=points();data[37]['cpu_pressure_ratio']=None
        result=w.chart_history(data,300)
        after=next(p for p in result if p['t']>data[37]['timestamp'])
        self.assertTrue(after['breaks']['pressure'])

    def test_invalid_interval_invalidates_all_series(self):
        data=points(80);data[21]['quality']=['clock_step']
        row=next(p for p in w.chart_history(data,300) if p['t']==data[21]['timestamp'])
        self.assertTrue(row['quality'])
        for field in FIELDS:self.assertIsNone(row[field])

    def test_translation_changes_times_not_values_or_breaks(self):
        data=points();data[32]['quality']=['counter_reset'];del data[300:304]
        before=w.chart_history(data,300)
        moved=copy.deepcopy(data)
        for p in moved:p['timestamp']+=86400*50
        after=w.chart_history(moved,300)
        self.assertEqual([{**p,'t':p['t']+86400*50} for p in before],after)

    def test_raw_input_and_weighted_policy_do_not_change(self):
        data=points();snapshot=copy.deepcopy(data)
        first=w.weighted(data,data[0]['timestamp']-300,data[-1]['timestamp'])
        w.chart_history(data,300)
        self.assertEqual(data,snapshot)
        self.assertEqual(w.weighted(data,data[0]['timestamp']-300,data[-1]['timestamp']),first)

    def test_real_time_gap_breaks_all_fields(self):
        data=points(60);del data[15]
        row=next(p for p in w.chart_history(data,300) if p['t']==1800000000+16*300)
        self.assertTrue(all(row['breaks'][field] for field in FIELDS))

    def test_missing_entire_context_stays_unknown(self):
        data=points(50)
        for p in data:
            for key in list(FIELDS.values())[1:]:p.pop(key)
        result=w.chart_history(data,300)
        self.assertTrue(all(p['execution'] is None and p['pressure'] is None and p['cfs'] is None for p in result))
        self.assertTrue(all(p['value']==.95 for p in result))

    def test_bad_timestamps_and_nonmonotonic_data_are_rejected(self):
        for transform in (lambda d:d.reverse(),lambda d:d.__setitem__(2,copy.deepcopy(d[1]))):
            data=points(10);transform(data)
            with self.assertRaises(ValueError):w.chart_history(data,300)

    def test_small_point_limits_stay_bounded(self):
        for limit in (10,14,30,100,600):
            result=w.chart_history(points(),300,limit)
            self.assertLessEqual(len(result),limit)


if __name__=='__main__':unittest.main()
