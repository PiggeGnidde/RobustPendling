from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_osm_structure import audit


class OSMGateTests(unittest.TestCase):
    def check(self, xml):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
            path = Path(directory) / 'test.osm'
            path.write_text(xml)
            return audit(path)

    def test_complete(self):
        self.assertTrue(self.check('<osm><node id="1"/><way id="2"><nd ref="1"/></way></osm>')['passed'])

    def test_missing_reference(self):
        result = self.check('<osm><way id="2"><nd ref="1"/></way></osm>')
        self.assertFalse(result['passed'])
        self.assertEqual(result['missing_references']['way/node'], 1)

    def test_conflicting_duplicates(self):
        result = self.check('<osm><node id="1" lat="1"/><node id="1" lat="2"/></osm>')
        self.assertFalse(result['passed'])
        self.assertEqual(result['conflicting_duplicates'], 1)
