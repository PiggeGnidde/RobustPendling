"""Deterministic station selection from GTFS, independent of routing packages."""
import csv
import io
import zipfile
import json
from datetime import datetime, timedelta
from pathlib import Path
from transit_inputs import fingerprint, atomic_json


def gtfs_tables(path):
    with zipfile.ZipFile(path) as archive:
        def table(name):
            with archive.open(name) as stream:
                return list(csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8-sig')))
        return table('stops.txt'), table('routes.txt')


def select_station(stops, name):
    matches = [r for r in stops if r['stop_name'].casefold() == name.casefold()]
    if not matches:
        raise ValueError('Station name absent from GTFS')
    # Prefer a station-area record; ties resolved by ID and explicitly reported.
    selected = min(matches, key=lambda r: (r.get('location_type') != '1', r['stop_id']))
    return dict(id=selected['stop_id'], name=name, lat=float(selected['stop_lat']),
                lon=float(selected['stop_lon']), candidates=len(matches))


def itinerary_summary(legs):
    """Use the actual clock span, preserving R5's unlabelled egress slack."""
    components = sum(l['travel_seconds'] + l['wait_seconds'] for l in legs)
    if any(l['departure'] == 'NaT' for l in legs):
        return dict(component_seconds=components, total_seconds=None)
    start = datetime.fromisoformat(legs[0]['departure'])
    end = datetime.fromisoformat(legs[-1]['departure']) + timedelta(seconds=legs[-1]['travel_seconds'])
    total = (end - start).total_seconds()
    return dict(component_seconds=components, total_seconds=total,
                unlabelled_slack_seconds=total-components,
                walking_seconds=sum(l['travel_seconds'] for l in legs if l['mode'].endswith('.WALK')),
                waiting_seconds=sum(l['wait_seconds'] for l in legs),
                departure=start.isoformat(), arrival=end.isoformat())


def check_scheduled_leg(source, leg, day):
    """Verify route, stops, clock times and active service directly in GTFS."""
    with zipfile.ZipFile(source) as z:
        def rows(name):
            return csv.DictReader(io.TextIOWrapper(z.open(name), encoding='utf-8-sig'))
        date = day.strftime('%Y%m%d')
        active = set()
        if 'calendar.txt' in z.namelist():
            weekday = day.strftime('%A').lower()
            active = {r['service_id'] for r in rows('calendar.txt')
                      if r['start_date'] <= date <= r['end_date'] and r[weekday] == '1'}
        if 'calendar_dates.txt' in z.namelist():
            for r in rows('calendar_dates.txt'):
                if r['date'] == date:
                    if r['exception_type'] == '1':
                        active.add(r['service_id'])
                    else:
                        active.discard(r['service_id'])
        trips = {r['trip_id'] for r in rows('trips.txt')
                 if r['route_id'] == leg['route_id'] and r['service_id'] in active}
        depart = datetime.fromisoformat(leg['departure'])
        arrive = depart + timedelta(seconds=leg['travel_seconds'])
        boarding, alighting = {}, {}
        for r in rows('stop_times.txt'):
            if r['trip_id'] not in trips:
                continue
            if r['stop_id'] == leg['start_stop'] and r['departure_time'] == depart.strftime('%H:%M:%S'):
                boarding[r['trip_id']] = int(r['stop_sequence'])
            if r['stop_id'] == leg['end_stop'] and r['arrival_time'] == arrive.strftime('%H:%M:%S'):
                alighting[r['trip_id']] = int(r['stop_sequence'])
        matches = sorted(t for t in boarding.keys() & alighting.keys() if boarding[t] < alighting[t])
        names = {r['stop_id']: r['stop_name'] for r in rows('stops.txt')}
        return dict(verified=bool(matches), matching_trip_ids=matches,
                    boarding_stop=names.get(leg['start_stop']), alighting_stop=names.get(leg['end_stop']))


def routing_feed(source, target):
    """Derive an R0 feed excluding unsupported advance-order route_type 1501."""
    source, target = Path(source), Path(target)
    with zipfile.ZipFile(source) as archive:
        def rows(name):
            return list(csv.DictReader(io.TextIOWrapper(archive.open(name), encoding='utf-8-sig')))
        routes = rows('routes.txt')
        excluded_routes = {r['route_id'] for r in routes if r['route_type'] == '1501'}
        trips = rows('trips.txt')
        excluded_trips = {r['trip_id'] for r in trips if r['route_id'] in excluded_routes}
        counts = {}
        temporary = target.with_suffix('.tmp')
        try:
            with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as out:
                def write(name, data):
                    info = zipfile.ZipInfo(name, date_time=(2026, 10, 11, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    out.writestr(info, data)
                for name in archive.namelist():
                    if name not in ('routes.txt', 'trips.txt', 'stop_times.txt', 'transfers.txt'):
                        write(name, archive.read(name))
                        continue
                    with archive.open(name) as raw:
                        reader = csv.DictReader(io.TextIOWrapper(raw, encoding='utf-8-sig'))
                        text = io.StringIO()
                        writer = csv.DictWriter(text, fieldnames=reader.fieldnames, lineterminator='\n')
                        writer.writeheader()
                        removed = 0
                        for row in reader:
                            reject = (row.get('route_id') in excluded_routes or row.get('trip_id') in excluded_trips
                                      or any(row.get(k) in excluded_routes for k in ('from_route_id','to_route_id'))
                                      or any(row.get(k) in excluded_trips for k in ('from_trip_id','to_trip_id')))
                            if reject:
                                removed += 1
                            else:
                                writer.writerow(row)
                        write(name, text.getvalue())
                        counts[name] = removed
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    metadata = dict(source=fingerprint(source), derived=fingerprint(target),
                    excluded_route_type='1501', removed_rows=counts)
    atomic_json(Path(str(target)+'.metadata.json'), metadata)
    return metadata
