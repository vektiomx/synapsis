"""Copy persistent state into an independent installation; never copy live keys."""
import os
import json
import shutil
import tempfile
from pathlib import Path

FILES = ('config.json', 'aprendido.json', 'sugerencias.json', 'hechos.json', 'descartados.json', 'problemas.json')
DIRECTORIES = ('historial',)


def migrate(source, destination, apply=False):
    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser().absolute()
    if not (source / 'config.json').is_file():
        raise ValueError('La carpeta de origen debe contener config.json.')
    if not isinstance(json.loads((source / 'config.json').read_text(encoding='utf-8')), dict):
        raise ValueError('La configuración de origen debe ser un objeto JSON.')
    if destination.exists() or destination.is_symlink():
        raise ValueError('El destino ya existe; no se combina ni reemplaza información automáticamente.')
    if destination.is_relative_to(source):
        raise ValueError('El destino debe estar fuera de la carpeta de origen.')
    selected = [source / name for name in FILES + DIRECTORIES if (source / name).exists()]
    for path in selected:
        if path.is_symlink() or (path.is_dir() and any(p.is_symlink() for p in path.rglob('*'))):
            raise ValueError('No se migran enlaces simbólicos; verifica los archivos de origen.')
    result = dict(source=str(source), destination=str(destination), apply=apply,
                  selected=[p.name for p in selected], excludes='Sesiones, claves del mapa, procesos y cachés')
    if not apply:
        return result
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.synopsis-migrate-', dir=destination.parent))
    try:
        for path in selected:
            target = staging / path.name
            if path.is_dir():
                shutil.copytree(path, target)
            else:
                shutil.copyfile(path, target)
        for path in staging.rglob('*'):
            path.chmod(0o700 if path.is_dir() else 0o600)
        if destination.exists() or destination.is_symlink():
            raise ValueError('El destino apareció durante la migración; no se reemplazó.')
        # Rename publishes a complete destination; the source remains untouched.
        os.rename(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return result
