"""Independent contract/timeline/geometry checks for every published scenario."""
from datetime import datetime
import hashlib
import json
from analysis_contract import itinerary_timing,validate_geojson
from nminus_core import HORIZON_SECONDS,summarize,remaining_resources
from t90_core import PARAMETERS
from planner_core import routing_parameters,combined_nminus


def validate_result(result,base):
    parameters=routing_parameters(base.get('metadata',{}).get('parameters',{}).get('max_rides',2))
    if 'canonical_sha256' in result:
        canonical={k:v for k,v in result.items() if k not in ('canonical_sha256','analysis_id','source')}
        checksum=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        if checksum!=result['canonical_sha256']:raise ValueError('N−1 result checksum mismatch')
    if result['status']!='OK' or result['base_metrics']!=base['metrics'] or result['minute_observations']!=base['minute_observations']:
        raise ValueError('Baseline differs')
    checked=0;unreachable=0;not_applicable=0
    if result.get('schema_version')=='nminus-1.1' and set(result['scenarios'])!={str(n) for n in range(1,parameters['max_rides']+1)}:
        raise ValueError('Missing configured leg scenario')
    for number,rows in result['scenarios'].items():
        if len(rows)!=len(base['minute_observations']):raise ValueError('Minute silently omitted')
        for index,(row,obs) in enumerate(zip(rows,base['minute_observations'])):
            if row['index']!=index or row['start']!=obs['start']:raise ValueError('Original start not preserved')
            baseline=result['base_itineraries'][index]
            positions=[i for i,s in enumerate(baseline or []) if s['mode']!='WALK']
            applicable=len(positions)>=int(number)
            if row['status']=='NOT_APPLICABLE':
                if applicable:raise ValueError('Applicable minute disguised as not applicable')
                not_applicable+=1;continue
            if not applicable:raise ValueError('Nonexistent failed leg')
            position=positions[int(number)-1]
            if 'remaining_parameters' in row:
                walked=sum(leg['walking_seconds'] for leg in baseline[:position])
                if row['remaining_parameters']!=remaining_resources(walked,int(number)-1,parameters):raise ValueError('Remaining resources differ')
            if row['completed']['segments']!=baseline[:position]:raise ValueError('Completed route changed')
            if row['failed_leg']!=obs['rides'][int(number)-1]:raise ValueError('Wrong cancelled trip')
            notify=row['notification'];failed=row['failed_leg'];prefix=row['completed']['segments']
            if notify['stop_id']!=failed['start_stop'] or notify['time']!=baseline[position]['departure']:raise ValueError('Notification at wrong place/time')
            start=datetime.fromisoformat(obs['start']);instant=datetime.fromisoformat(notify['time'])
            elapsed=(instant-start).total_seconds()
            if elapsed!=row['completed']['elapsed_seconds']:raise ValueError('Elapsed time reset')
            if not itinerary_timing(prefix,obs['start'])['valid']:raise ValueError('Impossible completed itinerary')
            wait=(instant-datetime.fromisoformat(prefix[-1]['arrival'])).total_seconds()
            if wait<0 or wait!=row['completed']['wait_before_notification_seconds']:raise ValueError('Notification before traveller arrives')
            if (datetime.fromisoformat(row['search_end'])-instant).total_seconds()!=HORIZON_SECONDS:raise ValueError('Horizon differs')
            reserve=row['reserve'];segments=reserve['segments']
            if row['status']=='UNREACHABLE':
                unreachable+=1
                if segments or reserve['duration_seconds'] is not None or row['total_seconds'] is not None or row['extra_seconds'] is not None or row['raw_r5_seconds'] is not None:raise ValueError('Invented unreachable travel time')
            elif row['status']=='REACHABLE':
                timing=itinerary_timing(segments,notify['time'])
                if not timing['valid'] or timing['duration_seconds']!=reserve['duration_seconds']:raise ValueError('Impossible reserve boarding/timing')
                if timing['duration_seconds']>HORIZON_SECONDS:raise ValueError('Arrival after horizon')
                total=(datetime.fromisoformat(segments[-1]['arrival'])-start).total_seconds()
                if total!=row['total_seconds'] or total-obs['duration_seconds']!=row['extra_seconds']:raise ValueError('Wrong total or extra')
                rides=[s for s in segments if s['mode']!='WALK']
                if any(s['trip_id']==failed['trip_id'] for s in rides):raise ValueError('Cancelled trip reused at another stop')
                walk=sum(s['walking_seconds'] for s in prefix+segments)
                if walk>parameters['max_walk_seconds'] or len(rides)+int(number)-1>parameters['max_rides']:raise ValueError('Resource budget reset')
                if row['raw_r5_seconds']!=reserve['duration_seconds']:raise ValueError('R5/sweep mismatch')
                checked+=1
            else:raise ValueError('Unknown status')
            expected=[]
            for phase,legs in [('completed',prefix),('reserve',segments)]:
                for i,leg in enumerate(legs):
                    props={k:v for k,v in leg.items() if k!='geometry'}
                    props.update(index=index,leg_number=int(number),phase=phase,segment=i)
                    expected.append(dict(type='Feature',geometry=leg['geometry'],properties=props))
            validate_geojson(row['geojson'])
            if row['geojson']['features']!=expected:raise ValueError('Map differs from itinerary')
        if result['summaries'][number]!=summarize(rows):raise ValueError('Wrong summary population/quantiles')
    if 'combined' in result and result['combined']!=combined_nminus(base['minute_observations'],result['scenarios']):raise ValueError('Wrong combined N−1 envelope')
    return dict(reachable_checked=checked,unreachable_checked=unreachable,not_applicable_checked=not_applicable,
                prefix_preserved=True,exact_failed_trip_absent=True,boarding_and_horizon_valid=True,geojson_matches_segments=True)
