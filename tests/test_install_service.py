"""Verify installation orchestration without changing user configs or services."""
import runpy
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


CLI = Path(__file__).resolve().parent.parent / 'bin' / 'synapsis'


class InstallServiceTest(unittest.TestCase):
    def invoke(self, args, platform='linux', codes=(0, 0), systemctl='/usr/bin/systemctl'):
        namespace = runpy.run_path(str(CLI))
        with patch.object(sys, 'argv', ['synapsis', 'install', 'codex', *args]), \
                patch.object(sys, 'platform', platform), \
                patch('shutil.which', return_value=systemctl), \
                patch('subprocess.run', side_effect=[
                    subprocess.CompletedProcess([], code) for code in codes
                ]) as run:
            result = namespace['main']()
        return result, [call.args[0] for call in run.call_args_list]

    def test_install_starts_service_after_integration(self):
        result, commands = self.invoke([])
        self.assertEqual(result, 0)
        self.assertEqual(len(commands), 2)
        self.assertTrue(commands[0][1].endswith('install_codex.py'))
        self.assertTrue(commands[1][1].endswith('instalar_servicio_mapa.py'))

    def test_dry_run_does_not_start_service(self):
        result, commands = self.invoke(['--dry-run'])
        self.assertEqual(result, 0)
        self.assertTrue(all('--dry-run' in command for command in commands))

    def test_failed_integration_skips_service(self):
        result, commands = self.invoke([], codes=(1,))
        self.assertEqual(result, 1)
        self.assertEqual(len(commands), 1)

    def test_service_failure_is_reported(self):
        result, _ = self.invoke([], codes=(0, 1))
        self.assertEqual(result, 1)

    def test_other_platform_or_missing_systemctl_skips_service(self):
        for overrides in ({'platform': 'darwin'}, {'systemctl': None}):
            with self.subTest(**overrides):
                result, commands = self.invoke([], codes=(0,), **overrides)
                self.assertEqual(result, 0)
                self.assertEqual(len(commands), 1)
