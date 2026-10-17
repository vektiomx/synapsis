#!/usr/bin/env python3
"""Instala el bridge de Synopsis para Codex. No pide contraseña ni sudo.

Usa el motor vendorizado en engine/ (no depende de tener Claude Code instalado). Si
querés usar otra copia, fijá SYNOPSIS_ROOT y SYNOPSIS_DATA antes de instalar.
"""
import argparse
import shlex
import datetime
import json
import os
from pathlib import Path
import re
import sys
import tomllib

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent))
import comun
import integration_setup

ROOT = comun.raiz_motor()
DATA = comun.carpeta_datos()
EVENTS = ('SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PostToolUse',
          'PermissionRequest', 'PreCompact', 'PostCompact', 'SubagentStart',
          'SubagentStop', 'Stop', 'SessionEnd', 'Interrupt')


def hooks_template():
    from desktop_runtime import hook_command
    bridge = str(BASE / 'bridge.py')
    return {evento: [{'hooks': [{'type': 'command', 'command': hook_command(bridge),
                                  'timeout': 40, 'statusMessage': f'Synopsis: {evento}'}]}]
            for evento in EVENTS}


def desactivar_plugin_duplicado(config):
    """The Claude plugin's raw hooks must not run alongside the Codex adapter."""
    parsed = tomllib.loads(config)
    plugin = parsed.get('plugins', {}).get('synopsis@synopsis')
    if plugin is None or plugin.get('enabled') is False:
        return config
    header = re.search(
        r'''(?m)^[ \t]*\[plugins\.(?:"synopsis@synopsis"|'synopsis@synopsis')\][ \t]*(?:\#[^\n]*)?$''',
        config,
    )
    if header is None:
        raise ValueError('No pude desactivar el plugin duplicado synopsis@synopsis: '
                         'usá una tabla [plugins."synopsis@synopsis"] con enabled = false.')
    siguiente = re.search(r'(?m)^[ \t]*\[', config[header.end():])
    fin = header.end() + siguiente.start() if siguiente else len(config)
    bloque = config[header.end():fin]
    if 'enabled' in plugin:
        bloque, cambios = re.subn(r'(?m)^([ \t]*enabled[ \t]*=[ \t]*)true\b',
                                 r'\g<1>false', bloque)
        if cambios != 1:
            raise ValueError('No pude cambiar enabled del plugin duplicado; no modifiqué la configuración.')
    else:
        bloque = '\nenabled = false\n' + bloque
    resultado = config[:header.end()] + bloque + config[fin:]
    esperado = tomllib.loads(config)
    esperado['plugins']['synopsis@synopsis']['enabled'] = False
    if tomllib.loads(resultado) != esperado:
        raise ValueError('La configuración cambió fuera del plugin duplicado; no la modifiqué.')
    return resultado


def prepare(config_dir):
    hp, cp = config_dir / 'hooks.json', config_dir / 'config.toml'
    hooks = json.loads(hp.read_text()) if hp.exists() else {'hooks': {}}
    config = cp.read_text() if cp.exists() else ''
    config = desactivar_plugin_duplicado(config)
    template = hooks_template()

    def es_synopsis(h):
        # Reconoce instalaciones de esta herramienta sin importar el nombre que tenía
        # entonces ("Synopsis") o el de ahora ("Synopsis"), para no duplicar al migrar.
        mensaje = str(h.get('statusMessage', ''))
        return mensaje.startswith('Synopsis: ') or mensaje.startswith('Synopsis: ') or \
            ('bridge.py' in h.get('command', '') and ('Synopsis' in mensaje or 'Synopsis' in mensaje))

    for evento, grupos in template.items():
        existentes = hooks.setdefault('hooks', {}).get(evento, [])
        hooks['hooks'][evento] = [g for g in existentes
                                   if not any(es_synopsis(h) for h in g.get('hooks', []))] + grupos
    parsed = tomllib.loads(config)
    from desktop_runtime import python_flags
    expected_args=[*python_flags(),str(BASE/'mcp.py')]
    if 'synopsis' in parsed.get('mcp_servers', {}):
        actual = parsed['mcp_servers']['synopsis']
        if str(BASE / 'mcp.py') not in actual.get('args', []):
            raise ValueError('Ya hay un servidor MCP "synopsis" con otra configuración; no lo toqué.')
        if actual.get('args')!=expected_args:
            header=re.search(r'(?m)^\[mcp_servers\.(?:synopsis|"synopsis"|\'synopsis\')\][ \t]*$',config)
            if header is None:raise ValueError('No pude migrar los argumentos MCP de Synopsis sin alterar otras tablas.')
            end=re.search(r'(?m)^\[',config[header.end():]);stop=header.end()+end.start() if end else len(config)
            block=config[header.end():stop]
            updated,count=re.subn(r'(?m)^args\s*=.*$',lambda _: 'args = '+json.dumps(expected_args),block)
            if count!=1:raise ValueError('Los argumentos MCP requieren migración explícita.')
            expected=tomllib.loads(config);expected['mcp_servers']['synopsis']['args']=expected_args
            config=config[:header.end()]+updated+config[stop:]
            verified=tomllib.loads(config)
            if verified!=expected:raise ValueError('La migración MCP alteraría otras preferencias.')
    else:
        config += ('\n[mcp_servers.synopsis]\ncommand = ' + json.dumps(sys.executable) + '\nargs = '
                   + json.dumps(expected_args) + '\nstartup_timeout_sec = 20\n\n'
                   '[mcp_servers.synopsis.env]\n')
        for clave, valor in {'SYNOPSIS_ROOT': str(ROOT), 'SYNOPSIS_DATA': str(DATA),
                             'PYTHONDONTWRITEBYTECODE': '1'}.items():
            config += clave + ' = ' + json.dumps(valor) + '\n'
    tomllib.loads(config)
    return hp, cp, json.dumps(hooks, indent=2) + '\n', config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--config-dir', type=Path, default=Path.home() / '.codex')
    args = parser.parse_args()
    if not (ROOT / 'hook_evento.py').is_file() or not (ROOT / 'conector_mcp.py').is_file():
        raise SystemExit(f'No encontré el motor de Synopsis en {ROOT}. Si clonaste synopsis completo (con '
                         'engine/ adentro) esto no debería pasar; si moviste el motor a otro lado, fijá '
                         'SYNOPSIS_ROOT a su ruta.')
    hp, cp, hooks, config = prepare(args.config_dir)
    if args.dry_run:
        print(f'Configuración válida: {len(EVENTS)} hooks, el servidor MCP y el skill de memoria. '
              'No se cambió ningún archivo.')
        return
    files = {hp: hooks, cp: config}
    files.update(integration_setup.skill_files(args.config_dir / 'skills'))
    backup = integration_setup.install_files(files, args.config_dir / 'synopsis-backups')
    print('Synopsis instalado para Codex: hooks, MCP y memoria compartida.')
    if backup:
        print('Respaldo en: ' + str(backup))
    comun.anotar_ubicacion()
    print('Reiniciá Codex y confiá los hooks nuevos con /hooks en la CLI.')


if __name__ == '__main__':
    main()
