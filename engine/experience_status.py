"""Read-only dashboard of registered projects; raw turn payloads never leave the queue."""
import configuracion
from project_identity import registered_memories


def overview():
    from auto_review import ReviewQueue
    from experience_engine import ExperienceStore
    projects=[]
    for record in registered_memories(configuracion.archivo()):
        queue=ReviewQueue(record['memory'],record['project'])
        experiences=ExperienceStore(record['memory'],record['project'])
        latest={}
        for item in experiences.current(include_inactive=True):latest[item['name']]=item
        from decision_rag import DecisionRAG
        decisions={c['name']:c for c in DecisionRAG(experiences).status()}
        from experience_timeline import ExperienceTimeline
        from research_workbench import ResearchWorkbench
        timeline=ExperienceTimeline(experiences).history()
        lifecycle={c['name']:c for c in timeline['cases']}
        research=ResearchWorkbench(experiences).history()
        from behavior_memory import BehaviorMemory
        behavior=BehaviorMemory(experiences)
        witnesses=[dict(id=r['id'],callable=r['data']['callable'],state=behavior.assess(r),sequence=r['sequence'],created=r['created'],
                        records=len(r['data']['records']),origin=r['data']['origin'],source_sha256=r['data']['source_sha256'],
                        evidence=[item['source'] for item in r['data']['records']]) for r in behavior.rows()[:20]]
        research_cards=[dict(id=r['id'],created=r['created'],query=r['query'],snapshot_sha256=r['snapshot_sha256'],
            candidates=[dict(title=c['title'],hypothesis=c['hypothesis'],state=c['state'],paths=[p['path'] for p in c['patches']],
                             observations=[dict(path=o['check']['path'],case=o['check']['case'],baseline=o['baseline']['status'],candidate=o['candidate']['status']) for o in c['observations']],
                             behavior_observations=[dict(id=o['id'],baseline=o['baseline']['state'],candidate=o['candidate']['state'],matches=o['candidate'].get('matches',[])) for o in c.get('behavior_observations',[])]) for c in r['candidates']]) for r in research[:10]]
        cards=[]
        for name,item in list(latest.items())[-20:]:
            decision=decisions.get(name)
            verification=dict(state=decision['state'],checks=decision['observations'],requirements=decision['guards']) if decision else experiences.verify(name)
            if lifecycle[name]['state']!='active':verification=dict(state=lifecycle[name]['state'])
            data=item['experience']
            cards.append(dict(name=name,revision=item['revision'],situation=data['situation'],action=data['action'],
                              limitations=data['limitations'],verification=verification,decision=data.get('decision'),
                              lifecycle=lifecycle[name],evidence=data['evidence'],updated=item['created']))
        reviews=[dict(turn=r['turn'],state=r['state'],attempts=r['attempts'],error=r['error']) for r in queue.status()]
        if cards or reviews or research_cards or witnesses:projects.append(dict(id=record['key'],project=record['project'],experiences=cards,reviews=reviews,timeline=timeline['events'][-20:],research=research_cards,witnesses=witnesses))
    return dict(projects=projects,notice='Las interpretaciones permanecen inferred; los checks solo respaldan observaciones concretas.')


def retry_project(data):
    if not isinstance(data,dict) or set(data)!={'project'}:raise ValueError('invalid_project_review')
    matches=[r for r in registered_memories(configuracion.archivo()) if r['key']==data['project']]
    if len(matches)!=1:raise ValueError('unknown_project_review')
    from auto_review import ReviewQueue,kick
    record=matches[0];queue=ReviewQueue(record['memory'],record['project'])
    if not queue.path.exists():raise ValueError('unknown_project_queue')
    queue.retry();kick(record['memory'],record['project'])
    return dict(scheduled=True)
