"""No project assignment is inferred from an IDE's lossy folder spelling."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'engine'))
import project_identity as identity
from memory_store import MemoryStore


class ProjectIdentityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / 'home'
        self.data = self.base / 'state'
        self.config = self.base / 'config.json'
        self.config.write_text(json.dumps(dict(fuentes=[], proyectos=[])))
        env = patch.dict(os.environ, dict(SYNOPSIS_DATA=str(self.data), CEREBRO_CONFIG=str(self.config)))
        env.start()
        self.addCleanup(env.stop)
        home = patch('pathlib.Path.home', return_value=self.home)
        home.start()
        self.addCleanup(home.stop)
        self.first = str(self.base / 'alpha-beta')
        self.second = str(self.base / 'alpha/beta')

    def save(self, folder):
        return MemoryStore(folder).save(filename='redis-policy', name='redis-policy', description='TTL Redis',
            kind='project', content='Redis conserva 120 segundos.', index_line='- [Redis](redis-policy.md)', source='user:test')

    def configured(self, claims):
        self.config.write_text(json.dumps(dict(fuentes=[dict(id=f'memory-{n}', memoria=True, proyecto=project,
            raices=[[str(folder), False, '']]) for n, (project, folder) in enumerate(claims)])))

    def legacy(self):
        return self.home / '.claude/projects' / self.first.replace('/', '-') / 'memory'

    def test_roots_that_collided_have_independent_storage_and_full_identity(self):
        a = identity.resolve_memory(self.first)
        b = identity.resolve_memory(self.second)
        self.assertNotEqual(a, b)
        self.assertEqual(identity.owner(a), self.first)
        self.assertEqual(identity.owner(b), self.second)
        self.save(a)
        self.assertFalse((b / 'redis-policy.md').exists())
        self.assertEqual(identity.resolve_memory(self.first), a)

    def test_explicit_config_reuses_legacy_notes_index_and_revisions_in_place(self):
        legacy = self.legacy()
        self.save(legacy)
        before = {name: (legacy / name).read_bytes() for name in ('redis-policy.md', 'MEMORY.md', '.synopsis/memory.sqlite3')}
        self.configured([(self.first, legacy)])
        self.assertEqual(identity.resolve_memory(self.first), legacy)
        self.assertEqual(before, {name: (legacy / name).read_bytes() for name in before})
        self.assertEqual(len(MemoryStore(legacy).history('redis-policy')), 1)
        self.assertFalse(identity.canonical_memory(self.first).exists())
        other = identity.resolve_memory(self.second)
        self.assertNotEqual(other, legacy)
        self.assertFalse((other / 'redis-policy.md').exists())

    def test_unassigned_legacy_folder_is_never_guessed_from_its_name(self):
        legacy = self.legacy()
        self.save(legacy)
        before = (legacy / 'redis-policy.md').read_bytes()
        preview = identity.describe(self.first)
        self.assertEqual(preview['legacy_unassigned'], str(legacy))
        self.assertFalse(self.data.exists())
        with self.assertRaises(identity.ProjectIdentityConflict):
            identity.resolve_memory(self.first)
        self.assertFalse((self.data / 'projects').exists())
        self.assertEqual(len(list((self.data / 'binding-requests').glob('*.json'))), 1)
        self.assertIsNone(identity.owner(legacy))
        self.assertEqual((legacy / 'redis-policy.md').read_bytes(), before)

    def test_explicit_binding_before_first_use_preserves_existing_data(self):
        legacy = self.legacy()
        self.save(legacy)
        self.assertEqual(identity.bind(self.first, legacy), legacy)
        self.assertEqual(identity.resolve_memory(self.first), legacy)
        with self.assertRaises(identity.ProjectIdentityConflict):
            identity.bind(self.second, legacy)
        with self.assertRaises(identity.ProjectIdentityConflict):
            identity.bind(self.first, self.base / 'other')

    def test_two_explicit_project_claims_cannot_share_the_same_folder(self):
        legacy = self.legacy()
        self.save(legacy)
        self.configured([(self.first, legacy), (self.second, legacy)])
        with self.assertRaises(identity.ProjectIdentityConflict):
            identity.resolve_memory(self.first)
        self.assertIsNone(identity.owner(legacy))

    def test_crash_between_owner_and_pointer_keeps_the_original_binding_intent(self):
        legacy = self.legacy()
        self.save(legacy)
        original = identity._publish
        def fail_pointer(path, payload):
            if path.name == 'location.json':
                raise OSError('simulated interruption')
            original(path, payload)
        with patch.object(identity, '_publish', side_effect=fail_pointer):
            with self.assertRaises(OSError):
                identity.bind(self.first, legacy)
        self.assertEqual(identity.resolve_memory(self.first), legacy)
        self.assertFalse(identity.canonical_memory(self.first).exists())
        self.assertEqual(len(MemoryStore(legacy).history('redis-policy')), 1)

    def test_concurrent_claims_even_in_different_data_roots_have_one_owner(self):
        legacy = self.legacy()
        legacy.mkdir(parents=True)
        script = '''
import sys
sys.path.insert(0,sys.argv[1])
import project_identity
try:
    project_identity.bind(sys.argv[2], sys.argv[3])
except project_identity.ProjectIdentityConflict:
    sys.exit(3)
'''
        processes = [subprocess.Popen([sys.executable, '-B', '-c', script, str(ROOT / 'engine'), project, str(legacy)],
                     env=dict(os.environ, SYNOPSIS_DATA=str(self.base / f'state-{n}')), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                     for n, project in enumerate((self.first, self.second))]
        results = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=15)
            self.assertIn(process.returncode, (0, 3), stderr.decode())
            results.append(process.returncode)
        self.assertEqual(sorted(results), [0, 3])
        self.assertIn(identity.owner(legacy), (self.first, self.second))

    def test_symlink_project_alias_is_one_identity(self):
        Path(self.first).mkdir()
        alias = self.base / 'alias'
        alias.symlink_to(self.first, target_is_directory=True)
        self.assertEqual(identity.resolve_memory(str(alias)), identity.resolve_memory(self.first))

    def test_identity_hash_collision_or_tampered_manifest_fails_closed(self):
        with patch.object(identity, 'project_key', return_value='fixed-key'):
            identity.resolve_memory(self.first)
            with self.assertRaises(identity.ProjectIdentityConflict):
                identity.resolve_memory(self.second)

    def test_binding_prevents_stale_search_source_from_exposing_another_projects_notes(self):
        from context_memory import belongs
        folder = identity.resolve_memory(self.first)
        self.save(folder)
        note = dict(ruta=str(folder / 'redis-policy.md'), owner_project=self.second)
        self.assertFalse(belongs(note, self.second))
        self.assertTrue(belongs(note, self.first))

    def test_cli_binding_preview_does_not_write_and_apply_reuses_existing_folder(self):
        legacy = self.legacy()
        self.save(legacy)
        env = dict(os.environ, HOME=str(self.home), SYNOPSIS_ROOT=str(ROOT / 'engine'))
        command = [sys.executable, '-B', str(ROOT / 'bin/synopsis'), 'memory-location', '--project', self.first,
                   '--bind', str(legacy)]
        preview = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
        self.assertFalse(self.data.exists())
        applied = subprocess.run(command + ['--apply'], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertEqual(json.loads(applied.stdout)['memory'], str(legacy))
        self.assertEqual(identity.resolve_memory(self.first), legacy)

    def test_real_mcp_isolates_both_roots_even_when_their_legacy_slugs_match(self):
        for project in (self.first, self.second):
            Path(project).mkdir(parents=True)
        calls = []
        for number, (project, seconds) in enumerate(((self.first, 120), (self.second, 900)), 1):
            args = dict(proyecto=project, archivo='redis-policy', nombre='redis-policy', tipo='project',
                        descripcion='TTL Redis', contenido=f'Redis conserva la caché {seconds} segundos.',
                        linea_indice='- [Redis](redis-policy.md)', fuente='user:regression')
            calls.append(dict(jsonrpc='2.0', id=number, method='tools/call', params=dict(name='guardar', arguments=args)))
        for number, project in enumerate((self.first, self.second), 3):
            calls.append(dict(jsonrpc='2.0', id=number, method='tools/call', params=dict(name='recordar', arguments=dict(proyecto=project, consulta='Redis caché segundos'))))
        process = subprocess.run([sys.executable, '-B', str(ROOT / 'mcp_entry.py')],
                                 env=dict(os.environ, HOME=str(self.home), SYNOPSIS_ROOT=str(ROOT / 'engine')),
                                 input=''.join(json.dumps(call) + '\n' for call in calls),
                                 capture_output=True, text=True, timeout=20)
        self.assertEqual(process.returncode, 0, process.stderr)
        replies = {row['id']: row['result'] for row in map(json.loads, process.stdout.splitlines())}
        self.assertTrue(all(not row.get('isError') for row in replies.values()), replies)
        first = json.dumps(replies[3]['structuredContent']['evidence'], ensure_ascii=False)
        second = json.dumps(replies[4]['structuredContent']['evidence'], ensure_ascii=False)
        self.assertIn('120 segundos', first)
        self.assertNotIn('900 segundos', first)
        self.assertIn('900 segundos', second)
        self.assertNotIn('120 segundos', second)

    def test_fresh_configuration_discovers_registered_memory_without_duplicate_roots(self):
        import configuracion
        folder = identity.resolve_memory(self.first)
        self.save(folder)
        config = configuracion.cargar(self.config)
        roots = [Path(root).resolve() for source in config['fuentes'] for root, _, _ in source['raices']]
        self.assertEqual(roots.count(folder), 1)
        self.configured([(self.first, folder)])
        config = configuracion.cargar(self.config)
        roots = [Path(root).resolve() for source in config['fuentes'] for root, _, _ in source['raices']]
        self.assertEqual(roots.count(folder), 1)

    def test_demo_cannot_discover_registered_personal_memories(self):
        import configuracion
        folder = identity.resolve_memory(self.first)
        self.save(folder)
        config = configuracion.cargar(configuracion.DEMO)
        roots = [Path(root).resolve() for source in config['fuentes'] for root, _, _ in source['raices']]
        self.assertNotIn(folder, roots)

    def test_pending_intent_survives_interruption_before_owner_publication(self):
        legacy = self.legacy()
        self.save(legacy)
        original = identity._publish
        def fail_owner(path, payload):
            if path.name == 'project.json':
                raise OSError('simulated interruption')
            original(path, payload)
        with patch.object(identity, '_publish', side_effect=fail_owner), self.assertRaises(OSError):
            identity.bind(self.first, legacy)
        self.assertIsNone(identity.owner(legacy))
        self.assertEqual(identity.resolve_memory(self.first), legacy)
        self.assertFalse(identity.canonical_memory(self.first).exists())

    def test_symlink_identity_folder_does_not_receive_lock_or_manifest_writes(self):
        folder = self.base / 'memory'
        folder.mkdir()
        foreign = self.base / 'foreign'
        foreign.mkdir()
        (folder / '.synopsis').symlink_to(foreign, target_is_directory=True)
        with self.assertRaises(identity.ProjectIdentityConflict):
            identity.bind(self.first, folder)
        self.assertEqual(list(foreign.iterdir()), [])

    def test_owned_legacy_folder_can_rebuild_a_missing_registry_pointer_without_copying(self):
        legacy = self.legacy()
        self.save(legacy)
        identity.bind(self.first, legacy)
        (self.data / 'projects' / identity.project_key(self.first) / 'location.json').unlink()
        self.assertEqual(identity.resolve_memory(self.first), legacy)
        self.assertFalse(identity.canonical_memory(self.first).exists())
        self.assertEqual(len(MemoryStore(legacy).history('redis-policy')), 1)

    def test_identity_resolution_happens_once_per_recall_packet(self):
        import context_memory
        folder = identity.resolve_memory(self.first)
        self.save(folder)
        note = dict(ruta=str(folder / 'redis-policy.md'), owner_project=self.first)
        cache = {}
        with patch.object(identity, 'note_owner', wraps=identity.note_owner) as lookup:
            for _ in range(25):
                self.assertTrue(context_memory.belongs(note, Path(self.first), folder, cache))
        self.assertEqual(lookup.call_count, 1)

    def test_dangling_owner_manifest_is_not_treated_as_unowned(self):
        folder = self.base / 'memory'
        private = folder / '.synopsis'
        private.mkdir(parents=True)
        (private / 'project.json').symlink_to(self.base / 'missing-owner.json')
        with self.assertRaises(identity.ProjectIdentityConflict):
            identity.note_owner(folder / 'redis-policy.md')

    def test_loading_another_configuration_does_not_import_personal_registered_memories(self):
        import configuracion
        folder = identity.resolve_memory(self.first)
        self.save(folder)
        selected = self.base / 'public-only.json'
        selected.write_text(json.dumps(dict(fuentes=[], proyectos=[])))
        config = configuracion.cargar(selected)
        roots = [Path(root).resolve() for source in config['fuentes'] for root, _, _ in source['raices']]
        self.assertNotIn(folder, roots)
        original = configuracion.cargar(self.config)
        roots = [Path(root).resolve() for source in original['fuentes'] for root, _, _ in source['raices']]
        self.assertIn(folder, roots)

    def test_custom_claude_directory_uses_the_same_legacy_ownership_check(self):
        custom = self.base / 'custom-claude'
        legacy = custom / 'projects' / self.first.replace('/', '-') / 'memory'
        self.save(legacy)
        with patch.dict(os.environ, CLAUDE_CONFIG_DIR=str(custom)):
            self.assertEqual(identity.describe(self.first)['legacy_unassigned'], str(legacy))
            with self.assertRaises(identity.ProjectIdentityConflict):
                identity.resolve_memory(self.first)
        self.assertFalse((self.data / 'projects').exists())
        self.assertEqual(len(list((self.data / 'binding-requests').glob('*.json'))), 1)

    def test_passive_scope_filter_never_registers_memory_or_creates_state(self):
        from context_memory import belongs
        note = dict(ruta=str(self.base / 'legacy-memory/note.md'), owner_project=self.first)
        with patch.object(identity, 'resolve_memory', side_effect=AssertionError('read-only scope must not bind')):
            self.assertTrue(belongs(note, self.first))
            self.assertFalse(belongs(note, self.second))
        self.assertFalse(self.data.exists())
