"""Bounded recovery while the authenticated map service is alive."""
import os
import threading

_semantic_cursor=0


def sweep():
    global _semantic_cursor
    import configuracion
    from project_identity import registered_memories
    from auto_review import ReviewQueue,kick
    count=0
    records=registered_memories(configuracion.archivo())
    from local_semantics import discover
    backend=discover() if os.environ.get('SYNOPSIS_EMBEDDINGS','auto')!='off' else None
    # Warm a bounded rotating subset without retaining task queries or calling an LLM.
    if backend and records:
        from experience_engine import ExperienceStore
        from experience_retrieval import semantic_scores
        for offset in range(min(4,len(records))):
            record=records[(_semantic_cursor+offset)%len(records)]
            try:
                rows=ExperienceStore(record['memory'],record['project']).current()
                semantic_scores([dict(r,_project=record['project']) for r in rows],None,record['memory'],backend)
            except (ValueError,OSError):pass
        _semantic_cursor=(_semantic_cursor+4)%len(records)
    if os.environ.get('SYNOPSIS_AUTO_REVIEW','1')=='0':return dict(checked=0)
    for record in records:
        queue=ReviewQueue(record['memory'],record['project'])
        if not queue.path.exists():continue
        try:
            # Expiration and recoverable jobs are processed even after closing the IDE.
            with queue.database():pass
            kick(record['memory'],record['project'])
            count+=1
        except (ValueError,OSError):continue
    return dict(checked=count)


def serve(stop=None,interval=30):
    stop=stop or threading.Event()
    while not stop.is_set():
        try:sweep()
        except Exception:pass
        stop.wait(interval)
