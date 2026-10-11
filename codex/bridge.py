#!/usr/bin/env python3
"""Codex lifecycle adapter for the installed Neuromapa hooks."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import comun

ROOT = comun.raiz_motor()
DATA = comun.carpeta_datos()
EVENTS = ('SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PostToolUse',
          'PermissionRequest', 'PreCompact', 'PostCompact', 'SubagentStart',
          'SubagentStop', 'Stop', 'SessionEnd', 'Interrupt')

def normalize(data):
    """Expand file patches so Neuromapa sees every affected file."""
    row = dict(data)
    name = str(row.get('tool_name', ''))
    args = row.get('tool_input')
    if not isinstance(args, dict):
        args = {'command': args} if isinstance(args, str) else {}
    row['tool_input'] = args
    if name in ('exec_command', 'functions.exec_command'):
        row['tool_name'] = 'Bash'
        row['tool_input'] = dict(args, command=args.get('cmd', args.get('command', '')))
    elif name in ('spawn_agent', 'collaboration.spawn_agent'):
        row['tool_name'] = 'Agent'
        row['tool_input'] = dict(args, subagent_type=args.get('task_name', 'codex'))
    if name == 'apply_patch':
        patch = args.get('command', args.get('patch', args.get('input', '')))
        matches = list(re.finditer(r'^\*\*\* (Add|Update|Delete) File: (.+)$', str(patch), re.M))
        rows = []
        for i, match in enumerate(matches):
            block = patch[match.end():matches[i+1].start() if i+1 < len(matches) else len(patch)]
            target = Path(match.group(2).strip())
            if not target.is_absolute():
                target = Path(row.get('cwd') or os.getcwd()) / target
            added = '\n'.join(line[1:] for line in block.splitlines() if line.startswith('+'))
            removed = '\n'.join(line[1:] for line in block.splitlines() if line.startswith('-'))
            item = dict(row, tool_name='Write' if match.group(1) == 'Add' else 'Edit')
            item['tool_input'] = {'file_path': str(target), 'content': added,
                                  'new_string': added, 'old_string': removed}
            if match.group(1) == 'Add':
                item['tool_response'] = {'type': 'create'}
            if row.get('tool_use_id'):
                item['tool_use_id'] = hashlib.sha256((str(row['tool_use_id']) + str(target)).encode()).hexdigest()[:10]
            rows.append(item)
        return rows or [row]
    return [row]

def record(row):
    # Use the original recorder, keeping its locking, rotation, and privacy rules.
    sys.path.insert(0, str(ROOT))
    import hook_evento
    event = row.get('hook_event_name')
    mapped = dict(row)
    mapped['hook_event_name'] = {'PermissionRequest': 'Notification',
                                'Interrupt': 'Stop', 'SubagentStart': 'PreToolUse',
                                'PostCompact': 'PostToolUse'}.get(event, event)
    if event == 'SessionStart' and row.get('source') == 'compact':
        mapped.update(hook_event_name='PostToolUse', tool_name='CodexCompact', tool_input={}, tool_response={})
    if event == 'SubagentStart':
        mapped.update(tool_name='Agent', tool_input={'subagent_type': row.get('agent_type', 'codex')},
                      tool_use_id='sub-' + str(row.get('agent_id', '')))
    elif event == 'PostCompact':
        mapped.update(tool_name='CodexCompact', tool_input={}, tool_response={})
    result = hook_evento.armar(mapped)
    if event == 'SubagentStop' and row.get('agent_id'):
        result['id'] = ('sub-' + str(row['agent_id']))[-10:]
        finished = dict(result, e='post', k='agente', h='Agent')
        hook_evento.escribir_evento(finished, 2.0)
    response = row.get('tool_response')
    failed = isinstance(response, dict) and (response.get('isError') is True or
                isinstance(response.get('exit_code'), int) and response['exit_code'] != 0)
    if isinstance(response, str):
        failed = bool(re.search(r'(?:Process exited with code|Exit code) [1-9][0-9]*', response))
    if event == 'PostToolUse' and failed:
        mapped['hook_event_name'] = 'PostToolUseFailure'
        result = hook_evento.armar(mapped)
    hook_evento.escribir_evento(result, 0.5 if event == 'Interrupt' else 2.0)
    if event in ('Stop', 'Interrupt', 'SessionEnd'):
        close_duplicate_sessions(row, hook_evento)
    if event == 'Stop':
        import aprender
        aprender.quizas()

def close_duplicate_sessions(row, recorder):
    """Close only fallback MCP sessions explicitly identified as duplicates."""
    mapping_path = DATA / 'en-vivo' / 'codex-mcp-orphans.json'
    if not mapping_path.exists():
        return
    mapping = json.loads(mapping_path.read_text())
    duplicates = mapping.get(str(row.get('session_id', ''))[:8], [])
    if not duplicates:
        return
    latest = {}
    path = DATA / 'en-vivo' / 'eventos.jsonl'
    with path.open('rb') as stream:
        stream.seek(0, 2)
        stream.seek(max(0, stream.tell() - 65536))
        for line in stream.read().splitlines():
            try:
                event = json.loads(line)
                if event.get('s') in duplicates:
                    latest[event['s']] = event
            except (ValueError, TypeError):
                continue
    for session, event in latest.items():
        if event.get('o') == 'app' and event.get('e') not in ('fin', 'cierre'):
            recorder.escribir_evento({'t': round(time.time(), 3), 's': session,
                                     'e': 'fin', 'k': 'fin', 'h': '', 'o': 'app'}, 0.5)

def invoke(script, row):
    proc = subprocess.run([sys.executable, '-I', '-S', str(ROOT / script)],
                          input=json.dumps(row), text=True, capture_output=True,
                          env=os.environ.copy(), timeout=9)
    if proc.returncode:
        raise RuntimeError(f'{script}: exit {proc.returncode}')
    if proc.stderr.strip():
        raise RuntimeError(f'{script}: {proc.stderr[-500:]}')
    return json.loads(proc.stdout) if proc.stdout.strip() else {}

def handle(data):
    event = data.get('hook_event_name')
    if event not in EVENTS:
        raise ValueError('Unsupported Codex event')
    os.environ['CLAUDE_PLUGIN_ROOT'] = str(ROOT)
    os.environ['CLAUDE_PLUGIN_DATA'] = str(DATA)
    os.environ['CLAUDE_PLUGIN_OPTION_SERVIR_CONTEXTO'] = 'true'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    sys.dont_write_bytecode = True
    # Original hooks swallow errors; debug exposes them so the bridge can report them.
    os.environ['NEUROMAPA_DEPURAR'] = '1'
    contexts, warnings, errors = [], [], []
    decision = None
    rows = normalize(data)
    for row in rows:
        try:
            record(row)
        except Exception as exc:
            errors.append(f'recorder: {type(exc).__name__}: {exc}')
        scripts = []
        if event == 'SessionStart':
            scripts = ['hook_inicio.py']
            if row.get('source') == 'compact':
                scripts.append('hook_guardar.py')
        elif event == 'UserPromptSubmit':
            scripts = ['hook_servir.py']
        elif event == 'Stop':
            scripts = ['hook_guardar.py']
        elif event == 'PreToolUse' and row.get('tool_name') in ('Agent', 'Task', 'Workflow'):
            scripts = ['hook_freno.py']
        elif event == 'PostToolUse' and row.get('tool_name') in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit'):
            scripts = ['hook_choques.py']
            if row.get('tool_name') == 'Write':
                scripts.append('hook_parecidas.py')
        for script in scripts:
            try:
                output = invoke(script, row)
                info = output.get('hookSpecificOutput') or {}
                if output.get('systemMessage'):
                    warnings.append(output['systemMessage'])
                if info.get('additionalContext'):
                    contexts.append(info['additionalContext'])
                if info.get('permissionDecision') == 'ask':
                    # Codex does not support Claude's "ask" decision. Deny and report why.
                    decision = {'hookEventName': event, 'permissionDecision': 'deny',
                                'permissionDecisionReason': info.get('permissionDecisionReason', 'Neuromapa agent limit')}
            except Exception as exc:
                errors.append(f'{script}: {type(exc).__name__}: {exc}')
    if contexts and event not in ('SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PostToolUse'):
        warnings.extend(contexts)
        contexts = []
    result = {}
    if warnings or errors:
        result['systemMessage'] = '\n'.join(warnings + ['Neuromapa bridge error: ' + e for e in errors])
    if decision:
        result['hookSpecificOutput'] = decision
    elif contexts:
        result['hookSpecificOutput'] = {'hookEventName': event, 'additionalContext': '\n'.join(contexts)}
    # Diagnostics contain event metadata only, never prompts, arguments, or note text.
    DATA.joinpath('en-vivo').mkdir(parents=True, exist_ok=True)
    with DATA.joinpath('en-vivo', 'codex-bridge.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'t': time.time(), 'event': event,
                                'session': str(data.get('session_id', ''))[:8],
                                'records': len(rows), 'ok': not errors, 'errors': errors}) + '\n')
    return result

def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError('Hook input must be an object')
        result = handle(data)
    except Exception as exc:
        result = {'systemMessage': f'Neuromapa bridge error: {type(exc).__name__}: {exc}'}
    print(json.dumps(result, ensure_ascii=True))

if __name__ == '__main__':
    main()
