#!/usr/bin/env python3
"""Optional real embedding smoke evaluation. FastEmbed is a test-only dependency.

Run in a temporary venv with fastembed installed. Downloads the selected public
model to --cache. Does not add a runtime dependency to Synopsis.
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'engine'))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',default='BAAI/bge-small-en-v1.5')
    parser.add_argument('--cache',required=True)
    parser.add_argument('--output')
    args=parser.parse_args()
    from fastembed import TextEmbedding
    from semantic_memory import Embeddings,rank
    model=TextEmbedding(model_name=args.model,cache_dir=args.cache,threads=2)
    # Warm inference before the transport timeout is measured.
    list(model.embed(['Warm the embedding model.']))
    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass
        def do_POST(self):
            length=int(self.headers.get('Content-Length','0'))
            data=json.loads(self.rfile.read(length))
            texts=data['input'];calls.append(len(texts))
            vectors=list(model.embed(texts))
            payload=json.dumps(dict(data=[dict(index=i,embedding=v.tolist()) for i,v in enumerate(vectors)]))
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(payload.encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    docs=['The appliance is broken and needs to be repaired by a technician.',
          'Back up the database nightly and restore the latest snapshot after data loss.',
          'Visitors can enjoy fresh oranges and apples in the orchard.']
    cases=[('The device has malfunctioned. What now?',0),('How can lost records be recovered?',1),('Tell me about seasonal fruit.',2),('What is the mass of a neutrino?',None)]
    index=SimpleNamespace(notas=[dict(titulo='',secciones=[i]) for i in range(len(docs))],secciones=[(None,None,1,t) for t in docs])
    backend=Embeddings('compatible',args.model,f'http://127.0.0.1:{server.server_port}/v1',timeout=3)
    # This is a calibrated test threshold for this model/corpus, not a product default.
    os.environ['SYNOPSIS_SEMANTIC_THRESHOLD']='.60'
    rows=[]
    try:
        with tempfile.TemporaryDirectory(prefix='synopsis-vector-eval-') as tmp:
            snapshots={i:(text,{}) for i,text in enumerate(docs)}
            for query,expected in cases:
                scores,status=rank(index,snapshots,query,tmp,backend)
                order=sorted(scores,key=lambda n:-scores[n][0])
                passed=(bool(order) and order[0]==expected) if expected is not None else not order
                rows.append(dict(query=query,expected=expected,returned=order,scores={n:round(v[0],4) for n,v in scores.items()},status=status,passed=passed))
            report=dict(passed=all(row['passed'] for row in rows),model=args.model,dimensions=384,cases=rows,
                        transport='actual HTTP compatible embeddings, SQLite cache',embedding_batch_sizes=calls,
                        threshold=.60,limitation='Four synthetic English queries with one calibrated model; not multilingual or broad recall quality.')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
    serialized=json.dumps(report,ensure_ascii=False,indent=2)
    print(serialized)
    if args.output:Path(args.output).write_text(serialized+'\n')
    return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
