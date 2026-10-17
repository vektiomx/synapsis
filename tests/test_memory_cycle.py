"""Crash recovery, verified receipts and turn accounting with invented data."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'engine'))
from memory_cycle import MemoryCycle
from memory_store import MemoryConflict, MemoryStore


class MemoryCycleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.cycle = MemoryCycle(self.base / 'memory', str(self.base / 'project'))
        self.turn = self.cycle.begin('session', 'Redis expires at 120 seconds')['turn']
        self.action = dict(filename='redis-policy', name='redis-policy', kind='project',
                           content='Redis conserva la caché 120 segundos.', description='Duración de caché Redis',
                           index_line='- [Redis](redis-policy.md)', source='user:test')

    def test_open_is_idempotent_without_persisting_the_prompt(self):
        self.assertEqual(self.cycle.begin('session', 'Redis expires at 120 seconds')['turn'], self.turn)
        with self.cycle.database() as db:
            rows = db.execute('SELECT * FROM cycle_turns').fetchall()
        self.assertEqual(len(rows), 1)
        self.assertNotIn('Redis expires', json.dumps(rows))
        self.cycle.close(self.turn, 'no_change', 'Solo consulta, sin decisión durable.')
        self.assertNotEqual(self.cycle.begin('session', 'Redis expires at 120 seconds')['turn'], self.turn)

    def test_native_event_ids_distinguish_turns_and_reject_changed_replays(self):
        first = self.cycle.begin('session', 'hello', 'one')
        second = self.cycle.begin('session', 'hello', 'two')
        self.assertNotEqual(first['turn'], second['turn'])
        self.assertEqual(self.cycle.begin('session', 'hello', 'one')['turn'], first['turn'])
        with self.assertRaises(MemoryConflict):
            self.cycle.begin('session', 'different', 'one')

    def test_only_verified_writes_allow_saved_and_retries_do_not_duplicate(self):
        with self.assertRaises(MemoryConflict):
            self.cycle.close(self.turn, 'saved')
        self.cycle.queue(self.turn, [self.action])
        with self.assertRaises(MemoryConflict):
            self.cycle.close(self.turn, 'saved')
        status = self.cycle.resume(self.turn)
        self.assertEqual(status['turns'][0]['actions'][0]['status'], 'applied')
        result = self.cycle.close(self.turn, 'saved')
        self.assertEqual(result['verified_writes'], 1)
        self.cycle.queue(self.turn, [self.action])
        self.cycle.resume(self.turn)
        self.assertTrue(self.cycle.close(self.turn, 'saved')['replayed'])
        self.assertEqual(len(self.cycle.store.history('redis-policy')), 1)

    def test_crash_after_save_before_acknowledgment_replays_receipt(self):
        import memory_store
        self.cycle.queue(self.turn, [self.action])
        original = memory_store.MemoryStore.save
        def crash(store, **kwargs):
            original(store, **kwargs)
            raise KeyboardInterrupt('simulated process death after commit')
        with patch.object(memory_store.MemoryStore, 'save', crash), self.assertRaises(KeyboardInterrupt):
            self.cycle.resume(self.turn)
        restarted = MemoryCycle(self.base / 'memory', self.cycle.project)
        status = restarted.resume(self.turn)
        receipt = status['turns'][0]['actions'][0]['receipt']
        self.assertTrue(receipt['replayed'])
        self.assertEqual(len(restarted.store.history('redis-policy')), 1)

    def test_update_crash_with_expected_revision_does_not_conflict_on_retry(self):
        self.cycle.store.save(**self.action)
        correction = dict(self.action, content='Redis conserva la caché 300 segundos.', overwrite=True, expected_revision=1)
        self.cycle.queue(self.turn, [correction])
        import memory_store
        original = memory_store.MemoryStore.save
        def crash(store, **kwargs):
            original(store, **kwargs)
            raise KeyboardInterrupt()
        with patch.object(memory_store.MemoryStore, 'save', crash), self.assertRaises(KeyboardInterrupt):
            self.cycle.resume(self.turn)
        result = self.cycle.resume(self.turn)
        self.assertEqual(result['turns'][0]['actions'][0]['status'], 'applied')
        self.assertEqual(len(self.cycle.store.history('redis-policy')), 2)

    def test_conflict_stays_visible_and_can_be_reconciled_without_forcing(self):
        self.cycle.store.save(**self.action)
        stale = dict(self.action, overwrite=True, expected_revision=0, content='Redis conserva la caché 300 segundos.')
        queued = self.cycle.queue(self.turn, [stale])
        identifier = queued['turns'][0]['actions'][0]['id']
        result = self.cycle.resume(self.turn)
        self.assertEqual(result['turns'][0]['actions'][0]['status'], 'conflict')
        with self.assertRaises(MemoryConflict):
            self.cycle.close(self.turn, 'saved')
        detail = self.cycle.status(self.turn, action=identifier)
        self.assertEqual(detail['turns'][0]['actions'][0]['proposal']['content'], stale['content'])
        self.cycle.discard(self.turn, identifier, 'Leída la revisión vigente; se reemplaza por propuesta conciliada.')
        self.cycle.queue(self.turn, [dict(stale, expected_revision=1)])
        self.cycle.resume(self.turn)
        self.assertEqual(self.cycle.close(self.turn, 'saved')['verified_writes'], 1)

    def test_no_change_needs_reason_and_cannot_hide_queued_or_applied_writes(self):
        with self.assertRaises(ValueError):
            self.cycle.close(self.turn, 'no_change')
        self.cycle.queue(self.turn, [self.action])
        with self.assertRaises(MemoryConflict):
            self.cycle.close(self.turn, 'no_change', 'Nothing')
        self.cycle.resume(self.turn)
        with self.assertRaises(MemoryConflict):
            self.cycle.close(self.turn, 'no_change', 'Nothing')

    def test_updates_require_revision_and_credentials_do_not_enter_the_queue(self):
        for action in (dict(self.action, overwrite=True), dict(self.action, content='-----BEGIN PRIVATE KEY-----')):
            with self.assertRaises(ValueError):
                self.cycle.queue(self.turn, [action])
        self.assertEqual(self.cycle.status(self.turn)['turns'][0]['actions'], [])

    def test_turn_cannot_be_accessed_through_another_project(self):
        other = MemoryCycle(self.base / 'memory', str(self.base / 'another'))
        with self.assertRaises(ValueError):
            other.queue(self.turn, [self.action])
        with self.assertRaises(ValueError):
            other.resume(self.turn)
        with self.assertRaises(ValueError):
            other.close(self.turn, 'no_change', 'Nothing')

    def test_external_edit_after_crash_is_not_mistaken_for_verified_write(self):
        import memory_store
        self.cycle.queue(self.turn, [self.action])
        original = memory_store.MemoryStore.save
        def crash(store, **kwargs):
            receipt = original(store, **kwargs)
            Path(receipt['path']).write_text('Cambio humano posterior')
            raise KeyboardInterrupt()
        with patch.object(memory_store.MemoryStore, 'save', crash), self.assertRaises(KeyboardInterrupt):
            self.cycle.resume(self.turn)
        result = self.cycle.resume(self.turn)
        self.assertEqual(result['turns'][0]['actions'][0]['status'], 'conflict')
        self.assertEqual((self.base / 'memory/redis-policy.md').read_text(), 'Cambio humano posterior')

    def test_operation_id_cannot_be_reused_for_different_content(self):
        self.cycle.store.save(**self.action, operation_id='receipt-1')
        with self.assertRaises(MemoryConflict):
            self.cycle.store.save(**dict(self.action, content='different'), operation_id='receipt-1')

    def test_real_process_death_after_commit_recovers_the_same_receipt(self):
        import subprocess
        script = '''
import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from memory_cycle import MemoryCycle
from memory_store import MemoryStore
cycle = MemoryCycle(sys.argv[2], sys.argv[3])
cycle.queue(sys.argv[4], [json.loads(sys.argv[5])])
original = MemoryStore.save
def crash(store, **kwargs):
    original(store, **kwargs)
    os._exit(23)
MemoryStore.save = crash
cycle.resume(sys.argv[4])
'''
        process = subprocess.run([sys.executable, '-B', '-c', script, str(ROOT / 'engine'),
                                  str(self.cycle.folder), self.cycle.project, self.turn, json.dumps(self.action)],
                                 capture_output=True, text=True, timeout=15)
        self.assertEqual(process.returncode, 23, process.stderr)
        status = self.cycle.resume(self.turn)
        receipt = status['turns'][0]['actions'][0]['receipt']
        self.assertTrue(receipt['replayed'])
        self.assertEqual(len(self.cycle.store.history('redis-policy')), 1)

    def test_concurrent_workers_apply_an_operation_once(self):
        from concurrent.futures import ThreadPoolExecutor
        self.cycle.queue(self.turn, [self.action])
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.cycle.resume(self.turn), range(4)))
        self.assertTrue(all(row['turns'][0]['actions'][0]['status'] == 'applied' for row in results))
        self.assertEqual(len(self.cycle.store.history('redis-policy')), 1)

    def test_post_tool_reminders_are_bounded_per_turn(self):
        self.assertTrue(self.cycle.claim_reminder(self.turn, 'PostToolUse'))
        self.assertFalse(self.cycle.claim_reminder(self.turn, 'PostToolUse'))
        self.cycle.close(self.turn, 'no_change', 'Sin hechos nuevos')
        self.assertFalse(self.cycle.claim_reminder(self.turn, 'Stop'))

    def test_index_edit_cannot_be_acknowledged_as_a_complete_projection(self):
        import memory_store
        self.cycle.queue(self.turn, [self.action])
        original = memory_store.MemoryStore.save
        def alter_index(store, **kwargs):
            result = original(store, **kwargs)
            (store.folder / 'MEMORY.md').write_text('# Índice editado por otra herramienta\n')
            return result
        with patch.object(memory_store.MemoryStore, 'save', alter_index):
            status = self.cycle.resume(self.turn)
        self.assertEqual(status['turns'][0]['actions'][0]['status'], 'conflict')
        with self.assertRaises(MemoryConflict):
            self.cycle.close(self.turn, 'saved')


    def test_latest_checkpoint_follows_commit_order_instead_of_turn_creation(self):
        first = self.cycle.begin('parallel-task', 'first')['turn']
        second = self.cycle.begin('parallel-task', 'second')['turn']
        self.cycle.close(second, 'no_change', 'Solo estado', checkpoint=dict(goal='Auditar', next_step='version B'))
        self.cycle.close(first, 'no_change', 'Conciliado después de B', checkpoint=dict(goal='Auditar', next_step='version C'),
                         checkpoint_revision=second)
        working = self.cycle.working(first)
        self.assertEqual(working['revision'], first)
        self.assertEqual(working['state']['next_step'], 'version C')
        with self.assertRaises(MemoryConflict):
            third = self.cycle.begin('parallel-task', 'third')['turn']
            self.cycle.close(third, 'no_change', 'Estado obsoleto', checkpoint=dict(goal='Auditar', next_step='old'),
                             checkpoint_revision=second)

    def test_old_checkpoint_schema_is_migrated_using_close_order(self):
        first = self.cycle.begin('migration-task', 'first')['turn']
        second = self.cycle.begin('migration-task', 'second')['turn']
        self.cycle.close(second, 'no_change', 'Estado anterior', checkpoint=dict(goal='Auditar', next_step='version B'))
        self.cycle.close(first, 'no_change', 'Estado posterior', checkpoint=dict(goal='Auditar', next_step='version C'), checkpoint_revision=second)
        with self.cycle.database() as db:
            with db:
                db.execute('DROP INDEX cycle_checkpoint_sequence')
                db.execute('ALTER TABLE cycle_turns DROP COLUMN checkpoint_sequence')
        restarted = MemoryCycle(self.cycle.folder, self.cycle.project)
        self.assertEqual(restarted.working(second)['state']['next_step'], 'version C')
        self.assertEqual(restarted.working(second)['revision'], first)

    def test_checkpoint_order_does_not_depend_on_wall_clock_progress(self):
        import datetime
        first = self.cycle.begin('clock-task', 'first')['turn']
        second = self.cycle.begin('clock-task', 'second')['turn']
        moments = [datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc),
                   datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)]
        with patch('memory_cycle.dt.datetime') as clock:
            clock.now.side_effect = moments
            self.cycle.close(second, 'no_change', 'Estado B', checkpoint=dict(goal='Auditar', next_step='B'))
            self.cycle.close(first, 'no_change', 'Estado C', checkpoint=dict(goal='Auditar', next_step='C'), checkpoint_revision=second)
        self.assertEqual(self.cycle.working(first)['state']['next_step'], 'C')
