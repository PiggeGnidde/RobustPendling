import sys
from pathlib import Path
import unittest
import tempfile
import zipfile
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from smoke_helpers import select_station, routing_feed, itinerary_summary, check_scheduled_leg


class StationTests(unittest.TestCase):
    def test_schedule_check_respects_calendar_exceptions(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
            source = Path(directory) / 'feed.zip'
            with zipfile.ZipFile(source, 'w') as z:
                z.writestr('calendar_dates.txt', 'service_id,date,exception_type\ns,20261012,1\ns,20261013,2\n')
                z.writestr('trips.txt', 'trip_id,route_id,service_id\nt,r,s\n')
                z.writestr('stops.txt', 'stop_id,stop_name\na,A\nb,B\n')
                z.writestr('stop_times.txt', 'trip_id,stop_id,departure_time,arrival_time,stop_sequence\nt,a,07:00:00,07:00:00,1\nt,b,07:02:00,07:02:00,2\n')
            leg = dict(route_id='r', start_stop='a', end_stop='b', departure='2026-10-12 07:00:00', travel_seconds=120)
            self.assertTrue(check_scheduled_leg(source, leg, datetime(2026, 10, 12))['verified'])
            self.assertFalse(check_scheduled_leg(source, leg, datetime(2026, 10, 13))['verified'])

    def test_timeline_includes_unlabelled_egress_slack(self):
        legs = [dict(mode='TransportMode.BUS', departure='2026-10-12 07:00:00', travel_seconds=120, wait_seconds=0),
                dict(mode='TransportMode.WALK', departure='2026-10-12 07:03:00', travel_seconds=60, wait_seconds=0)]
        result = itinerary_summary(legs)
        self.assertEqual(result['total_seconds'], 240)
        self.assertEqual(result['unlabelled_slack_seconds'], 60)

    def test_exact_name_and_parent_preference(self):
        rows = [dict(stop_id='1', stop_name='Lund Centrum', stop_lat='1', stop_lon='2'),
                dict(stop_id='2', stop_name='Lund C', stop_lat='3', stop_lon='4'),
                dict(stop_id='3', stop_name='Lund C', stop_lat='5', stop_lon='6', location_type='1')]
        self.assertEqual(select_station(rows, 'Lund C')['id'], '3')

    def test_missing_station(self):
        with self.assertRaises(ValueError):
            select_station([], 'Lomma station')

    def test_derivation_preserves_source_and_removes_references(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
            source = Path(directory) / 'source.zip'
            target = Path(directory) / 'derived.zip'
            with zipfile.ZipFile(source, 'w') as z:
                z.writestr('routes.txt', 'route_id,route_type\nr1,100\nr2,1501\n')
                z.writestr('trips.txt', 'trip_id,route_id\nt1,r1\nt2,r2\n')
                z.writestr('stop_times.txt', 'trip_id,stop_id\nt1,s1\nt2,s2\n')
                z.writestr('transfers.txt', 'from_trip_id,to_trip_id\nt1,t2\n')
                z.writestr('stops.txt', 'stop_id\ns1\ns2\n')
            original = source.read_bytes()
            first = routing_feed(source, target)
            second = routing_feed(source, target)
            self.assertEqual(first, second)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(first['removed_rows']['routes.txt'], 1)
            self.assertEqual(first['removed_rows']['transfers.txt'], 1)
            with zipfile.ZipFile(target) as z:
                self.assertNotIn(b't2', z.read('trips.txt'))
                self.assertNotIn(b't2', z.read('stop_times.txt'))
