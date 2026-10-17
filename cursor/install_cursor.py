#!/usr/bin/env python3
"""Merge global Cursor hooks, MCP and skill without changing workspace files."""
import argparse
import json
import shlex
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent))
import comun
import integration_setup as setup
from importlib.util import spec_from_file_location, module_from_spec
spec = spec_from_file_location('cursor_bridge', BASE / 'bridge.py')
bridge = module_from_spec(spec)
spec.loader.exec_module(bridge)

def files(home=None):
    folder = Path(home or Path.home()) / '.cursor'
    path = folder / 'hooks.json'
    data = json.loads(path.read_text()) if path.exists() else {'version': 1}
    if data.get('version', 1) != 1:
        raise ValueError('Versión de hooks de Cursor no compatible; no se modificó.')
    data['version'] = 1
    hooks = data.setdefault('hooks', {})
    from desktop_runtime import hook_command,hook_text
    command=hook_command(BASE/'bridge.py',environment=dict(SYNOPSIS_ROOT=comun.raiz_motor(),SYNOPSIS_DATA=comun.carpeta_datos()))
    for event in bridge.EVENTS:
        previous = hooks.get(event, [])
        hooks[event] = [row for row in previous if not (
            'SYNOPSIS_ROOT=' in hook_text(row.get('command', '')) and 'cursor/bridge.py' in hook_text(row.get('command', '')).replace('\\','/'))]
        hooks[event].append(dict(command=command, timeout=30))
    planned = {path: json.dumps(data, indent=2) + '\n', folder / 'mcp.json': setup.json_mcp(folder / 'mcp.json')}
    planned.update(setup.skill_files(folder / 'skills'))
    return planned

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    setup.install_files(files(), Path.home() / '.cursor/synopsis-backups', args.dry_run)
    print('Cursor: hooks, MCP y skill preparados.' if args.dry_run else 'Synopsis instalado para Cursor. Reinicia el cliente.')

if __name__ == '__main__':
    main()
