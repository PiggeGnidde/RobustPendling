from datetime import datetime
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from t90_core import statistics,minute_grid,metadata,combinations,component_statistics,PARAMETERS
from schedule_sweep import ScheduleSweep


def trip(identifier, stops, route='139'):
    return dict(id=identifier,route_id=route,line=route,mode='700',
                stops=[dict(id=s,arrival=t,departure=t,seq=i,pickup='0',dropoff='0')
                       for i,(s,t) in enumerate(stops)])


class StatisticsTests(unittest.TestCase):
    def test_nearest_rank(self):
        result=statistics(list(range(1,61)))
        self.assertEqual(result['percentiles_seconds'],dict(T50=30,T90=54,T99=60))
        self.assertEqual(result['mean_seconds'],30.5)

    def test_unreachable_never_dropped(self):
        result=statistics(list(range(54))+[None]*6)
        self.assertEqual(result['percentiles_seconds']['T90'],53)
        self.assertEqual(result['percentiles_seconds']['T99'],'UNREACHABLE')
        self.assertEqual(result['route_coverage'],.9)
        self.assertEqual(result['unreachable_count'],6)
        self.assertEqual(result['maximum_seconds'],'UNREACHABLE')
        self.assertEqual(result['mean_seconds'],'UNREACHABLE')
        self.assertEqual(statistics(list(range(53))+[None]*7)['percentiles_seconds']['T90'],'UNREACHABLE')

    def test_all_unreachable_and_bad_values(self):
        self.assertEqual(statistics([None]*60)['percentiles_seconds']['T50'],'UNREACHABLE')
        for values in ([],[-1],[float('nan')],[float('inf')]):
            with self.assertRaises(ValueError): statistics(values)

    def test_timezone_and_inclusive_end(self):
        grid=minute_grid('2026-10-12')
        self.assertEqual(len(grid),60)
        self.assertEqual(grid[0].isoformat(),'2026-10-12T07:00:00+02:00')
        self.assertEqual(grid[-1].isoformat(),'2026-10-12T07:59:00+02:00')
        self.assertEqual(len(minute_grid('2026-10-12',end='08:00:00')),61)
        self.assertEqual(len(minute_grid('2026-12-12')),60)
        self.assertEqual(minute_grid('2026-12-12')[0].utcoffset().total_seconds(),3600)
        self.assertEqual(minute_grid('2026-10-12',timezone='UTC')[0].utcoffset().total_seconds(),0)
        for kwargs in (dict(start='07:00:01'),dict(end='06:59:59')):
            with self.assertRaises(ValueError):minute_grid('2026-10-12',**kwargs)
        with self.assertRaises(ValueError):minute_grid('2026-10-25',start='02:00:00',end='02:59:59')
        with self.assertRaises(ValueError):minute_grid('2026-03-29',start='02:00:00',end='02:59:59')

    def test_reproducible_metadata(self):
        grid=minute_grid('2026-10-12')
        a=metadata(dict(b='b',a='a'),dict(r5='x'),grid)
        b=metadata(dict(a='a',b='b'),dict(r5='x'),grid)
        self.assertEqual(a,b)
        self.assertNotEqual(a['experiment_sha256'],metadata(dict(a='changed',b='b'),dict(r5='x'),grid)['experiment_sha256'])
        self.assertNotEqual(a['experiment_sha256'],metadata(dict(a='a',b='b'),dict(r5='x'),grid,dict(PARAMETERS,max_rides=1))['experiment_sha256'])


class SweepTests(unittest.TestCase):
    def test_driver_request_stops_allowed_agency_prebooking_rejected(self):
        t=trip('a',[('o',100),('d',200)])
        t['stops'][0]['pickup']='3'
        t['stops'][1]['dropoff']='3'
        model=ScheduleSweep([t],{'o':10},{'d':20},lambda s:{s:0})
        self.assertEqual(model.at(0)['duration_seconds'],280)
        t['stops'][0]['pickup']='2'
        self.assertIsNone(ScheduleSweep([t],{'o':10},{'d':20},lambda s:{s:0}).at(0)['duration_seconds'])

    def test_later_faster_trip_wins_and_waiting_included(self):
        model=ScheduleSweep([trip('slow',[('a',100),('b',1000)]),trip('fast',[('a',200),('b',400)])],
                            {'a':10},{'b':20},lambda s:{s:0})
        result=model.at(0)
        self.assertEqual(result['duration_seconds'],480)
        self.assertEqual(result['walking_seconds'],30)
        self.assertEqual(result['waiting_seconds'],190)
        self.assertEqual(result['rides'][0]['trip_id'],'fast')
        self.assertIsNone(model.at(300)['duration_seconds'])

    def test_two_rides_transfer_budget_and_strict_boarding(self):
        trips=[trip('a',[('o',100),('x',200)]),trip('b',[('y',400),('d',500)],'130')]
        model=ScheduleSweep(trips,{'o':20},{'d':30},lambda s:{'y':50} if s=='x' else {s:0})
        result=model.at(0)
        self.assertEqual(result['duration_seconds'],590)
        self.assertEqual(result['transfers'],1)
        self.assertEqual(result['walking_seconds'],100)
        self.assertEqual(result['waiting_seconds'],230)
        blocked=ScheduleSweep(trips,{'o':20},{'d':30},lambda s:{'y':850} if s=='x' else {s:0})
        self.assertIsNone(blocked.at(0)['duration_seconds'])
        self.assertIsNone(model.at(20)['duration_seconds']) # arrives 40 + strict slack 60 == departure

    def test_caps_and_combination_shares(self):
        t=trip('a',[('o',1000),('d',2000)])
        model=ScheduleSweep([t],{'o':500},{'d':500},lambda s:{s:0})
        self.assertIsNone(model.at(0)['duration_seconds']) # total walking exceeds 15 minutes
        valid=ScheduleSweep([t],{'o':10},{'d':20},lambda s:{s:0}).at(0)
        rows=[valid,dict(duration_seconds=None,rides=[])]
        c=combinations(rows)[0]
        self.assertEqual(c['share_all_minutes'],.5)
        self.assertEqual(c['share_reachable_minutes'],1)
        self.assertEqual(component_statistics(rows)['transfers'],{'0':1})
        self.assertIsNone(component_statistics([rows[1]])['walking_seconds'])


if __name__=='__main__':unittest.main()
