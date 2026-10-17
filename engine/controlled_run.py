"""Vendor-neutral execution protocol with memory reconciliation before answer release."""
import json
import os
import signal
import sqlite3
import subprocess
import threading
import time
import copy
import math
from pathlib import Path

from memory_cycle import MemoryCycle, contract, project_path, validate_closure
from conector_mcp import carpeta_memoria_de

PROTOCOL = 'synopsis.run.v2'
MAX_OUTPUT = 256 * 1024


class RunError(ValueError):
    def __init__(self, code, turn=None, status=None):
        super().__init__(code)
        self.code, self.turn, self.status = code, turn, status


def process_text(command, prompt, cwd, timeout=120, env=None):
    """User-supplied adapter: one JSON request on stdin, one JSON response on stdout."""
    if not isinstance(command, list) or not command or any(not isinstance(part, str) or not part for part in command):
        raise ValueError('Indica el ejecutable del adaptador y sus argumentos después de --.')
    if type(timeout) is not int or not 1 <= timeout <= 600:
        raise ValueError('El timeout debe estar entre 1 y 600 segundos.')
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               cwd=cwd, env=env, start_new_session=os.name != 'nt')
    buffers, failures = {}, []

    def stop():
        try:
            if os.name == 'nt':
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    def read(label, stream, limit):
        data = bytearray()
        try:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                if len(data) + len(chunk) > limit:
                    failures.append('adapter_output_limit')
                    stop()
                    break
                data.extend(chunk)
        finally:
            stream.close()
            buffers[label] = bytes(data)

    def write():
        try:
            process.stdin.write(prompt.encode('utf-8'))
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    threads = [threading.Thread(target=read, args=('stdout', process.stdout, MAX_OUTPUT), daemon=True),
               threading.Thread(target=read, args=('stderr', process.stderr, 65536), daemon=True),
               threading.Thread(target=write, daemon=True)]
    for thread in threads:
        thread.start()
    try:
        process.wait(timeout=timeout)
        for thread in threads:
            thread.join(timeout=2)
        if any(thread.is_alive() for thread in threads):
            stop()
            raise RunError('adapter_stream_incomplete')
        if failures:
            raise RunError(failures[0])
        if process.returncode:
            diagnostic = (buffers.get('stdout', b'') + buffers.get('stderr', b'')).decode('utf-8', errors='replace').lower()
            if 'subscription is required' in diagnostic:
                raise RunError('provider_subscription_required')
            if 'free tier can only be used' in diagnostic:
                raise RunError('provider_usage_restricted')
            raise RunError('adapter_failed')
        try:
            return buffers['stdout'].decode('utf-8')
        except (ValueError, UnicodeError, KeyError) as error:
            raise RunError('adapter_invalid_json') from error
    except subprocess.TimeoutExpired as error:
        stop()
        process.wait()
        raise RunError('adapter_timeout') from error
    finally:
        if process.poll() is None:
            stop()
            process.wait()
        for thread in threads:
            thread.join(timeout=2)


def command_transport(command, request, timeout=120):
    raw = process_text(command, json.dumps(request, ensure_ascii=False), request['project'], timeout)
    try:
        return json.loads(raw)
    except ValueError as error:
        raise RunError('adapter_invalid_json') from error


def run(*, project, session, prompt, command=None, transport=None, event_key=None, timeout=120):
    from conector_mcp import recordar
    if type(timeout) is not int or not 1<=timeout<=600:
        raise ValueError('El timeout debe estar entre 1 y 600 segundos.')
    deadline=time.monotonic()+timeout
    def ask(request):
        remaining=math.ceil(deadline-time.monotonic())
        if remaining<1:
            raise RunError('adapter_timeout')
        if transport is None:
            return command_transport(command,request,remaining)
        current=copy.copy(transport) if hasattr(transport,'timeout') else transport
        if hasattr(current,'timeout'):current.timeout=min(current.timeout,remaining)
        return current(request)
    project = project_path(project)
    if not Path(project).is_dir():
        raise ValueError('El proyecto debe ser un directorio existente.')
    cycle = MemoryCycle(carpeta_memoria_de(project), project)
    opened = cycle.begin('strict-v2:'+session, prompt, event_key, policy='strict-extractive-v1')
    turn = opened['turn']
    working = cycle.working(turn)
    current = cycle.status(turn)['turns'][0]
    if current['status'] != 'open':
        raise RunError('turn_already_closed', turn, current)
    try:
        from evidence_guard import EvidenceLedger, EvidenceError, safe_text
        safe_text(prompt)
        ledger=EvidenceLedger(project,cycle.folder)
        ledger.user(prompt)
        packet = recordar(dict(proyecto=project, consulta=prompt[:2000], presupuesto=6000))
        for evidence in packet['evidence']:
            try:
                ledger.memory_note(evidence)
            except EvidenceError as error:
                ledger.failures.append(error.code)
        pending = cycle.status(limit=5)
        from reconciliation import inventory
        existing = inventory(cycle.folder, budget=30000)
        request = dict(grounding_evidence=ledger.packet(), existing_notes=existing, protocol=PROTOCOL, turn=turn, project=project, prompt=prompt,
                       working=working, memory=dict(evidence=packet, pending=pending),
                       instructions=contract(turn, pending['pending']),
                       response_schema=dict(answer='unpublished draft string',grounding=dict(sources='up to six ids from grounding_evidence.sources; no user_input or unverified_memory',abstain='boolean'),evidence_requests='optional up to four read_file/memory_note/json_value/calculate requests; one round', memory=dict(outcome='saved | no_change',
                           reason='required for no_change', actions='objects with filename,support:[{source,quote:complete paragraphs}], optional kind; updates require overwrite and expected_revision; [] if no_change',
                           checkpoint='optional {goal,progress,next_step,blockers}; agent summary, not confirmed facts')))
        from experience_engine import ExperienceStore
        from decision_rag import DecisionRAG
        request['decision_context'] = DecisionRAG(ExperienceStore(cycle.folder, project)).plan(prompt[:2000], budget=5000)
        response = ask(request)
        # Only one bounded evidence-acquisition round; never execute a model command.
        requests=response.get('evidence_requests',[]) if isinstance(response,dict) else []
        if requests:
            if not isinstance(requests,list) or len(requests)>4:
                raise RunError('evidence_request_limit')
            for item in requests:
                try:
                    ledger.tool(item)
                except (EvidenceError,OSError) as error:
                    ledger.failures.append(error.code if isinstance(error,EvidenceError) else 'evidence_unreadable')
            request['grounding_evidence']=ledger.packet()
            request['evidence_round_complete']=True
            response=ask(request)
            if isinstance(response,dict) and response.get('evidence_requests'):
                raise RunError('evidence_round_limit')
        if not isinstance(response, dict) or not isinstance(response.get('answer'), str) or not response['answer'].strip() or len(response['answer']) > 64000:
            raise RunError('invalid_answer')
        memory = response.get('memory')
        if not isinstance(memory, dict) or set(memory) - {'outcome', 'reason', 'actions', 'checkpoint'}:
            raise RunError('memory_contract_required')
        outcome, actions = memory.get('outcome'), memory.get('actions', [])
        if outcome not in ('saved', 'no_change') or not isinstance(actions, list) or len(actions) > 12:
            raise RunError('invalid_memory_outcome')
        if outcome == 'no_change' and (actions or not isinstance(memory.get('reason'), str) or not memory['reason'].strip()):
            raise RunError('no_change_requires_reason_and_no_actions')
        validate_closure(outcome, memory.get('reason'), memory.get('checkpoint'))
        try:
            selected=ledger.selection(response)
            actions=ledger.admit(actions)
        except EvidenceError as error:
            raise RunError(error.code,turn) from None
        # Queue before applying. A crash after this point leaves recoverable operations.
        if actions:
            cycle.queue(turn, actions, admission=ledger.approval())
        status = cycle.resume(turn)
        written={entry['receipt']['path'] for entry in status['turns'][0]['actions'] if entry['status']=='applied' and entry.get('receipt')}
        selected=[identifier for identifier in selected if ledger.sources[identifier]['path'] not in written]
        try:
            grounded=ledger.render(selected)
        except EvidenceError as error:
            raise RunError(error.code,turn,status) from None
        try:
            receipt = cycle.close(turn, outcome, memory.get('reason'), memory.get('checkpoint'), working['revision'])
        except ValueError as error:
            raise RunError('memory_unresolved', turn, status) from error
        if receipt.get('verified_writes'):
            if grounded['verification']['status']=='abstained':
                grounded['answer']='Memoria actualizada: '+str(receipt['verified_writes'])+' escritura(s) comprobada(s). No se publica el borrador del modelo como hecho.'
                grounded['verification']['status']='write_verified'
            else:
                grounded['answer']='Memoria actualizada con recibo comprobado.\n\n'+grounded['answer']
        return dict(protocol=PROTOCOL, turn=turn, **grounded, receipt=receipt,
                    working=dict(revision=cycle.working(turn)['revision'],state_available=bool(cycle.working(turn)['state']),source='agent:checkpoint',assurance='unverified_agent_summary_not_published'))
    except RunError as error:
        if not error.turn:
            error.turn = turn
        raise
    except (ValueError, OSError, sqlite3.Error, subprocess.SubprocessError) as error:
        # Adapter stderr, prompts and memory content must not appear in diagnostics.
        raise RunError(type(error).__name__, turn) from error
