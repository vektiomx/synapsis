#!/usr/bin/env python3
"""Real inference and isolated tests with actual decision experiences in the packet.

Experiences are authored fixtures, not autonomous learning. No competitor ranking.
The all-history arm has equivalent policy information; removing experiences has none.
"""
import argparse
import json
import os
import shutil
from pathlib import Path
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'engine'))
from experience_engine import ExperienceStore
from memory_store import digest
from research_workbench import ResearchWorkbench,SYSTEM
from model_provider import ModelTransport
from experience_runner import run_python_test


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model',required=True);parser.add_argument('--provider',default='codex');parser.add_argument('--output',required=True);args=parser.parse_args()
    report=dict(protocol='synopsis.research-transfer-evaluation.v1',model=args.model,rows=[],negative_controls=[],calls=[],
        limitation='Two synthetic Python repositories, one call per arm. Authored experiences, not autonomous acquisition or OSS productivity. Equivalent full history is a positive control, not an inferior competitor.')
    transport=ModelTransport(args.provider,args.model,timeout=120)
    save=lambda:Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    with tempfile.TemporaryDirectory(prefix='synopsis-research-transfer-') as temp:
        for index,(field,values) in enumerate((('transient',[43,71]),('deduplicated',[17,31]))):
            project=Path(temp)/('case-'+str(index));project.mkdir();tests=project/'tests';tests.mkdir();(tests/'__init__.py').write_text('')
            source='def policy(context):\n    return 0\n';(project/'policy.py').write_text(source)
            contract='Policy must respect the recorded mode-specific values, including the opposite mode. A local test is not a production guarantee.'
            (project/'contract.txt').write_text(contract)
            hidden='import unittest\nfrom policy import policy\nclass Policy(unittest.TestCase):\n def test_positive(self): self.assertEqual(policy({'+repr(field)+':True}),'+str(values[0])+')\n def test_negative(self): self.assertEqual(policy({'+repr(field)+':False}),'+str(values[1])+')\n def test_extra_context(self): self.assertEqual(policy({'+repr(field)+':False,"unrelated":True}),'+str(values[1])+')\n'
            (tests/'test_policy.py').write_text(hidden)
            store=ExperienceStore(Path(temp)/('memory-'+str(index)),project)
            histories=[]
            for value,number in zip((True,False),values):
                (project/'context.json').write_text(json.dumps({field:value}))
                action=f'Return exactly {number} for {field}={str(value).lower()}.';histories.append(action)
                data=dict(situation='Implement the recorded mode-specific numeric policy.',action=action,rationale='A fixture observation fixed this value for this mode only.',outcome='Reported prior fixture result; recheck against current tests.',limitations='Authored synthetic experience; no causal or production claim.',
                    when=dict(paths=['policy.py'],keywords=['policy',field],conditions=[]),
                    evidence=[dict(path=p,sha256=digest((project/p).read_text())) for p in ('context.json','contract.txt')],
                    checks=[dict(kind='text_contains',path='contract.txt',text=contract)],
                    decision=dict(key='mode-policy',choice='mode-'+str(value).lower(),requires=[dict(kind='json_equals',path='context.json',pointer='/'+field,expected=value)]))
                store.save('mode-'+str(value).lower(),data,'fixture:authored-policy')
            (project/'context.json').write_text(json.dumps({field:True}))
            workbench=ResearchWorkbench(store);query='Implement policy(context) for both modes from the recorded evidence, including '+field+'.'
            for arm in ('without-experiences','full-history','synopsis'):
                arm_store=ExperienceStore(Path(temp)/('memory-'+str(index)+'-'+arm),project)
                arm_store.path.parent.mkdir(parents=True,mode=0o700)
                shutil.copy2(store.path,arm_store.path)
                workbench=ResearchWorkbench(arm_store)
                started=time.monotonic();seen=[]
                class Measured:
                    def complete(self,system,request,cwd):
                        request=json.loads(json.dumps(request))
                        if arm!='synopsis':request['experiences']=dict(groups=[],abstained=True)
                        if arm=='full-history':request['history']=histories
                        seen.append(request)
                        response=transport.complete(system,request,cwd)
                        report['calls'].append(dict(case=index,arm=arm,response=response,request=request,request_chars=len(json.dumps(request)),seconds=round(time.monotonic()-started,3)))
                        save();return response
                try:
                    outcome=workbench.run(query,transport=Measured(),execute=True)
                    states=[c['state'] for c in outcome['candidates']]
                    if seen[0].get('previous_experiments'):raise ValueError('cross_arm_history_leak')
                    groups=seen[0]['experiences'].get('groups',[])
                    report['rows'].append(dict(case=index,arm=arm,groups_used=len(groups),alternatives_used=sum(len(g['alternatives']) for g in groups),
                        outcome=outcome,passed=any(s=='observed_improvement' for s in states),abstained=not states,source_unchanged=(project/'policy.py').read_text()==source))
                except Exception as error:report['rows'].append(dict(case=index,arm=arm,passed=False,error=type(error).__name__))
                save()
            # Negative control: this candidate repairs one mode but breaks a passing
            # independent test. Requesting only the repaired mode cannot omit controls.
            (project/'policy.py').write_text('def policy(context):\n    return '+str(values[1])+'\n')
            original=(project/'policy.py').read_text()
            proposal=dict(candidates=[dict(title='Unsafe constant',hypothesis='Negative control, must detect regression.',
                patches=[dict(path='policy.py',symbol='policy',sha256=digest(original),source='def policy(context):\n    return '+str(values[0])+'\n')],
                tests=[dict(kind='python_unittest',path='tests/test_policy.py',case='Policy.test_positive')])])
            observed=ResearchWorkbench(store).run(query,proposal=proposal,execute=True)
            report['negative_controls'].append(dict(case=index,passed=observed['candidates'][0]['state']=='regression',outcome=observed))
    report['scores']={arm:dict(passed=sum(r.get('passed',False) for r in report['rows'] if r['arm']==arm),total=sum(r['arm']==arm for r in report['rows']),abstained=sum(r.get('abstained',False) for r in report['rows'] if r['arm']==arm)) for arm in ('without-experiences','full-history','synopsis')}
    report['passed']=all(r.get('passed',False) for r in report['rows'] if r['arm'] in ('synopsis','full-history')) and all(r.get('abstained',False) for r in report['rows'] if r['arm']=='without-experiences') and all(r['passed'] for r in report['negative_controls'])
    save();print(json.dumps(dict(passed=report['passed'],scores=report['scores'],negative_controls=[r['passed'] for r in report['negative_controls']],calls=len(report['calls']))))
    return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
