"""Platform command contracts shared by installers and health checks."""
import base64
import os
import shlex
import sys


def ps_literal(value):
    value=str(value)
    if any(c in value for c in ('\0','\r','\n')):raise ValueError('invalid_command_value')
    return "'"+value.replace("'","''")+"'"


def python_flags(platform=None):
    return ['-I','-S',*(['-X','utf8'] if (platform or sys.platform)=='win32' else [])]


def hook_command(script,arguments=(),environment=None,platform=None):
    environment=environment or {};platform=platform or sys.platform
    parts=[sys.executable,*python_flags(platform),str(script),*arguments]
    if platform!='win32':
        return ' '.join(shlex.quote(str(p)) for p in [*(str(k)+'='+str(v) for k,v in environment.items()),*parts])
    # EncodedCommand works from cmd.exe, PowerShell and Git Bash without relying
    # on shell-specific assignment/quoting. Explicit UTF-8 preserves event JSON.
    script="$OutputEncoding=[Console]::InputEncoding=[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);"
    for key,value in environment.items():
        if not key.replace('_','').isalnum():raise ValueError('invalid_environment_name')
        script+='$env:'+key+'='+ps_literal(value)+';'
    script+='$synopsisInput=[Console]::In.ReadToEnd();$synopsisInput | & '+' '.join(ps_literal(p) for p in parts)+';exit $LASTEXITCODE'
    return 'powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand '+base64.b64encode(script.encode('utf-16-le')).decode('ascii')


def hook_text(command):
    """Decode our wrapper for ownership checks only; never evaluate commands."""
    marker='powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand '
    if isinstance(command,str) and command.startswith(marker):
        try:return base64.b64decode(command[len(marker):],validate=True).decode('utf-16-le').replace("''","'")
        except (ValueError,UnicodeError):return ''
    return command if isinstance(command,str) else ''


def capabilities(platform=None):
    import shutil
    platform=platform or sys.platform
    isolated=platform.startswith('linux') and bool(shutil.which('bwrap'))
    return dict(platform=platform,memory=True,mcp=True,map=True,
                autostart_backend='launchd' if platform=='darwin' else 'windows-user-run' if platform=='win32' else 'systemd-user' if platform.startswith('linux') else None,
                isolated_experiments=dict(available=isolated,reason=None if isolated else 'Linux with bubblewrap is required; no host execution fallback.'))
