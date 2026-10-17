#!/usr/bin/env python3
"""Reproduce an experience lifecycle; optional real inference, never a broad quality score."""
import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'engine'))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--live',action='store_true',help='Usa el proveedor autenticado con datos ficticios')
    parser.add_argument('--provider',default='codex')
    parser.add_argument('--model')
    args=parser.parse_args()
    from experience_engine import ExperienceStore
    from memory_store import digest
    from auto_review import ReviewQueue
    from model_provider import ModelTransport
    started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='synopsis-experience-eval-') as tmp:
        base=Path(tmp);project=base/'project';project.mkdir();folder=base/'memory'
        policy=project/'policy.json';policy.write_text('{"retry":{"retain":true,"ttl_hours":19},"language":"python"}')
        store=ExperienceStore(folder,project)
        prompt='Registra una experiencia estructurada de desarrollo: al agotar tres reintentos transitorios se perdía trabajo de la cola. Decidimos preservar la entrada hasta que venza su retención de 19 horas porque el proveedor puede recuperarse. policy.json contiene esa intención; solo observamos la configuración, NO probamos una recuperación real. Aplica al modificar src/queue.py en proyectos Python. Un trabajo vencido sí se descarta. Conserva los límites y un check json_equals de /retry/retain.'
        if args.live:
            queue=ReviewQueue(folder,project);turn=queue.cycle.begin('evaluation',prompt,'experience-eval')['turn']
            queue.remember(turn,'evaluation',prompt,'codex','experience-eval')
            queue.track('evaluation',dict(tool_input=dict(file_path=str(policy))))
            queue.stop('evaluation','La recuperación completa quedó demostrada.','experience-eval')
            queue.process_one(ModelTransport(args.provider,args.model,timeout=120))
            status=queue.status()[0]
            if status['state']!='complete':
                print(json.dumps(dict(passed=False,review=status,limitation='Provider/contract failure is not success.')))
                return 1
        else:
            data=dict(situation='Retry provider exhaustion lost work.',action='Retain pending work until 19 hours expire.',rationale='The provider may recover.',outcome='Observed configuration only.',limitations='No actual recovery test was performed.',when=dict(paths=['src/queue.py'],keywords=['retry','provider'],conditions=[]),checks=[dict(kind='json_equals',path='policy.json',pointer='/retry/retain',expected=True)],evidence=[dict(path='policy.json',sha256=digest(policy.read_text()))],counterexamples=['An expired entry must be discarded.'])
            store.save('retry-retention',data,'synthetic:lifecycle-evaluation')
        packet=store.recall('provider retry retention','src/queue.py')
        answer=None
        if args.live and packet['experiences']:
            answer=ModelTransport(args.provider,args.model,timeout=120).complete('Return JSON {"ttl_hours":number|null,"decision":"keep_until_expiry|discard_now|abstain","recovery_proven":boolean}. Use the experience as historical evidence. Configuration observations do not prove successful recovery.',dict(task='El proveedor agotó reintentos. ¿Qué política previa considerar, plazo y límite?',experiences=packet),str(project))
        current=bool(packet['experiences']) and packet['experiences'][0]['verification']['state']=='observed_support'
        irrelevant=store.recall('provider retry','src/billing.py')['abstained']
        policy.write_text('{"retry":{"retain":false,"ttl_hours":19},"language":"python"}')
        changed=store.recall('provider retry retention','src/queue.py')
        stale=bool(changed['experiences']) and changed['experiences'][0]['verification']['state']=='stale'
        decisions=not args.live or bool(answer and answer.get('ttl_hours')==19 and answer.get('recovery_proven') is False and answer.get('decision')=='keep_until_expiry')
        report=dict(protocol='synopsis.experience-evaluation.v1',mode='real_provider' if args.live else 'deterministic_fixture',passed=current and irrelevant and stale and decisions,
                    checks=dict(experience_captured=bool(packet['experiences']),scoped_observation=current,unrelated_path_abstains=irrelevant,changed_evidence_stale=stale,reported_limits_respected=decisions if args.live else None),
                    answer=answer,seconds=round(time.monotonic()-started,2),
                    limitation='One synthetic development/configuration episode; not a comparative coding benchmark or proof of causal benefit.')
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
