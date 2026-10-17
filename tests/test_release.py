import hashlib
import json
import runpy
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

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

    def test_archive_excludes_developer_state_but_keeps_harness_templates(self):
        build=runpy.run_path(str(ROOT/'tools/build_release.py'))['build']
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/'source';base.mkdir()
            public=('LICENSE','README.md','bin/synopsis','engine/bin/synopsis','mcp_entry.py',
                    'AGENTS.md','.agents/docs/tasks/README.md','.agents/docs/progress/README.md')
            private=('.agents/docs/tasks/current.md','.agents/docs/tasks/backlog.md',
                     '.agents/docs/progress/decisions.md','.agents/docs/progress/history.md',
                     '.agents/docs/progress/history_2026-10.md')
            for name in public+private:
                path=base/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('synthetic state')
            output=Path(tmp)/'release.zip'
            with patch.dict(build.__globals__,ROOT=base):build(output)
            with zipfile.ZipFile(output) as archive:
                names=set(archive.namelist())
                self.assertTrue(all('synopsis/'+name in names for name in public))
                self.assertFalse(any('synopsis/'+name in names for name in private))
                manifest=json.loads(archive.read('synopsis/SHA256SUMS.json'))
                self.assertFalse(set(private)&manifest.keys())
