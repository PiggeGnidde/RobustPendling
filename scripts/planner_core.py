"""Planner parameters, data coverage, N−1 envelope and deadlines; no JVM."""
import csv
from datetime import datetime,timedelta
import io
import zipfile
from t90_core import PARAMETERS,statistics


def routing_parameters(max_rides=2):
    if isinstance(max_rides,bool) or not isinstance(max_rides,int) or not 1<=max_rides<=4:
        raise ValueError('Choose 1 to 4 transit legs')
    return dict(PARAMETERS,max_rides=max_rides)


def service_coverage(feed):
    with zipfile.ZipFile(feed) as archive:
        def rows(name):
            return list(csv.DictReader(io.StringIO(archive.read(name).decode('utf-8-sig')))) if name in archive.namelist() else []
        calendar=rows('calendar.txt');exceptions=rows('calendar_dates.txt');info=rows('feed_info.txt')
        zones={r['agency_timezone'] for r in rows('agency.txt')}
        dates=[r[k] for r in calendar for k in ('start_date','end_date')]+[r['date'] for r in exceptions]
        starts=[r.get('feed_start_date') for r in info if r.get('feed_start_date')]
        ends=[r.get('feed_end_date') for r in info if r.get('feed_end_date')]
        return dict(calendar=calendar,exceptions=exceptions,feed_timezone=next(iter(zones)) if len(zones)==1 else None,
            first=max([min(dates)]+starts) if dates else None,
            last=min([max(dates)]+ends) if dates else None)


def date_check(coverage,day):
    instant=datetime.fromisoformat(day);value=instant.strftime('%Y%m%d')
    if not coverage['first'] or not coverage['first']<=value<=coverage['last']:
        return dict(status='OUTSIDE_FEED_DATES',message='Datumet ligger utanför den frysta tidtabellens datatäckning.')
    weekday=instant.strftime('%A').lower()
    active={r['service_id'] for r in coverage['calendar'] if r['start_date']<=value<=r['end_date'] and r[weekday]=='1'}
    for row in coverage['exceptions']:
        if row['date']==value:
            if row['exception_type']=='1':active.add(row['service_id'])
            else:active.discard(row['service_id'])
    return dict(status='OK' if active else 'NO_SERVICE_DATE',message='' if active else 'Ingen aktiv trafikdag i denna feed.')


def combined_nminus(observations,scenarios):
    rows=[]
    for index,base in enumerate(observations):
        count=len(base.get('rides',[]))
        applicable=[scenarios[str(number)][index] for number in range(1,count+1)]
        if base['duration_seconds'] is None:
            total=None;status='BASE_UNREACHABLE';worst=None
        elif not count:
            total=base['duration_seconds'];status='NO_TRANSIT_LEGS';worst=None
        elif any(row['status']!='REACHABLE' for row in applicable):
            total=None;status='UNREACHABLE';worst=next(n for n,r in enumerate(applicable,1) if r['status']!='REACHABLE')
        else:
            worst=max(range(1,count+1),key=lambda n:applicable[n-1]['total_seconds'])
            total=applicable[worst-1]['total_seconds'];status='REACHABLE'
        rows.append(dict(index=index,start=base['start'],total_seconds=total,status=status,worst_leg=worst,transit_leg_count=count))
    summary=statistics([row['total_seconds'] for row in rows])
    summary.update(all_failures_covered_share=summary['route_coverage'],
        no_transit_leg_count=sum(r['status']=='NO_TRANSIT_LEGS' for r in rows),
        definition='Worst single-leg cancellation of chosen optimal baseline; unreachable is positive infinity; pure walk uses baseline')
    return dict(minute_observations=rows,summary=summary)


def deadline_result(observations,combined,deadline):
    instant=datetime.fromisoformat(deadline)
    if instant.tzinfo is None:raise ValueError('Deadline needs an explicit timezone offset')
    def latest(rows,key):
        eligible=[]
        for index,row in enumerate(rows):
            start=datetime.fromisoformat(observations[index]['start'])
            if row[key] is not None and start+timedelta(seconds=row[key])<=instant:
                eligible.append(dict(index=index,start=observations[index]['start'],arrival=(start+timedelta(seconds=row[key])).isoformat()))
        return max(eligible,key=lambda row:datetime.fromisoformat(row['start'])) if eligible else None
    return dict(deadline=deadline,baseline=latest(observations,'duration_seconds'),
        all_single_failures=latest(combined['minute_observations'],'total_seconds'),
        start_minutes_checked=len(observations),condition='Schedule-based conditions, no on-time probability; every start minute checked')
