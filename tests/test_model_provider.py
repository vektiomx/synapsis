import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'engine'))
from model_provider import ModelTransport, ProviderError, choose, parse_object, request_json


class ProviderTest(unittest.TestCase):
    def test_auto_prefers_local_generation_and_never_selects_embedding_model(self):
        with patch.dict(os.environ, {}, clear=True), patch('model_provider.ollama_models', return_value=['nomic-embed-text', 'local-brain']):
            self.assertEqual(choose(), ('ollama', 'local-brain'))

    def test_compatible_and_openai_use_distinct_protocols(self):
        for provider in ('openai', 'compatible', 'ollama'):
            with self.subTest(provider=provider), patch('model_provider.request_json') as call:
                answer = dict(answer='hola', memory=dict(outcome='no_change', reason='No hay dato durable', actions=[]))
                raw = json.dumps(answer)
                call.return_value = dict(output=[dict(content=[dict(type='output_text', text=raw)])],
                                         choices=[dict(message=dict(content=raw))], message=dict(content=raw))
                self.assertEqual(ModelTransport(provider, 'test-model')({'project':'/tmp', 'prompt':'hello'}), answer)
                url, path, body = call.call_args.args[:3]
                self.assertEqual(path, {'openai':'/responses', 'compatible':'/chat/completions', 'ollama':'/api/chat'}[provider])
                if provider == 'openai':
                    self.assertFalse(body['store'])
                else:
                    self.assertFalse(body['stream'])

    def test_plaintext_remote_and_embedded_credentials_are_rejected(self):
        for base in ('http://example.com', 'https://user:secret@example.com', 'file:///tmp', 'https://example.com?q=secret'):
            with self.subTest(base=base), self.assertRaises(ProviderError):
                request_json(base, '/test')

    def test_only_valid_json_objects_are_accepted(self):
        self.assertEqual(parse_object('```json\n{"answer":"ok"}\n```'), {'answer':'ok'})
        for raw in ('oops {"a":1}', '[]', None):
            with self.assertRaises(ProviderError):
                parse_object(raw)

    def test_native_transports_parse_events_and_deny_tools_for_opencode(self):
        from controlled_run import process_text
        for provider in ('opencode', 'codex', 'claude'):
            answer = dict(answer='ok', memory=dict(outcome='no_change', reason='Nothing new', actions=[]))
            text = json.dumps(answer)
            raw = {'codex':json.dumps(dict(type='item.completed', item=dict(type='agent_message', text=text))),
                   'opencode':json.dumps(dict(type='text', part=dict(text=text))),
                   'claude':json.dumps(dict(result=text, is_error=False))}[provider]
            with patch('controlled_run.process_text', return_value=raw) as call:
                self.assertEqual(ModelTransport(provider)({'project':'/tmp'}), answer)
                command, prompt, cwd, timeout, env = call.call_args.args
                self.assertEqual(env['SYNOPSIS_CONTROLLED_RUN'], '1')
                if provider == 'opencode':
                    self.assertEqual(json.loads(env['OPENCODE_CONFIG_CONTENT'])['permission'], 'deny')
                if provider == 'codex':
                    self.assertIn('read-only', command)
                    self.assertIn('--ignore-user-config',command)
                    self.assertIn('shell_tool',command)
                    self.assertIn('multi_agent',command)
                if provider == 'claude':
                    self.assertEqual(command[command.index('--tools')+1], '')

    def test_provider_errors_do_not_expose_response_or_api_key(self):
        import urllib.error
        with patch('urllib.request.OpenerDirector.open', side_effect=urllib.error.URLError('sk-secret-real-key')):
            with self.assertRaisesRegex(ProviderError, '^provider_request_failed$'):
                request_json('https://example.com', '/test', key='secret')

    def test_one_structural_repair_is_bounded_and_validated_before_any_write(self):
        invalid=dict(answer='ok',memory=dict(outcome='saved',actions=[dict(filename='note',name='Human Title',description='test',kind='project',content='fact',index_line='- [Note](note.md)',source='user:test')]))
        valid=json.loads(json.dumps(invalid))
        valid['memory']['actions'][0]['name']='note'
        transport=ModelTransport('ollama','test')
        with patch.object(ModelTransport,'complete',side_effect=[invalid,valid]) as call:
            self.assertEqual(transport({'project':'/tmp'}),valid)
            self.assertEqual(call.call_count,2)
        with patch.object(ModelTransport,'complete',return_value=invalid) as call:
            with self.assertRaisesRegex(ProviderError,'model_contract_invalid'):
                transport({'project':'/tmp'})
            self.assertEqual(call.call_count,2)

    def test_non_json_reply_can_be_repaired_but_provider_denials_cannot(self):
        valid=dict(answer='ok',memory=dict(outcome='no_change',reason='Nothing new',actions=[]))
        transport=ModelTransport('ollama','test')
        with patch.object(ModelTransport,'complete',side_effect=[ProviderError('model_invalid_json'),valid]) as call:
            self.assertEqual(transport({'project':'/tmp'}),valid)
            self.assertEqual(call.call_count,2)
        with patch.object(ModelTransport,'complete',side_effect=ProviderError('provider_request_failed')) as call:
            with self.assertRaises(ProviderError):
                transport({'project':'/tmp'})
            self.assertEqual(call.call_count,1)
