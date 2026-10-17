"""Event-specific Claude output contracts; PreCompact is informational only."""
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
from hooks_comun import context_output, contexto
from memory_cycle import MemoryCycle
from project_identity import canonical_memory


class ClaudeHookOutputTest(unittest.TestCase):
    def test_notifications_never_use_event_specific_context(self):
        for event in ('PreCompact', 'PostCompact', 'Notification', 'InstructionsLoaded',
                      'SessionEnd', 'Stop', 'SubagentStop', 'UnknownFutureEvent'):
            with self.subTest(event=event):
                self.assertEqual(context_output(event, 'Pending cycles'), dict(systemMessage='Pending cycles'))

    def test_recall_events_keep_the_context_channel(self):
        for event in ('SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PostToolUse',
                      'PostToolUseFailure', 'PostToolBatch', 'SubagentStart'):
            with self.subTest(event=event):
                self.assertEqual(context_output(event, 'Cited evidence'), dict(
                    hookSpecificOutput=dict(hookEventName=event, additionalContext='Cited evidence')))
        self.assertEqual(context_output('PreCompact', ''), {})

    def test_common_context_writer_obeys_precompact_schema(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            contexto('PreCompact', (lambda: 'Pending cycles',))
        self.assertEqual(json.loads(output.getvalue()), dict(systemMessage='Pending cycles'))

    def test_bridge_precompact_preserves_warnings_as_informational_output(self):
        bridge = runpy.run_path(str(ROOT / 'claude-code/bridge.py'))
        result = dict(contexts=['Pending cycles'], warnings=['Review pending'], errors=[], decision=None)
        with patch.object(runtime, 'dispatch', return_value=result), patch.object(runtime, 'heartbeat'):
            output = bridge['handle'](dict(hook_event_name='PreCompact'))
        self.assertEqual(output, dict(systemMessage='Review pending\nPending cycles'))

    def test_bridge_preserves_tool_permission_decisions(self):
        bridge = runpy.run_path(str(ROOT / 'claude-code/bridge.py'))
        decision = dict(hookEventName='PreToolUse', permissionDecision='ask', permissionDecisionReason='Review required')
        result = dict(contexts=[], warnings=[], errors=[], decision=decision)
        with patch.object(runtime, 'dispatch', return_value=result), patch.object(runtime, 'heartbeat'):
            output = bridge['handle'](dict(hook_event_name='PreToolUse'))
        self.assertEqual(output, dict(hookSpecificOutput=decision))

    def test_private_memory_write_durably_publishes_identity_note_and_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); project = base / 'project'; project.mkdir()
            config = base / 'config.json'; config.write_text(json.dumps(dict(fuentes=[], proyectos=[])))
            env = dict(os.environ, HOME=tmp, USERPROFILE=tmp, SYNOPSIS_DATA=str(base / 'state'),
                       CEREBRO_CONFIG=str(config), SYNOPSIS_AUTO_REVIEW='0', SYNOPSIS_SEMANTIC_SETUP='off')
            script = """import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from project_identity import resolve_memory,owner,canonical_project
from memory_store import MemoryStore
folder=resolve_memory(sys.argv[2])
assert owner(folder)==canonical_project(sys.argv[2])
result=MemoryStore(folder).save(filename='policy',name='policy',description='Synthetic policy',
 kind='project',content='Keep test data for 7 days.',index_line='- [Policy](policy.md)',source='user:test')
assert result['revision']==1
assert (folder/'policy.md').is_file()
assert (folder/'.synopsis/generation').is_file()
assert len(MemoryStore(folder).history('policy'))==1
print(json.dumps({'revision':result['revision']}))
"""
            result = subprocess.run([sys.executable, '-I', '-S', '-c', script, str(ROOT / 'engine'), str(project)],
                                    env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), dict(revision=1))

    def test_real_precompact_entry_points_preserve_pending_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); project = base / 'project'; project.mkdir()
            config = base / 'config.json'; config.write_text(json.dumps(dict(fuentes=[], proyectos=[])))
            state = base / 'state'; folder = canonical_memory(str(project), state)
            cycle = MemoryCycle(folder, str(project))
            turn = cycle.begin('claude-session', 'Unresolved task')['turn']
            original = cycle.status(turn)
            env = dict(os.environ, HOME=tmp, USERPROFILE=tmp, SYNOPSIS_DATA=str(state),
                       SYNOPSIS_ROOT=str(ROOT / 'engine'), CLAUDE_PLUGIN_DATA=str(state),
                       CEREBRO_CONFIG=str(config), CLAUDE_PLUGIN_OPTION_SERVIR_CONTEXTO='true',
                       SYNOPSIS_AUTO_REVIEW='0', SYNOPSIS_SEMANTIC_SETUP='off')
            row = dict(hook_event_name='PreCompact', session_id='claude-session', cwd=str(project))
            for script in ('engine/hook_cycle.py', 'claude-code/bridge.py'):
                with self.subTest(script=script):
                    result = subprocess.run([sys.executable, '-I', '-S', str(ROOT / script)], input=json.dumps(row),
                                            env=env, text=True, capture_output=True, timeout=15)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    output = json.loads(result.stdout)
                    # The reported Claude schema accepts this common field, not
                    # hookSpecificOutput with hookEventName=PreCompact.
                    self.assertEqual(set(output), {'systemMessage'})
                    self.assertIsInstance(output['systemMessage'], str)
                    self.assertIn(turn, output['systemMessage'])
            self.assertEqual(cycle.status(turn), original)
