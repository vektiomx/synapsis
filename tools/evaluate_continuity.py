#!/usr/bin/env python3
"""Bounded real-model continuity evaluation; isolated state and synthetic facts only."""
import argparse
import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'engine'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--provider', default='auto')
    parser.add_argument('--model')
    parser.add_argument('--second-model')
    parser.add_argument('--output')
    args = parser.parse_args()
    original_home = Path.home()
    with tempfile.TemporaryDirectory(prefix='synopsis-real-eval-') as tmp:
        base = Path(tmp)
        project = base / 'project'
        project.mkdir()
        # Native CLI account copies are temporary, private, never printed or retained.
        (base / 'home').mkdir(mode=0o700)
        for source, relative in [(original_home / '.local/share/opencode/auth.json', '.local/share/opencode/auth.json'),
                                 (original_home / '.codex/auth.json', '.codex/auth.json'),
                                 (original_home / '.claude/.credentials.json', '.claude/.credentials.json')]:
            if source.is_file():
                target = base / 'home' / relative
                target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
                shutil.copyfile(source, target)
                target.chmod(0o600)
        # Preserve provider definitions for custom gateways, without loading plugins,
        # instructions, permissions or unrelated user settings into the fixture.
        sys.path.insert(0,str(ROOT))
        from integration_setup import read_jsonc
        providers={}
        for name in ('opencode.json','opencode.jsonc'):
            path=original_home/'.config/opencode'/name
            if path.is_file():
                providers.update(read_jsonc(path).get('provider',{}))
        native_config=base/'home/.config/opencode/opencode.json'
        native_config.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
        native_config.write_text(json.dumps(dict(provider=providers)))
        native_config.chmod(0o600)
        config=base/'config.json'
        config.write_text(json.dumps(dict(usuario='Synthetic evaluation', fuentes=[], proyectos=[])))
        os.environ.update(HOME=str(base/'home'), XDG_CONFIG_HOME=str(base/'home/.config'), XDG_DATA_HOME=str(base/'home/.local/share'),
            XDG_STATE_HOME=str(base/'home/.local/state'), XDG_CACHE_HOME=str(base/'home/.cache'),
            SYNOPSIS_DATA=str(base/'state'), CEREBRO_CONFIG=str(config), CLAUDE_PLUGIN_DATA=str(base/'state'),
            SYNOPSIS_EMBEDDINGS='off', SYNOPSIS_CONTROLLED_RUN='1', PYTHONDONTWRITEBYTECODE='1')
        os.environ.pop('CODEX_HOME', None)
        from model_provider import ModelTransport
        from controlled_run import run, RunError
        from memory_store import MemoryStore
        from conector_mcp import carpeta_memoria_de
        traces=[]
        class TracedTransport(ModelTransport):
            def __call__(self,request):
                result=super().__call__(request)
                traces.append(dict(evidence=[dict(id=s['id'],kind=s['kind'],text=s['text']) for s in request.get('grounding_evidence',{}).get('sources',[])],failures=request.get('grounding_evidence',{}).get('failures',[]),proposal=result))
                return result
        transport=TracedTransport(args.provider,args.model,120)
        other=TracedTransport(args.provider,args.second_model or args.model,120)
        code='iris-'+uuid.uuid4().hex[:10]
        rows=[]
        prompts=[f'Recuerda estas dos decisiones explícitas del usuario para este proyecto ficticio, en una sola nota iris-policy:\n\nLa retención de la cola Iris es 127 segundos.\n\nEl código operativo de Iris es {code}.',
                 'Corrección explícita: actualiza la misma nota iris-policy y conserva el código operativo vigente.\n\nLa retención de la cola Iris es 389 segundos.',
                 '¿Cuántos segundos dura la retención de la cola Iris y cuál es su código operativo? No crees otra nota.']
        try:
            for i,prompt in enumerate(prompts):
                result=run(project=str(project),session='continuity',prompt=prompt,transport=transport if i<2 else other)
                rows.append(dict(stage=('save','correct','recall')[i],receipt=result['receipt'],answer=result['answer']))
            blind=base/'blind-project';blind.mkdir()
            baseline=run(project=str(blind),session='blind',prompt=prompts[-1],transport=other)
            answer=rows[-1]['answer']
            history=MemoryStore(carpeta_memoria_de(str(project))).history('iris-policy')
            passed=('389' in answer and code in answer and code not in baseline.get('answer','') and
                    len(history)==2 and '389' in history[-1]['text'] and code in history[-1]['text'] and '127 segundos' not in history[-1]['text'] and baseline['verification']['status']=='abstained')
            report=dict(passed=passed, provider=transport.provider, model=transport.model, recall_model=other.model,
                        scenario='synthetic private fact, correction, independent inference, blind baseline',
                        checks=dict(corrected_value='389' in answer, private_code=code in answer,
                                    baseline_has_no_private_code=code not in baseline.get('answer',''),
                                    baseline_abstained=baseline['verification']['status']=='abstained', revisions=len(history), single_note=len(list(carpeta_memoria_de(str(project)).glob('iris-policy.md')))==1),
                        stages=rows,baseline=baseline, trace=traces, limitation='One synthetic scenario, not a broad model intelligence benchmark.')
        except (ValueError,OSError) as error:
            report=dict(passed=False, error=error.code if isinstance(error,RunError) else str(error) if isinstance(error,ValueError) and str(error).startswith(('model_','native_','provider_')) else type(error).__name__, stages=rows, trace=traces, pending=error.status if isinstance(error,RunError) else None)
        serialized=json.dumps(report,ensure_ascii=False,indent=2)
        print(serialized)
        if args.output:
            Path(args.output).write_text(serialized+'\n')
        return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
