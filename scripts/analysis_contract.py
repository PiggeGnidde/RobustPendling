"""Pure, versioned A-to-B contract helpers; no JVM or geospatial imports."""
from collections import Counter
from datetime import datetime, time, timedelta
import hashlib
import json
import math
from zoneinfo import ZoneInfo
from t90_core import minute_grid, statistics

SCHEMA_VERSION = '2.0'
# complete_ways adds distant way nodes. The total object bbox cannot be used
# as coverage. Bind the actual extraction rectangle to its verified bytes.
VERIFIED_AREAS = {
    '47942e06ea6c96c8893933f71f448f7e1deac9d906c216a16c60a414db521b9d':
    dict(bbox=[12.95,55.60,13.30,55.80], source='prepare_lomma_lund.ps1 complete_ways extraction rectangle')}


def point(lat,lon,name=''):
    if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in (lat,lon)):
        raise ValueError('Coordinates must be finite numbers')
    if not -90<=lat<=90 or not -180<=lon<=180:
        raise ValueError('Coordinates outside WGS84 ranges')
    return dict(lat=float(lat),lon=float(lon),name=name)


def request_grid(day,start,window_minutes,timezone):
    if not isinstance(window_minutes,int) or isinstance(window_minutes,bool) or not 1<=window_minutes<=1440:
        raise ValueError('Window length must be 1 to 1440 whole minutes')
    if time.fromisoformat(start).tzinfo is not None:
        raise ValueError('Use a local clock time and a separate IANA timezone')
    first=datetime.fromisoformat(f'{day}T{start}').replace(tzinfo=ZoneInfo(timezone))
    if first.second or first.microsecond:
        raise ValueError('Start must be an exact minute')
    # Reuse the validated local-minute grid, including DST gap/fold rejection.
    last=first+timedelta(minutes=window_minutes-1)
    if last.date()!=first.date():
        raise ValueError('Window crossing local midnight is not yet supported')
    return minute_grid(day,start,last.time().isoformat(),timezone)


def area_check(origin,destination,osm_hash,configured=None):
    area=configured or VERIFIED_AREAS.get(osm_hash)
    if not area or (configured and configured.get('osm_sha256')!=osm_hash):
        return dict(status='NETWORK_AREA_UNVERIFIED',area=None,outside=[])
    bbox=area.get('bbox')
    if not isinstance(bbox,(list,tuple)) or len(bbox)!=4 or not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in bbox) or not (-180<=bbox[0]<bbox[2]<=180 and -90<=bbox[1]<bbox[3]<=90):
        raise ValueError('Invalid network coverage bbox')
    outside=[label for label,p in [('from',origin),('to',destination)]
             if not (bbox[0]<=p['lon']<=bbox[2] and bbox[1]<=p['lat']<=bbox[3])]
    return dict(status='OUTSIDE_NETWORK_AREA' if outside else 'OK',area=area,outside=outside)


def mode_name(value):
    text=str(value).strip().upper().removeprefix('TRANSPORTMODE.')
    if not text.isdecimal(): return text
    code=int(text)
    if 100<=code<200 or code==2:return 'RAIL'
    if 700<=code<800 or code in (3,11):return 'BUS'
    if 900<=code<1000 or code==0:return 'TRAM'
    if 400<=code<500 or code==1:return 'SUBWAY'
    if 1000<=code<1100 or code==4:return 'FERRY'
    return f'GTFS_{code}'


def family(rides):
    sequence=[]
    for r in rides:
        mode=mode_name(r['mode'])
        if mode=='WALK':continue
        route=str(r.get('route_id') or '').strip()
        line=str(r.get('line') or '').strip()
        sequence.append(dict(mode=mode,route_id=route or None,line=line or None,
                             start_stop=str(r.get('start_stop') or '').strip(),
                             end_stop=str(r.get('end_stop') or '').strip()))
    key=[(r['mode'],r['route_id'] or r['line'],r['start_stop'],r['end_stop']) for r in sequence]
    digest=hashlib.sha256(json.dumps(key,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    return dict(id='rf_'+digest,sequence=sequence,pure_walk=not sequence)


def structural_metrics(observations):
    stats=statistics([r['duration_seconds'] for r in observations])
    def difference(high,low):
        return 'UNREACHABLE' if isinstance(high,str) or isinstance(low,str) else high-low
    counts=Counter(family(r.get('rides',[]))['id'] for r in observations if r['duration_seconds'] is not None)
    reachable=sum(counts.values())
    dominant=min(counts,key=lambda k:(-counts[k],k)) if counts else None
    penalty=dict(seconds=0,from_start=None,to_start=None)
    transitions=Counter()
    for previous,current in zip(observations,observations[1:]):
        a,b=previous['duration_seconds'],current['duration_seconds']
        if a is None or b is None:
            kind='reachable_to_unreachable' if a is not None else ('unreachable_to_reachable' if b is not None else 'both_unreachable')
            transitions[kind]+=1
            if a is not None and penalty['seconds']!='UNREACHABLE':
                penalty=dict(seconds='UNREACHABLE',from_start=previous['start'],to_start=current['start'])
        elif penalty['seconds']!='UNREACHABLE' and b-a>penalty['seconds']:
            penalty=dict(seconds=b-a,from_start=previous['start'],to_start=current['start'])
    return dict(**stats,buffer_90=difference(stats['percentiles_seconds']['T90'],stats['percentiles_seconds']['T50']),
                buffer_99=difference(stats['percentiles_seconds']['T99'],stats['percentiles_seconds']['T50']),
                full_range=difference(stats['maximum_seconds'],stats['minimum_seconds']),
                dominant_route_family=dominant,dominant_route_share=counts[dominant]/reachable if dominant else 0,
                dominant_route_share_all_minutes=counts[dominant]/len(observations) if dominant else 0,
                distinct_selected_route_families=len(counts),
                transfer_count_distribution={str(k):v for k,v in sorted(Counter(r.get('transfers',0)
                    for r in observations if r['duration_seconds'] is not None).items())},
                departure_sensitivity=penalty,unreachable_transitions=dict(transitions))


def representatives(observations):
    stats=statistics([r['duration_seconds'] for r in observations])
    values=dict(min=stats['minimum_seconds'],**stats['percentiles_seconds'],max=stats['maximum_seconds'])
    chosen={}
    for role,value in values.items():
        index=next(i for i,r in enumerate(observations)
                   if (r['duration_seconds'] if r['duration_seconds'] is not None else 'UNREACHABLE')==value)
        chosen.setdefault(index,[]).append(role)
    return [dict(index=i,start=observations[i]['start'],percentile_roles=roles,
                 status=observations[i].get('status','UNREACHABLE' if observations[i]['duration_seconds'] is None else 'REACHABLE'))
            for i,roles in sorted(chosen.items())]


def validate_geojson(collection):
    if collection.get('type')!='FeatureCollection' or not isinstance(collection.get('features'),list):
        raise ValueError('Expected GeoJSON FeatureCollection')
    for f in collection['features']:
        if f.get('type')!='Feature' or not isinstance(f.get('properties'),dict):raise ValueError('Invalid Feature')
        g=f.get('geometry') or {}
        if g.get('type')=='LineString':lines=[g.get('coordinates')]
        elif g.get('type')=='MultiLineString':lines=g.get('coordinates')
        else:raise ValueError('Segment geometry must be LineString or MultiLineString')
        if not lines:raise ValueError('Empty segment geometry')
        for line in lines:
            if not line or len(line)<2:raise ValueError('Segment has fewer than two positions')
            for c in line:
                if len(c)!=2 or not all(math.isfinite(v) for v in c) or not (-180<=c[0]<=180 and -90<=c[1]<=90):
                    raise ValueError('Invalid EPSG:4326 longitude/latitude')
    json.dumps(collection,allow_nan=False)
    return collection
