"""Exercise independent adapter processes and MCP clients in an isolated home."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'engine'))
from memory_cycle import MemoryCycle
from memory_store import MemoryConflict


class ContinuityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / 'project'
        self.project.mkdir()
        config = self.base / 'config.json'
        config.write_text(json.dumps(dict(usuario='Test', fuentes=[], proyectos=[])))
        self.env = dict(os.environ, HOME=str(self.base), SYNOPSIS_DATA=str(self.base / 'state'),
                        SYNOPSIS_ROOT=str(ROOT / 'engine'), CEREBRO_CONFIG=str(config), CLAUDE_PLUGIN_OPTION_SERVIR_CONTEXTO="true", PYTHONDONTWRITEBYTECODE='1')
        from project_identity import canonical_memory
        self.folder = canonical_memory(str(self.project), self.base / 'state')

    def invoke(self, scenario, prompt=None, timeout=30):
        if prompt is None:
            prompt={'initial':'Redis conserva la caché 120 segundos.', 'correct':'Redis conserva la caché 300 segundos.', 'stale':'Redis conserva la caché 999 segundos.'}.get(scenario,'Redis caché segundos')
        return subprocess.run([sys.executable, '-B', str(ROOT / 'bin/synopsis'), 'run', '--project', str(self.project),
                               '--session', 'task-cross-model', '--prompt', prompt, '--timeout', str(timeout), '--',
                               sys.executable, '-B', str(ROOT / 'tests/fixtures/model_adapter.py')],
                              env=dict(self.env, SYNOPSIS_TEST_SCENARIO=scenario), capture_output=True, text=True, timeout=40)

    def test_independent_adapters_retain_working_state_and_only_recall_corrected_knowledge(self):
        for scenario in ('initial', 'correct', 'continue'):
            result = self.invoke(scenario)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            response = json.loads(result.stdout)
            self.assertEqual(response['receipt']['status'], 'no_change' if scenario == 'continue' else 'saved')
        self.assertIn('300 segundos', response['answer'])
        cycle = MemoryCycle(self.folder, str(self.project))
        self.assertEqual(cycle.status()['pending'], 0)
        self.assertEqual(len(cycle.store.history('redis-policy')), 2)

    def test_broken_contract_withholds_answer_and_preserves_pending_turn(self):
        result = self.invoke('broken')
        self.assertEqual(result.returncode, 2, result.stderr)
        response = json.loads(result.stdout)
        self.assertEqual(response['error'], 'memory_contract_required')
        self.assertNotIn('ESTA RESPUESTA', result.stdout + result.stderr)
        cycle = MemoryCycle(self.folder, str(self.project))
        self.assertEqual(cycle.status()['pending'], 1)

    def test_stale_correction_cannot_release_an_answer_claiming_success(self):
        self.assertEqual(self.invoke('initial').returncode, 0)
        result = self.invoke('stale')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['error'], 'memory_unresolved')
        self.assertNotIn('ESTA RESPUESTA', result.stdout + result.stderr)
        self.assertIn('120 segundos', (self.folder / 'redis-policy.md').read_text())
        self.assertNotIn('999 segundos', (self.folder / 'redis-policy.md').read_text())

    def test_adapter_limits_fail_without_losing_turn_accounting(self):
        for scenario in ('timeout', 'oversized'):
            with self.subTest(scenario=scenario):
                result = self.invoke(scenario, prompt=scenario, timeout=1)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                response = json.loads(result.stdout)
                self.assertEqual(response['error'], 'adapter_timeout' if scenario == 'timeout' else 'adapter_output_limit')
        self.assertEqual(MemoryCycle(self.folder, str(self.project)).status()['pending'], 2)

    def test_working_checkpoint_is_separate_from_knowledge_and_rejects_stale_updates(self):
        cycle = MemoryCycle(self.folder, str(self.project))
        first = cycle.begin('task', 'first')['turn']
        second = cycle.begin('task', 'second')['turn']
        checkpoint = dict(goal='Validar TTL', next_step='Leer configuración')
        cycle.close(first, 'no_change', 'Solo estado temporal', checkpoint=checkpoint)
        self.assertFalse((self.folder / 'MEMORY.md').exists())
        self.assertEqual(cycle.working(second)['revision'], first)
        with self.assertRaises(MemoryConflict):
            cycle.close(second, 'no_change', 'Actualización concurrente', checkpoint=checkpoint)
        cycle.close(second, 'no_change', 'Checkpoint conciliado', checkpoint=checkpoint, checkpoint_revision=first)
        third = cycle.begin('task', 'third')['turn']
        self.assertEqual(cycle.working(third)['revision'], second)

    def test_mcp_close_persists_operations_and_reports_unresolved_conflicts(self):
        def call(name, arguments):
            requests = [dict(jsonrpc='2.0', id=1, method='tools/call', params=dict(name=name, arguments=arguments))]
            process = subprocess.run([sys.executable, '-B', str(ROOT / 'mcp_entry.py')], env=self.env,
                                     input=''.join(json.dumps(row) + '\n' for row in requests),
                                     text=True, capture_output=True, timeout=20)
            self.assertEqual(process.returncode, 0, process.stderr)
            return json.loads(process.stdout)['result']
        opened = call('iniciar_turno_memoria', dict(proyecto=str(self.project), sesion='claude-task', consulta='Redis caché'))
        self.assertNotIn('isError', opened)
        turn = opened['structuredContent']['turn']
        action = dict(filename='redis-policy', name='redis-policy', kind='project', content='Redis conserva 120 segundos.',
                      description='TTL Redis', index_line='- [Redis](redis-policy.md)', source='agent:test')
        closed = call('cerrar_turno_memoria', dict(proyecto=str(self.project), turno=turn, resultado='saved', operaciones=[action]))
        self.assertTrue(closed['structuredContent']['closed'], closed)
        # A different client process can read the receipt and provenance after restart.
        status = call('estado_memoria', dict(proyecto=str(self.project), turno=turn))['structuredContent']
        self.assertEqual(status['turns'][0]['actions'][0]['status'], 'applied')
        self.assertEqual(status['pending'], 0)

    def test_native_prompt_opens_scoped_turn_and_a_new_session_recovers_queued_actions(self):
        cycle = MemoryCycle(self.folder, str(self.project))
        turn = cycle.begin('old-client', 'Redis caché')['turn']
        cycle.queue(turn, [dict(filename='redis-policy', name='redis-policy', description='TTL Redis',
                               kind='project', content='Redis conserva 120 segundos.',
                               index_line='- [Redis](redis-policy.md)', source='agent:test')])
        row = dict(hook_event_name='SessionStart', session_id='new-client', cwd=str(self.project))
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'engine/hook_cycle.py')], env=self.env,
                                input=json.dumps(row), capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(turn, result.stdout)
        self.assertEqual(cycle.status(turn)['turns'][0]['actions'][0]['status'], 'applied')
        # A new prompt receives a bounded cited packet and working contract.
        row.update(hook_event_name='UserPromptSubmit', prompt='Redis caché segundos', generation_id='one')
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'engine/hook_cycle.py')], env=self.env,
                                input=json.dumps(row), capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)['hookSpecificOutput']['additionalContext']
        self.assertIn('120 segundos', output)
        self.assertIn('cerrar_turno_memoria', output)
        self.assertLess(len(output), 12500)
        self.assertEqual(cycle.status()['pending'], 2)
