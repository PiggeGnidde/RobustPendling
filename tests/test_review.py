"""Review boundary and HTTP isolation tests; no JVM or local data needed."""
import json
from pathlib import Path
import sys
import threading
import tempfile
import queue
import subprocess
from unittest.mock import Mock,patch
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from review_server import normalize,digest,cached_detail,handler,Review,run_analysis,request_from_report
from transit_inputs import atomic_json


class ReviewTests(unittest.TestCase):
    def test_two_hour_default_and_historical_cache_are_distinct(self):
        req=normalize(self.request())
        self.assertEqual(req['max_time_minutes'],120)
        historic=normalize(dict(self.request(),max_time_minutes=45,walk_speed_kmh=3.6,max_walk_minutes=15))
        self.assertNotEqual(digest(req),digest(historic))
        report=dict(metadata=dict(date=req['date'],timezone=req['timezone'],start_minutes=['2026-10-12T07:00:00+02:00']*60,
                    parameters=dict(max_time_seconds=2700,max_rides=2,walk_speed_kmh=3.6,max_walk_seconds=900,
                    origin=dict(lat=req['from_lat'],lon=req['from_lon'],name=''),destination=dict(lat=req['to_lat'],lon=req['to_lon'],name=''))))
        self.assertEqual(request_from_report(report),historic)
        for horizon in (0,121,True,120.0):
            with self.assertRaises(ValueError):normalize(dict(self.request(),max_time_minutes=horizon))
        self.assertEqual(req['walk_speed_kmh'],4.5);self.assertEqual(req['max_walk_minutes'],20)
        for speed in (2.9,6.1,True,float('nan')):
            with self.assertRaises(ValueError):normalize(dict(self.request(),walk_speed_kmh=speed))
        for minutes in (9,31,True,20.5):
            with self.assertRaises(ValueError):normalize(dict(self.request(),max_walk_minutes=minutes))
        for key,value in [('walk_speed_kmh',3),('max_walk_minutes',30)]:
            self.assertNotEqual(digest(req),digest(normalize(dict(self.request(),**{key:value}))))

    def request(self):
        return dict(from_lat=55.67,from_lon=13.07,to_lat=55.70,to_lon=13.18,
                    date='2026-10-12',start='07:00',window_minutes=60,timezone='Europe/Stockholm')

    def test_invalid_coordinates_and_window(self):
        for key,value in [('from_lat',float('nan')),('from_lat',91),('to_lon',True),('window_minutes',1.5),('window_minutes',121),('max_rides',5),('max_rides',True),('start','07:00:01')]:
            with self.subTest(key=key),self.assertRaises(ValueError):normalize(dict(self.request(),**{key:value}))

    def test_input_identity_changes_for_each_routing_input(self):
        req=normalize(self.request());original=digest(req)
        for key,value in [('from_lat',55.68),('to_lon',13.19),('date','2026-10-13'),('start','07:01'),('window_minutes',59),('timezone','UTC'),('max_rides',4)]:
            self.assertNotEqual(original,digest(normalize(dict(self.request(),**{key:value}))))
        self.assertEqual(req,normalize(dict(self.request(),start='07:00:00')))

    def test_detail_matches_exact_index_not_duration(self):
        rep=dict(index=1,matches_sweep=True,best_duration_seconds=100)
        report=dict(minute_observations=[dict(duration_seconds=100),dict(duration_seconds=100),dict(duration_seconds=None)],representative_itineraries=[rep])
        self.assertIsNone(cached_detail(report,'a',0))
        self.assertEqual(cached_detail(report,'a',1)['itinerary'],rep)
        self.assertEqual(cached_detail(report,'b',1)['analysis_id'],'b')
        self.assertEqual(cached_detail(report,'a',2)['status'],'UNREACHABLE')
        rep['matches_sweep']=False
        self.assertIsNone(cached_detail(report,'a',1))
        for index in [-1,3,True,'0']:
            with self.assertRaises(ValueError):cached_detail(report,'a',index)

    def test_unsupported_nminus_day_and_dst_are_explicit_before_worker(self):
        for instant,seconds in [('2026-10-12T23:00:00+02:00',82800),('2026-10-25T07:00:00+01:00',25200)]:
            review=Review.__new__(Review)
            review.reports={'a':dict(metadata=dict(start_minutes=[instant],parameters=dict(feed_timezone='Europe/Stockholm',max_time_seconds=2700)),minute_observations=[dict(start_seconds=seconds,rides=[{}])])}
            self.assertEqual(review.nminus('a')['status'],'UNSUPPORTED_WINDOW')

    def test_baseline_horizon_cannot_silently_cross_feed_day(self):
        review=Review.__new__(Review)
        review.hashes={'osm':{'sha256':'47942e06ea6c96c8893933f71f448f7e1deac9d906c216a16c60a414db521b9d'}}
        review.area=None;review.coverage={'feed_timezone':'Europe/Stockholm'}
        request=dict(self.request(),start='22:01',window_minutes=1)
        self.assertEqual(review.analyze(request)['status'],'UNSUPPORTED_WINDOW')

    def test_pure_walk_does_not_require_two_hour_transit_horizon(self):
        with tempfile.TemporaryDirectory() as folder:
            for instant,seconds in [('2026-10-12T23:00:00+02:00',82800),('2026-10-25T07:00:00+01:00',25200)]:
                review=Review.__new__(Review);review.output=Path(folder);review.nminus_engine='test'
                review.reports={'walk':dict(metadata=dict(start_minutes=[instant],parameters=dict(feed_timezone='Europe/Stockholm',max_time_seconds=2700)),minute_observations=[dict(start_seconds=seconds,rides=[])])}
                review.worker_task=lambda *args:dict(status='ALLOWED')
                with patch('review_server.PRESETS',()):
                    self.assertEqual(review.nminus('walk')['status'],'ALLOWED')

    def test_loopback_http_exposes_only_whitelisted_files(self):
        review=SimpleNamespace(presets=[],jobs={},reports={})
        server=ThreadingHTTPServer(('127.0.0.1',0),handler(review))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        url=f'http://127.0.0.1:{server.server_port}'
        try:
            self.assertEqual(json.load(urlopen(url+'/api/presets'))['presets'],[])
            for path in ['/.env','/config/paths.toml','/../.env','/outputs/test.json']:
                with self.assertRaises(HTTPError) as caught:urlopen(url+path)
                self.assertEqual(caught.exception.code,404)
            with self.assertRaises(HTTPError) as caught:urlopen(Request(url+'/api/detail',data=b'[]',headers={'Content-Type':'application/json'}))
            self.assertEqual(caught.exception.code,400)
            with self.assertRaises(HTTPError) as caught:urlopen(Request(url+'/api/presets',headers={'Origin':'https://example.com'}))
            self.assertEqual(caught.exception.code,403)
        finally:server.shutdown();server.server_close()

    def test_detail_worker_reused_and_cache_avoids_second_request(self):
        with tempfile.TemporaryDirectory() as folder:
            review=Review.__new__(Review)
            review.output=Path(folder);review.engine='engine';review.lock=threading.Lock()
            review.reports={'analysis':dict(minute_observations=[dict(duration_seconds=100)]*3,representative_itineraries=[])}
            review.files={'analysis':Path(folder)/'report.json'}
            review.process=Mock();review.process.poll.return_value=None
            review.responses=queue.Queue();review.job=lambda work:work()
            def answer(line):
                task=json.loads(line)
                atomic_json(Path(task['output']),dict(status='OK',analysis_id=task['analysis_id'],index=task['index'],network_build_count=1))
                review.responses.put('REVIEW_RESULT '+task['output'])
            review.process.stdin.write.side_effect=answer
            with patch('review_server.subprocess.Popen') as spawn:
                first=review.detail('analysis',0)
                repeated=review.detail('analysis',0)
                other=review.detail('analysis',2)
            self.assertEqual(first['index'],0)
            self.assertEqual(repeated['source'],'cache')
            self.assertEqual(other['index'],2)
            self.assertEqual(review.process.stdin.write.call_count,2)
            spawn.assert_not_called()

    def test_analysis_timeout_stops_only_owned_process_tree(self):
        process=Mock(pid=12345)
        process.wait.side_effect=[subprocess.TimeoutExpired(['owned-worker'],1800),0]
        with patch('review_server.subprocess.Popen',return_value=process),patch('review_server.os.name','nt'),patch('review_server.subprocess.run') as kill:
            with self.assertRaises(subprocess.TimeoutExpired):run_analysis(['owned-worker'],None)
        self.assertEqual(kill.call_args.args[0],['taskkill','/PID','12345','/T','/F'])
        self.assertEqual(process.wait.call_count,2)


if __name__=='__main__':unittest.main()
