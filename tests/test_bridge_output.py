"""Exercise the wire output without recording real events or reading user notes."""
import contextlib
import io
import json
import runpy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class BridgeOutputTest(unittest.TestCase):
    def emit(self, event, result=None, error=None):
        namespace = runpy.run_path(str(Path(__file__).resolve().parent.parent / 'codex/bridge.py'))
        output = io.StringIO()
        with patch('sys.stdin', io.StringIO(json.dumps({'hook_event_name': event}))), \
                patch.dict(namespace['main'].__globals__, {'handle': self.handler(result, error)}), \
                contextlib.redirect_stdout(output):
            namespace['main']()
        return output.getvalue()

    @staticmethod
    def handler(result, error):
        def handle(_data):
            print('{"unexpected": "engine diagnostic"}')
            if error:
                raise error
            return result
        return handle

    def test_prompt_context_is_plain_text_and_preserves_unicode(self):
        output = self.emit('UserPromptSubmit', {
            'hookSpecificOutput': {'hookEventName': 'UserPromptSubmit', 'additionalContext': '{"nota": "señal"}'},
            'systemMessage': 'Aviso de memoria',
        })
        self.assertEqual(output, 'Synopsis:\n{"nota": "señal"}\n\nAviso de memoria\n')
        self.assertFalse(output.lstrip().startswith('{'))

    def test_empty_prompt_hook_is_silent(self):
        self.assertEqual(self.emit('UserPromptSubmit', {}), '')

    def test_prompt_errors_are_reported_as_plain_text(self):
        output = self.emit('UserPromptSubmit', error=RuntimeError('failure'))
        self.assertTrue(output.startswith('Synopsis:\n'))
        self.assertIn('RuntimeError: failure', output)

    def test_other_events_keep_structured_output(self):
        result = {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                        'permissionDecisionReason': 'policy'}}
        self.assertEqual(json.loads(self.emit('PreToolUse', result)), result)
        self.assertEqual(json.loads(self.emit('Stop', {})), {})

    def test_stop_adapts_claude_context_to_supported_system_message(self):
        namespace = runpy.run_path(str(Path(__file__).resolve().parent.parent / 'codex/bridge.py'))
        raw = {'hookSpecificOutput': {'hookEventName': 'Stop', 'additionalContext': 'Guardar una decisión'}}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ), \
                patch.dict(namespace['handle'].__globals__, {
                    'DATA': Path(tmp), 'record': lambda row: None,
                    'invoke': lambda script, row: raw,
                }):
            result = namespace['handle']({'hook_event_name': 'Stop', 'session_id': 'test-stop'})
        self.assertEqual(result, {'systemMessage': 'Guardar una decisión'})
        self.assertNotIn('hookSpecificOutput', result)
