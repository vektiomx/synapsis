#!/usr/bin/env python3
"""Reproducible retrieval evaluation. Synthetic evidence; no LLM judge or personal data."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'engine'))


def main():
    dataset = json.loads((ROOT / 'tests/fixtures/memory_eval.json').read_text())
    with tempfile.TemporaryDirectory(prefix='synopsis-eval-') as tmp:
        base = Path(tmp)
        project = base / 'project'
        project.mkdir()
        other = base / 'other'
        other.mkdir()
        (other / 'foreign.md').write_text('# Confidencial\n\nEl acuario tiene peces de arrecife.\n')
        folder = base / 'memory'
        config = base / 'config.json'
        config.write_text(json.dumps({'usuario': 'Evaluation', 'fuentes': [
            {'id': 'memory', 'memoria': True, 'proyecto': str(project), 'raices': [[str(folder), False, '']]},
            {'id': 'other', 'raices': [[str(other), True, '']]},
        ], 'proyectos': [{'raiz': str(project), 'alias': 'project'}, {'raiz': str(other), 'alias': 'other'}]}))
        os.environ['CEREBRO_CONFIG'] = str(config)
        os.environ['CLAUDE_PLUGIN_DATA'] = str(base)
        from memory_store import MemoryStore
        store = MemoryStore(folder)
        for note in dataset['notes']:
            name = note['name']
            store.save(filename=name, name=name, description=note['description'], kind='project',
                       content=note['content'], index_line=f'- [{name}]({name}.md)', source='synthetic:retrieval-eval',
                       state=note.get('state', 'confirmed'), expires_at=note.get('expires_at'), cues=note.get('cues'))
        import cerebro, buscador
        from context_memory import recall
        brain = cerebro.Cerebro()
        brain.recolectar()
        brain.analizar(base / 'suggestions.json', con_parecidas=False, con_entidades=False)
        index = buscador.Indice(brain)
        rows = []
        positives = hits = negatives = abstentions = leaks = forbidden = 0
        reciprocal = 0
        for case in dataset['queries']:
            start = time.perf_counter()
            packet = recall(index, case['query'], str(project), budget=3000, limit=5)
            elapsed = (time.perf_counter() - start) * 1000
            names = [Path(item['path']).stem for item in packet['evidence']]
            if case['expected']:
                positives += 1
                if case['expected'] in names:
                    hits += 1
                    reciprocal += 1 / (names.index(case['expected']) + 1)
            else:
                negatives += 1
                abstentions += packet['abstained']
            leaks += sum('/other/' in item['path'] for item in packet['evidence'])
            forbidden += sum(name in case.get('forbidden', []) for name in names)
            rows.append(dict(query=case['query'], expected=case['expected'], returned=names, ms=round(elapsed, 2)))
        passed = hits == positives and abstentions == negatives and leaks == forbidden == 0
        report = dict(dataset='synthetic-regression-v1', cases=len(rows), positive_cases=positives,
                      recall_at_5=round(hits / positives, 4), mrr=round(reciprocal / positives, 4),
                      negative_cases=negatives, abstention_accuracy=round(abstentions / negatives, 4),
                      project_leaks=leaks, superseded_leaks=forbidden, passed=passed, results=rows,
                      limitation='Retrieval regressions only; does not measure model intelligence or real-world accuracy.')
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
