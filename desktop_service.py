"""Per-user desktop autostart, no sudo, passwords or machine-wide changes."""
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

import comun

LABEL='com.synopsis.map'
RUN_KEY=r'Software\Microsoft\Windows\CurrentVersion\Run'
RUN_NAME='SynopsisMap'


def command(windowless=False):
    python=Path(sys.executable)
    if windowless and python.with_name('pythonw.exe').is_file():python=python.with_name('pythonw.exe')
    result=[str(python),'-I','-S',str(comun.REPO/'desktop_map.py'),'--engine',str(comun.raiz_motor()),'--data',str(comun.carpeta_datos())]
    if os.environ.get('CEREBRO_CONFIG'):result+=['--config',str(Path(os.environ['CEREBRO_CONFIG']).resolve())]
    return result


def launch_agent():
    return dict(Label=LABEL,ProgramArguments=command(),RunAtLoad=True,KeepAlive=dict(SuccessfulExit=False),ThrottleInterval=10,
                ProcessType='Background',WorkingDirectory=str(comun.REPO),
                EnvironmentVariables=dict(PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'))


def _owned(args):
    return isinstance(args,list) and any(Path(str(part)).name=='desktop_map.py' for part in args)


def macos(action,dry_run=False):
    path=Path.home()/'Library/LaunchAgents'/f'{LABEL}.plist'
    if path.is_symlink():raise ValueError('symlink_launch_agent_preserved')
    domain=f'gui/{os.getuid()}';target=domain+'/'+LABEL
    old=path.read_bytes() if path.exists() else None
    if old is not None:
        data=plistlib.loads(old)
        if data.get('Label')!=LABEL or not _owned(data.get('ProgramArguments')):raise ValueError('foreign_launch_agent_preserved')
    if action=='status':
        result=subprocess.run(['launchctl','print',target],capture_output=True,text=True,timeout=15)
        return dict(backend='launchd',configured=old is not None,loaded=result.returncode==0,path=str(path))
    if dry_run:return dict(backend='launchd',action=action,preview=True,path=str(path),definition=launch_agent() if action=='install' else None)
    if action=='remove':
        if old is not None:
            loaded=subprocess.run(['launchctl','print',target],capture_output=True,timeout=15).returncode==0
            if loaded:subprocess.run(['launchctl','bootout',target],check=True,capture_output=True,timeout=15)
            path.unlink()
        return dict(backend='launchd',removed=True)
    path.parent.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(comun.raiz_motor()))
    from archivos import escribir_atomico
    new=plistlib.dumps(launch_agent()).decode('utf-8')
    unloaded=False
    try:
        escribir_atomico(path,new);path.chmod(0o600)
        if old is not None and subprocess.run(['launchctl','print',target],capture_output=True,timeout=15).returncode==0:
            subprocess.run(['launchctl','bootout',target],check=True,capture_output=True,timeout=15)
            unloaded=True
        subprocess.run(['launchctl','bootstrap',domain,str(path)],check=True,capture_output=True,timeout=20)
    except (OSError,subprocess.SubprocessError):
        if old is None:path.unlink(missing_ok=True)
        else:
            escribir_atomico(path,old.decode('utf-8'))
            if unloaded:subprocess.run(['launchctl','bootstrap',domain,str(path)],capture_output=True,timeout=20)
        raise
    return dict(backend='launchd',configured=True,path=str(path))


def windows(action,dry_run=False):
    import winreg
    current=None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,RUN_KEY) as key:current,kind=winreg.QueryValueEx(key,RUN_NAME)
    except FileNotFoundError:pass
    from windows_install import command_folder
    launcher=command_folder()/'synopsis-map.pyw'
    marker='# Synopsis managed map launcher'
    if launcher.is_symlink() or launcher.exists() and not launcher.read_text(encoding='utf-8').startswith(marker):raise ValueError('foreign_map_launcher_preserved')
    interpreter=command(windowless=True)[0]
    definition=subprocess.list2cmdline([interpreter,'-I','-S',str(launcher)])
    if current is not None and (not isinstance(current,str) or current!=definition or kind!=winreg.REG_SZ):raise ValueError('foreign_windows_autostart_preserved')
    if action=='install' and len(definition.encode('utf-16-le'))//2>260:raise ValueError('windows_autostart_command_too_long')
    if action=='status':return dict(backend='windows-user-run',configured=current is not None,entry=RUN_NAME)
    if dry_run:return dict(backend='windows-user-run',action=action,preview=True,command=definition if action=='install' else None)
    if action=='remove':
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,RUN_KEY,0,winreg.KEY_SET_VALUE) as key:
            if current is not None:winreg.DeleteValue(key,RUN_NAME)
        launcher.unlink(missing_ok=True)
        return dict(backend='windows-user-run',removed=True)
    previous=launcher.read_bytes() if launcher.exists() else None
    registry_written=False
    sys.path.insert(0,str(comun.raiz_motor()))
    from archivos import escribir_atomico
    try:
        launcher.parent.mkdir(parents=True,exist_ok=True)
        text=marker+'\nimport runpy,sys\nsys.argv='+repr(command(windowless=True)[3:])+'\nrunpy.run_path(sys.argv[0],run_name="__main__")\n'
        escribir_atomico(launcher,text)
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,RUN_KEY,0,winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key,RUN_NAME,0,winreg.REG_SZ,definition)
            registry_written=True
        subprocess.Popen([interpreter,'-I','-S',str(launcher)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except OSError:
        if registry_written:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,RUN_KEY,0,winreg.KEY_SET_VALUE) as key:
                if current is None:winreg.DeleteValue(key,RUN_NAME)
                else:winreg.SetValueEx(key,RUN_NAME,0,kind,current)
        if previous is None:launcher.unlink(missing_ok=True)
        else:escribir_atomico(launcher,previous.decode('utf-8'))
        raise
    return dict(backend='windows-user-run',configured=True,started=True)


def manage(action,dry_run=False):
    if action not in ('install','remove','status'):raise ValueError('invalid_service_action')
    if sys.platform=='darwin':return macos(action,dry_run)
    if sys.platform=='win32':return windows(action,dry_run)
    if sys.platform.startswith('linux'):
        if action=='status':
            result=subprocess.run(['systemctl','--user','is-active','synopsis-mapa.service'],capture_output=True,text=True,timeout=15)
            return dict(backend='systemd-user',active=result.returncode==0)
        args=[sys.executable,str(comun.REPO/'linux/instalar_servicio_mapa.py')]
        if action=='remove':args+=['--quitar']
        if dry_run:args+=['--dry-run']
        subprocess.run(args,check=True,timeout=30)
        return dict(backend='systemd-user',action=action,preview=dry_run)
    return dict(backend=None,available=False)
