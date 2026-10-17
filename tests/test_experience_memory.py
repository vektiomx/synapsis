import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'engine'))
from experience_memory import learn
from memory_store import MemoryStore


class ExperienceTest(unittest.TestCase):
    def test_experience_retains_outcome_evidence_and_inferred_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            evidence=root/'result.txt'
            evidence.write_text('42 cases passed')
            record=dict(task='Validar retención',action='Ejecutar pruebas',outcome='42 casos aprobados',
                        evidence=[dict(path='result.txt',sha256=hashlib.sha256(evidence.read_bytes()).hexdigest())])
            receipt=learn(str(root),root/'memory','retention-experience',record,'agent:test')
            note=Path(receipt['path']).read_text()
            self.assertIn('42 casos aprobados',note)
            self.assertIn('sha256:',note)
            self.assertEqual(MemoryStore(root/'memory').history('retention-experience')[0]['metadata']['state'],'inferred')
            record['evidence'][0]['sha256']='0'*64
            with self.assertRaises(ValueError):
                learn(str(root),root/'memory','bad',record,'agent:test')

    def test_foreign_evidence_cannot_enter_a_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            project=root/'project'
            project.mkdir()
            outside=root/'secret.txt'
            outside.write_text('outside')
            record=dict(task='Test',action='Read',outcome='done',evidence=[dict(path='../secret.txt',sha256=hashlib.sha256(outside.read_bytes()).hexdigest())])
            with self.assertRaises(ValueError):
                learn(str(project),project/'memory','outside',record,'agent:test')
