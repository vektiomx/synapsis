"""A valid local Markdown link need not belong to the indexed graph."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class ExternalLinksTest(unittest.TestCase):
    def test_unindexed_targets_are_checked_without_importing_their_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = base / 'config.json'
            config.write_text(json.dumps({'usuario': 'Test', 'fuentes': [], 'proyectos': []}))
            script = r'''
import os
from pathlib import Path
from unittest.mock import patch
import cerebro
base = Path(os.environ['CASE_ROOT'])
memory = base / 'memory'
memory.mkdir()
external = base / 'docs' / 'guía externa.md'
external.parent.mkdir()
external.write_text('This content must not be loaded or added to the graph.')
node = {'ruta': str(memory / 'index.md'), 'grupo': 'memory'}
graph = cerebro.Cerebro.__new__(cerebro.Cerebro)
graph.por_id = {'origin': node}
graph.por_ruta = {}
graph.rotos = []
graph.rotos_vistos = set()
graph.agregar = lambda *args: (_ for _ in ()).throw(AssertionError('Unexpected graph edge'))
text = ('[relative](../docs/gu%C3%ADa%20externa.md#section)\n'
        + '[absolute](<' + str(external) + '>)\n'
        + '[missing](../docs/missing.md)\n'
        + '[directory](../docs/folder.md)\n')
(external.parent / 'folder.md').mkdir()
with patch.object(Path, 'read_text', side_effect=AssertionError('Must not read external content')):
    graph.analizar_enlaces('origin', text, [])
assert [x['destino'] for x in graph.rotos] == ['../docs/missing.md', '../docs/folder.md'], graph.rotos
assert graph.por_id == {'origin': node}
assert graph.por_ruta == {}
graph.por_ruta[cerebro.normalizar(str(external))] = 'indexed'
edges = []
graph.agregar = lambda *args: edges.append(args)
graph.analizar_enlaces('origin', '[existing](../docs/gu%C3%ADa%20externa.md)', [])
assert len(edges) == 1 and edges[0][1] == 'indexed', edges
'''
            result = subprocess.run([sys.executable, '-B', '-c', script],
                                    env=dict(os.environ, CEREBRO_CONFIG=str(config),
                                             CLAUDE_PLUGIN_DATA=tmp, CASE_ROOT=tmp,
                                             PYTHONPATH=str(ROOT / 'engine')),
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
