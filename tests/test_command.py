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
            self.assertEqual(destination.resolve(), comun.REPO / 'bin' / 'synopsis')
            self.assertTrue(os.access(destination, os.X_OK))
            destination.unlink()
            destination.write_text('another command')
            with self.assertRaises(RuntimeError):
                comun.instalar_comando()
            self.assertEqual(destination.read_text(), 'another command')


    def test_shortcut_and_path_survive_reinstall_and_new_shell(self):
        with tempfile.TemporaryDirectory() as tmp, patch('pathlib.Path.home', return_value=Path(tmp)), \
                patch.dict(os.environ, {'SHELL': '/bin/bash', 'PATH': '/usr/bin:/bin'}):
            home = Path(tmp)
            comun.instalar_comando(dry_run=True)
            self.assertEqual(list(home.iterdir()), [])
            comun.instalar_comando()
            before = (home / '.bashrc').read_text()
            comun.instalar_comando()
            self.assertEqual(before, (home / '.bashrc').read_text())
            self.assertEqual((home / '.local/bin/synopsis').resolve(), comun.REPO / 'bin/synopsis')
            command = '. "$HOME/.bashrc"; . "$HOME/.bashrc"; command -v synopsis; printf "%s" "$PATH"'
            result = subprocess.run(['/bin/sh', '-c', command], text=True, capture_output=True,
                                    env={**os.environ, 'HOME': tmp}, check=True)
            self.assertEqual(result.stdout.splitlines()[0], str(home / '.local/bin/synopsis'))
            self.assertEqual(result.stdout.splitlines()[1].split(':').count(str(home / '.local/bin')), 1)

    def test_unrelated_shortcut_is_preserved_before_installing_anything(self):
        with tempfile.TemporaryDirectory() as tmp, patch('pathlib.Path.home', return_value=Path(tmp)):
            shortcut = Path(tmp) / '.local/bin/synopsis'
            shortcut.parent.mkdir(parents=True)
            shortcut.write_bytes(b'\xffunrelated command')
            with self.assertRaises(RuntimeError):
                comun.instalar_comando()
            self.assertEqual(sorted(p.name for p in shortcut.parent.iterdir()), ['synopsis'])
            self.assertEqual(shortcut.read_bytes(), b'\xffunrelated command')

    def test_no_argument_opens_map_from_another_directory(self):
        namespace = runpy.run_path(str(comun.REPO / 'bin/synopsis'))
        with patch.object(sys, 'argv', ['synopsis']), \
                patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(namespace['main'](), 0)
        self.assertIn('abrir', run.call_args.args[0])

    def test_help_runs_from_another_directory(self):
        result = subprocess.run([sys.executable, str(comun.REPO / 'bin/synopsis'), '--help'],
                                cwd='/', text=True, capture_output=True, check=True)
        self.assertIn('recall', result.stdout)
        self.assertIn('memory', result.stdout)
        self.assertIn('mcp', result.stdout)

    def test_zsh_and_fish_path_configuration(self):
        for shell in ('zsh', 'fish'):
            with self.subTest(shell=shell), tempfile.TemporaryDirectory() as tmp, \
                    patch('pathlib.Path.home', return_value=Path(tmp)), \
                    patch.dict(os.environ, {'SHELL': f'/bin/{shell}', 'XDG_CONFIG_HOME': '', 'ZDOTDIR': ''}):
                comun.configurar_path()
                comun.configurar_path()
                home = Path(tmp)
                if shell == 'zsh':
                    self.assertEqual((home / '.zshrc').read_text().count('# Synopsis:'), 1)
                    self.assertEqual((home / '.zprofile').read_text().count('# Synopsis:'), 1)
                else:
                    self.assertEqual((home / '.config/fish/conf.d/synopsis.fish').read_text(),
                                     'fish_add_path --path "$HOME/.local/bin"\n')

    def test_open_uses_shared_engine_and_data(self):
        namespace = runpy.run_path(str(comun.REPO / 'bin' / 'synopsis'))
        with patch.object(sys, 'argv', ['synopsis', 'abrir']), \
                patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(namespace['main'](), 0)
        self.assertEqual(run.call_args.args[0], [
            '/bin/sh', str(comun.raiz_motor() / 'bin' / 'synopsis'), 'abrir',
        ])
        self.assertEqual(run.call_args.kwargs['env']['CLAUDE_PLUGIN_DATA'], str(comun.carpeta_datos()))

    def test_engine_options_and_demo_reach_the_same_engine(self):
        for args in (['--sobre', 'cache'], ['--salud'], ['--version'], ['abrir', '--demo', '--sin-navegador']):
            with self.subTest(args=args):
                namespace = runpy.run_path(str(comun.REPO / 'bin/synopsis'))
                with patch.object(sys, 'argv', ['synopsis', *args]), \
                        patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as run:
                    self.assertEqual(namespace['main'](), 0)
                self.assertEqual(run.call_args.args[0][-len(args):], args)
