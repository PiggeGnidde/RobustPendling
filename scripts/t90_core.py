"""Schedule statistics and frozen experiment metadata, without routing imports."""
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import json
import math
from zoneinfo import ZoneInfo

PARAMETERS = dict(walk_speed_kmh=3.6, max_time_seconds=2700,
                  max_walk_seconds=900, max_rides=2, board_slack_seconds=60,
                  boarding_rule='departure > arrival_at_stop + 60',
                  egress_slack_seconds=60, modes=['WALK', 'TRANSIT'],
                  percentile_method='nearest_rank_ceiling', missing='positive_infinity',
                  jvm_heap='4G', frequencies_policy='reject_nonempty')
PARAMETERS['pickup_dropoff_policy'] = 'allow 0 and 3; reject 1 and 2'
PARAMETERS['tie_break'] = 'duration, walking, lexicographic trip/boarding/alighting IDs'


def minute_grid(day, start='07:00:00', end='07:59:59', timezone='Europe/Stockholm'):
    if timezone != 'Europe/Stockholm':
        raise ValueError('This experiment requires Europe/Stockholm')
    zone = ZoneInfo(timezone)
    first = datetime.fromisoformat(f'{day}T{start}').replace(tzinfo=zone)
    last = datetime.fromisoformat(f'{day}T{end}').replace(tzinfo=zone)
    if first.second or first.microsecond or last < first:
        raise ValueError('Start must be a minute boundary and end must not precede start')
    grid = []
    while first <= last:
        # Reject DST ambiguity/nonexistent local times rather than silently choosing.
        if first.utcoffset() != first.replace(fold=1).utcoffset():
            raise ValueError('Ambiguous or nonexistent local start time')
        grid.append(first)
        first += timedelta(minutes=1)
    return grid


def statistics(values):
    if not values:
        raise ValueError('Empty experiment')
    if any(v is not None and (not math.isfinite(v) or v < 0) for v in values):
        raise ValueError('Use None for unreachable; durations must be finite and nonnegative')
    ordered = sorted(math.inf if v is None else v for v in values)
    finite = [v for v in values if v is not None]
    def encode(value):
        return 'UNREACHABLE' if math.isinf(value) else value
    return dict(count=len(values), reachable_count=len(finite),
                unreachable_count=len(values)-len(finite), route_coverage=len(finite)/len(values),
                percentiles_seconds={f'T{p}': encode(ordered[math.ceil(p*len(values)/100)-1])
                                     for p in (50, 90, 99)},
                minimum_seconds=encode(ordered[0]), maximum_seconds=encode(ordered[-1]),
                mean_seconds=sum(finite)/len(values) if len(finite)==len(values) else 'UNREACHABLE',
                reachable_mean_seconds=sum(finite)/len(finite) if finite else None)


def metadata(hashes, versions, grid, parameters=None):
    frozen = dict(method='T90_schedule', input_hashes=hashes, versions=versions,
                  date=grid[0].date().isoformat(), timezone=str(grid[0].tzinfo),
                  start_minutes=[t.isoformat() for t in grid],
                  parameters=parameters or PARAMETERS)
    encoded = json.dumps(frozen, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return dict(**frozen, experiment_sha256=hashlib.sha256(encoded.encode()).hexdigest())


def combinations(observations):
    counts = Counter(tuple((l['route_id'], l['line'], l['mode']) for l in row.get('rides', []))
                     for row in observations if row['duration_seconds'] is not None)
    reachable = sum(counts.values())
    return [dict(rides=[dict(route_id=r, line=l, mode=m) for r,l,m in key],
                 transfers=len(key)-1, count=count, share_all_minutes=count/len(observations),
                 share_reachable_minutes=count/reachable)
            for key,count in sorted(counts.items())]


def component_statistics(observations):
    reachable = [r for r in observations if r['duration_seconds'] is not None]
    def summary(key):
        values = [r[key] for r in reachable]
        return dict(minimum=min(values),maximum=max(values),mean=sum(values)/len(values)) if values else None
    return dict(walking_seconds=summary('walking_seconds'),waiting_seconds=summary('waiting_seconds'),
                fixed_slack_seconds=summary('fixed_slack_seconds'),
                transfers={str(k):v for k,v in sorted(Counter(r['transfers'] for r in reachable).items())})
