import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import download_gtfs_skane as downloader
import transit_inputs as inputs
import inspect_inputs


def feed(missing=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name in inputs.REQUIRED - {missing}:
            archive.writestr(name, 'id\n1\n')
    return buffer.getvalue()


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=inputs.ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / 'skane.zip'

    def client(self, payload):
        class Client:
            def open(self, request, timeout):
                return io.BytesIO(payload)
        return Client()

    def test_key_sources(self):
        env = Path(self.tmp.name) / '.env'
        env.write_text('TRAFIKLAB_API_KEY="file-secret"\n', encoding='utf-8')
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(inputs.api_key(env), 'file-secret')
        with patch.dict(os.environ, {'TRAFIKLAB_API_KEY': 'environment-secret'}):
            self.assertEqual(inputs.api_key(env), 'environment-secret')

    def test_missing_key_safe(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                inputs.api_key(Path(self.tmp.name) / 'absent')

    def test_metadata_success_and_reuse(self):
        payload = feed()
        with patch.dict(os.environ, {'TRAFIKLAB_API_KEY': 'secret-key'}):
            result = downloader.download(self.target, opener=self.client(payload))
        self.assertIn('VERIFIED', result)
        meta_file = inputs.metadata_path(self.target)
        raw = meta_file.read_text()
        meta = json.loads(raw)
        self.assertNotIn('secret-key', raw)
        self.assertNotIn('?key=', raw)
        self.assertEqual(meta['sha256'], hashlib.sha256(payload).hexdigest())
        self.assertEqual(meta['size_bytes'], len(payload))
        self.assertIn('+00:00', meta['downloaded_at_utc'])
        with patch.object(downloader, 'api_key', side_effect=AssertionError('should not read key')):
            self.assertIn('reused', downloader.download(self.target))
        self.assertEqual(raw, meta_file.read_text())
        self.target.write_bytes(payload + b'changed')
        self.assertFalse(inputs.metadata_valid(self.target))

    def test_zip_validation(self):
        for payload in (b'not zip', feed('trips.txt')):
            self.target.write_bytes(payload)
            with self.assertRaises((ValueError, zipfile.BadZipFile)):
                inputs.validate_gtfs(self.target)
        self.target.write_bytes(feed())
        self.assertTrue(inputs.REQUIRED.issubset(inputs.validate_gtfs(self.target)))

    def test_failed_force_preserves_existing(self):
        self.target.write_bytes(feed())
        before = self.target.read_bytes()
        with patch.dict(os.environ, {'TRAFIKLAB_API_KEY': 'secret'}):
            with self.assertRaises(zipfile.BadZipFile):
                downloader.download(self.target, force=True, opener=self.client(b'invalid'))
        self.assertEqual(before, self.target.read_bytes())
        self.assertEqual(list(Path(self.tmp.name).glob('*.tmp')), [])

    def test_exception_url_and_body_never_printed(self):
        secret = 'sensitive/key?value'
        for error in (RuntimeError('https://host/?key=' + secret),
                      OSError('server response contains ' + secret)):
            output = io.StringIO()
            with patch.object(downloader, 'download', side_effect=error), \
                 contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                self.assertEqual(downloader.main([]), 1)
            self.assertNotIn(secret, output.getvalue())
            self.assertNotIn('https://', output.getvalue())

    def test_metadata_interruption_is_detected(self):
        with patch.dict(os.environ, {'TRAFIKLAB_API_KEY': 'secret'}), \
             patch.object(downloader, 'atomic_json', side_effect=OSError('fail')):
            with self.assertRaises(OSError):
                downloader.download(self.target, opener=self.client(feed()))
        self.assertFalse(inputs.metadata_valid(self.target))
        self.assertIn('ASSUMED', downloader.download(self.target))

    def test_inspection_small_osm_and_missing(self):
        path = Path(self.tmp.name) / 'small.osm'
        self.assertIn('MISSING', inspect_inputs.inspect('osm', path))
        path.write_text('<osm><node lat="55.7" lon="13.1"/></osm>')
        result = inspect_inputs.inspect('osm', path)
        self.assertIn('VERIFIED', result)
        self.assertIn('[55.7, 13.1]', result)

    def test_redirects_blocked(self):
        self.assertIsNone(downloader.NoRedirect().redirect_request(
            None, None, 302, '', {}, 'https://other.example'))

    def test_force_replaces_feed_and_metadata(self):
        self.target.write_bytes(feed())
        payload = feed() + b'new-generation'
        with patch.dict(os.environ, {'TRAFIKLAB_API_KEY': 'secret'}):
            downloader.download(self.target, force=True, opener=self.client(payload))
        self.assertEqual(self.target.read_bytes(), payload)
        self.assertTrue(inputs.metadata_valid(self.target))

    def test_network_failure_leaves_no_temp_or_target(self):
        class BrokenClient:
            def open(self, request, timeout):
                raise OSError('credential-bearing error')
        with patch.dict(os.environ, {'TRAFIKLAB_API_KEY': 'secret'}):
            with self.assertRaises(OSError):
                downloader.download(self.target, opener=BrokenClient())
        self.assertFalse(self.target.exists())
        self.assertEqual(list(Path(self.tmp.name).glob('*.tmp')), [])


if __name__ == '__main__':
    unittest.main()
