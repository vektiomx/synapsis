"""Exercise the authenticated local map workflow using fictional projects only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class BindingHTTPTest(unittest.TestCase):
    def test_authenticated_choice_enforces_origin_snapshot_and_candidate_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = base / 'config.json'
            config.write_text(json.dumps(dict(fuentes=[], proyectos=[])))
            script = r'''
import http.client,json,os,threading
from pathlib import Path
import project_identity as identity
import workspace_registry as registry
import servidor
base=Path(os.environ['CASE_ROOT'])
project=base/'project';project.mkdir()
folder=base/'legacy';folder.mkdir();(folder/'MEMORY.md').write_text('Original index')
(folder/'policy.md').write_text('---\nname: policy\nmetadata:\n  type: project\n---\nRetention is 90 days.')
registry.request_binding(str(project),folder)
request=registry.pending()[0]
before=servidor.calcular_huella()
server=servidor.Servidor(('127.0.0.1',0),servidor.Manejador)
threading.Thread(target=server.serve_forever,daemon=True).start()
port=server.server_address[1]
def call(method,path,body=None,authenticated=True,origin=None):
    connection=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
    headers={}
    if authenticated:headers[servidor.CABECERA_CLAVE]=servidor.clave()
    if origin:headers.update(Origin=origin,**{'X-Synopsis-Action':'bind-project'})
    if body is not None:headers['Content-Type']='application/json';body=json.dumps(body)
    connection.request(method,path,body=body,headers=headers)
    response=connection.getresponse();data=response.read();status=response.status;connection.close()
    return status,data
try:
    assert call('GET','/project-bindings',authenticated=False)[0]==403
    status,data=call('GET','/project-bindings');assert status==200 and len(json.loads(data)['requests'])==1
    body={'id':request['id'],'choice':'existing'}
    assert call('POST','/project-bindings',body)[0]==403
    assert call('POST','/project-bindings',body,origin='http://external.example')[0]==403
    origin='http://127.0.0.1:'+str(port)
    assert call('POST','/project-bindings',dict(body,path='/arbitrary'),origin=origin)[0]==409
    assert identity.owner(folder) is None
    status,data=call('POST','/project-bindings',body,origin=origin)
    assert status==200,(status,data)
    assert json.loads(data)['bound'] is True
    assert identity.owner(folder)==str(project)
    assert (folder/'MEMORY.md').read_text()=='Original index'
    assert registry.pending()==[]
    assert servidor.regenerar['en']>0
    assert servidor.calcular_huella()!=before
    servidor.armar_indice()
    assert any(n['ruta']==str(folder/'policy.md') for n in servidor.indice['actual'].notas)
    assert call('POST','/project-bindings',body,origin=origin)[0]==409
    assert call('GET','/experience-status',authenticated=False)[0] in (401,403)
    assert call('GET','/experience-status')[0]==200
    from auto_review import ReviewQueue
    from unittest.mock import patch
    queue=ReviewQueue(folder,project)
    turn=queue.cycle.begin('review','DO_NOT_EXPORT_PROMPT')['turn']
    queue.remember(turn,'review','DO_NOT_EXPORT_PROMPT','codex');queue.stop('review')
    with queue.database() as db,db:db.execute("UPDATE reviews SET state='failed',attempts=3")
    status,data=call('GET','/experience-status')
    assert status==200 and b'DO_NOT_EXPORT_PROMPT' not in data
    connection=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
    headers={servidor.CABECERA_CLAVE:servidor.clave(),'Origin':origin,'X-Synopsis-Action':'review-memory','Content-Type':'application/json'}
    with patch('auto_review.kick'):
        connection.request('POST','/experience-status',json.dumps({'project':identity.project_key(str(project))}),headers)
        response=connection.getresponse();assert response.status==200,response.read()
        response.read();connection.close()
    assert queue.status()[0]['state']=='pending' and queue.status()[0]['attempts']==0
    # New retry actions reject cross-origin requests and arbitrary filesystem paths.
    assert call('POST','/experience-status',{'project':'unknown'},origin='http://external.example')[0]==403
finally:
    server.shutdown();server.server_close()
'''
            result = subprocess.run([sys.executable, '-B', '-c', script],
                env=dict(os.environ, CEREBRO_CONFIG=str(config), SYNOPSIS_DATA=str(base / 'data'),
                         CLAUDE_PLUGIN_DATA=str(base / 'data'), PYTHONPATH=str(ROOT / 'engine'), CASE_ROOT=tmp),
                capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    @unittest.skipUnless(shutil.which('node'), 'Node needed for experience panel contract')
    def test_experience_panel_uses_text_and_retries_only_known_project_id(self):
        html=(ROOT/'engine/plantilla.html').read_text()
        script=html.rsplit('<script>',1)[1].split('</script>')[0]
        harness=r"""
import assert from 'node:assert/strict';
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.listeners={};this.style={};this.dataset={};}
 append(...items){this.children.push(...items);}
 appendChild(item){this.children.push(item);}
 replaceChildren(){this.children=[];}
 addEventListener(name,fn){this.listeners[name]=fn;}
 set innerHTML(value){throw new Error('Unsafe HTML');}
}
const panels=new Map();
globalThis.document={hidden:false,getElementById:id=>{if(!panels.has(id))panels.set(id,new Element('panel'));return panels.get(id);},createElement:tag=>new Element(tag)};
globalThis.location={protocol:'http:'};globalThis.setInterval=()=>{};
const calls=[];
globalThis.fetch=async(url,options)=>{
 calls.push({url,options});
 return {ok:true,json:async()=>options?.method==='POST'?{scheduled:true}:url==='/project-bindings'?{requests:[]}:{projects:[{id:'f'.repeat(64),project:'/repo/<script>',reviews:[{state:'failed',error:'provider_unavailable'}],experiences:[{name:'retention',revision:1,situation:'<img onerror=attack()>',action:'Keep pending work',limitations:'Configuration only',verification:{state:'stale'}}],witnesses:[{id:'a'.repeat(64),source_sha256:'b'.repeat(64),callable:{path:'<script>policy.py',symbol:'policy'},state:'needs_replay',records:2,sequence:0,evidence:[{path:'tests/<img>.py',line:4,case:'Policy.test_modes'}]}]}]}};
};
"""
        assertions=r"""
await new Promise(resolve=>setImmediate(resolve));
const panel=panels.get('experience-status');assert.equal(panel.hidden,false);
const content=panels.get('experience-status-content');
const allText=node=>(node.textContent || '')+node.children.map(allText).join(' ');
assert.ok(allText(content).includes('<img onerror=attack()>'));
assert.ok(allText(content).includes('Evidencia desactualizada'));
assert.ok(allText(content).includes('Testigos de comportamiento'));
assert.ok(allText(content).includes('<script>policy.py :: policy'));
assert.ok(allText(content).includes('Histórico · falta reproducir'));
assert.ok(allText(content).includes('tests/<img>.py:4'));
const button=content.children.find(c=>c.tag==='button');assert.ok(button);
await button.listeners.click();
assert.deepEqual(JSON.parse(calls.at(-1).options.body),{project:'f'.repeat(64)});
assert.equal(calls.at(-1).options.headers['X-Synopsis-Action'],'review-memory');
"""
        result=subprocess.run(['node','--input-type=module','-e',harness+script+assertions],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node needed for the map interaction contract')
    def test_panel_renders_paths_as_text_and_submits_the_stored_choice(self):
        html = (ROOT / 'engine/plantilla.html').read_text()
        script = html.rsplit('<script>', 1)[1].split('</script>')[0]
        harness = r'''
import assert from 'node:assert/strict';
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.listeners={};}
  append(...items){for(const item of items){item.parent=this;this.children.push(item);}}
  replaceChildren(){this.children=[];}
  querySelectorAll(tag){return this.children.flatMap(c=>[...(c.tag===tag?[c]:[]),...c.querySelectorAll(tag)]);}
  addEventListener(name,fn){this.listeners[name]=fn;}
  remove(){this.parent.children=this.parent.children.filter(c=>c!==this);}
}
const panel=new Element('aside');
globalThis.document={hidden:false,getElementById:()=>panel,createElement:tag=>new Element(tag)};
globalThis.location={protocol:'http:'};globalThis.setInterval=()=>{};
const calls=[];
globalThis.fetch=async(url,options)=>{
  calls.push({url,options});
  return {ok:true,json:async()=> options?.method==='POST'?{bound:true}:{requests:[{id:'a'.repeat(32),project:'/test/<script>',choices:[{folder:'/memory/<img>'}]}]}};
};
'''
        assertions = r'''
await new Promise(resolve=>setImmediate(resolve));
assert.equal(panel.hidden,false);
const buttons=panel.querySelectorAll('button');assert.equal(buttons.length,2);
assert.match(buttons[0].textContent,/<img>/);
await buttons[0].listeners.click();
const body=JSON.parse(calls.at(-1).options.body);
assert.deepEqual(body,{id:'a'.repeat(32),choice:'existing:0'});
assert.equal(calls.at(-1).options.headers['X-Synopsis-Action'],'bind-project');
assert.equal(panel.querySelectorAll('button').length,0);
'''
        result = subprocess.run(['node', '--input-type=module', '-e', harness + script + assertions],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
