"""Claude stop notifications must not restart the model or fabricate memory closure."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'engine'))
import integration_runtime as runtime
from memory_cycle import MemoryCycle
from project_identity import canonical_memory


class StopHooksTest(unittest.TestCase):
    def test_claude_stop_status_is_visible_without_continuation_feedback(self):
        bridge = runpy.run_path(str(ROOT / 'claude-code/bridge.py'))
        response = dict(contexts=['Unresolved memory cycle'], warnings=['Review pending'], errors=[], decision=None)
        for event in ('Stop', 'SubagentStop'):
            with self.subTest(event=event), patch.object(runtime, 'dispatch', return_value=response), patch.object(runtime, 'heartbeat'):
                output = bridge['handle'](dict(hook_event_name=event))
            self.assertEqual(output, dict(systemMessage='Review pending\nUnresolved memory cycle'))
            self.assertNotIn('hookSpecificOutput', output)
            self.assertNotIn('decision', output)

    def test_claude_reentry_skips_dispatch_and_heartbeat(self):
        bridge = runpy.run_path(str(ROOT / 'claude-code/bridge.py'))
        with patch.object(runtime, 'dispatch') as dispatch, patch.object(runtime, 'heartbeat') as heartbeat:
            for event in ('Stop', 'SubagentStop'):
                self.assertEqual(bridge['handle'](dict(hook_event_name=event, stop_hook_active=True)), {})
            dispatch.assert_not_called(); heartbeat.assert_not_called()

    def test_shared_runtime_reentry_has_no_hooks_or_recording(self):
        with patch.object(runtime, 'environment') as environment, patch.object(runtime, 'record') as record, patch.object(runtime, 'invoke') as invoke:
            for event in ('Stop', 'SubagentStop'):
                self.assertEqual(runtime.dispatch(dict(hook_event_name=event, stop_hook_active=True)),
                                 dict(contexts=[], warnings=[], errors=[], decision=None))
            environment.assert_not_called(); record.assert_not_called(); invoke.assert_not_called()

    def test_reentry_flag_does_not_skip_user_prompts(self):
        with patch.object(runtime, 'environment'), patch.object(runtime, 'record') as record, patch.object(runtime, 'invoke', return_value={}) as invoke:
            runtime.dispatch(dict(hook_event_name='UserPromptSubmit', stop_hook_active=True))
        record.assert_called_once(); invoke.assert_called_once()

    def test_direct_cycle_reentry_does_not_resolve_or_modify_project(self):
        import hook_cycle
        with patch.object(hook_cycle, 'project_for') as resolve:
            for event in ('Stop', 'SubagentStop'):
                self.assertIsNone(hook_cycle.handle(dict(hook_event_name=event, stop_hook_active=True)))
            resolve.assert_not_called()

    def test_direct_save_reentry_does_not_read_or_write_history(self):
        hook = runpy.run_path(str(ROOT / 'engine/hook_guardar.py'))
        with patch('hooks_comun.entrada', return_value=dict(hook_event_name='Stop', stop_hook_active=True)), \
                patch.dict(hook['main'].__globals__, guardar_historial=lambda: self.fail('history touched'),
                           aviso_fin=lambda row: self.fail('reminder executed')), contextlib.redirect_stdout(io.StringIO()) as output:
            hook['main']()
        self.assertEqual(output.getvalue(), '')

    def test_direct_save_status_is_informational(self):
        hook = runpy.run_path(str(ROOT / 'engine/hook_guardar.py'))
        with patch('hooks_comun.entrada', return_value=dict(hook_event_name='Stop')), \
                patch.dict(hook['main'].__globals__, guardar_historial=lambda: None, aviso_fin=lambda row: 'Memory review pending'), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            hook['main']()
        self.assertEqual(json.loads(output.getvalue()), dict(systemMessage='Memory review pending'))

    def test_real_stop_entry_points_preserve_unresolved_cycles_and_do_not_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); project = base / 'project'; project.mkdir()
            config = base / 'config.json'; config.write_text(json.dumps(dict(fuentes=[], proyectos=[])))
            state = base / 'state'; folder = canonical_memory(str(project), state)
            cycle = MemoryCycle(folder, str(project))
            own = cycle.begin('claude-session', 'Unresolved task')['turn']
            other = cycle.begin('other-session', 'Separate task')['turn']
            env = dict(os.environ, HOME=tmp, USERPROFILE=tmp, SYNOPSIS_DATA=str(state),
                       SYNOPSIS_ROOT=str(ROOT / 'engine'), CLAUDE_PLUGIN_DATA=str(state),
                       CEREBRO_CONFIG=str(config), CLAUDE_PLUGIN_OPTION_SERVIR_CONTEXTO='true',
                       SYNOPSIS_AUTO_REVIEW='0', SYNOPSIS_SEMANTIC_SETUP='off')
            row = dict(hook_event_name='Stop', session_id='claude-session', cwd=str(project), stop_hook_active=False)
            for script in ('engine/hook_cycle.py', 'claude-code/bridge.py'):
                # Different sessions share a project; neither hook may close any of them.
                with self.subTest(script=script):
                    result = subprocess.run([sys.executable, '-I', '-S', str(ROOT / script)], input=json.dumps(row),
                                            env=env, text=True, capture_output=True, timeout=15)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    output = json.loads(result.stdout) if result.stdout.strip() else {}
                    self.assertNotIn('hookSpecificOutput', output); self.assertNotIn('decision', output)
                    if script.startswith('engine/'):
                        self.assertIn(own, output['systemMessage']); self.assertNotIn(other, output['systemMessage'])
                        repeated = subprocess.run([sys.executable, '-I', '-S', str(ROOT / script)], input=json.dumps(row),
                                                  env=env, text=True, capture_output=True, timeout=15)
                        self.assertEqual(repeated.returncode, 0, repeated.stderr); self.assertEqual(repeated.stdout, '')
                    active = subprocess.run([sys.executable, '-I', '-S', str(ROOT / script)], input=json.dumps(dict(row, stop_hook_active=True)),
                                            env=env, text=True, capture_output=True, timeout=15)
                    self.assertEqual(active.returncode, 0, active.stderr)
                    self.assertIn(active.stdout.strip(), ('', '{}'))
            self.assertEqual(cycle.status()['pending'], 2)
            for turn in (own, other):self.assertEqual(cycle.status(turn)['turns'][0]['status'], 'open')
