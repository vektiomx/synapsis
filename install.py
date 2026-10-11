#!/usr/bin/env python3
"""Atajo histórico: usa `python3 bin/synapsis install` (o `synapsis install claude|codex|antigravity`).

Se mantiene por compatibilidad; instala en todo lo que detecte, igual que antes.
"""
import subprocess
import sys
from pathlib import Path

if __name__ == '__main__':
    raise SystemExit(subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / 'bin' / 'synapsis'), 'install'] + sys.argv[1:]
    ).returncode)
