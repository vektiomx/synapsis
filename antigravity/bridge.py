#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import comun

SYNOPSIS_DIR = str(comun.raiz_motor())
os.environ.setdefault('CLAUDE_PLUGIN_DATA', str(comun.carpeta_datos()))
if SYNOPSIS_DIR not in sys.path:
    sys.path.insert(0, SYNOPSIS_DIR)

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
        with open(path, 'rb') as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 1024 * 1024))
            raw = f.read().splitlines()
            lines = [line.decode('utf-8', errors='replace') for line in (raw[1:] if size > 1024 * 1024 else raw)]
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

def handle(data, event_type):
    import integration_runtime as runtime
    mapping = {'SessionStart': 'SessionStart', 'PreInvocation': 'UserPromptSubmit',
               'PreToolUse': 'PreToolUse', 'PostToolUse': 'PostToolUse', 'Stop': 'Stop'}
    if event_type == 'PostInvocation' or (event_type == 'PreInvocation' and data.get('invocationNum', 1) > 1):
        return {}
    if event_type not in mapping:
        raise ValueError('Unsupported Antigravity event')
    workspaces = data.get('workspacePaths') or []
    cwd = data.get('cwd') or (workspaces[0] if len(workspaces) == 1 else os.getcwd() if not workspaces else '')
    if not cwd:
        return {}
    row = dict(synopsis_client='antigravity', last_assistant_message=data.get('last_assistant_message') or '', hook_event_name=mapping[event_type], session_id=str(data.get('conversationId') or ''),
               cwd=cwd, workspace_roots=workspaces, transcript_path=data.get('transcriptPath'))
    if event_type == 'PreInvocation':
        row['prompt'] = data.get('prompt') or get_last_user_prompt(data.get('transcriptPath'))
    if event_type in ('PreToolUse', 'PostToolUse'):
        call = data.get('toolCall') or {}
        row['tool_name'], row['tool_input'] = map_tool(call.get('name', ''), call.get('args', {}))
        if data.get('error'):
            row['hook_event_name'] = 'PostToolUseFailure'
            row['error'] = data['error']
    result = runtime.dispatch(row)
    runtime.heartbeat('antigravity', event_type, not result['errors'])
    for warning in result['errors']:
        print('Synopsis: ' + warning, file=sys.stderr)
    if event_type == 'PreToolUse':
        decision = result['decision'] or {}
        return dict(decision=decision.get('permissionDecision', 'allow'),
                    reason=decision.get('permissionDecisionReason', ''))
    if event_type == 'PreInvocation':
        messages = result['contexts'] + result['warnings']
        if messages:
            return dict(injectSteps=[dict(ephemeralMessage='\n'.join(messages))])
    return {}


def main():
    import contextlib
    import io
    import integration_runtime as runtime
    if '--probe' in sys.argv:
        print(json.dumps(runtime.probe('antigravity')))
        return
    event_type = sys.argv[1] if len(sys.argv) > 1 else ''
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError('Expected a hook object')
        with contextlib.redirect_stdout(io.StringIO()):
            result = handle(data, event_type)
    except Exception as error:
        print('Synopsis: ' + type(error).__name__, file=sys.stderr)
        result = {'decision': 'allow'} if event_type == 'PreToolUse' else {}
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
