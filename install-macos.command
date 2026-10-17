#!/bin/sh
set -eu
synopsis_root=$(CDPATH= cd "$(dirname "$0")" && pwd)
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Synopsis necesita Python 3.11 o superior: https://www.python.org/downloads/macos/' >&2
    exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'; then
    printf '%s\n' 'El Python disponible es anterior a 3.11. Instala una versión compatible.' >&2
    exit 1
fi
exec python3 -B "$synopsis_root/bin/synopsis" install "$@"
