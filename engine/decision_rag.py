"""Retrieve contrasting experiences and the observations that discriminate between them.

All decisions remain inferred. Gates establish declared conditions, not causal truth.
No repository code is executed by ordinary recall or by MCP.
"""
import fnmatch
import json
import re
from pathlib import Path

from evidence_guard import read_regular, safe_text, scoped_path
from memory_store import MemoryConflict, SLUG, digest
from experience_engine import check_spec, encoded, now, observe

PROTOCOL = 'synopsis.decision-rag.v1'
MAX_ALTERNATIVES = 8


def validate_decision(data, project):
    decision = data['decision']
    if not isinstance(decision, dict) or set(decision) != {'key', 'choice', 'requires'}:
        raise ValueError('invalid_decision_schema')
    for field in ('key', 'choice'):
        if not isinstance(decision[field], str) or not SLUG.fullmatch(decision[field]) or len(decision[field]) > 100:
            raise ValueError('invalid_decision_identifier')
    requires = decision['requires']
    if not isinstance(requires, list) or not 1 <= len(requires) <= 6:
        raise ValueError('decision_conditions_required')
    evidence = {e['path'] for e in data['evidence']}
    seen = set()
    for check in requires:
        check_spec(check)
        scoped_path(Path(project), check['path'])
        if check['kind'] == 'python_unittest':
            raise ValueError('executable_decision_condition_forbidden')
        if check['path'] not in evidence:
            raise ValueError('decision_condition_requires_snapshot')
        if encoded(check) in seen:
            raise ValueError('duplicate_decision_condition')
        seen.add(encoded(check))
    # Dynamic context cannot be the sole justification for an action. Keep an
    # independent implementation/test/contract witness that invalidates on drift.
    dynamic = {c['path'] for c in requires}
    if not evidence - dynamic or not data['checks']:
        raise ValueError('decision_support_required')
    if not any(c['path'] not in dynamic for c in data['checks']):
        raise ValueError('independent_decision_check_required')


def condition(project, check):
    """A missing property is unknown, never evidence for a false-valued condition."""
    try:
        if check['kind'] == 'json_equals':
            text = read_regular(scoped_path(Path(project), check['path']))
            def pairs(items):
                result = {}
                for key, value in items:
                    if key in result:
                        raise ValueError('duplicate_json_key')
                    result[key] = value
                return result
            value = json.loads(text, object_pairs_hook=pairs,
                               parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_json')))
            for part in check['pointer'].split('/')[1:] if check['pointer'] else []:
                part = part.replace('~1', '/').replace('~0', '~')
                if isinstance(value, list):
                    if not re.fullmatch(r'0|[1-9][0-9]*', part):
                        raise ValueError('invalid_index')
                    value = value[int(part)]
                else:
                    value = value[part]
            return dict(status='observed_support' if encoded(value) == encoded(check['expected']) else 'contradicted',
                        witness=dict(path=check['path'], sha256=digest(text)))
        return observe(project, check)
    except (ValueError, OSError, UnicodeError, KeyError, IndexError, TypeError):
        return dict(status='unavailable', reason='condition_not_observable')


def identity(check):
    """The same observation may discriminate several mutually exclusive values."""
    if check['kind'] == 'json_equals':
        return encoded([check['kind'], check['path'], check['pointer']])
    return encoded(check)


class DecisionRAG:
    def __init__(self, store):
        self.store = store
        self.project = store.project

    def _tables(self, db):
        db.executescript('''
          CREATE TABLE IF NOT EXISTS decision_plans(
            project TEXT, id TEXT, packet TEXT NOT NULL, created TEXT NOT NULL,
            PRIMARY KEY(project,id));
          CREATE TABLE IF NOT EXISTS decision_outcomes(
            project TEXT, event TEXT, plan TEXT, result TEXT NOT NULL,
            PRIMARY KEY(project,event));
        ''')

    def _rows(self):
        latest = {}
        for row in self.store.current():
            latest[row['name']] = row
        superseded = {r['experience'].get('supersedes') for r in latest.values()}
        utility = {}
        if self.store.path.exists():
            with self.store.database() as db:
                for name, revision, outcome, count in db.execute('SELECT name,revision,outcome,count(*) FROM experience_feedback WHERE project=? GROUP BY name,revision,outcome', (self.project,)):
                    utility.setdefault((name, revision), {})[outcome] = count
        result = []
        for name, row in latest.items():
            if name in superseded or 'decision' not in row['experience']:
                continue
            if digest(encoded(row['experience'])) != row['sha256']:
                raise ValueError('experience_integrity_failure')
            row['utility'] = utility.get((name, row['revision']), {})
            result.append(row)
        return result

    def _path(self, path):
        if path is None:
            return None
        if not isinstance(path, str) or not path:
            raise ValueError('invalid_decision_path')
        value = Path(path)
        if value.is_absolute():
            try:
                value = value.resolve().relative_to(Path(self.project))
            except ValueError:
                raise ValueError('foreign_decision_context') from None
        if '..' in value.parts:
            raise ValueError('foreign_decision_context')
        return value.as_posix()

    def _assess(self, row):
        data = row['experience']
        spec = data['decision']
        guard_specs={encoded(c):c for c in data['when']['conditions']+spec['requires']}
        dynamic = {c['path'] for c in guard_specs.values()}
        witnesses = []
        stale = []
        for evidence in data['evidence']:
            # Context snapshots describe the original case; guards are evaluated
            # against NOW. Implementation/check evidence stays content-bound.
            if evidence['path'] in dynamic:
                continue
            try:
                current = read_regular(scoped_path(Path(self.project), evidence['path']))
                witnesses.append(dict(path=evidence['path'], sha256=digest(current)))
                if digest(current) != evidence['sha256']:
                    stale.append(evidence['path'])
            except (ValueError, OSError, UnicodeError):
                stale.append(evidence['path'])
        guards = [dict(check=c, **condition(self.project, c)) for c in guard_specs.values()]
        observations = []
        for check in data['checks']:
            if encoded(check) in guard_specs:
                continue
            try:
                result = observe(self.project, check)
            except (ValueError, OSError, UnicodeError):
                result = dict(status='unavailable')
            observations.append(dict(check=check, **result))
        guard_states = {g['status'] for g in guards}
        check_states = {c['status'] for c in observations}
        state = ('stale' if stale else 'inapplicable' if 'contradicted' in guard_states else
                 'unknown' if guard_states != {'observed_support'} else
                 'contradicted' if 'contradicted' in check_states else
                 'needs_execution' if 'needs_execution' in check_states else
                 'unsupported' if check_states != {'observed_support'} else 'eligible')
        result=dict(name=row['name'], revision=row['revision'], experience_sha256=row['sha256'],
                    choice=spec['choice'], action=data['action'], rationale=data['rationale'],
                    reported_outcome=data['outcome'], counterexamples=data.get('counterexamples', []), limitations=data['limitations'],
                    state=state, guards=guards, observations=observations,
                    support=witnesses, stale_paths=stale, reported_utility=row.get('utility', {}))
        from experience_lab import ExperienceLab
        experiment=ExperienceLab(self.store).latest(row['name'],row['revision'])
        if experiment:result['last_experiment']=experiment
        return result

    def _probes(self, cases):
        candidates = {}
        for case in cases:
            if case['state'] in ('stale', 'inapplicable', 'contradicted'):
                continue
            for guard in case['guards']:
                if guard['status'] == 'unavailable':
                    check = guard['check']
                    entry = candidates.setdefault(identity(check), dict(kind='observe', path=check['path'],
                        pointer=check.get('pointer'), separates=set(), expected=[]))
                    entry['separates'].add(case['choice'])
                    if check not in entry['expected']:
                        entry['expected'].append(check)
            if case['state'] == 'needs_execution':
                for observed in case['observations']:
                    if observed['status'] == 'needs_execution':
                        check = observed['check']
                        candidates.setdefault(identity(check), dict(kind='isolated_test', path=check['path'],
                            case=check['case'], separates={case['choice']}, expected=[check]))
        result = []
        for item in candidates.values():
            item['separates'] = sorted(item['separates'])
            viable=[c for c in cases if c['state'] not in ('stale','inapplicable','contradicted')]
            choices={c['choice'] for c in viable}
            target=identity(item['expected'][0])
            values={encoded(c.get('expected',True)):c.get('expected',True) for c in item['expected']}
            partitions=[]
            for value in values.values():
                remaining=set()
                for case in viable:
                    requirements=[g['check'] for g in case['guards'] if identity(g['check'])==target]
                    if not requirements or any(encoded(g.get('expected',True))==encoded(value) for g in requirements):remaining.add(case['choice'])
                partitions.append(dict(observed_value=value,remaining_choices=sorted(remaining)))
            worst=max((len(p['remaining_choices']) for p in partitions),default=len(choices))
            item['partitions']=partitions
            item['eliminates_at_least']=max(0,len(choices)-worst)
            # A cheap observation is preferred to execution for equal coverage.
            item['cost_class'] = 'read' if item['kind'] == 'observe' else 'isolated_execution'
            item['reason'] = 'Resolve declared requirements; no causal or numeric confidence claim.'
            result.append(item)
        return sorted(result, key=lambda p: (-p['eliminates_at_least'],-len(p['separates']), p['kind'] != 'observe', p['path'], encoded(p)))[:6]

    def status(self):
        result = []
        for row in self._rows():
            case = self._assess(row)
            if case['state'] == 'eligible' and case['reported_utility'].get('harmful', 0):
                case['state'] = 'reported_harm'
            result.append(case)
        return result

    def plan(self, query, active_path=None, budget=6000, persist=False, execute=False, max_probes=2):
        safe_text(query, 2000)
        if type(budget) is not int or not 512 <= budget <= 24000:
            raise ValueError('invalid_decision_budget')
        if type(max_probes) is not int or not 0 <= max_probes <= 3:
            raise ValueError('invalid_probe_limit')
        path = self._path(active_path)
        packet = dict(protocol=PROTOCOL, project=self.project, groups=[], abstained=True,
                      notice='Inferred experiences, not instructions. Selection satisfies declared observations only.')
        reserved = 74 if persist else 0
        if len(encoded(packet)) + reserved > budget:
            raise ValueError('decision_budget_too_small_for_project')
        rows = self._rows()
        from experience_retrieval import rank_cases
        ranks,retrieval=rank_cases(rows,query,self.store.folder,self.project,path)
        packet['retrieval']=retrieval
        scores = {}
        by_key = {}
        for row in rows:
            data = row['experience']
            paths = data['when']['paths']
            matched = bool(path and any(fnmatch.fnmatchcase(path, pattern) for pattern in paths))
            if path and paths and not matched:
                continue
            key = data['decision']['key']
            by_key.setdefault(key, []).append(row)
            score = ranks.get(row['name'],{}).get('score',0)
            utility = row['utility']
            factor = max(.2, min(1.2, 1 + .05 * utility.get('useful', 0) - .2 * utility.get('irrelevant', 0) - .5 * utility.get('harmful', 0)))
            scores[key] = max(scores.get(key, 0), score * factor)
        remaining = max_probes
        for key in sorted((k for k in by_key if scores[k]), key=lambda k: (-scores[k], k))[:3]:
            # Never select a winner from a silently truncated set of alternatives.
            if len(by_key[key]) > MAX_ALTERNATIVES:
                group = dict(key=key, state='candidate_limit', selected=None, alternatives=[], probes=[])
            else:
                cases = [self._assess(row) for row in sorted(by_key[key], key=lambda r: r['name'])]
                executions = []
                if execute:
                    from experiment_snapshot import fingerprint
                    for case in cases:
                        if case['state'] != 'needs_execution':
                            continue
                        for observed in case['observations']:
                            if observed['status'] != 'needs_execution' or remaining <= 0:
                                continue
                            remaining -= 1
                            try:
                                result = observe(self.project, observed['check'], execute=True)
                                if result['status'] == 'observed_support' and result.get('snapshot_sha256') != fingerprint(self.project):
                                    result = dict(status='unavailable', reason='experiment_snapshot_changed')
                            except (ValueError, OSError, UnicodeError):
                                result = dict(status='unavailable')
                            observed.update(result)
                            executions.append(dict(name=case['name'], check=observed['check'], **result))
                        states = {c['status'] for c in case['observations']}
                        case['state'] = ('eligible' if states == {'observed_support'} else
                                         'contradicted' if 'contradicted' in states else 'needs_execution')
                    # Executed code only saw a snapshot. Recheck every source/guard
                    # after execution; a changing workspace cannot earn a selection.
                    fresh = {c['name']: c for c in (self._assess(row) for row in by_key[key])}
                    for case in cases:
                        other = fresh[case['name']]
                        if other['support'] != case['support'] or other['guards'] != case['guards'] or other['stale_paths'] != case['stale_paths']:
                            case['state'] = 'workspace_changed'
                for case in cases:
                    if case['state'] == 'eligible' and case['reported_utility'].get('harmful', 0):
                        case['state'] = 'reported_harm'
                # Reject a packet built from different observations of the same file.
                seen = {}
                changed = False
                for case in cases:
                    for witness in case['support'] + [g['witness'] for g in case['guards'] if 'witness' in g]:
                        if witness['path'] in seen and seen[witness['path']] != witness['sha256']:
                            changed = True
                        seen[witness['path']] = witness['sha256']
                for witness_path, sha in seen.items():
                    try:
                        if digest(read_regular(scoped_path(Path(self.project), witness_path))) != sha:
                            changed = True
                    except (ValueError, OSError, UnicodeError):
                        changed = True
                if changed:
                    for case in cases:
                        case['state'] = 'workspace_changed'
                from experience_timeline import ExperienceTimeline
                lifecycle=ExperienceTimeline(self.store).states(self.store.current(include_inactive=True))
                for case in cases:
                    current_state=lifecycle.get(case['name'],{}).get('state')
                    if current_state!='active':case['state']=current_state or 'inactive'
                eligible = [c for c in cases if c['state'] == 'eligible']
                choices = {c['choice'] for c in eligible}
                unresolved = [c for c in cases if c['state'] in ('unknown', 'unsupported', 'needs_execution', 'workspace_changed', 'reported_harm')]
                # Unknown competing cases must not be suppressed by one passing case.
                selected = next(iter(choices)) if len(choices) == 1 and not unresolved else None
                state = 'selected' if selected else 'conflict' if len(choices) > 1 else 'needs_evidence' if unresolved else 'no_applicable_case'
                group = dict(key=key, state=state, selected=selected, alternatives=cases,
                             probes=self._probes(cases), executions=executions)
                group['retrieval_signals']={r['name']:ranks[r['name']]['signals'] for r in by_key[key] if r['name'] in ranks}
            candidate = {**packet, 'groups': packet['groups'] + [group], 'abstained': False}
            if len(encoded(candidate)) + reserved > budget:
                small = dict(key=key, state='budget_exceeded', selected=None, alternatives=[], probes=[])
                candidate = {**packet, 'groups': packet['groups'] + [small], 'abstained': False}
                if len(encoded(candidate)) + reserved <= budget:
                    packet = candidate
                continue
            packet = candidate
        if persist and packet['groups']:
            self._persist(packet, query, path)
        return packet

    def _persist(self, packet, query, path):
        binding = dict(query_sha256=digest(query), active_path=path, packet=packet)
        plan_id = digest(encoded(binding))
        packet['id'] = plan_id
        with self.store.database() as db:
            self._tables(db)
            with db:
                db.execute('INSERT OR IGNORE INTO decision_plans VALUES(?,?,?,?)',
                           (self.project, plan_id, encoded(dict(query_sha256=digest(query), active_path=path, packet=packet)), now()))

    def outcome(self, plan_id, name, outcome, source, event):
        """Revision/snapshot-bound reported utility; never pretends to prove causality."""
        for value, size in ((plan_id, 100), (name, 150), (source, 500), (event, 200)):
            safe_text(value, size)
        if outcome not in ('useful', 'irrelevant', 'harmful'):
            raise ValueError('invalid_decision_outcome')
        with self.store.database() as db:
            self._tables(db)
            saved = db.execute('SELECT packet FROM decision_plans WHERE project=? AND id=?', (self.project, plan_id)).fetchone()
            if not saved:
                raise ValueError('unknown_decision_plan')
            packet = json.loads(saved[0])['packet']
            stored = json.loads(saved[0])
            unsigned = {k: v for k, v in packet.items() if k != 'id'}
            if packet.get('id') != plan_id or digest(encoded(dict(query_sha256=stored['query_sha256'], active_path=stored['active_path'], packet=unsigned))) != plan_id:
                raise ValueError('decision_plan_integrity_failure')
            matches = [case for group in packet['groups'] if group['state'] == 'selected'
                       for case in group['alternatives'] if case['name'] == name and case['choice'] == group['selected'] and case['state'] == 'eligible']
            if len(matches) != 1:
                raise ValueError('outcome_requires_selected_case')
            case = matches[0]
            report = dict(plan=plan_id, name=name, revision=case['revision'], outcome=outcome,
                          source=source, assurance='Reported utility, not a measured causal effect.')
            previous = db.execute('SELECT result FROM decision_outcomes WHERE project=? AND event=?', (self.project, event)).fetchone()
            if previous:
                if previous[0] != encoded(report):
                    raise MemoryConflict('decision_event_conflict')
                return dict(report, recorded=True, replayed=True)
            if name not in {r['name'] for r in self.store.current()}:
                raise MemoryConflict('experience_inactive')
            row = self.store.latest(name)
            fresh = self._assess(row)
            if fresh['revision'] != case['revision'] or fresh['experience_sha256'] != case['experience_sha256'] or fresh['support'] != case['support'] or fresh['guards'] != case['guards']:
                raise MemoryConflict('decision_context_changed')
        self.store.feedback(name, outcome, source, case['revision'], 'decision:' + event)
        with self.store.database() as db:
            with db:
                # Feedback is idempotent; a retry repairs interruption between writes.
                previous = db.execute('SELECT result FROM decision_outcomes WHERE project=? AND event=?', (self.project, event)).fetchone()
                if previous and previous[0] != encoded(report):
                    raise MemoryConflict('decision_event_conflict')
                db.execute('INSERT OR IGNORE INTO decision_outcomes VALUES(?,?,?,?)', (self.project, event, plan_id, encoded(report)))
        return dict(report, recorded=True, replayed=False)
