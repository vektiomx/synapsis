"""Opt-in executable replay in a disposable, credential-free Linux namespace."""
import shutil
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from evidence_guard import read_regular
from memory_store import digest


def run_python_test(project,check,context_overrides=None,function_patches=None):
    executable=shutil.which('bwrap')
    if sys.platform!='linux' or not executable:return dict(status='unavailable',reason='isolated_runner_unavailable')
    root=Path(project).resolve()
    # Only a named existing unittest is replayed; no model-supplied shell or Python code.
    module=check['path'][:-3].replace('/','.')
    with tempfile.TemporaryDirectory(prefix='synopsis-experiment-') as temp:
        snapshot=Path(temp)/'project';snapshot.mkdir()
        from experiment_snapshot import files
        manifest=[]
        try:
            for relative,text in files(root):
                target=snapshot/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text,encoding='utf-8')
                manifest.append(dict(path=relative,sha256=digest(text)))
        except ValueError:
            return dict(status='unavailable',reason='experiment_snapshot_limit')
        source_snapshot=digest(json.dumps(manifest,sort_keys=True))
        if function_patches:
            from research_workbench import apply_patches
            apply_patches(snapshot,function_patches)
        if context_overrides:
            from experience_lab import apply_context
            apply_context(snapshot,context_overrides)
            manifest=[dict(path=str(p.relative_to(snapshot)),sha256=digest(read_regular(p))) for p in sorted(snapshot.rglob('*')) if p.is_file()]
        if function_patches and not context_overrides:
            manifest=[dict(path=str(p.relative_to(snapshot)),sha256=digest(read_regular(p))) for p in sorted(snapshot.rglob('*')) if p.is_file()]
        if not (snapshot/check['path']).is_file():return dict(status='unavailable',reason='test_not_in_safe_snapshot')
        cmd=[executable,'--unshare-all','--unshare-user','--disable-userns','--cap-drop','ALL','--die-with-parent','--new-session','--clearenv']
        for path in ('/usr','/bin','/lib','/lib64'):
            if Path(path).exists():cmd+=['--ro-bind',path,path]
        python=Path(sys.executable).resolve()
        if not str(python).startswith(('/usr/','/bin/')):return dict(status='unavailable',reason='system_python_required')
        cmd+=['--ro-bind',str(snapshot),'/workspace','--size','16777216','--tmpfs','/tmp','--proc','/proc','--dev','/dev','--remount-ro','/dev',
              '--setenv','HOME','/tmp','--setenv','PATH','/usr/bin:/bin','--setenv','SYNOPSIS_CONTROLLED_RUN','1',
              '--setenv','PYTHONDONTWRITEBYTECODE','1','--setenv','PYTHONPATH','/workspace',
              '--chdir','/workspace',str(python),'-B','-m','unittest',module+'.'+check['case']]
        # Bound CPU, descriptors and address space inside the namespace, without preexec_fn.
        runner='import resource,sys,unittest,json;resource.setrlimit(resource.RLIMIT_CPU,(15,15));resource.setrlimit(resource.RLIMIT_AS,(536870912,536870912));resource.setrlimit(resource.RLIMIT_NOFILE,(64,64));resource.setrlimit(resource.RLIMIT_NPROC,(32,32));resource.setrlimit(resource.RLIMIT_FSIZE,(1048576,1048576));resource.setrlimit(resource.RLIMIT_CORE,(0,0));sys.path.insert(0,"/workspace");suite=unittest.defaultTestLoader.loadTestsFromName('+repr(module+'.'+check['case'])+');result=unittest.TextTestRunner(stream=sys.stderr).run(suite);print(json.dumps(dict(tests=result.testsRun,passed=result.wasSuccessful(),errors=len(result.errors),failures=len(result.failures))))'
        cmd=cmd[:-5]+[str(python),'-I','-B','-c',runner]
        from controlled_run import process_text,RunError
        try:
            output=process_text(cmd,'',str(snapshot),timeout=20,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
            receipt=json.loads(output)
            if type(receipt.get('tests')) is not int or receipt['tests']<1 or receipt.get('errors'):
                return dict(status='unavailable',reason='test_setup_failed')
            return dict(status='observed_support' if receipt.get('passed') is True else 'contradicted',runner='python_unittest',tests=receipt['tests'],
                        snapshot_sha256=digest(json.dumps(manifest,sort_keys=True)),source_snapshot_sha256=source_snapshot,assurance='Only named test outcome in isolated snapshot; no causal claim.')
        except RunError as error:
            # Nonzero exit can be setup failure or assertion failure; do not mislabel it.
            return dict(status='unavailable',reason=error.code)
        except (OSError,ValueError):return dict(status='unavailable',reason='isolated_runner_failed')
