#!/usr/bin/env python3
"""Replay immutable auto-captures from the independent audit; not a coding benchmark."""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'engine'))
from experience_engine import ExperienceStore
from decision_rag import DecisionRAG
from memory_store import digest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output')
    args=parser.parse_args()
    frozen=json.loads((ROOT/'tests/fixtures/captured_experiences_v07.json').read_text())
    results=[];started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='synopsis-upgrade-replay-') as tmp:
        for entry in frozen['domains']:
            domain=entry['domain'];project=Path(tmp)/domain['key'];project.mkdir()
            folder=Path(tmp)/(domain['key']+'-memory');store=ExperienceStore(folder,project)
            (project/'contract.txt').write_text(domain['contract'])
            for original in entry['experiences']:
                data=copy.deepcopy(original['experience'])
                expected=data['decision']['requires'][0]['expected']
                (project/'context.json').write_text(json.dumps({domain['field']:expected}))
                # Original evidence bytes must match. No regeneration or relabeling.
                for evidence in data['evidence']:
                    assert digest((project/evidence['path']).read_text())==evidence['sha256']
                store.save(original['name'],data,'fixture:unchanged-v07-capture')
            rag=DecisionRAG(store)
            for label,value,changed,irrelevant in [('positive',True,False,False),('negative',False,False,False),('unknown',None,False,False),('withdrawn',True,True,False),('irrelevant-field',True,False,True)]:
                context={} if value is None else {domain['field']:value}
                if irrelevant:context['non_semantic_observation']=312
                (project/'context.json').write_text(json.dumps(context))
                (project/'contract.txt').write_text('The old contract is withdrawn; replacement behavior has not yet been established.' if changed else domain['contract'])
                target=None if value is None or changed else next(i['experience']['decision']['choice'] for i in entry['experiences'] if i['experience']['decision']['requires'][0]['expected'] is value)
                before=time.monotonic();packet=rag.plan(domain['query'],budget=16000);elapsed=time.monotonic()-before
                groups=packet['groups'];choice=groups[0]['selected'] if groups else None
                probes=groups[0]['probes'] if groups else []
                passed=bool(groups) and choice==target and (label!='unknown' or bool(probes))
                results.append(dict(domain=domain['key'],scenario=label,expected=target,selected=choice,groups=len(groups),probes=len(probes),passed=passed,seconds=round(elapsed,5),retrieval=packet.get('retrieval')))
    report=dict(protocol='synopsis.retrieval-upgrade.v1',source_sha256=frozen['source_sha256'],passed=all(r['passed'] for r in results),rows=results,seconds=round(time.monotonic()-started,3),limitation='Regression replay of frozen synthetic auto-captures, not new independent holdout evidence or measured coding productivity.')
    raw=json.dumps(report,ensure_ascii=False,indent=2)
    if args.output:Path(args.output).write_text(raw+'\n')
    print(raw)
    return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
