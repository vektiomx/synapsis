"""Challenge an existing test under bounded interventions in disposable JSON context.

A passing test that cannot distinguish contexts is not evidence of a general rule.
Experiments never modify the user's checkout or promote a narrative to verified truth.
"""
import copy
import json
import re
from pathlib import Path
import uuid

from evidence_guard import read_regular,scoped_path
from experience_engine import check_spec,encoded,now
from memory_store import digest


def apply_context(snapshot,overrides):
    if not isinstance(overrides,list) or not 1<=len(overrides)<=6:raise ValueError('invalid_context_intervention')
    for check in overrides:
        check_spec(check)
        if check['kind']!='json_equals':raise ValueError('only_json_context_interventions')
        path=scoped_path(Path(snapshot),check['path'])
        def unique(items):
            value={}
            for key,item in items:
                if key in value:raise ValueError('duplicate_context_key')
                value[key]=item
            return value
        data=json.loads(read_regular(path),object_pairs_hook=unique,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_context')))
        if not check['pointer']:data=check['expected']
        else:
            if re.search(r'~(?![01])',check['pointer']):raise ValueError('invalid_context_pointer')
            parts=[p.replace('~1','/').replace('~0','~') for p in check['pointer'].split('/')[1:]]
            try:
                cursor=data
                for part in parts[:-1]:
                    if isinstance(cursor,list) and not re.fullmatch(r'0|[1-9][0-9]*',part):raise ValueError('invalid_context_index')
                    cursor=cursor[int(part)] if isinstance(cursor,list) else cursor[part]
                part=parts[-1]
                if isinstance(cursor,list):
                    if not re.fullmatch(r'0|[1-9][0-9]*',part):raise ValueError('invalid_context_index')
                    cursor[int(part)]=check['expected']
                else:cursor[part]=check['expected']
            except (KeyError,IndexError,TypeError):raise ValueError('invalid_context_pointer') from None
        path.write_text(encoded(data),encoding='utf-8')


class ExperienceLab:
    def __init__(self,store):self.store=store

    def latest(self,name,revision):
        if not self.store.path.exists():return None
        with self.store.database() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='experience_experiments'").fetchone():return None
            row=db.execute('SELECT id,report,created FROM experience_experiments WHERE project=? AND name=? AND revision=? ORDER BY rowid DESC LIMIT 1',(self.store.project,name,revision)).fetchone()
        if not row:return None
        report=json.loads(row[1])
        return dict(id=row[0],state=report['state'],created=row[2],assurance='Historical test sensitivity; rerun after changes. Not causal proof.')

    def explore(self,name,execute=False,max_runs=3):
        if type(max_runs) is not int or not 1<=max_runs<=4:raise ValueError('invalid_experiment_budget')
        row=self.store.latest(name);data=row['experience']
        if 'decision' not in data:raise ValueError('experiment_requires_decision_case')
        guards=list({encoded(c):c for c in data['when']['conditions']+data['decision']['requires']}.values())
        tests=[c for c in data['checks'] if c['kind']=='python_unittest']
        packet=dict(protocol='synopsis.experience-lab.v1',name=name,revision=row['revision'],runs=[],executed=False,
                    assurance='Named test sensitivity under one-at-a-time context interventions, not causal proof or exhaustive verification.')
        if not tests or any(g['kind']!='json_equals' for g in guards):
            return dict(packet,state='unavailable',reason='requires_existing_python_test_and_json_context')
        # Only existing, source-backed tests can be executed; no generated shell/code.
        from decision_rag import DecisionRAG
        assessment=DecisionRAG(self.store)._assess(row)
        if assessment['stale_paths']:return dict(packet,state='stale',reason='support_changed')
        variants=[dict(label='declared-context',overrides=guards)]
        for index,guard in enumerate(guards):
            if type(guard['expected']) is bool:
                altered=copy.deepcopy(guards);altered[index]['expected']=not guard['expected']
                variants.append(dict(label='flip-'+str(index),overrides=altered))
        packet['planned_runs']=variants[:max_runs]
        packet['coverage']='complete_single_flips' if len(variants)<=max_runs else 'partial'
        if not execute:return dict(packet,state='needs_execution')
        from experience_runner import run_python_test
        from experiment_snapshot import fingerprint
        source_snapshot=fingerprint(self.store.project)
        before={e['path']:digest(read_regular(scoped_path(Path(self.store.project),e['path']))) for e in data['evidence']}
        for variant in variants[:max_runs]:
            result=run_python_test(self.store.project,tests[0],context_overrides=variant['overrides'])
            packet['runs'].append(dict(**variant,check=tests[0],observation=result))
        after={e['path']:digest(read_regular(scoped_path(Path(self.store.project),e['path']))) for e in data['evidence']}
        if before!=after or source_snapshot!=fingerprint(self.store.project):return dict(packet,executed=True,state='workspace_changed')
        statuses=[r['observation']['status'] for r in packet['runs']]
        state=('unavailable' if 'unavailable' in statuses else
               'baseline_contradicted' if statuses[0]!='observed_support' else
               'scope_sensitive' if 'contradicted' in statuses[1:] else
               'non_discriminating' if len(statuses)>1 else 'baseline_only')
        packet.update(executed=True,state=state)
        packet['source_snapshot_sha256']=source_snapshot
        identity=uuid.uuid4().hex
        with self.store.database() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS experience_experiments(
                id TEXT PRIMARY KEY,project TEXT,name TEXT,revision INTEGER,report TEXT,created TEXT)''')
            with db:db.execute('INSERT INTO experience_experiments VALUES(?,?,?,?,?,?)',
                (identity,self.store.project,name,row['revision'],encoded(packet),now()))
        return dict(packet,id=identity,recorded=True)
