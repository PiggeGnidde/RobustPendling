from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from analysis_contract import positive_jumps,audited_representatives,itinerary_timing,connect_walk_geometry
from r5_adapter import permission_filtered_add,stop_permissions_allow
from jvm_diagnostics import cleanup_after_exit
from validate_phase2c import validate_worker,compare_results,REPRODUCIBLE_FIELDS


class ValidationTests(unittest.TestCase):
    def test_top_jumps_stable_ties_and_unreachable(self):
        rows=[dict(start=str(i),duration_seconds=v) for i,v in enumerate([100,200,150,250,None,200])]
        jumps=positive_jumps(rows)
        self.assertEqual([j['before_index'] for j in jumps],[3,0,2])
        self.assertEqual(jumps[0]['increase_seconds'],'UNREACHABLE')
        self.assertEqual(positive_jumps(rows,0),[])

    def test_overlapping_minutes_routed_once(self):
        rows=[dict(start=str(i),duration_seconds=v) for i,v in enumerate([100,200,400,300])]
        reps=audited_representatives(rows,positive_jumps(rows))
        self.assertEqual(len({r['index'] for r in reps}),len(reps))
        self.assertEqual(next(r for r in reps if r['index']==1)['audit_roles'],['jump_1_before','jump_2_after'])

    def test_no_dropoff_state_cannot_prune_valid_alternative(self):
        delegate=Mock();delegate.add.return_value=True
        bad=SimpleNamespace(pattern=0,boardStopPosition=0,alightStopPosition=1)
        permissions={0:(['COORDINATE_WITH_DRIVER','SCHEDULED'],['NONE','NONE'])}
        self.assertFalse(permission_filtered_add(bad,delegate,permissions))
        delegate.add.assert_not_called()
        permissions[0][1][1]='COORDINATE_WITH_DRIVER'
        self.assertTrue(permission_filtered_add(bad,delegate,permissions))
        delegate.add.assert_called_once_with(bad)
        self.assertFalse(stop_permissions_allow('CALL_AGENCY','SCHEDULED'))

    def test_transfer_clock_components_and_strict_boarding(self):
        ready='2026-10-12T07:00:00+02:00'
        def leg(mode,a,b,travel,wait=0):
            return dict(mode=mode,departure=f'2026-10-12T07:{a}+02:00',arrival=f'2026-10-12T07:{b}+02:00',
                        travel_seconds=travel,wait_seconds=wait,fixed_slack_seconds=0)
        segments=[leg('BUS','02:00','05:00',180,120),leg('WALK','05:00','06:00',60),
                  leg('TRAM','08:00','10:00',120,120)]
        result=itinerary_timing(segments,ready)
        self.assertTrue(result['valid'])
        self.assertEqual(result['duration_seconds'],600)
        segments[-1]=leg('TRAM','07:00','09:00',120,60)
        self.assertFalse(itinerary_timing(segments,ready)['valid'])

    def test_cleanup_rejects_untrusted_paths(self):
        with self.assertRaises(ValueError):cleanup_after_exit('JVM_CLEANUP_DEFERRED '+json.dumps('C:/Windows'))
        self.assertEqual(cleanup_after_exit('No deferred directory'),[])

    def test_walk_map_includes_named_stop_connectors(self):
        geometry=dict(type='LineString',coordinates=[[13.01,55.71],[13.00,55.71]])
        result,connectors=connect_walk_geometry(geometry,(13.00,55.70),(13.01,55.71))
        self.assertEqual(result['coordinates'][0],[13.00,55.70])
        self.assertEqual(result['coordinates'][-1],[13.01,55.71])
        self.assertGreater(connectors['start'],1000)

    def test_worker_cleanup_and_reproduction_exclusions(self):
        worker=dict(exit_code=0,exited=True,jpype_shutdown_error=False,cleanup_after_exit=[dict(removed=True)])
        validate_worker(worker)
        with self.assertRaises(ValueError):validate_worker(dict(worker,cleanup_after_exit=[dict(removed=False)]))
        with self.assertRaises(ValueError):validate_worker(dict(worker,jpype_shutdown_error=True))
        a={field:None for field in REPRODUCIBLE_FIELDS}
        b=dict(a,worker={'pid':'different'},timing={'seconds':3},geojson_path='different_basename')
        self.assertTrue(compare_results(a,b)['identical'])
        with self.assertRaises(ValueError):compare_results(a,dict(b,geojson_sha256='changed'))


if __name__=='__main__':unittest.main()
