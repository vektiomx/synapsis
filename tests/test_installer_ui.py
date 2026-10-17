import contextlib
import io
import os
import runpy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from installer_ui import InstallerUI


class InstallerUITest(unittest.TestCase):
    def test_plain_output_and_preview_do_not_claim_installation(self):
        stream = io.StringIO()
        ui = InstallerUI(stream)
        ui.banner(preview=True)
        ui.summary([('Codex', True)], preview=True)
        output = stream.getvalue()
        self.assertIn('S Y N O P S I S', output)
        self.assertIn('No se aplicaron cambios', output)
        self.assertNotIn('\x1b[', output)
        self.assertNotIn('reinicia tu asistente', output)

    def test_no_color_is_respected_in_a_terminal(self):
        stream = io.StringIO()
        with patch.object(stream, 'isatty', return_value=True), patch.dict(os.environ, {'TERM': 'xterm', 'NO_COLOR': ''}):
            ui = InstallerUI(stream)
            ui.banner()
        self.assertNotIn('\x1b[', stream.getvalue())

    def test_failure_summary_explains_how_to_retry(self):
        stream = io.StringIO()
        InstallerUI(stream).summary([('Codex', True), ('Servicio del mapa', False)])
        self.assertIn('PENDIENTE', stream.getvalue())
        self.assertIn('puedes repetir', stream.getvalue())

    def chooser(self):
        return runpy.run_path(str(Path(__file__).resolve().parent.parent / 'bin/synopsis'))

    def test_multi_selection_reprompts_after_invalid_or_unavailable_input(self):
        namespace = self.chooser()
        ui = InstallerUI(io.StringIO())
        with patch.dict(namespace['elegir_interactivo'].__globals__, {'diagnosticar': lambda key: (key != 'antigravity', None)}), \
                patch.object(sys.stdin, 'isatty', return_value=True), \
                patch('builtins.input', side_effect=['0', '3', '1,2,1']):
            selected = namespace['elegir_interactivo'](ui)
        self.assertEqual(selected, ['claude', 'codex'])
        self.assertEqual(ui.stream.getvalue().count('Selección inválida'), 2)

    def test_noninteractive_install_needs_an_explicit_target(self):
        namespace = self.chooser()
        ui = InstallerUI(io.StringIO())
        with patch.dict(namespace['elegir_interactivo'].__globals__, {'diagnosticar': lambda _: (True, None)}), \
                patch.object(sys.stdin, 'isatty', return_value=False), patch('builtins.input') as prompt:
            self.assertEqual(namespace['elegir_interactivo'](ui), [])
        prompt.assert_not_called()
        self.assertIn('--all', ui.stream.getvalue())

    def test_no_service_option_keeps_installation_manual(self):
        namespace = self.chooser()
        import subprocess
        with patch.object(sys, 'argv', ['synopsis', 'install', 'codex', '--no-service']), \
                patch('comun.instalar_comando'), \
                patch('integration_health.check', return_value={'ready': True}), \
                patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as run, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(namespace['main'](), 0)
        self.assertEqual(run.call_count, 1)

    def test_command_conflict_is_pending_in_summary_and_skips_service(self):
        namespace = self.chooser()
        import subprocess
        output = io.StringIO()
        with patch.object(sys, 'argv', ['synopsis', 'install', 'codex']), \
                patch('comun.instalar_comando', side_effect=RuntimeError('existing command')), \
                patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as run, \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(namespace['main'](), 1)
        self.assertEqual(run.call_count, 1)
        self.assertIn('PENDIENTE  Comando synopsis y PATH', output.getvalue())
        self.assertNotIn('Siguiente paso: reinicia', output.getvalue())
