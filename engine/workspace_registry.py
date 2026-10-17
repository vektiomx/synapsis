"""Automatic workspace discovery. Metadata identifies locations; names never grant ownership."""
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

ID = re.compile(r'^[a-f0-9]{32}$')


def _read(path):
    path = Path(path)
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('Workspace metadata must be regular.')
    if path.stat().st_size > 16000:
        raise ValueError('Workspace metadata exceeds its limit.')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except RecursionError as error:
        raise ValueError('Workspace metadata is too deeply nested.') from error
    if not isinstance(value, dict):
        raise ValueError('Invalid workspace metadata.')
    return value


def _valid_record(record):
    return (isinstance(record.get('id'), str) and bool(ID.fullmatch(record['id']))
            and isinstance(record.get('project'), str) and Path(record['project']).is_absolute()
            and isinstance(record.get('memory'), str) and Path(record['memory']).is_absolute())


def git_directory(root):
    entry = Path(root) / '.git'
    if entry.is_symlink():
        return None
    if entry.is_dir() and (entry / 'HEAD').is_file():
        return entry.resolve()
    if entry.is_file() and entry.stat().st_size <= 4000:
        value = entry.read_text(encoding='utf-8').strip()
        if value.startswith('gitdir:'):
            target = (Path(root) / value[7:].strip()).resolve()
            if (target / 'HEAD').is_file():
                return target
    return None


def discover(cwd, roots=None, active_path=None):
    """No disk scan. Prefer the active Git root, explicit IDE roots, or known ancestors."""
    if not isinstance(cwd, str) or not Path(cwd).is_absolute():
        return None
    path = Path(cwd).resolve()
    if not path.is_dir():
        return None
    choices = [Path(r).resolve() for r in roots or [] if isinstance(r, str) and Path(r).is_absolute() and Path(r).is_dir()]
    if active_path and isinstance(active_path, str) and Path(active_path).is_absolute():
        active = Path(active_path).resolve()
        matching = [r for r in choices if active == r or r in active.parents]
        if matching:
            path = max(matching, key=lambda r: len(r.parts))
    enclosing = [r for r in choices if path == r or r in path.parents]
    boundary = max(enclosing, key=lambda r: len(r.parts)) if enclosing else None
    for parent in (path, *path.parents):
        if git_directory(parent):
            return str(parent)
        if (parent / '.synopsis/workspace.json').is_file():
            return str(parent)
        if boundary == parent:
            return str(parent)
    # Registered roots also work for read-only projects, without a marker in the repo.
    from project_identity import data_root
    candidates = []
    for record in (data_root() / 'workspaces').glob('*.json'):
        try:
            value = _read(record)
            if not _valid_record(value):
                continue
            root = Path(value['project'])
            if root == path or root in path.parents:
                candidates.append(root)
        except (OSError, ValueError, KeyError):
            continue
    if candidates:
        return str(max(candidates, key=lambda r: len(r.parts)))
    if boundary:
        return str(boundary)
    for parent in (path, *path.parents):
        if any((parent / name).is_file() for name in ('pyproject.toml', 'package.json', 'composer.json', 'Cargo.toml', 'go.mod', 'AGENTS.md')):
            return str(parent)
    return str(path)


def _marker(root):
    git = git_directory(root)
    return git / 'synopsis-workspace.json' if git else Path(root) / '.synopsis/workspace.json'


def _stamp(path):
    value = path.stat()
    return [value.st_dev, value.st_ino]


def prepare(project):
    """Return an existing location before binding. Copied markers never merge two roots."""
    from project_identity import data_root, _lock, _publish, ProjectIdentityConflict
    root = Path(project)
    if not root.is_dir():
        return None  # Legacy public API permits virtual project paths.
    marker = _marker(root)
    registry = data_root() / 'workspaces'
    try:
        with _lock(registry / 'registry.lock'):
            metadata = _read(marker) if marker.exists() or marker.is_symlink() else None
            if metadata and (not isinstance(metadata.get('id'), str) or not ID.fullmatch(metadata['id'])):
                raise ProjectIdentityConflict('Identificador de workspace inválido.')
            fallback = None
            if metadata is None:
                for path in registry.glob('*.json'):
                    try:
                        candidate = _read(path)
                    except (OSError, ValueError):
                        continue
                    if not _valid_record(candidate):
                        continue
                    if candidate.get('marker') is None and (candidate.get('project') == project or
                            candidate.get('root_identity') == _stamp(root) and not Path(candidate['project']).exists()):
                        fallback = candidate
                        break
            key = metadata['id'] if metadata else fallback['id'] if fallback else uuid.uuid4().hex
            record_path = registry / (key + '.json')
            record = _read(record_path) if record_path.exists() else None
            if record is not None and (not _valid_record(record) or record['id'] != key):
                raise ProjectIdentityConflict('El registro del workspace es inválido.')
            if record and record.get('project') != project:
                old = Path(record['project'])
                same_object = (record.get('marker_identity') == _stamp(marker) if marker.exists()
                               else record.get('root_identity') == _stamp(root))
                if not old.exists() and not same_object:
                    folder = Path(record['memory'])
                    if folder.is_relative_to(old):
                        folder = root / folder.relative_to(old)
                    request_binding(project, folder, relocation=record)
                    raise ProjectIdentityConflict('El proyecto cambió de ubicación y necesita confirmar su identidad en el mapa.')
                if old.exists():
                    # A directory copy carries a copied marker, not the same workspace.
                    key, record = uuid.uuid4().hex, None
                    metadata = None
            group = None
            git = git_directory(root)
            if git:
                common = git
                if (git / 'commondir').is_file():
                    common = (git / (git / 'commondir').read_text().strip()).resolve()
                group = hashlib.sha256(str(common).encode()).hexdigest()
            if not metadata:
                try:
                    _publish(marker, dict(version=1, id=key))
                except PermissionError:
                    # A read-only repository can still use a private local registry.
                    marker = None
            return dict(id=key, project=project, previous=record, marker=str(marker) if marker else None,
                        marker_identity=_stamp(marker) if marker else None, root_identity=_stamp(root), group=group)
    except (ValueError, OSError) as error:
        if isinstance(error, PermissionError):
            raise
        raise ProjectIdentityConflict('No se pudo validar la identidad del workspace.') from error


def remember(workspace, memory):
    if not workspace:
        return
    from project_identity import data_root, _lock, _publish
    with _lock(data_root() / 'workspaces/registry.lock'):
        record = {key: value for key, value in workspace.items() if key != 'previous'}
        record['memory'] = str(memory)
        path = data_root() / 'workspaces' / (workspace['id'] + '.json')
        if path.exists() and _read(path) == record:
            return
        _publish(path, record)


def legacy_evidence(project, folder):
    """Client-written cwd metadata, never note prose or the lossy directory slug."""
    roots = set()
    parent = Path(folder).parent
    files = sorted(parent.glob('*.jsonl'), key=lambda p: p.stat().st_mtime, reverse=True)
    if len(files) > 16:
        return False  # A bounded sample cannot settle conflicting historical owners.
    for path in files:
        if path.is_symlink():
            continue
        try:
            with path.open('rb') as stream:
                raw = stream.read(65536)
            for line in raw.splitlines()[:256]:
                try:
                    row = json.loads(line)
                    cwd = row.get('cwd') if isinstance(row, dict) else None
                    if isinstance(cwd, str) and Path(cwd).is_absolute():
                        root = discover(cwd)
                        roots.add(root or os.path.normcase(str(Path(cwd).resolve())))
                except (ValueError, OSError, RecursionError):
                    continue
        except OSError:
            continue
    return roots == {project}


def folder_signature(folder):
    folder = Path(folder)
    entries = [(p.name, p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(folder.glob('*.md'))]
    from project_identity import owner
    return hashlib.sha256(json.dumps([str(folder.resolve()), _stamp(folder), owner(folder), entries]).encode()).hexdigest()


def request_binding(project, folder, relocation=None):
    from project_identity import data_root, project_key, _publish
    path = data_root() / 'binding-requests' / (project_key(project) + '.json')
    previous = _read(path) if path.exists() else {}
    folders = folder if isinstance(folder, list) else [folder]
    choices = [dict(folder=str(path), signature=folder_signature(path)) for path in folders]
    signature = hashlib.sha256(json.dumps(choices, sort_keys=True).encode()).hexdigest()
    if previous.get('signature') == signature and previous.get('project') == project:
        return
    _publish(path, dict(id=uuid.uuid4().hex, project=project, choices=choices, signature=signature,
                       relocation=relocation))


def pending():
    from project_identity import data_root, project_key
    result = []
    for path in (data_root() / 'binding-requests').glob('*.json'):
        try:
            record = _read(path)
            if path.stem != project_key(record['project']) or not ID.fullmatch(record['id']):
                continue
            result.append(record)
        except (ValueError, OSError, KeyError):
            continue
    return result


def choose(request_id, choice):
    """Authenticated UI selects a stored candidate; no caller-supplied filesystem paths."""
    from project_identity import data_root, bind, canonical_memory, project_key, ProjectIdentityConflict, _lock
    if not isinstance(request_id, str) or not ID.fullmatch(request_id) or not isinstance(choice, str) or not re.fullmatch(r'existing(?::[0-9]{1,3})?|independent', choice):
        raise ValueError('Selección inválida.')
    with _lock(data_root() / 'binding-requests/choice.lock'):
        matches = [row for row in pending() if row['id'] == request_id]
        if len(matches) != 1:
            raise ValueError('La solicitud ya se resolvió o cambió.')
        row = matches[0]
        choices = row['choices']
        for item in choices:
            if folder_signature(item['folder']) != item['signature']:
                request_binding(row['project'], [Path(item['folder']) for item in choices], row.get('relocation'))
                raise ProjectIdentityConflict('La memoria cambió; vuelve a revisar la vinculación.')
        number = int(choice.split(':')[1]) if ':' in choice else 0
        if number >= len(choices):
            raise ValueError('Selección inválida.')
        memory = Path(choices[number]['folder']) if choice.startswith('existing') else canonical_memory(row['project'])
        previous = row.get('relocation')
        if previous:
            metadata = _read(_marker(row['project']))
            registered = _read(data_root() / 'workspaces' / (previous['id'] + '.json'))
            if metadata.get('id') != previous['id'] or registered != previous or Path(previous['project']).exists():
                raise ProjectIdentityConflict('La identidad del proyecto cambió desde la vista previa.')
            if choice.startswith('existing'):
                from project_identity import _relocate
                workspace = dict(previous, project=row['project'], previous=previous,
                                 marker=str(_marker(row['project'])), marker_identity=_stamp(_marker(row['project'])))
                _relocate(workspace)
                remember(workspace, memory)
            else:
                from project_identity import _publish
                _publish(_marker(row['project']), dict(version=1, id=uuid.uuid4().hex))
        result = memory if previous and choice.startswith('existing') else bind(row['project'], memory)
        remember(prepare(row['project']), result)
        (data_root() / 'binding-requests' / (project_key(row['project']) + '.json')).unlink(missing_ok=True)
        return dict(project=row['project'], memory=str(result), bound=True)
