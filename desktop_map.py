"""Persistent map entrypoint for user-login managers; never opens a browser."""
import argparse
import os
from pathlib import Path
import sys


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--engine',type=Path,required=True);parser.add_argument('--data',type=Path,required=True);parser.add_argument('--config')
    args=parser.parse_args();engine=args.engine.resolve();data=args.data.resolve()
    if not (engine/'servidor.py').is_file():raise ValueError('map_engine_not_found')
    data.mkdir(parents=True,exist_ok=True,mode=0o700)
    os.environ.update(CLAUDE_PLUGIN_ROOT=str(engine),CLAUDE_PLUGIN_DATA=str(data),SYNOPSIS_ROOT=str(engine),SYNOPSIS_DATA=str(data),
                      CLAUDE_PLUGIN_OPTION_SERVIR_CONTEXTO='true',PYTHONIOENCODING='utf-8')
    if args.config:os.environ['CEREBRO_CONFIG']=args.config
    # launchd has a minimal PATH; use absolute interpreter and common user CLI
    # locations. Do not source profiles or execute user shell startup files.
    additions=[str(Path(sys.executable).parent),str(Path.home()/'.local/bin')]
    if sys.platform=='darwin':additions+=['/opt/homebrew/bin','/usr/local/bin']
    os.environ['PATH']=os.pathsep.join(dict.fromkeys(additions+os.environ.get('PATH','').split(os.pathsep)))
    sys.path.insert(0,str(engine));sys.dont_write_bytecode=True
    sys.argv=['synopsis map service','--sin-navegador']
    # servidor directly: the interactive wrapper adds --apagar-solo, which is
    # unsuitable for an always-on login agent.
    import servidor
    # Background mode must publish its private key file even when no browser
    # or authenticated HTTP request has happened yet.
    servidor.clave()
    return servidor.main()


if __name__=='__main__':raise SystemExit(main())
