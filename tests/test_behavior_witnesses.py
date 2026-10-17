"""External-oracle and isolated-bootstrap contracts for behavioral memory."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'engine'))
from behavior_runner import run_calls, calls_spec
from experience_runner import run_python_test


class BehaviorRunnerTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.descriptor=dict(path='policy.py',symbol='policy')
        (self.root/'policy.py').write_text('def policy(context):\n if context["fail"]: raise ValueError("bounded")\n return context["value"] * 2\n')

    def test_calls_reject_escape_nonfinite_and_extra_oracle_data(self):
        calls=[dict(args=[dict(fail=False,value=3)],kwargs={})]
        for descriptor,data in ((dict(path='../policy.py',symbol='policy'),calls),
            (self.descriptor,[dict(args=[float('nan')],kwargs={})]),
            (self.descriptor,[dict(args=[],kwargs={},expected=3)])):
            with self.assertRaises(ValueError):calls_spec(descriptor,data)

    @unittest.skipUnless(sys.platform=='linux' and shutil.which('bwrap'),'requires isolated Linux runner')
    def test_returns_values_and_exception_types_never_a_self_reported_pass(self):
        calls=[dict(args=[dict(fail=False,value=3)],kwargs={}),dict(args=[dict(fail=True)],kwargs={})]
        result=run_calls(self.root,self.descriptor,calls)
        self.assertEqual(result['status'],'observed',result)
        self.assertEqual(result['results'],[dict(value=6),dict(raises='ValueError')])
        self.assertNotIn('passed',result)
        self.assertEqual((self.root/'policy.py').read_text().splitlines()[0],'def policy(context):')

    @unittest.skipUnless(sys.platform=='linux' and shutil.which('bwrap'),'requires isolated Linux runner')
    def test_project_cannot_shadow_the_trusted_resource_bootstrap(self):
        (self.root/'resource.py').write_text('raise RuntimeError("untrusted bootstrap module")')
        result=run_calls(self.root,self.descriptor,[dict(args=[dict(fail=False,value=4)],kwargs={})])
        self.assertEqual(result['status'],'observed',result)
        self.assertEqual(result['results'],[dict(value=8)])
        tests=self.root/'tests';tests.mkdir();(tests/'__init__.py').write_text('')
        (tests/'test_policy.py').write_text('import unittest\nclass Policy(unittest.TestCase):\n def test_real(self): self.assertEqual(2+2,4)\n')
        observed=run_python_test(self.root,dict(kind='python_unittest',path='tests/test_policy.py',case='Policy.test_real'))
        self.assertEqual(observed['status'],'observed_support',observed)


from behavior_memory import BehaviorMemory, literal_assertions
from experience_engine import ExperienceStore

@unittest.skipUnless(sys.platform=='linux' and shutil.which('bwrap'),'requires isolated Linux runner')
class BehaviorMemoryTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'repo';self.root.mkdir()
        self.source=self.root/'policy.py';self.source.write_text('def policy(context):\n return 43 if context["flag"] else 71\n')
        tests=self.root/'tests';tests.mkdir();(tests/'__init__.py').write_text('')
        self.test=tests/'test_policy.py'
        self.test.write_text('import unittest\nfrom policy import policy\nclass Policy(unittest.TestCase):\n def test_modes(self):\n  self.assertEqual(policy({"flag":True}),43)\n  self.assertEqual(policy({"flag":False}),71)\n')
        self.checks=[dict(kind='python_unittest',path='tests/test_policy.py',case='Policy.test_modes')]
        self.descriptor=dict(path='policy.py',symbol='policy')
        self.store=ExperienceStore(Path(self.temp.name)/'memory',self.root);self.memory=BehaviorMemory(self.store)

    def capture(self):return self.memory.capture(self.descriptor,self.checks,'fixture:declared-and-observed')

    def test_literal_capture_requires_actual_function_to_match_declared_test(self):
        records,unsupported=literal_assertions(self.root,self.descriptor,self.checks)
        self.assertEqual(len(records),2);self.assertEqual(unsupported,0)
        self.source.write_text('def policy(context):\n return 0\n')
        self.assertFalse(self.capture()['captured']);self.assertEqual(self.memory.rows(),[])

    def test_witness_survives_lost_test_and_detects_changed_implementation(self):
        receipt=self.capture();self.assertTrue(receipt['captured'])
        self.assertTrue(self.capture()['replayed'])
        self.test.unlink()
        self.source.write_text('def policy(context):\n return 43\n')
        report=self.memory.verify(receipt['id'])
        self.assertEqual(report['state'],'contradicted');self.assertEqual(report['matches'],[True,False])
        self.assertFalse(self.test.exists())

    def test_current_explicit_assertion_can_supersede_old_test_without_erasing_it(self):
        receipt=self.capture();self.test.write_text(self.test.read_text().replace('),43', '),99'))
        report=self.memory.verify(receipt['id'])
        self.assertEqual(report['state'],'superseded_by_current_assertion');self.assertFalse(report['executed'])
        self.assertEqual(len(self.memory.rows()[0]['data']['records']),2)

    def test_new_test_file_can_replace_old_observation(self):
        receipt=self.capture();self.test.unlink()
        (self.root/'tests'/'test_new_contract.py').write_text('import unittest\nfrom policy import policy\nclass Contract(unittest.TestCase):\n def test_replacement(self):\n  self.assertEqual(policy({"flag":True}),99)\n')
        self.assertEqual(self.memory.verify(receipt['id'])['state'],'superseded_by_current_assertion')

    def test_scope_revision_and_guard_change_suspend_replay(self):
        from memory_store import digest
        from experience_timeline import ExperienceTimeline
        (self.root/'context.json').write_text('{"mode":"legacy"}')
        (self.root/'contract.txt').write_text('Legacy policy is active.')
        data=dict(situation='Mode policy',action='Preserve observed modes',rationale='Compatibility is explicit.',outcome='Declared cases observed.',limitations='Only literal JSON inputs.',
            when=dict(paths=['policy.py'],keywords=['policy'],conditions=[dict(kind='json_equals',path='context.json',pointer='/mode',expected='legacy')]),
            checks=[dict(kind='text_contains',path='contract.txt',text='active')],evidence=[dict(path=path,sha256=digest((self.root/path).read_text())) for path in ('contract.txt','context.json')])
        self.store.save('mode-policy',data,'fixture:policy');row=self.store.latest('mode-policy')
        receipt=self.memory.capture(self.descriptor,self.checks,'fixture:scoped',scopes=[dict(name=row['name'],revision=row['revision'],experience_sha256=row['sha256'])])
        self.assertTrue(receipt['captured'])
        (self.root/'context.json').write_text('{"mode":"new"}')
        self.assertEqual(self.memory.verify(receipt['id'])['state'],'scope_unobserved')
        (self.root/'context.json').write_text('{"mode":"legacy"}')
        (self.root/'contract.txt').write_text('Legacy policy has changed.')
        self.assertEqual(self.memory.verify(receipt['id'])['state'],'policy_changed')
        ExperienceTimeline(self.store).change('mode-policy','retired','Contract withdrawn','fixture:user',1)
        self.assertEqual(self.memory.verify(receipt['id'])['state'],'scope_revised_or_retired')

    def test_self_reported_pass_flag_is_never_an_oracle(self):
        receipt=self.capture();self.test.unlink()
        self.source.write_text('def policy(context):\n return {"passed": True}\n')
        self.assertEqual(self.memory.verify(receipt['id'])['state'],'contradicted')

    def test_interface_change_and_retirement_require_reconciliation(self):
        receipt=self.capture();self.source.write_text('def policy(context,required):\n return 43\n')
        self.assertEqual(self.memory.verify(receipt['id'])['state'],'incompatible_interface')
        self.memory.retire(receipt['id'],'Intentional contract replacement','user:test',0)
        self.assertEqual(self.memory.verify(receipt['id'])['state'],'retired')
        with self.assertRaises(ValueError):self.memory.retire(receipt['id'],'Again','user:test',0)

    def test_conditional_or_foreign_assertion_is_not_archived(self):
        self.test.write_text('import unittest\nfrom policy import policy\nclass Policy(unittest.TestCase):\n def test_modes(self):\n  if False:\n   self.assertEqual(policy({"flag":True}),999)\n')
        self.assertEqual(literal_assertions(self.root,self.descriptor,self.checks)[0],[])

    def test_prompt_context_discovers_witness_without_execution(self):
        from task_context import build
        receipt=self.capture()
        with patch('behavior_memory.run_calls') as execute:
            packet=build(self.store,'policy compatibility',active_path='policy.py')
        execute.assert_not_called()
        self.assertEqual(packet['witnesses'][0]['id'],receipt['id'])
        self.assertFalse(packet['abstained'])
        self.assertEqual(packet['used'],len(json.dumps(packet,sort_keys=True,ensure_ascii=False)))

    def test_mcp_inspection_cannot_trigger_witness_execution(self):
        import conector_mcp
        receipt=self.capture()
        with patch.object(conector_mcp,'carpeta_memoria_de',return_value=self.store.folder),patch('behavior_memory.run_calls') as execute:
            report=conector_mcp.experiencias(dict(proyecto=str(self.root),operacion='verify-witness',testigo=receipt['id']))
        execute.assert_not_called();self.assertFalse(report['executed'])
        self.assertEqual(report['state'],'needs_replay')

    def test_missing_identity_and_invalid_capture_descriptor_are_rejected(self):
        self.capture()
        with self.assertRaises(ValueError):self.memory.verify(None)
        with self.assertRaises(ValueError):self.memory.capture(dict(path=None,symbol=None),self.checks,'fixture')

    def test_unrelated_recent_history_cannot_hide_a_callable_witness(self):
        from memory_store import digest
        from experience_engine import encoded
        from research_workbench import ResearchWorkbench
        receipt=self.capture();row=self.memory.rows()[0]
        with self.store.database() as db:
            with db:
                for index in range(105):
                    path='other_'+str(index)+'.py';data=dict(row['data'],callable=dict(path=path,symbol='other'));raw=encoded(data)
                    db.execute('INSERT INTO behavior_capsules VALUES(?,?,?,?,?,?,?,?,?)',(self.store.project,digest(str(index)),path,'other',raw,digest(raw),'active',0,row['created']))
        prepared=ResearchWorkbench(self.store).prepare('policy compatibility')
        self.assertEqual(prepared['behavior_witnesses'][0]['id'],receipt['id'])

    def test_workbench_repairs_forgotten_behavior_and_rejects_new_regression(self):
        from research_workbench import ResearchWorkbench
        from memory_store import digest
        receipt=self.capture()
        self.test.write_text('import unittest\nfrom policy import policy\nclass Policy(unittest.TestCase):\n def test_extension(self):\n  self.assertEqual(policy({"emergency":True}),-1)\n')
        original='def policy(context):\n if context.get("emergency"): return -1\n return 0\n'
        self.source.write_text(original)
        check=dict(kind='python_unittest',path='tests/test_policy.py',case='Policy.test_extension')
        candidate=lambda text:dict(title='Compatibility experiment',hypothesis='Restore historical cases and preserve the extension.',patches=[dict(**self.descriptor,sha256=digest(original),source=text)],tests=[check])
        good='def policy(context):\n if context.get("emergency"): return -1\n return 43 if context["flag"] else 71\n'
        bad='def policy(context):\n if context.get("emergency"): return 42\n return 43 if context["flag"] else 71\n'
        report=ResearchWorkbench(self.store).run('policy compatibility',execute=True,proposal=dict(candidates=[candidate(good),candidate(bad)]))
        self.assertEqual([c['state'] for c in report['candidates']],['observed_improvement','regression'])
        self.assertEqual(report['candidates'][0]['behavior_observations'][0]['id'],receipt['id'])
        self.assertEqual(report['candidates'][0]['behavior_observations'][0]['candidate']['state'],'observed_support')
        self.assertEqual(self.source.read_text(),original)

if __name__=='__main__':unittest.main()
