import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'engine'))
from semantic_memory import normalize, rank, Embeddings
from model_provider import ProviderError


class SemanticTest(unittest.TestCase):
    def test_real_vector_validation(self):
        self.assertEqual(normalize([3,4]), [.6,.8])
        for value in ([0,0], [float('nan'), 1], [float('inf'),1], [True,1], ['1',2]):
            with self.assertRaises(ProviderError):
                normalize(value)

    def test_semantic_paraphrase_cached_and_query_never_persisted(self):
        calls = []
        class Backend:
            identity = 'test-real-vector-protocol'
            def __call__(self, texts):
                calls.append(texts)
                return [[1.,0.] if any(x in t for x in ('descompuesto','malfunction')) else [0.,1.] for t in texts]
        index = SimpleNamespace(notas=[dict(titulo='Device', secciones=[0]),dict(titulo='Food', secciones=[1])],
                                secciones=[(None,None,1,'El aparato está descompuesto'),(None,None,1,'Fresh oranges')])
        snapshots={0:('current',{}),1:('current',{})}
        with tempfile.TemporaryDirectory() as tmp:
            result, status = rank(index, snapshots, 'A malfunction occurred', tmp, Backend())
            self.assertEqual(set(result), {0})
            self.assertEqual(status, 'ready')
            rank(index, snapshots, 'A malfunction occurred', tmp, Backend())
            self.assertEqual([len(c) for c in calls], [2,1,1])
            # Only a scoped snapshot subset can reach the provider or cached results.
            result, _ = rank(index, {1:('current',{})}, 'A malfunction occurred', tmp, Backend())
            self.assertEqual(result, {})
            self.assertNotIn(b'A malfunction occurred', (Path(tmp)/'.synopsis/vectors.sqlite3').read_bytes())

    def test_backend_failure_falls_back_without_query_disclosure(self):
        class Backend:
            identity='bad'
            def __call__(self, texts):
                raise ProviderError('provider_request_failed')
        index=SimpleNamespace(notas=[dict(titulo='x',secciones=[0])],secciones=[(None,None,1,'body')])
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(rank(index,{0:('current',{})},'secret-query',tmp,Backend()), ({},'degraded'))

    def test_embedding_response_order_and_dimensions_are_checked(self):
        provider=Embeddings('compatible','model','http://localhost:1234')
        with patch('semantic_memory.request_json', return_value=dict(data=[dict(index=1,embedding=[0,1]),dict(index=0,embedding=[1,0])])):
            self.assertEqual(provider(['a','b']), [[1.,0.],[0.,1.]])
        with patch('semantic_memory.request_json', return_value=dict(data=[dict(index=0,embedding=[1,0]),dict(index=0,embedding=[0,1])])):
            with self.assertRaises(ProviderError):
                provider(['a','b'])
