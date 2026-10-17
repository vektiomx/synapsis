"""Automatic updates may refresh evidence, never quietly broaden a learned rule."""
import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_decision_rag as fixtures
from auto_review import ReviewQueue
from evidence_guard import EvidenceLedger,EvidenceError
from memory_store import MemoryConflict


class ExperienceUpdateTest(unittest.TestCase):
    setUp=fixtures.DecisionRAGTest.setUp
    case=fixtures.DecisionRAGTest.case
    revise=fixtures.DecisionRAGTest.revise

    def proposal(self):
        self.queue=ReviewQueue(self.store.folder,self.root)
        self.ledger=EvidenceLedger(self.root,self.store.folder)
        for path in ('context.json','contract.txt'):self.ledger.tool(dict(tool='read_file',path=path,start=1))
        previous=self.store.latest('retry')
        data=copy.deepcopy(previous['experience'])
        data['limitations']+=' A subsequent local inspection found no broader guarantee.'
        return dict(name='retry',experience=data,expected_revision=previous['revision']),{'retry':previous}

    def test_observed_revision_can_refresh_without_erasing_history(self):
        proposal,visible=self.proposal()
        self.queue.prepare_experiences([proposal],self.ledger,visible)
        receipt=self.store.save(proposal['name'],proposal['experience'],'agent:auto-review:test',proposal['expected_revision'])
        self.assertEqual(receipt['revision'],2)
        self.assertEqual(len(self.store.versions('retry')),2)

    def test_scope_action_limit_and_counterexample_cannot_be_removed(self):
        for mutation in (lambda d:d['decision']['requires'][0].update(expected=False),
                         lambda d:d.update(action='Always retry'),
                         lambda d:d.update(limitations='No limits'),
                         lambda d:d.update(checks=[]),
                         lambda d:d['when'].update(conditions=[d['decision']['requires'][0]])):
            proposal,visible=self.proposal();mutation(proposal['experience'])
            with self.assertRaises(EvidenceError):self.queue.prepare_experiences([proposal],self.ledger,visible)

    def test_stale_or_unseen_revision_is_not_adopted(self):
        proposal,visible=self.proposal()
        with self.assertRaises(EvidenceError):self.queue.prepare_experiences([proposal],self.ledger,{})
        self.revise('retry',lambda d:d.update(outcome='A newer observation.'))
        with self.assertRaises(MemoryConflict):self.queue.prepare_experiences([proposal],self.ledger,visible)

    def test_reported_harm_is_not_cleared_by_automatic_revision(self):
        proposal,visible=self.proposal()
        self.store.feedback('retry','harmful','agent:test',1,'harm-one')
        with self.assertRaises(EvidenceError):self.queue.prepare_experiences([proposal],self.ledger,visible)

    def test_real_review_dispatch_applies_expected_revision(self):
        proposal,_=self.proposal()
        turn=self.queue.cycle.begin('update','Retry payment timeout observations','update')['turn']
        self.queue.remember(turn,'update','Retry payment timeout observations','codex','update')
        for path in ('context.json','contract.txt'):self.queue.track('update',dict(tool_input=dict(file_path=path)))
        self.queue.stop('update','No new guarantee.','update')
        def complete(system,request,cwd):
            self.assertTrue(request['experience_inventory'])
            return dict(outcome='no_change',reason='Update an inferred scoped experience.',actions=[],experiences=[proposal])
        self.queue.process_one(type('Transport',(),{'complete':staticmethod(complete)})())
        self.assertEqual(self.queue.status()[0]['state'],'complete')
        self.assertEqual(self.store.latest('retry')['revision'],2)

if __name__=='__main__':unittest.main()
