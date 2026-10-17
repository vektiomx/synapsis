import json
import runpy
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent


class NativeClientsTest(unittest.TestCase):
    def test_cursor_does_not_emit_unsupported_prompt_context_or_scope_multiple_projects(self):
        import integration_runtime as runtime
        bridge = runpy.run_path(str(ROOT / 'cursor/bridge.py'))
        with patch.object(runtime, 'environment'), patch.object(runtime, 'record') as record, \
                patch.object(runtime, 'heartbeat'), patch.object(runtime, 'dispatch', return_value=dict(errors=[])) as dispatch:
            output = bridge['handle'](dict(hook_event_name='beforeSubmitPrompt', prompt='hello',
                                           workspace_roots=['/project'], conversation_id='one'))
            self.assertEqual(output, {'continue': True})
            record.assert_not_called()
            dispatch.assert_called_once()
            dispatch.reset_mock()
            output = bridge['handle'](dict(hook_event_name='sessionStart', workspace_roots=['/one', '/two']))
            self.assertEqual(output, {})
            dispatch.assert_not_called()

    def test_cursor_blocks_ask_instead_of_silently_allowing_it(self):
        import integration_runtime as runtime
        bridge = runpy.run_path(str(ROOT / 'cursor/bridge.py'))
        result = dict(contexts=[], warnings=[], errors=[], decision={
            'permissionDecision': 'ask', 'permissionDecisionReason': 'Review quota'})
        with patch.object(runtime, 'dispatch', return_value=result) as dispatch, patch.object(runtime, 'heartbeat'):
            output = bridge['handle'](dict(hook_event_name='preToolUse', tool_name='Task', cwd='/project'))
        self.assertEqual(output['permission'], 'deny')
        self.assertEqual(dispatch.call_args.args[0]['tool_name'], 'Task')

    @unittest.skipUnless(shutil.which('node'), 'Node is needed to exercise the native JS contract')
    def test_opencode_native_contract_preserves_prompts_and_isolates_sessions(self):
        script = '''
import assert from 'node:assert/strict';
import { createPlugin } from './opencode/plugin.mjs';
const events = [];
const mcp = {type:'local', command:['python','mcp_entry.py'], environment:{SYNOPSIS_ROOT:'/engine'}};
const transport = async row => {
  events.push(row);
  return {contexts:[row.hook_event_name + ':' + row.session_id], warnings:[], errors:[],
    decision:row.tool_name === 'Task' ? {permissionDecision:'ask', permissionDecisionReason:'Review'} : null};
};
const hooks = await createPlugin({mcp}, transport)({directory:'/project'});
const config = {mcp:{existing:{type:'local',command:['other']}}};
await hooks.config(config);
assert.equal(config.mcp.existing.command[0], 'other');
assert.deepEqual(config.mcp.synopsis,mcp);
await assert.rejects(hooks.config({mcp:{synopsis:{type:'remote',url:'https://other'}}}));
const input = {message:{},parts:[{type:'text',text:'original'}]};
const original = JSON.stringify(input);
await hooks['chat.message']({sessionID:'one',messageID:'user-one'},input);
assert.equal(JSON.stringify(input),original);
const system = {system:['existing']};
await hooks['experimental.chat.system.transform']({sessionID:'one'},system);
assert.match(system.system[1],/UserPromptSubmit:one/);
const separate = {system:[]};
await hooks['experimental.chat.system.transform']({sessionID:'two'},separate);
assert.equal(separate.system.length,0);
await hooks['chat.message']({sessionID:'one',messageID:'user-one'},input);
assert.equal(events.filter(row=>row.hook_event_name === 'SessionStart').length,1);
await assert.rejects(hooks['tool.execute.before']({sessionID:'one',tool:'task'}, {args:{}}), /Review/);
await hooks['tool.execute.after']({sessionID:'one',tool:'edit',args:{filePath:'/note'},callID:'call'}, {output:'ok'});
assert.equal(events.at(-1).tool_name,'Edit');
await hooks.event({event:{type:'message.updated',properties:{info:{sessionID:'one',role:'assistant',id:'assistant-one',parentID:'user-one'}}}});
await hooks.event({event:{type:'message.part.updated',properties:{part:{sessionID:'one',messageID:'assistant-one',id:'text-one',type:'text',text:'Final response'}}}});
await hooks.event({event:{type:'message.part.updated',properties:{part:{sessionID:'one',messageID:'assistant-one',id:'tool-one',type:'tool',text:'PRIVATE TOOL OUTPUT'}}}});
await hooks.event({event:{type:'session.idle',properties:{sessionID:'one'}}});
assert.equal(events.at(-1).hook_event_name,'Stop');
assert.equal(events.at(-1).message_id,'user-one');
assert.equal(events.at(-1).last_assistant_message,'Final response');
await hooks.event({event:{type:'session.deleted',properties:{info:{id:'one'}}}});
const after = {system:[]};
await hooks['experimental.chat.system.transform']({sessionID:'one'},after);
assert.equal(after.system.length,0);
'''
        result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT,
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cursor_merge_keeps_other_hooks_and_rejects_foreign_mcp(self):
        module = runpy.run_path(str(ROOT / 'cursor/install_cursor.py'))
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / '.cursor'
            folder.mkdir()
            hooks = folder / 'hooks.json'
            hooks.write_text(json.dumps({'version': 1, 'hooks': {'stop': [{'command': 'other'}]}}))
            planned = module['files'](tmp)
            self.assertEqual(json.loads(planned[hooks])['hooks']['stop'][0]['command'], 'other')
            (folder / 'mcp.json').write_text(json.dumps({'mcpServers': {'synopsis': {'command': 'foreign'}}}))
            with self.assertRaises(ValueError):
                module['files'](tmp)

    def test_opencode_checks_conflicts_without_rewriting_jsonc(self):
        import integration_setup
        module = runpy.run_path(str(ROOT / 'opencode/install_opencode.py'))
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / 'opencode.jsonc'
            original = '// existing\n{"mcp": {"synopsis": {"type":"remote", "url":"https://other//server",},},}\n'
            path.write_text(original)
            self.assertEqual(integration_setup.read_jsonc(path)['mcp']['synopsis']['url'], 'https://other//server')
            with patch.dict(module['main'].__globals__, {'config_dir': lambda: folder}), \
                    patch('sys.argv', ['install_opencode.py', '--dry-run']):
                with self.assertRaises(ValueError):
                    module['main']()
            self.assertEqual(path.read_text(), original)
            self.assertFalse((folder / 'plugins').exists())

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the JS to Python transport test')
    def test_generated_opencode_plugin_reaches_python_runtime(self):
        import os
        module = runpy.run_path(str(ROOT / 'opencode/install_opencode.py'))
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            config = folder / 'config.json'
            config.write_text(json.dumps({'usuario': 'Test', 'fuentes': [], 'proyectos': []}))
            env = dict(os.environ, HOME=tmp, SYNOPSIS_DATA=str(folder / 'state'),
                       SYNOPSIS_ROOT=str(ROOT / 'engine'), CEREBRO_CONFIG=str(config), PYTHONDONTWRITEBYTECODE='1')
            # Generate with the same environment the installer will capture.
            with patch.dict(os.environ, env):
                plugin = folder / 'synopsis.mjs'
                plugin.write_text(module['plugin_text']())
            script = '''
import assert from 'node:assert/strict';
const plugin = (await import(process.argv[1])).default;
const hooks = await plugin({directory:process.env.HOME});
const config = {mcp:{existing:{type:'local',command:['keep']}}};
await hooks.config(config);
assert.equal(config.mcp.synopsis.type,'local');
assert.equal(config.mcp.existing.command[0],'keep');
await hooks['chat.message']({sessionID:'integration-test'}, {message:{},parts:[{type:'text',text:'hello'}]});
'''
            result = subprocess.run(['node', '--input-type=module', '-e', script, plugin.as_uri()],
                                    env=env, text=True, capture_output=True, timeout=35)
            self.assertEqual(result.returncode, 0, result.stderr)
            marker = json.loads((folder / 'state/integrations/opencode.json').read_text())
            self.assertTrue(marker['ok'])
            self.assertEqual(marker['event'], 'UserPromptSubmit')
