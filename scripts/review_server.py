"""Loopback-only review server. No dependencies, credentials or public hosting."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import queue
import tomllib
from urllib.parse import urlparse
from analysis_contract import point,request_grid,area_check
from transit_inputs import ROOT,paths,fingerprint,atomic_json
from t90_core import PARAMETERS
from jvm_diagnostics import cleanup_after_exit
from smoke_helpers import gtfs_tables
from validate_phase2c import CASES
from nminus_validation import validate_result
from nminus_core import HORIZON_SECONDS
from planner_core import routing_parameters,service_coverage,date_check,combined_nminus,deadline_result

PRESETS=('lomma_lund','malmo_varnhem','gunnesbo_ideon')


def run_analysis(command,log):
    """A timed-out supervisor must not leave its isolated JVM child alive."""
    process=subprocess.Popen(command,stdout=log,stderr=log)
    try:return process.wait(timeout=1800)
    except subprocess.TimeoutExpired:
        if os.name=='nt':
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,check=False)
        else:process.kill()
        process.wait()
        raise


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def normalize(data):
    result={}
    for prefix in ('from','to'):
        p=point(data.get(prefix+'_lat'),data.get(prefix+'_lon'),str(data.get(prefix+'_name',''))[:120])
        result.update({prefix+'_'+k:p[k] for k in ('lat','lon','name')})
    grid=request_grid(data['date'],data['start'],data['window_minutes'],data['timezone'])
    result.update(date=data['date'],start=grid[0].time().isoformat(),window_minutes=len(grid),timezone=data['timezone'])
    horizon=data.get('max_time_minutes',120)
    if isinstance(horizon,bool) or not isinstance(horizon,int):raise ValueError('Journey horizon must be integer minutes')
    params=routing_parameters(data.get('max_rides',2),horizon*60)
    result.update(max_rides=params['max_rides'],max_time_minutes=horizon)
    if len(grid)>120:raise ValueError('Local planner allows at most 120 start minutes per request')
    return result


def request_from_report(report):
    meta=report['metadata']; p=meta['parameters']; first=meta['start_minutes'][0]
    result=dict(date=meta['date'],start=first[11:19],window_minutes=len(meta['start_minutes']),timezone=meta['timezone'],max_rides=p['max_rides'],max_time_minutes=p['max_time_seconds']//60)
    for prefix,key in [('from','origin'),('to','destination')]:
        result.update({prefix+'_'+k:p[key][k] for k in ('lat','lon','name')})
    return normalize(result)


def cached_detail(report,analysis_id,index):
    if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<len(report['minute_observations']):raise ValueError('Ogiltig startminut')
    obs=report['minute_observations'][index]
    if obs['duration_seconds'] is None:return dict(status='UNREACHABLE',analysis_id=analysis_id,index=index,message='Ingen resa hittades inom analysens gränser för restid, gång och trafikben. Det betyder inte att platsen saknar kollektivtrafik.')
    for item in report['representative_itineraries']:
        if item['index']==index and item['matches_sweep']:
            return dict(status='OK',analysis_id=analysis_id,index=index,itinerary=item,source='saved')
    return None


class Review:
    def __init__(self,config):
        self.config=config; self.inputs=paths(config)
        self.hashes={k:fingerprint(self.inputs[k]) for k in ('osm','gtfs')}
        self.area=tomllib.loads(config.read_text(encoding='utf-8')).get('network_area')
        self.coverage=service_coverage(self.inputs['gtfs'])
        self.legacy=json.loads((ROOT/'scripts/legacy_regressions.json').read_text(encoding='utf-8'))['analysis_identities']
        self.legacy_nminus=json.loads((ROOT/'scripts/legacy_regressions.json').read_text(encoding='utf-8'))['nminus_checksums']
        self.reports={};self.files={};self.presets=[];self.jobs={};self.pool=ThreadPoolExecutor(max_workers=2)
        self.lock=threading.Lock();self.analysis_lock=threading.Lock();self.process=None;self.log=None
        self.output=ROOT/'outputs/review';self.output.mkdir(parents=True,exist_ok=True)
        self.engine=digest({name:fingerprint(ROOT/'scripts'/name) for name in ('review_detail_worker.py','detailed_routes.py','r5_adapter.py','nminus_core.py','nminus_engine.py')})
        self.nminus_engine=digest({name:fingerprint(ROOT/'scripts'/name) for name in ('nminus_engine.py','nminus_core.py','review_detail_worker.py','schedule_sweep.py','planner_core.py','nminus_validation.py','r5_adapter.py')})
        for name in PRESETS:
            path=ROOT/'outputs'/f'phase2c_{name}_1.json'
            if not path.exists():
                stops={s['stop_id']:s for s in gtfs_tables(self.inputs['gtfs'])[0]}
                req=dict(date='2026-10-12',start='07:00:00',window_minutes=5,timezone='Europe/Stockholm',max_rides=2)
                for prefix,stop_id in zip(('from','to'),CASES[name]):
                    stop=stops[stop_id]
                    req.update({prefix+'_lat':float(stop['stop_lat']),prefix+'_lon':float(stop['stop_lon']),prefix+'_name':stop['stop_name']})
                self.presets.append(dict(id=None,request=req,label=req['from_name']+' → '+req['to_name']))
                continue
            report=json.loads(path.read_text(encoding='utf-8'))
            self.verify(report)
            geo=ROOT/report['geojson_path']
            if fingerprint(geo)['sha256']!=report['geojson_sha256']:raise ValueError('Saved GeoJSON checksum mismatch')
            identity=self.register(report,path)
            self.presets.append(dict(id=identity,request=request_from_report(report),label=request_from_report(report)['from_name']+' → '+request_from_report(report)['to_name']))

    def verify(self,report):
        meta=report['metadata'];h=meta['input_hashes']
        if report['status']!='OK' or h['osm']!=self.hashes['osm'] or h['gtfs_original']!=self.hashes['gtfs']:raise ValueError('Analysis or inputs not verified')
        if any(meta['parameters'].get(k)!=v for k,v in routing_parameters(meta['parameters']['max_rides'],meta['parameters']['max_time_seconds']).items()):raise ValueError('Routing parameters differ')
        if meta['versions']['r5py']!='1.1.7':raise ValueError('Unverified engine version')
        identity=digest(dict(metadata=meta,metrics=report['metrics'],minutes=report['minute_observations']))
        if identity in self.legacy.values():return
        for name in ('detailed_routes.py','r5_adapter.py','schedule_sweep.py','analysis_contract.py','t90_core.py','planner_core.py','nminus_core.py','nminus_engine.py'):
            if fingerprint(ROOT/'scripts'/name)!=h['code'][name]:raise ValueError('Saved analysis engine differs; regenerate analysis')

    def register(self,report,path):
        identity=digest(dict(metadata=report['metadata'],metrics=report['metrics'],minutes=report['minute_observations']))
        self.reports[identity]=report;self.files[identity]=path
        return identity

    def job(self,work):
        import uuid
        identity=uuid.uuid4().hex;self.jobs[identity]=dict(status='LOADING')
        def run():
            try:self.jobs[identity]=dict(status='DONE',result=work())
            except Exception as error:
                # No raw subprocess stderr or data paths cross the browser boundary.
                self.jobs[identity]=dict(status='ERROR',message='Körningen misslyckades ('+type(error).__name__+'). Se outputs/review.')
        self.pool.submit(run)
        return dict(job_id=identity)

    def analyze(self,data):
        req=normalize(data)
        area=area_check(point(req['from_lat'],req['from_lon']),point(req['to_lat'],req['to_lon']),self.hashes['osm']['sha256'],self.area)
        if area['status']!='OK':return dict(status=area['status'],message='Punkterna måste ligga inom OSM-området 12.95–13.30 / 55.60–55.80.')
        from datetime import timedelta
        from zoneinfo import ZoneInfo
        if not self.coverage['feed_timezone']:return dict(status='UNSUPPORTED_FEED',message='Feeden behöver en entydig trafik-tidszon.')
        grid=[t.astimezone(ZoneInfo(self.coverage['feed_timezone'])) for t in request_grid(req['date'],req['start'],req['window_minutes'],req['timezone'])]
        last=grid[-1]+timedelta(minutes=req['max_time_minutes'])
        if last.date()!=grid[0].date() or grid[-1].date()!=grid[0].date() or last.utcoffset()!=grid[0].utcoffset():
            return dict(status='UNSUPPORTED_WINDOW',message='Basresans sökhorisont passerar trafikdygn eller tidsomställning. Välj ett tidigare avreseintervall.')
        supported=date_check(self.coverage,grid[0].date().isoformat())
        if supported['status']!='OK':return supported
        for identity,report in list(self.reports.items()):
            if request_from_report(report)==req:return dict(status='OK',analysis_id=identity,report=report)
        engine={name:fingerprint(ROOT/'scripts'/name) for name in ('analyze_t90.py','planner_core.py','schedule_sweep.py','detailed_routes.py','r5_adapter.py','t90_core.py','analysis_contract.py','review_detail_worker.py','nminus_core.py','nminus_engine.py')}
        key=digest(dict(request=req,hashes=self.hashes,parameters=routing_parameters(req['max_rides'],req['max_time_minutes']*60),engine=engine))
        path=self.output/f'analysis-{key}.json'
        request_file=self.output/f'request-{key}.json'
        atomic_json(request_file,req);self.files[key]=request_file
        return self.worker_task(key,None,path,'analyze')

    def detail(self,identity,index):
        report=self.reports[identity]
        found=cached_detail(report,identity,index)
        if found:return found
        path=self.output/f'detail-{identity}-{index}-{self.engine}.json'
        return self.worker_task(identity,index,path,'detail')

    def nminus(self,identity):
        if identity not in self.reports:raise ValueError('Unknown analysis')
        from datetime import datetime,timedelta
        from zoneinfo import ZoneInfo
        report=self.reports[identity];meta=report['metadata'];p=meta['parameters']
        first=datetime.fromisoformat(meta['start_minutes'][0]).astimezone(ZoneInfo(p['feed_timezone']))
        midnight=first.replace(hour=0,minute=0,second=0,microsecond=0)
        has_transit=any(obs.get('rides') for obs in report['minute_observations'])
        latest=report['minute_observations'][-1]['start_seconds']+p['max_time_seconds']+(HORIZON_SECONDS if has_transit else 0)
        reference_offset=midnight.utcoffset() if has_transit else first.utcoffset()
        if latest>=86400 or (midnight+timedelta(seconds=latest)).utcoffset()!=reference_offset:
            return dict(status='UNSUPPORTED_WINDOW',message='N−1 stöder ännu inte trafikdygns- eller tidsomställningsövergång. Välj ett datum utan tidsomställning eller ett tidigare avreseintervall.')
        path=self.output/f'nminus-{identity}-{self.nminus_engine}.json'
        # Reuse CLI validation artifacts only when baseline identity AND current
        # N−1 code hashes match. Runtime/timing metadata is kept outside results.
        if not path.exists():
            for case in PRESETS:
                saved=ROOT/'outputs/nminus'/f'{case}_1.json'
                if saved.exists():
                    value=json.loads(saved.read_text(encoding='utf-8'))
                    current=all(fingerprint(ROOT/'scripts'/name)==h for name,h in value.get('code_hashes',{}).items()) and bool(value.get('code_hashes'))
                    archived=value.get('canonical_sha256')==self.legacy_nminus.get(case) and identity==self.legacy.get(case)
                    if value.get('analysis_id')==identity and (current or archived):
                        validate_result(value,self.reports[identity])
                        if 'combined' not in value:
                            value['combined']=combined_nminus(value['minute_observations'],value['scenarios'])
                            value['canonical_sha256']=digest({k:v for k,v in value.items() if k not in ('canonical_sha256','analysis_id','source')})
                        atomic_json(path,value);break
        return self.worker_task(identity,None,path,'nminus')

    def deadline(self,data):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        identity=data['analysis_id'];report=self.reports[identity]
        zone=ZoneInfo(report['metadata']['timezone'])
        instant=datetime.fromisoformat(report['metadata']['date']+'T'+data['deadline']).replace(tzinfo=zone)
        if instant.utcoffset()!=instant.replace(fold=1).utcoffset():raise ValueError('Ambiguous deadline')
        pending=self.nminus(identity)
        if pending.get('status')=='UNSUPPORTED_WINDOW':return pending
        def work():
            import time
            while self.jobs[pending['job_id']]['status']=='LOADING':time.sleep(.1)
            job=self.jobs[pending['job_id']]
            if job['status']!='DONE' or job['result']['status']!='OK':raise ValueError('N−1 deadline calculation failed')
            nminus=job['result'];combined=nminus.get('combined') or combined_nminus(report['minute_observations'],nminus['scenarios'])
            return dict(status='OK',analysis_id=identity,**deadline_result(report['minute_observations'],combined,instant.isoformat()))
        return self.job(work)

    def worker_task(self,identity,index,path,command):
        def publish(result):
            if command=='analyze' and result['status']=='OK':
                self.verify(result)
                actual=self.register(result,path)
                return dict(status='OK',analysis_id=actual,report=result)
            return result
        def run():
            with self.lock:
                if path.exists():
                    result=json.loads(path.read_text(encoding='utf-8'))
                    if result['status']=='OK':
                        if command=='analyze':return publish(result)
                        if result.get('analysis_id')!=identity:raise ValueError('Cache belongs to another analysis')
                        if command=='nminus':validate_result(result,self.reports[identity])
                        return dict(result,source='cache')
                if self.process is None or self.process.poll() is not None:
                    self.reap()
                    self.log=(self.output/'detail-worker.stderr.log').open('w',encoding='utf-8')
                    self.process=subprocess.Popen([sys.executable,'-B',str(ROOT/'scripts/review_detail_worker.py'),str(self.config)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,encoding='utf-8')
                    self.responses=queue.Queue()
                    def read_stdout(process,responses):
                        with (self.output/'detail-worker.stdout.log').open('w',encoding='utf-8') as log:
                            for line in process.stdout:
                                log.write(line);log.flush()
                                if line.startswith('REVIEW_RESULT '):responses.put(line.rstrip())
                        responses.put(None)
                    self.reader=threading.Thread(target=read_stdout,args=(self.process,self.responses),daemon=True)
                    self.reader.start()
                self.process.stdin.write(json.dumps(dict(command=command,report=str(self.files[identity]),analysis_id=identity,index=index,output=str(path)))+'\n');self.process.stdin.flush()
                try:
                    response=self.responses.get(timeout=600)
                    if response=='REVIEW_RESULT '+str(path):return publish(json.loads(path.read_text(encoding='utf-8')))
                except queue.Empty:self.process.kill()
                self.process.wait();self.reap()
                raise RuntimeError('Detail worker exited')
        return self.job(run)

    def reap(self):
        if self.process is None:return
        if self.process.poll() is None:return
        self.reader.join(timeout=2)
        if self.log:self.log.close()
        stderr=(self.output/'detail-worker.stderr.log').read_text(encoding='utf-8')
        atomic_json(self.output/'detail-worker-exit.json',dict(pid=self.process.pid,exit_code=self.process.returncode,cleanup_after_exit=cleanup_after_exit(stderr)))
        self.process=None

    def close(self):
        self.pool.shutdown(wait=True)
        if self.process and self.process.poll() is None:
            self.process.stdin.write('{"command":"stop"}\n');self.process.stdin.flush()
            try:self.process.wait(timeout=60)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        self.reap()


def handler(review):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,value,status=200):
            body=json.dumps(value,allow_nan=False).encode();self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store')
            self.end_headers();self.wfile.write(body)
        def trusted(self):
            host=self.headers.get('Host','')
            origin=self.headers.get('Origin')
            return host==f'127.0.0.1:{self.server.server_port}' and (origin is None or origin=='http://'+host)
        def do_GET(self):
            if not self.trusted():self.send(dict(message='Endast lokal åtkomst'),403);return
            path=urlparse(self.path).path
            if path=='/api/presets':
                value=dict(presets=review.presets,parameters=routing_parameters(2,7200))
                if hasattr(review,'coverage'):
                    value.update(coverage=dict(first=review.coverage['first'],last=review.coverage['last']),area=review.area,max_window_minutes=120)
                self.send(value);return
            if path.startswith('/api/jobs/'):
                self.send(review.jobs.get(path.rsplit('/',1)[1],dict(status='ERROR',message='Okänd körning')));return
            if path.startswith('/api/results/'):
                identity=path.rsplit('/',1)[1]
                if identity not in review.reports:self.send(dict(message='Okänd analys'),404);return
                self.send(dict(status='OK',analysis_id=identity,report=review.reports[identity]));return
            static={'/':'index.html','/app.js':'app.js','/review_map.js':'review_map.js','/style.css':'style.css'}
            if path not in static:self.send(dict(message='Hittades inte'),404);return
            body=(ROOT/'web'/static[path]).read_bytes();self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8' if path=='/' else 'text/css; charset=utf-8' if path=='/style.css' else 'text/javascript; charset=utf-8')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' https://unpkg.com 'unsafe-inline'; script-src 'self' https://unpkg.com; connect-src 'self'; img-src 'self' data: https://tile.openstreetmap.org; object-src 'none'; frame-ancestors 'none'")
            self.send_header('Referrer-Policy','strict-origin-when-cross-origin')
            self.end_headers();self.wfile.write(body)
        def do_POST(self):
            if not self.trusted():self.send(dict(message='Endast lokal åtkomst'),403);return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=8192:raise ValueError('Ogiltigt anrop')
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict):raise ValueError('Expected object')
                if self.path=='/api/shutdown':
                    self.send(dict(status='STOPPING'))
                    threading.Thread(target=self.server.shutdown,daemon=True).start()
                    return
                if self.path=='/api/analyze':result=review.analyze(data)
                elif self.path=='/api/detail':result=review.detail(data['analysis_id'],data['index'])
                elif self.path=='/api/nminus':result=review.nminus(data['analysis_id'])
                elif self.path=='/api/deadline':result=review.deadline(data)
                else:self.send(dict(message='Hittades inte'),404);return
                self.send(result)
            except (ValueError,KeyError,TypeError) as error:self.send(dict(status='INVALID_REQUEST',message='Kontrollera koordinater, datum, tidszon och heltalsminuter.'),400)
    return Handler


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8765);p.add_argument('--config',type=Path,default=ROOT/'config/paths.toml')
    args=p.parse_args();review=Review(args.config)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler(review))
    print(f'RobustPendling review: http://127.0.0.1:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close();review.close()


if __name__=='__main__':main()
