"""Rutas compartidas de Synopsis: motor local y estado privado del usuario.

El motor predeterminado vive en engine/; el estado, en ~/.local/share/synopsis.
SYNOPSIS_ROOT y SYNOPSIS_DATA permiten definir ubicaciones independientes.
"""
import json
import os
import sys
from pathlib import Path

if sys.platform=='win32':
    for stream in (sys.stdin,sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')

REPO = Path(__file__).resolve().parent
ENGINE_PREDETERMINADO = REPO / 'engine'
CARPETA_DATOS_PREDETERMINADA = Path.home() / '.local' / 'share' / 'synopsis'
PUNTERO = Path.home() / '.synopsis.json'


def raiz_motor():
    personalizada = os.environ.get('SYNOPSIS_ROOT')
    return Path(personalizada) if personalizada else ENGINE_PREDETERMINADO


def carpeta_datos():
    personalizada = os.environ.get('SYNOPSIS_DATA')
    if personalizada:
        return Path(personalizada)
    return CARPETA_DATOS_PREDETERMINADA


def anotar_ubicacion():
    """Deja un puntero en ~/.synopsis.json con la ruta real del repo, para que otros
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
    destino = Path(carpeta_skills) / 'memoria-synopsis' / 'SKILL.md'
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(origen.read_text(encoding='utf-8'), encoding='utf-8')
    return destino


def configurar_path(dry_run=False):
    """Persist the user command directory for login and interactive shells."""
    casa = Path.home()
    shell = Path(os.environ.get('SHELL', '/bin/bash')).name
    archivos = {casa / '.profile'}
    for nombre in ('.bashrc', '.bash_profile', '.zshrc', '.zprofile'):
        if (casa / nombre).exists():
            archivos.add(casa / nombre)
    if shell == 'bash':
        archivos.add(casa / '.bashrc')
    elif shell == 'zsh':
        zdir = Path(os.environ.get('ZDOTDIR') or casa)
        archivos.update((zdir / '.zprofile', zdir / '.zshrc'))
    bloque = ('\n# Synopsis: comandos del usuario\n'
              'case ":$PATH:" in\n'
              '    *":$HOME/.local/bin:"*) ;;\n'
              '    *) export PATH="$HOME/.local/bin:$PATH" ;;\n'
              'esac\n')
    for archivo in sorted(archivos):
        contenido = archivo.read_text(encoding='utf-8') if archivo.exists() else ''
        if bloque.strip() in contenido:
            continue
        if dry_run:
            print(f'Agregaría ~/.local/bin al PATH en {archivo}')
        else:
            archivo.parent.mkdir(parents=True, exist_ok=True)
            with archivo.open('a', encoding='utf-8') as stream:
                stream.write(bloque)
    if shell == 'fish':
        archivo = Path(os.environ.get('XDG_CONFIG_HOME') or casa / '.config') / 'fish/conf.d/synopsis.fish'
        contenido = 'fish_add_path --path "$HOME/.local/bin"\n'
        if archivo.exists() and archivo.read_text(encoding='utf-8') != contenido:
            raise RuntimeError(f'Ya existe otra configuración en {archivo}; no la reemplacé.')
        if dry_run:
            print(f'Configuraría el PATH en {archivo}')
        else:
            archivo.parent.mkdir(parents=True, exist_ok=True)
            archivo.write_text(contenido, encoding='utf-8')


def instalar_comando(dry_run=False):
    """Expose a single CLI without replacing unrelated commands."""
    if sys.platform=='win32':
        from windows_install import install
        return install(dry_run)
    folder = Path.home() / '.local' / 'bin'
    destination = folder / 'synopsis'
    origin = REPO / 'bin' / 'synopsis'
    if destination.exists() or destination.is_symlink():
        if not destination.is_symlink() or destination.resolve() != origin:
            raise RuntimeError(f'Ya existe otro comando en {destination}; no lo reemplacé.')
    if dry_run:
        print(f'Crearía el comando {destination} → {origin}')
    else:
        folder.mkdir(parents=True, exist_ok=True)
        origin.chmod(origin.stat().st_mode | 0o111)
        if not destination.is_symlink():
            destination.symlink_to(origin)
    configurar_path(dry_run=dry_run)
    return destination
