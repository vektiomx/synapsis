"""Shared, reversible installation of MCP, skills and host configuration."""
import datetime
import json
import os
import sys
from pathlib import Path

import comun


def mcp_definition(entry=None):
    from desktop_runtime import python_flags
    return dict(command=sys.executable, args=[*python_flags(), str(entry or comun.REPO / 'mcp_entry.py')],
                env=dict(SYNOPSIS_ROOT=str(comun.raiz_motor()), SYNOPSIS_DATA=str(comun.carpeta_datos()),
                         PYTHONDONTWRITEBYTECODE='1'))


def json_mcp(path):
    data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    servers = data.setdefault('mcpServers', {})
    expected = mcp_definition()
    current = servers.get('synopsis')
    if current and current != expected:
        owned = current.get('env', {}).get('SYNOPSIS_ROOT') and any(
            Path(arg).name in ('mcp.py', 'mcp_entry.py') for arg in current.get('args', []))
        if not owned:
            raise ValueError('Ya existe un MCP synopsis ajeno; no se reemplazó.')
    servers['synopsis'] = expected
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n'


def skill_files(root):
    return {Path(root) / 'memoria-synopsis/SKILL.md':
            (comun.REPO / 'skill_memoria/SKILL.md').read_text(encoding='utf-8')}


def install_files(files, backup_root, dry_run=False):
    """All plans are prepared first; a failed replacement restores earlier files."""
    if dry_run:
        return None
    sys.path.insert(0, str(comun.raiz_motor()))
    from archivos import escribir_atomico, tomar_candado, soltar_candado
    backup_root = Path(backup_root)
    backup_root.mkdir(parents=True, mode=0o700, exist_ok=True)
    lock = tomar_candado(backup_root / 'install.lock', espera=5)
    if lock is None:
        raise RuntimeError('Otra instalación está en curso; vuelve a intentar.')
    snapshots = {}
    applied = []
    try:
        # Resolve file symlinks without replacing the user's dotfile-manager links.
        files = {Path(path).resolve(): text for path, text in files.items()}
        snapshots = {path: path.read_bytes() if path.exists() else None for path in files}
        changed = {path: text for path, text in files.items() if snapshots[path] != text.encode('utf-8')}
        if not changed:
            return None
        backup = backup_root / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup.mkdir(mode=0o700)
        for number, path in enumerate(changed):
            if snapshots[path] is not None:
                saved = backup / f'{number}-{path.name}'
                saved.write_bytes(snapshots[path])
                saved.chmod(0o600)
        for path, text in changed.items():
            current = path.read_bytes() if path.exists() else None
            if current != snapshots[path]:
                raise RuntimeError('La configuración cambió durante la instalación; vuelve a intentar.')
            path.parent.mkdir(parents=True, exist_ok=True)
            escribir_atomico(path, text)
            applied.append(path)
            path.chmod(0o600)
        return backup
    except BaseException:
        for path in reversed(applied):
            if snapshots[path] is None:
                path.unlink(missing_ok=True)
            else:
                escribir_atomico(path, snapshots[path])
        raise
    finally:
        soltar_candado(lock)


def read_jsonc(path):
    """Read configuration comments/trailing commas without changing the original bytes."""
    text = Path(path).read_text(encoding='utf-8')
    clean, index, quoted = [], 0, False
    while index < len(text):
        char = text[index]
        if quoted:
            clean.append(char)
            if char == '\\' and index + 1 < len(text):
                index += 1
                clean.append(text[index])
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            clean.append(char)
        elif text[index:index + 2] == '//':
            end = text.find('\n', index)
            index = len(text) if end < 0 else end
            clean.append('\n')
            continue
        elif text[index:index + 2] == '/*':
            end = text.find('*/', index + 2)
            if end < 0:
                raise ValueError('Comentario JSONC sin cierre.')
            index = end + 2
            clean.append(' ')
            continue
        else:
            clean.append(char)
        index += 1
    text = ''.join(clean)
    clean, index, quoted = [], 0, False
    while index < len(text):
        char = text[index]
        if quoted:
            clean.append(char)
            if char == '\\' and index + 1 < len(text):
                index += 1
                clean.append(text[index])
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            clean.append(char)
        elif char == ',' and text[index + 1:].lstrip().startswith(('}', ']')):
            pass
        else:
            clean.append(char)
        index += 1
    return json.loads(''.join(clean))
