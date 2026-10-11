"""Isolated, instrumented reproduction of r5py's Python Java shutdown hook."""
import argparse
import os
from pathlib import Path
import sys
import traceback
from transit_inputs import ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--explicit',action='store_true')
    parser.add_argument('--epsg',action='store_true',help='Open the GeoTools EPSG database')
    args=parser.parse_args()
    os.environ['JAVA_HOME']=str(Path(sys.prefix)/'Library/lib/jvm')
    os.environ['LOCALAPPDATA']=str(ROOT/'cache/runtime')
    os.environ['APPDATA']=str(ROOT/'cache/config')
    os.environ['TEMP']=os.environ['TMP']=str(ROOT/'cache/tmp')
    sys.argv=[sys.argv[0],'--verbose','--max-memory','1G']
    import r5py
    import jpype
    from r5py.util.config import Config
    import r5py.util.jvm as jvm
    original=jvm.shutil.rmtree
    def traced_remove(path,*arguments,**keywords):
        print(f'HOOK_ENTER exists={Path(path).exists()}',flush=True)
        try:
            original(path,*arguments,**keywords)
            print('HOOK_SUCCESS',flush=True)
        except BaseException:
            traceback.print_exc()
            raise
    jvm.shutil.rmtree=traced_remove
    if args.epsg:jpype.JClass('org.geotools.referencing.CRS').decode('EPSG:4326')
    print(f'BEFORE_EXIT jvm_started={jpype.isJVMStarted()} temp_exists={Config().TEMP_DIR.exists()}',flush=True)
    if args.explicit:
        print('EXPLICIT_SHUTDOWN_BEGIN',flush=True)
        jpype.shutdownJVM()
        print(f'EXPLICIT_SHUTDOWN_END jvm_started={jpype.isJVMStarted()} temp_exists={Config().TEMP_DIR.exists()}',flush=True)


if __name__=='__main__':main()
