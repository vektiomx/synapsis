"""Learn from explicit retrieval outcomes, never from a note merely being opened."""
import contextlib
import datetime as dt
import hashlib
import json
import sqlite3
import uuid
from pathlib import Path


class RecallFeedback:
    def __init__(self, folder):
        self.folder = Path(folder)

    @contextlib.contextmanager
    def connect(self):
        self.folder.mkdir(parents=True, mode=0o700, exist_ok=True)
        path = self.folder / 'recall-feedback.sqlite3'
        with contextlib.closing(sqlite3.connect(path, timeout=5)) as db:
            path.chmod(0o600)
            db.executescript('''
                CREATE TABLE IF NOT EXISTS packets (
                    id TEXT PRIMARY KEY, project TEXT NOT NULL, query_hash TEXT NOT NULL,
                    evidence TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS feedback (
                    packet_id TEXT PRIMARY KEY REFERENCES packets(id), outcome TEXT NOT NULL,
                    source TEXT NOT NULL, created_at TEXT NOT NULL);
            ''')
            yield db

    def register(self, packet):
        identifier = uuid.uuid4().hex
        # Persist neither the prompt nor the contents of a retrieved note.
        evidence = [dict(path=e['path'], sha256=e['sha256']) for e in packet['evidence']]
        with self.connect() as db, db:
            db.execute('INSERT INTO packets VALUES(?,?,?,?,?)', (
                identifier, packet['project'], hashlib.sha256(packet['query'].encode()).hexdigest(),
                json.dumps(evidence), dt.datetime.now(dt.timezone.utc).isoformat()))
            # Bound prompt-derived metadata retention, independent of memory retention.
            cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=90)).isoformat()
            db.execute('DELETE FROM feedback WHERE packet_id IN (SELECT id FROM packets WHERE created_at < ?)', (cutoff,))
            db.execute('DELETE FROM packets WHERE created_at < ?', (cutoff,))
        return identifier

    def report(self, identifier, project, outcome, source):
        if outcome not in ('useful', 'irrelevant', 'incorrect'):
            raise ValueError('Resultado inválido: useful, irrelevant o incorrect.')
        if not isinstance(source, str) or not source.strip() or len(source) > 200:
            raise ValueError('Indica la procedencia de la evaluación (máximo 200 caracteres).')
        root = str(Path(project).expanduser().resolve())
        with self.connect() as db, db:
            packet = db.execute('SELECT project,created_at FROM packets WHERE id=?', (identifier,)).fetchone()
            cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=90)).isoformat()
            if packet is None or packet[0] != root or packet[1] < cutoff:
                raise ValueError('No existe ese paquete de contexto para este proyecto.')
            previous = db.execute('SELECT outcome,source FROM feedback WHERE packet_id=?', (identifier,)).fetchone()
            if previous:
                if previous != (outcome, source):
                    raise ValueError('Ese paquete ya fue evaluado; no se puede votar varias veces.')
                return {'recorded': False, 'unchanged': True}
            db.execute('INSERT INTO feedback VALUES(?,?,?,?)',
                       (identifier, outcome, source, dt.datetime.now(dt.timezone.utc).isoformat()))
        return {'recorded': True, 'unchanged': False}

    def factors(self, project):
        """Bounded Bayesian ranking adjustment, keyed by the exact file revision."""
        with self.connect() as db:
            cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=90)).isoformat()
            rows = db.execute('SELECT p.evidence,f.outcome FROM packets p JOIN feedback f ON f.packet_id=p.id WHERE p.project=? AND p.created_at>=?',
                              (str(Path(project).resolve()), cutoff)).fetchall()
        counts = {}
        for evidence, outcome in rows:
            for item in json.loads(evidence):
                pair = (item['path'], item['sha256'])
                good, total = counts.get(pair, (0, 0))
                counts[pair] = (good + int(outcome == 'useful'), total + 1)
        # Neutral prior: 2 positive and 2 negative. A single vote has small impact.
        return {key: 0.85 + 0.3 * (good + 2) / (total + 4) for key, (good, total) in counts.items()}
