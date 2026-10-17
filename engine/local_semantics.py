"""Private local semantic runtime. Models download only during explicit installation."""
import hashlib
import json
import os
import re
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.request

MODEL = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
FASTEMBED = '0.9.0'


def root():
    return Path(os.environ.get('SYNOPSIS_SEMANTIC_HOME', str(Path.home()/'.local/share/synopsis/semantic')))


def private_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError('unsafe_semantic_runtime')
    temp = path.with_name(path.name + '.' + secrets.token_hex(8))
    fd = os.open(temp, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def manifest():
    try:
        base = root()
        if base.is_symlink() or (base/'manifest.json').is_symlink():
            return None
        value = json.loads((base/'manifest.json').read_text())
        python = base/'venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        if (value.get('model') != MODEL or value.get('fastembed') != FASTEMBED or not python.is_file()
                or not isinstance(value.get('versions'),dict) or not isinstance(value.get('assets'),dict)
                or not value['assets'] or not re.fullmatch(r'[0-9a-f]{64}',str(value.get('identity','')))):
            return None
        return value
    except (ValueError, OSError):
        return None


def status():
    data = manifest()
    return dict(state='installed' if data else 'unavailable', model=MODEL,
                identity=data.get('identity') if data else None, local=True)


class LocalEmbeddings:
    def __init__(self, installed):
        self.identity = 'local:' + installed['identity']
        self.installed = installed

    def _request(self, state, texts=None, timeout=6):
        port = state.get('port')
        token = state.get('token')
        if type(port) is not int or not 1024 <= port <= 65535 or not isinstance(token,str) or len(token)<32:
            raise ValueError('invalid_semantic_endpoint')
        data = None if texts is None else json.dumps(dict(texts=texts)).encode('utf-8')
        req = urllib.request.Request('http://127.0.0.1:'+str(port)+('/health' if data is None else '/embed'),
            data=data, headers={'X-Synopsis-Embedding':token,'Content-Type':'application/json'})
        # Never honor a proxy for private text sent to the loopback worker.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=timeout) as response:
            raw = response.read(8_000_001)
        if len(raw)>8_000_000:
            raise ValueError('semantic_response_limit')
        result = json.loads(raw)
        if result.get('identity') != self.installed['identity']:
            raise ValueError('semantic_model_changed')
        return result

    def _state(self):
        path = root()/'worker.json'
        if path.is_symlink():
            raise ValueError('unsafe_semantic_endpoint')
        return json.loads(path.read_text())

    def ensure(self):
        try:
            state = self._state()
            self._request(state, timeout=.3)
            return state
        except (ValueError, OSError):
            pass
        from archivos import tomar_candado, soltar_candado
        base = root()
        lock = tomar_candado(base/'worker.lock', espera=1)
        if lock is None:
            raise ValueError('semantic_worker_starting')
        try:
            try:
                state = self._state()
                self._request(state, timeout=.3)
                return state
            except (ValueError, OSError):
                pass
            python = base/'venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
            env = {k:v for k,v in os.environ.items() if k in ('PATH','SYSTEMROOT','WINDIR','TMP','TEMP','LANG')}
            env.update(HOME=str(base),HF_HOME=str(base/'cache'),HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',
                DO_NOT_TRACK='1',ANONYMIZED_TELEMETRY='False',PYTHONDONTWRITEBYTECODE='1',SYNOPSIS_SEMANTIC_HOME=str(base))
            subprocess.Popen([str(python),'-I','-B',str(Path(__file__).with_name('semantic_worker.py')),str(base)],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                env=env,start_new_session=os.name!='nt',close_fds=True)
            deadline=time.monotonic()+6
            while time.monotonic()<deadline:
                try:
                    state=self._state();self._request(state,timeout=.3);return state
                except (ValueError,OSError):time.sleep(.05)
            raise ValueError('semantic_worker_unavailable')
        finally:
            soltar_candado(lock)

    def __call__(self, texts):
        from semantic_memory import normalize
        if not isinstance(texts,list) or not 1<=len(texts)<=64 or any(not isinstance(t,str) or not t.strip() or len(t)>6000 for t in texts):
            raise ValueError('invalid_local_embedding_input')
        result=self._request(self.ensure(),texts)
        vectors=result.get('vectors')
        if not isinstance(vectors,list) or len(vectors)!=len(texts):
            raise ValueError('invalid_local_embedding_count')
        return [normalize(v) for v in vectors]


def discover():
    data=manifest()
    return LocalEmbeddings(data) if data else None
