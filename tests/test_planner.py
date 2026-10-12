import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from datetime import datetime
import tempfile
import unittest
import zipfile
import random
from types import SimpleNamespace
from unittest.mock import Mock
from planner_core import routing_parameters,combined_nminus,deadline_result,service_coverage,date_check
from schedule_sweep import ScheduleSweep
from nminus_core import remaining_resources
from nminus_core import summarize
from nminus_validation import validate_result
from test_nminus_validation import fixture
from test_t90 import trip
from walking_links import merge_pairs
from nminus_engine import NMinusEngine


class PlannerTests(unittest.TestCase):
    def test_transfer_cache_is_separate_for_speed_and_whole_walk_budget(self):
        pairs=Mock();values=[1,800000,2,1100000]
        pairs.size.return_value=len(values);pairs.get.side_effect=lambda index:values[index]
        engine=NMinusEngine.__new__(NMinusEngine)
        engine.layer=SimpleNamespace(streetTransfers=Mock());engine.layer.streetTransfers.get.return_value=pairs
        engine.indices={'a':0};engine.ids={1:'b',2:'c'};engine.transfers_cache={}
        engine.parameters=routing_parameters(2,7200,3.6,900)
        self.assertEqual(engine.transfers('a'),{'a':0,'b':800})
        engine.parameters=routing_parameters(2,7200,4.5,1200)
        self.assertEqual(engine.transfers('a'),{'a':0,'b':640,'c':880})
        engine.parameters=routing_parameters(2,7200,3.6,900)
        self.assertEqual(engine.transfers('a'),{'a':0,'b':800})
        self.assertEqual(len(engine.transfers_cache),2)

    def test_extended_walk_links_preserve_existing_rules_and_budgets(self):
        original=[(1,250000),(2,1200000)]
        merged=merge_pairs(original,{1:100000,2:1100000,3:1000000,4:1000001,5:3000000})
        self.assertEqual(merged,[(1,250000),(2,1200000),(4,1000001),(5,3000000)])
        self.assertEqual(dict(merged)[1],250000) # existing GTFS/R5 rule is preserved
        p=routing_parameters(4,7200,4.5,1200)
        self.assertEqual(remaining_resources(300,2,p)['max_walk_seconds'],900)
        self.assertEqual(remaining_resources(300,2,p)['walk_speed_kmh'],4.5)
        for speed in (3,4.5,6):
            for budget in (600,1200,1800):
                self.assertEqual(routing_parameters(2,7200,speed,budget)['max_walk_seconds'],budget)
    def test_profile_matches_every_minute_at_first_boarding_boundaries(self):
        trips=[trip('early',[('a',600),('b',1000)]),trip('later_faster',[('a',1000),('b',1100)])]
        starts=list(range(0,1200,60))
        for rides in (1,2,3,4):
            s=ScheduleSweep(trips,{'a':120},{'b':30},lambda stop:{stop:0},routing_parameters(rides,7200))
            rows,anchors=s.profile(starts)
            self.assertEqual(rows,[s.at(t) for t in starts])
            self.assertEqual(anchors[:2],[0,7]) # first dep 600: latest start 419
            self.assertLess(len(anchors),len(starts))
            rows[0]['rides'][0]['line']='changed'
            self.assertNotEqual(rows[1]['rides'][0]['line'],'changed')

    def test_profile_direct_walk_can_be_overtaken_and_win_after_missed_bus(self):
        s=ScheduleSweep([trip('bus',[('a',600),('b',700)])],{'a':120},{'b':10},lambda stop:{stop:0},routing_parameters(2),direct_walk_seconds=600)
        starts=list(range(0,720,60));rows,_=s.profile(starts)
        self.assertEqual(rows,[s.at(t) for t in starts])
        self.assertEqual(rows[0]['rides'],[])
        self.assertEqual(rows[3]['rides'][0]['trip_id'],'bus')
        self.assertEqual(rows[7]['rides'],[]) # start 420 misses strict boarding

    def test_profile_random_graphs_walking_ties_horizon_and_unreachable(self):
        for seed in range(25):
            rng=random.Random(seed);trips=[]
            for n in range(18):
                a,b=rng.sample(list('abcde'),2);dep=rng.randrange(80,1800)
                t=trip(str(n),[(a,dep),(b,dep+rng.randrange(10,240))])
                if rng.random()<.15:t['stops'][-1]['dropoff']='1'
                trips.append(t)
            for rides in (1,2,3,4):
                p=dict(routing_parameters(rides),max_time_seconds=rng.choice((240,600,2700)))
                s=ScheduleSweep(trips,{'a':10,'b':20},{'d':20,'e':10},lambda stop:{stop:0},p,direct_walk_seconds=rng.choice((None,180,300)))
                starts=list(range(0,1500,60));rows,_=s.profile(starts)
                self.assertEqual(rows,[s.at(t) for t in starts],(seed,rides))
                self.assertEqual(s.p,p)
        with self.assertRaises(ValueError):s.profile([60,0])

    def test_two_hour_horizon_includes_long_journeys_with_original_walk_budget(self):
        trips=[trip('long', [('a',120),('b',3000)])]
        for rides in (1,2,3,4):
            old=ScheduleSweep(trips,{'a':10},{'b':20},lambda s:{s:0},routing_parameters(rides,2700))
            new=ScheduleSweep(trips,{'a':10},{'b':20},lambda s:{s:0},routing_parameters(rides,7200))
            self.assertIsNone(old.at(0)['duration_seconds'])
            self.assertEqual(new.at(0)['duration_seconds'],3080)
            self.assertEqual(new.at(0)['walking_seconds'],30)
            self.assertEqual(new.p['max_walk_seconds'],900)
        for horizon in (0,7201,7260,True,7200.0):
            with self.assertRaises(ValueError):routing_parameters(4,horizon)

    def chain(self,count):
        return [trip(str(n),[(str(n),100+n*300),(str(n+1),200+n*300)]) for n in range(count)]

    def test_three_four_legs_and_strict_budget(self):
        for count in (3,4):
            trips=self.chain(count)
            p=routing_parameters(count)
            sweep=ScheduleSweep(trips,{'0':10},{str(count):20},lambda s:{s:0},p)
            result=sweep.at(0)
            self.assertEqual(len(result['rides']),count)
            self.assertEqual(result['duration_seconds'],200+(count-1)*300+80)
            self.assertEqual(result['walking_seconds'],30)
            blocked=ScheduleSweep(trips,{'0':10},{str(count):20},lambda s:{s:0},routing_parameters(count-1))
            self.assertIsNone(blocked.at(0)['duration_seconds'])
            # Notification at leg n: completed n−1 legs remain spent.
            resources=remaining_resources(10,count-1,p)
            self.assertEqual(resources['max_rides'],1)
            failed=trips[-1]
            next_trip=trip('replacement',[(str(count-1),failed['stops'][0]['departure']+180),(str(count),failed['stops'][-1]['arrival']+180)])
            reserve=ScheduleSweep([next_trip],{str(count-1):0},{str(count):20},lambda s:{s:0},resources).at(failed['stops'][0]['departure'])
            self.assertEqual(reserve['rides'][0]['trip_id'],'replacement')
            self.assertIsNone(ScheduleSweep([], {str(count-1):0},{str(count):20},lambda s:{s:0},resources).at(0)['duration_seconds'])

    def test_backward_pruning_matches_unpruned_brute_force(self):
        for seed in range(20):
            rng=random.Random(seed);trips=[]
            for n in range(16):
                a,b=rng.sample(list('abcde'),2);departure=rng.randrange(100,1000)
                t=trip(str(n),[(a,departure),(b,departure+rng.randrange(30,180))])
                if rng.random()<.1:t['stops'][-1]['dropoff']='1'
                trips.append(t)
            def search(stop,ready,walked,rides,cap):
                candidates=[]
                if rides and stop=='e' and walked+20<=900:
                    candidates.append((ready+80,walked+20,tuple((r['id'],r['stops'][0]['id'],r['stops'][-1]['id']) for r in rides)))
                if len(rides)==cap:return candidates
                for t in trips:
                    a,b=t['stops']
                    if a['id']==stop and a['departure']>ready+60 and b['dropoff'] in ('0','3') and t not in rides:
                        candidates+=search(b['id'],b['arrival'],walked,rides+[t],cap)
                return candidates
            for cap in (3,4):
                expected=min(search('a',10,10,[],cap),default=None)
                result=ScheduleSweep(trips,{'a':10},{'e':20},lambda s:{s:0},routing_parameters(cap)).at(0)
                if expected is None:self.assertIsNone(result['duration_seconds'])
                else:
                    self.assertEqual((result['duration_seconds'],result['walking_seconds'],tuple((r['trip_id'],r['start_stop'],r['end_stop']) for r in result['rides'])),expected)

    def test_multileg_permissions_and_walking_are_not_reset(self):
        trips=self.chain(4)
        trips[2]['stops'][-1]['dropoff']='1'
        self.assertIsNone(ScheduleSweep(trips,{'0':10},{'4':20},lambda s:{s:0},routing_parameters(4)).at(0)['duration_seconds'])
        trips[2]['stops'][-1]['dropoff']='0'
        self.assertIsNone(ScheduleSweep(trips,{'0':300},{'4':300},lambda s:{s:200},routing_parameters(4)).at(-300)['duration_seconds'])
        for value in (0,5,True,1.5):
            with self.assertRaises(ValueError):routing_parameters(value)

    def test_later_fast_chain_and_transfer_slack_with_four_legs(self):
        trips=self.chain(4)
        trips[1]['stops'][-1]['arrival']=710;trips[1]['stops'][-1]['departure']=710
        fast=trip('fast',[('1',430),('2',450)])
        result=ScheduleSweep(trips+[fast],{'0':10},{'4':20},lambda s:{s:0},routing_parameters(4)).at(0)
        self.assertEqual(result['rides'][1]['trip_id'],'fast')
        trips[1]['stops'][0]['departure']=260
        trips[1]['stops'][0]['arrival']=260
        self.assertIsNone(ScheduleSweep(trips,{'0':10},{'4':20},lambda s:{s:0},routing_parameters(4)).at(0)['duration_seconds'])

    def test_earlier_prefix_cannot_prune_lexically_preferred_equal_final_arrival(self):
        trips=[trip('A',[('o',100),('x',200),('x',500),('z',600)]),
               trip('B',[('o',90),('x',150),('x',300),('z',650)]),trip('C',[('z',800),('d',900)])]
        result=ScheduleSweep(trips,{'o':10},{'d':20},lambda s:{s:0},routing_parameters(4)).at(0)
        self.assertEqual([r['trip_id'] for r in result['rides']],['A','B','C'])
        self.assertEqual(result['duration_seconds'],980)

    def test_combined_infinity_pure_walk_and_applicability(self):
        starts=['2026-10-12T07:0'+str(n)+':00+02:00' for n in range(4)]
        observations=[dict(start=starts[0],duration_seconds=100,rides=[{},{}]),dict(start=starts[1],duration_seconds=200,rides=[{}]),dict(start=starts[2],duration_seconds=50,rides=[]),dict(start=starts[3],duration_seconds=None,rides=[])]
        rows={'1':[dict(status='REACHABLE',total_seconds=400),dict(status='UNREACHABLE',total_seconds=None),dict(status='NOT_APPLICABLE'),dict(status='NOT_APPLICABLE')],
              '2':[dict(status='REACHABLE',total_seconds=500),dict(status='NOT_APPLICABLE'),dict(status='NOT_APPLICABLE'),dict(status='NOT_APPLICABLE')]}
        combined=combined_nminus(observations,rows)
        self.assertEqual([r['total_seconds'] for r in combined['minute_observations']],[500,None,50,None])
        self.assertEqual(combined['summary']['percentiles_seconds'],dict(T50=500,T90='UNREACHABLE',T99='UNREACHABLE'))
        self.assertEqual(combined['summary']['all_failures_covered_share'],.5)
        self.assertEqual(combined['minute_observations'][2]['status'],'NO_TRANSIT_LEGS')

    def test_deadline_checks_all_minutes_nonmonotonic_and_zone(self):
        obs=[dict(start=f'2026-10-12T07:0{i}:00+02:00',duration_seconds=d,rides=[]) for i,d in enumerate((100,900,50,500))]
        combined=combined_nminus(obs,{})
        result=deadline_result(obs,combined,'2026-10-12T05:04:00+00:00')
        self.assertEqual(result['baseline']['index'],2)
        self.assertEqual(result['all_single_failures']['index'],2)
        self.assertEqual(result['start_minutes_checked'],4)
        self.assertIsNone(deadline_result(obs,combined,'2026-10-12T06:00:00+02:00')['baseline'])
        with self.assertRaises(ValueError):deadline_result(obs,combined,'2026-10-12T07:04:00')

    def test_feed_date_bounds_exceptions_and_no_service(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'feed.zip'
            with zipfile.ZipFile(path,'w') as z:
                z.writestr('calendar.txt','service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\ns,1,0,0,0,0,0,0,20261001,20261031\n')
                z.writestr('calendar_dates.txt','service_id,date,exception_type\ns,20261012,2\ns,20261013,1\n')
                z.writestr('feed_info.txt','feed_start_date,feed_end_date\n20261005,20261020\n')
            coverage=service_coverage(path)
            self.assertEqual(date_check(coverage,'2026-10-12')['status'],'NO_SERVICE_DATE')
            self.assertEqual(date_check(coverage,'2026-10-13')['status'],'OK')
            self.assertEqual(date_check(coverage,'2026-11-01')['status'],'OUTSIDE_FEED_DATES')

    def test_fourth_leg_validator_keeps_three_completed_legs(self):
        result,base=fixture();row=result['scenarios']['1'][0]
        walk=result['base_itineraries'][0][0]
        def transit(n,departure,arrival,wait):
            return dict(walk,mode='BUS',walking_seconds=0,trip_id=str(n),departure=f'2026-10-12T07:{departure}:00+02:00',arrival=f'2026-10-12T07:{arrival}:00+02:00',travel_seconds=60,wait_seconds=wait,fixed_slack_seconds=0)
        baseline=[walk,transit(1,'02','03',90),transit(2,'05','06',120),transit(3,'08','09',120),transit(4,'11','12',120)]
        tail=dict(walk,departure='2026-10-12T07:13:00+02:00',arrival='2026-10-12T07:13:20+02:00',travel_seconds=20,walking_seconds=20,wait_seconds=0,fixed_slack_seconds=60)
        baseline.append(tail);result['base_itineraries']=[baseline]
        rides=[dict(trip_id=str(n),start_stop='stop',departure_seconds=25200+(2+(n-1)*3)*60) for n in range(1,5)]
        base['minute_observations'][0].update(duration_seconds=800,rides=rides)
        base['metadata']=dict(parameters=routing_parameters(4))
        reserve=[dict(walk,departure='2026-10-12T07:11:00+02:00',arrival='2026-10-12T07:11:00+02:00',travel_seconds=0,walking_seconds=0),transit('next','16','17',300),dict(tail,departure='2026-10-12T07:18:00+02:00',arrival='2026-10-12T07:18:20+02:00')]
        row.update(failed_leg=rides[-1],notification=dict(stop_id='stop',time='2026-10-12T07:11:00+02:00'),completed=dict(segments=baseline[:4],elapsed_seconds=660,wait_before_notification_seconds=120),search_end='2026-10-12T09:11:00+02:00',remaining_parameters=remaining_resources(30,3,routing_parameters(4)),reserve=dict(duration_seconds=440,segments=reserve),raw_r5_seconds=440,total_seconds=1100,extra_seconds=300)
        features=[]
        for phase,legs in [('completed',baseline[:4]),('reserve',reserve)]:
            for i,leg in enumerate(legs):
                props={k:v for k,v in leg.items() if k!='geometry'};props.update(index=0,leg_number=4,phase=phase,segment=i)
                features.append(dict(type='Feature',geometry=leg['geometry'],properties=props))
        row['geojson']['features']=features;result['scenarios']={'4':[row]};result['summaries']={'4':summarize([row])}
        self.assertEqual(validate_result(result,base)['reachable_checked'],1)
        row['remaining_parameters']['max_rides']=4
        with self.assertRaisesRegex(ValueError,'Remaining'):validate_result(result,base)


if __name__=='__main__':unittest.main()
