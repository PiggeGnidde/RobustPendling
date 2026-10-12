"""Extend R5's fixed 1 km street transfers once per network, to 3 km.

Existing pairs/rules remain intact. Only longer WALK pairs are appended;
per-request speed and whole-walk resource filtering still apply. Original
3.6 km/h / 15 min regressions cannot use these >1 km pairs.
"""
_EXTENDED=set()

def merge_pairs(original,reached):
    values=dict(original)
    for stop,distance in reached.items():
        if distance>1_000_000 and stop not in values:values[stop]=distance
    return sorted(values.items())

def ensure_walking_links(network,parameters):
    if parameters['walk_speed_kmh']/3.6*parameters['max_walk_seconds']<=1000:return
    import jpype
    java_network=network._transport_network
    if java_network in _EXTENDED:return
    layer=java_network.transitLayer
    Router=jpype.JClass('com.conveyal.r5.streets.StreetRouter')
    Variable=jpype.JClass('com.conveyal.r5.streets.StreetRouter$State$RoutingVariable')
    Mode=jpype.JClass('com.conveyal.r5.profile.StreetMode')
    List=jpype.JClass('gnu.trove.list.array.TIntArrayList')
    for stop in range(layer.getStopCount()):
        vertex=int(layer.streetVertexForStop.get(stop))
        if vertex<0:continue
        router=Router(java_network.streetLayer)
        router.distanceLimitMeters=3000;router.quantityToMinimize=Variable.DISTANCE_MILLIMETERS
        router.streetMode=Mode.WALK;router.transitStopSearch=True
        router.setOrigin(vertex);router.route()
        reached=router.getReachedStops()
        old=layer.streetTransfers.get(stop)
        original=[(int(old.get(i)),int(old.get(i+1))) for i in range(0,old.size(),2)]
        pairs=merge_pairs(original,{int(k):int(reached.get(k)) for k in reached.keys()})
        replacement=List()
        for target,distance in pairs:replacement.add(target);replacement.add(distance)
        layer.streetTransfers.set(stop,replacement)
    _EXTENDED.add(java_network)
