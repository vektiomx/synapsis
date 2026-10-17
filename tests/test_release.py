import hashlib
import json
import runpy
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent


class ReleaseTest(unittest.TestCase):
    def test_archive_is_reproducible_complete_and_has_verifiable_manifest(self):
        build=runpy.run_path(str(ROOT/'tools/build_release.py'))['build']
        with tempfile.TemporaryDirectory() as tmp:
            first,second=Path(tmp)/'one.zip',Path(tmp)/'two.zip'
            report=build(first)
            build(second)
            self.assertEqual(first.read_bytes(),second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                names=archive.namelist()
                self.assertIn('synopsis/LICENSE',names)
                self.assertIn('synopsis/engine/model_provider.py',names)
                self.assertFalse(any('/__pycache__/' in n or '/.git/' in n or '/.synopsis/' in n for n in names))
                manifest=json.loads(archive.read('synopsis/SHA256SUMS.json'))
                self.assertEqual(len(manifest),report['files'])
                for name,digest in manifest.items():
                    self.assertEqual(hashlib.sha256(archive.read('synopsis/'+name)).hexdigest(),digest)
                self.assertTrue((archive.getinfo('synopsis/bin/synopsis').external_attr>>16)&0o111)
                self.assertTrue((archive.getinfo('synopsis/install-macos.command').external_attr>>16)&0o111)
                self.assertIn('synopsis/install-windows.cmd',names)
                self.assertIn('synopsis/desktop_map.py',names)
