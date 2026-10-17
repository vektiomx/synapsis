"""Authenticated loopback-only ONNX worker. It never receives provider credentials."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0,str(Path(__file__).resolve().parent))
from local_semantics import MODEL, private_json


def load(base, offline=True):
    from fastembed import TextEmbedding
    import onnxruntime as ort
    ort.disable_telemetry_events()
    return TextEmbedding(model_name=MODEL, cache_dir=str(base/'cache'),threads=2,
                         local_files_only=offline, lazy_load=False)


def setup(base):
    model=load(base,offline=False)
    list(model.embed(['A small local semantic readiness check.']))
    folder=Path(model.model._model_dir)
    assets={str(p.relative_to(base)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob('*')) if p.is_file()}
    from importlib.metadata import version
    versions={name:version(name) for name in ('fastembed','onnxruntime','tokenizers','numpy')}
    identity=hashlib.sha256(json.dumps(dict(assets=assets,versions=versions),sort_keys=True).encode()).hexdigest()
    from local_semantics import FASTEMBED
    private_json(base/'manifest.json',dict(model=MODEL,fastembed=FASTEMBED,identity=identity,assets=assets,versions=versions))
    print(json.dumps(dict(ready=True,identity=identity,model=MODEL,files=len(assets))))


def serve(base):
    installed=json.loads((base/'manifest.json').read_text())
    # Validate the actual local assets once at start; never download in a hook.
    for name,sha in installed['assets'].items():
        path=(base/name).resolve()
        if not path.is_relative_to(base.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
            raise ValueError('semantic_asset_changed')
    model=load(base)
    token=secrets.token_urlsafe(32)
    lock=threading.Lock()
    last=[time.monotonic()]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,data,code=200):
            raw=json.dumps(data,allow_nan=False).encode()
            self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def authorized(self):
            host=self.headers.get('Host','')
            return host in ('127.0.0.1:'+str(self.server.server_address[1]),'localhost:'+str(self.server.server_address[1])) and hmac.compare_digest(self.headers.get('X-Synopsis-Embedding',''),token)
        def do_GET(self):
            if not self.authorized():self.send(dict(error='unauthorized'),403);return
            if self.path!='/health':self.send(dict(error='not_found'),404);return
            last[0]=time.monotonic();self.send(dict(identity=installed['identity'],model=MODEL))
        def do_POST(self):
            if not self.authorized():self.send(dict(error='unauthorized'),403);return
            try:
                if self.path!='/embed' or self.headers.get('Content-Type')!='application/json':raise ValueError()
                size=int(self.headers.get('Content-Length','0'))
                if not 1<=size<=400000:raise ValueError()
                self.connection.settimeout(6)
                value=json.loads(self.rfile.read(size))
                if set(value)!={'texts'}:raise ValueError()
                texts=value['texts']
                if not isinstance(texts,list) or not 1<=len(texts)<=64 or any(not isinstance(t,str) or not t.strip() or len(t)>6000 for t in texts):raise ValueError()
                if not lock.acquire(timeout=2):self.send(dict(error='busy'),503);return
                try:vectors=[v.tolist() for v in model.embed(texts,batch_size=8)]
                finally:lock.release()
                last[0]=time.monotonic();self.send(dict(identity=installed['identity'],vectors=vectors))
            except (ValueError,TypeError,OSError,KeyError):self.send(dict(error='invalid_embedding_request'),400)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    server.daemon_threads=True
    private_json(base/'worker.json',dict(port=server.server_address[1],token=token,pid=os.getpid(),identity=installed['identity']))
    server.timeout=1
    try:
        while time.monotonic()-last[0]<1800:server.handle_request()
    finally:
        server.server_close()
        state=base/'worker.json'
        try:
            if json.loads(state.read_text()).get('token')==token:state.unlink()
        except (ValueError,OSError):pass


if __name__=='__main__':
    base=Path(sys.argv[1]).resolve()
    if len(sys.argv)>2 and sys.argv[2]=='setup':setup(base)
    else:serve(base)
