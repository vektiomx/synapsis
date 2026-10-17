import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent


class GuardSurfacesTest(unittest.TestCase):
    def test_adversarial_process_scenarios(self):
        report=runpy.run_path(str(ROOT/'tools/evaluate_guard.py'))['evaluate']()
        self.assertTrue(report['passed'],json.dumps(report,ensure_ascii=False))
        self.assertEqual(report['cases'],10)

    def test_native_mcp_has_an_actual_source_bound_answer_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            project=root/'project';project.mkdir()
            (project/'settings.json').write_text('{"ttl":389}')
            cfg=root/'config.json';cfg.write_text(json.dumps(dict(usuario='QA',fuentes=[],proyectos=[])))
            env=dict(os.environ,HOME=str(root),SYNOPSIS_ROOT=str(ROOT/'engine'),SYNOPSIS_DATA=str(root/'state'),
                     CLAUDE_PLUGIN_DATA=str(root/'state'),CEREBRO_CONFIG=str(cfg),PYTHONDONTWRITEBYTECODE='1')
            requests=[dict(jsonrpc='2.0',id=1,method='tools/list'),dict(jsonrpc='2.0',id=2,method='tools/call',params=dict(name='responder_con_evidencia',
                arguments=dict(proyecto=str(project),fuentes=[dict(tool='json_value',path='settings.json',pointer='/ttl')])))]
            result=subprocess.run([sys.executable,'-B',str(ROOT/'mcp_entry.py')],input=''.join(json.dumps(r)+'\n' for r in requests),
                                  text=True,capture_output=True,env=env,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            replies=[json.loads(line) for line in result.stdout.splitlines()]
            self.assertIn('responder_con_evidencia',{t['name'] for t in replies[0]['result']['tools']})
            structured=replies[1]['result']['structuredContent']
            self.assertEqual(structured['verification']['status'],'evidence_bound')
            self.assertIn('/ttl = 389',structured['answer'])
