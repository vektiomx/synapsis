#!/usr/bin/env python3
"""Instala los hooks de Synopsis para Claude Code directo en ~/.claude/settings.json,
en vez de depender del plugin del marketplace. No pide contraseña ni sudo.

Si el plugin "synopsis" del marketplace ya está activo, lo desactiva para que no se
dupliquen los eventos (los dos llamarían al mismo motor por cada acción).
"""
import argparse
import shlex
import datetime
import json
import os
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent))
import comun
import integration_setup

ROOT = comun.raiz_motor()
DATA = comun.carpeta_datos()

# (evento, matcher_o_None, script, timeout)
EVENTS = ('SessionStart', 'PreToolUse', 'PostToolUse', 'PostToolUseFailure', 'UserPromptSubmit',
          'Stop', 'SubagentStop', 'Notification', 'PreCompact', 'SessionEnd')
HOOKS = tuple((event, '*' if event in ('PreToolUse', 'PostToolUse', 'PostToolUseFailure') else None,
               'bridge.py', 30) for event in EVENTS)
SCRIPTS_PROPIOS = {'bridge.py', 'hook_inicio.py', 'hook_cerebro.py', 'hook_guardar.py', 'hook_freno.py',
                  'hook_parecidas.py', 'hook_choques.py', 'hook_servir.py'}


def comando(script, timeout):
    from desktop_runtime import hook_command
    return dict(type='command',command=hook_command(BASE/script,environment=dict(SYNOPSIS_ROOT=ROOT,SYNOPSIS_DATA=DATA,CLAUDE_PLUGIN_OPTION_SERVIR_CONTEXTO='true')),timeout=timeout)


def hooks_nuevos():
    por_evento = {}
    for evento, matcher, script, timeout in HOOKS:
        grupo = {'hooks': [comando(script, timeout)]}
        if matcher is not None:
            grupo['matcher'] = matcher
        por_evento.setdefault(evento, []).append(grupo)
    return por_evento


def grupo_es_nuestro(grupo):
    """Reconoce un grupo instalado por una corrida anterior de este mismo script, aunque
    el repo se haya movido: mira el nombre del hook_*.py en el comando, no una marca
    efímera (la ruta completa puede cambiar de un reinstall al otro)."""
    for h in grupo.get('hooks', []):
        from desktop_runtime import hook_text
        comando_texto = hook_text(h.get('command', ''))
        if 'CLAUDE_PLUGIN_OPTION_SERVIR_CONTEXTO=' in comando_texto and \
                any(script in comando_texto for script in SCRIPTS_PROPIOS):
            return True
    return False


def preparar(ruta_settings):
    datos = json.loads(ruta_settings.read_text()) if ruta_settings.exists() else {}
    datos.setdefault('hooks', {})
    nuevos = hooks_nuevos()
    for evento, grupos in nuevos.items():
        existentes = datos['hooks'].get(evento, [])
        datos['hooks'][evento] = [g for g in existentes if not grupo_es_nuestro(g)] + grupos
    desactivados = []
    for clave in list(datos.get('enabledPlugins', {})):
        if clave.startswith('synopsis@') and datos['enabledPlugins'][clave]:
            datos['enabledPlugins'][clave] = False
            desactivados.append(clave)
    return json.dumps(datos, indent=2) + '\n', desactivados


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--settings', type=Path, default=Path.home() / '.claude' / 'settings.json')
    args = parser.parse_args()
    if not (ROOT / 'hook_cerebro.py').is_file():
        raise SystemExit(f'No encontré el motor de Synopsis en {ROOT}.')
    contenido, desactivados = preparar(args.settings)
    files = {args.settings: contenido}
    user_config = args.settings.parent.parent / '.claude.json'
    files[user_config] = integration_setup.json_mcp(user_config)
    files.update(integration_setup.skill_files(args.settings.parent / 'skills'))
    backup = integration_setup.install_files(files, args.settings.parent / 'synopsis-backups', args.dry_run)
    if args.dry_run:
        print(f'Plan válido: {len(HOOKS)} eventos, MCP y memoria compartida. Sin cambios.')
        return
    print('Synopsis instalado para Claude Code: hooks, MCP y memoria compartida.')
    if backup:
        print('Respaldo en: ' + str(backup))
    comun.anotar_ubicacion()
    print('Reinicia Claude Code para cargar la integración.')


if __name__ == '__main__':
    main()
