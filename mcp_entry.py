#!/usr/bin/env python3
"""Shared stdio MCP entrypoint for clients already connected through lifecycle hooks."""
import os
import sys

sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comun

os.environ.setdefault('CLAUDE_PLUGIN_DATA', str(comun.carpeta_datos()))
sys.path.insert(0, str(comun.raiz_motor()))
import conector_mcp

# Lifecycle hooks own activity tracking; MCP requests must not create duplicate chats.
conector_mcp.anotar = lambda *args, **kwargs: None

if __name__ == '__main__':
    conector_mcp.main()
