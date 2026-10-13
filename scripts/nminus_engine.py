"""N−1 on immutable GTFS + R5 street links, exact R5 exclusion and checks."""
import copy
from datetime import datetime,timedelta
import hashlib
import json
from zoneinfo import ZoneInfo
from analysis_contract import family,mode_name,connect_walk_geometry,validate_geojson
from schedule_sweep import ScheduleSweep,load_trips
from t90_core import PARAMETERS
from nminus_core import HORIZON_SECONDS,INFORMATION,exclude_schedule,remaining_resources,summarize,pareto_add,normalize_walk_geometry
from transit_inputs import ROOT,fingerprint
from planner_core import routing_parameters,combined_nminus
from walking_links import ensure_walking_links


def baseline_observation(obs):
    """Reuse the frozen exact-minute optimum, excluding presentation fields."""
    if obs['duration_seconds'] is None:
        return dict(duration_seconds=None,status='UNREACHABLE',rides=[])
    return {key:copy.deepcopy(obs[key]) for key in (
        'duration_seconds','walking_seconds','waiting_seconds','fixed_slack_seconds',
        'transfers','arrival_seconds','rides')}


def continuation_key(failed,walked,completed_rides):
    """Within one frozen feed/day/destination/parameter set, not per start minute."""
    return (failed['start_stop'],failed['departure_seconds'],failed['trip_id'],walked,completed_rides)


class NMinusEngine:
    def __init__(self,network,derived,stops,hashes):
        import jpype
        self.jpype=jpype;self.network=network;self.layer=network._transport_network.transitLayer
        self.derived=derived;self.hashes=hashes
        self.stops={s['stop_id']:s for s in stops}
        self.coords={k:(float(s['stop_lon']),float(s['stop_lat'])) for k,s in self.stops.items()}
        self.ids={i:str(self.layer.stopIdForIndex.get(i)).split(':',1)[1] for i in range(self.layer.getStopCount())}
        self.indices={v:k for k,v in self.ids.items()};self.locations={};self.permissions={}
        for pi,p in enumerate(self.layer.tripPatterns):
            self.permissions[pi]=([str(v) for v in p.pickups],[str(v) for v in p.dropoffs])
            for ti,t in enumerate(p.tripSchedules):
                if t.headwaySeconds is not None:raise ValueError('Frequency trip identity unsupported')
                scoped=str(t.tripId);tid=scoped.split(':',1)[1]
                if tid in self.locations:raise ValueError('Ambiguous trip ID across network feeds/patterns')
                self.locations[tid]=(pi,ti,t,scoped)
        self.inactive=max(int(v[2].serviceCode) for v in self.locations.values())+1
        self.calendar_original={tid:int(v[2].serviceCode) for tid,v in self.locations.items()}
        self.transfers_cache={};self.geometry_cache={};self.parameters=dict(PARAMETERS)

    def calendar_check(self):
        if any(int(v[2].serviceCode)!=self.calendar_original[k] for k,v in self.locations.items()):raise RuntimeError('Scenario contaminated network calendar')

    def transfers(self,stop):
        key=(stop,self.parameters['walk_speed_kmh'],self.parameters['max_walk_seconds'])
        if key not in self.transfers_cache:
            values={stop:0}
            pairs=self.layer.streetTransfers.get(self.indices[stop])
            for pos in range(0,pairs.size(),2):
                seconds=int(pairs.get(pos+1)/(self.parameters['walk_speed_kmh']/3.6*1000))
                if seconds<=self.parameters['max_walk_seconds']:values[self.ids[int(pairs.get(pos))]]=seconds
            self.transfers_cache[key]=values
        return self.transfers_cache[key]

    def java_times(self,values):
        jp=self.jpype;inner=jp.JClass('gnu.trove.map.hash.TIntIntHashMap')()
        for stop,seconds in values.items():inner.put(self.indices[stop],seconds)
        outer=jp.JClass('java.util.HashMap')()
        outer.put(jp.JClass('com.conveyal.r5.api.util.LegMode').WALK,inner)
        return outer

    def raw(self,request,ready,access,egress,parameters,direct,completed_rides,failed=None):
        jp=self.jpype;req=copy.copy(request)._regional_task
        req.fromTime,req.toTime,req.monteCarloDraws=ready-1,ready+1,1
        req.maxRides=parameters['max_rides'];req.maxTripDurationMinutes=(parameters['max_time_seconds']+59)//60
        # Disable target-time pruning: earliest arrival can consume too much walking.
        req.suboptimalMinutes=(HORIZON_SECONDS//60)+1
        def factory(_):
            states=[]
            def add(state):return pareto_add(state,states,ready,parameters['max_walk_seconds'],parameters['max_rides'],self.permissions)
            def get():
                values=jp.JClass('java.util.ArrayList')()
                for state in states:values.add(state)
                return values
            return jp.JProxy('com.conveyal.r5.profile.DominatingList',dict=dict(add=add,getNonDominatedStates=get))
        router=jp.JClass('com.conveyal.r5.profile.McRaptorSuboptimalPathProfileRouter')
        def search():
            engine=router(self.network,req,self.java_times(access),self.java_times(egress),factory,None,True)
            field=router.class_.getDeclaredField('mersenneTwister');field.setAccessible(True)
            field.set(engine,jp.JClass('org.apache.commons.math3.random.MersenneTwister')(0))
            engine.route()
            keys=sorted(int(k) for k in engine.finalStatesByDepartureTime.keys())
            if keys not in ([ready],[]):raise RuntimeError('R5 did not evaluate exact notification second')
            candidates=[];states=engine.finalStatesByDepartureTime.get(ready)
            if states is not None:
                for state in states:
                    current=state
                    while current is not None:
                        if failed and current.pattern>=0:
                            trip=self.layer.tripPatterns.get(current.pattern).tripSchedules.get(current.trip)
                            if str(trip.tripId).split(':',1)[1]==failed:raise RuntimeError('R5 boarded cancelled trip at another stop')
                        current=current.back
                    value=int(state.time)-ready+60
                    if value<=parameters['max_time_seconds']:candidates.append(value)
            if direct is not None and direct<=parameters['max_walk_seconds']:
                value=direct+(60 if completed_rides else 0)
                if value<=parameters['max_time_seconds']:candidates.append(value)
            return min(candidates,default=None)
        if failed is None:return search()
        schedule=self.locations[failed][2]
        if self.layer.getActiveServicesForDate(req.date).get(self.inactive):raise RuntimeError('Exclusion code unexpectedly active')
        with exclude_schedule(schedule,self.inactive):return search()

    def walk_geometry(self,planner,a,b):
        from shapely.geometry import mapping
        from shapely import line_merge
        if a==b:return dict(type='LineString',coordinates=[list(self.coords[a]),list(self.coords[b])]),None
        key=(a,b)
        if key not in self.geometry_cache:
            leg=planner._transit_transfer_path(self.indices[a],self.indices[b])
            geometry=mapping(line_merge(leg.geometry) if leg.geometry.geom_type=='MultiLineString' else leg.geometry)
            self.geometry_cache[key]=normalize_walk_geometry(geometry,self.coords[a],self.coords[b])
        return self.geometry_cache[key]

    def segments(self,planner,row,ready,origin,destination,access_paths,egress_paths,access_stop=None):
        from shapely.geometry import mapping,MultiLineString
        from shapely import from_wkt,line_merge
        result=[];cursor=ready
        def add(mode,a,b,departure,arrival,geometry,connectors=None,ride=None,slack=0):
            nonlocal cursor
            leg=dict(mode=mode,start_stop=a,end_stop=b,
                start_stop_name=self.stops[a]['stop_name'] if a else origin['name'],
                end_stop_name=self.stops[b]['stop_name'] if b else destination['name'],
                departure=self.iso(departure),arrival=self.iso(arrival),
                travel_seconds=arrival-departure,walking_seconds=arrival-departure if mode=='WALK' else 0,
                wait_seconds=departure-cursor-slack,fixed_slack_seconds=slack,
                route_id=ride['route_id'] if ride else None,line=ride['line'] if ride else None,
                trip_id=ride['trip_id'] if ride else None,geometry=geometry,
                geometry_connectors_m=connectors,geometry_source='R5_street_path' if mode=='WALK' else 'R5_GTFS_hops')
            if leg['wait_seconds']<0:raise RuntimeError('Impossible segment timing')
            result.append(leg);cursor=arrival
        rides=row['rides']
        if not rides:
            if access_stop:
                geometry,connectors=normalize_walk_geometry(mapping(egress_paths[access_stop].geometry),self.coords[access_stop],(destination['lon'],destination['lat']))
            else:geometry,connectors=normalize_walk_geometry(mapping(planner.direct_paths[0].legs[0].geometry),(origin['lon'],origin['lat']),(destination['lon'],destination['lat']))
            slack=row.get('fixed_slack_seconds',0)
            add('WALK',access_stop,None,ready+slack,row['arrival_seconds'],geometry,connectors,slack=slack)
            return result
        previous=None
        for i,ride in enumerate(rides):
            a,b=ride['start_stop'],ride['end_stop']
            if i==0:
                if access_stop:
                    seconds=self.transfers(access_stop)[a];geometry,connectors=self.walk_geometry(planner,access_stop,a)
                else:
                    seconds=round(access_paths[a].travel_time.total_seconds())
                    geometry,connectors=normalize_walk_geometry(mapping(access_paths[a].geometry),(origin['lon'],origin['lat']),self.coords[a])
                add('WALK',access_stop,a,cursor,cursor+seconds,geometry,connectors)
            elif previous!=a:
                seconds=self.transfers(previous)[a];geometry,connectors=self.walk_geometry(planner,previous,a)
                add('WALK',previous,a,cursor,cursor+seconds,geometry,connectors)
            pi,_,_,_=self.locations[ride['trip_id']];pattern=self.layer.tripPatterns.get(pi)
            positions=[(x,y) for x in range(len(pattern.stops)) for y in range(x+1,len(pattern.stops))
                if self.ids[int(pattern.stops[x])]==a and self.ids[int(pattern.stops[y])]==b
                and int(self.locations[ride['trip_id']][2].departures[x])==ride['departure_seconds']
                and int(self.locations[ride['trip_id']][2].arrivals[y])==ride['arrival_seconds']]
            if len(positions)!=1:raise RuntimeError('Ambiguous boarding/alighting occurrence')
            x,y=positions[0];hops=list(pattern.getHopGeometries(self.layer))[x:y]
            geometry=mapping(line_merge(MultiLineString([from_wkt(str(h.toText())) for h in hops])))
            add(mode_name(ride['mode']),a,b,ride['departure_seconds'],ride['arrival_seconds'],geometry,ride=ride)
            previous=b
        seconds=round(egress_paths[previous].travel_time.total_seconds())
        geometry,connectors=normalize_walk_geometry(mapping(egress_paths[previous].geometry),self.coords[previous],(destination['lon'],destination['lat']))
        add('WALK',previous,None,cursor+60,cursor+60+seconds,geometry,connectors,slack=60)
        if cursor!=row['arrival_seconds']:raise RuntimeError('Geometry itinerary differs from search')
        return result

    def iso(self,seconds):return (self.midnight+timedelta(seconds=seconds)).astimezone(self.display_zone).isoformat()

    def analyze(self,report,baseline_only=False,validation=False):
        import r5py
        from r5py.r5.regional_task import RegionalTask
        from r5py.r5.trip_planner import TripPlanner
        validation=validation or baseline_only
        self.calendar_check()
        meta=report['metadata'];params=meta['parameters'];parameters=routing_parameters(params['max_rides'],params['max_time_seconds'],params['walk_speed_kmh'],params['max_walk_seconds']);origin=params['origin'];destination=params['destination']
        self.parameters=parameters
        ensure_walking_links(self.network,parameters)
        first=datetime.fromisoformat(meta['start_minutes'][0]);self.display_zone=first.tzinfo
        feed_first=first.astimezone(ZoneInfo(params['feed_timezone']));self.midnight=feed_first.replace(hour=0,minute=0,second=0,microsecond=0)
        observations=report['minute_observations'];earliest=observations[0]['start_seconds']
        has_transit=any(obs.get('rides') for obs in observations)
        latest=observations[-1]['start_seconds']+parameters['max_time_seconds']+(HORIZON_SECONDS if has_transit else 0)
        reference_offset=self.midnight.utcoffset() if has_transit else feed_first.utcoffset()
        if (self.midnight+timedelta(seconds=latest)).utcoffset()!=reference_offset or latest>=86400:
            raise ValueError('N−1 service-day/DST crossing not yet supported')
        trips=load_trips(self.derived,feed_first,earliest,latest)
        request=RegionalTask(self.network,departure=feed_first,departure_time_window=timedelta(minutes=1),
            transport_modes=[r5py.TransportMode.WALK,r5py.TransportMode.TRANSIT],speed_walking=parameters['walk_speed_kmh'],
            max_time=timedelta(seconds=HORIZON_SECONDS),max_time_walking=timedelta(seconds=parameters['max_walk_seconds']),max_public_transport_rides=parameters['max_rides'])
        req=request._regional_task;req.fromLat,req.fromLon=origin['lat'],origin['lon'];req.toLat,req.toLon=destination['lat'],destination['lon']
        planner=TripPlanner(self.network,request)
        access_paths={self.ids[int(k)]:v for k,v in planner._transit_access_paths[r5py.TransportMode.WALK].items()}
        egress_paths={self.ids[int(k)]:v for k,v in planner._transit_egress_paths[r5py.TransportMode.WALK].items()}
        access={k:round(v.travel_time.total_seconds()) for k,v in access_paths.items() if v.travel_time.total_seconds()<=parameters['max_walk_seconds']}
        egress={k:round(v.travel_time.total_seconds()) for k,v in egress_paths.items() if v.travel_time.total_seconds()<=parameters['max_walk_seconds']}
        direct=min((round(t.travel_time.total_seconds()) for t in planner.direct_paths),default=None)
        base_sweep=ScheduleSweep(trips,access,egress,self.transfers,parameters,direct_walk_seconds=direct)
        code={name:fingerprint(ROOT/'scripts'/name) for name in ('nminus_core.py','nminus_engine.py','schedule_sweep.py','r5_adapter.py','planner_core.py','walking_links.py')}
        scenarios={str(i):[] for i in range(1,parameters['max_rides']+1)};base_details=[];memo={};features=[];checks=[]
        for index,obs in enumerate(observations):
            base=baseline_observation(obs)
            if validation:
                if base_sweep.at(obs['start_seconds'])!=base:raise RuntimeError('Baseline sweep changed')
                baseline_raw=self.raw(request,obs['start_seconds'],access,egress,parameters,direct,0)
                if baseline_raw!=obs['duration_seconds']:raise RuntimeError('Baseline raw R5 mismatch')
            if baseline_only:continue
            if base['duration_seconds'] is None:
                base_details.append(None)
                for rows in scenarios.values():rows.append(dict(index=index,start=obs['start'],status='NOT_APPLICABLE',reason='BASE_UNREACHABLE'))
                continue
            base_segments=self.segments(planner,base,obs['start_seconds'],origin,destination,access_paths,egress_paths)
            base_details.append(base_segments)
            transit_positions=[i for i,s in enumerate(base_segments) if s['mode']!='WALK']
            for number,rows in scenarios.items():
                leg_number=int(number)
                if leg_number>len(transit_positions):
                    rows.append(dict(index=index,start=obs['start'],status='NOT_APPLICABLE',reason='NO_SUCH_TRANSIT_LEG'));continue
                position=transit_positions[leg_number-1];failed=base['rides'][leg_number-1]
                ready=failed['departure_seconds'];stop=failed['start_stop'];prefix=copy.deepcopy(base_segments[:position])
                walked=sum(s['walking_seconds'] for s in prefix);resources=remaining_resources(walked,leg_number-1,parameters)
                key=continuation_key(failed,walked,leg_number-1)
                if key not in memo:
                    eligible=[t for t in trips if t['id']!=failed['trip_id']]
                    continuation_access={k:v for k,v in self.transfers(stop).items() if v<=resources['max_walk_seconds']}
                    continuation_direct=egress.get(stop)
                    sweep=ScheduleSweep(eligible,continuation_access,egress,self.transfers,resources,direct_walk_seconds=continuation_direct if leg_number==1 else None)
                    reserve=sweep.at(ready)
                    if leg_number>1 and continuation_direct is not None and continuation_direct<=resources['max_walk_seconds']:
                        total=continuation_direct+60
                        if total<=HORIZON_SECONDS and (reserve['duration_seconds'] is None or total<reserve['duration_seconds']):
                            reserve=dict(duration_seconds=total,walking_seconds=continuation_direct,waiting_seconds=0,fixed_slack_seconds=60,transfers=0,arrival_seconds=ready+total,rides=[])
                    raw=None
                    if validation:
                        raw=self.raw(request,ready,continuation_access,egress,resources,continuation_direct,leg_number-1,failed['trip_id'])
                        if raw!=reserve['duration_seconds']:raise RuntimeError(f'N−1 raw R5 mismatch {index}/{number}: {raw} vs {reserve["duration_seconds"]}')
                    reserve_segments=self.segments(planner,reserve,ready,origin,destination,access_paths,egress_paths,stop) if reserve['duration_seconds'] is not None else []
                    memo[key]=(reserve,reserve_segments,raw)
                reserve,reserve_segments,raw=memo[key]
                if validation:self.calendar_check()
                if any(r['trip_id']==failed['trip_id'] for r in reserve['rides']):raise RuntimeError('Cancelled trip reused')
                scoped=self.locations[failed['trip_id']][3]
                row=dict(index=index,start=obs['start'],leg_number=leg_number,
                    status='REACHABLE' if reserve['duration_seconds'] is not None else 'UNREACHABLE',
                    failed_leg=failed,failed_instance=dict(feed=scoped.split(':',1)[0],feed_sha256=self.hashes['gtfs_original']['sha256'],trip_id=failed['trip_id'],service_date=feed_first.date().isoformat(),r5_scoped_trip_id=scoped),
                    notification=dict(stop_id=stop,stop_name=self.stops[stop]['stop_name'],coordinates=list(self.coords[stop]),time=self.iso(ready)),
                    completed=dict(segments=prefix,elapsed_seconds=ready-obs['start_seconds'],walking_seconds=walked,transit_legs=leg_number-1,
                        wait_before_notification_seconds=ready-int((datetime.fromisoformat(prefix[-1]['arrival']).astimezone(self.midnight.tzinfo)-self.midnight).total_seconds())),
                    remaining_parameters=resources,search_end=self.iso(ready+HORIZON_SECONDS),
                    reserve=dict(**reserve,segments=copy.deepcopy(reserve_segments)),raw_r5_seconds=raw,
                    total_seconds=ready-obs['start_seconds']+reserve['duration_seconds'] if reserve['duration_seconds'] is not None else None,
                    extra_seconds=ready-obs['start_seconds']+reserve['duration_seconds']-obs['duration_seconds'] if reserve['duration_seconds'] is not None else None)
                row_features=[]
                for phase,segments in [('completed',prefix),('reserve',reserve_segments)]:
                    for segment,leg in enumerate(segments):
                        props={k:v for k,v in leg.items() if k!='geometry'};props.update(index=index,leg_number=leg_number,phase=phase,segment=segment)
                        row_features.append(dict(type='Feature',geometry=leg['geometry'],properties=props))
                row['geojson']=validate_geojson(dict(type='FeatureCollection',features=row_features));features.extend(row_features);rows.append(row)
                if validation:checks.append(dict(index=index,leg_number=leg_number,raw_equals_sweep=raw==reserve['duration_seconds'],calendar_restored=True))
            # Every scenario above restores the shared network before this baseline check.
            if validation:
                after=self.raw(request,obs['start_seconds'],access,egress,parameters,direct,0)
                if after!=baseline_raw:raise RuntimeError('Scenario altered subsequent baseline')
        if baseline_only:
            self.calendar_check()
            return dict(status='OK',base_metrics=report['metrics'],minutes_checked=len(observations),baseline_sweep_and_raw_r5_equal=True,network_build_count=1)
        result=dict(status='OK',schema_version='nminus-1.1',information_assumption=INFORMATION,
            label='Scenario enligt tidtabell – ingen sannolikhet för inställd tur uppskattas.',
            horizon_seconds=HORIZON_SECONDS,base_experiment_sha256=meta['experiment_sha256'],
            input_hashes=self.hashes,code_hashes=code,versions=meta['versions'],date=meta['date'],timezone=meta['timezone'],parameters=parameters,
            minute_observations=observations,base_metrics=report['metrics'],base_itineraries=base_details,
            scenarios=scenarios,summaries={k:summarize(v) for k,v in scenarios.items()},
            verification=dict(mode='full' if validation else 'structural',baseline_source='verified_minute_profile',
                baseline_before_after_equal_count=len(observations) if validation else 0,checks=checks,
                unique_continuation_searches=len(memo),network_build_count=1,
                exact_trip_exclusion='GTFS trip_id removed from active service-day search; full validation also disables R5 TripSchedule.serviceCode temporarily',
                raw_r5_sweep_equal_count=len(checks)),
            geojson=validate_geojson(dict(type='FeatureCollection',features=features)))
        self.calendar_check()
        if any(fingerprint(ROOT/'scripts'/name)!=value for name,value in code.items()):raise RuntimeError('N−1 code changed while running')
        result['combined']=combined_nminus(observations,scenarios)
        result['canonical_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        return result
