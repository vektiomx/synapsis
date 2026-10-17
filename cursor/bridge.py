#!/usr/bin/env python3
"""Translate Cursor's documented envelope; never fabricate unsupported outputs."""
import contextlib
import io
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import integration_runtime as runtime

EVENTS = {'sessionStart': 'SessionStart', 'sessionEnd': 'SessionEnd',
          'beforeSubmitPrompt': 'UserPromptSubmit', 'preToolUse': 'PreToolUse',
          'postToolUse': 'PostToolUse', 'postToolUseFailure': 'PostToolUseFailure',
          'preCompact': 'PreCompact', 'stop': 'Stop'}
GUIDANCE = ('Synopsis: consulta estado_memoria por MCP para obtener el turno abierto por hooks; si no lo hay usa iniciar_turno_memoria. Cierra con cerrar_turno_memoria antes de terminar cada tarea. Consulta recordar usando la ruta absoluta '
            'del proyecto. Guarda decisiones y correcciones relevantes con guardar; conserva '
            'su procedencia y comprueba las citas antes de aplicarlas.')

def handle(data):
    event = data.get('hook_event_name')
    if event not in EVENTS:
        return {}
    roots = data.get('workspace_roots') or []
    cwd = data.get('cwd') or (roots[0] if len(roots) == 1 else '')
    active = (data.get('tool_input') or {}).get('file_path')
    if not cwd and isinstance(active, str) and Path(active).is_absolute():
        matches = [root for root in roots if Path(active).resolve().is_relative_to(Path(root).resolve())]
        if len(matches) == 1:
            cwd = matches[0]
    row = dict(data, synopsis_client='cursor', hook_event_name=EVENTS[event],
               session_id=data.get('conversation_id') or data.get('session_id', ''),
               cwd=cwd,
               tool_name={'Shell': 'Bash'}.get(data.get('tool_name'), data.get('tool_name')),
               tool_response=data.get('tool_output'), duration_ms=data.get('duration'))
    # A multiroot session without cwd has no unambiguous project scope.
    if not row['cwd'] or not Path(row['cwd']).is_absolute():
        return {'continue': True} if event == 'beforeSubmitPrompt' else {}
    if event == 'beforeSubmitPrompt':
        result = runtime.dispatch(row)
        runtime.heartbeat('cursor', EVENTS[event], not result['errors'])
        return {'continue': True}
    result = runtime.dispatch(row)
    runtime.heartbeat('cursor', EVENTS[event], not result['errors'])
    if event in ('sessionStart', 'postToolUse', 'postToolUseFailure'):
        contexts = result['contexts'] + result['warnings']
        if event == 'sessionStart':
            contexts.insert(0, GUIDANCE)
        return {'additional_context': '\n'.join(contexts)} if contexts else {}
    if event == 'preToolUse' and result['decision']:
        decision = result['decision']
        # Cursor accepts ask syntactically but does not enforce it: block with a reason.
        permission = 'allow' if decision.get('permissionDecision') == 'allow' else 'deny'
        return dict(permission=permission, agent_message=decision.get('permissionDecisionReason', 'Synopsis'))
    return {}

def main():
    if '--probe' in sys.argv:
        print(json.dumps(runtime.probe('cursor')))
        return
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            output = handle(json.load(sys.stdin))
    except Exception as error:
        print('Synopsis: ' + type(error).__name__, file=sys.stderr)
        output = {}
    print(json.dumps(output))

if __name__ == '__main__':
    main()
