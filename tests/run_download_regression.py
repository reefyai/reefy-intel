"""Private CI runner for an unchanged-baseline/fixed HTTPS regression pair."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import unittest

from test_download_mirrors_e2e import DownloadMirrorE2E, SCRIPT

parser = argparse.ArgumentParser()
parser.add_argument('--expect-baseline', action='store_true')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
names = ['test_primary_outage_uses_verified_backup',
         'test_missing_archive_uses_next_verified_mirror']
suite = unittest.TestSuite(DownloadMirrorE2E(name) for name in names)
result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
reproduced = (len(result.errors) == 2 and not result.failures
              and {test._testMethodName for test, _ in result.errors} == set(names)
              and all('HTTP Error 503' in detail for _, detail in result.errors))
passed = reproduced if args.expect_baseline else result.wasSuccessful()
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps({'status': 'passed' if passed else 'failed',
    'scope': 'baseline reproduction' if args.expect_baseline else 'fixed HTTPS recovery',
    'source_sha256': hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
    'tests': names, 'errors': len(result.errors), 'failures': len(result.failures)}, indent=2) + '\n')
raise SystemExit(0 if passed else 1)
