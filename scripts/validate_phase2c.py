"""Run each frozen network-structure case twice and verify generated artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from analysis_contract import validate_geojson
from smoke_helpers import gtfs_tables
from transit_inputs import ROOT,paths,atomic_json

CASES={
    'lomma_lund':('9021012062000000','9021012081216000'),
    'malmo_varnhem':('9021012080000000','9021012080110000'),
    'gunnesbo_ideon':('9021012081215000','9021012081125000'),
}
REPRODUCIBLE_FIELDS=('status','metadata','metrics','minute_observations','departure_jumps',
                    'representative_itineraries','route_families','alternatives','verification',
                    'combinations','components','derivation','geojson_sha256','geojson_canonical_sha256')


def validate_segments(report,geojson):
    validate_geojson(geojson)
    features=geojson['features'];expected=0
    for rep in report['representative_itineraries']:
        for option in rep['options']:
            if not option['timing_validation']['valid']:raise ValueError('Invalid itinerary timing')
            for index,segment in enumerate(option['segments']):
                matching=[f for f in features if f['properties']['representative_start']==rep['start']
                    and f['properties']['option']==option['option'] and f['properties']['segment']==index]
                if len(matching)!=1:raise ValueError('Missing or duplicate map segment')
                f=matching[0]
                if f['geometry']!=segment['geometry']:raise ValueError('Map geometry differs from itinerary')
                if any(f['properties'].get(k)!=v for k,v in segment.items() if k!='geometry'):
                    raise ValueError('Map properties differ from itinerary')
                expected+=1
    if expected!=len(features):raise ValueError('Unexpected map segments')
    return dict(valid=True,segments=expected)


def compare_results(a,b):
    differences=[field for field in REPRODUCIBLE_FIELDS if a[field]!=b[field]]
    if differences:raise ValueError('Non-reproducible fields: '+', '.join(differences))
    return dict(identical=True,fields=list(REPRODUCIBLE_FIELDS),
                excluded=['timing','worker','geojson_path (output filename only)'])


def validate_worker(worker):
    if worker['exit_code']!=0 or not worker['exited']:raise ValueError('Worker did not exit cleanly')
    if worker['jpype_shutdown_error']:raise ValueError('Unresolved JVM proxy exception')
    if any(not t['removed'] for t in worker['cleanup_after_exit']):raise ValueError('Deferred cleanup failed')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=list(CASES))
    parser.add_argument('--config',type=Path,default=ROOT/'config/paths.toml')
    args=parser.parse_args()
    stops={s['stop_id']:s for s in gtfs_tables(paths(args.config)['gtfs'])[0]}
    summaries={}
    for name in ([args.case] if args.case else CASES):
        origin,destination=[stops[i] for i in CASES[name]]
        reports=[]
        for repeat in range(2):
            output=ROOT/'outputs'/f'phase2c_{name}_{repeat+1}.json'
            command=[sys.executable,'-B',str(ROOT/'scripts/analyze_t90.py'),
                '--config',str(args.config),'--date','2026-10-12','--start','07:00:00',
                '--window-minutes','60','--timezone','Europe/Stockholm','--audit-jumps','3',
                '--from-lat',origin['stop_lat'],'--from-lon',origin['stop_lon'],
                '--to-lat',destination['stop_lat'],'--to-lon',destination['stop_lon'],
                '--from-name',origin['stop_name'],'--to-name',destination['stop_name'],'--output',str(output)]
            print(f'RUN {name} repeat={repeat+1}',flush=True)
            subprocess.run(command,check=True,stdout=subprocess.DEVNULL)
            report=json.loads(output.read_text(encoding='utf-8'))
            if report['status']!='OK':raise ValueError(f"{name}: {report['status']}")
            if report['verification']['equal_count']!=60:raise ValueError('Sweep/R5 mismatch')
            if report['verification']['network_build_count']!=1:raise ValueError('Repeated network construction')
            validate_worker(report['worker'])
            geo_path=ROOT/report['geojson_path']
            if hashlib.sha256(geo_path.read_bytes()).hexdigest()!=report['geojson_sha256']:raise ValueError('GeoJSON checksum mismatch')
            map_check=validate_segments(report,json.loads(geo_path.read_text(encoding='utf-8')))
            reports.append(report)
        reproduction=compare_results(*reports)
        report=reports[0]
        if name=='lomma_lund' and report['metrics']['percentiles_seconds']!={'T50':2177,'T90':2357,'T99':2537}:
            raise ValueError('Phase 2B regression')
        if name=='malmo_varnhem' and not report['alternatives']:raise ValueError('No verified Malmö alternatives')
        if name=='gunnesbo_ideon' and (report['metrics']['route_coverage']!=1 or '0' in report['metrics']['transfer_count_distribution']):
            raise ValueError('Transfer case has insufficient coverage or a direct selected route')
        summaries[name]=dict(metrics=report['metrics'],jumps=report['departure_jumps'],map_check=map_check,
            reproduction=reproduction,output=f'outputs/phase2c_{name}_1.json',geojson=report['geojson_path'],
            workers=[r['worker'] for r in reports])
        atomic_json(ROOT/'outputs'/f'phase2c_{name}_validation.json',summaries[name])
        print(f'PASS {name}: 60/60 raw comparisons, repeat identical, {map_check["segments"]} segments',flush=True)
    atomic_json(ROOT/'outputs/phase2c_validation.json',summaries)


if __name__=='__main__':main()
