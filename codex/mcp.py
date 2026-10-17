#!/usr/bin/env python3
"""Compatibility entrypoint forwarding to Synopsis's shared MCP server."""
import runpy
from pathlib import Path

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).resolve().parent.parent / 'mcp_entry.py'), run_name='__main__')
