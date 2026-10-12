from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from nminus_core import exclude_schedule,remaining_resources,summarize,pareto_add,HORIZON_SECONDS,normalize_walk_geometry
from schedule_sweep import ScheduleSweep
from t90_core import PARAMETERS


class NMinusTests(unittest.TestCase):
    def test_exact_override_restores_on_success_and_failure(self):
        cancelled=SimpleNamespace(serviceCode=4);other=SimpleNamespace(serviceCode=4)
        with exclude_schedule(cancelled,999):
            self.assertEqual(cancelled.serviceCode,999)
            self.assertEqual(other.serviceCode,4)
        self.assertEqual(cancelled.serviceCode,4)
        with self.assertRaises(RuntimeError):
            with exclude_schedule(cancelled,999):raise RuntimeError('scenario failed')
        self.assertEqual(cancelled.serviceCode,4)

    def test_disconnected_street_parts_and_zero_length_paths_are_marked(self):
        geometry,lengths=normalize_walk_geometry(dict(type='MultiLineString',coordinates=[[[13.01,55.7],[13.02,55.7]],[[13.001,55.7],[13.005,55.7]]]),(13,55.7),(13.03,55.7))
        self.assertEqual(geometry['coordinates'][0],[13,55.7])
        self.assertEqual(geometry['coordinates'][-1],[13.03,55.7])
        self.assertTrue(geometry['approximate_connections'])
        self.assertGreater(lengths['internal'],1)
        point,_=normalize_walk_geometry(dict(type='Point',coordinates=[13,55.7]),(13,55.7),(13.001,55.7))
        self.assertEqual(point['type'],'LineString')

    def test_prefix_resources_are_not_reset_for_second_leg(self):
        resources=remaining_resources(590,1,PARAMETERS)
        self.assertEqual(resources['max_walk_seconds'],310)
        self.assertEqual(resources['max_rides'],1)
        self.assertEqual(resources['max_time_seconds'],HORIZON_SECONDS)
        with self.assertRaises(ValueError):remaining_resources(901,0,PARAMETERS)

    def test_not_applicable_distinct_from_unreachable_conditional_quantiles(self):
        rows=[dict(status='NOT_APPLICABLE'),dict(status='UNREACHABLE',total_seconds=None,extra_seconds=None),
              dict(status='REACHABLE',total_seconds=1000,extra_seconds=300),dict(status='REACHABLE',total_seconds=1200,extra_seconds=400)]
        summary=summarize(rows)
        self.assertEqual(summary['applicable_count'],3)
        self.assertEqual(summary['not_applicable_count'],1)
        self.assertEqual(summary['unreachable_count'],1)
        self.assertEqual(summary['coverage'],2/3)
        self.assertTrue(summary['conditional'])
        self.assertEqual(summary['total_percentiles_seconds'],dict(T50=1000,T90=1200,T99=1200))
        self.assertEqual(summary['extra_percentiles_seconds'],dict(P50=300,P90=400))
        self.assertIsNone(summarize([dict(status='UNREACHABLE')])['total_percentiles_seconds']['T90'])
        self.assertIsNone(summarize([dict(status='NOT_APPLICABLE')])['coverage'])

    def test_same_line_next_trip_and_no_reboarding_cancelled_at_later_stop(self):
        def trip(tid,dep):
            return dict(id=tid,route_id='same-line',line='139',mode='700',stops=[
                dict(id='A',departure=dep,arrival=dep,pickup='0',dropoff='0'),
                dict(id='B',departure=dep+100,arrival=dep+100,pickup='0',dropoff='0'),
                dict(id='C',departure=dep+200,arrival=dep+200,pickup='0',dropoff='0')])
        failed=trip('cancelled',100);next_trip=trip('next',400)
        resources=dict(PARAMETERS,max_time_seconds=HORIZON_SECONDS)
        # Filter the entire trip, not merely its original boarding departure.
        sweep=ScheduleSweep([next_trip],{'A':0,'B':0},{'C':0},lambda stop:{stop:0},resources)
        reserve=sweep.at(100)
        self.assertEqual(reserve['rides'][0]['trip_id'],'next')
        self.assertEqual(reserve['rides'][0]['route_id'],failed['route_id'])
        self.assertGreater(reserve['rides'][0]['departure_seconds'],160)
        too_late=trip('outside-horizon',8000)
        unreachable=ScheduleSweep([too_late],{'A':0},{'C':0},lambda stop:{stop:0},resources).at(100)
        self.assertIsNone(unreachable['duration_seconds'])
        self.assertEqual(unreachable['status'],'UNREACHABLE')

    def test_walk_and_permission_constraints_before_dominance(self):
        initial=SimpleNamespace(pattern=-1,back=None,time=100)
        bad=SimpleNamespace(pattern=0,back=initial,time=200,boardStopPosition=0,alightStopPosition=1)
        permissions={0:(['SCHEDULED','SCHEDULED'],['SCHEDULED','NONE'])}
        states=[]
        self.assertFalse(pareto_add(bad,states,100,900,2,permissions))
        self.assertEqual(states,[])
        permissions[0][1][1]='SCHEDULED'
        self.assertTrue(pareto_add(bad,states,100,900,2,permissions))
        walked=SimpleNamespace(pattern=-1,back=bad,time=1001)
        self.assertFalse(pareto_add(walked,[],100,800,2,permissions))


if __name__=='__main__':unittest.main()
