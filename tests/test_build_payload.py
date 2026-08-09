import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/build_payload.py'
SPEC = importlib.util.spec_from_file_location('intel_build_payload', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BuildPayloadTests(unittest.TestCase):
    def test_emits_exact_compatible_three_layer_host_extension(self):
        with tempfile.TemporaryDirectory() as temporary, \
                mock.patch.object(MODULE.subprocess, 'run') as run:
            root = Path(temporary)
            output = root / 'output'
            modules = root / 'inputs/modules-root/lib/modules/kernel/extra/intel'
            firmware = root / 'inputs/firmware-root'
            tools = root / 'inputs/xpu-smi-root'
            modules.mkdir(parents=True)
            for name in ('i915.ko', 'xe.ko', 'intel_vpu.ko', 'kvmgt.ko'):
                (modules / name).write_text(name)
            for path in (
                    'lib/firmware/i915/test.bin',
                    'lib/firmware/xe/test.bin',
                    'lib/firmware/intel/vpu/test.bin',
                    'usr/share/licenses/intel-provider/LICENSE.xe'):
                destination = firmware / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(path)
            (tools / 'bin').mkdir(parents=True)
            (tools / 'bin/xpu-smi').write_text('wrapper')

            with mock.patch('sys.argv', [
                    str(SCRIPT),
                    '--modules-root', str(root / 'inputs/modules-root'),
                    '--firmware-root', str(firmware),
                    '--xpu-smi-root', str(tools),
                    '--kernel-release', 'kernel',
                    '--reefy-build-id', 'build-id',
                    '--kernel-abi-digest', 'sha256:abi',
                    '--output', str(output)]):
                MODULE.main()

            config = json.loads((output / 'config.json').read_text())
            self.assertEqual(config['name'], 'intel-accelerator')
            self.assertEqual(config['version'], '3')
            self.assertEqual(config['reefy_build_id'], 'build-id')
            self.assertEqual(config['kernel_abi_digest'], 'sha256:abi')
            self.assertEqual(
                config['activation_hook'], 'usr/lib/reefy/activate')
            self.assertEqual(
                (output / 'common-root/usr/share/reefy/providers/intel').read_text(),
                '3\n')
            hook = output / 'common-root/usr/lib/reefy/activate'
            self.assertEqual(hook.stat().st_mode & 0o777, 0o755)
            self.assertIn('bound_driver', hook.read_text())
            self.assertTrue(
                (output / 'common-root/lib/firmware/intel/vpu/test.bin').is_file())
            self.assertTrue(
                (output / 'common-root/usr/share/licenses/intel-provider/'
                 'LICENSE.intel_vpu').is_file())
            self.assertTrue(
                (output / 'kernel-root/lib/modules/kernel/extra/intel/xe.ko').is_file())
            self.assertEqual(
                (output / 'tools-root/bin/xpu-smi').read_text(), 'wrapper')
            self.assertEqual(run.call_count, 3)
            for call in run.call_args_list:
                command = call.args[0]
                self.assertIn('-mkfs-time', command)
                self.assertIn('-all-root', command)

    def test_rejects_incomplete_module_set(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            modules = root / 'lib/modules/kernel/extra/intel'
            modules.mkdir(parents=True)
            (modules / 'i915.ko').write_text('i915')

            with self.assertRaisesRegex(
                    SystemExit, 'missing required Intel modules'):
                MODULE.stage_kernel(root, 'kernel', root / 'out')


if __name__ == '__main__':
    unittest.main()
