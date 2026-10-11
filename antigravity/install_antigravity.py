#!/usr/bin/env python3
"""Instala el bridge de Synapsis para Antigravity. No pide contraseña ni sudo.

Usa el motor vendorizado en engine/ (no depende de tener Claude Code instalado). Si
querés usar otra copia, fijá NEUROMAPA_ROOT y NEUROMAPA_DATA antes de instalar.
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
EVENTOS = ('PreInvocation', 'PreToolUse', 'PostToolUse', 'PostInvocation', 'Stop')


def bloque(evento):
    bridge = str(BASE / 'bridge.py')
    comando = {'type': 'command', 'command': f'/usr/bin/python3 {bridge} {evento}', 'timeout': 10}
    if evento in ('PreToolUse', 'PostToolUse'):
        return [{'matcher': '*', 'hooks': [comando]}]
    return [comando]


def preparar(ruta_hooks):
    datos = json.loads(ruta_hooks.read_text()) if ruta_hooks.exists() else {}
    datos['neuromapa'] = {evento: bloque(evento) for evento in EVENTOS}
    return json.dumps(datos, indent=2) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--config-dir', type=Path, default=Path.home() / '.gemini' / 'config')
    args = parser.parse_args()
    if not (ROOT / 'hook_evento.py').is_file():
        raise SystemExit(f'No encontré el motor de Synapsis en {ROOT}. Si clonaste synapsis completo (con '
                         'engine/ adentro) esto no debería pasar; si moviste el motor a otro lado, fijá '
                         'NEUROMAPA_ROOT a su ruta.')
    ruta_hooks = args.config_dir / 'hooks.json'
    contenido = preparar(ruta_hooks)
    if args.dry_run:
        print(f'Configuración válida: {len(EVENTOS)} hooks en "neuromapa". No se cambió ningún archivo.')
        return
    args.config_dir.mkdir(parents=True, exist_ok=True)
    backup = args.config_dir / 'neuromapa-backups' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True, mode=0o700)
    original = ruta_hooks.read_bytes() if ruta_hooks.exists() else None
    if original is not None:
        (backup / 'hooks.json').write_bytes(original)
        (backup / 'hooks.json').chmod(0o600)
    try:
        temporal = ruta_hooks.with_name(ruta_hooks.name + '.neuromapa.tmp')
        temporal.write_text(contenido, encoding='utf-8')
        temporal.chmod(0o600)
        os.replace(temporal, ruta_hooks)
    except Exception:
        if original is not None:
            ruta_hooks.write_bytes(original)
        elif ruta_hooks.exists():
            ruta_hooks.unlink()
        raise
    print('Synapsis instalado para Antigravity. Copia de seguridad en: ' + str(backup))
    print('Reiniciá Antigravity para que cargue los hooks nuevos.')


if __name__ == '__main__':
    main()
