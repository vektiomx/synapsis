"""Real pinned SDK acquisition/retrieval adapters; run with the evaluation venv.

Native authentication is reused with tools disabled. No mock retrieval or API key
is substituted for framework behavior. ShadowFrog profile uses official skill
format plus its viewer; it excludes Dream, initialization/commits and publication.
"""
import argparse
import asyncio
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'engine'))
from model_provider import ModelTransport

MODEL='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
CACHE='/home/harim/.local/share/synopsis/semantic/cache'
SHADOW=Path('/tmp/synopsis-shadowfrog-audit')
os.environ.update(MEM0_TELEMETRY='False',GRAPHITI_TELEMETRY_ENABLED='false',FASTEMBED_CACHE_PATH=CACHE,HF_HOME=CACHE,
                  SEMAPHORE_LIMIT='1',OPENAI_API_KEY='unused-native-adapter',OPENAI_BASE_URL='http://127.0.0.1:1')


def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,default=str)


class Capture:
    def __init__(self,base,profile):
        self.base=base;self.profile=profile;self.transport=ModelTransport('codex','gpt-6.1-sol',timeout=120)
        self.trace=base/('capture-'+profile+'.jsonl');self.total=sum(1 for _ in self.trace.open()) if self.trace.exists() else 0
        self.calls=0;self.chars=0
    def call(self,system,request):
        if self.total>=40:raise ValueError('predefined_sdk_capture_call_cap')
        self.total+=1;self.calls+=1;self.chars+=len(system)+len(encoded(request));start=time.monotonic();entry=dict(call=self.total,system=system,request=request)
        try:
            result=self.transport.complete(system,request,str(self.base));entry['response']=result;return result
        except Exception as error:entry['error']=repr(error);raise
        finally:
            entry['seconds']=time.monotonic()-start
            with self.trace.open('a') as stream:stream.write(encoded(entry)+'\n')
            print(self.profile,'capture call',self.total,round(entry['seconds'],2),entry.get('error','ok'),flush=True)


def mem0(task,base,profile,capture):
    from mem0 import Memory
    class NativeLLM:
        def generate_response(self,messages,response_format=None,tools=None,**kwargs):
            if tools:raise ValueError('unsupported_native_tool_api')
            return encoded(capture.call('Follow the supplied framework messages. Return the requested JSON object.',dict(messages=messages,response_format=response_format)))
    directory=base/'sdk'/profile/task['id'];directory.mkdir(parents=True,exist_ok=True)
    m=Memory.from_config(dict(llm=dict(provider='openai',config=dict(model='native-codex',api_key='unused',openai_base_url='http://127.0.0.1:1')),
        embedder=dict(provider='fastembed',config=dict(model=MODEL,embedding_dims=384)),
        vector_store=dict(provider='qdrant',config=dict(collection_name='memories',path=str(directory/'vectors'),embedding_model_dims=384)),history_db_path=str(directory/'history.sqlite')))
    m.llm=NativeLLM();captures=[];start=time.monotonic()
    for artifact in task['artifacts']:
        captures.append(m.add([dict(role='user',content=encoded(artifact))],user_id=task['id'],metadata=dict(source_id=artifact['source_id'],path=artifact['callable']['path'],symbol=artifact['callable']['symbol']),infer=profile!='mem0-raw'))
    seconds=time.monotonic()-start;start=time.monotonic()
    memory=m.search('policy.py policy function historical contract compatibility observed behavior',filters=dict(user_id=task['id']),top_k=8,explain=True)
    retrieval=time.monotonic()-start;raw=encoded(memory)
    ids=[a['source_id'] for a in task['artifacts'] if a['source_id'] in raw]
    return dict(memory=memory,source_ids=ids,captures=captures,metrics=dict(acquisition_seconds=seconds,retrieval_seconds=retrieval))


async def graphiti(task,base,profile,capture):
    from fastembed import TextEmbedding
    from graphiti_core import Graphiti
    from graphiti_core.llm_client.client import LLMClient
    from graphiti_core.llm_client.config import LLMConfig
    from graphiti_core.embedder.client import EmbedderClient,EmbedderConfig
    from graphiti_core.driver.falkordb_driver import FalkorDriver
    from graphiti_core.nodes import EpisodeType
    from graphiti_core.search.search_config_recipes import COMBINED_HYBRID_SEARCH_RRF
    from redislite.async_falkordb_client import AsyncFalkorDB
    encoder=TextEmbedding(model_name=MODEL,cache_dir=CACHE,threads=2,local_files_only=True)
    class NativeLLM(LLMClient):
        async def _generate_response(self,messages,response_model=None,*args,**kwargs):
            return capture.call('Follow the supplied framework messages. Return the requested JSON object.',dict(messages=[dict(role=m.role,content=m.content) for m in messages]))
    class NativeEmbedder(EmbedderClient):
        config=EmbedderConfig(embedding_dim=384)
        async def create(self,input_data):return list(encoder.embed([' '.join(input_data) if isinstance(input_data,list) else input_data]))[0].tolist()
        async def create_batch(self,values):return [value.tolist() for value in encoder.embed(values)]
    directory=base/'sdk'/profile/task['id'];directory.mkdir(parents=True,exist_ok=True)
    embedded=AsyncFalkorDB(dbfilename=str(directory/'memory.db'));group='task_'+str(abs(hash(task['id'])))
    g=Graphiti(graph_driver=FalkorDriver(falkor_db=embedded,database=group),llm_client=NativeLLM(LLMConfig(model='gpt-6.1-sol')),embedder=NativeEmbedder())
    try:
        await g.build_indices_and_constraints();start=time.monotonic();uuids={};captures=[]
        for artifact in task['artifacts']:
            result=await g.add_episode(name=artifact['source_id'],episode_body=encoded(artifact),source_description='Historical developer source and literal test observations with lifecycle and callable scope',reference_time=datetime(2026,10,16,tzinfo=timezone.utc),source=EpisodeType.json,group_id=group)
            uuids[result.episode.uuid]=artifact['source_id'];captures.append(dict(episode=result.episode.uuid,nodes=len(result.nodes),edges=len(result.edges)))
        seconds=time.monotonic()-start;start=time.monotonic()
        config=COMBINED_HYBRID_SEARCH_RRF.model_copy(deep=True);config.limit=8
        result=await g.search_('policy.py policy function historical contract compatibility observed behavior',config=config,group_ids=[group])
        retrieval=time.monotonic()-start;memory=result.model_dump(mode='json');raw=encoded(memory)
        ids=[a['source_id'] for a in task['artifacts'] if a['source_id'] in raw]
        # Episode provenance on retrieved graph objects also authorizes a fetch.
        ids.extend(source for uuid,source in uuids.items() if uuid in raw and source not in ids)
        return dict(memory=memory,source_ids=ids,captures=captures,metrics=dict(acquisition_seconds=seconds,retrieval_seconds=retrieval))
    finally:await g.close()


def shadow(task,base,profile,capture):
    directory=base/'sdk'/profile/task['id'];shadow_dir=directory/'.shadow';shadow_dir.mkdir(parents=True,exist_ok=True)
    skill=(SHADOW/'skills/shadow-frog-update/SKILL.md').read_text();start=time.monotonic()
    result=capture.call('Apply the supplied official memory skill to the supplied historical developer artifacts. Return JSON {"markdown":string} with the per-file shadow for policy.py, headed ## `policy`. Preserve source_id references and scope/lifecycle facts. No tools, no git commands.',dict(skill=skill,artifacts=task['artifacts']))
    markdown=result.get('markdown')
    if not isinstance(markdown,str):raise ValueError('invalid_shadow_markdown')
    (shadow_dir/'policy.py.md').write_text(markdown);seconds=time.monotonic()-start;start=time.monotonic()
    proc=subprocess.run([sys.executable,str(SHADOW/'skills/shadow-frog-viewer/shadow-viewer.py'),'--shadow-dir',str(shadow_dir),'--search','policy'],text=True,capture_output=True,timeout=15)
    if proc.returncode:raise ValueError('official_shadow_viewer_failed:'+proc.stderr[:300])
    # The official workflow explicitly reads a file's shadow before editing.
    # --top is bug/security-only and would incorrectly omit ordinary policy.
    memory=dict(viewer=proc.stdout,file=markdown);retrieval=time.monotonic()-start
    ids=[a['source_id'] for a in task['artifacts'] if a['source_id'] in encoded(memory)]
    return dict(memory=memory,source_ids=ids,metrics=dict(acquisition_seconds=seconds,retrieval_seconds=retrieval),profile_limit='Official skill native capture plus official viewer; no init, hook or Dream execution. No commits.')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base',type=Path,required=True);parser.add_argument('--profile',choices=['mem0-inferred','mem0-raw','graphiti','shadowfrog-file-symbol'],required=True);parser.add_argument('--split',choices=['development','reserved'],default='development');args=parser.parse_args()
    output=args.base/('retrieval-'+args.profile+'.json');results=json.loads(output.read_text()) if output.exists() else {};capture=Capture(args.base,args.profile)
    tasks=json.loads((args.base/'inputs.json').read_text())
    for task in tasks:
        if task['split']!=args.split or task['id'] in results:continue
        before_calls=capture.calls;before_chars=capture.chars;start=time.monotonic()
        try:
            if args.profile.startswith('mem0'):row=mem0(task,args.base,args.profile,capture)
            elif args.profile=='graphiti':row=asyncio.run(graphiti(task,args.base,args.profile,capture))
            else:row=shadow(task,args.base,args.profile,capture)
        except Exception as error:row=dict(error=repr(error),traceback=traceback.format_exc())
        row.setdefault('metrics',{}).update(acquisition_llm_calls=capture.calls-before_calls,request_characters=capture.chars-before_chars,wall_seconds=time.monotonic()-start)
        results[task['id']]=row;output.write_text(json.dumps(results,indent=2,ensure_ascii=False,default=str)+'\n')
        print(args.profile,task['id'],row.get('source_ids',[]),row.get('error','ok'),flush=True)


if __name__=='__main__':main()
