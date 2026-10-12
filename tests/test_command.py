import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import comun


class CommandTest(unittest.TestCase):
    def test_dry_run_and_repeated_install_preserve_other_commands(self):
        with tempfile.TemporaryDirectory() as tmp, patch('pathlib.Path.home', return_value=Path(tmp)):
            destination = comun.instalar_comando(dry_run=True)
            self.assertFalse(destination.exists())
            comun.instalar_comando()
            comun.instalar_comando()
            self.assertEqual(destination.resolve(), comun.REPO / 'bin' / 'synapsis')
            self.assertTrue(os.access(destination, os.X_OK))
            destination.unlink()
            destination.write_text('another command')
            with self.assertRaises(RuntimeError):
                comun.instalar_comando()
            self.assertEqual(destination.read_text(), 'another command')

    def test_open_uses_shared_engine_and_data(self):
        namespace = runpy.run_path(str(comun.REPO / 'bin' / 'synapsis'))
        with patch.object(sys, 'argv', ['synapsis', 'abrir']), \
                patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(namespace['main'](), 0)
        self.assertEqual(run.call_args.args[0], [
            '/bin/sh', str(comun.raiz_motor() / 'bin' / 'neuromapa'), 'abrir',
        ])
        self.assertEqual(run.call_args.kwargs['env']['CLAUDE_PLUGIN_DATA'], str(comun.carpeta_datos()))
