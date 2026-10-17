"""Scripted protocol fixture. This is not a real model or a model-quality benchmark."""
import json
import os
import sys
import time

request = json.load(sys.stdin)
scenario = os.environ.get('SYNOPSIS_TEST_SCENARIO', 'initial')
sources=request['grounding_evidence']['sources']
user=next(source for source in sources if source['kind']=='user_input')
memories=[source for source in sources if source['kind']=='memory_record']
action = dict(filename='redis-policy', name='redis-policy', description='Caducidad de caché Redis',
              kind='project', content='Redis conserva la caché 120 segundos.',
              index_line='- [Redis](redis-policy.md)', source='user:scripted-test', state='inferred',
              support=[dict(source=user['id'],quote=user['text'])])
if scenario == 'initial':
    response = dict(answer='Primera etapa terminada.', memory=dict(outcome='saved', actions=[action],
        checkpoint=dict(goal='Validar la política Redis', progress='Registrado TTL inicial', next_step='Aplicar corrección de TTL')))
elif scenario == 'correct':
    assert request['working']['state']['next_step'] == 'Aplicar corrección de TTL'
    assert '120 segundos' in json.dumps(request['memory']['evidence'], ensure_ascii=False)
    action.update(content='Redis conserva la caché 300 segundos.', overwrite=True, expected_revision=1)
    response = dict(answer='Corrección aplicada.', memory=dict(outcome='saved', actions=[action],
        checkpoint=dict(goal='Validar la política Redis', progress='Corregido TTL a 300 segundos', next_step='Validar TTL corregido')))
elif scenario == 'continue':
    assert request['working']['state']['next_step'] == 'Validar TTL corregido'
    evidence = json.dumps(request['memory']['evidence'], ensure_ascii=False)
    assert '300 segundos' in evidence and '120 segundos' not in evidence
    response = dict(answer='Retomado con TTL vigente: 300 segundos.',
                    memory=dict(outcome='no_change', reason='Solo consulta; sin aprendizaje durable nuevo.'))
elif scenario == 'stale':
    action.update(content='Redis conserva la caché 999 segundos.', overwrite=True, expected_revision=0)
    response = dict(answer='ESTA RESPUESTA NO DEBE ENTREGARSE', memory=dict(outcome='saved', actions=[action]))
elif scenario == 'broken':
    response = dict(answer='ESTA RESPUESTA NO DEBE ENTREGARSE')
elif scenario == 'timeout':
    time.sleep(10)
    response = {}
elif scenario == 'oversized':
    sys.stdout.write('x' * (300 * 1024))
    sys.exit(0)
else:
    raise ValueError('Unknown fixture scenario')
if scenario not in ('broken','timeout','oversized'):
    response['grounding']=dict(sources=[source['id'] for source in memories],abstain=not memories)
print(json.dumps(response, ensure_ascii=False))
