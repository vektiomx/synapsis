"""A context experiment must challenge a test without modifying the user's source."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_decision_rag as fixtures
from experience_lab import ExperienceLab,apply_context
from memory_store import digest

class ExperienceLabTest(unittest.TestCase):
    setUp=fixtures.DecisionRAGTest.setUp
    case=fixtures.DecisionRAGTest.case
    revise=fixtures.DecisionRAGTest.revise

    def executable(self):
        folder=self.root/'tests';folder.mkdir()
        path=folder/'test_guard.py'
        path.write_text('import unittest,json\nclass Guard(unittest.TestCase):\n def test_requirement(self):self.assertIs(json.load(open("context.json"))["idempotent"],True)\n')
        def update(data):
            data['checks']=[dict(kind='python_unittest',path='tests/test_guard.py',case='Guard.test_requirement')]
            data['evidence'].append(dict(path='tests/test_guard.py',sha256=digest(path.read_text())))
        self.revise('retry',update)
        return ExperienceLab(self.store)

    def test_explore_without_permission_is_a_plan_and_never_executes(self):
        lab=self.executable()
        with patch('experience_runner.run_python_test') as run:
            report=lab.explore('retry')
        run.assert_not_called()
        self.assertEqual(report['state'],'needs_execution')
        self.assertEqual(len(report['planned_runs']),2)

    def test_sensitive_test_and_non_discriminating_test_are_distinguished(self):
        lab=self.executable();before=self.context.read_bytes()
        def sensitive(project,check,context_overrides):
            return dict(status='observed_support' if context_overrides[0]['expected'] else 'contradicted',runner='python_unittest',tests=1)
        with patch('experience_runner.run_python_test',side_effect=sensitive):
            report=lab.explore('retry',execute=True)
        self.assertEqual(report['state'],'scope_sensitive')
        self.assertEqual(self.context.read_bytes(),before)
        self.assertEqual(lab.latest('retry',2)['state'],'scope_sensitive')
        with patch('experience_runner.run_python_test',return_value=dict(status='observed_support',runner='python_unittest',tests=1)):
            self.assertEqual(lab.explore('retry',execute=True)['state'],'non_discriminating')

    def test_workspace_dependency_drift_prevents_recording_positive_experiment(self):
        lab=self.executable()
        def drift(*args,**kwargs):
            (self.root/'dependency.py').write_text('CHANGED = True')
            return dict(status='observed_support',runner='python_unittest',tests=1)
        with patch('experience_runner.run_python_test',side_effect=drift):
            self.assertEqual(lab.explore('retry',execute=True,max_runs=1)['state'],'workspace_changed')

    def test_context_overlay_does_not_escape_or_accept_invalid_pointer(self):
        for check in (dict(kind='json_equals',path='../outside.json',pointer='/a',expected=True),
                      dict(kind='json_equals',path='context.json',pointer='/missing/child',expected=True),
                      dict(kind='json_equals',path='context.json',pointer='/bad~2',expected=True)):
            with self.assertRaises(ValueError):apply_context(self.root,[check])
        self.context.write_text('{"items":[1,2]}')
        with self.assertRaises(ValueError):apply_context(self.root,[dict(kind='json_equals',path='context.json',pointer='/items/-1',expected=9)])

    def test_ambiguous_or_nonfinite_context_cannot_be_intervened(self):
        for raw in ('{"a":true,"a":false}','{"a":NaN}'):
            self.context.write_text(raw)
            with self.assertRaises(ValueError):
                apply_context(self.root,[dict(kind='json_equals',path='context.json',pointer='/a',expected=True)])
            self.assertEqual(self.context.read_text(),raw)

    def test_unavailable_runner_is_not_a_negative_result(self):
        lab=self.executable()
        with patch('experience_runner.run_python_test',return_value=dict(status='unavailable')):
            self.assertEqual(lab.explore('retry',execute=True)['state'],'unavailable')

    def test_stale_support_not_replayed_as_current(self):
        lab=self.executable();self.contract.write_text('No current contract')
        with patch('experience_runner.run_python_test') as run:
            self.assertEqual(lab.explore('retry',execute=True)['state'],'stale')
        run.assert_not_called()

if __name__=='__main__':unittest.main()
