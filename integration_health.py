"""Probe the transport without recording fake conversations or reading notes."""
import json
import os
import subprocess
import sys
from pathlib import Path

import comun


def check(expected_clients=None):
    from desktop_runtime import capabilities,hook_text,python_flags
    requests = [dict(jsonrpc='2.0', id=1, method='initialize', params={'protocolVersion': '2025-06-18'}),
                dict(jsonrpc='2.0', id=2, method='tools/list')]
    try:
        process = subprocess.run([sys.executable, '-B', str(comun.REPO / 'mcp_entry.py')],
                                 input=''.join(json.dumps(row) + '\n' for row in requests),
                                 text=True, capture_output=True, timeout=15)
        replies = {row.get('id'): row for row in map(json.loads, process.stdout.splitlines())}
        names = {tool['name'] for tool in replies.get(2, {}).get('result', {}).get('tools', [])}
        ready = process.returncode == 0 and 'result' in replies.get(1, {}) and {'recordar', 'guardar'} <= names
    except (OSError, ValueError, subprocess.TimeoutExpired):
        ready, names = False, set()
    clients = {}
    for key, directory in (('claude', 'claude-code'), ('codex', 'codex'), ('antigravity', 'antigravity'), ('opencode', 'opencode'), ('cursor', 'cursor')):
        try:
            process = subprocess.run([sys.executable, '-B', str(comun.REPO / directory / 'bridge.py'), '--probe'],
                                     capture_output=True, text=True, timeout=10)
            adapter = process.returncode == 0 and json.loads(process.stdout).get('client') == key
        except (OSError, ValueError, subprocess.TimeoutExpired):
            adapter = False
        marker = comun.carpeta_datos() / 'integrations' / (key + '.json')
        try:
            last = json.loads(marker.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            last = None
        activity = 'observed' if last and last.get('ok', True) else 'observed_with_errors' if last else 'waiting_for_first_event'
        home = Path.home()
        paths = {'claude': (home / '.claude/settings.json', home / '.claude.json'),
                 'codex': (home / '.codex/hooks.json', home / '.codex/config.toml'),
                 'antigravity': (home / '.gemini/config/hooks.json', home / '.gemini/config/mcp_config.json'),
                 'cursor': (home / '.cursor/hooks.json', home / '.cursor/mcp.json'),
                 'opencode': (Path(os.environ.get('XDG_CONFIG_HOME', str(home / '.config'))) / 'opencode/plugins/synopsis.js', None)}
        hooks_path, mcp_path = paths[key]
        configured = False
        try:
            hooks_text = hooks_path.read_text(encoding='utf-8')
            # Decode managed PowerShell wrappers only for ownership validation.
            try:
                def decoded(value):
                    if isinstance(value,dict):return {k:decoded(v) for k,v in value.items()}
                    if isinstance(value,list):return [decoded(v) for v in value]
                    return hook_text(value) if isinstance(value,str) else value
                inspected_hooks=json.dumps(decoded(json.loads(hooks_text)),ensure_ascii=False) if key!='opencode' else hooks_text
            except ValueError:inspected_hooks=hooks_text
            if key == 'opencode':
                import runpy
                expected_text = runpy.run_path(str(comun.REPO / 'opencode/install_opencode.py'))['plugin_text']()
                configured = hooks_text == expected_text and (comun.REPO / 'opencode/plugin.mjs').is_file()
                clients[key] = dict(adapter_ready=adapter, configured=configured,
                                    activity=activity, last_event=last)
                continue
            if key == 'codex':
                import tomllib
                mcp = tomllib.loads(mcp_path.read_text(encoding='utf-8')).get('mcp_servers', {})
            else:
                mcp = json.loads(mcp_path.read_text(encoding='utf-8')).get('mcpServers', {})
            server = mcp.get('synopsis') or {}
            expected = comun.REPO / ('codex/mcp.py' if key == 'codex' else 'mcp_entry.py')
            server_env = server.get('env', {})
            configured = (server.get('args') == [*python_flags(), str(expected)]
                          and Path(server.get('command', '')).resolve() == Path(sys.executable).resolve()
                          and server_env.get('SYNOPSIS_ROOT') == str(comun.raiz_motor())
                          and server_env.get('SYNOPSIS_DATA') == str(comun.carpeta_datos())
                          and server.get('enabled', True) and not server.get('disabled', False)
                          and str(comun.REPO / directory / 'bridge.py').replace('\\','/') in inspected_hooks.replace('\\\\','/').replace('\\','/'))
        except (OSError, ValueError):
            pass
        clients[key] = dict(adapter_ready=adapter, configured=configured, activity=activity,
                            last_event=last)
    targets = expected_clients if expected_clients is not None else [key for key, row in clients.items() if row['configured']]
    connected = bool(targets) and all(clients[key]['configured'] and clients[key]['adapter_ready'] for key in targets)
    sys.path.insert(0, str(comun.raiz_motor()))
    from model_provider import detect
    from semantic_memory import discover
    try:
        semantic = 'available' if discover() else 'lexical_fallback'
    except ValueError:
        semantic = 'configuration_error'
    from workspace_registry import pending
    binding_requests = len(pending())
    from local_semantics import status as local_semantic_status
    return dict(capabilities=capabilities(),semantic_runtime=local_semantic_status(),automatic_review=dict(enabled=os.environ.get('SYNOPSIS_AUTO_REVIEW','1')!='0',
                status_command='synopsis reviews --project /ruta/proyecto',
                routing='same_client_cli_or_local_ollama',
                note='La presencia del cliente no prueba autorización de inferencia; consulta recibos por proyecto.'),inference=detect(), semantic=semantic, ready=ready and connected,
                project_binding='automatic_on_first_use', pending_bindings=binding_requests,
                mcp_ready=ready, tools=len(names), clients=clients,
                note='La prueba de transporte no demuestra que el IDE haya autorizado o cargado sus hooks.')
