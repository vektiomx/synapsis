"""Reproducible common controller for the frozen competitive memory protocol.

Run prepare, then competitive_sdk.py per profile, then evaluate. All writes stay
in the selected benchmark directory. Native model tools are disabled. No git.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'engine'))
from behavior_memory import BehaviorMemory
from behavior_runner import run_calls
from experience_engine import ExperienceStore,encoded
from model_provider import ModelTransport
from research_workbench import ResearchWorkbench,SYSTEM
from competitive_corpus import write_repository,DESCRIPTOR

PROFILES=('synopsis-behavior-memory','mem0-inferred','mem0-raw','graphiti','shadowfrog-file-symbol','full-history','no-memory')


def read(path):return json.loads(Path(path).read_text())
def write(path,data):Path(path).write_text(json.dumps(data,indent=2,ensure_ascii=False,default=str)+'\n')


def prepare(base):
    if (base/'manifest.json').exists():raise ValueError('benchmark_exists_do_not_overwrite_results')
    base.mkdir(parents=True,exist_ok=True);corpus=read(ROOT/'docs/competitive_corpus.json');tasks=[]
    for split in ('development','reserved'):
        for item in corpus[split]:
            project=base/'repos'/item['id'];write_repository(project,item,historical=True)
            store=ExperienceStore(base/'attestations'/item['id'],project)
            start=time.monotonic();memory=BehaviorMemory(store)
            receipt=memory.capture(DESCRIPTOR,[dict(kind='python_unittest',path='tests/test_policy.py',case='Policy.test_history')],'benchmark:historical-source-and-real-test')
            if not receipt.get('captured'):raise ValueError('fixture_capture_failed:'+str(receipt))
            if item['scenario']=='withdrawn_policy':memory.retire(receipt['id'],'Historical policy explicitly withdrawn','benchmark:contract',0)
            elapsed=time.monotonic()-start;write_repository(project,item)
            artifacts=[item['artifact']]
            if item['scenario']=='irrelevant_distractors':
                artifacts.extend(dict(source_id=item['id']+'-distractor-'+str(i),callable=dict(path='unrelated_'+str(i)+'.py',symbol='policy'),policy='Unrelated component: never use for policy.py',source='def policy(context):\n return '+str(100+i)+'\n',observations=[],lifecycle='active',scope='Other file only.') for i in range(4))
            tasks.append(dict(id=item['id'],split=split,project=str(project),artifacts=artifacts,source_id=item['artifact']['source_id'],witness=receipt['id'],capture_seconds=elapsed))
    write(base/'inputs.json',tasks)
    hashes={name:hashlib.sha256((ROOT/'docs'/name).read_bytes()).hexdigest() for name in ('competitive_protocol.json','competitive_corpus.json')}
    write(base/'manifest.json',dict(protocol='synopsis.competitive-execution.v1',hashes=hashes,model='gpt-6.1-sol',profiles=PROFILES,
          note='Synthetic tasks, same common source-fetch and behavior controller for all profiles; SDK acquisition measured separately. Corpus and gold frozen before SDK acquisition.'))


class LoggedTransport:
    def __init__(self,base,task,profile,repetition):
        self.base=base;self.task=task;self.profile=profile;self.repetition=repetition;self.calls=0;self.characters=0
        self.native=ModelTransport('codex','gpt-6.1-sol',timeout=120)
    def complete(self,system,request,cwd):
        self.calls+=1
        if self.calls>2:raise ValueError('generation_budget_exhausted')
        self.characters+=len(system)+len(encoded(request));entry=dict(task=self.task,profile=self.profile,repetition=self.repetition,call=self.calls,system=system,request=request)
        start=time.monotonic()
        try:
            response=self.native.complete(system,request,cwd);entry['response']=response;return response
        except Exception as error:entry['error']=repr(error);raise
        finally:
            entry['seconds']=time.monotonic()-start
            with (self.base/'generation-trace.jsonl').open('a') as stream:stream.write(encoded(entry)+'\n')


def evaluate(base,profile,split,repetitions):
    corpus=read(ROOT/'docs/competitive_corpus.json');gold={item['id']:item for item in corpus[split]}
    inputs=[item for item in read(base/'inputs.json') if item['split']==split]
    output=base/('results-'+profile+'-'+split+'.json');results=read(output) if output.exists() else []
    retrievals=read(base/('retrieval-'+profile+'.json')) if profile not in ('synopsis-behavior-memory','full-history','no-memory') else {}
    for repetition in range(repetitions):
        for task in inputs:
            if any(r['task']==task['id'] and r['repetition']==repetition for r in results):continue
            start=time.monotonic();row=dict(task=task['id'],profile=profile,repetition=repetition,synthetic=True);item=gold[task['id']]
            store=ExperienceStore(base/'arms'/profile/split/str(repetition)/task['id'],task['project'])
            try:
                retrieval_start=time.monotonic()
                if profile=='synopsis-behavior-memory':
                    attested=BehaviorMemory(ExperienceStore(base/'attestations'/task['id'],task['project']))
                    witnesses=attested.relevant(DESCRIPTOR,include_cases=False)
                    source_ids=[task['source_id']] if witnesses else []
                    recalled=witnesses
                elif profile=='full-history':source_ids=[a['source_id'] for a in task['artifacts']];recalled=task['artifacts']
                elif profile=='no-memory':source_ids=[];recalled=[]
                else:
                    retrieval=retrievals[task['id']]
                    if retrieval.get('error'):raise ValueError('SDK acquisition/retrieval failed: '+retrieval['error'])
                    recalled=retrieval['memory'];source_ids=retrieval['source_ids']
                row['retrieval_seconds']=time.monotonic()-retrieval_start
                if task['id'] in retrievals:row['sdk_metrics']=retrievals[task['id']].get('metrics')
                # One source-fetch round is available equally, only for IDs that
                # the real retrieval returned. Never search the gold by answer.
                artifacts=[a for a in task['artifacts'] if a['source_id'] in source_ids][:2]
                if len(encoded(dict(memory=recalled,artifacts=artifacts)))>8000:
                    recalled=[]
                    while artifacts and len(encoded(artifacts))>8000:artifacts.pop()
                row['retrieved_source_ids']=source_ids;row['resolved_source_ids']=[a['source_id'] for a in artifacts]
                row['raw_retrieval']=recalled
                if task['source_id'] in row['resolved_source_ids']:
                    # Common controller capability, not a Synopsis-only oracle:
                    # hydrate precisely the attested artifact actually fetched.
                    original=ExperienceStore(base/'attestations'/task['id'],task['project'])
                    with original.database() as db:record=db.execute('SELECT * FROM behavior_capsules WHERE project=? AND id=?',(original.project,task['witness'])).fetchone()
                    with store.database() as db:
                        BehaviorMemory(store)._tables(db)
                        with db:db.execute('INSERT OR IGNORE INTO behavior_capsules VALUES(?,?,?,?,?,?,?,?,?)',tuple(record))
                workbench=ResearchWorkbench(store);packet=workbench.prepare(item['task']);packet['tests']=packet['tests'][:3]
                # Once a cited source is resolved, avoid duplicating its text
                # differently per engine: every agent sees the same artifact.
                packet['retrieved_history']=dict(artifacts=artifacts,memory=[] if artifacts else recalled)
                packet['current_contract']=read(Path(task['project'])/'contract.json')
                transport=LoggedTransport(base,task['id'],profile,repetition)
                proposal=transport.complete(SYSTEM,packet,task['project'])
                report=workbench.run(item['task'],execute=True,proposal=proposal)
                row.update(proposal=proposal,report=report,use_llm_calls=transport.calls,request_characters=transport.characters)
                candidates=[]
                for candidate in report['candidates']:
                    observed=run_calls(task['project'],DESCRIPTOR,item['hidden_calls'],function_patches=candidate['patches']) if item['expected_action']=='patch' else None
                    correct=bool(observed and observed.get('status')=='observed' and encoded(observed['results'])==encoded(item['hidden_expected']))
                    candidates.append(dict(state=candidate['state'],hidden_correct=correct,hidden_observation=observed))
                row['candidates']=candidates;row['expected_action']=item['expected_action'];row['abstained']=not candidates
                row['correct']=not candidates if item['expected_action']=='abstain' else any(c['hidden_correct'] for c in candidates)
                row['wrong_patch']=bool(candidates) and not row['correct']
                row['regression_escape']=any(c['state'] in ('observed_improvement','no_measured_gain') and not c['hidden_correct'] for c in candidates)
            except Exception as error:row.update(error=repr(error),traceback=traceback.format_exc(),correct=False)
            row['seconds']=time.monotonic()-start;results.append(row);write(output,results)
            print(profile,split,task['id'],repetition,'correct='+str(row.get('correct')),row.get('error',''),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','evaluate']);parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--profile',choices=PROFILES);parser.add_argument('--split',choices=['development','reserved'],default='development');parser.add_argument('--repetitions',type=int,default=1)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.base.resolve())
    else:evaluate(args.base.resolve(),args.profile,args.split,args.repetitions)
