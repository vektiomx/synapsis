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
import os
from pathlib import Path

ENGINE_PREDETERMINADO = Path(__file__).resolve().parent / 'engine'
CARPETA_DATOS_PREDETERMINADA = Path.home() / '.claude' / 'plugins' / 'data' / 'neuromapa-neuromapa'


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
