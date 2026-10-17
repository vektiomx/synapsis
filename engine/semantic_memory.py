"""Optional real embeddings, cached per project. No implicit remote transfer."""
import contextlib
import hashlib
import json
import math
import os
import sqlite3
import time
from pathlib import Path

from model_provider import ProviderError, ollama_models, request_json

_DISCOVERY = (0, None)


def normalize(vector):
    if (not isinstance(vector, list) or not 2 <= len(vector) <= 8192 or
            any(type(x) not in (int, float) or not math.isfinite(x) for x in vector)):
        raise ProviderError('invalid_embedding')
    norm = math.sqrt(sum(x*x for x in vector))
    if not math.isfinite(norm) or norm < 1e-12:
        raise ProviderError('invalid_embedding')
    return [x / norm for x in vector]


class Embeddings:
    def __init__(self, provider, model, base, timeout=3):
        self.provider, self.model, self.base, self.timeout = provider, model, base, timeout
        self.identity = hashlib.sha256(json.dumps([provider, model, base]).encode()).hexdigest()

    def __call__(self, texts):
        key = os.environ.get('SYNOPSIS_EMBEDDING_KEY')
        if self.provider == 'ollama':
            result = request_json(self.base, '/api/embed', dict(model=self.model, input=texts, truncate=False), timeout=self.timeout)
            vectors = result.get('embeddings')
        else:
            result = request_json(self.base, '/embeddings', dict(model=self.model, input=texts, encoding_format='float'), key, self.timeout)
            data = result.get('data')
            if not isinstance(data, list) or any(not isinstance(row, dict) or type(row.get('index')) is not int for row in data) or sorted(row.get('index', -1) for row in data) != list(range(len(texts))):
                raise ProviderError('invalid_embedding_count')
            vectors = [row.get('embedding') for row in sorted(data, key=lambda row: row['index'])]
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise ProviderError('invalid_embedding_count')
        vectors = [normalize(vector) for vector in vectors]
        if len({len(vector) for vector in vectors}) != 1:
            raise ProviderError('embedding_dimensions_changed')
        return vectors


def discover():
    global _DISCOVERY
    mode = os.environ.get('SYNOPSIS_EMBEDDINGS', 'auto')
    if mode == 'off':
        return None
    model = os.environ.get('SYNOPSIS_EMBEDDING_MODEL')
    if mode == 'compatible':
        if not model or not os.environ.get('SYNOPSIS_EMBEDDING_BASE'):
            raise ProviderError('embedding_configuration_required')
        return Embeddings(mode, model, os.environ['SYNOPSIS_EMBEDDING_BASE'])
    if mode not in ('auto', 'ollama'):
        raise ProviderError('unknown_embedding_provider')
    if mode=='auto':
        from local_semantics import discover as local_discover
        local=local_discover()
        if local:return local
    base = os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434')
    # Auto discovery contacts only the loopback endpoint. Remote is explicitly opt-in.
    if mode == 'auto' and base not in ('http://127.0.0.1:11434', 'http://localhost:11434'):
        return None
    if model:
        return Embeddings('ollama', model, base)
    now = time.monotonic()
    if now - _DISCOVERY[0] > 30:
        names = ollama_models()
        selected = next((name for name in names if any(x in name.lower() for x in ('embed', 'nomic', 'bge-'))), None)
        _DISCOVERY = (now, selected)
    return Embeddings('ollama', _DISCOVERY[1], base) if _DISCOVERY[1] else None


def rank(index, snapshots, query, folder, backend=None):
    """Return note -> (cosine, original section id), never another project's text.

    Work is bounded to 512 current sections, 64 cold embeddings per call and 8 sec
    per batch. Query vectors are never persisted. A failed backend returns no ranks.
    """
    try:
        backend = backend or discover()
        if not backend:
            return {}, 'unavailable'
        threshold = float(os.environ.get('SYNOPSIS_SEMANTIC_THRESHOLD', '.72'))
        if not math.isfinite(threshold) or not .3 <= threshold <= 1:
            raise ValueError('invalid_threshold')
        chunks = []
        # Stable bounded order. Rank all cached candidates; warm at most 64 cold chunks.
        for n in sorted(snapshots):
            for section in index.notas[n]['secciones']:
                body = index.secciones[section][3]
                if not body.strip():
                    continue
                text = (index.notas[n]['titulo'] + '\n' + body)[:6000]
                key = hashlib.sha256(text.encode()).hexdigest()
                chunks.append((n, section, key, text))
                if len(chunks) >= 512:
                    break
            if len(chunks) >= 512:
                break
        if not chunks:
            return {}, 'ready'
        private = Path(folder) / '.synopsis'
        private.mkdir(parents=True, mode=0o700, exist_ok=True)
        path = private / 'vectors.sqlite3'
        if path.is_symlink():
            raise ValueError('unsafe_cache')
        with contextlib.closing(sqlite3.connect(path, timeout=2)) as db:
            path.chmod(0o600)
            db.execute('CREATE TABLE IF NOT EXISTS vectors (backend TEXT, hash TEXT, vector TEXT, PRIMARY KEY(backend,hash))')
            vectors = {}
            for _, _, key, _ in chunks:
                row = db.execute('SELECT vector FROM vectors WHERE backend=? AND hash=?', (backend.identity, key)).fetchone()
                if row:
                    vectors[key] = normalize(json.loads(row[0]))
            missing = list(dict.fromkeys(key for _, _, key, _ in chunks if key not in vectors))[:64]
            texts = {key: text for _, _, key, text in chunks}
            # One batch: bounded latency, provider failure leaves lexical search intact.
            if missing:
                fresh = backend([texts[key] for key in missing])
                if len(fresh) != len(missing):
                    raise ProviderError('invalid_embedding_count')
                with db:
                    for key, vector in zip(missing, fresh):
                        vector = normalize(vector)
                        db.execute('INSERT OR REPLACE INTO vectors VALUES(?,?,?)', (backend.identity, key, json.dumps(vector)))
                        vectors[key] = vector
            # Remove obsolete hashes for this backend; never use cached stale chunks.
            current = {key for _, _, key, _ in chunks}
            with db:
                for (key,) in db.execute('SELECT hash FROM vectors WHERE backend=?', (backend.identity,)).fetchall():
                    if key not in current:
                        db.execute('DELETE FROM vectors WHERE backend=? AND hash=?', (backend.identity, key))
        vector = normalize(backend([query])[0])
        scores = {}
        for n, section, key, _ in chunks:
            candidate = vectors.get(key)
            if candidate is None or len(candidate) != len(vector):
                continue
            cosine = sum(a*b for a, b in zip(candidate, vector))
            if cosine >= threshold and (n not in scores or cosine > scores[n][0]):
                scores[n] = (cosine, section)
        return scores, 'ready' if len(vectors) == len(current) else 'warming'
    except (ValueError, OSError, sqlite3.Error, TypeError, KeyError, IndexError):
        return {}, 'degraded'
