#!/usr/bin/env python3
"""Download and verify the pinned XPU-SMI Debian packages."""

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent
VERSIONS = json.loads((ROOT / 'versions.json').read_text())
DOWNLOAD_TIMEOUT_SECONDS = 30
DOWNLOAD_ATTEMPTS = 20
DOWNLOAD_BUDGET_SECONDS = 300
MAX_RETRY_DELAY_SECONDS = 30
RETRY_HTTP_STATUS = {408, 429, 500, 502, 503, 504}


def retryable(error):
    if isinstance(error, urllib.error.HTTPError):
        return error.code in RETRY_HTTP_STATUS
    return isinstance(error, (urllib.error.URLError, TimeoutError,
                              ConnectionError))


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
    deadline = time.monotonic() + DOWNLOAD_BUDGET_SECONDS
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(
                    url, timeout=min(DOWNLOAD_TIMEOUT_SECONDS,
                                     max(0.001, deadline - time.monotonic()))) as response, \
                    temporary.open('wb') as stream:
                while chunk := response.read(1024 * 1024):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("package download budget exhausted")
                    stream.write(chunk)
            if time.monotonic() >= deadline:
                raise TimeoutError("package download budget exhausted")
            actual = sha256(temporary)
            if actual != expected:
                raise SystemExit(
                    f'checksum mismatch for {name}: expected {expected}, got {actual}')
            temporary.replace(destination)
            return destination
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            remaining = deadline - time.monotonic()
            if (not retryable(error) or attempt == DOWNLOAD_ATTEMPTS
                    or remaining <= 0):
                raise
            delay = min(2 ** attempt, MAX_RETRY_DELAY_SECONDS, remaining)
            print(f'download {name} failed (attempt {attempt}/'
                  f'{DOWNLOAD_ATTEMPTS}): {error}; retrying in {delay}s',
                  file=sys.stderr)
            temporary.unlink(missing_ok=True)
            time.sleep(delay)
            if time.monotonic() >= deadline:
                raise
        finally:
            temporary.unlink(missing_ok=True)



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
