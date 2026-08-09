#!/usr/bin/env python3
"""Download and verify the pinned XPU-SMI Debian packages."""

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent
VERSIONS = json.loads((ROOT / 'versions.json').read_text())


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def download(package, output):
    url = package['url']
    expected = package['sha256']
    name = Path(urlparse(url).path).name
    if not name.endswith('.deb') or not name:
        raise SystemExit(f'invalid XPU-SMI package URL: {url}')
    destination = output / name
    temporary = output / f'.{name}.tmp'
    if destination.is_file() and sha256(destination) == expected:
        return destination
    temporary.unlink(missing_ok=True)
    try:
        with urllib.request.urlopen(url) as response, temporary.open('wb') as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        actual = sha256(temporary)
        if actual != expected:
            raise SystemExit(
                f'checksum mismatch for {name}: expected {expected}, got {actual}')
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    names = set()
    for package in VERSIONS['xpu_smi']['packages']:
        path = download(package, args.output)
        if path.name in names:
            raise SystemExit(f'duplicate XPU-SMI package name: {path.name}')
        names.add(path.name)
        print(f'verified {path.name}')


if __name__ == '__main__':
    main()
