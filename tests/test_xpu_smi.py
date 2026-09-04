import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/stage_xpu_smi.py'
SPEC = importlib.util.spec_from_file_location('intel_stage_xpu_smi', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class StageXpuSmiTests(unittest.TestCase):
    def test_stages_private_runtime_wrapper_resources_and_licenses(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / 'output'

            def fake_extract(_packages, sysroot):
                binary = sysroot / 'usr/bin/xpu-smi'
                binary.parent.mkdir(parents=True)
                binary.write_text('binary')
                resources = sysroot / 'usr/share/xpum/resources/config'
                resources.mkdir(parents=True)
                (resources / 'pci.conf').write_text('pci')
                license_file = sysroot / 'usr/share/doc/xpu-smi/copyright'
                license_file.parent.mkdir(parents=True)
                license_file.write_text('license')
                libraries = sysroot / 'usr/lib/x86_64-linux-gnu'
                libraries.mkdir(parents=True)
                for library in MODULE.LIBRARIES:
                    name = (
                        f'{library}.3.0'
                        if library == 'libigsc.so.1' else library)
                    (libraries / name).write_text(library)

            with mock.patch.object(
                    MODULE, 'extract_packages', side_effect=fake_extract):
                MODULE.stage(root / 'packages', output)

            wrapper = output / 'bin/xpu-smi'
            self.assertEqual(wrapper.stat().st_mode & 0o777, 0o755)
            self.assertIn(
                'root=/run/reefy-xpu-smi', wrapper.read_text())
            self.assertEqual(
                (output / 'bin/xpu-smi.real').read_text(), 'binary')
            self.assertEqual(
                (output / 'share/xpum/resources/config/pci.conf').read_text(),
                'pci')
            self.assertTrue((output / 'lib/libze_loader.so.1').is_file())
            self.assertTrue((output / 'lib/libigsc.so.1').is_symlink())
            self.assertEqual(
                (output / 'licenses/xpu-smi/copyright').read_text(),
                'license')
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(manifest['version'], '2.0.1')


if __name__ == '__main__':
    unittest.main()
