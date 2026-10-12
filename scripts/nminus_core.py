"""Deterministic single-trip cancellation contract, without JVM imports."""
from contextlib import contextmanager
import math
from analysis_contract import connect_walk_geometry

HORIZON_SECONDS = 7200
INFORMATION = 'At the failed leg scheduled departure, already at its boarding stop'


def normalize_walk_geometry(geometry,start,end):
    """Preserve street pieces and disclose every >1 m connecting gap."""
    def distance(a,b):return math.hypot((a[0]-b[0])*111320*math.cos(math.radians(a[1])),(a[1]-b[1])*111320)
    if geometry['type']=='Point':geometry=dict(type='LineString',coordinates=[geometry['coordinates'],geometry['coordinates']])
    internal=[]
    if geometry['type']=='MultiLineString':
        remaining=[list(line) for line in geometry['coordinates'] if line]
        coordinates=[];cursor=start
        while remaining:
            index=min(range(len(remaining)),key=lambda i:min(distance(cursor,remaining[i][0]),distance(cursor,remaining[i][-1])))
            line=remaining.pop(index)
            if distance(cursor,line[-1])<distance(cursor,line[0]):line.reverse()
            if coordinates and distance(coordinates[-1],line[0])>1:internal.append([list(coordinates[-1]),list(line[0])])
            coordinates.extend(line);cursor=line[-1]
        geometry=dict(type='LineString',coordinates=coordinates)
    if not geometry.get('coordinates'):
        length=distance(start,end)
        return dict(type='LineString',coordinates=[list(start),list(end)],approximate_connections=[[list(start),list(end)]]),dict(start=0,end=0,internal=max(length,1.01))
    connected,lengths=connect_walk_geometry(geometry,start,end)
    if internal:
        connected['approximate_connections']=internal
        lengths['internal']=max(distance(a,b) for a,b in internal)
    return connected,lengths


@contextmanager
def exclude_schedule(schedule, inactive_code):
    """Exact R5 TripSchedule calendar override, restored even on exceptions."""
    original=int(schedule.serviceCode)
    try:
        schedule.serviceCode=inactive_code
        yield
    finally:
        schedule.serviceCode=original
        if int(schedule.serviceCode)!=original:raise RuntimeError('Trip restoration failed')


def remaining_resources(completed_walk,completed_rides,parameters):
    walk=parameters['max_walk_seconds']-completed_walk
    rides=parameters['max_rides']-completed_rides
    if walk<0 or rides<0:raise ValueError('Completed prefix exceeds baseline resources')
    return dict(parameters,max_walk_seconds=walk,max_rides=rides,max_time_seconds=HORIZON_SECONDS)


def summarize(rows):
    applicable=[r for r in rows if r['status']!='NOT_APPLICABLE']
    reachable=[r for r in applicable if r['status']=='REACHABLE']
    def quantiles(key,ps):
        values=sorted(r[key] for r in reachable)
        return {f'P{p}':values[math.ceil(p*len(values)/100)-1] if values else None for p in ps}
    total=quantiles('total_seconds',(50,90,99))
    return dict(applicable_count=len(applicable),not_applicable_count=len(rows)-len(applicable),
        reachable_count=len(reachable),unreachable_count=len(applicable)-len(reachable),
        coverage=len(reachable)/len(applicable) if applicable else None,
        conditional=len(reachable)<len(applicable),
        total_percentiles_seconds={k.replace('P','T'):v for k,v in total.items()},
        extra_percentiles_seconds=quantiles('extra_seconds',(50,90)),
        maximum_extra_seconds=max((r['extra_seconds'] for r in reachable),default=None),
        percentile_population='reachable applicable scenarios; nearest rank; equal minute weights')


def state_resources(state,ready):
    walking=0;rides=0;current=state
    while current is not None:
        previous=current.back
        if current.pattern>=0:rides+=1
        elif previous is None:walking+=int(current.time)-ready
        else:walking+=int(current.time)-int(previous.time)
        current=previous
    return walking,rides


def pareto_add(state,states,ready,walk_cap,ride_cap,permissions):
    """Resource/permission checks precede dominance, including transfer states."""
    if state.pattern>=0:
        pickup,dropoff=permissions[int(state.pattern)]
        allowed={'SCHEDULED','COORDINATE_WITH_DRIVER'}
        if pickup[int(state.boardStopPosition)] not in allowed or dropoff[int(state.alightStopPosition)] not in allowed:return False
    walk,rides=state_resources(state,ready)
    if walk>walk_cap or rides>ride_cap:return False
    key=(int(state.time),walk,rides)
    def resource(s):
        w,r=state_resources(s,ready)
        return int(s.time),w,r
    if any(all(a<=b for a,b in zip(resource(s),key)) for s in states):return False
    states[:]=[s for s in states if not all(a<=b for a,b in zip(key,resource(s)))]
    states.append(state)
    return True
