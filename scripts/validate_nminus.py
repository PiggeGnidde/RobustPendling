"""Run the three cases twice through one persistent isolated network worker."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from transit_inputs import ROOT,atomic_json,paths,fingerprint
from review_server import digest
from jvm_diagnostics import cleanup_after_exit
from nminus_validation import validate_result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',choices=['lomma_lund','malmo_varnhem','gunnesbo_ideon'])
    p.add_argument('--config',type=Path,default=ROOT/'config/paths.toml')
    p.add_argument('--repeat',type=int,default=2,choices=[1,2])
    p.add_argument('--check-existing',action='store_true',help='Recheck completed repeated artifacts without routing')
    args=p.parse_args();out=ROOT/'outputs/nminus';out.mkdir(parents=True,exist_ok=True)
    if args.check_existing:
        checks={}
        inputs=paths(args.config)
        current_inputs={key:fingerprint(inputs[key]) for key in ('osm','gtfs')}
        legacy=json.loads((ROOT/'scripts/legacy_regressions.json').read_text(encoding='utf-8'))
        for case in ([args.case] if args.case else ['lomma_lund','malmo_varnhem','gunnesbo_ideon']):
            base=json.loads((ROOT/'outputs'/f'phase2c_{case}_1.json').read_text(encoding='utf-8'))
            results=[json.loads((out/f'{case}_{i+1}.json').read_text(encoding='utf-8')) for i in range(args.repeat)]
            for result in results:
                archived=result.get('canonical_sha256')==legacy['nminus_checksums'].get(case) and result.get('analysis_id')==legacy['analysis_identities'].get(case)
                hashes=result['input_hashes']
                if hashes['osm']!=current_inputs['osm'] or hashes['gtfs_original']!=current_inputs['gtfs']:
                    raise ValueError('Saved N−1 inputs differ from current inputs')
                for name,value in result['code_hashes'].items():
                    if fingerprint(ROOT/'scripts'/name)!=value and not archived:
                        raise ValueError('Saved N−1 routing code differs: '+name)
            checks[case]=[validate_result(r,base) for r in results]
            if len(results)==2 and results[0]!=results[1]:raise ValueError('Repeated result differs')
            if len(results)==2 and (out/f'{case}_1.geojson').read_bytes()!=(out/f'{case}_2.geojson').read_bytes():raise ValueError('Repeated GeoJSON differs')
        destination=ROOT/'outputs/planner/archive_checks.json'
        destination.parent.mkdir(parents=True,exist_ok=True)
        atomic_json(destination,checks)
        print(json.dumps(checks),flush=True);return
    summaries={};started=time.perf_counter()
    stderr_path=out/'worker.stderr.log';stdout_path=out/'worker.stdout.log'
    with stderr_path.open('w',encoding='utf-8') as stderr,stdout_path.open('w',encoding='utf-8') as stdout:
        process=subprocess.Popen([sys.executable,'-B',str(ROOT/'scripts/review_detail_worker.py'),str(args.config)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,text=True,encoding='utf-8')
        try:
            for case in ([args.case] if args.case else ['lomma_lund','malmo_varnhem','gunnesbo_ideon']):
                source=ROOT/'outputs'/f'phase2c_{case}_1.json';report=json.loads(source.read_text(encoding='utf-8'))
                identity=digest(dict(metadata=report['metadata'],metrics=report['metrics'],minutes=report['minute_observations']))
                results=[]
                for repeat in range(args.repeat):
                    output=out/f'{case}_{repeat+1}.json'
                    task=dict(command='nminus',report=str(source),analysis_id=identity,output=str(output))
                    print(f'RUN {case} {repeat+1}',flush=True)
                    process.stdin.write(json.dumps(task)+'\n');process.stdin.flush()
                    for line in process.stdout:
                        stdout.write(line);stdout.flush()
                        if line.rstrip()=='REVIEW_RESULT '+str(output):break
                    else:raise RuntimeError('Worker ended before result')
                    result=json.loads(output.read_text(encoding='utf-8'))
                    if result['status']!='OK':raise RuntimeError('N−1 validation failed; see outputs/nminus/worker.stderr.log')
                    validate_result(result,report)
                    geo=output.with_suffix('.geojson');atomic_json(geo,result['geojson'])
                    results.append(result)
                    print(f'PASS {case} {repeat+1}: {result["summaries"]}',flush=True)
                if len(results)==2 and results[0]!=results[1]:raise RuntimeError('Repeated N−1 output differs')
                if len(results)==2 and (out/f'{case}_1.geojson').read_bytes()!=(out/f'{case}_2.geojson').read_bytes():raise RuntimeError('Repeated GeoJSON differs')
                summaries[case]=dict(summaries=results[0]['summaries'],canonical_sha256=results[0]['canonical_sha256'],verification=results[0]['verification'],repeat_identical=len(results)==2)
        finally:
            if process.poll() is None:
                process.stdin.write('{"command":"stop"}\n');process.stdin.flush();process.wait(timeout=60)
    stderr=stderr_path.read_text(encoding='utf-8')
    worker=dict(pid=process.pid,exit_code=process.returncode,cleanup_after_exit=cleanup_after_exit(stderr),elapsed_seconds=time.perf_counter()-started)
    atomic_json(out/'validation.json',dict(cases=summaries,worker=worker))
    if worker['exit_code']!=0:raise RuntimeError('Worker exit failure')
    print('VALIDATION_OK '+json.dumps(worker),flush=True)


if __name__=='__main__':main()
