"""Lifecycle, context boundaries and non-destructive research contracts."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'engine'))
import test_decision_rag as decision_fixture
from experience_timeline import ExperienceTimeline, validate_validity
from task_context import build, diverse
from research_workbench import ResearchWorkbench, discover, apply_patches, validate_patch
from experience_engine import ExperienceStore
from memory_store import MemoryConflict,digest
from experiment_snapshot import fingerprint


class Cases(unittest.TestCase):
    def setUp(self):
        self.fixture=decision_fixture.DecisionRAGTest();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.store=self.fixture.store;self.root=self.fixture.root


class TimelineTest(Cases):
    def test_retirement_replay_conflict_and_restore_preserve_payload(self):
        timeline=ExperienceTimeline(self.store);original=self.store.latest('retry')
        receipt=timeline.change('retry','retired','Rule withdrawn','user:test',1,event='withdraw')
        self.assertEqual(receipt['sequence'],1)
        self.assertEqual({r['name'] for r in self.store.current()},{'reconcile'})
        self.assertEqual(self.store.latest('retry'),original)
        self.assertTrue(timeline.change('retry','retired','Rule withdrawn','user:test',1,event='withdraw')['replayed'])
        with self.assertRaises(MemoryConflict):timeline.change('retry','active','Restore','user:test',1,0)
        timeline.change('retry','active','Restore after review','user:test',1,1)
        self.assertEqual(len(self.store.current()),2)
        self.assertEqual(len(timeline.history('retry')['events']),2)

    def test_validity_requires_timezone_and_excludes_expired_or_scheduled(self):
        for validity in ({'until':'bad'},{'from':'2030-01-01'},{'from':'2030-01-02T00:00:00Z','until':'2030-01-01T00:00:00Z'}):
            with self.assertRaises(ValueError):validate_validity(validity)
        for name,validity in (('retry',{'until':'2000-01-01T00:00:00Z'}),('reconcile',{'from':'2099-01-01T00:00:00Z'})):
            data=copy.deepcopy(self.store.latest(name)['experience']);data['validity']=validity
            self.store.save(name,data,'fixture',1)
        self.assertEqual(self.store.current(),[])
        self.assertEqual(len(self.store.current(include_inactive=True)),2)
        self.assertEqual({x['state'] for x in ExperienceTimeline(self.store).history()['cases']},{'expired','scheduled'})

    def test_expired_replacement_does_not_revive_superseded_rule(self):
        data=self.fixture.case();data['supersedes']='retry';data['validity']={'until':'2000-01-01T00:00:00Z'}
        self.store.save('replacement',data,'fixture')
        self.assertNotIn('retry',{r['name'] for r in self.store.current()})

    def test_retirement_invalidates_an_old_decision_receipt(self):
        plan=self.fixture.plan(persist=True)
        ExperienceTimeline(self.store).change('retry','retired','Withdraw','user:test',1)
        with self.assertRaises(MemoryConflict):self.fixture.rag.outcome(plan['id'],'retry','useful','user:test','old-plan')

    def test_automatic_update_cannot_remove_expiration(self):
        from auto_review import ReviewQueue
        from evidence_guard import EvidenceLedger
        self.fixture.revise('retry',lambda d:d.update(validity={'until':'2099-01-01T00:00:00Z'}))
        old=self.store.latest('retry');ledger=EvidenceLedger(self.root,self.store.folder)
        for path in ('context.json','contract.txt'):ledger.tool(dict(tool='read_file',path=path))
        queue=ReviewQueue(self.store.folder,self.root)
        proposal=dict(name='retry',experience=copy.deepcopy(old['experience']),expected_revision=2)
        queue.prepare_experiences([proposal],ledger,{'retry':old})
        proposal['experience'].pop('validity')
        with self.assertRaises(ValueError):queue.prepare_experiences([proposal],ledger,{'retry':old})

    def test_old_revision_cannot_retire_newer_rule(self):
        self.fixture.revise('retry',lambda d:d.update(outcome='Additional observation'))
        with self.assertRaises(MemoryConflict):ExperienceTimeline(self.store).change('retry','retired','Withdraw','user:test',1)


class TaskContextTest(Cases):
    def test_budget_never_hides_one_opposing_alternative(self):
        for budget in (1024,3000,9000):
            packet=build(self.store,'retry payment timeout',budget=budget)
            self.assertLessEqual(len(json.dumps(packet,ensure_ascii=False,sort_keys=True)),budget)
            self.assertEqual(packet['used'],len(json.dumps(packet,ensure_ascii=False,sort_keys=True)))
            if packet['decisions']:
                self.assertEqual({a['choice'] for a in packet['decisions'][0]['alternatives']},{'retry','reconcile'})
            else:self.assertTrue(packet['omitted'])

    def test_notes_keep_exact_citations_deduplicate_and_reject_foreign_project(self):
        note=dict(path='/memory/a.md',start=1,end=2,text='Use the chosen payment policy.',sha256='a'*64,metadata={'state':'inferred'})
        packet=build(self.store,'payment retry',dict(project=self.store.project,evidence=[note,note]),budget=9000)
        self.assertEqual(packet['evidence'],[note])
        with self.assertRaises(ValueError):build(self.store,'payment',dict(project='/another/project',evidence=[note]))

    def test_diversity_prefers_new_topic_over_near_duplicate(self):
        items=[dict(text='payment timeout retry record'),dict(text='payment timeout retry record'),dict(text='invoice reconciliation ledger')]
        self.assertEqual(diverse(items)[1],items[2])

    def test_retired_case_never_reappears_in_task_context(self):
        ExperienceTimeline(self.store).change('retry','retired','No longer applicable','user:test',1)
        packet=build(self.store,'payment retry')
        self.assertFalse(any(c['name']=='retry' for g in packet['decisions'] for c in g['alternatives']))


class ResearchTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'repo';self.root.mkdir()
        self.path=self.root/'policy.py';self.original='def policy(context):\n    return 0\n';self.path.write_text(self.original)
        tests=self.root/'tests';tests.mkdir();(tests/'__init__.py').write_text('')
        (tests/'test_policy.py').write_text('import unittest\nfrom policy import policy\nclass Policy(unittest.TestCase):\n def test_value(self):\n  self.assertEqual(policy({}),41)\n')
        self.store=ExperienceStore(Path(self.temp.name)/'memory',self.root)
        self.workbench=ResearchWorkbench(self.store)
        self.patch=dict(path='policy.py',symbol='policy',sha256=digest(self.original),source='def policy(context):\n    return 41\n')
        self.test=dict(kind='python_unittest',path='tests/test_policy.py',case='Policy.test_value')
        self.proposal=dict(candidates=[dict(title='Correct policy',hypothesis='The declared value should satisfy the existing test.',patches=[self.patch],tests=[self.test])])

    def test_discovery_uses_real_ast_tests_without_exposing_oracle_body(self):
        context=self.workbench.prepare('policy')
        self.assertIn(self.test,context['tests'])
        self.assertNotIn('assertEqual',json.dumps(context))
        self.assertTrue(all(source['path']!='tests/test_policy.py' for source in context['sources']))
        self.assertEqual(context['sources'][0]['symbols'],['policy'])

    def test_source_with_embedded_credential_is_not_sent_for_inference(self):
        self.path.write_text('API_KEY = '+repr('sk-'+'x'*32)+'\n'+self.original)
        self.assertEqual(self.workbench.prepare('policy')['sources'],[])

    def test_plan_never_calls_model_or_executes_code(self):
        with patch('experience_runner.run_python_test') as runner:
            plan=self.workbench.run('policy',proposal=self.proposal)
        runner.assert_not_called();self.assertEqual(plan['state'],'needs_execution')
        self.assertEqual(self.path.read_text(),self.original)

    def test_test_or_io_or_signature_changes_are_rejected(self):
        for source in ('def policy(context):\n return open("tests/test_policy.py").read()','def policy(context):\n import os\n return 41','def policy(other):\n return 41','def policy(context):\n return context.__class__','def policy(context):\n len=context.get\n return len("x")'):
            with self.subTest(source=source),self.assertRaises(ValueError):validate_patch(self.original,dict(self.patch,source=source))
        with self.assertRaises(ValueError):apply_patches(self.root,[dict(self.patch,path='tests/test_policy.py')])
        self.assertEqual(self.path.read_text(),self.original)

    def test_changed_source_invalidates_proposal(self):
        self.path.write_text(self.original+'# edited\n')
        with self.assertRaises(MemoryConflict):self.workbench.run('policy',execute=True,proposal=self.proposal)

    def test_observed_improvement_is_recorded_without_applying_patch(self):
        sha=fingerprint(self.root)
        def run(project,check,**kwargs):return dict(status='observed_support' if kwargs.get('function_patches') else 'contradicted',source_snapshot_sha256=sha)
        with patch('experience_runner.run_python_test',side_effect=run):report=self.workbench.run('policy',execute=True,proposal=self.proposal)
        self.assertEqual(report['candidates'][0]['state'],'observed_improvement')
        self.assertTrue(report['recorded']);self.assertEqual(len(self.workbench.history()),1)
        previous=self.workbench.prepare('policy')['previous_experiments']
        self.assertEqual(previous[0]['id'],report['id'])
        recalled=build(self.store,'policy')
        self.assertEqual(recalled['research'][0]['id'],report['id'])
        self.assertEqual(recalled['research'][0]['use'],'historical_candidate_revalidate_before_reuse')
        self.assertEqual(previous[0]['applicability'],'same_snapshot')
        self.path.write_text(self.original+'# drift\n')
        self.assertEqual(self.workbench.prepare('policy')['previous_experiments'][0]['applicability'],'historical_revalidate')
        self.path.write_text(self.original)
        self.assertEqual(self.path.read_text(),self.original)

    def test_unavailable_or_changed_snapshot_cannot_earn_improvement(self):
        for result in (dict(status='unavailable'),dict(status='observed_support',source_snapshot_sha256='wrong')):
            with patch('experience_runner.run_python_test',return_value=result):report=self.workbench.run('policy',execute=True,proposal=self.proposal)
            self.assertEqual(report['candidates'][0]['state'],'unavailable')

    def test_missing_or_new_test_cannot_be_proposed(self):
        bad=copy.deepcopy(self.proposal);bad['candidates'][0]['tests'][0]['case']='Policy.test_invented'
        with self.assertRaises(ValueError):self.workbench.run('policy',proposal=bad)

if __name__=='__main__':unittest.main()
