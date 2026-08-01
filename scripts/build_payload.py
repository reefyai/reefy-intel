#!/usr/bin/env python3
"""Build Reefy's initial Intel accelerator host-extension payload."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
VERSION = json.loads((ROOT / 'versions.json').read_text())['provider']['version']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reefy-build-id', required=True)
    parser.add_argument('--kernel-abi-digest', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    payload = args.output / 'common-root'
    shutil.rmtree(payload, ignore_errors=True)
    marker = payload / 'usr/share/reefy/providers/intel'
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(f'{VERSION}\n')
    args.output.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        'mksquashfs', str(payload), str(args.output / 'common.squashfs'),
        '-noappend', '-comp', 'xz', '-b', '1M', '-Xdict-size', '1M',
        '-all-root', '-all-time', '0', '-mkfs-time', '0', '-no-xattrs',
        '-no-progress',
    ], check=True)

    config = {
        'artifact_schema': 1,
        'kind': 'host-extension',
        'name': 'intel-accelerator',
        'version': VERSION,
        'architecture': 'x86_64',
        'publisher': 'reefyai',
        'reefy_build_id': args.reefy_build_id,
        'kernel_abi_digest': args.kernel_abi_digest,
    }
    (args.output / 'config.json').write_text(
        json.dumps(config, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
