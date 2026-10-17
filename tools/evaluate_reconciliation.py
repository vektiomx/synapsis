#!/usr/bin/env python3
"""One real-model semantic reconciliation scenario; synthetic memories only."""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'engine'))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--provider',default='codex')
    parser.add_argument('--model')
    parser.add_argument('--output')
    args=parser.parse_args()
    original=Path.home()
    with tempfile.TemporaryDirectory(prefix='synopsis-semantic-review-') as tmp:
        base=Path(tmp)
        for relative in ('.codex/auth.json','.claude/.credentials.json','.local/share/opencode/auth.json'):
            source=original/relative
            if source.is_file():
                target=base/'home'/relative
                target.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
                shutil.copyfile(source,target)
                target.chmod(0o600)
        cfg=base/'config.json'
        cfg.write_text(json.dumps(dict(usuario='Synthetic review',fuentes=[],proyectos=[])))
        os.environ.update(HOME=str(base/'home'),XDG_CONFIG_HOME=str(base/'home/.config'),XDG_DATA_HOME=str(base/'home/.local/share'),
            XDG_STATE_HOME=str(base/'home/.local/state'),XDG_CACHE_HOME=str(base/'home/.cache'),PWD=str(base),
            SYNOPSIS_DATA=str(base/'state'),CLAUDE_PLUGIN_DATA=str(base/'state'),CEREBRO_CONFIG=str(cfg),SYNOPSIS_EMBEDDINGS='off',SYNOPSIS_CONTROLLED_RUN='1')
        os.environ.pop('CODEX_HOME',None)
        project=base/'project';project.mkdir()
        folder=base/'memory'
        from memory_store import MemoryStore
        from model_provider import ModelTransport
        from reconciliation import review
        store=MemoryStore(folder)
        texts={'release-policy':'Deploy only if all automated tests pass.',
               'deployment-rule':'Deployment is not allowed unless every automated test has passed.',
               'iris-rule-a':'At present the retention of queue Iris is 389 seconds.',
               'iris-rule-b':'At present the retention of queue Iris is 127 seconds.'}
        for name,content in texts.items():
            store.save(filename=name,name=name,description=name,content=content,kind='project',index_line=f'- [{name}]({name}.md)',source='user:synthetic')
        before={name:(folder/(name+'.md')).read_bytes() for name in texts}
        outputs=[]
        transport=ModelTransport(args.provider,args.model,120)
        complete=transport.complete
        def capture(*values):
            result=complete(*values)
            outputs.append(result)
            return result
        transport.complete=capture
        try:
            plan=review(str(project),folder,transport)
            duplicate=any(f['relation']=='duplicate' and {'release-policy','deployment-rule'}<=set(f['files']) for f in plan['findings'])
            contradiction=any(f['relation']=='contradiction' and {'iris-rule-a','iris-rule-b'}<=set(f['files']) for f in plan['findings'])
            untouched=all((folder/(name+'.md')).read_bytes()==text for name,text in before.items())
            safe=not any(a['filename'] in ('iris-rule-a','iris-rule-b') for a in plan['actions'])
            report=dict(passed=duplicate and contradiction and untouched and safe,provider=args.provider,model=args.model,
                        checks=dict(semantic_duplicate=duplicate,contradiction=contradiction,read_only=untouched,no_invented_winner=safe),
                        findings=plan['findings'],actions=len(plan['actions']),limitation='One synthetic review; not a broad semantic benchmark.')
        except (ValueError,OSError) as error:
            report=dict(passed=False,error=str(error),model_output=outputs[-1] if outputs else None)
        serialized=json.dumps(report,ensure_ascii=False,indent=2)
        print(serialized)
        if args.output: Path(args.output).write_text(serialized+'\n')
        return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
