import json
import tempfile
import unittest
from pathlib import Path

from migrate_data import migrate


class DataMigrationTest(unittest.TestCase):
    def test_invalid_configuration_cannot_be_published_as_a_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source'
            source.mkdir()
            (source / 'config.json').write_text('not json')
            destination = Path(tmp) / 'destination'
            with self.assertRaises(ValueError):
                migrate(source, destination, apply=True)
            self.assertFalse(destination.exists())

    def test_preview_and_apply_preserve_original_and_exclude_live_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source'
            source.mkdir()
            (source / 'config.json').write_text(json.dumps({'fuentes': []}))
            (source / 'en-vivo').mkdir()
            (source / 'en-vivo/clave.txt').write_text('test-private-key')
            (source / 'historial').mkdir()
            (source / 'historial/day.json').write_text('{}')
            destination = Path(tmp) / 'new/data'
            plan = migrate(source, destination)
            self.assertFalse(plan['apply'])
            self.assertFalse(destination.parent.exists())
            migrate(source, destination, apply=True)
            self.assertEqual((destination / 'config.json').read_text(), (source / 'config.json').read_text())
            self.assertTrue((destination / 'historial/day.json').is_file())
            self.assertFalse((destination / 'en-vivo').exists())
            self.assertTrue((source / 'en-vivo/clave.txt').is_file())
            with self.assertRaises(ValueError):
                migrate(source, destination, apply=True)

    def test_symlink_and_nested_destination_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'source'
            source.mkdir()
            target = source / 'config.json'
            target.write_text('{}')
            with self.assertRaises(ValueError):
                migrate(source, source / 'nested')
            (source / 'historial').symlink_to(Path(tmp), target_is_directory=True)
            with self.assertRaises(ValueError):
                migrate(source, Path(tmp) / 'destination', apply=True)
