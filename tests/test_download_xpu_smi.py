import hashlib
import importlib.util
import io
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/download_xpu_smi.py'
SPEC = importlib.util.spec_from_file_location('intel_download_xpu_smi', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DownloadXpuSmiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.data = b'synthetic package contents'
        self.package = {
            'url': 'https://packages.example.invalid/runtime.deb',
            'sha256': hashlib.sha256(self.data).hexdigest(),
        }
        self.destination = self.output / 'runtime.deb'
        self.partial = self.output / '.runtime.deb.tmp'
        self.sleep = mock.patch.object(MODULE.time, 'sleep').start()
        self.addCleanup(mock.patch.stopall)

    def http_error(self, status):
        return urllib.error.HTTPError(
            self.package['url'], status, 'synthetic HTTP error', {}, None)

    def test_transient_http_errors_retry_then_verify(self):
        for status in MODULE.RETRY_HTTP_STATUS:
            with self.subTest(status=status), mock.patch.object(
                    MODULE.urllib.request, 'urlopen', side_effect=[
                        self.http_error(status), io.BytesIO(self.data)]) as request:
                self.destination.unlink(missing_ok=True)
                self.assertEqual(
                    MODULE.download(self.package, self.output), self.destination)
                self.assertEqual(self.destination.read_bytes(), self.data)
                self.assertEqual(request.call_count, 2)
                request.assert_called_with(self.package['url'], timeout=30)
                self.assertFalse(self.partial.exists())

    def test_timeout_and_connection_failure_retry(self):
        for error in [TimeoutError('synthetic timeout'),
                      urllib.error.URLError('synthetic network outage'),
                      ConnectionResetError('synthetic connection reset')]:
            with self.subTest(error=error), mock.patch.object(
                    MODULE.urllib.request, 'urlopen', side_effect=[
                        error, io.BytesIO(self.data)]) as request:
                self.destination.unlink(missing_ok=True)
                MODULE.download(self.package, self.output)
                self.assertEqual(request.call_count, 2)
                self.assertEqual(self.destination.read_bytes(), self.data)

    def test_exhaustion_has_bounded_backoff_and_cleans_partial(self):
        self.partial.write_bytes(b'stale partial')
        with mock.patch.object(MODULE.urllib.request, 'urlopen',
                               side_effect=self.http_error(503)) as request:
            with self.assertRaises(urllib.error.HTTPError):
                MODULE.download(self.package, self.output)
        self.assertEqual(request.call_count, 4)
        self.assertEqual(self.sleep.call_args_list,
                         [mock.call(2), mock.call(4), mock.call(8)])
        self.assertFalse(self.destination.exists())
        self.assertFalse(self.partial.exists())

    def test_partial_response_is_discarded_before_retry(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.side_effect = [b'partial', TimeoutError('read timed out')]
        with mock.patch.object(MODULE.urllib.request, 'urlopen',
                               side_effect=[response, io.BytesIO(self.data)]):
            MODULE.download(self.package, self.output)
        self.assertEqual(self.destination.read_bytes(), self.data)
        self.assertFalse(self.partial.exists())

    def test_permanent_http_errors_do_not_retry(self):
        for status in [401, 403, 404]:
            with self.subTest(status=status), mock.patch.object(
                    MODULE.urllib.request, 'urlopen',
                    side_effect=self.http_error(status)) as request:
                with self.assertRaises(urllib.error.HTTPError):
                    MODULE.download(self.package, self.output)
                request.assert_called_once()
        self.sleep.assert_not_called()

    def test_checksum_failure_does_not_retry_or_replace_destination(self):
        self.destination.write_bytes(b'previous invalid cached package')
        with mock.patch.object(MODULE.urllib.request, 'urlopen',
                               return_value=io.BytesIO(b'wrong contents')) as request:
            with self.assertRaisesRegex(SystemExit, 'checksum mismatch'):
                MODULE.download(self.package, self.output)
        request.assert_called_once()
        self.sleep.assert_not_called()
        self.assertEqual(self.destination.read_bytes(),
                         b'previous invalid cached package')
        self.assertFalse(self.partial.exists())

    def test_verified_cache_avoids_network(self):
        self.destination.write_bytes(self.data)
        with mock.patch.object(MODULE.urllib.request, 'urlopen') as request:
            self.assertEqual(
                MODULE.download(self.package, self.output), self.destination)
        request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
