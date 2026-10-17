"""Identity conflicts remain visible without leaking arbitrary exception text."""
import contextlib
import io
import json
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'engine'))
from project_identity import ProjectIdentityConflict
import integration_runtime


class HookIdentityErrorTest(unittest.TestCase):
    def test_conflict_is_structured_actionable_and_marks_dispatch_failed(self):
        hook = runpy.run_path(str(ROOT / 'engine/hook_cycle.py'))
        output, errors = io.StringIO(), io.StringIO()
        with patch.dict(hook['main'].__globals__, {'handle': lambda row: self.fail_identity()}), \
                patch('sys.stdin', io.StringIO('{}')), contextlib.redirect_stdout(output), \
                contextlib.redirect_stderr(errors):
            hook['main']()
        response = json.loads(output.getvalue())
        self.assertEqual(errors.getvalue(), '')
        self.assertEqual(response['synopsisError'], 'memory_identity_conflict')
        self.assertIn('memory-location', response['systemMessage'])
        self.assertNotIn('private-exception-data', output.getvalue())
        with patch.object(integration_runtime, 'environment'):
            result = integration_runtime.dispatch({'hook_event_name': 'UserPromptSubmit'},
                record_event=lambda row: None, invoke_hook=lambda script, row: response)
        self.assertEqual(result['errors'], ['hook_cycle.py: memory_identity_conflict'])
        self.assertEqual(result['warnings'], [response['systemMessage']])

    @staticmethod
    def fail_identity():
        raise ProjectIdentityConflict('private-exception-data')
