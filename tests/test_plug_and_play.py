"""Install real adapters into a fake home; never change the developer's IDEs."""
import contextlib
import io
import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


class PlugAndPlayTest(unittest.TestCase):
    def test_single_command_installs_five_clients_and_verifies_transport_without_questions(self):
        with tempfile.TemporaryDirectory(prefix='synopsis-install-') as tmp:
            home = Path(tmp)
            for folder in ('.claude', '.codex', '.gemini/config', '.cursor', '.config/opencode'):
                (home / folder).mkdir(parents=True)
            custom = {'mcpServers': {'existing': {'command': 'keep-me'}}}
            (home / '.claude.json').write_text(json.dumps(custom))
            (home / '.gemini/config/mcp_config.json').write_text(json.dumps(custom))
            (home / '.cursor/mcp.json').write_text(json.dumps(custom))
            jsonc = home / '.config/opencode/opencode.jsonc'
            jsonc.write_text('// keep comments\n{\n  \"theme\": \"existing\",\n}\n')
            config = home / 'isolated.json'
            config.write_text(json.dumps({'usuario': 'Test', 'fuentes': [], 'proyectos': []}))
            env = dict(os.environ, HOME=tmp, XDG_CONFIG_HOME=str(home / '.config'), SHELL='/bin/bash', SYNOPSIS_ROOT=str(ROOT / 'engine'),
                       SYNOPSIS_DATA=str(home / 'state'), CEREBRO_CONFIG=str(config), PYTHONDONTWRITEBYTECODE='1',
                       SYNOPSIS_SEMANTIC_SETUP='off')
            cli = [sys.executable, '-B', str(ROOT / 'bin/synopsis')]
            preview = subprocess.run(cli + ['install', '--dry-run', '--no-service'], env=env,
                                     input='', capture_output=True, text=True, timeout=30)
            self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
            self.assertFalse((home / '.codex/hooks.json').exists())
            self.assertFalse((home / '.local').exists())
            installed = subprocess.run(cli + ['install', '--no-service'], env=env,
                                       input='', capture_output=True, text=True, timeout=40)
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            self.assertIn('Prueba de conexión MCP y adaptadores', installed.stdout)
            for folder in ('.claude/skills', '.codex/skills', '.gemini/config/skills', '.cursor/skills', '.config/opencode/skills'):
                self.assertTrue((home / folder / 'memoria-synopsis/SKILL.md').is_file())
            self.assertEqual(jsonc.read_text(), '// keep comments\n{\n  \"theme\": \"existing\",\n}\n')
            for path in (home / '.claude.json', home / '.gemini/config/mcp_config.json', home / '.cursor/mcp.json'):
                data = json.loads(path.read_text())
                self.assertEqual(data['mcpServers']['existing']['command'], 'keep-me')
                self.assertIn('synopsis', data['mcpServers'])
            before = (home / '.claude/settings.json').read_text()
            repeated = subprocess.run(cli + ['install', '--no-service'], env=env,
                                      input='', capture_output=True, text=True, timeout=40)
            self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
            self.assertEqual(before, (home / '.claude/settings.json').read_text())
            doctor = subprocess.run(cli + ['doctor', '--json'], env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
            report = json.loads(doctor.stdout)
            self.assertEqual(report['tools'], 15)
            self.assertTrue(all(client['configured'] for client in report['clients'].values()))
            self.assertTrue(all(client['activity'] == 'waiting_for_first_event' for client in report['clients'].values()))

    def test_configuration_transaction_rolls_back_after_second_write_fails(self):
        import integration_setup
        sys.path.insert(0, str(ROOT / 'engine'))
        import archivos
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / 'first.json', Path(tmp) / 'second.json'
            first.write_text('original')
            atomic = archivos.escribir_atomico
            def write(path, content):
                if path == second:
                    raise OSError('simulated disk error')
                atomic(path, content)
            with patch.object(archivos, 'escribir_atomico', side_effect=write):
                with self.assertRaises(OSError):
                    integration_setup.install_files({first: 'new', second: 'new'}, Path(tmp) / 'backups')
            self.assertEqual(first.read_text(), 'original')
            self.assertFalse(second.exists())

    def test_dispatch_is_shared_but_preserves_client_permission_semantics(self):
        import integration_runtime as runtime
        row = dict(hook_event_name='PreToolUse', tool_name='Agent')
        with patch.object(runtime, 'environment'):
            result = runtime.dispatch(row, record_event=lambda _: None, invoke_hook=lambda *_: {
                'hookSpecificOutput': {'permissionDecision': 'ask', 'permissionDecisionReason': 'quota'}})
        self.assertEqual(result['decision']['permissionDecision'], 'ask')
        anti = runpy.run_path(str(ROOT / 'antigravity/bridge.py'))
        with patch.object(runtime, 'dispatch', return_value=result), patch.object(runtime, 'heartbeat'):
            output = anti['handle']({'conversationId': 'sample', 'toolCall': {'name': 'browser_subagent'}}, 'PreToolUse')
        self.assertEqual(output['decision'], 'ask')

    def test_antigravity_does_not_close_a_chat_after_each_model_invocation(self):
        import integration_runtime as runtime
        anti = runpy.run_path(str(ROOT / 'antigravity/bridge.py'))
        with patch.object(runtime, 'dispatch') as dispatch:
            self.assertEqual(anti['handle']({}, 'PostInvocation'), {})
            self.assertEqual(anti['handle']({'invocationNum': 2}, 'PreInvocation'), {})
        dispatch.assert_not_called()

    def test_probe_does_not_create_fake_activity(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, SYNOPSIS_DATA=tmp, PYTHONDONTWRITEBYTECODE='1')
            for directory, client in (('claude-code', 'claude'), ('codex', 'codex'), ('antigravity', 'antigravity'), ('opencode', 'opencode'), ('cursor', 'cursor')):
                process = subprocess.run([sys.executable, '-B', str(ROOT / directory / 'bridge.py'), '--probe'],
                                         env=env, capture_output=True, text=True, timeout=10)
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertEqual(json.loads(process.stdout)['client'], client)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_real_native_start_events_reach_the_common_runtime_for_all_five_clients(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = base / 'config.json'
            config.write_text(json.dumps({'usuario': 'Test', 'fuentes': [], 'proyectos': []}))
            env = dict(os.environ, HOME=tmp, SYNOPSIS_DATA=str(base / 'state'),
                       SYNOPSIS_ROOT=str(ROOT / 'engine'), CEREBRO_CONFIG=str(config),
                       PYTHONDONTWRITEBYTECODE='1')
            for directory, client in (('claude-code', 'claude'), ('codex', 'codex'), ('antigravity', 'antigravity'), ('opencode', 'opencode'), ('cursor', 'cursor')):
                data = dict(hook_event_name='SessionStart', session_id='test-session', cwd=tmp)
                args = []
                if client == 'antigravity':
                    data = dict(conversationId='test-session', workspacePaths=[tmp])
                    args = ['SessionStart']
                if client == 'cursor':
                    data = dict(hook_event_name='sessionStart', conversation_id='test-session', workspace_roots=[tmp])
                result = subprocess.run([sys.executable, '-B', str(ROOT / directory / 'bridge.py'), *args],
                                        input=json.dumps(data), env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                json.loads(result.stdout)
                activity = json.loads((base / 'state/integrations' / f'{client}.json').read_text())
                self.assertTrue(activity['ok'], result.stdout + result.stderr)
                self.assertEqual(activity['event'], 'SessionStart')
