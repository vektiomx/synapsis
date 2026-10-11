#!/usr/bin/env python3
"""Instala el bridge de Synapsis para Codex. No pide contraseña ni sudo.

Usa el motor vendorizado en engine/ (no depende de tener Claude Code instalado). Si
querés usar otra copia, fijá NEUROMAPA_ROOT y NEUROMAPA_DATA antes de instalar.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import sys
import tomllib

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parent))
import comun

ROOT = comun.raiz_motor()
DATA = comun.carpeta_datos()
EVENTS = ('SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PostToolUse',
          'PermissionRequest', 'PreCompact', 'PostCompact', 'SubagentStart',
          'SubagentStop', 'Stop', 'SessionEnd', 'Interrupt')


def hooks_template():
    bridge = str(BASE / 'bridge.py')
    return {evento: [{'hooks': [{'type': 'command', 'command': f'/usr/bin/python3 -I -S {bridge}',
                                  'timeout': 40, 'statusMessage': f'Synapsis: {evento}'}]}]
            for evento in EVENTS}


def prepare(config_dir):
    hp, cp = config_dir / 'hooks.json', config_dir / 'config.toml'
    hooks = json.loads(hp.read_text()) if hp.exists() else {'hooks': {}}
    config = cp.read_text() if cp.exists() else ''
    tomllib.loads(config)
    template = hooks_template()

    def es_neuromapa(h):
        # Reconoce instalaciones de esta herramienta sin importar el nombre que tenía
        # entonces ("Neuromapa") o el de ahora ("Synapsis"), para no duplicar al migrar.
        mensaje = str(h.get('statusMessage', ''))
        return mensaje.startswith('Neuromapa: ') or mensaje.startswith('Synapsis: ') or \
            ('bridge.py' in h.get('command', '') and ('Neuromapa' in mensaje or 'Synapsis' in mensaje))

    for evento, grupos in template.items():
        existentes = hooks.setdefault('hooks', {}).get(evento, [])
        hooks['hooks'][evento] = [g for g in existentes
                                   if not any(es_neuromapa(h) for h in g.get('hooks', []))] + grupos
    parsed = tomllib.loads(config)
    if 'neuromapa' in parsed.get('mcp_servers', {}):
        actual = parsed['mcp_servers']['neuromapa']
        if str(BASE / 'mcp.py') not in actual.get('args', []):
            raise ValueError('Ya hay un servidor MCP "neuromapa" con otra configuración; no lo toqué.')
    else:
        config += ('\n[mcp_servers.neuromapa]\ncommand = "/usr/bin/python3"\nargs = '
                   + json.dumps(['-I', '-S', str(BASE / 'mcp.py')]) + '\nstartup_timeout_sec = 20\n\n'
                   '[mcp_servers.neuromapa.env]\n')
        for clave, valor in {'NEUROMAPA_ROOT': str(ROOT), 'NEUROMAPA_DATA': str(DATA),
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
        raise SystemExit(f'No encontré el motor de Synapsis en {ROOT}. Si clonaste synapsis completo (con '
                         'engine/ adentro) esto no debería pasar; si moviste el motor a otro lado, fijá '
                         'NEUROMAPA_ROOT a su ruta.')
    hp, cp, hooks, config = prepare(args.config_dir)
    if args.dry_run:
        print(f'Configuración válida: {len(EVENTS)} hooks y el servidor MCP. No se cambió ningún archivo.')
        return
    args.config_dir.mkdir(parents=True, exist_ok=True)
    backup = args.config_dir / 'neuromapa-backups' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True, mode=0o700)
    originales = {}
    for ruta in (hp, cp):
        originales[ruta] = ruta.read_bytes() if ruta.exists() else None
        if originales[ruta] is not None:
            (backup / ruta.name).write_bytes(originales[ruta])
            (backup / ruta.name).chmod(0o600)
    try:
        for ruta, contenido in ((hp, hooks), (cp, config)):
            temporal = ruta.with_name(ruta.name + '.neuromapa.tmp')
            temporal.write_text(contenido, encoding='utf-8')
            temporal.chmod(0o600)
            os.replace(temporal, ruta)
    except Exception:
        for ruta, valor in originales.items():
            if valor is not None:
                ruta.write_bytes(valor)
            elif ruta.exists():
                ruta.unlink()
        raise
    print('Synapsis instalado para Codex. Copia de seguridad en: ' + str(backup))
    comun.anotar_ubicacion()
    print('Reiniciá Codex y confiá los hooks nuevos con /hooks en la CLI.')


if __name__ == '__main__':
    main()
