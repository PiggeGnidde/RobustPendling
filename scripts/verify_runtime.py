"""Verify isolated runtime; process-local settings only, no network construction."""
import importlib
import json
import os
from pathlib import Path
import sys
import time

root = Path(__file__).resolve().parents[1]
prefix = Path(sys.prefix)
java_home = prefix / 'Library/lib/jvm'
if not (java_home / 'bin/server/jvm.dll').is_file():
    raise RuntimeError('Run this script inside the project conda environment')
# These settings affect only this verifier process and its children.
os.environ['JAVA_HOME'] = str(java_home)
os.environ['LOCALAPPDATA'] = str(root / 'cache/runtime')
os.environ['MPLCONFIGDIR'] = str(root / 'cache/matplotlib')
temporary = root / 'cache/tmp'
temporary.mkdir(parents=True, exist_ok=True)
os.environ['TEMP'] = os.environ['TMP'] = str(temporary)
sys.argv = [sys.argv[0], '--max-memory', '2G']
start = time.perf_counter()
versions = {}
for name in ('r5py', 'geopandas', 'rasterio', 'shapely', 'pyproj'):
    module = importlib.import_module(name)
    versions[name] = module.__version__
import jpype
from r5py.util import start_jvm
start_jvm()
System = jpype.JClass('java.lang.System')
actual_home = str(System.getProperty('java.home'))
if Path(actual_home).resolve() != java_home.resolve():
    raise RuntimeError('Unexpected JVM runtime')
import psutil
print(json.dumps(dict(python=sys.version, executable=sys.executable,
                      packages=versions, java_home=actual_home,
                      java_version=str(System.getProperty('java.version')),
                      java_vendor=str(System.getProperty('java.vendor')),
                      jvm_dll=jpype.getDefaultJVMPath(),
                      startup_seconds=round(time.perf_counter()-start, 2),
                      rss_bytes=psutil.Process().memory_info().rss), indent=2))
