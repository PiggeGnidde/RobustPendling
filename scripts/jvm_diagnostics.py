"""Instrument the pinned r5py shutdown callback without changing installed packages."""
import sys
import traceback
import json
import shutil
from pathlib import Path
from transit_inputs import ROOT


def instrument_shutdown():
    import r5py.util.jvm as jvm
    from r5py.util.config import Config
    expected=Config().TEMP_DIR.resolve()
    original=jvm.shutil.rmtree
    def traced_remove(path,*args,**kwargs):
        if Path(path).resolve()!=expected:return original(path,*args,**kwargs)
        print(f'JVM_CLEANUP_BEGIN exists={Path(path).exists()}',file=sys.stderr,flush=True)
        try:
            original(path,*args,**kwargs)
            print('JVM_CLEANUP_OK',file=sys.stderr,flush=True)
        except PermissionError as error:
            print('JVM_CLEANUP_ERROR',file=sys.stderr,flush=True)
            traceback.print_exc(file=sys.stderr)
            if getattr(error,'winerror',None)!=32:raise
            # HSQL's EPSG file is still open in this JVM. The supervisor waits
            # for this exact worker to exit, then performs the same cleanup.
            print('JVM_CLEANUP_DEFERRED '+json.dumps(str(expected)),file=sys.stderr,flush=True)
    jvm.shutil.rmtree=traced_remove


def cleanup_after_exit(stderr):
    """Delete only a verified direct child of this worktree's cache/tmp."""
    targets=[json.loads(line.split(' ',1)[1]) for line in stderr.splitlines()
             if line.startswith('JVM_CLEANUP_DEFERRED ')]
    results=[]
    root=(ROOT/'cache/tmp').resolve()
    for value in targets:
        target=Path(value).resolve()
        if target.parent!=root or not target.name.startswith('r5py'):
            raise ValueError('Refusing cleanup outside worker temporary directory')
        try:
            if target.exists():shutil.rmtree(target)
            results.append(dict(path=str(target),removed=not target.exists()))
        except OSError as error:
            results.append(dict(path=str(target),removed=False,winerror=getattr(error,'winerror',None)))
    return results
