import copy
import json
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from analysis_contract import (point,request_grid,area_check,VERIFIED_AREAS,family,
                               structural_metrics,representatives,validate_geojson)
from analyze_t90 import parser,empty_response
from t90_core import metadata,combinations
from schedule_sweep import ScheduleSweep


def rows(values):
    return [dict(start=f'2026-10-12T07:{i:02d}:00+02:00',duration_seconds=v,
                 rides=[],transfers=0) for i,v in enumerate(values)]


class ContractTests(unittest.TestCase):
    def test_arbitrary_coordinates_and_cli_aliases(self):
        p=point(55.68,13.10,'Home')
        self.assertEqual(p,dict(lat=55.68,lon=13.10,name='Home'))
        args=parser().parse_args(['--from_lat','55.68','--from_lon','13.1',
                                '--to-lat','55.70','--to-lon','13.18','--window-length','17'])
        self.assertEqual((args.from_lat,args.to_lon,args.window_minutes),(55.68,13.18,17))
        for lat,lon in [(91,0),(0,181),(float('nan'),0),(True,0)]:
            with self.assertRaises(ValueError):point(lat,lon)

    def test_verified_extraction_not_distant_complete_way_nodes(self):
        sha=next(iter(VERIFIED_AREAS))
        p=point(55.68,13.1)
        self.assertEqual(area_check(p,p,sha)['status'],'OK')
        result=area_check(p,point(55.68,10.9),sha)
        self.assertEqual((result['status'],result['outside']),('OUTSIDE_NETWORK_AREA',['to']))
        self.assertEqual(area_check(p,p,'unknown')['status'],'NETWORK_AREA_UNVERIFIED')
        configured=dict(bbox=[13,55,14,56],osm_sha256='custom',source='verified extraction')
        self.assertEqual(area_check(p,p,'custom',configured)['status'],'OK')
        self.assertEqual(area_check(p,p,'changed',configured)['status'],'NETWORK_AREA_UNVERIFIED')
        with self.assertRaises(ValueError):area_check(p,p,'custom',dict(configured,bbox=['west',55,14,56]))

    def test_family_normalizes_modes_ignores_walk_geometry_retains_stop_order(self):
        ride=dict(mode='700',route_id='139',line='139',start_stop='a',end_stop='b')
        normalized=dict(ride,mode='BUS',route_id=' 139 ',line='Renamed line')
        self.assertEqual(family([ride])['id'],family([dict(mode='WALK',geometry='different'),normalized])['id'])
        self.assertNotEqual(family([ride])['id'],family([dict(ride,end_stop='c')])['id'])
        rail=dict(ride,mode='RAIL',route_id='train')
        self.assertNotEqual(family([ride,rail])['id'],family([rail,ride])['id'])
        self.assertTrue(family([])['pure_walk'])

    def test_buffers_shares_transfer_distribution_and_adjacent_penalty(self):
        observations=rows([100,90,400,200])
        observations[2]['rides']=[dict(mode='BUS',route_id='139',start_stop='a',end_stop='b')]
        observations[2]['transfers']=1
        m=structural_metrics(observations)
        self.assertEqual((m['buffer_90'],m['buffer_99'],m['full_range']),(300,300,310))
        self.assertEqual(m['departure_sensitivity']['seconds'],310)
        self.assertEqual(m['dominant_route_share'],.75)
        self.assertEqual(m['distinct_selected_route_families'],2)
        self.assertEqual(m['transfer_count_distribution'],{'0':3,'1':1})

    def test_missing_minutes_and_infinite_sensitivity(self):
        m=structural_metrics(rows([100,200,None]))
        self.assertEqual(m['buffer_90'],'UNREACHABLE')
        self.assertEqual(m['departure_sensitivity']['seconds'],'UNREACHABLE')
        self.assertEqual(m['route_coverage'],2/3)
        self.assertEqual(m['unreachable_count'],1)
        self.assertEqual(m['dominant_route_share_all_minutes'],2/3)
        self.assertEqual(m['unreachable_transitions'],{'reachable_to_unreachable':1})

    def test_representative_roles_coalesce_and_missing_remains_visible(self):
        selected=representatives(rows(list(range(1,61))))
        self.assertEqual([r['index'] for r in selected],[0,29,53,59])
        self.assertEqual(selected[-1]['percentile_roles'],['T99','max'])
        missing=representatives(rows([1,None]))[-1]
        self.assertEqual(missing['status'],'UNREACHABLE')
        self.assertEqual(missing['percentile_roles'],['T90','T99','max'])

    def test_geojson_is_wgs84_and_strict_json(self):
        collection=dict(type='FeatureCollection',features=[dict(type='Feature',
            geometry=dict(type='LineString',coordinates=[[13.07,55.67],[13.18,55.70]]),
            properties=dict(mode='BUS',percentile_role=['T90'],route_family='rf_test',option=0))])
        self.assertEqual(validate_geojson(json.loads(json.dumps(collection))),collection)
        invalid=copy.deepcopy(collection)
        invalid['features'][0]['geometry']['coordinates'][0]=[500000,6100000]
        with self.assertRaises(ValueError):validate_geojson(invalid)
        invalid['features'][0]['geometry']['coordinates']=[]
        with self.assertRaises(ValueError):validate_geojson(invalid)

    def test_timezones_window_edges_and_metadata_reproduction(self):
        utc=request_grid('2026-10-12','05:00:00',60,'UTC')
        local=request_grid('2026-10-12','07:00:00',60,'Europe/Stockholm')
        self.assertEqual([t.astimezone(ZoneInfo('Europe/Stockholm')) for t in utc],local)
        self.assertEqual(utc[-1].minute,59)
        for day,start,length in [('2026-10-12','23:59:00',2),('2026-10-12','07:00:01',1),
                                 ('2026-10-25','02:00:00',60),('2026-03-29','02:00:00',60)]:
            with self.assertRaises(ValueError):request_grid(day,start,length,'Europe/Stockholm')
        for length in [0,1441,1.5,True]:
            with self.assertRaises(ValueError):request_grid('2026-10-12','07:00',length,'UTC')
        with self.assertRaises(ValueError):request_grid('2026-10-12','07:00:00+02:00',1,'UTC')
        a=metadata({'osm':'hash'},{'r5py':'1.1.7'},utc,dict(origin=point(55.68,13.10)))
        b=metadata({'osm':'hash'},{'r5py':'1.1.7'},utc,dict(origin=point(55.68,13.10)))
        self.assertEqual(json.dumps(a,sort_keys=True),json.dumps(b,sort_keys=True))
        self.assertNotEqual(a['experiment_sha256'],metadata({'osm':'changed'},{'r5py':'1.1.7'},utc)['experiment_sha256'])
        self.assertEqual(empty_response('OUTSIDE_NETWORK_AREA','outside')['minute_observations'],[])

    def test_pure_walk_optimal_and_zero_transfers(self):
        result=ScheduleSweep([],{}, {},lambda _: {},direct_walk_seconds=100).at(0)
        self.assertEqual((result['duration_seconds'],result['waiting_seconds'],result['transfers']),(100,0,0))
        self.assertEqual(combinations([result])[0]['transfers'],0)
        self.assertIsNone(ScheduleSweep([],{}, {},lambda _: {},direct_walk_seconds=901).at(0)['duration_seconds'])


if __name__=='__main__':unittest.main()
