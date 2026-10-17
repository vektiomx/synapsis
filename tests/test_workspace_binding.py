"""Automatic bindings across clients, moves, copies, worktrees and legacy migrations."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'engine'))
import project_identity as identity
import workspace_registry as workspaces
from memory_store import MemoryStore
from memory_cycle import MemoryCycle


class WorkspaceBindingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / 'home'
        self.data = self.base / 'data'
        self.config = self.base / 'config.json'
        self.config.write_text(json.dumps(dict(fuentes=[], proyectos=[])))
        env = patch.dict(os.environ, HOME=str(self.home), SYNOPSIS_DATA=str(self.data),
                         CEREBRO_CONFIG=str(self.config), CLAUDE_CONFIG_DIR=str(self.home / '.claude'))
        env.start()
        self.addCleanup(env.stop)
        self.project = self.base / 'repo'
        self.project.mkdir()

    def save(self, folder):
        return MemoryStore(folder).save(filename='policy', name='policy', description='Decision', kind='project',
            content='The project retains records for 90 days.', index_line='- [Policy](policy.md)', source='user:test')

    def legacy(self):
        folder = self.home / '.claude/projects' / str(self.project).replace('/', '-') / 'memory'
        self.save(folder)
        return folder

    def test_plain_project_and_subfolder_have_one_memory_after_first_use(self):
        child = self.project / 'src'
        child.mkdir()
        folder = identity.resolve_memory(str(self.project))
        self.assertEqual(workspaces.discover(str(child)), str(self.project))
        self.assertEqual(identity.resolve_memory(str(child)), folder)
        self.assertEqual(len(list((self.data / 'projects').glob('*/location.json'))), 1)

    def test_ide_root_and_active_path_disambiguate_multiroot_without_scanning_disk(self):
        child = self.project / 'src'
        child.mkdir()
        other = self.base / 'other'
        other.mkdir()
        self.assertEqual(workspaces.discover(str(child), [str(self.project)]), str(self.project))
        self.assertEqual(workspaces.discover(str(self.base), [str(self.project), str(other)], str(other / 'file.py')), str(other))

    def test_real_cwd_metadata_adopts_legacy_memory_without_copying_notes_or_history(self):
        folder = self.legacy()
        before = {p.name: p.read_bytes() for p in folder.glob('*.md')}
        (folder.parent / 'session.jsonl').write_text(json.dumps({'cwd': str(self.project), 'message': {'text': 'not inspected'}})+'\n')
        self.assertEqual(identity.resolve_memory(str(self.project)), folder)
        self.assertEqual(before, {p.name: p.read_bytes() for p in folder.glob('*.md')})
        self.assertEqual(len(MemoryStore(folder).history('policy')), 1)
        self.assertFalse(identity.canonical_memory(str(self.project)).exists())

    def test_missing_or_conflicting_legacy_metadata_creates_ui_request_without_claiming_memory(self):
        folder = self.legacy()
        (folder.parent / 'session.jsonl').write_text(json.dumps({'cwd': str(self.base / 'deleted-other-project')}))
        with self.assertRaises(identity.ProjectIdentityConflict):
            identity.resolve_memory(str(self.project))
        self.assertIsNone(identity.owner(folder))
        self.assertFalse(identity.canonical_memory(str(self.project)).exists())
        requests = workspaces.pending()
        self.assertEqual(len(requests), 1)
        self.assertTrue(workspaces.choose(requests[0]['id'], 'existing')['bound'])
        self.assertEqual(identity.resolve_memory(str(self.project)), folder)
        self.assertEqual(workspaces.pending(), [])

    def test_ui_can_keep_unrelated_legacy_memory_independent(self):
        folder = self.legacy()
        with self.assertRaises(identity.ProjectIdentityConflict):
            identity.resolve_memory(str(self.project))
        result = workspaces.choose(workspaces.pending()[0]['id'], 'independent')
        self.assertNotEqual(Path(result['memory']), folder)
        self.assertIsNone(identity.owner(folder))
        self.assertFalse((Path(result['memory']) / 'policy.md').exists())

    def test_stale_request_cannot_bind_changed_or_foreign_memory(self):
        folder = self.legacy()
        with self.assertRaises(identity.ProjectIdentityConflict):
            identity.resolve_memory(str(self.project))
        request = workspaces.pending()[0]
        (folder / 'policy.md').write_text('Changed after preview')
        with self.assertRaises(identity.ProjectIdentityConflict):
            workspaces.choose(request['id'], 'existing')
        self.assertIsNone(identity.owner(folder))

    def test_move_preserves_stable_id_notes_revisions_and_pending_turn(self):
        folder = identity.resolve_memory(str(self.project))
        self.save(folder)
        cycle = MemoryCycle(folder, str(self.project))
        turn = cycle.begin('session', 'continue')['turn']
        before = workspaces.prepare(str(self.project))['id']
        moved = self.base / 'renamed'
        self.project.rename(moved)
        self.assertEqual(identity.resolve_memory(str(moved)), folder)
        self.assertEqual(workspaces.prepare(str(moved))['id'], before)
        self.assertEqual(identity.owner(folder), str(moved))
        self.assertEqual(len(MemoryStore(folder).history('policy')), 1)
        self.assertEqual(MemoryCycle(folder, str(moved)).status(turn)['turns'][0]['turn'], turn)
        self.assertEqual(len(list((self.data / 'projects').glob('*/location.json'))), 1)

    def test_copied_project_has_new_identity_and_cannot_read_original_notes(self):
        folder = identity.resolve_memory(str(self.project))
        self.save(folder)
        copy = self.base / 'copy'
        shutil.copytree(self.project, copy)
        other = identity.resolve_memory(str(copy))
        self.assertNotEqual(other, folder)
        self.assertNotEqual(workspaces.prepare(str(copy))['id'], workspaces.prepare(str(self.project))['id'])
        self.assertFalse((other / 'policy.md').exists())

    def test_same_names_in_different_directories_never_share_memory(self):
        other = self.base / 'nested/repo'
        other.mkdir(parents=True)
        first, second = identity.resolve_memory(str(other)), identity.resolve_memory(str(self.project))
        self.assertNotEqual(first, second)
        self.save(first)
        self.save(second)
        result = subprocess.run([sys.executable, '-B', '-c',
            "import cerebro,json;d=cerebro.desde_disco().armar();print(json.dumps([n['titulo'] for n in d['nodos'] if n['tipo']=='indice']))"],
            env=dict(os.environ, PYTHONPATH=str(ROOT / 'engine')), capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        labels = json.loads(result.stdout)
        self.assertEqual(len(set(labels)), 2)
        self.assertTrue(any(str(self.project) in label for label in labels))

    def test_worktrees_have_shared_group_but_independent_branch_memory(self):
        git = self.project / '.git'
        git.mkdir()
        (git / 'HEAD').write_text('ref: refs/heads/main')
        tree = self.base / 'feature'
        tree.mkdir()
        meta = git / 'worktrees/feature'
        meta.mkdir(parents=True)
        (meta / 'HEAD').write_text('ref: refs/heads/feature')
        (meta / 'commondir').write_text('../..')
        (tree / '.git').write_text('gitdir: ' + str(meta))
        folder = identity.resolve_memory(str(self.project))
        feature = identity.resolve_memory(str(tree))
        self.assertNotEqual(folder, feature)
        self.assertEqual(workspaces.prepare(str(self.project))['group'], workspaces.prepare(str(tree))['group'])
        self.save(feature)
        self.assertFalse((folder / 'policy.md').exists())

    def test_symlink_metadata_and_bad_ids_fail_without_binding(self):
        private = self.project / '.synopsis'
        private.mkdir()
        foreign = self.base / 'foreign.json'
        foreign.write_text(json.dumps({'id': '0'*32}))
        (private / 'workspace.json').symlink_to(foreign)
        with self.assertRaises(identity.ProjectIdentityConflict):
            identity.resolve_memory(str(self.project))
        self.assertFalse(identity.canonical_memory(str(self.project)).exists())

    def test_readonly_project_registry_is_reused_without_a_repo_marker(self):
        original = identity._publish
        def publish(path, data):
            if Path(path).name == 'workspace.json':
                raise PermissionError('read-only project')
            return original(path, data)
        with patch.object(identity, '_publish', side_effect=publish):
            folder = identity.resolve_memory(str(self.project))
            first = workspaces.prepare(str(self.project))['id']
            self.assertEqual(identity.resolve_memory(str(self.project)), folder)
            self.assertEqual(workspaces.prepare(str(self.project))['id'], first)
        self.assertEqual(len(list((self.data / 'workspaces').glob('*.json'))), 1)

    def test_move_with_a_recreated_marker_requires_ui_confirmation(self):
        folder = identity.resolve_memory(str(self.project))
        self.save(folder)
        moved = self.base / 'moved'
        self.project.rename(moved)
        marker = moved / '.synopsis/workspace.json'
        text = marker.read_text()
        replacement = marker.with_suffix('.replacement')
        replacement.write_text(text)
        replacement.replace(marker)
        with self.assertRaises(identity.ProjectIdentityConflict):
            identity.resolve_memory(str(moved))
        request = workspaces.pending()[0]
        self.assertTrue(request['relocation'])
        self.assertTrue(workspaces.choose(request['id'], 'existing')['bound'])
        self.assertEqual(identity.resolve_memory(str(moved)), folder)
        self.assertEqual(identity.owner(folder), str(moved))

    def test_multiple_configured_memories_are_resolved_in_the_ui_without_merging(self):
        folders = [self.base / 'memory-one', self.base / 'memory-two']
        for folder in folders:
            self.save(folder)
        self.config.write_text(json.dumps(dict(fuentes=[dict(id='m'+str(n), memoria=True,
            proyecto=str(self.project), raices=[[str(folder), False, '']]) for n, folder in enumerate(folders)], proyectos=[])))
        with self.assertRaises(identity.ProjectIdentityConflict):
            identity.resolve_memory(str(self.project))
        request = workspaces.pending()[0]
        self.assertEqual(len(request['choices']), 2)
        workspaces.choose(request['id'], 'existing:1')
        self.assertEqual(identity.resolve_memory(str(self.project)), folders[1])
        self.assertIsNone(identity.owner(folders[0]))

    def test_partial_relocation_is_recoverable_without_creating_another_store(self):
        folder = identity.resolve_memory(str(self.project))
        self.save(folder)
        moved = self.base / 'moved'
        self.project.rename(moved)
        original = identity._publish
        def publish(path, data):
            if Path(path).name == 'location.json':
                raise OSError('interrupted relocation')
            return original(path, data)
        with patch.object(identity, '_publish', side_effect=publish), self.assertRaises(OSError):
            identity.resolve_memory(str(moved))
        self.assertEqual(identity.resolve_memory(str(moved)), folder)
        self.assertEqual(len(MemoryStore(folder).history('policy')), 1)

    def test_concurrent_first_use_has_one_store_and_one_workspace_identity(self):
        script = 'import project_identity,sys; print(project_identity.resolve_memory(sys.argv[1]))'
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'engine'))
        processes = [subprocess.Popen([sys.executable, '-B', '-c', script, str(self.project)],
                    env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(3)]
        results = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, stderr)
            results.append(stdout.strip())
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(len(list((self.data / 'projects').glob('*/location.json'))), 1)
        self.assertEqual(len(list((self.data / 'workspaces').glob('*.json'))), 1)

    def test_five_real_bridges_reuse_one_project_when_working_in_a_subfolder(self):
        child = self.project / 'src'
        child.mkdir()
        env = dict(os.environ, SYNOPSIS_ROOT=str(ROOT / 'engine'), PYTHONDONTWRITEBYTECODE='1')
        clients = [('claude-code', 'claude'), ('codex', 'codex'), ('antigravity', 'antigravity'),
                   ('opencode', 'opencode'), ('cursor', 'cursor')]
        for directory, client in clients:
            for cwd in (str(self.project), str(child)):
                data = dict(hook_event_name='UserPromptSubmit', session_id=client, cwd=cwd,
                            prompt='Remember the record retention policy.', workspace_roots=[str(self.project)])
                args = []
                if client == 'antigravity':
                    data = dict(conversationId=client, cwd=cwd, workspacePaths=[str(self.project)], prompt=data['prompt'])
                    args = ['PreInvocation']
                if client == 'cursor':
                    data.update(hook_event_name='beforeSubmitPrompt', conversation_id=client)
                result = subprocess.run([sys.executable, '-B', str(ROOT / directory / 'bridge.py'), *args],
                                        input=json.dumps(data), env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn('bridge error', result.stdout)
                self.assertNotIn('memory_identity_conflict', result.stdout + result.stderr)
                if client == 'codex':
                    self.assertIn('ciclo de memoria', result.stdout)
                else:
                    json.loads(result.stdout)
        self.assertEqual(len(list((self.data / 'projects').glob('*/location.json'))), 1)
        self.assertEqual(len(list((self.data / 'workspaces').glob('*.json'))), 1)
        state = MemoryCycle(identity.resolve_memory(str(self.project)), str(self.project)).status(limit=20)
        self.assertEqual(state['pending'], 5)

    def test_map_index_has_project_name_and_verified_project_group(self):
        folder = identity.resolve_memory(str(self.project))
        self.save(folder)
        script = '''
import cerebro,json
data=cerebro.desde_disco().armar()
print(json.dumps({'indices':[n for n in data['nodos'] if n['tipo']=='indice'], 'groups':data['gruposDeProyecto']}))
'''
        result = subprocess.run([sys.executable, '-B', '-c', script],
            env=dict(os.environ, PYTHONPATH=str(ROOT / 'engine')), text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['indices'][0]['titulo'], 'repo · Memoria')
        self.assertTrue(any(group['nombre'] == 'repo' for group in data['groups']))

    def test_readonly_directory_can_move_on_same_filesystem_without_losing_memory(self):
        original = identity._publish
        def publish(path, data):
            if Path(path).name == 'workspace.json':
                raise PermissionError('read-only project')
            return original(path, data)
        with patch.object(identity, '_publish', side_effect=publish):
            folder = identity.resolve_memory(str(self.project))
            before = workspaces.prepare(str(self.project))['id']
            moved = self.base / 'moved'
            self.project.rename(moved)
            self.assertEqual(identity.resolve_memory(str(moved)), folder)
            self.assertEqual(workspaces.prepare(str(moved))['id'], before)

    def test_unrelated_corrupt_workspace_records_do_not_block_a_new_project(self):
        registry = self.data / 'workspaces'
        registry.mkdir(parents=True)
        (registry / 'malformed.json').write_text('{broken')
        (registry / 'invalid.json').write_text(json.dumps(dict(id=42, project=[], memory=None)))
        folder = identity.resolve_memory(str(self.project))
        self.assertEqual(identity.owner(folder), str(self.project))
        self.assertTrue(identity.describe(str(self.project))['workspace']['id'])
