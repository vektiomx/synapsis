#!/usr/bin/env python3
"""Frozen multilingual relevance probes and real isolated sensitivity experiments."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'engine'))
from local_semantics import discover
from experience_engine import ExperienceStore
from decision_rag import DecisionRAG
from experience_lab import ExperienceLab
from memory_store import digest

PAIRS=[
 ('Un enlace duro comparte las escrituras del archivo original.','A hard link shares writes with the original file.','Fresh oranges are delicious.'),
 ('Las operaciones no conmutativas requieren preservar el orden de los eventos.','Noncommuting operations must retain event order.','The garden flowers are growing.'),
 ('Conservar los bytes originales evita alterar identificadores firmados.','Preserving original bytes avoids changing signed identifiers.','A good recipe uses less sugar.'),
 ('La sesión del navegador necesita enviar una cookie después de un formulario de otro sitio.','The browser session must send a cookie after a cross-site form submission.','How should a worker multiply two matrices?'),
 ('Reanudar una transferencia requiere que la huella del archivo remoto siga coincidiendo.','Resuming a transfer requires the remote file fingerprint to still match.','Our team wants to plant more trees.'),
 ('Un nombre inexistente se almacena temporalmente solo cuando la respuesta negativa es autoritativa.','Cache a missing host name only when the negative answer is authoritative.','The orchestra plays a new symphony.'),
]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output');parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    backend=discover()
    if backend is None:raise SystemExit('Prepare local semantics with synopsis semantic setup first.')
    started=time.monotonic();rows=[]
    for spanish,english,unrelated in PAIRS:
        vectors=backend([spanish,english,unrelated])
        cosine=lambda a,b:sum(x*y for x,y in zip(a,b))
        positive=cosine(vectors[0],vectors[1]);negative=cosine(vectors[0],vectors[2])
        rows.append(dict(positive_cosine=positive,negative_cosine=negative,passed=positive>negative+.15))
    retrieval=[];experiments=[]
    with tempfile.TemporaryDirectory(prefix='synopsis-semantic-eval-') as temp:
        root=Path(temp)/'project';root.mkdir();folder=Path(temp)/'memory'
        (root/'estado.json').write_text('{"inmutable":true}')
        contract='Solo se permite compartir un inodo si la fuente no cambia.'
        (root/'contrato.txt').write_text(contract)
        store=ExperienceStore(folder,root)
        for immutable,choice in ((True,'enlace-duro'),(False,'copia-independiente')):
            data=dict(situation='Archivar artefactos cuyos bytes deben conservarse.',action=choice,rationale='Los enlaces comparten escrituras; una copia conserva sus propios bytes.',outcome='Caso sintético.',limitations='No demuestra causalidad.',when=dict(paths=[],keywords=['archivo','inodo','almacenamiento'],conditions=[]),
                decision=dict(key='archivo-inmutable',choice=choice,requires=[dict(kind='json_equals',path='estado.json',pointer='/inmutable',expected=immutable)]),
                checks=[dict(kind='text_contains',path='contrato.txt',text=contract)],evidence=[dict(path=p,sha256=digest((root/p).read_text())) for p in ('estado.json','contrato.txt')])
            store.save(choice,data,'fixture:multilingual-standalone')
        for query in ('How should I preserve build artifacts without losing their original content?','¿Cómo conservo los bytes de un artefacto?','Como devo guardar um artefato sem alterar seus bytes?'):
            packet=DecisionRAG(store).plan(query,budget=12000)
            selected=packet['groups'][0]['selected'] if packet['groups'] else None
            retrieval.append(dict(query=query,selected=selected,passed=selected=='enlace-duro',retrieval=packet.get('retrieval')))
        negative=DecisionRAG(store).plan('How do I grow oranges in a greenhouse?',budget=12000)
        retrieval.append(dict(query='unrelated',passed=negative['abstained']))
        if args.execute:
            tests=root/'tests';tests.mkdir();(tests/'__init__.py').write_text('')
            source=tests/'test_scope.py'
            source.write_text('import unittest,json\nclass Scope(unittest.TestCase):\n def test_sensitive(self):self.assertIs(json.load(open("estado.json"))["inmutable"],True)\n def test_weak(self):self.assertTrue(True)\n')
            original=store.latest('enlace-duro')['experience']
            for label,case in (('sensitive','Scope.test_sensitive'),('weak','Scope.test_weak')):
                import copy
                data=copy.deepcopy(original);data['checks']=[dict(kind='python_unittest',path='tests/test_scope.py',case=case)]
                data['evidence'].append(dict(path='tests/test_scope.py',sha256=digest(source.read_text())))
                store.save('lab-'+label,data,'fixture:lab')
                before=(root/'estado.json').read_bytes()
                report=ExperienceLab(store).explore('lab-'+label,execute=True)
                expected='scope_sensitive' if label=='sensitive' else 'non_discriminating'
                experiments.append(dict(case=label,expected=expected,passed=report['state']==expected and (root/'estado.json').read_bytes()==before,report=report))
    report=dict(protocol='synopsis.local-semantic-evaluation.v1',model_identity=backend.identity,translations=rows,retrieval=retrieval,experiments=experiments,passed=all(r['passed'] for r in rows+retrieval+experiments),seconds=round(time.monotonic()-started,3),limitation='Small synthetic multilingual and test-sensitivity probes; no competitive coding productivity claim. The context remains unchanged across query languages.')
    raw=json.dumps(report,ensure_ascii=False,indent=2)
    if args.output:Path(args.output).write_text(raw+'\n')
    print(raw);return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
