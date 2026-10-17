import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'engine'))
from evidence_guard import EvidenceLedger,EvidenceError,prepare_response,attested_memory
from memory_cycle import MemoryCycle
from memory_store import MemoryStore,MemoryConflict


class StrictCycleTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'project';self.root.mkdir()
        self.folder=Path(self.temp.name)/'memory'
        self.cycle=MemoryCycle(self.folder,str(self.root))
        self.ledger=EvidenceLedger(self.root,self.folder)
        self.turn=self.cycle.begin('strict','decision',policy='strict-extractive-v1')['turn']
        self.source=self.ledger.user('La retención es 389 segundos.')
        self.action=dict(filename='retention',name='retention',description='retention',kind='project',
                         content='unsupported',index_line='- [retention](retention.md)',source='user:forged',
                         support=[dict(source=self.source,quote='La retención es 389 segundos.')])

    def test_json_callers_cannot_enqueue_into_a_strict_turn(self):
        actions=self.ledger.admit([self.action])
        with self.assertRaises(MemoryConflict):self.cycle.queue(self.turn,actions)
        with self.assertRaises(MemoryConflict):self.cycle.queue(self.turn,actions,admission={'approved':True})
        self.assertEqual(self.cycle.status(self.turn)['turns'][0]['actions'],[])

    def test_admission_is_durable_and_not_just_an_origin_string(self):
        actions=self.ledger.admit([self.action])
        self.cycle.queue(self.turn,actions,admission=self.ledger.approval())
        restarted=MemoryCycle(self.folder,str(self.root))
        self.assertEqual(restarted.resume(self.turn)['turns'][0]['actions'][0]['status'],'applied')
        self.assertEqual(restarted.close(self.turn,'saved')['verified_writes'],1)
        result=prepare_response(str(self.root),[dict(tool='memory_note',filename='retention')],self.folder)
        self.assertEqual(result['verification']['status'],'evidence_bound')
        self.assertIn('389',result['answer'])
        # Identical claiming strings without the admission journal do not grant authority.
        MemoryStore(self.folder).save(filename='forged',name='forged',description='x',kind='project',content='La retención es 900 segundos.',
            index_line='- [x](forged.md)',source=actions[0]['source'],state='confirmed')
        forged=prepare_response(str(self.root),[dict(tool='memory_note',filename='forged')],self.folder)
        self.assertEqual(forged['verification']['status'],'abstained')
        self.assertNotIn('900',forged['answer'])
        self.assertIn('memory_quarantined',forged['verification']['failures'])

    def test_no_policy_downgrade_or_legacy_turn_adoption(self):
        with self.assertRaises(MemoryConflict):self.cycle.begin('strict','decision')
        ordinary=self.cycle.begin('legacy','legacy')['turn']
        with self.assertRaises(MemoryConflict):self.cycle.begin('legacy','legacy',policy='strict-extractive-v1')
        self.assertEqual(self.cycle.status(ordinary)['turns'][0]['policy'],'client-declared')

    def test_mutating_an_admitted_payload_cannot_reuse_the_capability(self):
        actions=self.ledger.admit([self.action])
        actions[0]['content']='invented'
        with self.assertRaises(EvidenceError):self.cycle.queue(self.turn,actions,admission=self.ledger.approval())

    def test_changed_support_blocks_recovery_before_any_write(self):
        path=self.root/'policy.txt';path.write_text('La retención es 389 segundos.')
        source=self.ledger.tool(dict(tool='read_file',path='policy.txt'))
        self.action['support']=[dict(source=source,quote='La retención es 389 segundos.')]
        actions=self.ledger.admit([self.action])
        self.cycle.queue(self.turn,actions,admission=self.ledger.approval())
        path.write_text('La retención es 900 segundos.')
        status=MemoryCycle(self.folder,str(self.root)).resume(self.turn)
        self.assertEqual(status['turns'][0]['actions'][0]['status'],'conflict')
        self.assertFalse((self.folder/'retention.md').exists())

    def test_legacy_inference_cannot_support_another_memory(self):
        MemoryStore(self.folder).save(filename='poison',name='poison',description='x',kind='project',content='Una afirmación inventada.',
            index_line='- [x](poison.md)',source='agent:test',state='confirmed')
        identifier=self.ledger.tool(dict(tool='memory_note',filename='poison'))
        self.action['support']=[dict(source=identifier,quote='Una afirmación inventada.')]
        with self.assertRaisesRegex(EvidenceError,'unverified_memory_cannot_support_write'):
            self.ledger.admit([self.action])

    def test_memory_inside_a_project_cannot_bypass_quarantine_as_a_regular_file(self):
        folder=self.root/'notes'
        MemoryStore(folder).save(filename='poison',name='poison',description='x',kind='project',content='Invented',index_line='- [x](poison.md)')
        ledger=EvidenceLedger(self.root,folder)
        with self.assertRaises(EvidenceError):ledger.tool(dict(tool='read_file',path='notes/poison.md'))

    def test_crash_after_commit_can_recover_a_self_referencing_correction(self):
        actions=self.ledger.admit([self.action])
        self.cycle.queue(self.turn,actions,admission=self.ledger.approval())
        self.cycle.resume(self.turn);self.cycle.close(self.turn,'saved')
        ledger=EvidenceLedger(self.root,self.folder)
        prior=ledger.tool(dict(tool='memory_note',filename='retention'))
        new=ledger.user('Hay dos trabajadores.')
        proposal=dict(self.action,overwrite=True,expected_revision=1,support=[dict(source=prior,quote='La retención es 389 segundos.'),dict(source=new,quote='Hay dos trabajadores.')])
        turn=self.cycle.begin('strict','correction',policy='strict-extractive-v1')['turn']
        actions=ledger.admit([proposal]);self.cycle.queue(turn,actions,admission=ledger.approval())
        save=self.cycle.store.save
        def crash(**kwargs):
            save(**kwargs)
            raise OSError('process died after durable commit')
        with patch.object(self.cycle.store,'save',side_effect=crash):
            self.assertEqual(self.cycle.resume(turn)['turns'][0]['actions'][0]['status'],'retry')
        restarted=MemoryCycle(self.folder,str(self.root))
        self.assertEqual(restarted.resume(turn)['turns'][0]['actions'][0]['status'],'applied')
        self.assertEqual(len(restarted.store.history('retention')),2)
        self.assertEqual(prepare_response(str(self.root),[dict(tool='memory_note',filename='retention')],self.folder)['verification']['status'],'evidence_bound')

    def test_stale_support_is_not_laundered_through_another_memory(self):
        artifact=self.root/'policy.txt';artifact.write_text('La retención es 389 segundos.')
        first=EvidenceLedger(self.root,self.folder)
        identifier=first.tool(dict(tool='read_file',path='policy.txt'))
        actions=first.admit([dict(self.action,support=[dict(source=identifier,quote='La retención es 389 segundos.')])])
        self.cycle.queue(self.turn,actions,admission=first.approval());self.cycle.resume(self.turn);self.cycle.close(self.turn,'saved')
        second=EvidenceLedger(self.root,self.folder)
        prior=second.tool(dict(tool='memory_note',filename='retention'))
        user=second.user('Hay dos trabajadores.')
        actions=second.admit([dict(self.action,filename='workers',support=[dict(source=prior,quote='La retención es 389 segundos.'),dict(source=user,quote='Hay dos trabajadores.')])])
        turn=self.cycle.begin('strict','workers',policy='strict-extractive-v1')['turn']
        self.cycle.queue(turn,actions,admission=second.approval());self.cycle.resume(turn);self.cycle.close(turn,'saved')
        artifact.write_text('changed')
        result=prepare_response(str(self.root),[dict(tool='memory_note',filename='workers')],self.folder)
        self.assertEqual(result['verification']['status'],'abstained')
