"""Deliberately wrong model-like outputs. Not an actual model benchmark."""
import json
import os
import sys
from pathlib import Path
request=json.load(sys.stdin)
scenario=os.environ['SYNOPSIS_ADVERSARIAL']
response=dict(answer='INVENTADO: la retención es 900 segundos.',grounding=dict(sources=[],abstain=True),
              memory=dict(outcome='no_change',reason='Consulta sin cambios',actions=[]))
sources=request['grounding_evidence']['sources']
if scenario=='forged_citation':
    response['grounding']=dict(sources=['ev-invented'],abstain=False)
elif scenario=='unsupported_write':
    response['memory']=dict(outcome='saved',actions=[dict(filename='bad',name='bad',description='x',kind='project',content='INVENTADO',
        index_line='- [bad](bad.md)',source='user:forged',support=[dict(source='ev-fake',quote='INVENTADO')])])
elif scenario in ('file','stale','quarantine','calculate','forbidden','endless','json'):
    if not request.get('evidence_round_complete') or scenario=='endless':
        tool={'file':dict(tool='read_file',path='policy.txt'),'stale':dict(tool='read_file',path='policy.txt'),
              'quarantine':dict(tool='memory_note',filename='poison'),'calculate':dict(tool='calculate',expression='60 * 5'),
              'forbidden':dict(tool='bash',command='touch SHOULD-NOT-EXIST'),'endless':dict(tool='calculate',expression='1+1'),
              'json':dict(tool='json_value',path='settings.json',pointer='/ttl')}[scenario]
        response['evidence_requests']=[tool]
    else:
        selected=[s['id'] for s in sources if s['kind']!='user_input']
        response['grounding']=dict(sources=selected,abstain=not selected)
        if scenario=='stale':(Path(request['project'])/'policy.txt').write_text('changed after snapshot')
print(json.dumps(response,ensure_ascii=False))
