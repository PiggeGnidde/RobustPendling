"""Standard-library static GTFS statistics; no network requests."""
import csv
from datetime import date, datetime, timedelta
import io
import zipfile
from collections import Counter
from transit_inputs import fingerprint


def summarize(path, as_of=None):
    with zipfile.ZipFile(path) as archive:
        def rows(name):
            if name not in archive.namelist():
                return
            with archive.open(name) as stream:
                yield from csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8-sig'))

        def day(value):
            return datetime.strptime(value, '%Y%m%d').date()

        routes = {r['route_id']: r['route_type'] for r in rows('routes.txt')}
        trips = {r['trip_id']: r for r in rows('trips.txt')}
        stops = sum(1 for _ in rows('stops.txt'))
        calendar = list(rows('calendar.txt'))
        exceptions = list(rows('calendar_dates.txt'))
        dates = [day(r[k]) for r in calendar for k in ('start_date', 'end_date')]
        dates += [day(r['date']) for r in exceptions]
        departures = 0
        first = {}
        for r in rows('stop_times.txt'):
            departures += 1
            value = r.get('departure_time') or r.get('arrival_time')
            if value:
                h, m, s = map(int, value.split(':'))
                seconds = h * 3600 + m * 60 + s
                first[r['trip_id']] = min(seconds, first.get(r['trip_id'], seconds))
        info = [{k: r.get(k) for k in ('feed_version', 'feed_start_date', 'feed_end_date')}
                for r in rows('feed_info.txt')]
        result = dict(fingerprint(path), feed_info=info, stops=stops,
                      routes=len(routes), trips=len(trips), stop_times=departures,
                      route_types=dict(Counter(routes.values())))
        if not dates:
            result['service_coverage'] = 'MISSING'
            return result
        start, end = min(dates), max(dates)
        result['service_coverage'] = [str(start), str(end)]
        # Samples are actual calendar dates; no inference that every date has service.
        as_of = as_of or date.today()
        result['sample_reference_date'] = str(as_of)
        anchor = max(start, as_of)
        samples = []
        weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for label, weekday in [('weekday', 0), ('saturday', 5), ('sunday', 6)]:
            selected = anchor + timedelta(days=(weekday - anchor.weekday()) % 7)
            if selected > end:
                selected = start + timedelta(days=(weekday - start.weekday()) % 7)
            active = {r['service_id'] for r in calendar
                      if day(r['start_date']) <= selected <= day(r['end_date'])
                      and r[weekdays[selected.weekday()]] == '1'}
            for r in exceptions:
                if day(r['date']) == selected:
                    if r['exception_type'] == '1':
                        active.add(r['service_id'])
                    elif r['exception_type'] == '2':
                        active.discard(r['service_id'])
            ids = {tid for tid, r in trips.items() if r['service_id'] in active}
            counts = Counter(routes[trips[tid]['route_id']] for tid in ids)
            samples.append(dict(profile=label, date=str(selected), active_trips=len(ids),
                                route_types=dict(counts),
                                evening_trip_starts_21_23=sum(21*3600 <= first.get(tid, -1) < 23*3600 for tid in ids)))
        result['samples'] = samples
        result['notes'] = ('stop_times counts table rows, not unique vehicle departures; '
                           'evening counts trip starts, not every stop departure; '
                           'service coverage is calendar envelope; routing not verified')
        return result
