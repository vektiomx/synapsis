#!/usr/bin/env python3
"""OpenCode's JS plugin sends canonical events to the common runtime."""
import contextlib
import io
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import integration_runtime as runtime

def main():
    if '--probe' in sys.argv:
        print(json.dumps(runtime.probe('opencode')))
        return
    try:
        row = json.load(sys.stdin)
        if not isinstance(row, dict) or not Path(row.get('cwd', '')).is_absolute():
            raise ValueError('Expected a scoped event')
        with contextlib.redirect_stdout(io.StringIO()):
            result = runtime.dispatch(dict(row,synopsis_client='opencode'))
            runtime.heartbeat('opencode', row.get('hook_event_name'), not result['errors'])
    except Exception as error:
        result = dict(contexts=[], warnings=[], errors=[type(error).__name__], decision=None)
    print(json.dumps(result))

if __name__ == '__main__':
    main()
