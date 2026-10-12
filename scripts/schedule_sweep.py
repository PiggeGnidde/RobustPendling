"""Independent bounded timetable search on R5 walking links (1–4 rides).

All boarding/alighting positions are considered, including a later faster
vehicle. The graph and limits are fixed; no sampled departure times are used.
"""
from bisect import bisect_right
import csv
from datetime import timedelta
import io
import zipfile
from t90_core import PARAMETERS


def load_trips(feed, day, earliest, latest):
    with zipfile.ZipFile(feed) as z:
        def rows(name):
            return csv.DictReader(io.TextIOWrapper(z.open(name), encoding='utf-8-sig'))
        if 'frequencies.txt' in z.namelist() and any(rows('frequencies.txt')):
            raise ValueError('Frequency-based trips require a separately defined method')
        date = day.strftime('%Y%m%d')
        active = set()
        if 'calendar.txt' in z.namelist():
            active = {r['service_id'] for r in rows('calendar.txt')
                      if r['start_date'] <= date <= r['end_date'] and r[day.strftime('%A').lower()] == '1'}
        if 'calendar_dates.txt' in z.namelist():
            for r in rows('calendar_dates.txt'):
                if r['date'] == date:
                    if r['exception_type'] == '1': active.add(r['service_id'])
                    else: active.discard(r['service_id'])
        routes = {r['route_id']: r for r in rows('routes.txt')}
        trips = {r['trip_id']: dict(id=r['trip_id'], route_id=r['route_id'],
                                    line=routes[r['route_id']]['route_short_name'],
                                    mode=routes[r['route_id']]['route_type'], stops=[])
                 for r in rows('trips.txt') if r['service_id'] in active}
        def seconds(value):
            if not value:
                raise ValueError('Missing stop time requires an explicit interpolation policy')
            h,m,s = map(int, value.split(':'))
            return h*3600+m*60+s
        for r in rows('stop_times.txt'):
            if r['trip_id'] in trips:
                trips[r['trip_id']]['stops'].append(dict(id=r['stop_id'], seq=int(r['stop_sequence']),
                    arrival=seconds(r['arrival_time']), departure=seconds(r['departure_time']),
                    pickup=r.get('pickup_type','0') or '0', dropoff=r.get('drop_off_type','0') or '0'))
        result = []
        for t in trips.values():
            t['stops'].sort(key=lambda s:s['seq'])
            previous = -1
            for s in t['stops']:
                if s['arrival'] < previous or s['departure'] < s['arrival']:
                    raise ValueError('Non-monotonic timetable requires an explicit repair policy')
                previous = s['departure']
            if t['stops'] and t['stops'][-1]['arrival'] >= earliest and t['stops'][0]['departure'] <= latest:
                result.append(t)
        return result


class ScheduleSweep:
    def profile(self, starts, progress=None):
        """Exact forward profile: reuse optimum until its first boarding expires.

        Later starts only remove catchable departures. Newly horizon-feasible
        journeys arrive after the current optimum, so cannot improve it.
        Pure walk is evaluated separately because its arrival shifts with start.
        Unreachable transit minutes are searched individually (finite horizon).
        """
        if any(a>=b for a,b in zip(starts,starts[1:])):raise ValueError('Starts must increase strictly')
        import copy
        direct=self.direct_walk_seconds;cached=None;latest=-1;rows=[];anchors=[]
        access={trip['stops'][board]['id']:walk for dep,trip,board,walk in self.first}
        def key(row):
            return (row['duration_seconds'],row['walking_seconds'],tuple((r['trip_id'],r['start_stop'],r['end_stop']) for r in row['rides']))
        for index,start in enumerate(starts):
            if progress:progress(index,len(starts),len(anchors))
            if cached is None or start>latest:
                self.direct_walk_seconds=None
                original=self.p
                if direct is not None and 0<=direct<=min(self.p['max_walk_seconds'],self.p['max_time_seconds']):
                    self.p=dict(self.p,max_time_seconds=direct)
                try:cached=self.at(start)
                finally:self.direct_walk_seconds=direct;self.p=original
                anchors.append(index)
                if cached['duration_seconds'] is not None:
                    first=cached['rides'][0]
                    latest=first['departure_seconds']-access[first['start_stop']]-self.p['board_slack_seconds']-1
                else:latest=start
            row=copy.deepcopy(cached)
            if row['duration_seconds'] is not None:
                row['duration_seconds']=row['arrival_seconds']-start
                row['waiting_seconds']=row['duration_seconds']-row['walking_seconds']-row['fixed_slack_seconds']-sum(r['arrival_seconds']-r['departure_seconds'] for r in row['rides'])
            if direct is not None and 0<=direct<=min(self.p['max_walk_seconds'],self.p['max_time_seconds']):
                walk=dict(duration_seconds=direct,walking_seconds=direct,waiting_seconds=0,fixed_slack_seconds=0,transfers=0,arrival_seconds=start+direct,rides=[])
                if row['duration_seconds'] is None or key(walk)<key(row):row=walk
            rows.append(row)
        if progress:progress(len(starts),len(starts),len(anchors))
        return rows,anchors

    def __init__(self, trips, access, egress, transfers, parameters=None, direct_walk_seconds=None):
        self.p = parameters or PARAMETERS
        self.direct_walk_seconds = direct_walk_seconds
        self.egress, self.transfers = egress, transfers
        self.first = []
        self.last = {}
        self.boardings={}
        for trip in trips:
            stops = trip['stops']
            # 3 means coordinate with driver (ordinary request stop), not phone
            # the agency in advance (2). 1 prohibits boarding/alighting.
            for board, s in enumerate(stops[:-1]):
                if s['pickup'] not in ('0','3'): continue
                self.boardings.setdefault(s['id'],[]).append((s['departure'],trip,board))
                if s['id'] in access:
                    self.first.append((s['departure'], trip, board, access[s['id']]))
                for alight in range(board+1,len(stops)):
                    target = stops[alight]
                    if target['id'] in egress and target['dropoff'] in ('0','3'):
                        self.last.setdefault(s['id'], []).append((s['departure'], trip, board, alight))
        self.first.sort(key=lambda v:(v[0],v[1]['id'],v[2]))
        self.last_times = {}
        for stop, events in self.last.items():
            events.sort(key=lambda v:(v[0],v[1]['id'],v[2],v[3]))
            self.last_times[stop] = [e[0] for e in events]
        self.boarding_times={}
        for stop,events in self.boardings.items():
            events.sort(key=lambda v:(v[0],v[1]['id'],v[2]))
            self.boarding_times[stop]=[e[0] for e in events]

    @staticmethod
    def ride(trip, board, alight):
        a,b = trip['stops'][board], trip['stops'][alight]
        return dict(trip_id=trip['id'], route_id=trip['route_id'], line=trip['line'], mode=trip['mode'],
                    start_stop=a['id'], end_stop=b['id'], departure_seconds=a['departure'],
                    arrival_seconds=b['arrival'])

    def at(self, start):
        if self.p['max_rides']>2:return self.multi_at(start)
        cap, walking_cap = self.p['max_time_seconds'], self.p['max_walk_seconds']
        slack, egress_slack = self.p['board_slack_seconds'], self.p['egress_slack_seconds']
        best = None
        direct = self.direct_walk_seconds
        if direct is not None and 0 <= direct <= min(cap,walking_cap):
            best = ((direct,direct,()),dict(duration_seconds=direct,walking_seconds=direct,
                    waiting_seconds=0,fixed_slack_seconds=0,transfers=0,arrival_seconds=start+direct,rides=[]))
        def consider(rides, walking):
            nonlocal best
            arrival = rides[-1]['arrival_seconds'] + self.egress[rides[-1]['end_stop']] + egress_slack
            duration = arrival-start
            if walking > walking_cap or not 0 <= duration <= cap: return
            candidate = dict(duration_seconds=duration, walking_seconds=walking,
                             waiting_seconds=duration-walking-egress_slack-
                                 sum(r['arrival_seconds']-r['departure_seconds'] for r in rides),
                             fixed_slack_seconds=egress_slack, transfers=len(rides)-1,
                             arrival_seconds=arrival, rides=rides)
            key = (duration,walking,tuple((r['trip_id'],r['start_stop'],r['end_stop']) for r in rides))
            if best is None or key < best[0]: best = (key,candidate)
        for dep, trip, board, access_walk in self.first:
            if dep <= start+access_walk+slack or dep > start+cap: continue
            for alight in range(board+1,len(trip['stops'])):
                stop = trip['stops'][alight]
                if stop['arrival'] > start+cap: break
                if stop['dropoff'] not in ('0','3'): continue
                ride = self.ride(trip, board, alight)
                if stop['id'] in self.egress:
                    consider([ride],access_walk+self.egress[stop['id']])
                if self.p['max_rides'] < 2: continue
                for second_stop, transfer_walk in self.transfers(stop['id']).items():
                    if access_walk+transfer_walk > walking_cap: continue
                    events = self.last.get(second_stop, [])
                    pos = bisect_right(self.last_times.get(second_stop, []),stop['arrival']+transfer_walk+slack)
                    for dep2, trip2, board2, alight2 in events[pos:]:
                        if dep2 > start+cap: break
                        if trip2['id'] == trip['id']: continue
                        ride2 = self.ride(trip2,board2,alight2)
                        consider([ride,ride2],access_walk+transfer_walk+self.egress[ride2['end_stop']])
        return best[1] if best else dict(duration_seconds=None, status='UNREACHABLE', rides=[])

    def multi_at(self,start):
        """Round-based labels; time/walk/used-trip dominance preserves budgets."""
        cap=self.p['max_time_seconds'];walk_cap=self.p['max_walk_seconds']
        slack=self.p['board_slack_seconds'];end_slack=self.p['egress_slack_seconds']
        # Optimistic backward deadlines prune only provably impossible prefixes.
        # They ignore the accumulated walk budget and used trips, so cannot
        # reject a feasible continuation. Strict boarding needs at least 1 s.
        terminal={stop:start+cap-walk-end_slack for stop,walk in self.egress.items()}
        latest=[terminal]
        unique={event[1]['id']:event[1] for events in self.boardings.values() for event in events}
        for remaining in range(1,self.p['max_rides']):
            future={} if remaining==1 else dict(latest[-1])
            def limit_at(stop):
                if remaining==1:return terminal.get(stop,-1)
                return max((latest[-1].get(target,-1)-walk for target,walk in self.transfers(stop).items()),default=-1)
            for trip in unique.values():
                possible=False
                for stop in reversed(trip['stops']):
                    if possible and stop['pickup'] in ('0','3'):
                        future[stop['id']]=max(future.get(stop['id'],-1),stop['departure']-slack-1)
                    if stop['dropoff'] in ('0','3') and stop['arrival']<=limit_at(stop['id']):possible=True
            latest.append(future)
        def can_finish(stop,arrival,remaining):
            if not remaining:return arrival<=terminal.get(stop,-1)
            return arrival<=max((latest[remaining].get(target,-1)-walk for target,walk in self.transfers(stop).items()),default=-1)
        best=None
        direct=self.direct_walk_seconds
        if direct is not None and 0<=direct<=min(cap,walk_cap):
            best=((direct,direct,()),dict(duration_seconds=direct,walking_seconds=direct,waiting_seconds=0,
                fixed_slack_seconds=0,transfers=0,arrival_seconds=start+direct,rides=[]))
        access={}
        for dep,trip,board,walking in self.first:access[trip['stops'][board]['id']]=walking
        frontier=[(stop,start+walking,walking,[]) for stop,walking in access.items() if walking<=walk_cap]
        for number in range(1,self.p['max_rides']+1):
            labels={};next_frontier=[]
            for stop,ready,walked,rides in frontier:
                links={stop:0} if not rides else self.transfers(stop)
                used=frozenset(r['trip_id'] for r in rides)
                for boarding,transfer in links.items():
                    walking=walked+transfer
                    if walking>walk_cap:continue
                    final=number==self.p['max_rides']
                    events=(self.last if final else self.boardings).get(boarding,[])
                    times=(self.last_times if final else self.boarding_times).get(boarding,[])
                    pos=bisect_right(times,ready+transfer+slack)
                    for event in events[pos:]:
                        dep,trip,board=event[:3]
                        limit=start+(best[0][0] if best else cap)
                        if dep>limit:break
                        if trip['id'] in used:continue
                        for alight in ([event[3]] if final else range(board+1,len(trip['stops']))):
                            target=trip['stops'][alight];arrival=target['arrival']
                            if arrival>limit:break
                            if target['dropoff'] not in ('0','3'):continue
                            chain=rides+[self.ride(trip,board,alight)]
                            if target['id'] in self.egress:
                                total_walk=walking+self.egress[target['id']]
                                end=arrival+self.egress[target['id']]+end_slack;duration=end-start
                                key=(duration,total_walk,tuple((r['trip_id'],r['start_stop'],r['end_stop']) for r in chain))
                                if total_walk<=walk_cap and 0<=duration<=cap and (best is None or key<best[0]):
                                    best=(key,dict(duration_seconds=duration,walking_seconds=total_walk,
                                        waiting_seconds=duration-total_walk-end_slack-sum(r['arrival_seconds']-r['departure_seconds'] for r in chain),
                                        fixed_slack_seconds=end_slack,transfers=number-1,arrival_seconds=end,rides=chain))
                            if number==self.p['max_rides']:continue
                            if not can_finish(target['id'],arrival,self.p['max_rides']-number):continue
                            state=(target['id'],arrival,walking,chain)
                            bucket=labels.setdefault(target['id'],[]);new_used=used|{trip['id']}
                            chain_key=tuple((r['trip_id'],r['start_stop'],r['end_stop']) for r in chain)
                            def dominates(a,b_time,b_walk,b_used,b_key):
                                a_used=frozenset(r['trip_id'] for r in a[3])
                                a_key=tuple((r['trip_id'],r['start_stop'],r['end_stop']) for r in a[3])
                                return a[1]<=b_time and a[2]<=b_walk and a_used.issubset(b_used) and (a[2]<b_walk or a_key<=b_key)
                            if any(dominates(a,arrival,walking,new_used,chain_key) for a in bucket):continue
                            bucket[:]=[a for a in bucket if not dominates(state,a[1],a[2],frozenset(r['trip_id'] for r in a[3]),tuple((r['trip_id'],r['start_stop'],r['end_stop']) for r in a[3]))]
                            bucket.append(state)
            frontier=[state for bucket in labels.values() for state in bucket]
            if not frontier:break
        return best[1] if best else dict(duration_seconds=None,status='UNREACHABLE',rides=[])
