"""Standard-library input helpers. No raw exception text crosses the CLI boundary."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = 'https://opendata.samtrafiken.se/gtfs/skane/skane.zip'
REQUIRED = {'agency.txt', 'stops.txt', 'routes.txt', 'trips.txt', 'stop_times.txt'}


def paths(config=None):
    source = Path(config) if config else ROOT / 'config/paths.example.toml'
    values = tomllib.loads(source.read_text(encoding='utf-8'))['paths']
    return {key: (Path(value) if Path(value).is_absolute() else ROOT / value)
            for key, value in values.items()}


def api_key(env_file=ROOT / '.env'):
    # Non-empty process environment takes precedence; never echo either source.
    value = os.environ.get('TRAFIKLAB_API_KEY', '').strip()
    if not value and Path(env_file).exists():
        for line in Path(env_file).read_text(encoding='utf-8-sig').splitlines():
            key, sep, candidate = line.strip().partition('=')
            if sep and key == 'TRAFIKLAB_API_KEY':
                value = candidate.strip().strip('\"\'')
    if not value:
        raise ValueError('Missing credential')
    return value


def validate_gtfs(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if not REQUIRED.issubset(names) or len(names) != len(set(names)):
            raise ValueError('Invalid GTFS structure')
        if any(archive.getinfo(name).file_size == 0 for name in REQUIRED):
            raise ValueError('Empty required table')
        if archive.testzip() is not None:
            raise ValueError('Corrupt archive')
    return sorted(names)


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'size_bytes': Path(path).stat().st_size, 'sha256': digest.hexdigest()}


def metadata_path(path):
    return Path(str(path) + '.metadata.json')


def metadata_valid(path):
    try:
        meta = json.loads(metadata_path(path).read_text(encoding='utf-8'))
        return (all(meta.get(k) == v for k, v in fingerprint(path).items())
                and meta.get('source') == ENDPOINT and meta.get('operator') == 'skane'
                and isinstance(meta.get('downloaded_at_utc'), str))
    except (OSError, ValueError, TypeError):
        return False


def atomic_json(path, value):
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
