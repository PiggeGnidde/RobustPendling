"""Read-only XML structural gate before an R5 smoke test; no deduplication."""
from collections import Counter
import json
import sys
import xml.etree.ElementTree as ET
from transit_inputs import paths


def audit(path):
    ids = {kind: set() for kind in ('node', 'way', 'relation')}
    counts = Counter()
    references = []
    signatures = {}
    conflicts = 0
    for _, element in ET.iterparse(path, events=('end',)):
        if element.tag not in ids:
            continue
        kind = element.tag
        identity = int(element.attrib['id'])
        counts[kind] += 1
        ids[kind].add(identity)
        # Way node order and relation member order matter; tag order does not.
        signature = (sorted(element.attrib.items()),
                     [(c.tag, sorted(c.attrib.items())) for c in element if c.tag != 'tag'],
                     sorted(tuple(sorted(c.attrib.items())) for c in element if c.tag == 'tag'))
        key = (kind, identity)
        if key in signatures and signatures[key] != signature:
            conflicts += 1
        signatures[key] = signature
        if kind == 'way':
            references.extend(('way/node', 'node', int(c.attrib['ref'])) for c in element.findall('nd'))
        elif kind == 'relation':
            references.extend(('relation/' + c.attrib['type'], c.attrib['type'], int(c.attrib['ref']))
                              for c in element.findall('member'))
        element.clear()
    missing = Counter(label for label, kind, identity in references if identity not in ids[kind])
    duplicates = {kind: counts[kind] - len(ids[kind]) for kind in ids}
    return dict(objects=dict(counts), unique_ids={k: len(v) for k, v in ids.items()},
                duplicates=duplicates, conflicting_duplicates=conflicts,
                missing_references=dict(missing),
                passed=not any(duplicates.values()) and not missing)


if __name__ == '__main__':
    result = audit(paths()['osm'])
    print(json.dumps(result, indent=2))
    sys.exit(0 if result['passed'] else 1)
