"""Fetch static Skåne GTFS without printing credentials or network exceptions."""
import argparse
import gzip
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import tempfile
import urllib.parse
import urllib.error
import urllib.request

from transit_inputs import (ENDPOINT, api_key, atomic_json, fingerprint,
                            metadata_path, metadata_valid, paths, validate_gtfs)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the credential to a redirect destination.
        return None


def download(target, force=False, env_file=None, opener=None):
    target = Path(target)
    if target.exists() and not force:
        validate_gtfs(target)
        return 'VERIFIED: reused GTFS; metadata matched' if metadata_valid(target) else (
            'ASSUMED: reused valid ZIP; provenance missing or mismatched; use --force')
    key = api_key() if env_file is None else api_key(env_file)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=target.parent, suffix='.tmp')
    try:
        request = urllib.request.Request(ENDPOINT + '?' + urllib.parse.urlencode({'key': key}),
                                         headers={'Accept-Encoding': 'gzip'}, method='GET')
        client = opener or urllib.request.build_opener(NoRedirect())
        with os.fdopen(fd, 'wb') as stream:
            with client.open(request, timeout=60) as response:
                encoding = response.headers.get('Content-Encoding', '').strip().lower()
                if encoding not in ('', 'identity', 'gzip'):
                    raise ValueError('Unsupported content encoding')
                source = gzip.GzipFile(fileobj=response) if encoding == 'gzip' else response
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        validate_gtfs(temporary)
        meta = dict(fingerprint(temporary), source=ENDPOINT, operator='skane',
                    downloaded_at_utc=datetime.now(timezone.utc).isoformat(), schema_version=1)
        os.replace(temporary, target)
        # Two files cannot be replaced as a transaction. Readers verify the hash;
        # interrupted metadata replacement is reported as unverified provenance.
        atomic_json(metadata_path(target), meta)
        return 'VERIFIED: downloaded and validated GTFS'
    finally:
        Path(temporary).unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args(argv)
    try:
        print(download(paths(args.config)['gtfs'], args.force))
        return 0
    except urllib.error.HTTPError as error:
        # Only a numeric status is safe: reason, body and URL can contain secrets.
        print(f'MISSING: GTFS request rejected (HTTP {int(error.code)}).', file=sys.stderr)
        # Strict value allowlists prevent arbitrary echoed secrets in headers.
        allowed = {'Content-Encoding': {'gzip', 'identity'},
                   'Content-Type': {'application/json', 'application/zip', 'text/plain', 'text/html'}}
        for name, values in allowed.items():
            value = error.headers.get(name, '').lower().strip()
            if value in values:
                print(f'{name}: {value}', file=sys.stderr)
        value = error.headers.get('Content-Length', '')
        if value.isascii() and value.isdigit() and len(value) <= 12:
            print(f'Content-Length: {value}', file=sys.stderr)
        return 1
    except Exception:
        # HTTP errors can contain the entire credential-bearing URL or body.
        print('MISSING: GTFS ingestion failed; check credential, network, ZIP and file permissions.',
              file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
