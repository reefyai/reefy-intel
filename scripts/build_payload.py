#!/usr/bin/env python3
"""Build Reefy's Intel firmware and exact-kernel provider layers."""

import argparse
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
VERSION = json.loads((ROOT / 'versions.json').read_text())['provider']['version']
REQUIRED_MODULES = {'i915', 'xe', 'intel_vpu'}


def copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_tree(source, destination):
    if not source.is_dir():
        raise SystemExit(f'missing Intel provider input: {source}')
    shutil.copytree(source, destination, dirs_exist_ok=True, symlinks=True)


def stage_common(firmware_root, root):
    copy_tree(
        firmware_root / 'lib/firmware/i915',
        root / 'lib/firmware/i915')
    copy_tree(
        firmware_root / 'lib/firmware/xe',
        root / 'lib/firmware/xe')
    copy_tree(
        firmware_root / 'lib/firmware/intel/vpu',
        root / 'lib/firmware/intel/vpu')

    licenses = firmware_root / 'usr/share/licenses/intel-provider'
    if licenses.is_dir():
        copy_tree(licenses, root / 'usr/share/licenses/intel-provider')
    copy(
        ROOT / 'licenses/LICENSE.intel_vpu',
        root / 'usr/share/licenses/intel-provider/LICENSE.intel_vpu')

    marker = root / 'usr/share/reefy/providers/intel'
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(f'{VERSION}\n')
    hook = root / 'usr/lib/reefy/activate'
    copy(ROOT / 'scripts/activate', hook)
    hook.chmod(0o755)


def stage_kernel(modules_root, kernel_release, root):
    source = modules_root / 'lib/modules' / kernel_release / 'extra/intel'
    modules = sorted(source.glob('*.ko*'))
    present = {
        path.name.split('.ko', 1)[0]
        for path in modules
    }
    missing = REQUIRED_MODULES - present
    if missing:
        raise SystemExit(
            'missing required Intel modules: ' + ', '.join(sorted(missing)))
    destination = root / 'lib/modules' / kernel_release / 'extra/intel'
    for module in modules:
        copy(module, destination / module.name)


def squash(source, destination):
    subprocess.run([
        'mksquashfs', str(source), str(destination),
        '-noappend', '-comp', 'xz', '-b', '1M', '-Xdict-size', '1M',
        '-all-root', '-all-time', '0', '-mkfs-time', '0', '-no-xattrs',
        '-no-progress',
    ], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--modules-root', type=Path, required=True)
    parser.add_argument('--firmware-root', type=Path, required=True)
    parser.add_argument('--kernel-release', required=True)
    parser.add_argument('--reefy-build-id', required=True)
    parser.add_argument('--kernel-abi-digest', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    common = args.output / 'common-root'
    kernel = args.output / 'kernel-root'
    shutil.rmtree(common, ignore_errors=True)
    shutil.rmtree(kernel, ignore_errors=True)
    stage_common(args.firmware_root.resolve(), common)
    stage_kernel(
        args.modules_root.resolve(), args.kernel_release, kernel)
    squash(common, args.output / 'common.squashfs')
    squash(kernel, args.output / 'kernel.squashfs')

    config = {
        'artifact_schema': 1,
        'kind': 'host-extension',
        'name': 'intel-accelerator',
        'version': VERSION,
        'architecture': 'x86_64',
        'publisher': 'reefyai',
        'activation_hook': 'usr/lib/reefy/activate',
        'reefy_build_id': args.reefy_build_id,
        'kernel_abi_digest': args.kernel_abi_digest,
    }
    (args.output / 'config.json').write_text(
        json.dumps(config, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
