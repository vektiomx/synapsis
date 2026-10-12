"""Resolución compartida de rutas para los bridges: dónde está el motor de Synapsis
y dónde guarda sus datos (el registro en vivo, el caché del mapa, etc).

Por defecto usa el motor vendorizado en engine/ (así synapsis no depende de tener
Claude Code instalado). La carpeta de datos (registro en vivo, caché del mapa) es
siempre la misma, exista o no Claude Code todavía: ~/.claude/plugins/data/neuromapa-…
Es solo una carpeta en disco, no requiere la app — así que si alguien instala Claude
Code después y le suma el plugin "neuromapa", lo encuentra con el historial ya puesto,
sin migrar nada, y el mapa en vivo muestra la actividad de los tres por igual. Ambas
rutas se pueden fijar a mano con las variables de entorno NEUROMAPA_ROOT y
NEUROMAPA_DATA.
"""
import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent
ENGINE_PREDETERMINADO = REPO / 'engine'
CARPETA_DATOS_PREDETERMINADA = Path.home() / '.claude' / 'plugins' / 'data' / 'neuromapa-neuromapa'
PUNTERO = Path.home() / '.synapsis.json'


def raiz_motor():
    personalizada = os.environ.get('NEUROMAPA_ROOT')
    return Path(personalizada) if personalizada else ENGINE_PREDETERMINADO


def carpeta_datos():
    personalizada = os.environ.get('NEUROMAPA_DATA')
    if personalizada:
        return Path(personalizada)
    base = Path.home() / '.claude' / 'plugins' / 'data'
    candidatos = sorted(base.glob('neuromapa*')) if base.is_dir() else []
    return candidatos[0] if candidatos else CARPETA_DATOS_PREDETERMINADA


def anotar_ubicacion():
    """Deja un puntero en ~/.synapsis.json con la ruta real del repo, para que otros
    proyectos (ej. el dev:all de otra app) lo encuentren sin tener que adivinar la
    carpeta ni leer la configuración interna de Claude Code/Codex/Antigravity."""
    try:
        PUNTERO.write_text(json.dumps({'repo': str(REPO)}, indent=2) + '\n', encoding='utf-8')
    except OSError:
        pass


def instalar_skill_memoria(carpeta_skills):
    """Copia el skill que le enseña a la herramienta a guardar y consultar memoria por
    su cuenta (ver skill_memoria/SKILL.md) a su carpeta global de skills. No requiere
    el conector MCP: guardar una nota es solo escribir un .md, cualquier herramienta
    con edición de archivos ya puede hacerlo."""
    origen = REPO / 'skill_memoria' / 'SKILL.md'
    destino = Path(carpeta_skills) / 'memoria-synapsis' / 'SKILL.md'
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(origen.read_text(encoding='utf-8'), encoding='utf-8')
    return destino


def instalar_comando(dry_run=False):
    """Expose the CLI without replacing unrelated user commands."""
    destino = Path.home() / '.local' / 'bin' / 'synapsis'
    origen = REPO / 'bin' / 'synapsis'
    if destino.exists() or destino.is_symlink():
        if not destino.is_symlink() or destino.resolve() != origen:
            raise RuntimeError(f'Ya existe otro comando en {destino}; no lo reemplacé.')
    if dry_run:
        print(f'Crearía el comando {destino} → {origen}')
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    origen.chmod(origen.stat().st_mode | 0o111)
    if not destino.is_symlink():
        destino.symlink_to(origen)
    print('Para abrir el mapa: synapsis abrir')
    if str(destino.parent) not in os.environ.get('PATH', '').split(os.pathsep):
        print(f'Agregá {destino.parent} al PATH de tu terminal para usar el comando.')
    return destino
