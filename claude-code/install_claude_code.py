#!/usr/bin/env python3
"""Instala los hooks de Synapsis para Claude Code directo en ~/.claude/settings.json,
en vez de depender del plugin del marketplace. No pide contraseña ni sudo.

Si el plugin "neuromapa" del marketplace ya está activo, lo desactiva para que no se
dupliquen los eventos (los dos llamarían al mismo motor por cada acción).
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent))
import comun

ROOT = comun.raiz_motor()
DATA = comun.carpeta_datos()

# (evento, matcher_o_None, script, timeout)
HOOKS = (
    ('SessionStart', None, 'hook_inicio.py', 10),
    ('SessionStart', None, 'hook_cerebro.py', 5),
    ('SessionStart', 'compact', 'hook_guardar.py', 10),
    ('PreToolUse', '*', 'hook_cerebro.py', 5),
    ('PreToolUse', 'Agent|Task|Workflow', 'hook_freno.py', 10),
    ('PostToolUse', '*', 'hook_cerebro.py', 5),
    ('PostToolUse', 'Write', 'hook_parecidas.py', 10),
    ('PostToolUse', 'Edit|Write|MultiEdit|NotebookEdit', 'hook_choques.py', 5),
    ('PostToolUseFailure', '*', 'hook_cerebro.py', 5),
    ('UserPromptSubmit', None, 'hook_cerebro.py', 5),
    ('UserPromptSubmit', None, 'hook_servir.py', 10),
    ('Stop', None, 'hook_cerebro.py', 5),
    ('Stop', None, 'hook_guardar.py', 10),
    ('SubagentStop', None, 'hook_cerebro.py', 5),
    ('Notification', None, 'hook_cerebro.py', 5),
    ('PreCompact', None, 'hook_cerebro.py', 5),
    ('SessionEnd', None, 'hook_cerebro.py', 5),
)
# Nombres de script estables (no cambian aunque se mueva el repo o cambie de nombre):
# son la forma confiable de reconocer "esto lo instalamos nosotros" al reinstalar.
SCRIPTS_PROPIOS = {script for _, _, script, _ in HOOKS}


def comando(script, timeout):
    script_ruta = BASE.parent / 'engine' / script
    partes = [f'CLAUDE_PLUGIN_ROOT={ROOT}', f'CLAUDE_PLUGIN_DATA={DATA}',
              'CLAUDE_PLUGIN_OPTION_SERVIR_CONTEXTO=true',
              '/usr/bin/python3', '-I', '-S', str(script_ruta)]
    return {'type': 'command', 'command': ' '.join(partes), 'timeout': timeout}


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
        comando_texto = h.get('command', '')
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
        if clave.startswith('neuromapa@') and datos['enabledPlugins'][clave]:
            datos['enabledPlugins'][clave] = False
            desactivados.append(clave)
    return json.dumps(datos, indent=2) + '\n', desactivados


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--settings', type=Path, default=Path.home() / '.claude' / 'settings.json')
    args = parser.parse_args()
    if not (ROOT / 'hook_cerebro.py').is_file():
        raise SystemExit(f'No encontré el motor de Synapsis en {ROOT}.')
    contenido, desactivados = preparar(args.settings)
    if args.dry_run:
        extra = f' (desactivaría el plugin del marketplace: {", ".join(desactivados)})' if desactivados else ''
        print(f'Configuración válida: {len(HOOKS)} hooks.{extra} No se cambió ningún archivo.')
        return
    args.settings.parent.mkdir(parents=True, exist_ok=True)
    backup = args.settings.parent / 'neuromapa-backups' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True, mode=0o700)
    original = args.settings.read_bytes() if args.settings.exists() else None
    if original is not None:
        (backup / 'settings.json').write_bytes(original)
        (backup / 'settings.json').chmod(0o600)
    try:
        temporal = args.settings.with_name(args.settings.name + '.neuromapa.tmp')
        temporal.write_text(contenido, encoding='utf-8')
        temporal.chmod(0o600)
        os.replace(temporal, args.settings)
    except Exception:
        if original is not None:
            args.settings.write_bytes(original)
        elif args.settings.exists():
            args.settings.unlink()
        raise
    print('Synapsis instalado para Claude Code. Copia de seguridad en: ' + str(backup))
    if desactivados:
        print('Desactivé el plugin del marketplace para evitar eventos duplicados: ' + ', '.join(desactivados))
        print('Perdés /neuromapa:abrir, /neuromapa:salud y /neuromapa:sobre (son del plugin); '
              'usá los scripts de engine/ directo si los necesitás.')
    comun.anotar_ubicacion()
    print('Reiniciá Claude Code para que cargue los hooks nuevos.')


if __name__ == '__main__':
    main()
