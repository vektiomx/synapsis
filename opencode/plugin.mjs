import { spawn } from 'node:child_process';

// No shell, dependency install, network listener or per-model bridge is required.
export function createPlugin(options, transport) {
  const invoke = transport || (row => new Promise(resolve => {
    const child = spawn(options.python, ['-I', '-S', options.bridge], {
      env: { ...process.env, ...options.environment }, stdio: ['pipe', 'pipe', 'pipe']
    });
    let output = '', size = 0;
    const timer = setTimeout(() => child.kill(), 28000);
    const finish = value => { clearTimeout(timer); resolve(value); };
    child.on('error', () => finish({ contexts: [], errors: ['transport'] }));
    child.stdout.on('data', chunk => {
      size += chunk.length;
      if (size > 1024 * 1024) child.kill();
      else output += chunk.toString();
    });
    child.stderr.resume();
    child.stdin.on('error', () => {});
    child.on('close', code => {
      try { finish(code === 0 ? JSON.parse(output) : { contexts: [], errors: ['transport'] }); }
      catch { finish({ contexts: [], errors: ['invalid_response'] }); }
    });
    child.stdin.end(JSON.stringify(row));
  }));
  return async ({ directory }) => {
    const sessions = new Map();
    const tools = { bash: 'Bash', read: 'Read', write: 'Write', edit: 'Edit',
                    multiedit: 'MultiEdit', task: 'Task', grep: 'Grep', glob: 'Glob' };
    const args = value => ({ ...value,
      file_path: value?.file_path || value?.filePath,
      old_string: value?.old_string ?? value?.oldString,
      new_string: value?.new_string ?? value?.newString });
    const state = id => {
      if (!sessions.has(id)) {
        if (sessions.size >= 128) sessions.delete(sessions.keys().next().value);
        sessions.set(id, { started: false, context: '', userMessageID: null, assistantMessageID: null, assistantIDs: new Set(), texts: new Map() });
      }
      return sessions.get(id);
    };
    const run = async (id, event, fields = {}) => {
      if (!id) return { contexts: [] };
      const result = await invoke({ ...fields, session_id: id, cwd: directory, hook_event_name: event });
      return result;
    };
    const context = result => [...(result.contexts || []), ...(result.warnings || [])].join('\n').slice(0, 16000);
    return {
      config: async config => {
        config.mcp ||= {};
        const current = config.mcp.synopsis;
        if (current && JSON.stringify(current) !== JSON.stringify(options.mcp)) {
          const owned = current.environment?.SYNOPSIS_ROOT && current.command?.some(arg => /mcp(_entry)?\.py$/.test(arg));
          if (!owned) throw new Error('Synopsis: an unrelated MCP already uses this name.');
        }
        config.mcp.synopsis = structuredClone(options.mcp);
      },
      'chat.message': async (input, output) => {
        const entry = state(input.sessionID);
        let initial = '';
        if (!entry.started) {
          initial = context(await run(input.sessionID, 'SessionStart'));
          entry.started = true;
        }
        const prompt = output.parts.filter(part => part.type === 'text' && !part.synthetic).map(part => part.text).join('\n').slice(0, 20000);
        entry.userMessageID = input.messageID || output.message?.id;
        entry.assistantMessageID = null; entry.assistantIDs.clear(); entry.texts.clear();
        entry.context = [initial, context(await run(input.sessionID, 'UserPromptSubmit', { prompt, message_id: input.messageID || output.message?.id }))].filter(Boolean).join('\n').slice(0, 16000);
      },
      'experimental.chat.system.transform': async (input, output) => {
        const value = sessions.get(input.sessionID)?.context;
        if (value) output.system.push('<synopsis-memory>\n' + value + '\n</synopsis-memory>');
      },
      'tool.execute.before': async (input, output) => {
        const result = await run(input.sessionID, 'PreToolUse', { tool_name: tools[input.tool] || input.tool, tool_input: args(output.args) });
        if (result.decision && result.decision.permissionDecision !== 'allow') {
          throw new Error(result.decision.permissionDecisionReason || 'Synopsis: review required.');
        }
      },
      'tool.execute.after': async (input, output) => {
        const result = await run(input.sessionID, 'PostToolUse', { tool_name: tools[input.tool] || input.tool,
          tool_input: args(input.args), tool_response: output.output, tool_use_id: input.callID });
        const extra = context(result);
        if (extra) {
          const entry = state(input.sessionID);
          entry.context = [entry.context, extra].filter(Boolean).join('\n').slice(-16000);
        }
      },
      'experimental.session.compacting': async (input, output) => {
        const result = await run(input.sessionID, 'SessionStart', { source: 'compact' });
        const extra = context(result);
        if (extra) output.context.push(extra);
        sessions.delete(input.sessionID);
      },
      event: async ({ event }) => {
        const info = event.properties?.info;
        if (event.type === 'message.updated' && info?.role === 'assistant') {
          const entry = sessions.get(info.sessionID);
          if (entry && info.parentID === entry.userMessageID) {
            entry.assistantMessageID = info.id;
            if (entry.assistantIDs.size < 16) entry.assistantIDs.add(info.id);
          }
        }
        if (event.type === 'message.part.updated') {
          const part = event.properties?.part;
          const entry = sessions.get(part?.sessionID);
          if (entry && part.type === 'text' && entry.assistantIDs.has(part.messageID) && entry.texts.size < 32) {
            // 10001 intentionally causes rejection rather than silently truncating a claim.
            entry.texts.set(part.id, { message: part.messageID, text: String(part.text || '').slice(0,10001) });
          }
        }
        const id = event.properties?.sessionID || event.properties?.info?.id;
        if (event.type === 'session.idle') {
          const entry = sessions.get(id);
          const text = entry ? [...entry.texts.values()].filter(p => p.message === entry.assistantMessageID).map(p => p.text).join('\n').slice(0,10001) : '';
          await run(id, 'Stop', { message_id: entry?.userMessageID, last_assistant_message: text });
        }
        if (event.type === 'session.deleted') {
          await run(id, 'SessionEnd');
          sessions.delete(id);
        }
      }
    };
  };
}
