#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import comun

NEUROMAPA_DIR = str(comun.raiz_motor())
os.environ.setdefault('CLAUDE_PLUGIN_DATA', str(comun.carpeta_datos()))
if NEUROMAPA_DIR not in sys.path:
    sys.path.insert(0, NEUROMAPA_DIR)

def map_tool(name, args):
    if not isinstance(args, dict):
        args = {}
    if name == 'run_command':
        return 'Bash', {'command': args.get('CommandLine', '')}
    elif name == 'view_file':
        return 'Read', {'file_path': args.get('AbsolutePath', '')}
    elif name in ('replace_file_content', 'multi_replace_file_content'):
        return 'Edit', {'file_path': args.get('TargetFile', '')}
    elif name == 'write_to_file':
        return 'Write', {'file_path': args.get('TargetFile', '')}
    elif name == 'grep_search':
        return 'Grep', {'path': args.get('SearchPath', '')}
    elif name == 'list_dir':
        return 'Bash', {'command': 'ls ' + str(args.get('DirectoryPath', ''))}
    elif name == 'browser_subagent':
        return 'Agent', {'task': str(args.get('Task', ''))}
    return name, args

def get_last_user_prompt(path):
    if not path or not os.path.isfile(path):
        return ''
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        for line in reversed(lines):
            try:
                row = json.loads(line)
                if row.get('type') == 'USER_INPUT':
                    content = row.get('content', '')
                    m = re.search(r'<USER_REQUEST>(.*?)</USER_REQUEST>', content, re.DOTALL)
                    if m:
                        return m.group(1).strip()
                    return content.strip()
            except Exception:
                continue
    except Exception:
        pass
    return ''

def main():
    event_type = sys.argv[1] if len(sys.argv) > 1 else ''
    raw_input = ''
    try:
        raw_input = sys.stdin.read()
    except Exception:
        pass

    try:
        data = json.loads(raw_input) if raw_input.strip() else {}
    except Exception:
        data = {}

    conversation_id = str(data.get('conversationId') or '')[:8]
    workspaces = data.get('workspacePaths') or []
    cwd = workspaces[0] if workspaces else os.getcwd()
    injected_message = None

    try:
        import hook_evento

        if event_type == 'PreToolUse':
            tool_call = data.get('toolCall') or {}
            tool_name_raw = tool_call.get('name') or ''
            args_raw = tool_call.get('args') or {}
            mapped_name, mapped_input = map_tool(tool_name_raw, args_raw)

            payload = {
                'hook_event_name': 'PreToolUse',
                'session_id': conversation_id,
                'tool_name': mapped_name,
                'tool_input': mapped_input,
                'cwd': cwd,
            }
            ev = hook_evento.armar(payload)
            hook_evento.escribir_evento(ev)

        elif event_type == 'PostToolUse':
            error = data.get('error')
            payload = {
                'hook_event_name': 'PostToolUse' if not error else 'PostToolUseFailure',
                'session_id': conversation_id,
                'cwd': cwd,
                'error': error,
            }
            ev = hook_evento.armar(payload)
            hook_evento.escribir_evento(ev)

        elif event_type == 'PreInvocation':
            prompt = get_last_user_prompt(data.get('transcriptPath'))
            # Only record UserPromptSubmit on the initial invocation of a user turn
            if data.get('invocationNum', 1) <= 1:
                payload = {
                    'hook_event_name': 'UserPromptSubmit',
                    'session_id': conversation_id,
                    'cwd': cwd,
                    'prompt': prompt,
                }
                ev = hook_evento.armar(payload)
                hook_evento.escribir_evento(ev)

            # Query Neuromapa automatic context
            try:
                import hook_servir
                if prompt:
                    ctx = hook_servir.contexto(prompt, cwd, sesion=conversation_id)
                    if ctx:
                        injected_message = ctx
            except Exception:
                pass

        elif event_type in ('PostInvocation', 'Stop'):
            payload = {
                'hook_event_name': 'Stop',
                'session_id': conversation_id,
                'cwd': cwd,
            }
            ev = hook_evento.armar(payload)
            hook_evento.escribir_evento(ev)
            try:
                import aprender
                aprender.quizas()
            except Exception:
                pass

    except Exception:
        pass

    if event_type == 'PreToolUse':
        print(json.dumps({'decision': 'allow'}))
    elif event_type == 'PreInvocation' and injected_message:
        print(json.dumps({'injectSteps': [{'ephemeralMessage': injected_message}]}))
    else:
        print(json.dumps({}))

if __name__ == '__main__':
    main()
