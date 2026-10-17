"""Adversarial contracts for decision boundaries, competing cases and feedback."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'engine'))
from experience_engine import ExperienceStore
from decision_rag import DecisionRAG, condition
from memory_store import MemoryConflict, digest


class DecisionRAGTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / 'project'
        self.root.mkdir()
        self.context = self.root / 'context.json'
        self.context.write_text('{"idempotent":true}')
        self.contract = self.root / 'contract.txt'
        self.contract.write_text('Retries require idempotency; otherwise reconcile first.')
        self.store = ExperienceStore(base / 'memory', self.root)
        self.rag = DecisionRAG(self.store)
        for choice, expected in [('retry', True), ('reconcile', False)]:
            self.store.save(choice, self.case(choice, expected), 'fixture:decision')

    def case(self, choice='retry', expected=True):
        return dict(situation='Retry a payment after a timeout.', action=choice,
                    rationale='The response can be lost after a commit.', outcome='Declared contract observed.',
                    limitations='Synthetic case. No external service has been tested.',
                    when=dict(paths=['src/payments.py'], keywords=['retry', 'payment', 'timeout'], conditions=[]),
                    checks=[dict(kind='text_contains', path='contract.txt', text='Retries require idempotency')],
                    evidence=[dict(path=p.name, sha256=digest(p.read_text())) for p in (self.context, self.contract)],
                    decision=dict(key='payment-timeout', choice=choice,
                                  requires=[dict(kind='json_equals', path='context.json', pointer='/idempotent', expected=expected)]))

    def plan(self, **kwargs):
        return self.rag.plan('retry payment timeout', 'src/payments.py', **kwargs)

    def group(self, **kwargs):
        return self.plan(**kwargs)['groups'][0]

    def revise(self, name, change):
        row = self.store.latest(name)
        data = copy.deepcopy(row['experience'])
        change(data)
        return self.store.save(name, data, 'fixture:revision', row['revision'])

    def test_near_identical_cases_choose_opposite_actions_when_context_changes(self):
        self.assertEqual(self.group()['selected'], 'retry')
        self.context.write_text('{"idempotent":false}')
        group = self.group()
        self.assertEqual(group['selected'], 'reconcile')
        self.assertEqual({c['state'] for c in group['alternatives']}, {'eligible', 'inapplicable'})
        self.assertEqual(len(group['alternatives']), 2)

    def test_missing_property_is_unknown_and_recovers_one_discriminating_observation(self):
        self.context.write_text('{}')
        group = self.group()
        self.assertIsNone(group['selected'])
        self.assertEqual(group['state'], 'needs_evidence')
        self.assertEqual(len(group['probes']), 1)
        self.assertEqual(group['probes'][0]['pointer'], '/idempotent')
        self.assertEqual(group['probes'][0]['separates'], ['reconcile', 'retry'])

    def test_reading_missing_condition_closes_retrieval_loop(self):
        self.context.write_text('{}')
        self.assertIsNone(self.group()['selected'])
        self.context.write_text('{"idempotent":false}')
        self.assertEqual(self.group()['selected'], 'reconcile')

    def test_missing_file_does_not_certify_false(self):
        self.context.unlink()
        self.assertIsNone(self.group()['selected'])
        self.assertEqual(self.group()['alternatives'][0]['state'], 'unknown')

    def test_ambiguous_competing_conditions_abstain(self):
        self.revise('reconcile', lambda d: d['decision']['requires'][0].update(expected=True))
        self.assertEqual(self.group()['state'], 'conflict')
        self.assertIsNone(self.group()['selected'])

    def test_unknown_competitor_prevents_premature_selection(self):
        self.revise('reconcile', lambda d: d['decision']['requires'][0].update(pointer='/unknown'))
        self.assertEqual(self.group()['state'], 'needs_evidence')
        self.assertIsNone(self.group()['selected'])

    def test_changed_implementation_invalidates_both_cases(self):
        self.contract.write_text('Different contract')
        group = self.group()
        self.assertIsNone(group['selected'])
        self.assertEqual({c['state'] for c in group['alternatives']}, {'stale'})

    def test_observed_false_support_never_selected(self):
        self.revise('retry', lambda d: d['checks'][0].update(text='never observed'))
        self.assertIsNone(self.group()['selected'])
        self.assertIn('contradicted', [c['state'] for c in self.group()['alternatives']])

    def test_legacy_experience_is_not_implicitly_promoted_to_decision(self):
        legacy = self.case()
        legacy.pop('decision')
        self.store.save('legacy', legacy, 'fixture')
        self.assertEqual(len(self.group()['alternatives']), 2)

    def test_irrelevant_query_and_path_abstain(self):
        self.assertTrue(self.rag.plan('oranges harvesting')['abstained'])
        self.assertTrue(self.rag.plan('payment retry', 'src/elsewhere.py')['abstained'])

    def test_path_cannot_escape_project(self):
        for path in ('../outside.py', str(self.root.parent / 'elsewhere.py')):
            with self.assertRaises(ValueError):
                self.rag.plan('payment', path)

    def test_same_folder_different_project_cannot_retrieve_plans(self):
        project = self.root.parent / 'other'
        project.mkdir()
        other = DecisionRAG(ExperienceStore(self.store.folder, project))
        self.assertTrue(other.plan('retry payment')['abstained'])
        packet = self.plan(persist=True)
        with self.assertRaises(ValueError):
            other.outcome(packet['id'], 'retry', 'useful', 'fixture', 'one')

    def test_budget_includes_receipt_and_does_not_hide_competitor(self):
        for budget in (512, 1000, 3000, 6000):
            packet = self.plan(budget=budget, persist=True)
            self.assertLessEqual(len(json.dumps(packet, ensure_ascii=False, sort_keys=True)), budget)
            for group in packet['groups']:
                if not group['alternatives']:
                    self.assertIsNone(group['selected'])

    def test_candidate_overflow_abstains_instead_of_selecting_partial_set(self):
        for i in range(7):
            self.store.save('extra-' + str(i), self.case('extra-' + str(i)), 'fixture')
        self.assertEqual(self.group()['state'], 'candidate_limit')
        self.assertIsNone(self.group()['selected'])

    def test_receipt_stable_and_prompt_not_stored(self):
        one = self.plan(persist=True)
        two = self.plan(persist=True)
        self.assertEqual(one['id'], two['id'])
        with self.store.database() as db:
            rows = db.execute('SELECT packet FROM decision_plans').fetchall()
        self.assertEqual(len(rows), 1)
        self.assertNotIn('retry payment timeout', rows[0][0])

    def test_outcome_is_idempotent_revision_bound_and_reported(self):
        packet = self.plan(persist=True)
        args = (packet['id'], 'retry', 'useful', 'agent:test', 'task-one')
        report = self.rag.outcome(*args)
        self.assertTrue(report['recorded'])
        self.assertIn('Reported utility', report['assurance'])
        self.assertTrue(self.rag.outcome(*args)['replayed'])
        with self.assertRaises(MemoryConflict):
            self.rag.outcome(packet['id'], 'retry', 'harmful', 'agent:test', 'task-one')

    def test_cannot_report_an_unselected_case(self):
        packet = self.plan(persist=True)
        with self.assertRaises(ValueError):
            self.rag.outcome(packet['id'], 'reconcile', 'useful', 'agent:test', 'task-one')

    def test_context_drift_rejects_feedback_attribution(self):
        packet = self.plan(persist=True)
        self.context.write_text('{"idempotent":false}')
        with self.assertRaises(MemoryConflict):
            self.rag.outcome(packet['id'], 'retry', 'useful', 'agent:test', 'task-one')

    def test_revision_drift_rejects_feedback_attribution(self):
        packet = self.plan(persist=True)
        self.revise('retry', lambda d: d.update(limitations='Revised scope.'))
        with self.assertRaises(MemoryConflict):
            self.rag.outcome(packet['id'], 'retry', 'useful', 'agent:test', 'task-one')

    def test_harmful_feedback_suspends_same_revision_until_reconciled(self):
        packet = self.plan(persist=True)
        self.rag.outcome(packet['id'], 'retry', 'harmful', 'agent:test', 'task-one')
        self.assertIsNone(self.group()['selected'])
        self.assertIn('reported_harm', [c['state'] for c in self.group()['alternatives']])
        self.revise('retry', lambda d: d.update(limitations='Corrected boundary, still inferred.'))
        self.assertEqual(self.group()['selected'], 'retry')

    def test_duplicate_keys_invalid_json_and_bool_coercion_fail_closed(self):
        for text in ('{"idempotent":true,"idempotent":false}', '{bad', '{"idempotent":NaN}'):
            self.context.write_text(text)
            self.assertIsNone(self.group()['selected'])
        self.context.write_text('{"idempotent":1}')
        self.assertIsNone(self.group()['selected'])

    def test_dynamic_context_alone_cannot_justify_action(self):
        data = self.case()
        data['evidence'] = data['evidence'][:1]
        data['checks'] = [data['decision']['requires'][0]]
        with self.assertRaises(ValueError):
            self.store.save('weak', data, 'fixture')

    def test_executable_guards_and_injected_shell_are_rejected(self):
        for check in (dict(kind='shell', command='touch forbidden'),
                      dict(kind='python_unittest', path='tests/test_case.py', case='Case.test_ok')):
            data = self.case()
            data['decision']['requires'] = [check]
            with self.assertRaises(ValueError):
                self.store.save('unsafe', data, 'fixture')

    def test_symlink_condition_never_read(self):
        outside = self.root.parent / 'outside.json'
        outside.write_text('{"idempotent":true}')
        self.context.unlink()
        self.context.symlink_to(outside)
        self.assertIsNone(self.group()['selected'])

    def test_tampered_experience_fails_integrity(self):
        with self.store.database() as db, db:
            db.execute("UPDATE experience_versions SET hash='tampered' WHERE name='retry'")
        with self.assertRaises(ValueError):
            self.plan()

    def test_mcp_exposes_decisions_and_bound_feedback_without_execution(self):
        import conector_mcp
        with patch('conector_mcp.carpeta_memoria_de', return_value=self.store.folder):
            packet = conector_mcp.experiencias(dict(proyecto=str(self.root), operacion='decide', consulta='retry payment'))
            receipt = conector_mcp.experiencias(dict(proyecto=str(self.root), operacion='outcome', plan=packet['id'], nombre='retry', resultado='useful', fuente='agent:test', evento='mcp-one'))
        self.assertTrue(receipt['recorded'])
        schema = next(t for t in conector_mcp.HERRAMIENTAS if t['name'] == 'experiencias')
        self.assertNotIn('execute', schema['inputSchema']['properties'])

    def test_pretool_hook_retains_opposing_case_and_does_not_run_tests(self):
        import hook_cycle
        with patch('conector_mcp.carpeta_memoria_de', return_value=self.store.folder), patch('hook_cycle.project_for', return_value=str(self.root)), patch('hooks_comun.contexto_automatico', return_value=True), patch('experience_runner.run_python_test') as run:
            text = hook_cycle.handle(dict(hook_event_name='PreToolUse', cwd=str(self.root), session_id='hook', tool_input=dict(file_path='src/payments.py')))
        self.assertIn('payment-timeout', text)
        self.assertIn('reconcile', text)
        run.assert_not_called()

    def test_superseded_case_preserves_history_and_is_not_competing(self):
        data = self.case('retry')
        data['supersedes'] = 'retry'
        self.store.save('retry-v2', data, 'fixture')
        self.assertEqual({c['name'] for c in self.group()['alternatives']}, {'reconcile', 'retry-v2'})
        self.assertTrue(self.store.versions('retry'))

    def test_executable_checks_require_explicit_bounded_execution(self):
        tests = self.root / 'tests'
        tests.mkdir()
        file = tests / 'test_case.py'
        file.write_text('import unittest\nclass Case(unittest.TestCase):\n def test_ok(self):self.assertTrue(True)\n')
        def change(data):
            data['checks'] = [dict(kind='python_unittest', path='tests/test_case.py', case='Case.test_ok')]
            data['evidence'].append(dict(path='tests/test_case.py', sha256=digest(file.read_text())))
        self.revise('retry', change)
        from experiment_snapshot import fingerprint
        with patch('experience_runner.run_python_test', side_effect=lambda *args: dict(status='observed_support', runner='python_unittest', tests=1, snapshot_sha256=fingerprint(self.root))) as run:
            self.assertIsNone(self.group()['selected'])
            run.assert_not_called()
            self.assertIsNone(self.group(execute=True, max_probes=0)['selected'])
            run.assert_not_called()
            self.assertEqual(self.group(execute=True, max_probes=1)['selected'], 'retry')
            self.assertEqual(run.call_count, 1)

    def test_workspace_drift_during_execution_prevents_selection(self):
        self.test_executable_checks_require_explicit_bounded_execution()
        def changed(*args):
            self.context.write_text('{"idempotent":false}')
            return dict(status='observed_support', runner='python_unittest', tests=1)
        with patch('experience_runner.run_python_test', side_effect=changed):
            self.assertIsNone(self.group(execute=True)['selected'])

    def test_automatic_reviewer_can_capture_a_grounded_decision_case(self):
        from auto_review import ReviewQueue
        queue = ReviewQueue(self.store.folder, self.root)
        turn = queue.cycle.begin('capture', 'Investigate payment retry timeout', 'capture')['turn']
        queue.remember(turn, 'capture', 'Investigate payment retry timeout', 'codex', 'capture')
        for file in (self.context, self.contract):
            queue.track('capture', dict(tool_input=dict(file_path=str(file))))
        queue.stop('capture', 'No claim of executed tests.', 'capture')
        proposal = self.case('retry-new', True)
        def complete(system, request, cwd):
            return dict(outcome='no_change', reason='Grounded inferred decision experience', actions=[],
                        experiences=[dict(name='captured-retry', experience=proposal)])
        transport = type('Transport', (), {'complete': staticmethod(complete)})()
        queue.process_one(transport)
        self.assertEqual(queue.status()[0]['state'], 'complete')
        self.assertEqual(self.store.latest('captured-retry')['experience']['decision']['key'], 'payment-timeout')

    def test_cli_decide_and_outcome_share_the_same_persisted_protocol(self):
        home = self.root.parent / 'home'
        home.mkdir()
        config = home / 'config.json'
        config.write_text(json.dumps(dict(fuentes=[], proyectos=[])))
        env = dict(os.environ, HOME=str(home), CEREBRO_CONFIG=str(config),
                   SYNOPSIS_DATA=str(home / 'data'), CLAUDE_PLUGIN_DATA=str(home / 'data'))
        # Bind the existing fixture store under the child's isolated configuration.
        code = "import sys;sys.path.insert(0,sys.argv[1]);from project_identity import bind;bind(sys.argv[2],sys.argv[3])"
        bound = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT/'engine'), str(self.root), str(self.store.folder)], env=env, capture_output=True, text=True)
        self.assertEqual(bound.returncode, 0, bound.stderr)
        command = [sys.executable, '-B', str(ROOT/'bin/synopsis'), 'experience']
        decided = subprocess.run(command + ['decide', '--project', str(self.root), '--query', 'retry payment timeout'], env=env, capture_output=True, text=True)
        self.assertEqual(decided.returncode, 0, decided.stderr)
        packet = json.loads(decided.stdout)
        self.assertEqual(packet['groups'][0]['selected'], 'retry')
        completed = subprocess.run(command + ['outcome', '--project', str(self.root), '--plan', packet['id'], '--name', 'retry', '--outcome', 'useful', '--event', 'cli-task'], env=env, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)['recorded'])

    def test_tampered_decision_receipt_cannot_attribute_feedback(self):
        packet = self.plan(persist=True)
        with self.store.database() as db, db:
            raw = db.execute('SELECT packet FROM decision_plans').fetchone()[0]
            stored = json.loads(raw)
            stored['packet']['groups'][0]['selected'] = 'reconcile'
            db.execute('UPDATE decision_plans SET packet=?', (json.dumps(stored),))
        with self.assertRaises(ValueError):
            self.rag.outcome(packet['id'], 'retry', 'useful', 'agent:test', 'tampered')

    def test_snapshot_drift_of_uncited_test_dependency_is_not_accepted(self):
        self.test_executable_checks_require_explicit_bounded_execution()
        from experiment_snapshot import fingerprint
        before = fingerprint(self.root)
        def changed(*args):
            (self.root/'dependency.py').write_text('BEHAVIOR = "changed"')
            return dict(status='observed_support', runner='python_unittest', tests=1, snapshot_sha256=before)
        with patch('experience_runner.run_python_test', side_effect=changed):
            self.assertIsNone(self.group(execute=True)['selected'])

    def test_dashboard_uses_current_decision_conditions_not_historical_context_hash(self):
        import experience_status
        self.context.write_text('{"idempotent":false}')
        record = dict(memory=str(self.store.folder), project=str(self.root), key='fixture')
        with patch('experience_status.registered_memories', return_value=[record]):
            report = experience_status.overview()
        cards = {card['name']: card for card in report['projects'][0]['experiences']}
        self.assertEqual(cards['reconcile']['verification']['state'], 'eligible')
        self.assertEqual(cards['retry']['verification']['state'], 'inapplicable')

    def test_invalid_limits_and_unknown_plan_rejected(self):
        for kwargs in (dict(budget=511), dict(max_probes=4), dict(max_probes=True)):
            with self.assertRaises(ValueError):
                self.plan(**kwargs)
        with self.assertRaises(ValueError):
            self.rag.outcome('missing', 'retry', 'useful', 'fixture', 'one')

if __name__ == '__main__':
    unittest.main()
