"""Real retrieval and crash/concurrency regressions, using invented isolated notes."""
import contextlib
import concurrent.futures
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'engine'))
from memory_store import MemoryStore, MemoryConflict, active


class MemoryEngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.isolation = tempfile.TemporaryDirectory()
        base = Path(cls.isolation.name)
        config = base / 'config.json'
        config.write_text(json.dumps({'usuario': 'Test', 'fuentes': [], 'proyectos': []}))
        cls.environment = patch.dict(os.environ, {'CEREBRO_CONFIG': str(config), 'CLAUDE_PLUGIN_DATA': str(base)})
        cls.environment.start()
        import cerebro, buscador, conector_mcp
        cls.core, cls.search, cls.mcp = cerebro, buscador, conector_mcp

    @classmethod
    def tearDownClass(cls):
        cls.environment.stop()
        cls.isolation.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.folder = self.base / 'memory'
        self.store = MemoryStore(self.folder)

    def save(self, **changes):
        args = dict(filename='cache-policy', name='cache-policy', description='Caducidad de caché del proyecto',
                    kind='project', content='La caché Redis caduca después de 90 segundos.',
                    index_line='- [Caché](cache-policy.md) — regla confirmada', source='user:session-test', state='confirmed')
        args.update(changes)
        return self.store.save(**args)

    def test_retry_is_idempotent_and_index_has_one_entry(self):
        first = self.save()
        again = self.save()
        self.assertEqual(first['revision'], 1)
        self.assertTrue(again['unchanged'])
        self.assertEqual(len(self.store.history('cache-policy')), 1)
        self.assertEqual((self.folder / 'MEMORY.md').read_text().count('(cache-policy.md)'), 1)

    def test_correction_preserves_provenance_and_prior_revision(self):
        self.save()
        self.save(content='La caché Redis caduca después de 120 segundos.', overwrite=True, expected_revision=1)
        history = self.store.history('cache-policy')
        self.assertEqual([item['revision'] for item in history], [1, 2])
        self.assertIn('90 segundos', history[0]['text'])
        self.assertIn('120 segundos', history[1]['text'])
        self.assertEqual(history[1]['metadata']['source'], 'user:session-test')
        with self.assertRaises(MemoryConflict):
            self.save(overwrite=True, expected_revision=1)

    def test_parallel_writers_do_not_lose_index_entries(self):
        def writer(number):
            return self.save(filename=f'note-{number}', name=f'note-{number}',
                             content=f'La unidad de prueba {number} usa la configuración {number}.',
                             index_line=f'- [Unidad {number}](note-{number}.md)')
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(writer, range(16)))
        self.assertEqual(len(results), 16)
        index = (self.folder / 'MEMORY.md').read_text()
        for n in range(16):
            self.assertEqual(index.count(f'(note-{n}.md)'), 1)

    def test_failure_between_note_and_index_is_recovered_on_retry(self):
        import memory_store
        atomic = memory_store.escribir_atomico
        def fail_index(path, text):
            if path.name == 'MEMORY.md':
                raise OSError('simulated interrupted write')
            atomic(path, text)
        with patch.object(memory_store, 'escribir_atomico', side_effect=fail_index):
            with self.assertRaises(OSError):
                self.save()
        self.assertTrue((self.folder / 'cache-policy.md').exists())
        self.assertTrue(self.save()['unchanged'])
        self.assertEqual((self.folder / 'MEMORY.md').read_text().count('(cache-policy.md)'), 1)
        self.assertEqual(len(self.store.history('cache-policy')), 1)

    def test_recovery_refuses_to_overwrite_an_external_edit(self):
        import memory_store
        with patch.object(memory_store, 'escribir_atomico', side_effect=OSError('interruption')):
            with self.assertRaises(OSError):
                self.save()
        target = self.folder / 'cache-policy.md'
        target.write_text('Edición humana posterior')
        with self.assertRaises(MemoryConflict):
            self.save()
        self.assertEqual(target.read_text(), 'Edición humana posterior')

    def test_external_edits_invalidate_expected_revision(self):
        self.save()
        target = self.folder / 'cache-policy.md'
        target.write_text(target.read_text() + '\nNueva corrección humana\n')
        with self.assertRaises(MemoryConflict):
            self.save(overwrite=True, expected_revision=1)
        self.assertIn('Nueva corrección humana', target.read_text())

    def test_replacing_a_legacy_note_preserves_its_original_text(self):
        self.folder.mkdir()
        (self.folder / 'cache-policy.md').write_text('Regla original escrita a mano.')
        result = self.save(overwrite=True)
        history = self.store.history('cache-policy')
        self.assertEqual(result['revision'], 2)
        self.assertEqual(history[0]['text'], 'Regla original escrita a mano.')
        self.assertEqual(history[0]['metadata']['source'], 'external:file')

    def test_explicit_replacement_preserves_an_out_of_band_correction(self):
        self.save()
        path = self.folder / 'cache-policy.md'
        path.write_text('Cambio humano entre sesiones.')
        result = self.save(overwrite=True)
        history = self.store.history('cache-policy')
        self.assertEqual(result['revision'], 3)
        self.assertEqual(history[1]['text'], 'Cambio humano entre sesiones.')

    def test_duplicate_under_another_name_is_rejected(self):
        self.save()
        with self.assertRaises(MemoryConflict):
            self.save(filename='cache-copy', name='cache-copy', index_line='- [Copia](cache-copy.md)')

    def test_rejects_path_traversal_reserved_index_yaml_and_recognizable_secrets(self):
        invalid = [dict(filename='../escape'), dict(filename='MEMORY.md'), dict(name='x\nmetadata:'),
                   dict(content='-----BEGIN PRIVATE KEY-----'), dict(index_line='- [Ajeno](other.md)'),
                   dict(index_line='- [Caché](cache-policy.md)\n- [Otro](other.md)'),
                   dict(expires_at='2030-01-01'), dict(expected_revision=True),
                   dict(overwrite='false'), dict(cues={}), dict(source=True)]
        for args in invalid:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.save(**args)
        self.assertFalse(self.folder.exists())

    @unittest.skipIf(os.name == 'nt', 'POSIX symlinks and permissions')
    def test_symlink_projection_cannot_modify_an_unrelated_file(self):
        self.folder.mkdir()
        victim = self.base / 'victim'
        victim.write_text('private')
        (self.folder / 'cache-policy.md').symlink_to(victim)
        with self.assertRaises(MemoryConflict):
            self.save(overwrite=True)
        self.assertEqual(victim.read_text(), 'private')

    def test_lifecycle_excludes_expired_archived_and_invalid_dates(self):
        self.assertTrue(active({'state': 'confirmed'}))
        self.assertTrue(active({'state': 'inferred', 'expires_at': '2999-01-01T00:00:00Z'}))
        self.assertFalse(active({'state': 'archived'}))
        self.assertFalse(active({'expires_at': '2000-01-01T00:00:00Z'}))
        self.assertFalse(active({'expires_at': 'broken'}))

    def build_index(self):
        import configuracion, fichas
        project = self.base / 'project'
        other = self.base / 'other-project'
        project.mkdir(exist_ok=True)
        other.mkdir(exist_ok=True)
        docs = project / 'docs'
        docs.mkdir(exist_ok=True)
        (docs / 'routing.md').write_text('# Ruteo\n\nEl ruteo de vehículos utiliza OSRM privado.\n')
        (other / 'routing.md').write_text('# Ruteo\n\nEl ruteo de vehículos utiliza un proveedor externo secreto.\n')
        sources = configuracion.fuentes_de({'fuentes': [
            dict(id='primary', memoria=True, proyecto=str(project), raices=[
                [str(self.folder), False, 'memory'], [str(docs), True, 'docs']]),
            dict(id='other', memoria=False, raices=[[str(other), True, '']]),
        ]}, self.base)
        config = dict(self.core.CONFIG, proyectos=[
            dict(raiz=str(project), alias='project', codigo=[], pistas=[], marca=None),
            dict(raiz=str(other), alias='other-project', codigo=[], pistas=[], marca=None),
        ])
        with patch.object(self.core, 'FUENTES', sources), patch.object(self.core, 'CONFIG', config), \
                patch.object(fichas, 'leer', return_value={'fichas': {}}), \
                patch.object(self.search, 'rutas_de_codigo', return_value=None):
            self.core._listados.clear()
            brain = self.core.Cerebro()
            brain.recolectar()
            brain.analizar(self.base / 'suggestions.json', con_parecidas=False, con_entidades=False)
            index = self.search.Indice(brain)
        return brain, index, project

    def test_mixed_source_keeps_docs_out_of_memory_health_rules(self):
        import medico
        self.save()
        brain, _, _ = self.build_index()
        docs = [node for node in brain.nodos if node['ruta'].endswith('routing.md')]
        self.assertTrue(docs)
        self.assertTrue(all(not brain.fuente_de[node['id']].get('memoria') for node in docs))
        self.assertFalse({n['id'] for n in docs} & set(brain.sin_indice))
        self.assertFalse(any(item['nota'] in {n['id'] for n in docs} for item in medico.regla_frontmatter(brain)))

    def test_recall_is_scoped_cited_budgeted_and_does_not_invent_evidence(self):
        from context_memory import recall
        self.save()
        _, index, project = self.build_index()
        packet = recall(index, 'ruteo vehículos OSRM', str(project), budget=1600)
        self.assertFalse(packet['abstained'], packet)
        self.assertTrue(all('/other-project/' not in item['path'] for item in packet['evidence']))
        self.assertLessEqual(len(json.dumps(packet, ensure_ascii=False)), 1600)
        self.assertEqual(packet['used'], len(json.dumps(packet, ensure_ascii=False)))
        for evidence in packet['evidence']:
            lines = Path(evidence['path']).read_text().splitlines()
            self.assertEqual(evidence['text'], '\n'.join(lines[evidence['start'] - 1:evidence['end']]))
        missing = recall(index, 'neutrinos quásares astrofísica', str(project))
        self.assertTrue(missing['abstained'], missing)

    def test_recall_observes_expiry_and_external_edits_without_waiting_for_cache(self):
        from context_memory import recall
        self.save()
        _, index, project = self.build_index()
        first = recall(index, 'Redis caché segundos', str(project))
        self.assertFalse(first['abstained'], first)
        path = self.folder / 'cache-policy.md'
        text = path.read_text()
        path.write_text(text.replace('  state: "confirmed"', '  state: "archived"'))
        self.assertTrue(recall(index, 'Redis caché segundos', str(project))['abstained'])
        path.write_text(text.replace('90 segundos', '120 segundos'))
        self.assertTrue(recall(index, 'Redis caché segundos', str(project))['abstained'])
        self.assertFalse(index.sobre('Redis caché segundos')['leerPrimero'])

    def test_touching_a_file_does_not_discard_unchanged_evidence(self):
        from context_memory import recall
        self.save()
        _, index, project = self.build_index()
        path = self.folder / 'cache-policy.md'
        state = path.stat()
        os.utime(path, ns=(state.st_atime_ns, state.st_mtime_ns + 1_000_000_000))
        self.assertFalse(recall(index, 'Redis caché segundos', str(project))['abstained'])
        self.assertTrue(index.buscar('Redis caché segundos')['resultados'])

    def test_a_new_project_can_save_then_recall_without_restarting_the_mcp_server(self):
        project = self.base / 'new-project'
        project.mkdir()
        home = self.base / 'home'
        home.mkdir()
        args = dict(proyecto=str(project), archivo='new-rule', nombre='new-rule', tipo='project',
                    descripcion='Política de Redis', contenido='Redis conserva la caché durante 120 segundos.',
                    linea_indice='- [Redis](new-rule.md)', fuente='user:test', estado='confirmed')
        old_scope = self.search.ALCANCE
        self.addCleanup(setattr, self.search, 'ALCANCE', old_scope)
        with patch('pathlib.Path.home', return_value=home), patch.object(self.core, 'FUENTES', []), \
                patch.object(self.mcp, 'anotar'), patch.dict(self.mcp._indice, valor=None):
            saved = self.mcp.llamar({'name': 'guardar', 'arguments': args})
            self.assertNotIn('isError', saved, saved)
            first = self.mcp.llamar({'name': 'recordar', 'arguments': dict(proyecto=str(project), consulta='Redis caché')})
            self.assertFalse(first['structuredContent']['abstained'], first)
            args.update(contenido='Redis conserva la caché durante 180 segundos.', sobrescribir=True, revision_esperada=1)
            changed = self.mcp.llamar({'name': 'guardar', 'arguments': args})
            self.assertNotIn('isError', changed, changed)
            second = self.mcp.llamar({'name': 'recordar', 'arguments': dict(proyecto=str(project), consulta='Redis caché')})
            evidence = second['structuredContent']['evidence']
            self.assertTrue(any('180 segundos' in item['text'] for item in evidence), second)
            self.assertFalse(any('120 segundos' in item['text'] for item in evidence), second)

    def test_mcp_returns_a_structured_context_packet(self):
        self.save()
        _, index, project = self.build_index()
        with patch.object(self.mcp, 'indice', return_value=index), patch.object(self.mcp, 'anotar'):
            result = self.mcp.llamar({'name': 'recordar', 'arguments': dict(consulta='Redis caché', proyecto=str(project))})
        self.assertNotIn('isError', result, result)
        self.assertFalse(result['structuredContent']['abstained'])
        self.assertIn('texto citado', result['content'][0]['text'])

    def test_retrieval_cues_bridge_vocabulary_and_remain_separate_from_facts(self):
        from context_memory import recall
        self.save(cues=['session retention policy', 'remember previous conversation'])
        _, index, project = self.build_index()
        result = recall(index, 'session retention policy', str(project))
        self.assertFalse(result['abstained'], result)
        evidence = result['evidence'][0]
        self.assertEqual(evidence['reason'], 'retrieval_cue')
        self.assertIn('90 segundos', evidence['text'])
        self.assertIn('retention', evidence['metadata']['retrieval_cues'])
        path = self.folder / 'cache-policy.md'
        path.write_text(path.read_text().replace('session retention policy', 'different retrieval vocabulary'))
        self.assertTrue(recall(index, 'session retention policy', str(project))['abstained'])

    def test_outcome_feedback_is_revision_bound_project_scoped_and_idempotent(self):
        from recall_feedback import RecallFeedback
        from context_memory import recall
        feedback = RecallFeedback(self.base / 'feedback')
        self.save()
        _, index, project = self.build_index()
        result = recall(index, 'Redis caché', str(project), budget=1600, feedback=feedback)
        identifier = result['feedback_id']
        self.assertTrue(identifier)
        self.assertLessEqual(result['used'], 1600)
        with self.assertRaises(ValueError):
            feedback.report(identifier, str(self.base / 'other'), 'useful', 'user:test')
        self.assertTrue(feedback.report(identifier, str(project), 'useful', 'user:test')['recorded'])
        self.assertTrue(feedback.report(identifier, str(project), 'useful', 'user:test')['unchanged'])
        with self.assertRaises(ValueError):
            feedback.report(identifier, str(project), 'incorrect', 'user:test')
        evidence = result['evidence'][0]
        factors = feedback.factors(str(project))
        self.assertGreater(factors[(evidence['path'], evidence['sha256'])], 1)
        self.assertLess(factors[(evidence['path'], evidence['sha256'])], 1.15)
        with contextlib.closing(sqlite3.connect(self.base / 'feedback/recall-feedback.sqlite3')) as db:
            stored = db.execute('SELECT query_hash, evidence FROM packets').fetchone()
        self.assertNotIn('Redis', str(stored))
        self.assertNotIn('90 segundos', str(stored))
        self.assertNotIn((evidence['path'], 'another-revision'), factors)
        with contextlib.closing(sqlite3.connect(self.base / 'feedback/recall-feedback.sqlite3')) as db:
            db.execute('UPDATE packets SET created_at=?', ('2000-01-01T00:00:00+00:00',))
            db.commit()
        self.assertEqual(feedback.factors(str(project)), {})
        with self.assertRaises(ValueError):
            feedback.report(identifier, str(project), 'useful', 'user:test')

    def test_positive_feedback_cannot_create_evidence_for_an_unrelated_query(self):
        from recall_feedback import RecallFeedback
        from context_memory import recall
        self.save()
        _, index, project = self.build_index()
        feedback = RecallFeedback(self.base / 'feedback')
        result = recall(index, 'Redis caché', str(project), feedback=feedback)
        feedback.report(result['feedback_id'], str(project), 'useful', 'user:test')
        unrelated = recall(index, 'neutrinos quásares astrofísica', str(project), feedback=feedback)
        self.assertTrue(unrelated['abstained'])
        self.assertIsNone(unrelated['feedback_id'])

    def test_generic_cli_saves_history_without_a_model_or_external_service(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home, SYNOPSIS_DATA=str(self.base / 'data'))
            cli = [sys.executable, '-B', str(ROOT / 'bin/synopsis'), 'memory']
            saved = subprocess.run(cli + ['save', '--project', str(self.base), '--file', 'cli-note',
                                         '--description', 'Preferencia de salida', '--source', 'user:test'],
                                   input='El usuario prefiere respuestas concisas.', text=True, capture_output=True, env=env)
            self.assertEqual(saved.returncode, 0, saved.stderr)
            history = subprocess.run(cli + ['history', '--project', str(self.base), '--file', 'cli-note'],
                                     text=True, capture_output=True, env=env)
            self.assertEqual(history.returncode, 0, history.stderr)
            self.assertEqual(json.loads(history.stdout)[0]['metadata']['source'], 'user:test')

    def test_corrupt_foreign_identity_is_excluded_without_blocking_project_recall(self):
        from context_memory import recall
        self.save()
        _, index, project = self.build_index()
        private = self.base / 'other-project/.synopsis'
        private.mkdir()
        (private / 'project.json').write_text('not json')
        packet = recall(index, 'Redis caché segundos', str(project))
        self.assertFalse(packet['abstained'], packet)
        self.assertTrue(all('/other-project/' not in item['path'] for item in packet['evidence']))

    def test_semantic_recall_emits_verifiable_citations_with_project_scope(self):
        from context_memory import recall
        self.save(content='El aparato está descompuesto y requiere reparación.')
        _, index, project = self.build_index()
        seen = []
        class Backend:
            identity='test-vector-transport'
            def __call__(self, texts):
                seen.extend(texts)
                return [[1.,0.] if any(word in text for word in ('descompuesto','malfunction')) else [0.,1.] for text in texts]
        with patch('semantic_memory.discover', return_value=Backend()):
            packet = recall(index, 'A malfunction occurred', str(project), budget=1600)
        self.assertFalse(packet['abstained'], packet)
        self.assertEqual(packet['retrieval']['mode'],'hybrid')
        self.assertEqual(packet['evidence'][0]['reason'],'semantic_evidence')
        self.assertTrue(packet['evidence'][0]['path'].endswith('cache-policy.md'))
        self.assertTrue(all('externo secreto' not in text for text in seen))
        self.assertLessEqual(len(json.dumps(packet,ensure_ascii=False)),1600)
        for evidence in packet['evidence']:
            lines=Path(evidence['path']).read_text().splitlines()
            self.assertEqual(evidence['text'],'\n'.join(lines[evidence['start']-1:evidence['end']]))
