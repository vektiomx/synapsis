#!/usr/bin/env python3
"""Instala el bridge de Synopsis para Antigravity. No pide contraseña ni sudo.

Usa el motor vendorizado en engine/ (no depende de tener Claude Code instalado). Si
querés usar otra copia, fijá SYNOPSIS_ROOT y SYNOPSIS_DATA antes de instalar.
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
EVENTOS = ('SessionStart', 'PreInvocation', 'PreToolUse', 'PostToolUse', 'PostInvocation', 'Stop')


def bloque(evento):
    from desktop_runtime import hook_command
    bridge = str(BASE / 'bridge.py')
    comando = {'type': 'command', 'command': hook_command(bridge,arguments=[evento]), 'timeout': 30}
    if evento in ('PreToolUse', 'PostToolUse'):
        return [{'matcher': '*', 'hooks': [comando]}]
    return [comando]


def preparar(ruta_hooks):
    datos = json.loads(ruta_hooks.read_text()) if ruta_hooks.exists() else {}
    datos['synopsis'] = {evento: bloque(evento) for evento in EVENTOS}
    return json.dumps(datos, indent=2) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--config-dir', type=Path, default=Path.home() / '.gemini' / 'config')
    args = parser.parse_args()
    if not (ROOT / 'hook_evento.py').is_file():
        raise SystemExit(f'No encontré el motor de Synopsis en {ROOT}. Si clonaste synopsis completo (con '
                         'engine/ adentro) esto no debería pasar; si moviste el motor a otro lado, fijá '
                         'SYNOPSIS_ROOT a su ruta.')
    ruta_hooks = args.config_dir / 'hooks.json'
    contenido = preparar(ruta_hooks)
    files = {ruta_hooks: contenido}
    mcp_path = args.config_dir / 'mcp_config.json'
    files[mcp_path] = integration_setup.json_mcp(mcp_path)
    files.update(integration_setup.skill_files(args.config_dir / 'skills'))
    backup = integration_setup.install_files(files, args.config_dir / 'synopsis-backups', args.dry_run)
    if args.dry_run:
        print(f'Plan válido: {len(EVENTOS)} eventos, MCP y memoria compartida. Sin cambios.')
        return
    print('Synopsis instalado para Antigravity: hooks, MCP y memoria compartida.')
    if backup:
        print('Respaldo en: ' + str(backup))
    comun.anotar_ubicacion()
    print('Reinicia Antigravity para cargar la integración.')


if __name__ == '__main__':
    main()
