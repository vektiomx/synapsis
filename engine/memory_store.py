"""Versioned local memory with a recoverable Markdown projection (stdlib only)."""
import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import uuid
from pathlib import Path

from archivos import escribir_atomico, tomar_candado, soltar_candado

TYPES = {'user', 'feedback', 'project', 'reference'}
STATES = {'confirmed', 'inferred', 'archived'}
SLUG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')
SECRET = re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{32,})\b')


class MemoryConflict(ValueError):
    """The caller must resolve a duplicate, stale revision or external edit."""


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('La fecha debe incluir zona horaria.')
    return parsed.astimezone(dt.timezone.utc)


def active(metadata, now=None):
    if metadata.get('state') in ('archived', 'superseded'):
        return False
    expiry = metadata.get('expires_at')
    try:
        return not expiry or timestamp(expiry) > (now or dt.datetime.now(dt.timezone.utc))
    except (ValueError, TypeError):
        return False


class MemoryStore:
    """Markdown stays editable. SQLite journals writes, revisions and provenance.

    A committed outbox survives interruption between note and index replacement.
    Recovery refuses to overwrite edits made outside this store.
    """

    def __init__(self, folder):
        self.folder = Path(folder)

    @contextlib.contextmanager
    def locked(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        private = self.folder / '.synopsis'
        private.mkdir(mode=0o700, exist_ok=True)
        lock = tomar_candado(private / 'write.lock', espera=5)
        if lock is None:
            raise MemoryConflict('La memoria está ocupada; vuelve a intentar.')
        try:
            with contextlib.closing(sqlite3.connect(private / 'memory.sqlite3', timeout=5)) as db:
                (private / 'memory.sqlite3').chmod(0o600)
                db.execute('PRAGMA synchronous=FULL')
                db.executescript('''
                    CREATE TABLE IF NOT EXISTS revisions (
                        id INTEGER PRIMARY KEY, filename TEXT NOT NULL, revision INTEGER NOT NULL,
                        text TEXT NOT NULL, metadata TEXT NOT NULL, created_at TEXT NOT NULL,
                        UNIQUE(filename, revision));
                    CREATE TABLE IF NOT EXISTS operations (
                        id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, receipt TEXT NOT NULL);
                    CREATE TABLE IF NOT EXISTS outbox (
                        filename TEXT PRIMARY KEY, previous TEXT, target TEXT NOT NULL);
                ''')
                self._recover(db)
                yield db
        finally:
            soltar_candado(lock)

    def _recover(self, db):
        pending = list(db.execute('SELECT filename, previous, target FROM outbox'))
        # Validate every projection before writing any, including symlink targets.
        for filename, previous, target in pending:
            path = self.folder / filename
            if path.is_symlink():
                raise MemoryConflict('La proyección de memoria no admite enlaces simbólicos.')
            current = path.read_text(encoding='utf-8') if path.exists() else None
            if current != target and (digest(current) if current is not None else None) != previous:
                raise MemoryConflict(f'{filename} cambió fuera de Synopsis; conserva la revisión pendiente antes de resolverlo.')
        for filename, _, target in pending:
            path = self.folder / filename
            escribir_atomico(path, target)
            path.chmod(0o600)
            with path.open('r+b') as stream:
                os.fsync(stream.fileno())
        if pending and os.name != 'nt':
            directory = os.open(self.folder, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        if pending:
            generation = self.folder / '.synopsis/generation'
            escribir_atomico(generation, uuid.uuid4().hex)
            with generation.open('r+b') as stream:
                os.fsync(stream.fileno())
            if os.name != 'nt':
                directory = os.open(generation.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        with db:
            db.execute('DELETE FROM outbox')

    @staticmethod
    def validate(*, filename, name, description, kind, content, index_line,
                 overwrite=False, expected_revision=None, source='agent', state='inferred', expires_at=None, cues=None, operation_id=None):
        if any(not isinstance(value, str) for value in (filename, name, description, kind, content, index_line, source, state)):
            raise ValueError('Los campos de texto de la memoria deben ser cadenas.')
        if type(overwrite) is not bool:
            raise ValueError('La autorización de sobrescritura debe ser booleana.')
        if operation_id is not None and (not isinstance(operation_id, str) or not re.fullmatch(r'[a-zA-Z0-9:-]{1,160}', operation_id)):
            raise ValueError('Identificador de operación inválido.')
        stem = filename.removesuffix('.md')
        if not SLUG.fullmatch(stem) or stem == 'memory' or not SLUG.fullmatch(name):
            raise ValueError('Archivo y nombre deben ser slugs kebab-case; MEMORY.md está reservado.')
        filename = stem + '.md'
        if kind not in TYPES or state not in STATES:
            raise ValueError('Tipo o estado de memoria inválido.')
        if not content.strip() or not description.strip() or not source.strip():
            raise ValueError('Contenido, descripción y procedencia son obligatorios.')
        if any(len(value) > limit for value, limit in ((content, 20000), (description, 2000), (source, 2000))):
            raise ValueError('La memoria supera el tamaño permitido.')
        if SECRET.search(content + description + source):
            raise ValueError('No se guardan claves privadas ni tokens reconocibles en memoria.')
        if expires_at is not None and not isinstance(expires_at, str):
            raise ValueError('La fecha de vigencia debe ser texto ISO 8601.')
        if expires_at:
            timestamp(expires_at)
        if expected_revision is not None and (type(expected_revision) is not int or expected_revision < 0):
            raise ValueError('La revisión esperada debe ser un entero no negativo.')
        if '\n' in index_line or not re.search(r'\]\(' + re.escape(filename) + r'\)', index_line):
            raise ValueError('La entrada de índice debe enlazar únicamente la nota guardada en una sola línea.')
        if len(re.findall(r'\]\(', index_line)) != 1:
            raise ValueError('La entrada del índice debe contener un solo enlace.')
        cues = [] if cues is None else cues
        if (not isinstance(cues, list) or len(cues) > 12 or
                any(not isinstance(cue, str) or not cue.strip() or len(cue) > 80 or '\n' in cue for cue in cues)):
            raise ValueError('Usa hasta 12 claves de recuperación de 80 caracteres cada una.')
        if SECRET.search(' '.join(cues)):
            raise ValueError('No se guardan tokens en las claves de recuperación.')
        cues = list(dict.fromkeys(cue.strip() for cue in cues))
        payload = dict(cues=cues, name=name, description=description, type=kind, source=source, state=state, expires_at=expires_at)
        body = content.strip() + '\n'
        request_hash = digest(json.dumps(dict(filename=filename, payload=payload, body=body,
            index_line=index_line, overwrite=overwrite, expected_revision=expected_revision), sort_keys=True))
        return filename, cues, payload, body, request_hash

    def save(self, *, filename, name, description, kind, content, index_line,
             overwrite=False, expected_revision=None, source='agent', state='inferred', expires_at=None, cues=None, operation_id=None):
        filename, cues, payload, body, request_hash = self.validate(
            filename=filename, name=name, description=description, kind=kind, content=content,
            index_line=index_line, overwrite=overwrite, expected_revision=expected_revision,
            source=source, state=state, expires_at=expires_at, cues=cues, operation_id=operation_id)
        with self.locked() as db:
            if operation_id:
                receipt = db.execute('SELECT request_hash,receipt FROM operations WHERE id=?', (operation_id,)).fetchone()
                if receipt:
                    if receipt[0] != request_hash:
                        raise MemoryConflict('El identificador ya pertenece a otra escritura.')
                    return dict(json.loads(receipt[1]), replayed=True)
            path = self.folder / filename
            if path.is_symlink() or (self.folder / 'MEMORY.md').is_symlink():
                raise MemoryConflict('La nota y su índice deben ser archivos regulares.')
            old = path.read_text(encoding='utf-8') if path.exists() else None
            latest = db.execute('SELECT revision, text, metadata FROM revisions WHERE filename=? ORDER BY revision DESC LIMIT 1',
                                (filename,)).fetchone()
            revision = latest[0] if latest else 0
            if expected_revision is not None and expected_revision != revision:
                raise MemoryConflict(f'Revisión desactualizada: esperada {expected_revision}, actual {revision}.')
            if latest and latest[2] == json.dumps(payload, sort_keys=True) and old == latest[1] and old.endswith('\n\n' + body):
                receipt = dict(path=str(path), revision=revision, unchanged=True, sha256=digest(old))
                if operation_id:
                    with db:
                        db.execute('INSERT INTO operations VALUES(?,?,?)', (operation_id, request_hash, json.dumps(receipt)))
                return receipt
            if latest and expected_revision is not None and old != latest[1]:
                raise MemoryConflict('La nota fue editada por fuera; vuelve a leerla antes de actualizarla.')
            if old is not None and not overwrite:
                raise MemoryConflict('La nota ya existe; revisa su contenido antes de reemplazarla.')
            external = old is not None and (not latest or old != latest[1])
            baseline_revision = revision + 1 if external else None
            if external:
                revision += 1
            # Exact duplicates under another name add noise rather than knowledge.
            from frontmatter import separar_frontmatter
            normalized = ' '.join(body.split()).casefold()
            for other in self.folder.glob('*.md'):
                if other.name in (filename, 'MEMORY.md') or other.is_symlink():
                    continue
                _, other_body = separar_frontmatter(other.read_text(encoding='utf-8'))
                if ' '.join(other_body.split()).casefold() == normalized:
                    raise MemoryConflict(f'El contenido ya existe en {other.name}; actualiza esa nota.')
            now = dt.datetime.now(dt.timezone.utc).isoformat()
            metadata = dict(type=kind, source=source, state=state, revision=revision + 1, updated_at=now)
            if cues:
                metadata['retrieval_cues'] = ' | '.join(cues)
            if expires_at:
                metadata['expires_at'] = expires_at
            quote = lambda value: json.dumps(value, ensure_ascii=False)
            text = f'---\nname: {quote(name)}\ndescription: {quote(description)}\nmetadata:\n'
            text += ''.join(f'  {key}: {quote(value)}\n' for key, value in metadata.items())
            text += '---\n\n' + body
            index_path = self.folder / 'MEMORY.md'
            before = index_path.read_text(encoding='utf-8') if index_path.exists() else None
            link = re.compile(r'\]\(' + re.escape(filename) + r'\)')
            lines = [line for line in (before or '# Memoria\n').splitlines() if not link.search(line)]
            index = '\n'.join(lines).rstrip() + '\n\n' + index_line.strip() + '\n'
            receipt = dict(path=str(path), revision=revision + 1, unchanged=False, sha256=digest(text))
            with db:
                if operation_id:
                    db.execute('INSERT INTO operations VALUES(?,?,?)', (operation_id, request_hash, json.dumps(receipt)))
                if external:
                    db.execute('INSERT INTO revisions(filename,revision,text,metadata,created_at) VALUES(?,?,?,?,?)',
                               (filename, baseline_revision, old,
                                json.dumps({'source': 'external:file', 'state': 'unverified'}), now))
                db.execute('INSERT INTO revisions(filename,revision,text,metadata,created_at) VALUES(?,?,?,?,?)',
                           (filename, revision + 1, text, json.dumps(payload, sort_keys=True), now))
                for target_name, previous, target in ((filename, old, text), ('MEMORY.md', before, index)):
                    db.execute('INSERT INTO outbox VALUES(?,?,?)',
                               (target_name, digest(previous) if previous is not None else None, target))
            self._recover(db)
            return receipt

    def history(self, filename):
        if not SLUG.fullmatch(filename.removesuffix('.md')):
            raise ValueError('Nombre de archivo inválido.')
        with self.locked() as db:
            return [dict(revision=row[0], text=row[1], metadata=json.loads(row[2]), created_at=row[3])
                    for row in db.execute('SELECT revision,text,metadata,created_at FROM revisions WHERE filename=? ORDER BY revision',
                                          (filename.removesuffix('.md') + '.md',))]
