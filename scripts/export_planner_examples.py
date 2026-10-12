"""Small planner envelopes/deadlines extracted from frozen N−1 regressions."""
import json
import argparse
from pathlib import Path
from transit_inputs import ROOT
from planner_core import combined_nminus,deadline_result
from nminus_validation import validate_result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path);parser.add_argument('--nminus',type=Path)
    args=parser.parse_args()
    examples=[]
    for case in ('lomma_lund','malmo_varnhem','gunnesbo_ideon'):
        saved=json.loads((ROOT/'outputs/nminus'/f'{case}_1.json').read_text(encoding='utf-8'))
        observations=saved['minute_observations'];combined=combined_nminus(observations,saved['scenarios'])
        examples.append(dict(relation=case,source_result_sha256=saved['canonical_sha256'],
            baseline=saved['base_metrics']['percentiles_seconds'],combined_summary=combined['summary'],
            deadline=deadline_result(observations,combined,'2026-10-12T08:00:00+02:00')))
    target=ROOT/'examples/planner-summary.json'
    target.write_text(json.dumps(dict(description='Derived from preserved saved regressions; no new routing',cases=examples),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    if bool(args.baseline)!=bool(args.nminus):raise ValueError('Supply both baseline and N−1 result')
    if args.baseline:
        baseline=json.loads(args.baseline.read_text(encoding='utf-8'));result=json.loads(args.nminus.read_text(encoding='utf-8'))
        validate_result(result,baseline)
        rows=[]
        for number,scenarios in result['scenarios'].items():
            for row in scenarios:
                if row['status']!='REACHABLE':continue
                item={key:row[key] for key in ('start','leg_number','failed_instance','notification','total_seconds','extra_seconds','remaining_parameters')}
                item['completed_elapsed_seconds']=row['completed']['elapsed_seconds']
                for phase,legs in [('completed',row['completed']['segments']),('reserve',row['reserve']['segments'])]:
                    item[phase]=[{k:v for k,v in leg.items() if k not in ('geometry','geometry_connectors_m')} for leg in legs]
                rows.append(item)
        example=dict(description='Verified real four-leg completed+reserve trip; one exact start minute, not a population sample',
            parameters=baseline['metadata']['parameters'],versions=result['versions'],input_hashes={k:v for k,v in result['input_hashes'].items() if k!='code'},code_hashes=result['code_hashes'],source_result_sha256=result['canonical_sha256'],
            baseline=baseline['metrics'],combined=result['combined'],scenarios=rows)
        (ROOT/'examples/planner-four-leg-reserve.json').write_text(json.dumps(example,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('Exported planner examples')


if __name__=='__main__':main()
