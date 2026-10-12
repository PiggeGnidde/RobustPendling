"""Exact-minute, all-state adapter for pinned r5py 1.1.7 / R5 7.5.1.

DetailedItineraries supplies its normal request/frame machinery. Only its
OD hook is replaced: the stock hook samples times and collapses alternatives.
All leg snapshots below are independent, avoiding mutable access/egress reuse.
"""
from datetime import datetime,timedelta
import copy
import json
from analysis_contract import family,mode_name,validate_geojson,itinerary_timing,connect_walk_geometry
_GEOMETRY_ADAPTERS={}


def collect(network,origin,destination,representative,observation,feed_instant,trip_lookup,stop_names,stop_coordinates,parameters=None):
    import r5py
    import jpype
    import pandas as pd
    import geopandas as gpd
    from shapely.geometry import Point,mapping,MultiLineString
    from shapely import from_wkt,line_merge
    from r5py.r5.trip_planner import TripPlanner
    from t90_core import PARAMETERS
    parameters=parameters or PARAMETERS
    from r5_adapter import dominating_factory
    from nminus_core import normalize_walk_geometry
    if r5py.__version__!='1.1.7':raise RuntimeError('Detailed adapter requires r5py 1.1.7')
    layer=network._transport_network.transitLayer
    ready=feed_instant.hour*3600+feed_instant.minute*60
    midnight=feed_instant.replace(hour=0,minute=0,second=0,microsecond=0)
    ids={i:str(layer.stopIdForIndex.get(i)).split(':',1)[1] for i in range(layer.getStopCount())}
    diagnostics={}
    planners=[]
    line_lookup={t['route_id']:t['line'] for t in trip_lookup.values()}
    def frame(p):
        return gpd.GeoDataFrame({'id':[p['id']]},geometry=[Point(p['lon'],p['lat'])],crs='EPSG:4326')
    def segment(mode,departure,duration,wait,geometry,route=None,a=None,b=None,trip=None,slack=0):
        return dict(transport_mode=r5py.TransportMode(mode),departure_time=midnight+timedelta(seconds=departure),
                    distance=None,travel_time=timedelta(seconds=duration),wait_time=timedelta(seconds=wait),
                    feed=None,agency_id=None,route_id=route,start_stop_id=a,end_stop_id=b,geometry=geometry,
                    trip_id=trip,fixed_slack_seconds=slack)

    class ExactDetailed(r5py.DetailedItineraries):
        def _travel_details_per_od_pair(self,from_id,to_id):
            request=copy.copy(self.request)
            req=request._regional_task
            req.fromLat,req.fromLon=origin['lat'],origin['lon']
            req.toLat,req.toLon=destination['lat'],destination['lon']
            planner=TripPlanner(network,request)
            planners.append(planner)
            # Keep the same access/egress budget as the exhaustive sweep.
            def times(paths):
                outer=jpype.JClass('java.util.HashMap')()
                for mode,legs in paths.items():
                    inner=jpype.JClass('gnu.trove.map.hash.TIntIntHashMap')()
                    for stop,leg in legs.items():
                        seconds=round(leg.travel_time.total_seconds())
                        if seconds<=900:inner.put(int(stop),seconds)
                    outer.put(jpype.JClass('com.conveyal.r5.api.util.LegMode').valueOf(mode.name),inner)
                return outer
            router=jpype.JClass('com.conveyal.r5.profile.McRaptorSuboptimalPathProfileRouter')
            req.fromTime,req.toTime,req.monteCarloDraws=ready-1,ready+1,1
            engine=router(network,request,times(planner._transit_access_paths),times(planner._transit_egress_paths),
                          dominating_factory(layer,int(req.suboptimalMinutes),parameters=parameters,ready=ready),None,True)
            field=router.class_.getDeclaredField('mersenneTwister');field.setAccessible(True)
            field.set(engine,jpype.JClass('org.apache.commons.math3.random.MersenneTwister')(0))
            engine.route()
            evaluated=sorted(int(k) for k in engine.finalStatesByDepartureTime.keys())
            if evaluated not in ([ready],[]):raise RuntimeError('Detailed adapter did not evaluate the exact requested minute')
            diagnostics['evaluated_seconds']=evaluated
            options=[]
            for trip in planner.direct_paths:
                leg=trip.legs[0]
                seconds=round(leg.travel_time.total_seconds())
                if seconds<=900:
                    options.append([segment('WALK',ready,seconds,0,leg.geometry)])
            states=engine.finalStatesByDepartureTime.get(ready)
            for state in states if states is not None else []:
                chain=[];current=state
                while current is not None:chain.append(current);current=current.back
                chain.reverse()
                legs=[];eligible=True
                for i,current in enumerate(chain):
                    if i==0:
                        leg=planner._transit_access_paths[r5py.TransportMode.WALK][int(current.stop)]
                        legs.append(segment('WALK',ready,int(current.time)-ready,0,leg.geometry,b=ids[int(current.stop)]))
                    elif current.stop==-1:
                        previous=chain[i-1]
                        leg=planner._transit_egress_paths[r5py.TransportMode.WALK][int(previous.stop)]
                        legs.append(segment('WALK',int(previous.time)+60,int(current.time-previous.time),0,
                                            leg.geometry,a=ids[int(previous.stop)],slack=60))
                    elif current.pattern==-1:
                        previous=chain[i-1]
                        leg=planner._transit_transfer_path(int(previous.stop),int(current.stop))
                        if current.time>previous.time:
                            legs.append(segment('WALK',int(previous.time),int(current.time-previous.time),0,
                                                leg.geometry,a=ids[int(previous.stop)],b=ids[int(current.stop)]))
                    else:
                        previous=chain[i-1]
                        pattern=layer.tripPatterns.get(current.pattern)
                        route=layer.routes.get(pattern.routeIndex)
                        trip_id=str(pattern.tripSchedules.get(current.trip).tripId).split(':',1)[-1]
                        scheduled=trip_lookup.get(trip_id)
                        a,b=ids[int(previous.stop)],ids[int(current.stop)]
                        if scheduled is None or not any(s['id']==a and s['departure']==current.boardTime and s['pickup'] in ('0','3') for s in scheduled['stops']) or not any(s['id']==b and s['arrival']==current.time and s['dropoff'] in ('0','3') for s in scheduled['stops']):
                            eligible=False;break
                        hops=list(pattern.getHopGeometries(layer))[current.boardStopPosition:current.alightStopPosition]
                        geometry=line_merge(MultiLineString([from_wkt(str(h.toText())) for h in hops]))
                        mode=mode_name(route.route_type)
                        legs.append(segment(mode,int(current.boardTime),int(current.time-current.boardTime),
                                            int(current.boardTime-previous.time),geometry,str(route.route_id),a,b,trip_id))
                if eligible:options.append(legs)
            rows=[]
            for option,legs in enumerate(options):
                for number,leg in enumerate(legs):
                    rows.append(dict(from_id=from_id,to_id=to_id,option=option,segment=number,**leg))
            # Normal DetailedItineraries._compute retains these extra columns.
            return pd.DataFrame(rows,columns=self.COLUMNS+['trip_id','fixed_slack_seconds'])

    result=ExactDetailed(network,frame(origin),frame(destination),departure=feed_instant,
           departure_time_window=timedelta(minutes=5),speed_walking=3.6,
           transport_modes=[r5py.TransportMode.WALK,r5py.TransportMode.TRANSIT],
           max_time=timedelta(minutes=45),max_time_walking=timedelta(minutes=15),max_public_transport_rides=parameters['max_rides'])
    result=result.to_crs('EPSG:4326')
    families={};invalid=0
    for _,group in result.groupby('option'):
        legs=[]
        for _,r in group.sort_values('segment').iterrows():
            depart=r.departure_time.to_pydatetime() if hasattr(r.departure_time,'to_pydatetime') else r.departure_time
            duration=r.travel_time.total_seconds()
            a=None if pd.isna(r.start_stop_id) else str(r.start_stop_id)
            b=None if pd.isna(r.end_stop_id) else str(r.end_stop_id)
            route=None if pd.isna(r.route_id) else str(r.route_id)
            # Source times are in feed timezone; display in request timezone.
            display_zone=datetime.fromisoformat(observation['start']).tzinfo
            geometry=mapping(r.geometry)
            connectors=None
            if mode_name(r.transport_mode)=='WALK':
                geometry,connectors=normalize_walk_geometry(geometry,
                    stop_coordinates[a] if a else (origin['lon'],origin['lat']),
                    stop_coordinates[b] if b else (destination['lon'],destination['lat']))
            legs.append(dict(mode=mode_name(r.transport_mode),route_id=route,
                line=line_lookup.get(route),
                start_stop=a,end_stop=b,start_stop_name=stop_names.get(a) if a else origin['name'],
                end_stop_name=stop_names.get(b) if b else destination['name'],
                departure=depart.astimezone(display_zone).isoformat(),
                arrival=(depart+timedelta(seconds=duration)).astimezone(display_zone).isoformat(),
                travel_seconds=duration,walking_seconds=duration if mode_name(r.transport_mode)=='WALK' else 0,
                wait_seconds=r.wait_time.total_seconds(),fixed_slack_seconds=float(r.fixed_slack_seconds),
                trip_id=None if pd.isna(r.trip_id) else str(r.trip_id),geometry=geometry,
                geometry_source='R5_street_path_with_approximate_straight_connectors' if connectors else 'R5_GTFS_hops',
                geometry_connectors_m=connectors))
        total=(datetime.fromisoformat(legs[-1]['arrival'])-datetime.fromisoformat(observation['start'])).total_seconds()
        walking=sum(l['walking_seconds'] for l in legs)
        if not 0<=total<=2700 or walking>900 or any(l['wait_seconds']<0 for l in legs):invalid+=1;continue
        rides=[dict(mode=l['mode'],route_id=l['route_id'],line=l['line'],start_stop=l['start_stop'],end_stop=l['end_stop']) for l in legs if l['mode']!='WALK']
        f=family(rides)
        item=dict(route_family=f, duration_seconds=total,walking_seconds=walking,
                  waiting_seconds=sum(l['wait_seconds'] for l in legs),
                  fixed_slack_seconds=sum(l['fixed_slack_seconds'] for l in legs),
                  transfers=max(len(rides)-1,0),segments=legs)
        item['timing_validation']=itinerary_timing(legs,observation['start'])
        if f['id'] not in families or (total,walking,json.dumps(legs,sort_keys=True))<(families[f['id']]['duration_seconds'],families[f['id']]['walking_seconds'],json.dumps(families[f['id']]['segments'],sort_keys=True)):
            families[f['id']]=item
    primary_family=family(observation.get('rides',[]))['id']
    # R5 dominance may retain another equally fast chain. Always map the
    # exact independently selected baseline, including its trip instances.
    from nminus_engine import NMinusEngine
    java_network=network._transport_network
    if java_network not in _GEOMETRY_ADAPTERS:
        stops=[dict(stop_id=stop,stop_name=stop_names[stop],stop_lon=coords[0],stop_lat=coords[1]) for stop,coords in stop_coordinates.items()]
        _GEOMETRY_ADAPTERS[java_network]=NMinusEngine(network,None,stops,{})
    geometry_adapter=_GEOMETRY_ADAPTERS[java_network]
    geometry_adapter.midnight=midnight
    geometry_adapter.display_zone=datetime.fromisoformat(observation['start']).tzinfo
    planner=planners[0]
    access={str(layer.stopIdForIndex.get(int(k))).split(':',1)[1]:v for k,v in planner._transit_access_paths[r5py.TransportMode.WALK].items()}
    egress={str(layer.stopIdForIndex.get(int(k))).split(':',1)[1]:v for k,v in planner._transit_egress_paths[r5py.TransportMode.WALK].items()}
    chosen=geometry_adapter.segments(planner,observation,ready,origin,destination,access,egress)
    families[primary_family]=dict(route_family=family(observation.get('rides',[])),duration_seconds=observation['duration_seconds'],
        walking_seconds=observation['walking_seconds'],waiting_seconds=observation['waiting_seconds'],
        fixed_slack_seconds=observation['fixed_slack_seconds'],transfers=observation['transfers'],segments=chosen,
        source='selected independent sweep; R5 street/hop geometry',timing_validation=itinerary_timing(chosen,observation['start']))
    options=sorted(families.values(),key=lambda o:(o['duration_seconds'],o['walking_seconds'],
                                                  o['route_family']['id']!=primary_family,o['route_family']['id']))
    features=[]
    best=observation['duration_seconds']
    for option,item in enumerate(options):
        item['option']=option
        item['slower_than_best_seconds']=item['duration_seconds']-best
        for index,leg in enumerate(item['segments']):
            props={k:v for k,v in leg.items() if k!='geometry'}
            props.update(option=option,route_family=item['route_family']['id'],segment=index,
                         representative_start=observation['start'],percentile_role=representative['percentile_roles'],
                         audit_roles=representative.get('audit_roles',[]),
                         slower_than_best_seconds=item['slower_than_best_seconds'])
            features.append(dict(type='Feature',geometry=leg['geometry'],properties=props))
    validate_geojson(dict(type='FeatureCollection',features=features))
    matches=bool(options) and options[0]['duration_seconds']==best and options[0]['timing_validation']['valid']
    return dict(**representative,best_duration_seconds=best,best_r5_option=options[0] if options else None,
                matches_sweep=matches,primary_route_family=primary_family,options=options,
                diagnostics=dict(**diagnostics,raw_options=int(result.option.nunique()),
                                 deduplicated_families=len(options),discarded_invalid=invalid)),features
