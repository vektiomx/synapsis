#!/usr/bin/env python3
"""Claude's native JSON envelope around the common lifecycle runtime."""
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import integration_runtime as runtime
from engine.hooks_comun import context_output


def handle(row):
    if row.get('hook_event_name') in ('Stop', 'SubagentStop') and row.get('stop_hook_active') is True:
        return {}
    result = runtime.dispatch(dict(row,synopsis_client='claude'))
    event = row.get('hook_event_name')
    output = context_output(event, '\n'.join(result['contexts']))
    warnings = result['warnings'] + result['errors']
    if warnings:
        output['systemMessage'] = '\n'.join(warnings + ([output['systemMessage']] if output.get('systemMessage') else []))
    if result['decision'] and event == 'PreToolUse':
        output['hookSpecificOutput'] = result['decision']
    runtime.heartbeat('claude', row.get('hook_event_name'), not result['errors'])
    return output


def main():
    if '--probe' in sys.argv:
        print(json.dumps(runtime.probe('claude')))
        return
    try:
        row = json.load(sys.stdin)
        if not isinstance(row, dict):
            raise ValueError('Expected a hook object')
        with contextlib.redirect_stdout(io.StringIO()):
            output = handle(row)
    except Exception as error:
        output = {'systemMessage': 'Synopsis: ' + type(error).__name__}
    print(json.dumps(output, ensure_ascii=True))


if __name__ == '__main__':
    main()
