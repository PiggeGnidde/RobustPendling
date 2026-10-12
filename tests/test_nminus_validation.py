import copy
import hashlib
import json
import tempfile
import threading
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from nminus_validation import validate_result
from nminus_core import summarize
from review_server import Review
from transit_inputs import atomic_json


def fixture():
    def time(value):return f'2026-10-12T07:{value}+02:00'
    geometry=dict(type='LineString',coordinates=[[13,55.7],[13.001,55.7]])
    def leg(mode,a,b,travel,wait=0,slack=0,trip=None):
        return dict(mode=mode,departure=time(a),arrival=time(b),travel_seconds=travel,
            wait_seconds=wait,fixed_slack_seconds=slack,walking_seconds=travel if mode=='WALK' else 0,
            trip_id=trip,geometry=geometry)
    baseline=[leg('WALK','00:00','00:30',30),leg('BUS','02:00','04:00',120,90,trip='failed'),leg('WALK','05:00','05:20',20,slack=60)]
    reserve=[leg('WALK','02:00','02:00',0),leg('BUS','07:00','09:00',120,300,trip='next'),leg('WALK','10:00','10:20',20,slack=60)]
    failed=dict(trip_id='failed',start_stop='stop',departure_seconds=25320)
    obs=dict(start=time('00:00'),duration_seconds=320,rides=[failed])
    base=dict(metrics={'test':True},minute_observations=[obs])
    row=dict(index=0,start=obs['start'],status='REACHABLE',failed_leg=failed,
        notification=dict(stop_id='stop',time=time('02:00')),
        completed=dict(segments=baseline[:1],elapsed_seconds=120,wait_before_notification_seconds=90),
        search_end='2026-10-12T09:02:00+02:00',reserve=dict(duration_seconds=500,segments=reserve),
        total_seconds=620,extra_seconds=300,raw_r5_seconds=500)
    features=[]
    for phase,segments in [('completed',row['completed']['segments']),('reserve',reserve)]:
        for index,segment in enumerate(segments):
            props={k:v for k,v in segment.items() if k!='geometry'}
            props.update(index=0,leg_number=1,phase=phase,segment=index)
            features.append(dict(type='Feature',geometry=segment['geometry'],properties=props))
    row['geojson']=dict(type='FeatureCollection',features=features)
    rows=[row]
    result=dict(status='OK',base_metrics=base['metrics'],minute_observations=base['minute_observations'],
        base_itineraries=[baseline],scenarios={'1':rows},summaries={'1':summarize(rows)})
    return result,base


class ContractTests(unittest.TestCase):
    def test_checksum_rejects_tampering_but_allows_cache_envelope(self):
        result,base=fixture()
        result['canonical_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        result.update(analysis_id='local-analysis',source='cache')
        self.assertEqual(validate_result(result,base)['reachable_checked'],1)
        result['summaries']['1']['unexpected']='tampered'
        with self.assertRaisesRegex(ValueError,'checksum mismatch'):
            validate_result(result,base)

    def test_server_revalidates_cached_nminus_and_analysis_identity(self):
        result,base=fixture()
        result['canonical_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        result['analysis_id']='analysis'
        review=Review.__new__(Review)
        review.lock=threading.Lock();review.job=lambda work:work()
        review.reports={'analysis':base}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'cached.json'
            atomic_json(path,result)
            self.assertEqual(review.worker_task('analysis',None,path,'nminus')['source'],'cache')
            result['analysis_id']='another-analysis';atomic_json(path,result)
            with self.assertRaisesRegex(ValueError,'another analysis'):
                review.worker_task('analysis',None,path,'nminus')
            result['analysis_id']='analysis';result['summaries']['1']['unexpected']='tampered'
            atomic_json(path,result)
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):
                review.worker_task('analysis',None,path,'nminus')

    def test_preserved_prefix_and_wait_at_notification(self):
        result,base=fixture()
        self.assertEqual(validate_result(result,base)['reachable_checked'],1)

    def test_unreachable_has_no_finite_duration_or_geometry(self):
        result,base=fixture();row=result['scenarios']['1'][0]
        row.update(status='UNREACHABLE',total_seconds=None,extra_seconds=None,raw_r5_seconds=None)
        row['reserve']=dict(duration_seconds=None,segments=[])
        row['geojson']['features']=row['geojson']['features'][:1]
        result['summaries']['1']=summarize([row])
        self.assertEqual(validate_result(result,base)['unreachable_checked'],1)
        row['total_seconds']=9999
        with self.assertRaisesRegex(ValueError,'Invented'):validate_result(result,base)

    def test_restart_at_origin_or_cancelled_reuse_rejected(self):
        result,base=fixture();result['scenarios']['1'][0]['completed']['segments']=[]
        with self.assertRaisesRegex(ValueError,'Completed'):validate_result(result,base)
        result,base=fixture();result['scenarios']['1'][0]['reserve']['segments'][1]['trip_id']='failed'
        with self.assertRaisesRegex(ValueError,'Cancelled'):validate_result(result,base)

    def test_original_time_boarding_and_map_tampering_rejected(self):
        result,base=fixture();result['scenarios']['1'][0]['start']='2026-10-12T07:02:00+02:00'
        with self.assertRaisesRegex(ValueError,'Original'):validate_result(result,base)
        result,base=fixture();result['scenarios']['1'][0]['reserve']['segments'][1]['wait_seconds']=60
        with self.assertRaisesRegex(ValueError,'reserve'):validate_result(result,base)
        result,base=fixture();result['scenarios']['1'][0]['geojson']['features']=[]
        with self.assertRaisesRegex(ValueError,'Map'):validate_result(result,base)


if __name__=='__main__':unittest.main()
