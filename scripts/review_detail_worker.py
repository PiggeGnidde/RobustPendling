"""Private JSON-lines worker: one JVM/network for the local review session."""
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import traceback
import time
from zoneinfo import ZoneInfo
from transit_inputs import ROOT, paths, fingerprint, atomic_json
from t90_core import PARAMETERS
from smoke_helpers import gtfs_tables, routing_feed
from schedule_sweep import load_trips


def main():
    config=Path(sys.argv[1]); inputs=paths(config)
    source_names=('analyze_t90.py','schedule_sweep.py','detailed_routes.py','r5_adapter.py','planner_core.py','nminus_core.py','nminus_engine.py','nminus_validation.py','t90_core.py','analysis_contract.py','walking_links.py')
    loaded_sources={name:fingerprint(ROOT/'scripts'/name) for name in source_names}
    hashes={k:fingerprint(inputs[k]) for k in ('osm','gtfs')}
    for key,value in {'JAVA_HOME':str(Path(sys.prefix)/'Library/lib/jvm'),
        'LOCALAPPDATA':str(ROOT/'cache/runtime'),'APPDATA':str(ROOT/'cache/config'),
        'MPLCONFIGDIR':str(ROOT/'cache/matplotlib'),'TEMP':str(ROOT/'cache/tmp'),
        'TMP':str(ROOT/'cache/tmp')}.items():os.environ[key]=value
    (ROOT/'cache/tmp').mkdir(parents=True,exist_ok=True)
    sys.argv=[sys.argv[0],'--max-memory',PARAMETERS['jvm_heap'],'--verbose']
    import r5py
    import jpype
    from jvm_diagnostics import instrument_shutdown
    from detailed_routes import collect
    instrument_shutdown()
    if r5py.__version__!='1.1.7':raise RuntimeError('Unverified r5py version')
    if fingerprint(ROOT/'cache/runtime/r5py/r5-v7.5.1-r5py-all.jar')['sha256']!='d50be106cadd7b636cfc0e209052767d7df570629f79fdf98ecd5cf5d2d89be7':raise RuntimeError('Unverified R5 jar')
    derived=ROOT/'data/gtfs/skane-20261011-r0.zip'
    routing_feed(inputs['gtfs'],derived)
    network=None
    nminus=None
    stops,_=gtfs_tables(inputs['gtfs'])
    names={s['stop_id']:s['stop_name'] for s in stops}
    coordinates={s['stop_id']:(float(s['stop_lon']),float(s['stop_lat'])) for s in stops}
    for line in sys.stdin:
        task=json.loads(line)
        if task.get('command')=='stop':break
        try:
            if any(fingerprint(ROOT/'scripts'/name)!=value for name,value in loaded_sources.items()):
                raise ValueError('Routing code changed; restart the review server')
            if task.get('command')=='analyze':
                from analyze_t90 import parser,worker
                from analysis_contract import request_grid
                data=json.loads(Path(task['report']).read_text(encoding='utf-8'))
                arguments=['--config',str(config),'--output',task['output'],'--planner']
                for key,value in data.items():arguments.extend(['--'+key.replace('_','-'),str(value)])
                args=parser().parse_args(arguments)
                if network is None:
                    started=time.perf_counter();network=r5py.TransportNetwork(inputs['osm'],[derived])
                    build_seconds=time.perf_counter()-started
                worker(args,request_grid(args.date,args.start,args.window_minutes,args.timezone),reused_network=network)
                print('REVIEW_RESULT '+task['output'],flush=True)
                continue
            report=json.loads(Path(task['report']).read_text(encoding='utf-8'))
            actual_versions=dict(python=sys.version.split()[0],r5py=r5py.__version__,r5='7.5.1-r5py',
                java=str(jpype.JClass('java.lang.System').getProperty('java.version')))
            if actual_versions!=report['metadata']['versions']:raise ValueError('Runtime differs from baseline; regenerate baseline')
            expected=report['metadata']['input_hashes']
            if hashes['osm']!=expected['osm'] or hashes['gtfs']!=expected['gtfs_original']:
                raise ValueError('Input hashes differ from analysis')
            if any(fingerprint(inputs[k])!=hashes[k] for k in hashes):raise ValueError('Inputs changed')
            if network is None:
                started=time.perf_counter()
                network=r5py.TransportNetwork(inputs['osm'],[derived])
                build_seconds=time.perf_counter()-started
            if task.get('command') in ('nminus','regression'):
                from nminus_engine import NMinusEngine
                if nminus is None:nminus=NMinusEngine(network,derived,stops,expected)
                started=time.perf_counter()
                result=nminus.analyze(report,baseline_only=task['command']=='regression',validation=task.get('validation',False))
                from nminus_validation import validate_result
                if task['command']=='nminus':validate_result(result,report)
                if any(fingerprint(inputs[k])!=hashes[k] for k in hashes):raise ValueError('Inputs changed during N−1 routing')
                result.update(analysis_id=task['analysis_id'])
                atomic_json(Path(task['output']),result)
                print('REVIEW_TIMING '+json.dumps(dict(command=task['command'],seconds=time.perf_counter()-started)),flush=True)
                print('REVIEW_RESULT '+task['output'],flush=True)
                continue
            index=task['index']; obs=report['minute_observations'][index]
            instant=datetime.fromisoformat(obs['start']).astimezone(ZoneInfo('Europe/Stockholm'))
            ready=instant.hour*3600+instant.minute*60
            params=report['metadata']['parameters']
            trips={t['id']:t for t in load_trips(derived,instant,ready,ready+params['max_time_seconds'])}
            rep=dict(index=index,start=obs['start'],percentile_roles=[],audit_roles=[],status='REACHABLE')
            item,features=collect(network,params['origin'],params['destination'],rep,obs,instant,trips,names,coordinates,parameters=params)
            if not item['matches_sweep']:raise ValueError('Detail does not match verified minute sweep')
            if any(fingerprint(inputs[k])!=hashes[k] for k in hashes):raise ValueError('Inputs changed during routing')
            result=dict(status='OK',analysis_id=task['analysis_id'],index=index,itinerary=item,
                        geojson=dict(type='FeatureCollection',features=features),source='worker',network_build_count=1,
                        worker_pid=os.getpid(),network_build_seconds=build_seconds,input_hashes=hashes)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            result=dict(status='DETAIL_ERROR',message='Körningen kunde inte verifieras. Se lokal workerlogg.',analysis_id=task['analysis_id'],index=task.get('index'))
        atomic_json(Path(task['output']),result)
        print('REVIEW_RESULT '+task['output'],flush=True)


if __name__=='__main__':main()
