"""Adversarial guard regressions: provenance is verified mechanically, not by a judge."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'engine'))
from evidence_guard import EvidenceLedger,EvidenceError,calculate,read_regular


class EvidenceGuardTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'project';self.root.mkdir()
        self.memory=Path(self.temp.name)/'memory';self.memory.mkdir()
        self.ledger=EvidenceLedger(self.root,self.memory)
        self.path=self.root/'policy.txt'
        self.path.write_text('La retención NO es 300 segundos.\n\nEl valor vigente es 389 segundos.\n')

    def source(self):
        return self.ledger.tool(dict(tool='read_file',path='policy.txt'))

    def action(self,identifier,quote):
        return dict(filename='policy',name='model-title',description='La retención es 900 segundos',kind='project',
                    content='La retención es 900 segundos',index_line='invented',source='user:forged',state='confirmed',
                    cues=['900 segundos'],support=[dict(source=identifier,quote=quote)])

    def test_fabricated_draft_never_reaches_the_response(self):
        identifier=self.source()
        response=dict(answer='La retención es 900 segundos',grounding=dict(sources=[identifier],abstain=False))
        selected=self.ledger.selection(response)
        result=self.ledger.render(selected)
        self.assertNotIn('900',result['answer'])
        self.assertIn('NO es 300',result['answer'])
        self.assertIn('389',result['answer'])
        self.assertEqual(result['verification']['scope'],'source_fidelity_only')

    def test_missing_or_unknown_citations_fail_closed(self):
        for response in ({},dict(grounding=dict(sources=['fake'],abstain=False)),dict(grounding=dict(sources=['x'],abstain=True))):
            with self.assertRaises(EvidenceError):self.ledger.selection(response)

    def test_empty_evidence_abstains_and_user_question_is_not_its_own_answer(self):
        identifier=self.ledger.user('¿La retención es 900 segundos?')
        selected=self.ledger.selection(dict(grounding=dict(sources=[identifier],abstain=False)))
        result=self.ledger.render(selected)
        self.assertEqual(result['verification']['status'],'abstained')
        self.assertNotIn('900',result['answer'])

    def test_memory_content_titles_cues_and_authority_cannot_be_forged(self):
        identifier=self.source()
        quote='El valor vigente es 389 segundos.'
        actions=self.ledger.admit([self.action(identifier,quote)])
        canonical=actions[0]
        self.assertEqual(canonical['content'],quote)
        self.assertEqual(canonical['state'],'inferred')
        self.assertNotIn('900',json.dumps(canonical))
        self.assertEqual(canonical['cues'],[])
        self.assertTrue(canonical['source'].startswith('synopsis:quoted-evidence:'))

    def test_negation_cannot_be_cut_out_of_a_memory_quote(self):
        identifier=self.source()
        for quote in ('300 segundos.','La retención es 300 segundos.','NO es 300'):
            with self.assertRaises(EvidenceError):self.ledger.admit([self.action(identifier,quote)])

    def test_current_source_change_blocks_render_and_admission(self):
        identifier=self.source()
        self.path.write_text('changed')
        with self.assertRaisesRegex(EvidenceError,'evidence_changed'):self.ledger.render([identifier])
        with self.assertRaisesRegex(EvidenceError,'evidence_changed'):self.ledger.admit([self.action(identifier,'El valor vigente es 389 segundos.')])

    def test_mutating_a_model_packet_does_not_mutate_the_ledger(self):
        identifier=self.source()
        packet=self.ledger.packet()
        packet['sources'][0]['text']='900 seconds'
        self.assertNotIn('900',self.ledger.render([identifier])['answer'])

    def test_path_traversal_hidden_paths_symlinks_and_unknown_tools_are_denied(self):
        outside=self.root.parent/'outside.txt';outside.write_text('private')
        (self.root/'link.txt').symlink_to(outside)
        for request in (dict(tool='read_file',path='../outside.txt'),dict(tool='read_file',path=str(outside)),
                        dict(tool='read_file',path='link.txt'),dict(tool='read_file',path='.env'),
                        dict(tool='bash',command='anything')):
            with self.subTest(request=request),self.assertRaises(EvidenceError):self.ledger.tool(request)

    def test_literal_calculations_and_json_are_observations_not_world_truth(self):
        self.assertEqual(calculate('0.1 + 0.2'),'0.3')
        self.assertEqual(calculate('60 * 5'),'300')
        for expression in ('__import__("os")','2**10000','1/0','True + 1','x+1','[1]','1e309','1/3','1e-99999999','0e-99999999'):
            with self.subTest(expression=expression),self.assertRaises(EvidenceError):calculate(expression)
        (self.root/'settings.json').write_text(json.dumps(dict(cache=dict(ttl=389))))
        identifier=self.ledger.tool(dict(tool='json_value',path='settings.json',pointer='/cache/ttl'))
        result=self.ledger.render([identifier])
        self.assertIn('/cache/ttl = 389',result['answer'])
        self.assertIsNone(result['verification']['sources'][0]['start'])

    def test_source_change_after_a_symlink_swap_is_not_accepted(self):
        identifier=self.source()
        self.path.unlink();self.path.symlink_to(self.root.parent/'outside')
        with self.assertRaises(EvidenceError):self.ledger.render([identifier])

    def test_negation_spanning_lines_cannot_be_laundered_into_memory(self):
        self.path.write_text('No se debe utilizar:\n300 segundos.\n')
        identifier=self.source()
        with self.assertRaises(EvidenceError):
            self.ledger.admit([self.action(identifier,'300 segundos.')])

    def test_json_ambiguity_nonfinite_numbers_and_sensitive_subtrees_are_rejected(self):
        for text in ('{"ttl":127,"ttl":389}','{"ttl":NaN}','{"data":{"password":"example-password"}}'):
            (self.root/'settings.json').write_text(text)
            with self.subTest(text=text),self.assertRaises(EvidenceError):self.ledger.tool(dict(tool='json_value',path='settings.json',pointer=''))
        (self.root/'settings.json').write_text('{"value":0.12345678901234567890123456789}')
        identifier=self.ledger.tool(dict(tool='json_value',path='settings.json',pointer='/value'))
        self.assertIn('0.12345678901234567890123456789',self.ledger.render([identifier])['answer'])

    def test_public_agent_documentation_can_be_inspected_without_opening_hidden_secrets(self):
        docs=self.root/'.agents/docs';docs.mkdir(parents=True)
        (docs/'rules.md').write_text('Use local test databases.')
        identifier=self.ledger.tool(dict(tool='read_file',path='.agents/docs/rules.md'))
        self.assertIn('local test databases',self.ledger.render([identifier])['answer'])

    def test_source_markup_is_literal_and_cannot_escape_its_fence(self):
        self.path.write_text('![tracker](https://example.com)\n```\n<img src="https://example.com">')
        identifier=self.source()
        answer=self.ledger.render([identifier])['answer']
        self.assertIn('````text',answer)
        self.assertTrue(answer.endswith('````'))

    def test_read_rejects_an_ancestor_link_even_if_a_scope_lookup_was_cached(self):
        actual=self.root/'actual';actual.mkdir()
        (actual/'data.txt').write_text('private')
        (self.root/'linked').symlink_to(actual,target_is_directory=True)
        if os.name=='posix':
            with self.assertRaises(EvidenceError):read_regular(self.root/'linked/data.txt')

    def test_models_can_propose_only_semantics_without_fabricating_storage_fields(self):
        identifier=self.ledger.user('La retención es 389 segundos.')
        canonical=self.ledger.admit([dict(filename='retention',support=[dict(source=identifier,quote='La retención es 389 segundos.')])])[0]
        self.assertEqual(canonical['kind'],'project')
        self.assertEqual(canonical['content'],'La retención es 389 segundos.')
