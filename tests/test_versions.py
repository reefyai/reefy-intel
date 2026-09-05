#!/usr/bin/env python3

import json
import unittest
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]


class VersionsTests(unittest.TestCase):
    def test_xpu_smi_packages_are_pinned_and_unique(self):
        versions = json.loads((ROOT / 'versions.json').read_text())
        packages = versions['xpu_smi']['packages']
        urls = [package['url'] for package in packages]

        self.assertEqual(len(urls), len(set(urls)))
        for package in packages:
            self.assertEqual(urlparse(package['url']).scheme, 'https')
            self.assertRegex(package['sha256'], r'^[0-9a-f]{64}$')

    def test_xpu_smi_does_not_depend_on_ephemeral_ppa_files(self):
        versions = json.loads((ROOT / 'versions.json').read_text())
        urls = [package['url'] for package in versions['xpu_smi']['packages']]

        self.assertFalse(any('ppa.launchpadcontent.net' in url for url in urls))
        self.assertFalse(any('archive.ubuntu.com' in url for url in urls))


if __name__ == '__main__':
    unittest.main()
