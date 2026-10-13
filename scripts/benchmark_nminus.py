"""Compare N−1 execution modes on saved minutes, without a new baseline sweep."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
from analysis_contract import structural_metrics
from nminus_validation import validate_result
from planner_core import combined_nminus
from t90_core import metadata
from transit_inputs import ROOT,atomic_json
from jvm_diagnostics import cleanup_after_exit


def travel_payload(result):
    """Compare travel and geometry, excluding explicitly different audit evidence."""
    scenarios=copy.deepcopy(result['scenarios'])
    for rows in scenarios.values():
        for row in rows:row.pop('raw_r5_seconds',None)
    return dict(base_metrics=result['base_metrics'],minutes=result['minute_observations'],
        base_itineraries=result['base_itineraries'],scenarios=scenarios,
        summaries=result['summaries'],geojson=result['geojson'],
        combined=result.get('combined') or combined_nminus(result['minute_observations'],scenarios))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--minutes',type=int,default=3)
    p.add_argument('--full-validation',action='store_true',help='Run expensive R5 cross-checks first')
    p.add_argument('--expected',type=Path,help='Compare against an archived full-window N−1 result')
    p.add_argument('--config',type=Path,default=ROOT/'config/paths.toml')
    p.add_argument('--output',type=Path,default=ROOT/'outputs/nminus-performance')
    args=p.parse_args()
    report=json.loads(args.report.read_text(encoding='utf-8'))
    if not 1<=args.minutes<=len(report['minute_observations']):p.error('Minutes outside saved profile')
    if args.minutes<len(report['minute_observations']):
        from datetime import datetime
        report['minute_observations']=report['minute_observations'][:args.minutes]
        old=report['metadata']
        report['metadata']=metadata(old['input_hashes'],old['versions'],
            [datetime.fromisoformat(o['start']) for o in report['minute_observations']],old['parameters'])
        report['metrics']=structural_metrics(report['minute_observations'])
    args.output.mkdir(parents=True,exist_ok=True)
    source=args.output/'baseline.json';atomic_json(source,report)
    modes=([True] if args.full_validation else [])+[False,False]
    results=[];timings=[]
    with (args.output/'worker.stderr.log').open('w',encoding='utf-8') as stderr:
        process=subprocess.Popen([sys.executable,'-B',str(ROOT/'scripts/review_detail_worker.py'),str(args.config)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,text=True,encoding='utf-8')
        try:
            for index,full in enumerate(modes):
                destination=args.output/f'result-{index}.json'
                task=dict(command='nminus',validation=full,report=str(source),output=str(destination),analysis_id='benchmark')
                process.stdin.write(json.dumps(task)+'\n');process.stdin.flush()
                for line in process.stdout:
                    if line.startswith('REVIEW_TIMING '):
                        timings.append(dict(mode='full' if full else 'structural',**json.loads(line[len('REVIEW_TIMING '):])))
                    if line.rstrip()=='REVIEW_RESULT '+str(destination):break
                else:raise RuntimeError('Worker exited before result; see worker.stderr.log')
                result=json.loads(destination.read_text(encoding='utf-8'))
                validate_result(result,report);results.append(result)
                print(json.dumps(dict(timing=timings[-1],verification=result['verification'])),flush=True)
        finally:
            if process.poll() is None:
                process.stdin.write('{"command":"stop"}\n');process.stdin.flush();process.wait(timeout=60)
    cleanup=cleanup_after_exit((args.output/'worker.stderr.log').read_text(encoding='utf-8'))
    if results[-1]!=results[-2]:raise RuntimeError('Repeated fast results differ')
    if any(travel_payload(result)!=travel_payload(results[-1]) for result in results):
        raise RuntimeError('Fast and full travel/GeoJSON differ')
    if args.expected:
        expected=json.loads(args.expected.read_text(encoding='utf-8'))
        if travel_payload(expected)!=travel_payload(results[-1]):raise RuntimeError('Archived travel/GeoJSON differs')
    summary=dict(minutes=args.minutes,timings=timings,repeat_identical=True,travel_and_geojson_identical=True,
        full_compared=args.full_validation,archive_compared=str(args.expected) if args.expected else None,
        input_hashes=report['metadata']['input_hashes'],worker_exit_code=process.returncode,cleanup_after_exit=cleanup)
    atomic_json(args.output/'benchmark.json',summary)
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
