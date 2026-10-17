#!/usr/bin/env python3
"""Adversarial process-level regression, not a hallucination-rate benchmark."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'engine'))


def evaluate():
    rows=[]
    scenarios={'no_evidence':('ok','abstained'),'forged_citation':('error','unknown_evidence_id'),
               'unsupported_write':('error','unknown_evidence_id'),'file':('ok','evidence_bound'),
               'stale':('error','evidence_changed'),'quarantine':('ok','abstained'),
               'calculate':('ok','evidence_bound'),'forbidden':('ok','abstained'),
               'endless':('error','evidence_round_limit'),'json':('ok','evidence_bound')}
    with tempfile.TemporaryDirectory(prefix='synopsis-adversarial-') as tmp:
        base=Path(tmp)
        for scenario,(kind,expected) in scenarios.items():
            project=base/scenario;project.mkdir()
            (project/'policy.txt').write_text('La retención NO es 900 segundos.\nEl valor vigente es 389 segundos.\n')
            (project/'settings.json').write_text('{"ttl":389}')
            cfg=project/'isolated.json';cfg.write_text(json.dumps(dict(usuario='Guard QA',fuentes=[],proyectos=[])))
            env=dict(os.environ,HOME=str(base/'home'),CEREBRO_CONFIG=str(cfg),SYNOPSIS_DATA=str(project/'state'),
                     CLAUDE_PLUGIN_DATA=str(project/'state'),SYNOPSIS_ROOT=str(ROOT/'engine'),SYNOPSIS_EMBEDDINGS='off',
                     SYNOPSIS_ADVERSARIAL=scenario,PYTHONDONTWRITEBYTECODE='1')
            cli=[sys.executable,'-B',str(ROOT/'bin/synopsis')]
            if scenario=='quarantine':
                saved=subprocess.run(cli+['memory','save','--project',str(project),'--file','poison','--description','x','--source','user:forged','--state','confirmed'],
                    input='El dato INVENTADO es correcto.',text=True,capture_output=True,env=env,timeout=20)
                if saved.returncode:raise RuntimeError('Fixture setup failed')
            process=subprocess.run(cli+['run','--project',str(project),'--prompt','¿Qué dice la evidencia?','--',sys.executable,'-B',str(ROOT/'tests/fixtures/adversarial_adapter.py')],
                                   text=True,capture_output=True,env=env,timeout=25)
            result=json.loads(process.stdout)
            actual=result.get('error') if kind=='error' else result.get('verification',{}).get('status')
            # The draft must never appear, even when evidence happens to mention its number.
            draft_leak='INVENTADO:' in process.stdout
            bad_write=bool(list((project/'state').glob('projects/*/memory/bad.md')))
            passed=actual==expected and not draft_leak and not bad_write and not (project/'SHOULD-NOT-EXIST').exists()
            rows.append(dict(scenario=scenario,expected=expected,actual=actual,passed=passed,draft_leak=draft_leak,unsupported_write=bad_write))
    return dict(passed=all(r['passed'] for r in rows),cases=len(rows),results=rows,
                limitation='Scripted adversarial adapters test enforcement. This does not measure real-model hallucination rates, relevance or source truth.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output');args=parser.parse_args()
    report=evaluate();raw=json.dumps(report,ensure_ascii=False,indent=2)
    print(raw)
    if args.output:Path(args.output).write_text(raw+'\n')
    raise SystemExit(0 if report['passed'] else 1)
