"""Real HTTPS download/fallback regression with synthetic packages and a test CA."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import ssl
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

SCRIPT = Path(os.environ.get('INTEL_DOWNLOAD_SCRIPT',
    str(Path(__file__).resolve().parents[1] / 'scripts/download_xpu_smi.py')))
SPEC = importlib.util.spec_from_file_location('mirror_download_under_test', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
REAL_URLOPEN = urllib.request.urlopen


class DownloadMirrorE2E(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = b'synthetic pinned runtime package'
        self.requests = []
        self.responses = {'/primary/runtime.deb': (503, b'unavailable'),
                          '/archive/runtime.deb': (200, self.data),
                          '/backup/runtime.deb': (200, self.data)}
        config = self.root / 'certificate.conf'
        config.write_text('[req]\nprompt=no\ndistinguished_name=dn\nx509_extensions=ext\n'
                          '[dn]\nCN=localhost\n[ext]\nsubjectAltName=DNS:localhost,IP:127.0.0.1\n'
                          'basicConstraints=critical,CA:TRUE\n')
        self.certificate = self.root / 'certificate.pem'
        key = self.root / 'key.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-days', '1', '-config', str(config), '-keyout', str(key),
                        '-out', str(self.certificate)], check=True, capture_output=True)
        key.chmod(0o600)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.requests.append(self.path)
                status, body = owner.responses.get(self.path, (404, b'missing'))
                self.send_response(status)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.certificate, key)
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval': .01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        base = f'https://localhost:{self.server.server_port}'
        self.urls = [base + path for path in self.responses]
        self.package = {'url': self.urls[0], 'sha256': hashlib.sha256(self.data).hexdigest()}
        self.output = self.root / 'output'
        self.output.mkdir()
        # Resolver substitution confines all traffic to this disposable HTTPS
        # fixture. The real urllib client, TLS, HTTP and filesystem path run.
        resolver = mock.patch.object(MODULE, 'package_sources', return_value=self.urls,
                                     create=True)
        resolver.start()
        self.addCleanup(resolver.stop)
        sleep = mock.patch.object(MODULE.time, 'sleep', return_value=None)
        sleep.start()
        self.addCleanup(sleep.stop)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def trusted_download(self):
        context = ssl.create_default_context(cafile=str(self.certificate))
        def request(url, timeout):
            return REAL_URLOPEN(url, timeout=timeout, context=context)
        with mock.patch.object(MODULE.urllib.request, 'urlopen', side_effect=request):
            return MODULE.download(self.package, self.output)

    def test_primary_outage_uses_verified_backup(self):
        result = self.trusted_download()
        self.assertEqual(result.read_bytes(), self.data)
        self.assertEqual(self.requests, ['/primary/runtime.deb', '/archive/runtime.deb'])
        self.assertFalse((self.output / '.runtime.deb.tmp').exists())

    def test_missing_archive_uses_next_verified_mirror(self):
        self.responses['/archive/runtime.deb'] = (404, b'pruned version')
        result = self.trusted_download()
        self.assertEqual(result.read_bytes(), self.data)
        self.assertEqual(self.requests, list(self.responses))

    def test_wrong_mirror_hash_never_replaces_existing_file(self):
        destination = self.output / 'runtime.deb'
        destination.write_bytes(b'previous invalid cached file')
        self.responses['/archive/runtime.deb'] = (200, b'wrong package bytes')
        with self.assertRaisesRegex(SystemExit, 'checksum mismatch'):
            self.trusted_download()
        self.assertEqual(destination.read_bytes(), b'previous invalid cached file')
        self.assertEqual(self.requests, ['/primary/runtime.deb', '/archive/runtime.deb'])
        self.assertFalse((self.output / '.runtime.deb.tmp').exists())

    def test_untrusted_tls_certificate_is_rejected(self):
        with self.assertRaises(urllib.error.URLError) as error:
            MODULE.download(self.package, self.output)
        self.assertIn('CERTIFICATE_VERIFY_FAILED', str(error.exception))
        self.assertEqual(list(self.output.iterdir()), [])
        self.assertEqual(self.requests, [])


class MirrorSourceTests(unittest.TestCase):
    def test_only_known_https_ubuntu_snapshot_paths_get_backups(self):
        source = 'https://snapshot.ubuntu.com/ubuntu/20260101T000000Z/pool/main/p/pkg/runtime.deb'
        urls = MODULE.package_sources(source)
        self.assertEqual(urls[0], source)
        self.assertEqual(urls[1:], [
            'https://archive.ubuntu.com/ubuntu/pool/main/p/pkg/runtime.deb',
            'https://azure.archive.ubuntu.com/ubuntu/pool/main/p/pkg/runtime.deb',
            'https://us-east-1.ec2.archive.ubuntu.com/ubuntu/pool/main/p/pkg/runtime.deb'])
        for other in [source.replace('https:', 'http:'),
                      source.replace('snapshot.ubuntu.com', 'snapshot.ubuntu.com.example.invalid'),
                      source + '?changed=true', source.replace('/pool/', '/private/'),
                      'https://packages.example.invalid/runtime.deb']:
            self.assertEqual(MODULE.package_sources(other), [other])

    def test_original_pinned_package_descriptor_is_not_mutated(self):
        before = json.dumps(MODULE.VERSIONS, sort_keys=True)
        for package in MODULE.VERSIONS['xpu_smi']['packages']:
            MODULE.package_sources(package['url'])
        self.assertEqual(json.dumps(MODULE.VERSIONS, sort_keys=True), before)
