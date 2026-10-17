"""One lifecycle engine; adapters only translate client input and output."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import comun


def environment():
    root, data = comun.raiz_motor(), comun.carpeta_datos()
    os.environ.update(CLAUDE_PLUGIN_ROOT=str(root), CLAUDE_PLUGIN_DATA=str(data),
                      CLAUDE_PLUGIN_OPTION_SERVIR_CONTEXTO='true', PYTHONDONTWRITEBYTECODE='1')
    sys.dont_write_bytecode = True
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def invoke(script, row):
    from desktop_runtime import python_flags
    process = subprocess.run([sys.executable,*python_flags(), str(comun.raiz_motor() / script)],
                             input=json.dumps(row), text=True, capture_output=True,
                             env=dict(os.environ), timeout=9)
    if process.returncode or process.stderr.strip():
        # Do not persist interpreter output, which can contain user-controlled data.
        raise RuntimeError(f'{script}: process failed ({process.returncode})')
    return json.loads(process.stdout) if process.stdout.strip() else {}


def record(row):
    import hook_evento
    if hook_evento.se_anota(row):
        event = hook_evento.armar(row)
        hook_evento.escribir_evento(event, 2.0)
        if event['e'] == 'fin':
            import aprender
            aprender.quizas()


def scripts_for(row):
    event, tool = row.get('hook_event_name'), row.get('tool_name')
    if event == 'SessionStart':
        return ['hook_inicio.py', 'hook_cycle.py'] + (['hook_guardar.py'] if row.get('source') == 'compact' else [])
    if event == 'UserPromptSubmit':
        return ['hook_cycle.py']
    if event == 'Stop':
        return ['hook_guardar.py', 'hook_cycle.py']
    if event == 'PreCompact':
        return ['hook_cycle.py']
    if event == 'PreToolUse' and tool in ('Read','Write','Edit','MultiEdit','NotebookEdit'):
        return ['hook_cycle.py']
    if event == 'PreToolUse' and tool in ('Agent', 'Task', 'Workflow'):
        return ['hook_freno.py']
    if event == 'PostToolUse' and tool in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit'):
        return ['hook_cycle.py', 'hook_choques.py'] + (['hook_parecidas.py'] if tool == 'Write' else [])
    if event == 'PostToolUse':
        return ['hook_cycle.py']
    return []


def dispatch(row, record_event=None, invoke_hook=None):
    output = dict(contexts=[], warnings=[], errors=[], decision=None)
    if row.get("hook_event_name") in ("Stop", "SubagentStop") and row.get("stop_hook_active") is True:
        return output
    if os.environ.get("SYNOPSIS_CONTROLLED_RUN") == "1":
        return output
    environment()
    try:
        (record_event or record)(row)
    except Exception as error:
        output['errors'].append('recorder: ' + type(error).__name__)
    for script in scripts_for(row):
        try:
            response = (invoke_hook or invoke)(script, row)
            if response.get('synopsisError') == 'memory_identity_conflict':
                output['errors'].append(script + ': memory_identity_conflict')
            info = response.get('hookSpecificOutput') or {}
            if response.get('systemMessage'):
                output['warnings'].append(response['systemMessage'])
            if info.get('additionalContext'):
                if info['additionalContext'] not in output['contexts']:
                    output['contexts'].append(info['additionalContext'])
            if info.get('permissionDecision'):
                output['decision'] = info
        except Exception as error:
            output['errors'].append(script + ': ' + type(error).__name__)
    return output


def heartbeat(client, event, ok=True, data=None):
    if client not in ('claude', 'codex', 'antigravity', 'opencode', 'cursor'):
        raise ValueError('Unsupported client')
    from archivos import escribir_atomico
    folder = Path(data or comun.carpeta_datos()) / 'integrations'
    try:
        folder.mkdir(parents=True, mode=0o700, exist_ok=True)
        escribir_atomico(folder / (client + '.json'), json.dumps(dict(time=time.time(), event=event, ok=ok)))
    except OSError:
        return False
    return True


def probe(client):
    return dict(synopsis=True, client=client, protocol=1)
