"""Autonomous inference, durable receipts and failure states without trusting drafts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'engine'))
from auto_review import ReviewQueue, provider_for
from memory_store import digest
from evidence_guard import attested_memory
from model_provider import ProviderError


class Transport:
    def __init__(self,fn): self.fn=fn;self.calls=[]
    def complete(self,system,request,cwd):
        self.calls.append(request)
        return self.fn(request)


def save_user(request,filename='retention'):
    source=request['evidence']['sources'][0]
    return dict(outcome='saved',reason='Durable user decision',actions=[dict(filename=filename,support=[dict(source=source['id'],quote=source['text'])])])


class AutoReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.project=self.base/'repo';self.project.mkdir()
        self.folder=self.base/'memory';self.queue=ReviewQueue(self.folder,self.project)
        self.turn=self.queue.cycle.begin('session','Keep records for 90 days.','event')['turn']

    def enqueue(self,prompt='Keep records for 90 days.',assistant='I completed the changes.'):
        self.queue.remember(self.turn,'session',prompt,'codex','event')
        self.queue.stop('session',assistant,'event')

    def test_saves_without_primary_model_memory_tool_and_verifies_receipt(self):
        self.enqueue();transport=Transport(save_user)
        self.assertTrue(self.queue.process_one(transport))
        result=self.queue.status()[0]
        self.assertEqual(result['state'],'complete')
        self.assertEqual(result['result']['receipt']['status'],'saved')
        receipt=result['result']['actions'][0]['receipt']
        path=Path(receipt['path'])
        self.assertEqual(digest(path.read_text()),receipt['sha256'])
        self.assertTrue(attested_memory(self.folder,path,receipt['sha256'],self.project))
        self.assertNotIn('I completed',path.read_text())
        with self.queue.database() as db:
            self.assertIsNone(db.execute('SELECT payload FROM reviews').fetchone()[0])
        self.assertFalse(self.queue.process_one(transport));self.assertEqual(len(transport.calls),1)

    def test_stop_replay_is_idempotent(self):
        self.enqueue();self.queue.stop('session','Repeated','event')
        self.queue.process_one(Transport(save_user))
        self.queue.stop('session','Repeated','event')
        self.assertEqual(len(self.queue.cycle.store.history('retention')),1)

    def test_no_change_requires_successful_review(self):
        self.enqueue();self.queue.process_one(Transport(lambda _:dict(outcome='no_change',reason='Task chatter',actions=[])))
        self.assertEqual(self.queue.cycle.status(self.turn)['turns'][0]['status'],'no_change')
        self.assertEqual(list(self.folder.glob('retention.md')),[])

    def test_provider_failure_does_not_close_turn_or_save_memory(self):
        self.enqueue()
        def unavailable(_):raise ProviderError('failure')
        self.queue.process_one(Transport(unavailable))
        self.assertEqual(self.queue.status()[0]['state'],'waiting_for_provider')
        self.assertEqual(self.queue.cycle.status(self.turn)['turns'][0]['status'],'open')

    def test_fabricated_assistant_claim_cannot_be_used_as_support(self):
        self.enqueue(assistant='Retention is 900 days.')
        def fabricate(req):
            response=save_user(req);response['actions'][0]['support'][0]['quote']='Retention is 900 days.'
            return response
        self.queue.process_one(Transport(fabricate))
        self.assertEqual(self.queue.status()[0]['state'],'conflict')
        self.assertFalse((self.folder/'retention.md').exists())

    def test_recognized_secrets_are_rejected_before_inference_or_spooling(self):
        self.enqueue(prompt='api_key=superprivatevalue')
        self.assertEqual(self.queue.status()[0]['state'],'rejected')
        with self.queue.database() as db:
            self.assertIsNone(db.execute('SELECT payload FROM reviews').fetchone()[0])

    def test_oversized_prompt_is_rejected_without_truncating_qualifications(self):
        self.enqueue(prompt='x'*10001)
        self.assertEqual(self.queue.status()[0]['state'],'rejected')

    def test_generation_does_not_close_newer_prompt(self):
        self.queue.remember(self.turn,'session','Keep records for 90 days.','codex','event')
        other=self.queue.cycle.begin('session','Second prompt','other')['turn']
        self.queue.remember(other,'session','Second prompt','codex','other')
        self.assertEqual(self.queue.stop('session','First reply','event'),self.turn)
        states={r['turn']:r['state'] for r in self.queue.status()}
        self.assertEqual(states[other],'awaiting_stop')

    def test_expiry_erases_payload_and_leaves_cycle_open(self):
        self.enqueue()
        with self.queue.database() as db,db:db.execute('UPDATE reviews SET created=?',(time.time()-90000,))
        self.assertEqual(self.queue.status()[0]['state'],'expired')
        self.assertEqual(self.queue.cycle.status(self.turn)['turns'][0]['status'],'open')

    def test_live_lease_prevents_two_workers_claiming_same_job(self):
        self.enqueue();self.assertIsNotNone(self.queue.claim())
        self.assertIsNone(ReviewQueue(self.folder,self.project).claim())

    def test_abandoned_lease_can_be_recovered(self):
        self.enqueue();self.queue.claim()
        with self.queue.database() as db,db:db.execute('UPDATE reviews SET lease=0')
        self.assertTrue(self.queue.process_one(Transport(save_user)))
        self.assertEqual(self.queue.status()[0]['state'],'complete')

    def test_recovers_applied_operations_without_second_inference(self):
        self.enqueue()
        from evidence_guard import EvidenceLedger,EvidenceAdmission
        ledger=EvidenceLedger(self.project,self.folder);ledger.user('Keep records for 90 days.')
        request=dict(evidence=ledger.packet());actions=ledger.admit(save_user(request)['actions'])
        self.queue.cycle.queue(self.turn,actions,admission=EvidenceAdmission(ledger.admissions))
        self.queue.cycle.resume(self.turn)
        transport=Transport(lambda _:self.fail('Must recover without inference'))
        self.queue.process_one(transport)
        self.assertEqual(self.queue.status()[0]['state'],'complete')
        self.assertEqual(len(self.queue.cycle.store.history('retention')),1)

    def test_file_evidence_can_back_new_memory_but_tools_are_bounded(self):
        self.enqueue();(self.project/'policy.md').write_text('Durable justification from project review.')
        def review(req):
            if not req['evidence_round_complete']:
                return dict(evidence_requests=[dict(tool='read_file',path='policy.md',start=1,end=1)])
            source=req['evidence']['sources'][1]
            return dict(outcome='saved',reason='Relevant finding',actions=[dict(filename='rationale',support=[dict(source=source['id'],quote=source['text'])])])
        transport=Transport(review);self.queue.process_one(transport)
        self.assertEqual(self.queue.status()[0]['state'],'complete');self.assertEqual(len(transport.calls),2)

    def test_forbidden_evidence_tool_never_executes(self):
        self.enqueue();self.queue.process_one(Transport(lambda _:dict(evidence_requests=[dict(tool='shell',command='touch forbidden')])) )
        self.assertEqual(self.queue.status()[0]['state'],'conflict')
        self.assertFalse((self.project/'forbidden').exists())

    def test_conflicts_remain_pending_in_native_cycle(self):
        self.enqueue();self.queue.process_one(Transport(lambda _:dict(outcome='conflict',reason='Contradictory facts',actions=[])))
        self.assertEqual(self.queue.status()[0]['state'],'conflict')
        self.assertEqual(self.queue.cycle.status(self.turn)['turns'][0]['status'],'open')

    def test_native_worker_runs_in_detached_process_with_inherited_provider(self):
        self.enqueue();binary=self.base/'bin';binary.mkdir();fake=binary/'codex'
        fake.write_text('#!'+sys.executable+'\nimport json,sys,os\nassert os.environ["SYNOPSIS_CONTROLLED_RUN"]=="1"\nr=json.loads(sys.stdin.read().split("INPUT JSON:\\n",1)[1])\ns=r["evidence"]["sources"][0]\nresponse=dict(outcome="saved",reason="Durable",actions=[dict(filename="retention",support=[dict(source=s["id"],quote=s["text"])])])\nprint(json.dumps(dict(type="item.completed",item=dict(type="agent_message",text=json.dumps(response)))))\n')
        fake.chmod(0o755)
        env={**os.environ,'PATH':str(binary)+os.pathsep+os.environ['PATH']}
        process=subprocess.run([sys.executable,'-I','-S',str(ROOT/'engine/auto_review.py'),str(self.folder),str(self.project)],env=env,capture_output=True,text=True,timeout=20)
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertEqual(self.queue.status()[0]['state'],'complete')

    def test_provider_routing_never_sends_cursor_transcript_to_unrelated_cli(self):
        with patch('auto_review.shutil.which',return_value='/bin/codex'),patch('auto_review.ollama_models',return_value=[]),patch.dict(os.environ,{},clear=True):
            with self.assertRaises(ProviderError):provider_for('cursor')
            self.assertEqual(provider_for('codex'),('codex',None))

    def test_sensitive_assistant_context_rejected_before_send(self):
        self.enqueue(assistant='password=veryprivatevalue')
        self.assertEqual(self.queue.status()[0]['state'],'rejected')

    def test_primary_no_change_receives_independent_source_bound_review(self):
        self.enqueue();self.queue.cycle.close(self.turn,'no_change','Already reviewed')
        transport=Transport(save_user)
        self.queue.process_one(transport)
        self.assertEqual(len(transport.calls),1)
        receipt=self.queue.status()[0]['result']['receipt']
        self.assertEqual(receipt['status'],'saved')
        self.assertNotEqual(receipt['turn'],self.turn)
        self.assertEqual(self.queue.cycle.status(self.turn)['turns'][0]['status'],'no_change')


    def test_append_update_preserves_existing_note_and_revision(self):
        self.enqueue();self.queue.process_one(Transport(save_user))
        second=self.queue.cycle.begin('session','Keep backups for 7 days.','second')['turn']
        self.queue.remember(second,'session','Keep backups for 7 days.','codex','second')
        self.queue.stop('session','Completed','second')
        def update(req):
            if not req['evidence_round_complete']:
                return dict(evidence_requests=[dict(tool='memory_note',filename='retention')])
            user,old=req['evidence']['sources']
            return dict(outcome='saved',reason='Append supported decision',actions=[dict(filename='retention',overwrite=True,expected_revision=1,support=[dict(source=old['id'],quote=old['text'].strip()),dict(source=user['id'],quote=user['text'])])])
        self.queue.process_one(Transport(update))
        self.assertEqual(self.queue.status()[0]['state'],'complete')
        history=self.queue.cycle.store.history('retention')
        self.assertEqual(len(history),2)
        self.assertIn('90 days',history[-1]['text']);self.assertIn('7 days',history[-1]['text'])

    def test_duplicate_passage_closes_no_change_without_new_note(self):
        self.enqueue();self.queue.process_one(Transport(save_user))
        second=self.queue.cycle.begin('session','Keep records for 90 days.','second')['turn']
        self.queue.remember(second,'session','Keep records for 90 days.','codex','second')
        self.queue.stop('session','','second')
        self.queue.process_one(Transport(lambda req:save_user(req,'different-title')))
        self.assertEqual(self.queue.status()[0]['result']['receipt']['status'],'no_change')
        self.assertFalse((self.folder/'different-title.md').exists())

    def test_all_five_native_bridges_trigger_independent_background_review(self):
        binary=self.base/'bin';binary.mkdir();fake=binary/'codex'
        fake.write_text('#!'+sys.executable+'\nimport json,sys,os\nassert os.environ["SYNOPSIS_CONTROLLED_RUN"]=="1"\nr=json.loads(sys.stdin.read().split("INPUT JSON:\\n",1)[1])\ns=r["evidence"]["sources"][0]\nresponse=dict(outcome="saved",reason="Durable",actions=[dict(filename="retention",support=[dict(source=s["id"],quote=s["text"])])])\nprint(json.dumps(dict(type="item.completed",item=dict(type="agent_message",text=json.dumps(response)))))\n')
        fake.chmod(0o755)
        for directory,client in [('claude-code','claude'),('codex','codex'),('opencode','opencode'),('cursor','cursor'),('antigravity','antigravity')]:
            with self.subTest(client=client):
                home=self.base/client;home.mkdir();project=home/'repo';project.mkdir()
                config=home/'config.json';config.write_text(json.dumps(dict(fuentes=[],proyectos=[])))
                env={**os.environ,'HOME':str(home),'PATH':str(binary)+os.pathsep+os.environ['PATH'],
                     'CEREBRO_CONFIG':str(config),'SYNOPSIS_ROOT':str(ROOT/'engine'),'SYNOPSIS_DATA':str(home/'data'),
                     'CLAUDE_PLUGIN_DATA':str(home/'data'),'SYNOPSIS_AUTO_REVIEW':'1','SYNOPSIS_REVIEW_PROVIDER':'codex'}
                common=dict(cwd=str(project),session_id='session',prompt='Keep records for 90 days.')
                events=[dict(common,hook_event_name='UserPromptSubmit'),dict(common,hook_event_name='Stop',last_assistant_message='Completed')]
                if client=='cursor':
                    events[0].update(hook_event_name='beforeSubmitPrompt',conversation_id='session')
                    events[1].update(hook_event_name='stop',conversation_id='session')
                if client=='antigravity':
                    for event in events:event['conversationId']='session'
                for index,event in enumerate(events):
                    command=[sys.executable,str(ROOT/directory/'bridge.py')]
                    if client=='antigravity':command.append('PreInvocation' if index==0 else 'Stop')
                    result=subprocess.run(command,input=json.dumps(event),env=env,capture_output=True,text=True,timeout=30)
                    self.assertEqual(result.returncode,0,result.stderr)
                    self.assertNotIn('Synopsis cycle:',result.stderr)
                deadline=time.monotonic()+15
                found=[]
                while time.monotonic()<deadline:
                    found=list(home.rglob('retention.md'))
                    if found:break
                    time.sleep(.1)
                self.assertEqual(len(found),1,client+' did not save automatically')
                self.assertIn('90 days',found[0].read_text())

    def test_exhausted_abandoned_worker_can_recover_committed_actions(self):
        self.enqueue()
        from evidence_guard import EvidenceLedger,EvidenceAdmission
        ledger=EvidenceLedger(self.project,self.folder);ledger.user('Keep records for 90 days.')
        actions=ledger.admit(save_user(dict(evidence=ledger.packet()))['actions'])
        self.queue.cycle.queue(self.turn,actions,admission=EvidenceAdmission(ledger.admissions))
        self.queue.cycle.resume(self.turn)
        with self.queue.database() as db,db:
            db.execute("UPDATE reviews SET state='running',lease=0,attempts=3")
        self.queue.process_one(Transport(lambda _:self.fail('Must use durable receipt')))
        self.assertEqual(self.queue.status()[0]['state'],'complete')
        self.assertEqual(len(self.queue.cycle.store.history('retention')),1)

    def test_three_provider_failures_can_be_retried_before_expiry(self):
        self.enqueue()
        def failed(_):raise ProviderError('transient_failure')
        for _ in range(3):
            with self.queue.database() as db,db:db.execute('UPDATE reviews SET available=0')
            self.queue.process_one(Transport(failed))
        self.assertEqual(self.queue.status()[0]['state'],'failed')
        with self.queue.database() as db:self.assertIsNotNone(db.execute('SELECT payload FROM reviews').fetchone()[0])
        self.queue.retry();self.queue.process_one(Transport(save_user))
        self.assertEqual(self.queue.status()[0]['state'],'complete')
        self.assertEqual(len(self.queue.cycle.store.history('retention')),1)

    def test_relevant_note_after_budget_filling_noise_is_still_selected(self):
        for i in range(5):
            name='aaa-'+str(i)
            self.queue.cycle.store.save(filename=name,name=name,description='Unrelated',kind='project',content=str(i)+' '+('x'*2400),index_line='- ['+name+']('+name+'.md)',source='fixture')
        self.queue.cycle.store.save(filename='zzz-retention',name='policy',description='Retention',kind='project',content='Keep records for 90 days.',index_line='- [policy](zzz-retention.md)',source='fixture')
        inventory=self.queue.inventory('records retention days')
        self.assertIn('zzz-retention',[n['filename'] for n in inventory])

    def test_independent_review_of_saved_primary_is_idempotent(self):
        self.enqueue();self.queue.cycle.queue(self.turn,[dict(filename='retention',name='retention',description='policy',kind='project',content='Keep records for 90 days.',index_line='- [retention](retention.md)',source='fixture')])
        self.queue.cycle.resume(self.turn);self.queue.cycle.close(self.turn,'saved')
        self.queue.process_one(Transport(save_user))
        self.assertEqual(self.queue.status()[0]['state'],'complete')
        self.assertEqual(len(self.queue.cycle.store.history('retention')),1)

    def test_automatic_experience_capture_observes_file_but_not_assistant_claim(self):
        self.enqueue(assistant='Everything has been tested in production.')
        (self.project/'policy.json').write_text('{"retain":true}')
        # Populate the observed path before Stop, as a native tool event would do.
        with self.queue.database() as db,db:db.execute("UPDATE reviews SET state='awaiting_stop'")
        self.queue.track('session',dict(tool_input=dict(file_path=str(self.project/'policy.json'))))
        self.queue.stop('session','Everything has been tested in production.','event')
        def propose(req):
            source=next(s for s in req['evidence']['sources'] if s['kind']=='project_file')
            experience=dict(situation='Transient retry exhausted.',action='Retain work.',rationale='Allow recovery.',outcome='Configuration retains work.',limitations='No recovery experiment was observed.',when=dict(paths=['src/queue.py'],keywords=['retry'],conditions=[]),checks=[dict(kind='json_equals',path='policy.json',pointer='/retain',expected=True)],evidence=[dict(path='policy.json',sha256=source['sha256'])])
            return dict(outcome='no_change',reason='Experience only',actions=[],experiences=[dict(name='retry-recovery',experience=experience)])
        self.queue.process_one(Transport(propose))
        result=self.queue.status()[0]
        self.assertEqual(result['state'],'complete')
        self.assertEqual(len(result['result']['experiences']),1)
        from experience_engine import ExperienceStore
        store=ExperienceStore(self.folder,self.project)
        self.assertEqual(store.verify('retry-recovery')['state'],'observed_support')
        self.assertNotIn('production',json.dumps(store.versions()))

    def test_track_does_not_capture_commands_or_tool_output(self):
        self.queue.remember(self.turn,'session','Keep records for 90 days.','codex','event')
        file=self.project/'policy.md';file.write_text('Retention policy')
        self.queue.track('session',dict(tool_input=dict(file_path=str(file),command='DO NOT STORE'),tool_response='PRIVATE OUTPUT'))
        with self.queue.database() as db:payload=db.execute('SELECT payload FROM reviews').fetchone()[0]
        self.assertIn('policy.md',payload);self.assertNotIn('PRIVATE OUTPUT',payload);self.assertNotIn('DO NOT STORE',payload)

    def test_experience_schema_gets_one_bounded_repair_without_inventing_sources(self):
        self.enqueue()
        file=self.project/'policy.json';file.write_text('{"retain":true}')
        with self.queue.database() as db,db:db.execute("UPDATE reviews SET state='awaiting_stop'")
        self.queue.track('session',dict(tool_input=dict(file_path=str(file))));self.queue.stop('session','','event')
        def respond(req):
            if req['protocol']=='synopsis.experience-repair.v1':
                proposals=req['experiences'];proposals[0]['experience']['when']['conditions']=[]
                return dict(experiences=proposals)
            source=next(s for s in req['evidence']['sources'] if s['kind']=='project_file')
            data=dict(situation='Retry failures.',action='Preserve pending work.',rationale='Allow retry.',outcome='Configuration observed.',limitations='No recovery experiment; Python scope untested.',when=dict(paths=['src/queue.py'],keywords=['retry'],conditions=['Python only']),checks=[dict(kind='json_equals',path='policy.json',pointer='/retain',expected=True)],evidence=[dict(path='policy.json',sha256=source['sha256'])])
            return dict(outcome='no_change',reason='Experience only',actions=[],experiences=[dict(name='retry-experiment',experience=data)])
        transport=Transport(respond);self.queue.process_one(transport)
        self.assertEqual(len(transport.calls),2);self.assertEqual(self.queue.status()[0]['state'],'complete')

if __name__=='__main__':unittest.main()
