"""Pinned R5 state filtering: enforce GTFS permissions before dominance pruning."""
ALLOWED_ACTIONS={'SCHEDULED','COORDINATE_WITH_DRIVER'}
_PERMISSIONS_CACHE={}


def stop_permissions_allow(pickup,dropoff):
    return pickup in ALLOWED_ACTIONS and dropoff in ALLOWED_ACTIONS


def permission_filtered_add(state,delegate,permissions):
    if state.pattern>=0:
        pickup,dropoff=permissions[int(state.pattern)]
        if not stop_permissions_allow(pickup[int(state.boardStopPosition)],dropoff[int(state.alightStopPosition)]):
            return False
    return delegate.add(state)


def dominating_factory(layer,suboptimal_minutes):
    import jpype
    if layer not in _PERMISSIONS_CACHE:
        _PERMISSIONS_CACHE[layer]={i:([str(v) for v in p.pickups],[str(v) for v in p.dropoffs])
                                  for i,p in enumerate(layer.tripPatterns)}
    permissions=_PERMISSIONS_CACHE[layer]
    def factory(_):
        delegate=jpype.JClass('com.conveyal.r5.profile.SuboptimalDominatingList')(max(suboptimal_minutes,0))
        def add(state):
            return permission_filtered_add(state,delegate,permissions)
        return jpype.JProxy('com.conveyal.r5.profile.DominatingList',dict=dict(
            add=add,getNonDominatedStates=delegate.getNonDominatedStates))
    return factory
