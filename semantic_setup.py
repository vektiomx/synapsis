"""One-step local semantic installation in a private venv, without remote inference."""
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'engine'))


def setup(dry_run=False):
    from local_semantics import root,manifest,FASTEMBED,MODEL,LocalEmbeddings
    if os.environ.get('SYNOPSIS_SEMANTIC_SETUP')=='off':
        return dict(state='disabled',ready=False)
    base=root()
    if dry_run:return dict(state='planned',model=MODEL,local=True,download_mb=220)
    if base.is_symlink():raise ValueError('unsafe_semantic_runtime')
    base.mkdir(mode=0o700,parents=True,exist_ok=True)
    from archivos import tomar_candado,soltar_candado
    lock=tomar_candado(base/'setup.lock',espera=3)
    if lock is None:return dict(state='busy',ready=False)
    try:
        existing=manifest()
        if existing:
            LocalEmbeddings(existing)(['Local semantic runtime readiness.'])
            return dict(state='ready',ready=True,model=MODEL)
        environment=base/'venv'
        python=environment/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        if not python.is_file():venv.EnvBuilder(with_pip=True).create(environment)
        env=dict(os.environ,HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1',ANONYMIZED_TELEMETRY='False',HF_HUB_DISABLE_PROGRESS_BARS='1',PYTHONDONTWRITEBYTECODE='1')
        result=subprocess.run([str(python),'-m','pip','install','--disable-pip-version-check','fastembed=='+FASTEMBED],env=env,capture_output=True,timeout=240)
        if result.returncode:raise RuntimeError('semantic_dependency_install_failed')
        result=subprocess.run([str(python),'-I','-B',str(ROOT/'engine/semantic_worker.py'),str(base),'setup'],env=env,capture_output=True,timeout=600)
        if result.returncode:raise RuntimeError('semantic_model_setup_failed')
        data=manifest()
        if not data:raise RuntimeError('semantic_manifest_missing')
        LocalEmbeddings(data)(['Local semantic runtime readiness.'])
        return dict(state='ready',ready=True,model=MODEL,identity=data['identity'])
    finally:soltar_candado(lock)
