"""Exhaustive one/two-ride timetable search on R5 walking links.

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
    def __init__(self, trips, access, egress, transfers, parameters=None, direct_walk_seconds=None):
        self.p = parameters or PARAMETERS
        self.direct_walk_seconds = direct_walk_seconds
        self.egress, self.transfers = egress, transfers
        self.first = []
        self.last = {}
        for trip in trips:
            stops = trip['stops']
            # 3 means coordinate with driver (ordinary request stop), not phone
            # the agency in advance (2). 1 prohibits boarding/alighting.
            for board, s in enumerate(stops[:-1]):
                if s['pickup'] not in ('0','3'): continue
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

    @staticmethod
    def ride(trip, board, alight):
        a,b = trip['stops'][board], trip['stops'][alight]
        return dict(trip_id=trip['id'], route_id=trip['route_id'], line=trip['line'], mode=trip['mode'],
                    start_stop=a['id'], end_stop=b['id'], departure_seconds=a['departure'],
                    arrival_seconds=b['arrival'])

    def at(self, start):
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
