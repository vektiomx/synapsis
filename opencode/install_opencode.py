#!/usr/bin/env python3
"""Auto-loaded native plugin preserves existing OpenCode JSONC verbatim."""
import argparse
import json
import os
import sys
from pathlib import Path
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent))
import comun
import integration_setup as setup

def config_dir():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'opencode'

def plugin_text():
    server = setup.mcp_definition()
    options = dict(python=sys.executable, bridge=str(BASE / 'bridge.py'), environment=server['env'],
                   mcp=dict(type='local', command=[server['command'], *server['args']], enabled=True,
                            environment=server['env']))
    return ('// Synopsis managed integration.\nimport { createPlugin } from ' + json.dumps((BASE / 'plugin.mjs').as_uri()) + ';\n'
            + 'export default createPlugin(' + json.dumps(options) + ');\n')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    folder = config_dir()
    for config in (folder / 'opencode.json', folder / 'opencode.jsonc'):
        if config.exists():
            current = setup.read_jsonc(config).get('mcp', {}).get('synopsis')
            if current and not (isinstance(current, dict) and current.get('environment', {}).get('SYNOPSIS_ROOT')):
                raise ValueError('Ya existe un MCP synopsis ajeno; no se reemplazó.')
    path = folder / 'plugins/synopsis.js'
    if path.exists() and not path.read_text().startswith('// Synopsis managed integration.'):
        raise ValueError('Ya existe un plugin synopsis ajeno; no se reemplazó.')
    files = {path: plugin_text()}
    files.update(setup.skill_files(folder / 'skills'))
    setup.install_files(files, folder / 'synopsis-backups', args.dry_run)
    print('OpenCode: plugin, MCP y skill preparados.' if args.dry_run else 'Synopsis instalado para OpenCode. Reinicia el cliente.')

if __name__ == '__main__':
    main()
