"""Local runtime boundaries and one-step installer contracts, without downloads in tests."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'engine'))
from local_semantics import private_json,LocalEmbeddings
import local_semantics
import semantic_setup

class LocalSemanticTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)/'semantic'
        self.env=patch.dict(os.environ,{'SYNOPSIS_SEMANTIC_HOME':str(self.base),'SYNOPSIS_SEMANTIC_SETUP':'auto'})
        self.env.start();self.addCleanup(self.env.stop)

    def test_dry_run_download_plan_creates_nothing(self):
        self.assertEqual(semantic_setup.setup(dry_run=True)['state'],'planned')
        self.assertFalse(self.base.exists())

    def test_private_endpoint_receipt_is_owner_only_and_symlinks_rejected(self):
        path=self.base/'worker.json';private_json(path,dict(token='fixture'))
        if os.name=='posix':self.assertEqual(path.stat().st_mode&0o777,0o600)
        path.unlink();outside=Path(self.temp.name)/'outside';outside.write_text('unchanged');path.symlink_to(outside)
        with self.assertRaises(ValueError):private_json(path,dict(token='replacement'))
        self.assertEqual(outside.read_text(),'unchanged')

    def test_input_limits_apply_before_worker_start(self):
        backend=LocalEmbeddings(dict(identity='fixture'))
        with patch.object(backend,'ensure') as start:
            for texts in ([],['a']*65,[''],[7],['a'*6001]):
                with self.assertRaises(ValueError):backend(texts)
        start.assert_not_called()

    def test_endpoint_cannot_target_arbitrary_ports_or_missing_auth(self):
        backend=LocalEmbeddings(dict(identity='fixture'))
        for state in (dict(port=80,token='x'*40),dict(port=True,token='x'*40),dict(port=9000,token='short')):
            with self.assertRaises(ValueError):backend._request(state,['private input'])

    def test_proxy_environment_is_not_used_for_private_text(self):
        backend=LocalEmbeddings(dict(identity='fixture'))
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,size):return b'{"identity":"fixture","vectors":[[1,0]]}'
        class Opener:
            def open(self,request,timeout):
                self.request=request
                assert request.full_url.startswith('http://127.0.0.1:')
                return Response()
        with patch('local_semantics.urllib.request.ProxyHandler') as proxy,patch('local_semantics.urllib.request.build_opener',return_value=Opener()):
            backend._request(dict(port=9000,token='x'*40),['private input'])
        proxy.assert_called_once_with({})

    def test_changed_model_assets_are_rejected_before_loading(self):
        from semantic_worker import serve
        self.base.mkdir()
        (self.base/'model.onnx').write_text('corrupt')
        (self.base/'manifest.json').write_text(json.dumps(dict(assets={'model.onnx':'not-the-hash'},identity='fixture')))
        with patch('semantic_worker.load') as load:
            with self.assertRaises(ValueError):serve(self.base)
        load.assert_not_called()

    def test_existing_runtime_reuses_model_without_pip(self):
        self.base.mkdir()
        with patch('local_semantics.manifest',return_value=dict(identity='fixture')),patch('local_semantics.LocalEmbeddings') as backend,patch('semantic_setup.subprocess.run') as run:
            result=semantic_setup.setup()
        self.assertTrue(result['ready']);run.assert_not_called();backend.assert_called_once()

    def test_installer_prepares_semantics_by_default_and_allows_offline_opt_out(self):
        main=runpy.run_path(str(ROOT/'bin/synopsis'))['main']
        for extra,expected in (([],1),(['--no-semantic'],0)):
            with self.subTest(extra=extra),patch.object(sys,'argv',['synopsis','install','codex','--no-service',*extra]),patch('subprocess.run',return_value=type('Result',(),dict(returncode=0,stdout='',stderr=''))()),patch('comun.instalar_comando'),patch('integration_health.check',return_value=dict(ready=True)),patch('semantic_setup.setup',return_value=dict(state='ready',ready=True)) as setup,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(),0)
                self.assertEqual(setup.call_count,expected)

if __name__=='__main__':unittest.main()
