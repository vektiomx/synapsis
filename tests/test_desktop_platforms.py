"""Portable contracts and real per-OS CLI/transport probes, no login changes."""
import base64
import contextlib
import io
import json
import os
from pathlib import Path
import plistlib
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
import urllib.request
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import comun
import desktop_runtime as runtime
import desktop_service as service


class DesktopContractsTest(unittest.TestCase):
    def test_source_windows_bootstraps_have_native_line_endings(self):
        for filename in ('bin/synopsis.cmd','install-windows.cmd'):
            raw=(ROOT/filename).read_bytes();raw.decode('ascii')
            self.assertIn(b'\r\n',raw);self.assertNotIn(b'\n',raw.replace(b'\r\n',b''))

    def test_persistent_map_entry_serves_an_authenticated_private_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);data=base/'data';data.mkdir();config=data/'config.json';config.write_text(json.dumps(dict(fuentes=[],proyectos=[])))
            command=[sys.executable,'-I','-S',str(ROOT/'desktop_map.py'),'--engine',str(ROOT/'engine'),'--data',str(data),'--config',str(config)]
            process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(os.environ,SYNOPSIS_AUTO_REVIEW='0',SYNOPSIS_SEMANTIC_SETUP='off'))
            try:
                deadline=time.monotonic()+15;state=data/'en-vivo/servidor.json';key_file=data/'en-vivo/clave.txt'
                while not (state.exists() and key_file.exists()) and process.poll() is None and time.monotonic()<deadline:time.sleep(.1)
                self.assertTrue(state.exists(),'Private desktop map did not become ready')
                port=json.loads(state.read_text())['puerto'];key=(data/'en-vivo/clave.txt').read_text().strip()
                request=urllib.request.Request(f'http://127.0.0.1:{port}/experience-status',headers={'X-Cerebro-Clave':key})
                with urllib.request.urlopen(request,timeout=5) as response:packet=json.load(response)
                self.assertEqual(packet['projects'],[]);self.assertIsNone(process.poll())
            finally:
                if process.poll() is None:process.terminate()
                try:process.communicate(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.communicate(timeout=5)

    def registry(self):
        values={}
        registry=types.SimpleNamespace(HKEY_CURRENT_USER=1,KEY_SET_VALUE=2,REG_SZ=1,REG_EXPAND_SZ=2)
        registry.OpenKey=lambda *args:contextlib.nullcontext(args[1])
        registry.CreateKeyEx=registry.OpenKey
        def query(key,name):
            if (key,name) not in values:raise FileNotFoundError()
            return values[key,name]
        def save(key,name,reserved,kind,value):values[key,name]=(value,kind)
        registry.QueryValueEx=query;registry.SetValueEx=save;registry.DeleteValue=lambda key,name:values.pop((key,name))
        return registry,values

    def test_windows_autostart_is_user_only_and_remove_preserves_memory(self):
        registry,values=self.registry()
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,LOCALAPPDATA=tmp),patch.dict(sys.modules,winreg=registry),patch('subprocess.Popen') as spawn:
            data=Path(tmp)/'memory';data.mkdir();note=data/'note.md';note.write_text('keep')
            plan=service.windows('install',True);self.assertTrue(plan['preview']);self.assertEqual(values,{})
            receipt=service.windows('install');self.assertTrue(receipt['started']);self.assertEqual(spawn.call_count,1)
            self.assertIn((service.RUN_KEY,service.RUN_NAME),values)
            launcher=Path(tmp)/'Synopsis/bin/synopsis-map.pyw';self.assertTrue(launcher.exists())
            self.assertTrue(service.windows('status')['configured'])
            service.windows('remove');self.assertFalse(launcher.exists());self.assertEqual(note.read_text(),'keep')
            self.assertEqual(values,{})

    def test_windows_autostart_failure_rolls_back_registry_and_launcher(self):
        registry,values=self.registry()
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,LOCALAPPDATA=tmp),patch.dict(sys.modules,winreg=registry),patch('subprocess.Popen',side_effect=OSError('failed start')):
            with self.assertRaises(OSError):service.windows('install')
            self.assertEqual(values,{})
            self.assertFalse((Path(tmp)/'Synopsis/bin/synopsis-map.pyw').exists())

    def test_windows_foreign_autostart_is_never_overwritten(self):
        registry,values=self.registry();values[service.RUN_KEY,service.RUN_NAME]=('another application',1)
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,LOCALAPPDATA=tmp),patch.dict(sys.modules,winreg=registry),patch('subprocess.Popen') as spawn:
            with self.assertRaises(ValueError):service.windows('install')
            self.assertEqual(values[service.RUN_KEY,service.RUN_NAME][0],'another application');spawn.assert_not_called()

    def test_windows_path_append_preserves_existing_entries_and_is_idempotent(self):
        import windows_install
        registry,values=self.registry();values['Environment','Path']=('C:\\existing;C:\\other',2)
        # Broadcast is an OS notification; only the registry transformation is
        # exercised on Linux. Native Windows also runs the same assertion.
        fake=unittest.mock.Mock();fake.argtypes=None
        dll=types.SimpleNamespace(user32=types.SimpleNamespace(SendMessageTimeoutW=fake))
        with patch.dict(sys.modules,winreg=registry),patch('ctypes.windll',dll,create=True):
            windows_install.persist_path(Path('C:/Synopsis/bin'))
            windows_install.persist_path(Path('C:/Synopsis/bin'))
        self.assertEqual(values['Environment','Path'],('C:\\existing;C:\\other;'+str(Path('C:/Synopsis/bin')),2))

    def test_windows_path_invalid_type_is_preserved(self):
        import windows_install
        registry,values=self.registry();values['Environment','Path']=(['unexpected'],7)
        with patch.dict(sys.modules,winreg=registry):
            with self.assertRaises(ValueError):windows_install.persist_path(Path('C:/Synopsis/bin'))
        self.assertEqual(values['Environment','Path'],(['unexpected'],7))

    @unittest.skipIf(sys.platform=='win32','symlink privilege varies on Windows')
    def test_windows_command_rejects_dangling_symlink(self):
        import windows_install
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,LOCALAPPDATA=tmp),patch.object(windows_install,'persist_path') as persist:
            destination=windows_install.command_folder()/'synopsis.cmd';destination.parent.mkdir(parents=True)
            target=Path(tmp)/'missing.cmd';destination.symlink_to(target)
            with self.assertRaises(RuntimeError):windows_install.install()
            self.assertFalse(target.exists());persist.assert_not_called()

    def test_windows_command_update_rolls_back_when_path_write_fails(self):
        import windows_install
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,LOCALAPPDATA=tmp),patch.object(windows_install,'persist_path') as persist:
            destination=windows_install.install();old=destination.read_bytes()
            persist.side_effect=OSError('registry denied')
            with self.assertRaises(OSError):windows_install.install()
            self.assertEqual(destination.read_bytes(),old)
            destination.unlink()
            with self.assertRaises(OSError):windows_install.install()
            self.assertFalse(destination.exists())

    def test_windows_foreign_autostart_with_embedded_owned_path_is_preserved(self):
        import windows_install
        registry,values=self.registry()
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,LOCALAPPDATA=tmp),patch.dict(sys.modules,winreg=registry):
            original='foreign.exe '+str(windows_install.command_folder()/'synopsis-map.pyw')
            values[service.RUN_KEY,service.RUN_NAME]=(original,1)
            with self.assertRaises(ValueError):service.windows('install')
            self.assertEqual(values[service.RUN_KEY,service.RUN_NAME][0],original)

    def test_mac_write_failure_preserves_existing_registration(self):
        sys.path.insert(0,str(ROOT/'engine'))
        with tempfile.TemporaryDirectory() as tmp,patch('pathlib.Path.home',return_value=Path(tmp)),patch('os.getuid',return_value=123,create=True),patch('subprocess.run') as run:
            path=Path(tmp)/'Library/LaunchAgents/com.synopsis.map.plist';path.parent.mkdir(parents=True)
            original=plistlib.dumps(service.launch_agent());path.write_bytes(original)
            with patch('archivos.escribir_atomico',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):service.macos('install')
            self.assertEqual(path.read_bytes(),original);run.assert_not_called()

    def test_linux_unit_uses_persistent_entry_and_escapes_specifiers(self):
        namespace=runpy.run_path(str(ROOT/'linux/instalar_servicio_mapa.py'))
        with patch.object(service,'command',return_value=['/usr/bin/python3','-I','-S','/tmp/100%/desktop_map.py']):
            unit=namespace['unidad']()
        self.assertIn('100%%/desktop_map.py',unit)
        self.assertNotIn(' abrir ',unit);self.assertNotIn('--apagar-solo',unit)

    def test_windows_hook_encoding_preserves_unicode_quotes_and_environment(self):
        command=runtime.hook_command("C:\\Users\\O'Brien\\Mémoria A\\bridge.py",environment={'SYNOPSIS_DATA':"C:\\a b\\O'Brien"},platform='win32')
        self.assertTrue(command.startswith('powershell.exe -NoLogo'))
        script=base64.b64decode(command.split()[-1]).decode('utf-16-le')
        self.assertIn("O''Brien",script);self.assertIn('ReadToEnd',script)
        self.assertIn("'-X' 'utf8'",script)
        self.assertIn('Mémoria A',runtime.hook_text(command));self.assertIn("O'Brien",runtime.hook_text(command))
        self.assertNotIn('EncodedCommand',runtime.hook_text(command))

    def test_windows_open_never_requires_unix_shell(self):
        namespace=runpy.run_path(str(ROOT/'bin/synopsis'))
        with patch.object(sys,'argv',['synopsis','abrir']),patch.object(sys,'platform','win32'),patch('subprocess.run',return_value=subprocess.CompletedProcess([],0)) as run:
            self.assertEqual(namespace['main'](),0)
        command=run.call_args.args[0]
        self.assertEqual(command[0],sys.executable);self.assertNotIn('/bin/sh',command)
        self.assertTrue(command[-2].endswith('synopsis.py'));self.assertEqual(command[-1],'abrir')

    def test_capabilities_do_not_advertise_host_execution_on_desktops(self):
        for platform in ('darwin','win32'):
            result=runtime.capabilities(platform)
            self.assertTrue(result['mcp']);self.assertFalse(result['isolated_experiments']['available'])

    def test_launch_agent_uses_absolute_arguments_and_is_persistent(self):
        definition=service.launch_agent();encoded=plistlib.dumps(definition)
        self.assertEqual(plistlib.loads(encoded),definition)
        self.assertTrue(Path(definition['ProgramArguments'][0]).is_absolute())
        self.assertIn('desktop_map.py',' '.join(definition['ProgramArguments']))
        self.assertNotIn('--apagar-solo',definition['ProgramArguments'])
        self.assertTrue(definition['RunAtLoad'])

    def test_mac_install_rolls_back_after_bootstrap_failure(self):
        with tempfile.TemporaryDirectory() as tmp,patch('pathlib.Path.home',return_value=Path(tmp)),patch('os.getuid',return_value=123,create=True),patch('subprocess.run',side_effect=subprocess.CalledProcessError(1,['launchctl'])):
            with self.assertRaises(subprocess.CalledProcessError):service.macos('install')
            self.assertFalse((Path(tmp)/'Library/LaunchAgents/com.synopsis.map.plist').exists())

    def test_mac_dry_run_and_foreign_agent_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp,patch('pathlib.Path.home',return_value=Path(tmp)),patch('os.getuid',return_value=123,create=True),patch('subprocess.run') as run:
            plan=service.macos('install',True);self.assertTrue(plan['preview']);self.assertEqual(list(Path(tmp).iterdir()),[])
            path=Path(plan['path']);path.parent.mkdir(parents=True);original=plistlib.dumps(dict(Label='other',ProgramArguments=['keep']))
            path.write_bytes(original)
            with self.assertRaises(ValueError):service.macos('install')
            self.assertEqual(path.read_bytes(),original);run.assert_not_called()

    def test_windows_command_does_not_replace_foreign_file(self):
        import windows_install
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,LOCALAPPDATA=tmp),patch.object(windows_install,'persist_path') as persist:
            destination=windows_install.install(True);self.assertFalse(destination.exists())
            windows_install.install();windows_install.install()
            self.assertIn('-I -S',destination.read_text());self.assertNotIn('mklink',destination.read_text())
            destination.write_bytes(b'foreign command')
            with self.assertRaises(RuntimeError):windows_install.install()
            self.assertEqual(destination.read_bytes(),b'foreign command')

    def test_five_clients_install_and_stdio_probe_with_private_home(self):
        namespace=runpy.run_path(str(ROOT/'bin/synopsis'))
        with tempfile.TemporaryDirectory(prefix='synopsis-desktop-') as tmp:
            home=Path(tmp);config=home/'config.json';config.write_text(json.dumps(dict(fuentes=[],proyectos=[])))
            for folder in ('.claude','.codex','.gemini/config','.cursor','.config/opencode'):(home/folder).mkdir(parents=True)
            env=dict(HOME=tmp,USERPROFILE=tmp,LOCALAPPDATA=str(home/'AppData/Local'),APPDATA=str(home/'AppData/Roaming'),XDG_CONFIG_HOME=str(home/'.config'),SYNOPSIS_ROOT=str(ROOT/'engine'),SYNOPSIS_DATA=str(home/'data'),CLAUDE_PLUGIN_DATA=str(home/'data'),CEREBRO_CONFIG=str(config),SYNOPSIS_SEMANTIC_SETUP='off',SYNOPSIS_AUTO_REVIEW='0')
            with patch.dict(os.environ,env),patch('pathlib.Path.home',return_value=home),patch('comun.instalar_comando'),patch.object(sys,'argv',['synopsis','install','--no-service','--no-semantic']),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(namespace['main'](),0)
                from integration_health import check
                result=check(expected_clients=['claude','codex','antigravity','opencode','cursor'])
            self.assertTrue(result['ready'],result);self.assertEqual(result['tools'],15)

    @unittest.skipUnless(sys.platform=='win32','requires native Windows cmd and PowerShell')
    def test_native_windows_hook_roundtrip_without_git_bash(self):
        with tempfile.TemporaryDirectory() as tmp:
            bridge=Path(tmp)/"mémoire O'Brien.py";bridge.write_text('import json,sys\nprint(json.dumps(json.load(sys.stdin),ensure_ascii=False))\n',encoding='utf-8')
            command=runtime.hook_command(bridge)
            payload=dict(text='áé 中文',path="C:\\O'Brien\\un espacio")
            result=subprocess.run(command.split(),input=json.dumps(payload,ensure_ascii=False),text=True,encoding='utf-8',capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout),payload)

    @unittest.skipUnless(sys.platform=='win32','requires native Windows cmd')
    def test_native_installed_cmd_runs_the_full_cli(self):
        import windows_install
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,LOCALAPPDATA=tmp),patch.object(windows_install,'persist_path'):
            path=windows_install.install()
            result=subprocess.run(['cmd.exe','/d','/c',str(path),'--version'],capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr);self.assertIn('Synopsis',result.stdout)


if __name__=='__main__':unittest.main()
