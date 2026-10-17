"""Portable, source-cited behavior witnesses; the oracle stays outside executed code."""
import ast
import json
from pathlib import Path
import re

from behavior_runner import run_calls, calls_spec, json_value
from decision_rag import condition
from evidence_guard import read_regular, safe_text, scoped_path
from experience_engine import check_spec, encoded, now
from memory_store import digest, MemoryConflict
from experiment_snapshot import fingerprint
from research_workbench import function


def literal_assertions(project, descriptor, checks):
    """Extract literal assertEqual calls to the named imported function, not execute tests."""
    records=[];unsupported=0
    module=descriptor['path'][:-3].replace('/','.')
    for check in checks:
        check_spec(check)
        if check['kind']!='python_unittest':continue
        path=scoped_path(Path(project),check['path'])
        try:text=read_regular(path);tree=ast.parse(text)
        except (ValueError,OSError,SyntaxError):continue
        aliases=set();modules=set()
        for node in tree.body:
            if isinstance(node,ast.ImportFrom) and node.module==module:
                aliases.update(n.asname or n.name for n in node.names if n.name==descriptor['symbol'])
            if isinstance(node,ast.Import):modules.update(n.asname or n.name for n in node.names if n.name==module)
        parts=check['case'].split('.')
        if len(parts)!=2:continue
        methods=[method for cls in tree.body if isinstance(cls,ast.ClassDef) and cls.name==parts[0] for method in cls.body if isinstance(method,ast.FunctionDef) and method.name==parts[1]]
        for method in methods:
            # Only direct assertions: a call inside an unreachable branch, loop,
            # helper or exception handler is not evidence the test declared it.
            for statement in method.body:
                assertion=statement.value if isinstance(statement,ast.Expr) else None
                if not isinstance(assertion,ast.Call) or not isinstance(assertion.func,ast.Attribute) or not isinstance(assertion.func.value,ast.Name) or assertion.func.value.id!='self' or assertion.func.attr!='assertEqual' or len(assertion.args)<2:continue
                pair=assertion.args[:2]
                for target,expected in (pair,pair[::-1]):
                    if not isinstance(target,ast.Call):continue
                    matched=isinstance(target.func,ast.Name) and target.func.id in aliases or isinstance(target.func,ast.Attribute) and isinstance(target.func.value,ast.Name) and target.func.value.id in modules and target.func.attr==descriptor['symbol']
                    if not matched:continue
                    try:
                        if any(keyword.arg is None for keyword in target.keywords):raise ValueError()
                        call=dict(args=[ast.literal_eval(arg) for arg in target.args],kwargs={kw.arg:ast.literal_eval(kw.value) for kw in target.keywords})
                        value=ast.literal_eval(expected);calls_spec(descriptor,[call]);json_value(value)
                        safe_text(encoded(dict(call=call,value=value)),10000)
                        records.append(dict(call=call,expected=dict(value=value),source=dict(path=check['path'],line=assertion.lineno,sha256=digest(text),case=check['case'])))
                    except (ValueError,TypeError,RecursionError):unsupported+=1
                    break
    if len(records)>24:raise ValueError('behavior_assertion_limit')
    return records,unsupported


class BehaviorMemory:
    def __init__(self,store):self.store=store

    def _tables(self,db):
        db.executescript('''CREATE TABLE IF NOT EXISTS behavior_capsules(
            project TEXT,id TEXT,path TEXT,symbol TEXT,payload TEXT,sha256 TEXT,state TEXT,sequence INTEGER,created TEXT,
            PRIMARY KEY(project,id));
            CREATE INDEX IF NOT EXISTS behavior_callable ON behavior_capsules(project,path,symbol);
            CREATE TABLE IF NOT EXISTS behavior_events(project TEXT,id TEXT,sequence INTEGER,payload TEXT,
            PRIMARY KEY(project,id,sequence));''')

    def capture(self,descriptor,checks,origin,scopes=None,function_patches=None):
        calls_spec(descriptor,[dict(args=[],kwargs={})])
        if not isinstance(checks,list) or not 1<=len(checks)<=20:raise ValueError('behavior_check_limit')
        if scopes is not None and (not isinstance(scopes,list) or len(scopes)>10):raise ValueError('behavior_scope_limit')
        safe_text(origin,500)
        before=fingerprint(self.store.project)
        records,unsupported=literal_assertions(self.store.project,descriptor,checks)
        if not records:return dict(state='unavailable',reason='no_literal_assertions',captured=False)
        calls=[r['call'] for r in records]
        observed=run_calls(self.store.project,descriptor,calls,function_patches=function_patches)
        if observed['status']!='observed':return dict(state='unavailable',captured=False,reason=observed.get('reason'))
        if observed['results']!=[r['expected'] for r in records]:
            return dict(state='contradicted',captured=False,reason='literal_assertions_not_observed')
        if observed['source_snapshot_sha256']!=before or fingerprint(self.store.project)!=before:
            return dict(state='unavailable',captured=False,reason='behavior_workspace_changed')
        for record,actual in zip(records,observed['results']):
            record['declared_expected']=record['expected'];record['expected']=actual
        source=read_regular(scoped_path(Path(self.store.project),descriptor['path']))
        signature=ast.dump(function(source,descriptor['symbol']).args)
        bindings=[]
        for ref in scopes or []:
            row=self.store.latest(ref['name'])
            if row['revision']!=ref['revision'] or row['sha256']!=ref['experience_sha256']:raise MemoryConflict('behavior_scope_changed')
            data=row['experience'];guards=data['when']['conditions']+data.get('decision',{}).get('requires',[])
            if any(condition(self.store.project,g)['status']!='observed_support' for g in guards):raise MemoryConflict('behavior_scope_unobserved')
            guard_paths={g['path'] for g in guards}
            policy=[e for e in data['evidence'] if e['path']!=descriptor['path'] and e['path'] not in guard_paths and not e['path'].endswith('.py')]
            bindings.append(dict(name=row['name'],revision=row['revision'],sha256=row['sha256'],guards=guards,policy=policy))
        payload=dict(protocol='synopsis.behavior-witness.v1',project=self.store.project,callable=descriptor,signature=signature,
                     records=records,scopes=bindings,origin=origin,source_sha256=observed['source_sha256'],source_snapshot_sha256=observed['source_snapshot_sha256'],
                     unsupported_assertions=unsupported,notice='Historical declared test behavior observed for these inputs. Not a universal rule or causal proof.')
        # Deduplicate the same witness even if another research run observed it.
        identity=digest(encoded({k:v for k,v in payload.items() if k not in ('origin','source_snapshot_sha256')}));raw=encoded(payload)
        with self.store.database() as db:
            self._tables(db)
            with db:
                old=db.execute('SELECT payload,sha256,state FROM behavior_capsules WHERE project=? AND id=?',(self.store.project,identity)).fetchone()
                if old and digest(old[0])!=old[1]:raise ValueError('behavior_integrity_failure')
                if not old:db.execute('INSERT INTO behavior_capsules VALUES(?,?,?,?,?,?,?,?,?)',(self.store.project,identity,descriptor['path'],descriptor['symbol'],raw,digest(raw),'active',0,now()))
        return dict(id=identity,captured=True,replayed=bool(old),records=len(records),state='retired' if old and old[2]=='retired' else 'observed_witness')

    def count(self,descriptor=None):
        if not self.store.path.exists():return 0
        with self.store.database() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='behavior_capsules'").fetchone():return 0
            sql='SELECT COUNT(*) FROM behavior_capsules WHERE project=?';args=[self.store.project]
            if descriptor:sql+=' AND path=? AND symbol=?';args.extend([descriptor['path'],descriptor['symbol']])
            return db.execute(sql,args).fetchone()[0]

    def rows(self,descriptor=None,identity=None,path=None):
        if not self.store.path.exists():return []
        with self.store.database() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='behavior_capsules'").fetchone():return []
            sql='SELECT id,payload,sha256,state,sequence,created FROM behavior_capsules WHERE project=?';args=[self.store.project]
            if descriptor:
                sql+=' AND path=? AND symbol=?';args.extend([descriptor['path'],descriptor['symbol']])
            elif path:
                sql+=' AND path=?';args.append(path)
            if identity:
                sql+=' AND id=?';args.append(identity)
            rows=db.execute(sql+' ORDER BY rowid DESC LIMIT 100',args).fetchall()
        result=[]
        for identity,raw,sha,state,sequence,created in rows:
            if digest(raw)!=sha:raise ValueError('behavior_integrity_failure')
            result.append(dict(id=identity,data=json.loads(raw),state=state,sequence=sequence,created=created))
        return result

    def assess(self,row):
        data=row['data'];descriptor=data['callable']
        if row['state']!='active':return 'retired'
        try:
            source=read_regular(scoped_path(Path(self.store.project),descriptor['path']))
            if ast.dump(function(source,descriptor['symbol']).args)!=data['signature']:return 'incompatible_interface'
            active={r['name']:r for r in self.store.current()}
            for scope in data['scopes']:
                current=active.get(scope['name'])
                if not current or current['revision']!=scope['revision'] or current['sha256']!=scope['sha256']:return 'scope_revised_or_retired'
                if any(condition(self.store.project,g)['status']!='observed_support' for g in scope['guards']):return 'scope_unobserved'
                if any(digest(read_regular(scoped_path(Path(self.store.project),e['path'])))!=e['sha256'] for e in scope['policy']):return 'policy_changed'
            # A new explicit test for the same invocation outranks the old witness.
            checks_by_key={encoded(dict(kind='python_unittest',path=r['source']['path'],case=r['source']['case'])):dict(kind='python_unittest',path=r['source']['path'],case=r['source']['case']) for r in data['records']}
            from research_workbench import discover
            for check in discover(self.store.project,descriptor['path']+' '+descriptor['symbol'])['tests']:
                checks_by_key[encoded(check)]=check
            checks=list(checks_by_key.values())
            current,_=literal_assertions(self.store.project,descriptor,checks)
            current_values={encoded(r['call']):r['expected'] for r in current}
            if any(encoded(r['call']) in current_values and current_values[encoded(r['call'])]!=r.get('declared_expected',r['expected']) for r in data['records']):return 'superseded_by_current_assertion'
            return 'needs_replay'
        except (ValueError,OSError,SyntaxError):return 'unavailable'

    def relevant(self,descriptor,include_cases=True):
        result=[]
        for row in self.rows(descriptor):
            state=self.assess(row)
            item=dict(id=row['id'],callable=row['data']['callable'],state=state,sequence=row['sequence'],created=row['created'],
                      source_sha256=row['data']['source_sha256'],origin=row['data']['origin'],record_count=len(row['data']['records']))
            if include_cases and state=='needs_replay':item['records']=row['data']['records']
            result.append(item)
        return result

    def verify(self,identity,function_patches=None):
        if not isinstance(identity,str) or not re.fullmatch('[0-9a-f]{64}',identity):raise ValueError('invalid_behavior_identity')
        row=next(iter(self.rows(identity=identity)),None)
        if row is None:raise ValueError('unknown_behavior_witness')
        state=self.assess(row)
        if state!='needs_replay':return dict(id=identity,state=state,executed=False)
        data=row['data'];observed=run_calls(self.store.project,data['callable'],[r['call'] for r in data['records']],function_patches=function_patches)
        if observed['status']!='observed':return dict(id=identity,state='unavailable',executed=False,reason=observed.get('reason'))
        # The child never receives these expectations and never decides pass/fail.
        matches=[actual==record['expected'] and encoded(actual)==encoded(record['expected']) for actual,record in zip(observed['results'],data['records'])]
        return dict(id=identity,state='observed_support' if all(matches) else 'contradicted',executed=True,matches=matches,
                    observed=observed['results'],source_snapshot_sha256=observed['source_snapshot_sha256'],
                    assurance='Only historical declared inputs compared by the controller; not general correctness.')

    def retire(self,identity,reason,source,expected_sequence):
        if not isinstance(identity,str) or not re.fullmatch('[0-9a-f]{64}',identity):raise ValueError('invalid_behavior_identity')
        safe_text(reason,1000);safe_text(source,500)
        if type(expected_sequence) is not int or expected_sequence<0:raise ValueError('invalid_behavior_revision')
        with self.store.database() as db:
            self._tables(db);db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT sequence,state FROM behavior_capsules WHERE project=? AND id=?',(self.store.project,identity)).fetchone()
            if not old:raise ValueError('unknown_behavior_witness')
            if old[0]!=expected_sequence:raise MemoryConflict('behavior_revision_conflict')
            event=dict(reason=reason,source=source,state='retired',created=now())
            db.execute('UPDATE behavior_capsules SET state=?,sequence=? WHERE project=? AND id=?',('retired',expected_sequence+1,self.store.project,identity))
            db.execute('INSERT INTO behavior_events VALUES(?,?,?,?)',(self.store.project,identity,expected_sequence+1,encoded(event)));db.commit()
        return dict(id=identity,state='retired',sequence=expected_sequence+1)
