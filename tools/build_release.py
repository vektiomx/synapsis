#!/usr/bin/env python3
"""Build a reproducible source archive, excluding state, credentials and caches."""
import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
EXCLUDED={'.git','.synopsis','__pycache__','.venv','venv','node_modules','synopsis-backups','.pytest_cache'}
EXECUTABLES={'bin/synopsis','engine/bin/synopsis','engine/scripts/python.sh','install-macos.command'}


def build(output):
    output=Path(output).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError('Escribe el archivo de entrega fuera del checkout.')
    files={}
    for path in sorted(ROOT.rglob('*')):
        relative=path.relative_to(ROOT)
        if set(relative.parts)&EXCLUDED or not path.is_file() or path.is_symlink() or path.suffix in ('.pyc','.pyo','.sqlite3','.log','.zip'):
            continue
        # Repository-owned examples only, never operational config or credentials.
        if path.name in ('.env','auth.json','credentials.json') or relative.as_posix()=='engine/config.json':
            continue
        files[relative.as_posix()]=path
    required={'LICENSE','README.md','bin/synopsis','engine/bin/synopsis','mcp_entry.py'}
    if not required<=files.keys():
        raise ValueError('Entrega incompleta.')
    manifest={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in files.items()}
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,path in files.items():
            info=zipfile.ZipInfo('synopsis/'+name,date_time=(2026,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=(stat.S_IFREG | (0o755 if name in EXECUTABLES or path.stat().st_mode & 0o111 else 0o644)) << 16
            archive.writestr(info,path.read_bytes())
        info=zipfile.ZipInfo('synopsis/SHA256SUMS.json',date_time=(2026,1,1,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED
        info.external_attr=(stat.S_IFREG|0o644)<<16
        archive.writestr(info,json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():
            raise ValueError('Archivo corrupto.')
    return dict(path=str(output),files=len(files),sha256=hashlib.sha256(output.read_bytes()).hexdigest(),bytes=output.stat().st_size)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.output)))
