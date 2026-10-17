"""Regression contracts frozen from the independent 0.7 audit, not quality scores."""
import copy
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_decision_rag as fixtures


class BoundaryRegressionTest(unittest.TestCase):
    setUp=fixtures.DecisionRAGTest.setUp
    case=fixtures.DecisionRAGTest.case
    plan=fixtures.DecisionRAGTest.plan
    group=fixtures.DecisionRAGTest.group
    revise=fixtures.DecisionRAGTest.revise
    def test_dynamic_file_does_not_become_static_because_check_duplicates_guard(self):
        self.revise('retry',lambda d:d['checks'].append(copy.deepcopy(d['decision']['requires'][0])))
        self.context.write_text('{"idempotent":true,"unrelated":"new"}')
        self.assertEqual(self.group()['selected'],'retry')
        self.context.write_text('{}')
        group=self.group()
        self.assertIsNone(group['selected'])
        self.assertEqual(group['state'],'needs_evidence')
        self.assertTrue(group['probes'])

    def test_support_contract_still_invalidates_after_dynamic_fix(self):
        self.revise('retry',lambda d:d['checks'].append(copy.deepcopy(d['decision']['requires'][0])))
        self.contract.write_text('Prior policy withdrawn. No replacement is established.')
        self.assertIsNone(self.group()['selected'])

    def test_semantic_candidates_cannot_override_false_requirements(self):
        from semantic_memory import normalize
        class SemanticProtocol:
            identity='unit-protocol-only-not-a-quality-benchmark'
            def __call__(self,texts):return [[1.,0.] for text in texts]
        with patch('experience_retrieval.discover',return_value=SemanticProtocol()):
            packet=self.rag.plan('¿Debo volver a cobrar tras perder la respuesta?')
        self.assertEqual(packet['groups'][0]['selected'],'retry')
        self.assertEqual(len(packet['groups'][0]['alternatives']),2)
        self.assertEqual(packet['retrieval']['semantic'],'ready')

    def test_probe_prefers_a_discriminator_over_a_shared_unknown_requirement(self):
        for name in ('retry','reconcile'):
            self.revise(name,lambda d:d['decision']['requires'].append(dict(kind='json_equals',path='context.json',pointer='/common',expected=True)))
        self.context.write_text('{}')
        group=self.group()
        self.assertEqual(group['probes'][0]['pointer'],'/idempotent')
        self.assertEqual(group['probes'][0]['eliminates_at_least'],1)
        self.assertEqual(group['probes'][1]['eliminates_at_least'],0)


class VectorCacheContractTest(unittest.TestCase):
    def test_scoped_lookup_does_not_evict_other_file_or_persist_query(self):
        import tempfile
        from experience_retrieval import semantic_scores
        fixture=fixtures.DecisionRAGTest();fixture.setUp()
        try:
            first=fixture.store.latest('retry');first['_project']=str(fixture.root)
            second=fixture.store.latest('reconcile');second['_project']=str(fixture.root)
            calls=[]
            class Backend:
                identity='unit-cache-protocol'
                def __call__(self,texts):calls.append(len(texts));return [[1.,0.] for text in texts]
            backend=Backend()
            semantic_scores([first],'private-query-one',fixture.store.folder,backend)
            semantic_scores([second],'private-query-two',fixture.store.folder,backend)
            before=len(calls)
            semantic_scores([first],'private-query-three',fixture.store.folder,backend)
            self.assertEqual(calls[before:],[1])
            raw=(fixture.store.folder/'.synopsis/experience-vectors.sqlite3').read_bytes()
            self.assertNotIn(b'private-query',raw)
        finally:fixture.doCleanups()

if __name__=='__main__':unittest.main()
