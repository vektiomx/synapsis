"""Executable lifecycle contracts for scoped, inferred development experiences."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'engine'))
from experience_engine import ExperienceStore,observe
from memory_store import MemoryConflict,digest


class ExperienceEngineTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.root=self.base/'project';self.root.mkdir()
        self.policy=self.root/'policy.json';self.policy.write_text('{"retry":{"retain":true},"language":"python"}')
        self.store=ExperienceStore(self.base/'memory',self.root)
        self.data=dict(situation='Transient retry failures exhausted the provider budget.',
            action='Preserve recoverable input until the retention deadline.',
            rationale='A network failure does not establish that the work can be discarded.',
            outcome='The declared retention setting was observed enabled.',
            limitations='A configuration observation alone does not prove that recovery succeeds.',
            when=dict(paths=['src/queue.py'],keywords=['retry','provider','retention'],conditions=[dict(kind='json_equals',path='policy.json',pointer='/language',expected='python')]),
            checks=[dict(kind='json_equals',path='policy.json',pointer='/retry/retain',expected=True)],
            evidence=[dict(path='policy.json',sha256=digest(self.policy.read_text()))],
            counterexamples=['A job whose retention has expired should not be recovered.'])

    def save(self,name='retry-retention',data=None):return self.store.save(name,data or self.data,'agent:test')

    def test_receipt_versions_and_interpretation_remains_inferred(self):
        receipt=self.save();self.assertEqual(receipt['revision'],1)
        self.assertEqual(receipt['sha256'],self.store.latest('retry-retention')['sha256'])
        self.assertEqual(receipt['assurance'],'inferred_narrative')
        self.assertTrue(self.save()['replayed']);self.assertEqual(len(self.store.versions()),1)

    def test_observation_is_checked_not_the_narrative(self):
        self.save();report=self.store.verify('retry-retention')
        self.assertEqual(report['state'],'observed_support')
        self.assertIn('narrative',report['assurance'])
        recalled=self.store.recall('retry provider retention',active_path='src/queue.py')
        entry=recalled['experiences'][0]
        self.assertEqual(entry['state'],'inferred');self.assertTrue(entry['limitations'])

    def test_changed_evidence_becomes_stale_without_deleting_history(self):
        self.save();self.store.verify('retry-retention');self.policy.write_text('{"retry":{"retain":false},"language":"python"}')
        self.assertEqual(self.store.verify('retry-retention')['state'],'stale')
        self.assertEqual(len(self.store.versions()),1)
        packet=self.store.recall('retry retention')
        self.assertEqual(packet['experiences'][0]['use'],'historical_lead')

    def test_changed_applicability_conditions_abstain(self):
        self.save();self.policy.write_text('{"retry":{"retain":true},"language":"php"}')
        self.assertTrue(self.store.recall('retry retention')['abstained'])

    def test_active_path_cannot_cross_project_boundaries(self):
        self.save()
        with self.assertRaises(ValueError):self.store.recall('retry',str(self.base/'outside.py'))
        self.assertTrue(self.store.recall('retry','src/unrelated.py')['abstained'])

    def test_unrelated_query_abstains(self):
        self.save();self.assertTrue(self.store.recall('seasonal oranges and apples')['abstained'])

    def test_foreign_project_cannot_read_experience_database(self):
        self.save();other=self.base/'other';other.mkdir()
        packet=ExperienceStore(self.base/'memory',other).recall('retry retention')
        self.assertTrue(packet['abstained']);self.assertEqual(packet['experiences'],[])

    def test_revisions_require_expected_version(self):
        self.save();data=copy.deepcopy(self.data);data['limitations']='Only the declared setting was checked.'
        with self.assertRaises(MemoryConflict):self.store.save('retry-retention',data,'agent:test')
        receipt=self.store.save('retry-retention',data,'agent:test',expected_revision=1)
        self.assertEqual(receipt['revision'],2);self.assertEqual(len(self.store.versions()),2)

    def test_false_check_is_contradicted_without_rewriting_narrative(self):
        data=copy.deepcopy(self.data);data['checks'][0]['expected']=False
        self.save(data=data);self.assertEqual(self.store.verify('retry-retention')['state'],'contradicted')
        self.assertEqual(self.store.latest('retry-retention')['experience']['outcome'],data['outcome'])

    def test_same_meaning_types_not_coerced(self):
        self.assertEqual(observe(self.root,dict(kind='json_equals',path='policy.json',pointer='/retry/retain',expected=1))['status'],'contradicted')

    def test_missing_runtime_capability_is_never_a_pass(self):
        tests=self.root/'tests';tests.mkdir();(tests/'test_case.py').write_text('import unittest\nclass Case(unittest.TestCase):\n def test_ok(self):self.assertTrue(True)\n')
        with patch('experience_runner.shutil.which',return_value=None):
            result=observe(self.root,dict(kind='python_unittest',path='tests/test_case.py',case='Case.test_ok'),execute=True)
        self.assertEqual(result['status'],'unavailable')

    def test_executable_probe_is_not_run_automatically(self):
        tests=self.root/'tests';tests.mkdir();(tests/'test_case.py').write_text('raise RuntimeError("must not run")')
        result=observe(self.root,dict(kind='python_unittest',path='tests/test_case.py',case='Case.test_ok'))
        self.assertEqual(result['status'],'needs_execution')

    def test_arbitrary_commands_and_parent_paths_rejected(self):
        data=copy.deepcopy(self.data);data['checks']=[dict(kind='shell',command='touch forbidden')]
        with self.assertRaises(ValueError):self.save(data=data)
        data=copy.deepcopy(self.data);data['evidence'][0]['path']='../outside'
        with self.assertRaises(ValueError):self.save(data=data)

    def test_symlinks_cannot_be_read_as_evidence(self):
        outside=self.base/'outside.json';outside.write_text('{}');(self.root/'linked.json').symlink_to(outside)
        data=copy.deepcopy(self.data);data['evidence']=[dict(path='linked.json',sha256=digest('{}'))]
        with self.assertRaises(ValueError):self.save(data=data)

    def test_recognized_secrets_are_rejected_before_persistence(self):
        data=copy.deepcopy(self.data);data['outcome']='password=not-for-memory'
        with self.assertRaises(ValueError):self.save(data=data)
        self.assertFalse(self.store.path.exists())

    def test_checks_require_cited_file_snapshots(self):
        (self.root/'other.json').write_text('{}')
        data=copy.deepcopy(self.data);data['checks']=[dict(kind='json_equals',path='other.json',pointer='',expected={})]
        with self.assertRaises(ValueError):self.save(data=data)

    def test_declared_counterexamples_and_limits_survive_recall(self):
        self.save();entry=self.store.recall('retry retention')['experiences'][0]
        self.assertEqual(entry['counterexamples'],self.data['counterexamples'])
        self.assertIn('alone does not prove',entry['limitations'])

    def test_reported_feedback_idempotent_and_revision_bound(self):
        self.save();one=self.store.feedback('retry-retention','useful','agent:test',1,'task-one')
        self.assertEqual(one,self.store.feedback('retry-retention','useful','agent:test',1,'task-one'))
        with self.assertRaises(MemoryConflict):self.store.feedback('retry-retention','harmful','agent:test',1,'task-one')
        with self.assertRaises(MemoryConflict):self.store.feedback('retry-retention','useful','agent:test',0,'task-two')

    def test_packet_budget_is_respected(self):
        self.save();packet=self.store.recall('retry retention',budget=512)
        self.assertLessEqual(len(json.dumps(packet,ensure_ascii=False,sort_keys=True)),512)
        self.assertTrue(packet['abstained'])

    def test_supersession_preserves_history(self):
        self.save();data=copy.deepcopy(self.data);data['supersedes']='retry-retention';data['action']='Preserve a minimal recoverable input until the retention deadline.'
        self.save('retry-retention-v2',data)
        names=[x['name'] for x in self.store.recall('retry retention')['experiences']]
        self.assertEqual(names,['retry-retention-v2']);self.assertTrue(self.store.versions('retry-retention'))

    def test_duplicate_json_keys_do_not_produce_a_verified_observation(self):
        self.policy.write_text('{"retain":true,"retain":false}')
        with self.assertRaises(ValueError):observe(self.root,dict(kind='json_equals',path='policy.json',pointer='/retain',expected=False))

    def test_supersession_cycle_is_rejected(self):
        self.save();new=copy.deepcopy(self.data);new['supersedes']='retry-retention'
        self.save('next-retention',new)
        old=copy.deepcopy(self.data);old['supersedes']='next-retention'
        with self.assertRaises(MemoryConflict):self.store.save('retry-retention',old,'agent:test',1)

    def test_repeated_observation_does_not_expand_journal(self):
        self.save()
        for _ in range(5):self.store.verify('retry-retention')
        with self.store.database() as db:count=db.execute('SELECT count(*) FROM experience_checks').fetchone()[0]
        self.assertEqual(count,1)

    def test_hook_retrieves_experience_on_submit_and_before_edit(self):
        self.save()
        import hook_cycle
        cycle=type('Cycle',(),{})
        from memory_cycle import MemoryCycle
        from unittest.mock import patch
        with patch('conector_mcp.carpeta_memoria_de',return_value=self.store.folder),patch('hook_cycle.project_for',return_value=str(self.root)),patch('hooks_comun.contexto_automatico',return_value=True):
            text=hook_cycle.handle(dict(hook_event_name='PreToolUse',cwd=str(self.root),session_id='hook',tool_input=dict(file_path=str(self.root/'src/queue.py'))))
        self.assertIn('retry-retention',text)
        self.assertIn('no instrucciones',text)
        with patch('conector_mcp.carpeta_memoria_de',return_value=self.store.folder),patch('hook_cycle.project_for',return_value=str(self.root)),patch('hooks_comun.contexto_automatico',return_value=True),patch('conector_mcp.recordar',return_value=dict(evidence=[])),patch.dict(os.environ,{'SYNOPSIS_AUTO_REVIEW':'0'}):
            submitted=hook_cycle.handle(dict(hook_event_name='UserPromptSubmit',cwd=str(self.root),session_id='hook-submit',prompt='retry provider retention'))
        self.assertIn('retry-retention',submitted)

    def test_mcp_dispatch_exposes_same_lifecycle_without_execution(self):
        import conector_mcp
        with patch('conector_mcp.carpeta_memoria_de',return_value=self.store.folder):
            receipt=conector_mcp.experiencias(dict(proyecto=str(self.root),operacion='record',nombre='retry-retention',experiencia=self.data,fuente='agent:test'))
            recalled=conector_mcp.experiencias(dict(proyecto=str(self.root),operacion='recall',consulta='retry provider'))
        self.assertEqual(receipt['revision'],1);self.assertFalse(recalled['abstained'])
        schema=next(x for x in conector_mcp.HERRAMIENTAS if x['name']=='experiencias')
        self.assertNotIn('execute',schema['inputSchema']['properties'])

    def test_periodic_maintenance_only_wakes_existing_bound_queues(self):
        import memory_maintenance
        from auto_review import ReviewQueue
        queue=ReviewQueue(self.store.folder,self.root)
        turn=queue.cycle.begin('maintenance','retry')['turn']
        queue.remember(turn,'maintenance','retry','codex');queue.stop('maintenance')
        record=dict(project=str(self.root),memory=str(self.store.folder))
        with patch('project_identity.registered_memories',return_value=[record]),patch('auto_review.kick') as kick,patch.dict(os.environ,{'SYNOPSIS_AUTO_REVIEW':'1'}):
            result=memory_maintenance.sweep()
        self.assertEqual(result['checked'],1);kick.assert_called_once()

if __name__=='__main__':unittest.main()
