#!/usr/bin/env python3
"""Codex lifecycle adapter for the installed Synopsis hooks."""
import hashlib
import contextlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import comun
import integration_runtime as runtime

ROOT = comun.raiz_motor()
DATA = comun.carpeta_datos()
EVENTS = ('SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PostToolUse',
          'PermissionRequest', 'PreCompact', 'PostCompact', 'SubagentStart',
          'SubagentStop', 'Stop', 'SessionEnd', 'Interrupt')

def normalize(data):
    """Expand file patches so Synopsis sees every affected file."""
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
    from desktop_runtime import python_flags
    proc = subprocess.run([sys.executable,*python_flags(), str(ROOT / script)],
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
    os.environ['SYNOPSIS_DEPURAR'] = '1'
    contexts, warnings, errors = [], [], []
    decision = None
    rows = normalize(data)
    for row in rows:
        result = runtime.dispatch(dict(row,synopsis_client='codex'), record_event=record, invoke_hook=invoke)
        contexts.extend(result['contexts'])
        warnings.extend(result['warnings'])
        errors.extend(result['errors'])
        if result['decision']:
            decision = dict(result['decision'])
            if decision.get('permissionDecision') == 'ask':
                decision['permissionDecision'] = 'deny'
    if contexts and event not in ('SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PostToolUse'):
        warnings.extend(contexts)
        contexts = []
    result = {}
    if warnings or errors:
        result['systemMessage'] = '\n'.join(warnings + ['Synopsis bridge error: ' + e for e in errors])
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
    runtime.heartbeat('codex', event, not errors, data=DATA)
    return result

def main():
    if '--probe' in sys.argv:
        print(json.dumps(runtime.probe('codex')))
        return
    data = {}
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError('Hook input must be an object')
        # Engine diagnostics must never become a second payload on hook stdout.
        with contextlib.redirect_stdout(io.StringIO()):
            result = handle(data)
    except Exception as exc:
        result = {'systemMessage': f'Synopsis bridge error: {type(exc).__name__}: {exc}'}
    if isinstance(data, dict) and data.get('hook_event_name') == 'UserPromptSubmit':
        # Codex also accepts plain developer context for this event. Avoid the JSON
        # decoder here; other lifecycle events still require their structured output.
        info = result.get('hookSpecificOutput') or {}
        parts = [part for part in (info.get('additionalContext'), result.get('systemMessage')) if part]
        if parts:
            print('Synopsis:\n' + '\n\n'.join(parts))
    else:
        print(json.dumps(result, ensure_ascii=True))

if __name__ == '__main__':
    main()
