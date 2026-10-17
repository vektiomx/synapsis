#!/usr/bin/env python3
"""Claude's native JSON envelope around the common lifecycle runtime."""
import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import integration_runtime as runtime


def handle(row):
    result = runtime.dispatch(dict(row,synopsis_client='claude'))
    output = {}
    warnings = result['warnings'] + result['errors']
    if warnings:
        output['systemMessage'] = '\n'.join(warnings)
    if result['decision']:
        output['hookSpecificOutput'] = result['decision']
    elif result['contexts']:
        output['hookSpecificOutput'] = dict(hookEventName=row.get('hook_event_name'),
                                            additionalContext='\n'.join(result['contexts']))
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
