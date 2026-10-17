"""A reviewed turn cuts off old edit reminders without pretending memory was written."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'engine'))
from memory_cycle import MemoryCycle
from hook_guardar import cuentas, texto_fin


class ReviewReminderTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.folder = self.base / 'memory'
        self.project = str(self.base / 'repo')
        self.cycle = MemoryCycle(self.folder, self.project)

    def test_review_lookup_without_a_database_does_not_create_one(self):
        self.assertIsNone(self.cycle.last_review('session'))
        self.assertFalse(self.folder.exists())

    def test_no_change_is_a_review_and_lookup_does_not_modify_the_database(self):
        turn = self.cycle.begin('session', 'Review project state')['turn']
        self.cycle.close(turn, 'no_change', 'Already documented in project docs.')
        database = self.folder / '.synopsis/memory.sqlite3'
        before = (database.read_bytes(), database.stat().st_mtime_ns)
        review = self.cycle.last_review('session')
        self.assertEqual(review['outcome'], 'no_change')
        self.assertGreater(review['at'], 0)
        self.assertEqual(before, (database.read_bytes(), database.stat().st_mtime_ns))

    def test_verified_saved_turn_is_also_a_review(self):
        turn = self.cycle.begin('session', 'Remember policy')['turn']
        self.cycle.queue(turn, [dict(filename='retention', name='retention', description='Retention policy',
            kind='project', content='Records are kept for 90 days.', index_line='- [Retention](retention.md)', source='user:test')])
        self.cycle.resume(turn)
        self.cycle.close(turn, 'saved')
        self.assertEqual(self.cycle.last_review('session')['outcome'], 'saved')

    def test_closure_of_another_session_or_project_does_not_suppress_review(self):
        turn = self.cycle.begin('samehead-first', 'Review')['turn']
        self.cycle.close(turn, 'no_change', 'No durable facts.')
        self.assertIsNone(self.cycle.last_review('samehead-second'))
        other = MemoryCycle(self.folder, str(self.base / 'other'))
        self.assertIsNone(other.last_review('samehead-first'))

    def test_open_turns_stay_pending_and_do_not_count_as_reviewed(self):
        turn = self.cycle.begin('session', 'Unreviewed changes')['turn']
        self.assertIsNone(self.cycle.last_review('session'))
        self.assertEqual(self.cycle.status(turn)['pending'], 1)

    def test_counter_excludes_old_and_foreign_edits_after_review(self):
        events = [dict(t=t, s='session', e='post', k='editar', f=str(Path(self.project) / f'{t}.py'))
                  for t in (10, 20, 30)]
        events.append(dict(t=40, s='session', e='post', k='editar', f=str(self.base / 'other/file.py')))
        result = cuentas(events, 'session', lambda path: False, revisado=25, proyecto=self.project)
        self.assertEqual(result[:3], (1, 0, False))
        text = texto_fin(5, 0, False, revisado=True)
        self.assertIn('desde la última revisión', text)
        self.assertNotIn('todavía no se escribió', text)
        self.assertNotIn('escribió en la memoria', text)

    def test_live_hook_uses_closure_and_only_counts_new_changes_in_its_project(self):
        config = self.base / 'config.json'
        config.write_text(json.dumps(dict(fuentes=[], proyectos=[])))
        script = r'''
import json,os,time
from pathlib import Path
from unittest.mock import patch
import project_identity
from memory_cycle import MemoryCycle
import hook_guardar,consultas
base=Path(os.environ['CASE_ROOT']);project=base/'repo';project.mkdir()
folder=project_identity.resolve_memory(str(project));cycle=MemoryCycle(folder,str(project))
session='testhead-real-session';short=session[:8]
turn=cycle.begin(session,'Review docs')['turn']
cycle.close(turn,'no_change','Changes are documented in project docs.')
review=cycle.last_review(session)
entries=[dict(t=review['at']-1,s=short,e='post',k='editar',f=str(project/(str(n)+'.py'))) for n in range(22)]
entries += [dict(t=review['at']+1,s=short,e='post',k='editar',f=str(base/'other'/(str(n)+'.py'))) for n in range(6)]
row=dict(hook_event_name='Stop',session_id=session,cwd=str(project))
def write():
    consultas.REGISTRO.parent.mkdir(parents=True,exist_ok=True)
    consultas.REGISTRO.write_text(''.join(json.dumps(item,separators=(',',':'))+'\n' for item in entries))
write()
with patch.object(hook_guardar,'anotar') as recorded:
    assert hook_guardar.aviso_fin(row,ahora=review['at']+1000) is None
    recorded.assert_not_called()
    entries += [dict(t=review['at']+2,s=short,e='post',k='editar',f=str(project/('new'+str(n)+'.py'))) for n in range(5)]
    write()
    text=hook_guardar.aviso_fin(row,ahora=review['at']+1000)
    assert 'desde la última revisión' in text,text
    assert 'se cambiaron 5 archivos' in text,text
    recorded.assert_called_once()
'''
        result = subprocess.run([sys.executable, '-B', '-c', script], env=dict(os.environ,
            CASE_ROOT=str(self.base), CEREBRO_CONFIG=str(config), HOME=str(self.base / 'home'),
            SYNOPSIS_DATA=str(self.base / 'data'), CLAUDE_PLUGIN_DATA=str(self.base / 'data'),
            CLAUDE_PLUGIN_OPTION_SERVIR_CONTEXTO='true', PYTHONPATH=str(ROOT / 'engine')),
            capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
