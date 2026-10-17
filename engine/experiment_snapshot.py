"""One deterministic, bounded file policy for isolated snapshots and drift checks."""
import json
import os
from pathlib import Path

from evidence_guard import read_regular
from memory_store import digest


def files(project):
    root = Path(project).resolve()
    total = count = 0
    ignored = {'.git', '.synopsis', '.venv', 'venv', 'node_modules', 'vendor', '__pycache__'}
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(name for name in dirs if not name.startswith('.') and name not in ignored and not (Path(directory) / name).is_symlink())
        for name in sorted(names):
            path = Path(directory) / name
            if name.startswith('.') or path.is_symlink():
                continue
            if path.suffix.lower() not in ('.py', '.json', '.toml', '.txt', '.md', '.yaml', '.yml', '.ini', '.cfg'):
                continue
            try:
                text = read_regular(path)
            except (ValueError, OSError, UnicodeError):
                continue
            total += len(text.encode('utf-8'))
            count += 1
            if total > 32_000_000 or count > 3000:
                raise ValueError('experiment_snapshot_limit')
            yield path.relative_to(root).as_posix(), text


def fingerprint(project):
    manifest = [dict(path=path, sha256=digest(text)) for path, text in files(project)]
    return digest(json.dumps(manifest, sort_keys=True))
