"""User command installation without symlinks, admin rights or profile edits."""
import os
from pathlib import Path
import sys

import comun

MARKER='rem Synopsis managed command'


def command_folder():
    return Path(os.environ.get('LOCALAPPDATA') or Path.home()/'AppData/Local')/'Synopsis/bin'


def persist_path(folder,dry_run=False):
    import winreg
    current='';kind=winreg.REG_EXPAND_SZ
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as key:current,kind=winreg.QueryValueEx(key,'Path')
    except FileNotFoundError:pass
    if not isinstance(current,str) or kind not in (winreg.REG_SZ,winreg.REG_EXPAND_SZ):
        raise ValueError('unsupported_user_path_preserved')
    normalize=lambda value:os.path.expandvars(value).rstrip('\\/').replace('/','\\').casefold()
    if normalize(str(folder)) in [normalize(p) for p in current.split(';')]:return
    if dry_run:return
    value=current+(';' if current and not current.endswith(';') else '')+str(folder)
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,'Environment',0,winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key,'Path',0,kind,value)
    # New terminals/IDE sessions need the new user environment, not a reboot.
    import ctypes
    result=ctypes.c_size_t()
    from ctypes import wintypes
    send=ctypes.windll.user32.SendMessageTimeoutW
    send.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPCWSTR,wintypes.UINT,wintypes.UINT,ctypes.POINTER(ctypes.c_size_t)]
    try:send(0xffff,0x1a,0,'Environment',0x2,1000,ctypes.byref(result))
    except OSError:pass  # Registry is authoritative; existing processes may retain their environment.


def install(dry_run=False):
    destination=command_folder()/'synopsis.cmd'
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or MARKER.encode() not in destination.read_bytes()[:120]:raise RuntimeError('existing_windows_command_preserved')
    quote=lambda value:str(value).replace('%','%%')
    text='@echo off\r\n'+MARKER+'\r\nsetlocal DisableDelayedExpansion\r\nchcp 65001 >nul\r\nset "PYTHONIOENCODING=utf-8"\r\n"'+quote(sys.executable)+'" -I -S -X utf8 "'+quote(comun.REPO/'bin/synopsis')+'" %*\r\nexit /b %errorlevel%\r\n'
    previous=destination.read_bytes() if destination.exists() else None
    if not dry_run:
        sys.path.insert(0,str(comun.raiz_motor()))
        from archivos import escribir_atomico
        destination.parent.mkdir(parents=True,exist_ok=True)
        try:
            escribir_atomico(destination,text)
            persist_path(destination.parent)
        except Exception:
            if previous is None:destination.unlink(missing_ok=True)
            else:escribir_atomico(destination,previous)
            raise
    else:persist_path(destination.parent,True)
    print(('Crearía' if dry_run else 'Instalado')+' el comando '+str(destination))
    return destination
