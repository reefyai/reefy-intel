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
    def test_emits_exact_compatible_host_extension(self):
        with tempfile.TemporaryDirectory() as temporary, \
                mock.patch.object(MODULE.subprocess, 'run') as run:
            output = Path(temporary) / 'output'
            with mock.patch('sys.argv', [
                    str(SCRIPT), '--reefy-build-id', 'build-id',
                    '--kernel-abi-digest', 'sha256:abi',
                    '--output', str(output)]):
                MODULE.main()

            config = json.loads((output / 'config.json').read_text())
            self.assertEqual(config['name'], 'intel-accelerator')
            self.assertEqual(config['reefy_build_id'], 'build-id')
            self.assertEqual(config['kernel_abi_digest'], 'sha256:abi')
            self.assertEqual(
                (output / 'common-root/usr/share/reefy/providers/intel').read_text(),
                '1\n')
            run.assert_called_once()


if __name__ == '__main__':
    unittest.main()
