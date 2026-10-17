"""Scoped BM25 + technical anchors + real semantic vectors, fused without certifying truth."""
import collections
import fnmatch
import hashlib
import json
import math
import re
import sqlite3
import time
import unicodedata
from pathlib import Path

from semantic_memory import discover, normalize

STOP=set('the and for with from this that these those what how should when which would could into have has was were will been are can una uno unos unas con para por del los las que como cual cuando debe debemos tiene este esta estos estas sobre'.split())


def tokens(text):
    text=re.sub(r'([a-z])([A-Z])',r'\1 \2',text)
    text=''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))
    return [w for w in re.findall(r'[^\W_]+',text) if len(w)>=2 and w not in STOP]


def representation(row):
    data=row['experience'];scope=data['when'];decision=data.get('decision',{})
    anchors=[row['name'],decision.get('key',''),decision.get('choice',''),*scope['paths'],*scope['keywords']]
    for check in scope['conditions']+data['checks']+decision.get('requires',[]):
        anchors.extend(str(check.get(key,'')) for key in ('path','pointer','case'))
    # Checks include source-backed contract text, not only an LLM's paraphrase.
    contract=[check.get('text','') for check in data['checks'] if check['kind']=='text_contains']
    text='\n'.join(anchors+[data[k] for k in ('situation','action','rationale','outcome','limitations')]+contract+data.get('counterexamples',[]))
    chunks=[data['situation'][:250]+'\n'+data['action'][:200]+'\n'+' '.join(scope['keywords'])[:100],
            data['rationale'][:250]+'\n'+'\n'.join(contract)[:300]]
    return text,' '.join(anchors),chunks


def semantic_scores(rows,query,folder,backend=None):
    """Cache documents by content+backend+project, never query text or query vectors."""
    try:
        backend=backend or discover()
        if backend is None:return {},'unavailable'
        chunks=[]
        for row in rows[:2048]:
            for text in representation(row)[2]:
                chunks.append((row['name'],hashlib.sha256(text.encode()).hexdigest(),text))
        if not chunks:return {},'ready'
        private=Path(folder)/'.synopsis'
        private.mkdir(parents=True,exist_ok=True,mode=0o700)
        path=private/'experience-vectors.sqlite3'
        if private.is_symlink() or path.is_symlink():raise ValueError('unsafe_experience_vectors')
        with sqlite3.connect(path,timeout=2) as db:
            path.chmod(0o600)
            db.execute('CREATE TABLE IF NOT EXISTS vectors(project TEXT,backend TEXT,hash TEXT,vector TEXT,updated REAL,PRIMARY KEY(project,backend,hash))')
            if 'updated' not in {r[1] for r in db.execute('PRAGMA table_info(vectors)')}:db.execute('ALTER TABLE vectors ADD COLUMN updated REAL DEFAULT 0')
            project=rows[0].get('_project','')
            vectors={}
            for _,key,_ in chunks:
                old=db.execute('SELECT vector FROM vectors WHERE project=? AND backend=? AND hash=?',(project,backend.identity,key)).fetchone()
                if old:vectors[key]=normalize(json.loads(old[0]))
            texts={key:text for _,key,text in chunks}
            missing=list(dict.fromkeys(key for _,key,_ in chunks if key not in vectors))[:64]
            if missing:
                fresh=backend([texts[key] for key in missing])
                if not isinstance(fresh,list) or len(fresh)!=len(missing):raise ValueError('embedding_count')
                with db:
                    for key,vector in zip(missing,fresh):
                        vector=normalize(vector);vectors[key]=vector
                        db.execute('INSERT OR REPLACE INTO vectors VALUES(?,?,?,?,?)',(project,backend.identity,key,json.dumps(vector),time.time()))
            current=set(texts)
            with db:
                db.executemany('UPDATE vectors SET updated=? WHERE project=? AND backend=? AND hash=?',[(time.time(),project,backend.identity,key) for key in vectors])
                # A file-scoped lookup must not evict another file's current vectors.
                # Content-addressed keys exclude stale text; LRU bounds disk usage.
                db.execute('DELETE FROM vectors WHERE project=? AND rowid NOT IN (SELECT rowid FROM vectors WHERE project=? ORDER BY updated DESC LIMIT 8192)',(project,project))
        readiness='ready' if len(vectors)==len(current) and len(rows)<=2048 else 'warming'
        if query is None:return {},readiness
        query_vector=normalize(backend([query])[0])
        scores={}
        for name,key,_ in chunks:
            vector=vectors.get(key)
            if vector is None:continue
            if len(vector)!=len(query_vector):raise ValueError('embedding_dimension_changed')
            cosine=sum(a*b for a,b in zip(vector,query_vector))
            if cosine>=.48:scores[name]=max(scores.get(name,-1),cosine)
        return scores,readiness
    except (ValueError,OSError,sqlite3.Error,TypeError,KeyError,IndexError):
        return {},'degraded'


def rank_cases(rows,query,folder,project,active_path=None):
    scoped=[]
    for row in rows:
        paths=row['experience']['when']['paths']
        matched=bool(active_path and any(fnmatch.fnmatchcase(active_path,p) for p in paths))
        if active_path and paths and not matched:continue
        scoped.append(dict(row,_project=project,_matched_path=matched))
    query_words=set(tokens(query))
    documents={r['name']:collections.Counter(tokens(representation(r)[0])) for r in scoped}
    lengths={name:sum(words.values()) for name,words in documents.items()}
    average=sum(lengths.values())/max(1,len(lengths)) or 1
    frequency=collections.Counter(word for words in documents.values() for word in words)
    lexical={};anchor={}
    for row in scoped:
        name=row['name'];words=documents[name];score=0
        for term in query_words:
            count=words[term]
            if count:
                idf=math.log(1+(len(scoped)-frequency[term]+.5)/(frequency[term]+.5))
                score+=idf*count*2.2/(count+1.2*(.25+.75*lengths[name]/average))
        if score:lexical[name]=score
        technical=len(query_words & set(tokens(representation(row)[1])))+4*row['_matched_path']
        if technical:anchor[name]=technical
    ordered=sorted(scoped,key=lambda r:(-lexical.get(r['name'],0),-anchor.get(r['name'],0),r['name']))
    semantic,state=semantic_scores(ordered,query,folder)
    fused={};signals={}
    for label,scores in (('bm25',lexical),('anchors',anchor),('semantic',semantic)):
        for position,(name,score) in enumerate(sorted(scores.items(),key=lambda p:(-p[1],p[0])),1):
            fused[name]=fused.get(name,0)+1/(60+position)
            signals.setdefault(name,{})[label]=round(score,6)
    return {name:dict(score=score,signals=signals[name]) for name,score in fused.items()},dict(
        mode='hybrid' if state in ('ready','warming') else 'lexical_fallback',semantic=state,
        candidates=len(scoped),channels=['bm25','anchors','semantic'],assurance='Ranking relevance, not correctness or confidence.')
