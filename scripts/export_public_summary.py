import json
from pathlib import Path

cases=[]
for case in ('lomma_lund','malmo_varnhem','gunnesbo_ideon'):
    source=Path('outputs/nminus')/(case+'_1.json')
    result=json.loads(source.read_text(encoding='utf-8'))
    scenarios={}
    for number,rows in result['scenarios'].items():
        reachable=[row for row in rows if row['status']=='REACHABLE']
        if not reachable:continue
        row=max(reachable,key=lambda r:r['extra_seconds'])
        reserve=[{key:leg[key] for key in ('mode','line','trip_id','start_stop_name','end_stop_name','departure','arrival','walking_seconds','wait_seconds','fixed_slack_seconds')} for leg in row['reserve']['segments']]
        scenarios[number]=dict(summary=result['summaries'][number],maximum_extra_example=dict(start=row['start'],failed_instance=row['failed_instance'],failed_leg=row['failed_leg'],notification=row['notification'],completed_elapsed_seconds=row['completed']['elapsed_seconds'],reserve_segments=reserve,total_seconds=row['total_seconds'],extra_seconds=row['extra_seconds']))
    cases.append(dict(relation=case,source_result_sha256=result['canonical_sha256'],base_metrics=result['base_metrics'],scenarios=scenarios))
output=dict(schema_version='public-nminus-summary-1',description='Extracted from validated saved results; no new routing. Not an API response or complete routing dataset.',date=result['date'],timezone=result['timezone'],window=dict(start='07:00:00',end='07:59:59',start_minutes=60),information_assumption=result['information_assumption'],horizon_seconds=result['horizon_seconds'],parameters=result['parameters'],versions=result['versions'],input_hashes={key:result['input_hashes'][key] for key in ('osm','gtfs_original','gtfs_derived','r5_jar')},code_hashes=result['code_hashes'],cases=cases)
Path('examples').mkdir(exist_ok=True)
target=Path('examples/nminus-summary.json')
target.write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
print('Exported saved public summaries:',target.stat().st_size,'bytes')
