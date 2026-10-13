import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from nminus_engine import baseline_observation,continuation_key
from nminus_validation import validate_result
from benchmark_nminus import travel_payload
from test_nminus_validation import fixture


class PerformanceContractTests(unittest.TestCase):
    def test_same_cancelled_departure_reuses_reserve_but_not_budget(self):
        failed=dict(start_stop='A',departure_seconds=26000,trip_id='trip')
        self.assertEqual(continuation_key(failed,100,0),continuation_key(copy.deepcopy(failed),100,0))
        for changed in (dict(failed,trip_id='next'),dict(failed,start_stop='B'),dict(failed,departure_seconds=26060)):
            self.assertNotEqual(continuation_key(failed,100,0),continuation_key(changed,100,0))
        self.assertNotEqual(continuation_key(failed,100,0),continuation_key(failed,101,0))
        self.assertNotEqual(continuation_key(failed,100,0),continuation_key(failed,100,1))

    def test_baseline_is_exact_and_not_mutated(self):
        obs=dict(duration_seconds=20,walking_seconds=1,waiting_seconds=9,fixed_slack_seconds=0,
            transfers=0,arrival_seconds=100,rides=[{'trip_id':'t'}],start='presentation')
        row=baseline_observation(obs)
        self.assertNotIn('start',row);self.assertEqual(row['duration_seconds'],20)
        row['rides'][0]['trip_id']='changed';self.assertEqual(obs['rides'][0]['trip_id'],'t')
        self.assertEqual(baseline_observation(dict(duration_seconds=None,rides=[],start='time')),
            dict(duration_seconds=None,status='UNREACHABLE',rides=[]))

    def test_fast_mode_keeps_timeline_and_failed_trip_checks(self):
        result,base=fixture();result['verification']={'mode':'structural'}
        result['scenarios']['1'][0]['raw_r5_seconds']=None
        validate_result(result,base)
        result['scenarios']['1'][0]['total_seconds']+=1
        with self.assertRaisesRegex(ValueError,'Wrong total'):validate_result(result,base)

    def test_missing_raw_check_is_not_claimed_as_full_validation(self):
        result,base=fixture();result['scenarios']['1'][0]['raw_r5_seconds']=None
        with self.assertRaisesRegex(ValueError,'R5/sweep mismatch'):validate_result(result,base)
        result['verification']={'mode':'structural'}
        validate_result(result,base)
        result['scenarios']['1'][0]['raw_r5_seconds']=500
        with self.assertRaisesRegex(ValueError,'Unperformed'):validate_result(result,base)

    def test_comparison_ignores_audit_evidence_but_detects_changed_reserve(self):
        full,_=fixture();full['geojson']=full['scenarios']['1'][0]['geojson'];fast=copy.deepcopy(full)
        fast['verification']={'mode':'structural'};fast['scenarios']['1'][0]['raw_r5_seconds']=None
        self.assertEqual(travel_payload(full),travel_payload(fast))
        fast['scenarios']['1'][0]['reserve']['segments'][1]['trip_id']='different'
        self.assertNotEqual(travel_payload(full),travel_payload(fast))
