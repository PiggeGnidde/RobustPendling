"""Read-only inspection; never hydrate cloud placeholders or print raw errors."""
import argparse
import json
import sys
import xml.etree.ElementTree as ET
import zipfile

from transit_inputs import metadata_valid, paths, validate_gtfs
from gtfs_summary import summarize


def inspect(kind, path):
    if not path.is_file():
        return 'MISSING: file absent'
    stat = path.stat()
    # Windows Offline / RecallOnOpen / RecallOnDataAccess flags.
    if getattr(stat, 'st_file_attributes', 0) & (0x1000 | 0x40000 | 0x400000):
        return 'ASSUMED: cloud placeholder; content not read'
    if kind == 'osm':
        if path.suffix.lower() != '.osm':
            return f'ASSUMED: {stat.st_size} bytes; non-XML coverage requires a reader'
        low = [float('inf'), float('inf')]
        high = [float('-inf'), float('-inf')]
        count = 0
        root = None
        for event, elem in ET.iterparse(path, events=('start', 'end')):
            if root is None:
                root = elem
                if root.tag != 'osm':
                    raise ValueError('Not OSM')
            if event == 'end':
                if elem.tag == 'node':
                    point = [float(elem.attrib['lat']), float(elem.attrib['lon'])]
                    low = [min(a, b) for a, b in zip(low, point)]
                    high = [max(a, b) for a, b in zip(high, point)]
                    count += 1
                if elem.tag in ('node', 'way', 'relation'):
                    root.clear()
        if not count:
            return f'ASSUMED: {stat.st_size} bytes; no node coverage found'
        return f'VERIFIED: {stat.st_size} bytes; {count} nodes; lat/lon bbox {low} to {high}; topology untested'
    if kind == 'gtfs':
        names = validate_gtfs(path)
        status = 'VERIFIED' if metadata_valid(path) else 'ASSUMED'
        calendar = 'calendar.txt' in names or 'calendar_dates.txt' in names
        return f'{status}: ZIP tables verified; calendar present={calendar}; ' + json.dumps(summarize(path), ensure_ascii=True)
    if kind == 'lomma_archive':
        with zipfile.ZipFile(path) as archive:
            boundary = json.loads(archive.read('V4/lomma_boundary.geojson'))
            population = json.loads(archive.read('V4/lomma_population_origins.geojson'))
        return f"VERIFIED: {stat.st_size} bytes; boundary features={len(boundary['features'])}; population points={len(population['features'])}; age 20–64 unverified"
    return 'ASSUMED: configured directory; no content validation'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config')
    args = parser.parse_args(argv)
    try:
        inputs = paths(args.config)
    except Exception:
        print('MISSING: configuration unreadable')
        return 1
    failed = False
    for kind in ('osm', 'lomma_archive', 'gtfs'):
        try:
            print(f'{kind}: {inspect(kind, inputs[kind])}')
        except Exception:
            print(f'{kind}: MISSING: input could not be validated')
            failed = True
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())
