"""Recheck frozen baseline regressions with current sweep/raw R5, once each."""
import json
from pathlib import Path
import subprocess
import sys
from transit_inputs import ROOT,atomic_json
from jvm_diagnostics import cleanup_after_exit


def main():
    output=ROOT/'outputs/planner';output.mkdir(parents=True,exist_ok=True)
    errors=output/'regression.stderr.log';logs=output/'regression.stdout.log'
    summaries={}
    with errors.open('w',encoding='utf-8') as stderr,logs.open('w',encoding='utf-8') as stdout:
        process=subprocess.Popen([sys.executable,'-B',str(ROOT/'scripts/review_detail_worker.py'),str(ROOT/'config/paths.toml')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr,text=True,encoding='utf-8')
        try:
            for case in ('lomma_lund','malmo_varnhem','gunnesbo_ideon'):
                target=output/f'regression-{case}.json'
                process.stdin.write(json.dumps(dict(command='regression',report=str(ROOT/'outputs'/f'phase2c_{case}_1.json'),output=str(target),analysis_id=case))+'\n');process.stdin.flush()
                for line in process.stdout:
                    stdout.write(line);stdout.flush()
                    if line.rstrip()=='REVIEW_RESULT '+str(target):break
                else:raise RuntimeError('Regression worker ended')
                value=json.loads(target.read_text(encoding='utf-8'))
                if value['status']!='OK':raise RuntimeError('Regression mismatch; inspect local stderr log')
                summaries[case]=value
                print(case+': '+str(value['minutes_checked'])+' exact minutes pass',flush=True)
        finally:
            if process.poll() is None:
                process.stdin.write('{"command":"stop"}\n');process.stdin.flush();process.wait(timeout=60)
    cleanup=cleanup_after_exit(errors.read_text(encoding='utf-8'))
    atomic_json(output/'regressions.json',dict(cases=summaries,exit_code=process.returncode,cleanup_after_exit=cleanup))
    if process.returncode:raise RuntimeError('Regression worker failed at exit')


if __name__=='__main__':main()
