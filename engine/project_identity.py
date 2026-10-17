"""Project identities independent of IDE directory slugs; reuse owned memories in place."""
import contextlib
import hashlib
import json
import os
from pathlib import Path

from archivos import escribir_atomico, tomar_candado, soltar_candado


class ProjectIdentityConflict(ValueError):
    pass


def canonical_project(project):
    if not isinstance(project, str) or not project or not Path(project).is_absolute() or len(project) > 4000:
        raise ValueError('El proyecto debe ser una ruta absoluta de hasta 4000 caracteres.')
    from workspace_registry import discover
    return os.path.normcase(discover(project) or str(Path(project).resolve()))


def project_key(project):
    return hashlib.sha256(canonical_project(project).encode('utf-8')).hexdigest()


def data_root():
    for name in ('SYNOPSIS_DATA', 'CLAUDE_PLUGIN_OPTION_CARPETA_DATOS', 'CLAUDE_PLUGIN_DATA'):
        value = os.environ.get(name, '').strip()
        if value:
            return Path(value).expanduser().resolve()
    return Path.home() / '.local/share/synopsis'


def canonical_memory(project, root=None):
    return Path(root or data_root()) / 'projects' / project_key(project) / 'memory'


def _json(path):
    if path.is_symlink():
        raise ProjectIdentityConflict('La identidad del proyecto no admite manifiestos simbólicos.')
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ProjectIdentityConflict('El manifiesto de identidad no es un objeto válido.')
    return value


def owner(folder):
    folder = Path(folder).resolve()
    private = folder / '.synopsis'
    if private.is_symlink():
        raise ProjectIdentityConflict('La identidad de memoria debe estar en una carpeta regular.')
    marker = private / 'project.json'
    if not marker.exists() and not marker.is_symlink():
        return None
    data = _json(marker)
    project = canonical_project(data.get('project'))
    if data.get('key') != project_key(project):
        raise ProjectIdentityConflict('La huella de identidad no coincide con su proyecto.')
    return project


def note_owner(path):
    """An explicit binding wins over a stale or incorrect search-source assignment."""
    for parent in Path(path).resolve().parents:
        marker = parent / '.synopsis/project.json'
        if marker.exists() or marker.is_symlink() or (parent / '.synopsis').is_symlink():
            return owner(parent)
    return None


def configured_memories():
    # Read explicit ownership only. An IDE's lossy directory name is not proof.
    import configuracion
    path = configuracion.archivo()
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(raw, dict):
        raise ProjectIdentityConflict('La configuración debe ser un objeto JSON.')
    claims = []
    for source in configuracion.fuentes_de(raw, path.parent):
        assigned = source.get('proyecto')
        if not assigned:
            continue
        for folder, _, _ in source['raices']:
            if source.get('memoria_por_raiz', {}).get(folder, source.get('memoria')):
                claims.append((Path(folder).resolve(), canonical_project(assigned)))
    return claims


def _assert_owner(folder, project, claims):
    assigned = {claim for path, claim in claims if path == folder}
    actual = owner(folder)
    if assigned - {project} or actual and actual != project:
        raise ProjectIdentityConflict('La carpeta de memoria pertenece o está asignada a otro proyecto.')


def _location(project):
    return data_root() / 'projects' / project_key(project) / 'location.json'


def _manifest_folder(path, project):
    data = _json(path)
    if data.get('project') != project or data.get('key') != project_key(project):
        raise ProjectIdentityConflict('El manifiesto pertenece a otra identidad de proyecto.')
    value = data.get('memory')
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise ProjectIdentityConflict('La ubicación de memoria debe ser absoluta.')
    return Path(value).resolve()


def _intent(project):
    path = _location(project).with_name('location.pending.json')
    return _manifest_folder(path, project) if path.exists() or path.is_symlink() else None


def _registered(project):
    path = _location(project)
    if not path.exists() and not path.is_symlink():
        return None
    folder = _manifest_folder(path, project)
    if owner(folder) != project:
        raise ProjectIdentityConflict('La ubicación registrada perdió su propietario; revisa el manifiesto.')
    return folder


def _target(project, claims):
    candidates = {path for path, assigned in claims if assigned == project}
    if len(candidates) > 1:
        raise ProjectIdentityConflict('Hay varias memorias asignadas al proyecto; usa memory-location para elegir el destino existente.')
    if candidates:
        return next(iter(candidates))
    legacy = _legacy_memory(project)
    if legacy.is_dir() and owner(legacy) == project:
        return legacy.resolve()
    return canonical_memory(project).resolve()


@contextlib.contextmanager
def _lock(path):
    if path.parent.is_symlink() or path.is_symlink():
        raise ProjectIdentityConflict('El bloqueo de identidad debe ser regular.')
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    handle = tomar_candado(path, espera=5)
    if handle is None:
        raise ProjectIdentityConflict('Otra vinculación de memoria está en curso; vuelve a intentar.')
    try:
        yield
    finally:
        soltar_candado(handle)


def bind(project, folder):
    """Adopt a user/config-assigned folder in place; never copy, move or merge notes."""
    project = canonical_project(project)
    folder = Path(folder).expanduser()
    if not folder.is_absolute():
        raise ValueError('La carpeta de memoria debe ser absoluta.')
    folder = folder.resolve()
    with _lock(data_root() / 'projects/identity.lock'):
        registered = _registered(project)
        pending = _intent(project)
        if pending and pending != folder:
            raise ProjectIdentityConflict('Hay una vinculación pendiente a otra carpeta; resuélvela antes de cambiar de destino.')
        if registered and registered != folder:
            raise ProjectIdentityConflict('El proyecto ya tiene otra memoria; no se cambia ni se mezclan destinos automáticamente.')
        _assert_owner(folder, project, configured_memories())
        # This second lock also serializes owners using different SYNOPSIS_DATA roots.
        with _lock(folder / '.synopsis/write.lock'):
            _assert_owner(folder, project, configured_memories())
            marker = dict(version=1, project=project, key=project_key(project))
            private = folder / '.synopsis'
            if private.is_symlink():
                raise ProjectIdentityConflict('La identidad debe residir en una carpeta regular.')
            import configuracion
            manifest = dict(marker, memory=str(folder), configuration=str(configuracion.archivo().resolve()))
            intent = _location(project).with_name('location.pending.json')
            _publish(intent, manifest)
            _publish(private / 'project.json', marker)
            _publish(_location(project), manifest)
            intent.unlink(missing_ok=True)
    return folder


def _publish(path, data):
    # The intent is durable before ownership/pointer publication; retries keep the same folder.
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if path.is_symlink():
        raise ProjectIdentityConflict('No se reemplazan manifiestos simbólicos.')
    escribir_atomico(path, json.dumps(data, ensure_ascii=False, sort_keys=True) + '\n')
    path.chmod(0o600)
    with path.open('rb') as stream:
        os.fsync(stream.fileno())
    if os.name != 'nt':
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def resolve_memory(project):
    project = canonical_project(project)
    from workspace_registry import prepare, remember, legacy_evidence, request_binding
    workspace = prepare(project)
    if workspace and workspace.get('previous') and workspace['previous']['project'] != project:
        _relocate(workspace)
    registered = _registered(project)
    if registered:
        remember(workspace, registered)
        return registered
    claims = configured_memories()
    pending = _intent(project)
    candidates = [path for path, assigned in claims if assigned == project]
    if not pending and len(set(candidates)) > 1:
        request_binding(project, list(dict.fromkeys(candidates)))
        raise ProjectIdentityConflict('Hay varias memorias asignadas al proyecto. Elige una desde el panel de vinculación del mapa.')
    folder = pending or _target(project, claims)
    legacy = _legacy_memory(project)
    if (not pending and legacy.is_dir() and legacy.resolve() != folder
            and owner(legacy) is None and folder == canonical_memory(project).resolve()):
        if legacy_evidence(project, legacy):
            folder = legacy.resolve()
        else:
            request_binding(project, legacy)
            raise ProjectIdentityConflict('Existe memoria heredada sin propietario explícito. Abre synopsis para elegir su vinculación en el mapa.')
    _assert_owner(folder, project, claims)
    result = bind(project, folder)
    remember(workspace, result)
    return result


def _relocate(workspace):
    """Same marker object at a new location; preserve storage, revisions and cycle IDs."""
    previous = workspace['previous']
    old, new = previous['project'], workspace['project']
    folder = Path(previous['memory'])
    if folder.is_relative_to(old):
        folder = Path(new) / folder.relative_to(old)
    with _lock(data_root() / 'projects/identity.lock'):
        with _lock(folder / '.synopsis/write.lock'):
            actual = owner(folder)
            if actual not in (old, new):
                raise ProjectIdentityConflict('La memoria movida tiene otro propietario.')
            marker = dict(version=1, project=new, key=project_key(new))
            database = folder / '.synopsis/memory.sqlite3'
            if database.is_symlink():
                raise ProjectIdentityConflict('El diario de memoria no puede ser un enlace simbólico.')
            import configuracion
            manifest = dict(marker, memory=str(folder), configuration=str(configuracion.archivo().resolve()))
            intent = _location(new).with_name('location.pending.json')
            _publish(intent, manifest)
            _publish(folder / '.synopsis/project.json', marker)
            _publish(_location(new), manifest)
            intent.unlink(missing_ok=True)
            # Old locations cannot continue resolving this memory as their own.
            old_location = data_root() / 'projects' / hashlib.sha256(old.encode()).hexdigest() / 'location.json'
            if old_location != _location(new):
                old_location.unlink(missing_ok=True)
            if database.is_file():
                import sqlite3
                with sqlite3.connect(database) as db:
                    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    if 'cycle_turns' in tables:
                        db.execute('UPDATE cycle_turns SET project=? WHERE project=?', (new, old))



def _legacy_memory(project):
    old_slug = project.rstrip('/\\').replace('\\', '-').replace('/', '-').replace(':', '-') or '-raiz'
    claude = Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude').expanduser()
    return claude / 'projects' / old_slug / 'memory'


def describe(project, folder=None):
    """A read-only preview exposes ambiguous legacy data without assigning it."""
    project = canonical_project(project)
    registered = _registered(project)
    claims = configured_memories()
    if folder and not Path(folder).expanduser().is_absolute():
        raise ValueError('La carpeta de memoria debe ser absoluta.')
    target = Path(folder).expanduser().resolve() if folder else registered or _intent(project) or _target(project, claims)
    _assert_owner(target, project, claims)
    legacy = _legacy_memory(project)
    workspace = None
    from workspace_registry import _read
    for path in (data_root() / 'workspaces').glob('*.json'):
        try:
            record = _read(path)
        except (ValueError, OSError):
            continue
        if record.get('project') == project:
            workspace = {key: record.get(key) for key in ('id', 'group', 'marker')}
            break
    return dict(project=project, key=project_key(project), memory=str(target), registered=registered is not None,
                workspace=workspace,
                legacy_unassigned=str(legacy) if legacy.is_dir() and legacy.resolve() != target and owner(legacy) is None else None,
                note='Las memorias existentes se vinculan sin copiarlas. Un nombre de carpeta no acredita propiedad.')


def registered_memories(configuration=None):
    """Read verified bindings for fresh map/search processes; no directory creation."""
    records = []
    profile = str(Path(configuration).resolve()) if configuration is not None else None
    for path in sorted((data_root() / 'projects').glob('*/location.json')):
        try:
            data = _json(path)
            if profile is not None and data.get('configuration') != profile:
                continue
            project = canonical_project(data.get('project'))
            if path.parent.name != project_key(project):
                continue
            folder = _manifest_folder(path, project)
            if owner(folder) == project and folder.is_dir():
                records.append(dict(project=project, key=project_key(project), memory=str(folder)))
        except (ValueError, OSError):
            # A corrupt binding must never become a search source.
            continue
    return records
