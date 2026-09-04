#!/usr/bin/env python3
"""Stage a private, host-only XPU-SMI runtime from pinned packages."""

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent
VERSIONS = json.loads((ROOT / 'versions.json').read_text())
LIBRARIES = (
    'libhwloc.so.15',
    'libigdgmm.so.12',
    'libigsc.so.1',
    'libmetee.so.6',
    'libpciaccess.so.0',
    'libze_intel_gpu.so.1',
    'libze_loader.so.1',
    'libze_tracing_layer.so.1',
)


def copy_tree(source, destination):
    if not source.is_dir():
        raise SystemExit(f'missing XPU-SMI input: {source}')
    shutil.copytree(source, destination, dirs_exist_ok=True, symlinks=True)


def package_names():
    return [
        Path(urlparse(package['url']).path).name
        for package in VERSIONS['xpu_smi']['packages']
    ]


def extract_packages(package_dir, sysroot):
    for name in package_names():
        package = package_dir / name
        if not package.is_file():
            raise SystemExit(f'missing pinned XPU-SMI package: {package}')
        subprocess.run(
            ['dpkg-deb', '--extract', str(package), str(sysroot)], check=True)


def copy_library(sysroot, name, destination):
    matches = []
    for directory in (
            sysroot / 'lib/x86_64-linux-gnu',
            sysroot / 'usr/lib/x86_64-linux-gnu'):
        matches.extend(directory.glob(f'{name}*'))
    if not matches:
        raise SystemExit(f'missing XPU-SMI runtime library: {name}')
    destination.mkdir(parents=True, exist_ok=True)
    for source in matches:
        target = destination / source.name
        if target.exists() or target.is_symlink():
            continue
        if source.is_symlink():
            target.symlink_to(source.readlink())
        else:
            shutil.copy2(source, target)
    canonical = destination / name
    if not canonical.exists() and not canonical.is_symlink():
        versioned = sorted(
            path for path in destination.glob(f'{name}*')
            if path.is_file() and not path.is_symlink())
        if not versioned:
            raise SystemExit(f'missing versioned XPU-SMI library: {name}')
        canonical.symlink_to(versioned[0].name)


def stage(package_dir, output):
    shutil.rmtree(output, ignore_errors=True)
    output.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as temporary:
        sysroot = Path(temporary) / 'sysroot'
        extract_packages(package_dir, sysroot)

        binary = sysroot / 'usr/bin/xpu-smi'
        if not binary.is_file():
            raise SystemExit(f'missing XPU-SMI binary: {binary}')
        destination = output / 'bin/xpu-smi.real'
        destination.parent.mkdir(parents=True)
        shutil.copy2(binary, destination)
        destination.chmod(0o755)

        copy_tree(
            sysroot / 'usr/share/xpum',
            output / 'share/xpum')
        for library in LIBRARIES:
            copy_library(sysroot, library, output / 'lib')

        licenses = output / 'licenses'
        for copyright_file in sorted(
                (sysroot / 'usr/share/doc').glob('*/copyright')):
            package = copyright_file.parent.name
            target = licenses / package / 'copyright'
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(copyright_file, target)

    wrapper = output / 'bin/xpu-smi'
    wrapper.write_text(
        '#!/bin/sh\n'
        'set -eu\n'
        'root=/run/reefy-xpu-smi\n'
        'export LD_LIBRARY_PATH="$root/lib"\n'
        'export ZES_ENABLE_SYSMAN="${ZES_ENABLE_SYSMAN:-1}"\n'
        'exec "$root/bin/xpu-smi.real" "$@"\n')
    wrapper.chmod(0o755)

    manifest = {
        'name': 'xpu-smi',
        'version': VERSIONS['xpu_smi']['version'],
        'packages': VERSIONS['xpu_smi']['packages'],
    }
    (output / 'manifest.json').write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--packages', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    stage(args.packages.resolve(), args.output.resolve())


if __name__ == '__main__':
    main()
