#!/usr/bin/env python3
"""Use Neuromapa tools while Codex lifecycle hooks own activity tracking."""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import comun

root = comun.raiz_motor()
os.environ.setdefault('CLAUDE_PLUGIN_DATA', str(comun.carpeta_datos()))
sys.path.insert(0, str(root))
import conector_mcp

# The original fallback tracker is for clients without lifecycle hooks.
# In Codex it would create an unrelated app session with no Stop event.
conector_mcp.anotar = lambda *args, **kwargs: None

if __name__ == '__main__':
    conector_mcp.main()
