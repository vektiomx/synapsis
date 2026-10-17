"""Observe JSON function outputs in isolation; expected values never enter the child."""
import json
import math
from pathlib import Path
import re
import shutil
import sys
import tempfile

from controlled_run import process_text, RunError
from evidence_guard import read_regular, scoped_path, safe_text
from experiment_snapshot import files
from memory_store import digest


def json_value(value, depth=0):
    if depth>8:raise ValueError('behavior_value_depth')
    if value is None or type(value) in (bool,int,str):
        if isinstance(value,str) and len(value)>4000:raise ValueError('behavior_string_limit')
        if type(value) is int and abs(value)>2**53:raise ValueError('behavior_integer_limit')
        return value
    if type(value) is float and math.isfinite(value):return value
    if isinstance(value,list) and len(value)<=100:
        for item in value:json_value(item,depth+1)
        return value
    if isinstance(value,dict) and len(value)<=100 and all(isinstance(k,str) and len(k)<=200 for k in value):
        for item in value.values():json_value(item,depth+1)
        return value
    raise ValueError('invalid_behavior_json')


def calls_spec(descriptor, calls):
    if not isinstance(descriptor,dict) or set(descriptor)!={'path','symbol'}:raise ValueError('invalid_behavior_callable')
    path=descriptor['path'];symbol=descriptor['symbol']
    if not isinstance(path,str) or not path.endswith('.py') or path.startswith('tests/') or Path(path).is_absolute() or '..' in Path(path).parts:raise ValueError('invalid_behavior_module')
    if not isinstance(symbol,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,99}',symbol):raise ValueError('invalid_behavior_symbol')
    if not isinstance(calls,list) or not 1<=len(calls)<=24:raise ValueError('behavior_call_limit')
    for call in calls:
        if not isinstance(call,dict) or set(call)!={'args','kwargs'} or not isinstance(call['args'],list) or len(call['args'])>10 or not isinstance(call['kwargs'],dict):raise ValueError('invalid_behavior_call')
        json_value(call)
    if len(json.dumps(calls))>24000:raise ValueError('behavior_input_limit')


BOOTSTRAP=r'''
import resource,sys,json,importlib.util
resource.setrlimit(resource.RLIMIT_CPU,(10,10))
resource.setrlimit(resource.RLIMIT_AS,(536870912,536870912))
resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
resource.setrlimit(resource.RLIMIT_NPROC,(32,32))
resource.setrlimit(resource.RLIMIT_FSIZE,(1048576,1048576))
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
payload=json.load(sys.stdin)
sys.path.insert(0,'/workspace')
try:
 spec=importlib.util.spec_from_file_location('synopsis_behavior_target','/workspace/'+payload['callable']['path'])
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 target=getattr(module,payload['callable']['symbol'])
except Exception as error:
 print(json.dumps({'load_error':type(error).__name__}));sys.exit(0)
results=[]
for call in payload['calls']:
 try:results.append({'value':target(*call['args'],**call['kwargs'])})
 except Exception as error:results.append({'raises':type(error).__name__})
print(json.dumps({'results':results},allow_nan=False))
'''


def run_calls(project, descriptor, calls, function_patches=None):
    calls_spec(descriptor,calls)
    executable=shutil.which('bwrap')
    if sys.platform!='linux' or not executable:return dict(status='unavailable',reason='isolated_runner_unavailable')
    python=Path(sys.executable).resolve()
    if not str(python).startswith(('/usr/','/bin/')):return dict(status='unavailable',reason='system_python_required')
    root=Path(project).resolve();scoped_path(root,descriptor['path'])
    with tempfile.TemporaryDirectory(prefix='synopsis-behavior-') as temp:
        snapshot=Path(temp)/'project';snapshot.mkdir();manifest=[]
        try:
            for relative,text in files(root):
                target=snapshot/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text,encoding='utf-8')
                manifest.append(dict(path=relative,sha256=digest(text)))
            source_hash=digest(json.dumps(manifest,sort_keys=True))
            if function_patches:
                from research_workbench import apply_patches
                apply_patches(snapshot,function_patches)
        except (ValueError,OSError):return dict(status='unavailable',reason='behavior_snapshot_invalid')
        if not (snapshot/descriptor['path']).is_file():return dict(status='unavailable',reason='behavior_source_not_in_snapshot')
        cmd=[executable,'--unshare-all','--unshare-user','--disable-userns','--cap-drop','ALL','--die-with-parent','--new-session','--clearenv']
        for path in ('/usr','/bin','/lib','/lib64'):
            if Path(path).exists():cmd+=['--ro-bind',path,path]
        cmd+=['--ro-bind',str(snapshot),'/workspace','--size','16777216','--tmpfs','/tmp','--proc','/proc','--dev','/dev','--remount-ro','/dev',
            '--setenv','HOME','/tmp','--setenv','PATH','/usr/bin:/bin','--chdir','/workspace',str(python),'-I','-B','-c',BOOTSTRAP]
        payload=dict(callable=descriptor,calls=calls)
        def unique(items):
            result={}
            for key,value in items:
                if key in result:raise ValueError('duplicate_behavior_key')
                result[key]=value
            return result
        try:
            raw=process_text(cmd,json.dumps(payload,allow_nan=False),str(snapshot),timeout=15,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
            result=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite_behavior_output')))
            if not isinstance(result,dict) or set(result)!={'results'} or not isinstance(result['results'],list) or len(result['results'])!=len(calls):raise ValueError('invalid_behavior_output')
            for item in result['results']:
                if not isinstance(item,dict) or set(item) not in ({'value'},{'raises'}):raise ValueError('invalid_behavior_output')
                json_value(item)
            safe_text(json.dumps(result,ensure_ascii=False),120000)
            return dict(status='observed',results=result['results'],source_snapshot_sha256=source_hash,
                        source_sha256=digest(read_regular(snapshot/descriptor['path'])),
                        assurance='Only observed return values/exceptions for these inputs; not normative truth.')
        except (ValueError,OSError,RecursionError,RunError):return dict(status='unavailable',reason='behavior_execution_unavailable')
