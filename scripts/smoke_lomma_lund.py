"""One deterministic detailed A–B routing request; no percentile calculation."""
from datetime import datetime, timedelta
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import tempfile
import time
import warnings
from transit_inputs import ROOT, paths, fingerprint
from smoke_helpers import gtfs_tables, select_station, routing_feed, itinerary_summary, check_scheduled_leg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rebuild', action='store_true', help='Use a new ignored network cache; preserve existing caches')
    arguments = parser.parse_args()
    inputs = paths(ROOT / 'config/paths.toml')
    prefix = Path(sys.prefix)
    os.environ['JAVA_HOME'] = str(prefix / 'Library/lib/jvm')
    os.environ['LOCALAPPDATA'] = str(ROOT / 'cache/runtime')
    os.environ['APPDATA'] = str(ROOT / 'cache/config')
    os.environ['MPLCONFIGDIR'] = str(ROOT / 'cache/matplotlib')
    temp = ROOT / 'cache/tmp'
    temp.mkdir(parents=True, exist_ok=True)
    os.environ['TEMP'] = os.environ['TMP'] = str(temp)
    sys.argv = [sys.argv[0], '--max-memory', '4G', '--verbose']
    import r5py
    if r5py.__version__ != '1.1.7':
        raise RuntimeError('Single-departure adapter requires r5py 1.1.7')
    if arguments.rebuild:
        from r5py.util import Config
        Config().CACHE_DIR = Path(tempfile.mkdtemp(prefix='network-', dir=ROOT / 'cache'))
    import geopandas as gpd
    from shapely.geometry import Point
    import psutil
    import jpype
    # Capture every R5 warning without drowning the log in INFO/debug output.
    context = jpype.JClass('org.slf4j.LoggerFactory').getILoggerFactory()
    context.getLogger('ROOT').setLevel(jpype.JClass('ch.qos.logback.classic.Level').WARN)
    stops, routes = gtfs_tables(inputs['gtfs'])
    origin = select_station(stops, 'Lomma station')
    destination = select_station(stops, 'Lund C')
    route_lookup = {r['route_id']: r for r in routes}
    derived = ROOT / 'data/gtfs/skane-20261011-r0.zip'
    derived.parent.mkdir(parents=True, exist_ok=True)
    derivation = routing_feed(inputs['gtfs'], derived)
    report = dict(origin=origin, destination=destination,
                  osm=fingerprint(inputs['osm']), gtfs=fingerprint(inputs['gtfs']), derivation=derivation)
    report['fresh_network_cache'] = arguments.rebuild
    peak = [psutil.Process().memory_info().rss]
    done = threading.Event()
    def monitor():
        while not done.wait(.1):
            peak[0] = max(peak[0], psutil.Process().memory_info().rss)
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    try:
        start = time.perf_counter()
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always')
            network = r5py.TransportNetwork(inputs['osm'], [derived])
            report['build_seconds'] = round(time.perf_counter() - start, 2)
            report['python_build_warnings'] = [str(w.message) for w in captured]
        vertices = network._transport_network.transitLayer.streetVertexForStop
        report['unlinked_stops'] = sum(int(vertices.get(i)) < 0 for i in range(vertices.size()))
        report['network_stops'] = vertices.size()
        def frame(station):
            return gpd.GeoDataFrame({'id': [station['id']]},
                                    geometry=[Point(station['lon'], station['lat'])], crs='EPSG:4326')
        departure = datetime(2026, 10, 12, 7, 0)
        class SingleDepartureItineraries(r5py.DetailedItineraries):
            def _compute(self):
                # R5 uses a coordinate-seeded internal start-time selector.
                # Exactly one selected start avoids aliasing mutable access legs
                # between departures; no percentiles or disruption simulation.
                self.request._regional_task.monteCarloDraws = 1
                return super()._compute()
        result = SingleDepartureItineraries(network, frame(origin), frame(destination),
                    departure=departure, departure_time_window=timedelta(minutes=5),
                    transport_modes=[r5py.TransportMode.WALK, r5py.TransportMode.TRANSIT],
                    max_time=timedelta(minutes=45), max_time_walking=timedelta(minutes=15),
                    max_public_transport_rides=2, speed_walking=3.6)
        if result.empty:
            raise RuntimeError('No itinerary found')
        # One request may return alternative itineraries; report all legs and
        # choose fastest scheduled transit itinerary for the hand check.
        itineraries = []
        for option, group in result.groupby('option'):
            legs = []
            for _, row in group.sort_values('segment').iterrows():
                route = route_lookup.get(str(row.route_id), {})
                legs.append(dict(mode=str(row.transport_mode), departure=str(row.departure_time),
                     travel_seconds=row.travel_time.total_seconds(), wait_seconds=row.wait_time.total_seconds(),
                     route_id=str(row.route_id), line=route.get('route_short_name'),
                     route_type=route.get('route_type'), start_stop=str(row.start_stop_id),
                     end_stop=str(row.end_stop_id)))
            itineraries.append(dict(option=int(option), legs=legs, **itinerary_summary(legs)))
        report['itineraries'] = itineraries
        transit = [i for i in itineraries if any(l['line'] for l in i['legs'])]
        if not transit:
            raise RuntimeError('No public transport itinerary found')
        chosen = min(transit, key=lambda i: i['total_seconds'])
        report['selected_option'] = chosen['option']
        report['schedule_checks'] = [check_scheduled_leg(inputs['gtfs'], l, departure)
                                     for l in chosen['legs'] if l['line']]
        if not all(c['verified'] for c in report['schedule_checks']):
            raise RuntimeError('GTFS timetable hand check failed')
        report['sampled_peak_rss_bytes'] = peak[0]
        report['parameters'] = dict(r5py_version=r5py.__version__, walk_speed_kmh=3.6,
                                    max_time_minutes=45, max_walk_minutes=15, max_rides=2,
                                    internal_departure_draws=1, jvm_heap='4G')
        report['window'] = '2026-10-12 07:00:00 to 07:05:00 Europe/Stockholm'
        print(json.dumps(report, indent=2))
        inputs['output'].mkdir(parents=True, exist_ok=True)
        (inputs['output'] / 'lomma_lund_smoke.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    finally:
        done.set()
        thread.join()
        print('SAMPLED_PEAK_RSS_BYTES', peak[0], flush=True)


if __name__ == '__main__':
    main()
