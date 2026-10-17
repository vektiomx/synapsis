"""Summarize preserved benchmark receipts without reclassifying gold or failures."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics


def quantile(values,fraction):
    if not values:return None
    values=sorted(values)
    return values[min(len(values)-1,max(0,int(len(values)*fraction+.999)-1))]


def summarize(base):
    read=lambda name:json.loads((base/name).read_text())
    manifest=read('manifest.json');inputs=read('inputs.json');profiles={}
    for profile in manifest['profiles']:
        entry={}
        acquisition=read('retrieval-'+profile+'.json') if (base/('retrieval-'+profile+'.json')).exists() else {}
        for split in ('development','reserved'):
            results=read('results-'+profile+'-'+split+'.json')
            tasks=[t for t in inputs if t['split']==split];expected=len(tasks)*(2 if split=='reserved' else 1)
            latencies=[r.get('sdk_metrics',{}).get('retrieval_seconds',r['retrieval_seconds']) for r in results if 'retrieval_seconds' in r]
            metrics=[acquisition[t['id']]['metrics'] for t in tasks if t['id'] in acquisition]
            entry[split]=dict(expected_runs=expected,completed=len(results),correct=sum(bool(r.get('correct')) for r in results),
                errors=sum(bool(r.get('error')) for r in results),wrong_patches=sum(bool(r.get('wrong_patch')) for r in results),
                correct_abstentions=sum(r.get('expected_action')=='abstain' and r.get('abstained') is True for r in results),
                patches_correct=sum(r.get('expected_action')=='patch' and r.get('correct') is True for r in results),
                regression_escapes=sum(bool(r.get('regression_escape')) for r in results),
                acquisition_llm_calls=sum(m['acquisition_llm_calls'] for m in metrics),
                acquisition_request_characters=sum(m['request_characters'] for m in metrics),
                use_llm_calls=sum(r.get('use_llm_calls',0) for r in results),
                use_request_characters=sum(r.get('request_characters',0) for r in results),
                acquisition_seconds=sum(t['capture_seconds'] for t in tasks) if profile=='synopsis-behavior-memory' else sum(m.get('acquisition_seconds',0) for m in metrics) if metrics else None,
                retrieval_p50_seconds=statistics.median(latencies) if latencies else None,retrieval_p95_seconds=quantile(latencies,.95),
                generation_and_execution_seconds=sum(r['seconds'] for r in results),
                acquisition_charged_once_per_task_not_per_repetition=True)
        profiles[profile]=entry
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(base.glob('*.json*')) if p.name!='summary.json'}
    return dict(protocol='synopsis.competitive-summary.v1',manifest=manifest,profiles=profiles,files=files,
        limits=['Eight synthetic tasks, four held-out task identities repeated twice; repetitions are not independent new tasks.',
                'No real OSS issue/productivity or universal superiority claim.',
                'Same common source-fetch and behavioral executor offered to all profiles; this isolates memory acquisition/retrieval.',
                'Initial development prompts duplicated retrieved text for five profiles. All held-out prompts use the common deduplicated controller; raw initial traces retained.',
                'ShadowFrog official skill capture and viewer/file memory only, not Dream or full IDE workflow. Top-only adapter corrected before evaluation; original receipt retained.',
                'Mem0 spaCy extra unavailable; SDK fallback logged. Graphiti embedded FalkorDB and native custom LLM adapters, not vendor defaults.',
                'Shared cached multilingual MiniLM embeddings for Mem0/Graphiti; exact callable lookup for Synopsis. No retrieval LLM calls.',
                'Wall times are observations on a shared machine with concurrent jobs and cache effects, not a stable throughput ranking.',
                'Full-history retrieval reads the already supplied artifact array; acquisition cost not independently measured.',
                'Request characters are not tokens, billing, dollar cost or model FLOPs. No tuning against held-out gold.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base',type=Path,required=True);args=parser.parse_args()
    result=summarize(args.base);(args.base/'summary.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    for profile,row in result['profiles'].items():
        r=row['reserved'];print(profile,str(r['correct'])+'/'+str(r['completed']),'acquisition_calls='+str(r['acquisition_llm_calls']),'use_calls='+str(r['use_llm_calls']),'errors='+str(r['errors']))
