"""Reproduce an explicit schedule sweep, supervising an isolated JVM worker."""
import argparse
import copy
from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import warnings

from transit_inputs import ROOT, paths, fingerprint, atomic_json
from smoke_helpers import gtfs_tables, select_station, routing_feed
from t90_core import PARAMETERS, minute_grid, statistics, metadata, combinations, component_statistics
from schedule_sweep import ScheduleSweep, load_trips


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=ROOT/'config/paths.toml')
    p.add_argument('--date', default='2026-10-12')
    p.add_argument('--start', default='07:00:00')
    p.add_argument('--end', default='07:59:59')
    p.add_argument('--timezone', default='Europe/Stockholm')
    p.add_argument('--output', type=Path, default=ROOT/'outputs/t90_schedule_lomma_lund.json')
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    return p


def worker(args, grid):
    inputs = paths(args.config)
    initial_hashes = dict(osm=fingerprint(inputs['osm']),gtfs=fingerprint(inputs['gtfs']))
    os.environ['JAVA_HOME'] = str(Path(sys.prefix)/'Library/lib/jvm')
    os.environ['LOCALAPPDATA'] = str(ROOT/'cache/runtime')
    os.environ['APPDATA'] = str(ROOT/'cache/config')
    os.environ['MPLCONFIGDIR'] = str(ROOT/'cache/matplotlib')
    temporary = ROOT/'cache/tmp'
    temporary.mkdir(parents=True,exist_ok=True)
    os.environ['TEMP'] = os.environ['TMP'] = str(temporary)
    sys.argv = [sys.argv[0], '--max-memory', PARAMETERS['jvm_heap'], '--verbose']
    import r5py
    import jpype
    from r5py.r5.regional_task import RegionalTask
    from r5py.r5.trip_planner import TripPlanner
    if r5py.__version__ != '1.1.7': raise RuntimeError('Adapter requires r5py 1.1.7')
    jar = ROOT/'cache/runtime/r5py/r5-v7.5.1-r5py-all.jar'
    if fingerprint(jar)['sha256'] != 'd50be106cadd7b636cfc0e209052767d7df570629f79fdf98ecd5cf5d2d89be7':
        raise RuntimeError('Adapter requires the verified R5 7.5.1-r5py jar')
    derived = ROOT/'data/gtfs/skane-20261011-r0.zip'
    derived.parent.mkdir(parents=True,exist_ok=True)
    derivation = routing_feed(inputs['gtfs'],derived)
    stops,_ = gtfs_tables(inputs['gtfs'])
    origin, destination = select_station(stops,'Lomma station'), select_station(stops,'Lund C')
    started = time.perf_counter()
    network = r5py.TransportNetwork(inputs['osm'],[derived])
    build_seconds = time.perf_counter()-started
    request = RegionalTask(network, departure=grid[0], departure_time_window=timedelta(hours=1),
                          transport_modes=[r5py.TransportMode.WALK,r5py.TransportMode.TRANSIT],
                          speed_walking=3.6, max_time=timedelta(seconds=2700),
                          max_time_walking=timedelta(seconds=900), max_public_transport_rides=2)
    task = request._regional_task
    task.fromLat,task.fromLon = origin['lat'],origin['lon']
    task.toLat,task.toLon = destination['lat'],destination['lon']
    planner = TripPlanner(network,request)
    layer = network._transport_network.transitLayer
    ids = {i:str(layer.stopIdForIndex.get(i)).split(':',1)[1] for i in range(layer.getStopCount())}
    indices = {v:k for k,v in ids.items()}
    def walking(paths_by_mode):
        return {ids[int(stop)]:round(leg.travel_time.total_seconds())
                for paths in paths_by_mode.values() for stop,leg in paths.items()
                if leg.travel_time.total_seconds() <= PARAMETERS['max_walk_seconds']}
    access = walking(planner._transit_access_paths)
    egress = walking(planner._transit_egress_paths)
    transfer_cache = {}
    def transfers(stop):
        if stop not in transfer_cache:
            values = {stop:0}
            if stop in indices:
                pairs = layer.streetTransfers.get(indices[stop])
                for pos in range(0,pairs.size(),2):
                    duration = int(pairs.get(pos+1)/(PARAMETERS['walk_speed_kmh']/3.6*1000))
                    if duration <= PARAMETERS['max_walk_seconds']:
                        values[ids[int(pairs.get(pos))]] = duration
            transfer_cache[stop] = values
        return transfer_cache[stop]
    midnight = grid[0].replace(hour=0,minute=0,second=0,microsecond=0)
    start_seconds = [t.hour*3600+t.minute*60 for t in grid]
    trips = load_trips(derived,grid[0],start_seconds[0],start_seconds[-1]+2700)
    sweep = ScheduleSweep(trips,access,egress,transfers)
    started = time.perf_counter()
    observations = []
    for instant, seconds in zip(grid,start_seconds):
        row = dict(start=instant.isoformat(),start_seconds=seconds,**sweep.at(seconds))
        if row['duration_seconds'] is not None:
            row['arrival'] = (midnight+timedelta(seconds=row['arrival_seconds'])).isoformat()
            row['status'] = 'REACHABLE'
        observations.append(row)
    sweep_seconds = time.perf_counter()-started

    # Raw R5 states are inspected, avoiding r5py's one-state-per-departure dict
    # and shared/mutable access/egress legs. The independent search above is
    # authoritative for the explicitly enforced walking and duration budgets.
    java_map = jpype.JClass('java.util.HashMap')
    int_map = jpype.JClass('gnu.trove.map.hash.TIntIntHashMap')
    walk = jpype.JClass('com.conveyal.r5.api.util.LegMode').WALK
    def times(values):
        inner = int_map()
        for stop,seconds in values.items(): inner.put(indices[stop],seconds)
        outer = java_map(); outer.put(walk,inner)
        return outer
    access_java,egress_java = times(access),times(egress)
    router_class = jpype.JClass('com.conveyal.r5.profile.McRaptorSuboptimalPathProfileRouter')
    rng_class = jpype.JClass('org.apache.commons.math3.random.MersenneTwister')
    rng_field = router_class.class_.getDeclaredField('mersenneTwister'); rng_field.setAccessible(True)
    generator = router_class.class_.getDeclaredMethod('generateDepartureTimesToSample',
                      jpype.JClass('com.conveyal.r5.profile.ProfileRequest').class_)
    generator.setAccessible(True)
    seed = next(s for s in range(1000) if (lambda r:r.nextInt(2)==1 and r.nextInt(2)==1)(rng_class(s)))
    def router(req):
        return router_class(network,req,access_java,egress_java,
                            lambda _:jpype.JClass('com.conveyal.r5.profile.SuboptimalDominatingList')(
                                max(req.suboptimalMinutes,0)),None,True)
    def state_result(state, ready):
        chain = []
        current = state
        while current is not None:
            chain.append(current); current=current.back
        chain.reverse()
        walking_seconds = int(chain[0].time)-ready
        rides = []
        for previous,current in zip(chain,chain[1:]):
            if current.pattern == -1:
                walking_seconds += int(current.time-previous.time)
            else:
                pattern = layer.tripPatterns.get(current.pattern)
                info = layer.routes.get(pattern.routeIndex)
                rides.append(dict(route_id=str(info.route_id),line=str(info.route_short_name),
                    mode=str(info.route_type),start_stop=ids[int(previous.stop)],end_stop=ids[int(current.stop)],
                    departure_seconds=int(current.boardTime),arrival_seconds=int(current.time)))
        duration = int(state.time)-ready+PARAMETERS['egress_slack_seconds']
        if not rides or walking_seconds>900 or duration>2700: return None
        return dict(duration_seconds=duration,walking_seconds=walking_seconds,rides=rides)
    comparisons = []
    for row,seconds in zip(observations,start_seconds):
        req = copy.copy(request)._regional_task
        req.fromTime,req.toTime,req.monteCarloDraws = seconds-1,seconds+1,1
        engine = router(req)
        rng_field.set(engine,rng_class(seed))
        selected = [int(t) for t in generator.invoke(engine,req)]
        if selected != [seconds]: raise RuntimeError('Exact-minute adapter failed its start-time check')
        rng_field.set(engine,rng_class(seed))
        engine.route()
        keys = sorted(int(k) for k in engine.finalStatesByDepartureTime.keys())
        if keys != [seconds]: raise RuntimeError('Router did not evaluate requested exact minute')
        choices = [state_result(s,seconds) for s in engine.finalStatesByDepartureTime.get(seconds)]
        finite = [c for c in choices if c is not None]
        best = min(finite,key=lambda c:c['duration_seconds']) if finite else None
        value = best['duration_seconds'] if best else None
        comparisons.append(dict(start=row['start'],evaluated_seconds=keys,raw_r5_seconds=value,
                                explicit_seconds=row['duration_seconds'],equal=value==row['duration_seconds']))
    native = copy.copy(request)._regional_task
    # Do not use 60 draws for a shorter CLI window: R5 can otherwise create
    # zero-width random-walk steps. R5 also explicitly rejects 200 draws.
    native.fromTime,native.toTime,native.monteCarloDraws = start_seconds[0],start_seconds[-1]+60,min(len(grid),199)
    engine = router(native)
    selected = [int(t) for t in generator.invoke(engine,native)]
    # generator mutates its RNG; reconstruct before the actual experiment.
    engine = router(native); engine.route()
    native_keys = sorted(int(k) for k in engine.finalStatesByDepartureTime.keys())
    matrix_comparison = None
    import geopandas as gpd
    from shapely.geometry import Point
    def frame(station):
        return gpd.GeoDataFrame({'id':[station['id']]},geometry=[Point(station['lon'],station['lat'])],crs='EPSG:4326')
    matrix = r5py.TravelTimeMatrix(network,frame(origin),frame(destination),departure=grid[0],
                 departure_time_window=timedelta(minutes=len(grid)),percentiles=[50,90,99],
                 transport_modes=[r5py.TransportMode.WALK,r5py.TransportMode.TRANSIT],
                 speed_walking=3.6,max_time=timedelta(minutes=45),max_time_walking=timedelta(minutes=15),
                 max_public_transport_rides=2)
    import pandas as pd
    matrix_comparison = json.loads(pd.DataFrame(matrix).to_json(orient='records'))
    minute_matrices = []
    matrix_warnings = set()
    for instant,row in zip(grid,observations):
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always')
            minute_matrix = r5py.TravelTimeMatrix(network,frame(origin),frame(destination),departure=instant,
                 departure_time_window=timedelta(minutes=1),percentiles=[50],
                 transport_modes=[r5py.TransportMode.WALK,r5py.TransportMode.TRANSIT],
                 speed_walking=3.6,max_time=timedelta(minutes=45),max_time_walking=timedelta(minutes=15),
                 max_public_transport_rides=2)
            matrix_warnings.update(str(w.message) for w in captured)
        result_minutes = json.loads(pd.DataFrame(minute_matrix).to_json(orient='records'))[0]['travel_time']
        expected = ((row['duration_seconds']-60)//60) if row['duration_seconds'] is not None else None
        minute_matrices.append(dict(start=instant.isoformat(),r5_matrix_minutes=result_minutes,
                                     explicit_minus_egress_floor_minutes=expected,equal=result_minutes==expected))
    frozen = dict(PARAMETERS,origin=origin,destination=destination,
                  r5_suboptimal_minutes=int(task.suboptimalMinutes),
                  window_start=args.start,window_end_inclusive=args.end,
                  sweep='exhaustive_one_or_two_rides_on_R5_walking_links',
                  exact_r5_adapter_seed=seed, exact_r5_interval_seconds=2)
    frozen['native_diagnostic_draws'] = int(native.monteCarloDraws)
    hashes = dict(osm=fingerprint(inputs['osm']),gtfs_original=fingerprint(inputs['gtfs']),
                  gtfs_derived=fingerprint(derived),r5_jar=fingerprint(jar),
                  code={name:fingerprint(ROOT/'scripts'/name) for name in
                        ('analyze_t90.py','t90_core.py','schedule_sweep.py','smoke_helpers.py')})
    if initial_hashes != dict(osm=hashes['osm'],gtfs=hashes['gtfs_original']):
        raise RuntimeError('Input changed during the experiment; no result published')
    versions = dict(python=sys.version.split()[0],r5py=r5py.__version__,r5='7.5.1-r5py',
                    java=str(jpype.JClass('java.lang.System').getProperty('java.version')))
    report = dict(metadata=metadata(hashes,versions,grid,frozen),derivation=derivation,
                  statistics=statistics([r['duration_seconds'] for r in observations]),
                  observations=observations,combinations=combinations(observations),
                  components=component_statistics(observations),
                  verification=dict(exact_minute_comparisons=comparisons,
                    equal_count=sum(c['equal'] for c in comparisons),
                    native_generated_seconds=selected,native_evaluated_seconds=native_keys,
                    native_exact_grid=native_keys==start_seconds,
                    native_grid_minute_matches=sum(k in start_seconds for k in native_keys),
                    r5_travel_time_matrix=matrix_comparison,
                    explicit_one_minute_matrices=minute_matrices,
                    minute_matrix_equal_count=sum(c['equal'] for c in minute_matrices),
                    minute_matrix_warnings=sorted(matrix_warnings)),
                  timing=dict(network_seconds=build_seconds,sweep_seconds=sweep_seconds),
                  limitations=['bounded regional street extract','route_type 1501 excluded',
                               'no operational delay/cancellation observations'])
    atomic_json(args.output,report)
    print('RESULT_WRITTEN_ATOMICALLY',flush=True)


def main():
    args = parser().parse_args()
    grid = minute_grid(args.date,args.start,args.end,args.timezone)
    args.output = args.output.resolve()
    # This CLI only emits generated artifacts in the ignored output directory.
    if not args.output.is_relative_to((ROOT/'outputs').resolve()):
        raise ValueError('Generated output must be under the ignored worktree outputs directory')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.worker:
        worker(args,grid)
    else:
        log = args.output.with_suffix('.worker.log')
        work_result = args.output.with_suffix('.worker.json')
        command = [sys.executable,'-B',str(Path(__file__).resolve()),'--worker','--config',str(args.config.resolve()),
                   '--date',args.date,'--start',args.start,'--end',args.end,'--timezone',args.timezone,
                   '--output',str(work_result)]
        # Remove only our previous temporary result, so a failed worker cannot
        # be mistaken for a new success. Preserve the previous final result.
        work_result.unlink(missing_ok=True)
        with log.open('w',encoding='utf-8') as stream:
            job = subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,check=False)
        if not work_result.is_file():
            raise RuntimeError(f'Routing worker failed (exit {job.returncode}); inspect {log}')
        report = json.loads(work_result.read_text(encoding='utf-8'))
        report['worker'] = dict(exit_code=job.returncode,log=str(log),
                               jpype_shutdown_error='PyExceptionProxy' in log.read_text(encoding='utf-8'),
                               result_status='VALID' if job.returncode==0 else 'DIAGNOSTIC')
        atomic_json(args.output,report)
        print(json.dumps(dict(statistics=report['statistics'],combinations=report['combinations'],
                              components=report['components'],
                              verification_equal_count=report['verification']['equal_count'],
                              matrix_minute_equal_count=report['verification']['minute_matrix_equal_count'],
                              native_exact_grid=report['verification']['native_exact_grid'],
                              r5_matrix=report['verification']['r5_travel_time_matrix'],
                              worker=report['worker']),indent=2))
        if job.returncode: raise RuntimeError('Worker exited unsuccessfully; recorded result is diagnostic only')


if __name__ == '__main__':
    main()
