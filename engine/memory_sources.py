"""Discover requested project memories and track changes without rescanning content."""
import hashlib
from pathlib import Path


def prepare_project(project):
    import cerebro
    import buscador
    from conector_mcp import carpeta_memoria_de
    from project_identity import canonical_project
    root = Path(canonical_project(str(project)))
    memory = carpeta_memoria_de(str(root))
    if not memory.is_dir():
        return
    for source in cerebro.FUENTES:
        if not any(Path(path).resolve() == memory.resolve() and source.get('memoria_por_raiz', {}).get(path, source.get('memoria'))
                   for path, _, _ in source['raices']):
            continue
        assigned = source.get('proyecto')
        from project_identity import owner
        if assigned and Path(assigned).resolve() != root and owner(memory) != str(root):
            raise ValueError('La fuente de memoria está asignada a otro proyecto.')
        return
    source = dict(id='project-memory-' + hashlib.sha256(str(root).encode()).hexdigest(),
                  nombre=root.name + ' Memory', memoria=True, proyecto=str(root), foco=True,
                  raices=[(str(memory), False, '')])
    cerebro.FUENTES.append(source)
    buscador.ALCANCE = tuple(source['id'] for source in cerebro.FUENTES if source.get('foco'))


def generations():
    import cerebro
    result = []
    for source in cerebro.FUENTES:
        for root, _, _ in source['raices']:
            if not source.get('memoria_por_raiz', {}).get(root, source.get('memoria')):
                continue
            marker = Path(root) / '.synopsis/generation'
            try:
                state = marker.stat()
                signature = (state.st_mtime_ns, state.st_size)
            except OSError:
                signature = None
            result.append((source['id'], str(root), signature))
    return result
