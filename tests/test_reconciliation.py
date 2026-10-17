import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'engine'))
from memory_store import MemoryStore, MemoryConflict
from reconciliation import inventory, review, apply_plan


class ReconciliationTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project=Path(self.temp.name)/'project'
        self.project.mkdir()
        self.folder=Path(self.temp.name)/'memory'
        self.store=MemoryStore(self.folder)
        for name, content in [('ttl','Redis conserva 300 segundos.'),('cache','Cache expires after five minutes.')]:
            self.store.save(filename=name,name=name,description='Policy',kind='project',content=content,
                            index_line=f'- [{name}]({name}.md)',source='user:test')

    def plan(self):
        action=dict(filename='ttl',name='ttl',description='Policy',kind='project',content='Redis conserva 300 segundos (cinco minutos).',
                    index_line='- [TTL](ttl.md)',source='agent:reconciliation',state='inferred',overwrite=True,expected_revision=1)
        transport=Mock()
        transport.complete.return_value=dict(findings=[dict(relation='duplicate',files=['ttl','cache'],reason='300 segundos = five minutes')], actions=[action],summary='Duplicate')
        return review(str(self.project),self.folder,transport)

    def test_review_is_read_only_and_apply_preserves_revisions(self):
        before=(self.folder/'ttl.md').read_bytes()
        plan=self.plan()
        self.assertEqual((self.folder/'ttl.md').read_bytes(),before)
        result=apply_plan(plan,str(self.project),self.folder)
        self.assertTrue(result['applied'])
        self.assertEqual(len(self.store.history('ttl')),2)
        self.assertTrue((self.folder/'cache.md').exists())

    def test_stale_plan_and_foreign_project_cannot_apply(self):
        plan=self.plan()
        (self.folder/'ttl.md').write_text('external edit')
        with self.assertRaises(MemoryConflict):
            apply_plan(plan,str(self.project),self.folder)
        with self.assertRaises(ValueError):
            apply_plan(plan,str(self.project.parent),self.folder)
        self.assertEqual((self.folder/'ttl.md').read_text(),'external edit')

    def test_model_cannot_confirm_inference_or_write_unreviewed_file(self):
        for key,value in [('state','confirmed'),('filename','other'),('expected_revision',0),('filename','../secret')]:
            plan=self.plan()
            plan['actions'][0][key]=value
            with self.assertRaises(ValueError):
                apply_plan(plan,str(self.project),self.folder)

    def test_unresolved_contradiction_is_a_finding_without_changes(self):
        transport=Mock()
        transport.complete.return_value=dict(findings=[dict(relation='contradiction',files=['ttl','cache'],reason='uncertain')],actions=[],summary='ask')
        plan=review(str(self.project),self.folder,transport)
        self.assertFalse(apply_plan(plan,str(self.project),self.folder)['applied'])

    def test_a_model_cannot_resolve_a_reported_contradiction_by_picking_a_winner(self):
        plan=self.plan()
        plan['findings'][0]['relation']='contradiction'
        with self.assertRaises(MemoryConflict):
            apply_plan(plan,str(self.project),self.folder)

    def test_archive_requires_a_surviving_duplicate(self):
        plan=self.plan()
        plan['actions'][0]['state']='archived'
        plan['findings'][0]['relation']='related'
        with self.assertRaises(MemoryConflict):
            apply_plan(plan,str(self.project),self.folder)

    def test_model_proposes_meaning_while_controller_constructs_write_mechanics(self):
        transport=Mock()
        transport.complete.return_value=dict(findings=[],actions=[dict(filename='ttl',description='Policy',kind='project',content='Redis conserva 300 segundos.',state='inferred')])
        plan=review(str(self.project),self.folder,transport)
        action=plan['actions'][0]
        self.assertEqual(action['name'],'ttl')
        self.assertEqual(action['index_line'],'- [ttl](ttl.md)')
        self.assertEqual(action['expected_revision'],1)
        self.assertTrue(action['overwrite'])
        self.assertEqual(action['source'],'agent:reconciliation')
