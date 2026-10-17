"""Explicit validity and reversible retirement without deleting experience history."""
import datetime as dt
import json

from evidence_guard import safe_text
from memory_store import MemoryConflict
from experience_engine import encoded, now


def instant(value):
    if not isinstance(value, str):
        raise ValueError('invalid_validity_timestamp')
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('invalid_validity_timestamp') from None
    if parsed.tzinfo is None:
        raise ValueError('validity_requires_timezone')
    return parsed.astimezone(dt.timezone.utc)


def validate_validity(value):
    if not isinstance(value, dict) or not value or set(value) - {'from', 'until'}:
        raise ValueError('invalid_experience_validity')
    dates = {key: instant(text) for key, text in value.items()}
    if 'from' in dates and 'until' in dates and dates['from'] >= dates['until']:
        raise ValueError('invalid_validity_interval')


class ExperienceTimeline:
    def __init__(self, store):
        self.store = store

    def events(self):
        if not self.store.path.exists():
            return []
        with self.store.database() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE name='experience_lifecycle'").fetchone():
                return []
            return [json.loads(row[0]) for row in db.execute(
                'SELECT payload FROM experience_lifecycle WHERE project=? ORDER BY rowid', (self.store.project,))]

    def states(self, rows, at=None):
        current = instant(at) if at else dt.datetime.now(dt.timezone.utc)
        latest = {event['name']: event for event in self.events() if instant(event['recorded_at']) <= current}
        superseded = set()
        for row in rows:
            data = row['experience']
            start = data.get('validity', {}).get('from')
            if data.get('supersedes') and (not start or instant(start) <= current):
                superseded.add(data['supersedes'])
        result = {}
        for row in rows:
            name = row['name']
            event = latest.get(name)
            validity = row['experience'].get('validity', {})
            state = 'active'
            if event and event['state'] == 'retired':
                state = 'retired'
            elif name in superseded:
                state = 'superseded'
            elif validity.get('from') and current < instant(validity['from']):
                state = 'scheduled'
            elif validity.get('until') and current >= instant(validity['until']):
                state = 'expired'
            result[name] = dict(state=state, lifecycle_revision=event['sequence'] if event else 0,
                                validity=validity, reason=event['reason'] if event else None)
        return result

    def change(self, name, state, reason, source, expected_revision, expected_sequence=0, event=None):
        if state not in ('active', 'retired'):
            raise ValueError('invalid_lifecycle_state')
        safe_text(reason, 1000)
        safe_text(source, 500)
        if type(expected_sequence) is not int or expected_sequence < 0:
            raise ValueError('invalid_lifecycle_revision')
        row = self.store.latest(name)
        if row['revision'] != expected_revision:
            raise MemoryConflict('experience_revision_conflict')
        binding = dict(name=name, state=state, reason=reason, source=source, revision=expected_revision)
        if event is not None:
            safe_text(event, 200)
        from memory_store import digest
        key = digest(encoded([self.store.project, event or encoded([binding, expected_sequence])]))
        with self.store.database() as db:
            db.execute('CREATE TABLE IF NOT EXISTS experience_lifecycle(project TEXT,id TEXT,payload TEXT,PRIMARY KEY(project,id))')
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT payload FROM experience_lifecycle WHERE project=? AND id=?', (self.store.project,key)).fetchone()
            if old:
                value = json.loads(old[0])
                if any(value[k] != v for k,v in binding.items()):
                    raise MemoryConflict('lifecycle_event_conflict')
                return dict(value, replayed=True)
            revision = db.execute('SELECT max(revision) FROM experience_versions WHERE project=? AND name=?',(self.store.project,name)).fetchone()[0]
            if revision != expected_revision:
                raise MemoryConflict('experience_revision_conflict')
            previous = db.execute('SELECT payload FROM experience_lifecycle WHERE project=? ORDER BY rowid DESC',(self.store.project,)).fetchall()
            sequence = next((json.loads(p[0])['sequence'] for p in previous if json.loads(p[0])['name']==name),0)
            if sequence != expected_sequence:
                raise MemoryConflict('lifecycle_revision_conflict')
            value = dict(binding, id=key, sequence=sequence+1, recorded_at=now())
            db.execute('INSERT INTO experience_lifecycle VALUES(?,?,?)',(self.store.project,key,encoded(value)))
            db.commit()
        return dict(value, replayed=False)

    def history(self, name=None):
        rows = self.store.current(include_inactive=True)
        states = self.states(rows)
        return dict(cases=[dict(name=r['name'], revision=r['revision'],created=r['created'],**states[r['name']]) for r in rows if not name or r['name']==name],
                    events=[e for e in self.events() if not name or e['name']==name],
                    notice='Explicit lifecycle and declared validity, not inferred truth or a general temporal knowledge graph.')
