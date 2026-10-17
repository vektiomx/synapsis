import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

root = Path('/tmp/synopsis-shadowfrog-audit')
work = Path(tempfile.mkdtemp(prefix='shadowfrog-audit-probes-'))
shutil.copytree(root / 'examples/coupon-demo', work / 'example')
example = work / 'example'
env = {'PATH': '/usr/bin:/bin:/usr/local/bin', 'HOME': str(work), 'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_SYSTEM': '/dev/null', 'SHADOWFROG_TMP_DIR': str(work)}
results = []
def run(name, args, stdin=None):
    p = subprocess.run(args, input=stdin, capture_output=True, text=True, cwd=example, env=env, timeout=15)
    record = {'name': name, 'exit_code': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}
    results.append(record)
    return record

viewer = str(root / 'skills/shadow-frog-viewer/shadow-viewer.py')
summary = run('viewer-summary', ['python3', '-B', viewer, '--shadow-dir', '.shadow', '--summary'])
assert summary['exit_code'] == 0 and 'cart.py' in summary['stdout']
top = run('viewer-top', ['python3', '-B', viewer, '--shadow-dir', '.shadow', '--top', 'cart.py'])
assert top['exit_code'] == 0 and len(top['stdout'].strip()) <= 600
invariants = run('viewer-invariants', ['python3', '-B', viewer, '--shadow-dir', '.shadow', '--check-invariants'])
assert invariants['exit_code'] == 0
claim = 'Returns None for unknown codes (via dict.get default), not an exception. Callers must handle None.'
cite = run('citation-increment', ['python3', '-B', str(root / 'skills/shadow-frog/shadow-cite.py'), '.shadow/cart.py.md', '--symbol', 'load_coupon', '--text', claim])
assert cite['exit_code'] == 0 and '0 -> 1' in cite['stdout']
payload = json.dumps({'tool_name':'Edit', 'tool_input': {'file_path':'cart.py'}})
hook = run('hook-context', ['bash', str(root / 'hook-templates/scripts/shadow-frog-pre-tool.sh')], payload)
context = json.loads(hook['stdout'])
assert hook['exit_code'] == 0 and 'Actionable discoveries for cart.py' in context['additionalContext']
assert context['additionalContext'] == context['hookSpecificOutput']['additionalContext']
out = {'repository_sha':'1f6e615c2ddfeffa8ba709401afafa1e9ffa9452', 'fixture':str(example), 'result':'passed', 'limitations':'No LLM or Dream run; no git commit/push, installation, private remote or user auth. Hook delivers actual actionable discoveries by resolving the source viewer script; this is direct invocation, not a live Claude/Copilot client.', 'probes':results}
Path('/tmp/shadowfrog-audit-probes.json').write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(json.dumps({'result':'passed', 'probes':len(results), 'output':'/tmp/shadowfrog-audit-probes.json'}))
