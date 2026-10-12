# Synapsis — one shared memory for Claude Code, Codex, and Antigravity

*[Versión en español](README.md)*

Synapsis connects Claude Code, Codex, and Antigravity to the same live memory: each
tool gets real lifecycle hooks (not just an MCP server the model may or may not decide
to call), all pointing at the same engine and the same live 3D memory map.

![The live map](docs-img/mapa-en-vivo.gif)

## What it does

- **A map of your notes.** It gathers each project's memory
  (`~/.claude/projects/*/memory/`) and draws it as a brain: each note is a neuron, and
  every time a note names another one, a connection.
- **Live.** While you work (from any of the 3 tools), you see which note is being read,
  which file is being edited, which agent was launched, and in which chat — all on the
  same page, no matter which of the 3 tools generated it.
- **A health checker.** Reviews the memory: links to notes that no longer exist, notes
  nobody references, duplicate memories, incomplete headers.
- **A search tool.** Says which notes to read first for a topic, flags data that might
  be outdated, and gathers the recorded decisions that touch it — before answering.
- **Learns from your usage.** What gets used together gets connected; what stops
  repeating gets forgotten. Each machine learns from its own usage.

What `synapsis` adds on top of that: the three tools (Claude Code, Codex, Antigravity)
feed and read **the same** brain, with real hooks in all three — not only in the one
that has the official plugin.

## How the engine searches and learns, in short

It's not semantic indexing and there are no embeddings: it's lexical word search
(BM25-style, with typo correction), combined with a graph of which notes and files get
used together. That graph is actually pruned — weak connections fade away on their
own over time, they don't pile up forever.

**What it learned on its own**, with nobody telling it which files belonged together
(real output from `cerebro.py --aprendido`, taken after the session where a new
category was added to a service catalog — the files touched together are exactly the
ones it connected):

![Learned co-occurrence weight between files](docs-img/coocurrencia-aprendida.svg)

**How well it actually works in practice, unvarnished:** of the notes it recommended,
this is how many times they actually got read afterward (out of every 10 times it
recommended them):

![Effectiveness of the recommendations](docs-img/efectividad-pistas.svg)

This is honest on purpose: some notes get used afterward almost every time, others
almost never. It's not a marketing number — it's the real metric the engine itself
keeps (`aprendido.json`) to calibrate itself.

**Why that happened, and the real fix.** Digging into the 0-out-of-10, we found the
exact cause: the engine always tried to fill a fixed quota of 4 notes per response,
even when none were actually relevant — and the typo corrector sometimes "corrects" a
word into a different, unrelated but valid word (both real, 1-2 letters apart).
Measured in this same session, same question, before and after adding a minimum score
to qualify for that quota:

| | Before | After |
|---|---|---|
| Notices for a question unrelated to any note | 3 (2 were pure noise) | 1 |
| A genuinely related question | 3 correct notes | 3 correct notes (unchanged) |

The engine's own official smoke test (753 cases) was also run: 750 passed, 3 are
Windows/PowerShell-specific and don't apply on this machine — no real failures.

**Round two: the fixed floor wasn't enough.** Testing with more real questions turned
up a case the 1.0 floor didn't catch: asking about payroll also pulled in "Landing
design direction" (score 2.1, above the floor, but only 18% of the score of the note
that actually matched, 11.38). A second rule got added: besides the fixed floor, also
drop anything that doesn't reach 30% of that query's best score.

| Real question | Before (fixed floor only) | After (+ relative floor) |
|---|---|---|
| "how's payroll going this week" | Payroll + Landing design | Payroll only |
| "landing page in remotion" | Landing + Payroll | Landing only |

Confirmed again against the official smoke test (750/753, unchanged) and synapsis's
own suite (10/10).

**Round three: the typo corrector kept inventing relationships.** The "readme"→"read"
case (six letters, two apart) got through because the corrector allowed correcting to
2 letters apart for any word, no matter how short. That got restricted: 2-letter-apart
corrections now only apply to words of 8+ letters; shorter ones only get 1-letter-apart
corrections. Confirmed: "readme" no longer gets "corrected" to "read".

**What's left, honestly:** "nuevo"→"nueve" and "trae"→"true" still get through — both
are real words, 1 letter apart, the smallest distance that exists. Without a full
dictionary (which this project deliberately doesn't have, to stay simple and dependency-
free) there's no generic way to know the original word was already valid. The relative
floor from the previous round is still the real defense against the damage this
causes, not the corrector itself.

**Second finding, verifying the fix through the real path (not the console):**
testing it through the MCP server the way Claude Code actually uses it, the fix
wasn't applied — the live map server had the old code loaded in memory from before
`buscador.py` got patched. **If you change anything in `engine/`, you have to
restart that server** (`neuromapa abrir --reiniciar`) for it to take effect;
otherwise it keeps running the old code indefinitely, with no warning that it's
stale. After restarting it, the real path (MCP server → `sobre`) gives the same
result as the direct test: 1 note, not 3.

## What real benefit this has for a project

- **Less "we already decided this," repeated.** An architecture decision, a non-obvious
  business rule, a testing gotcha — they become a note tied to the code they touch. The
  next time anyone (or any of the 3 AIs) touches that code, the note surfaces on its
  own, before the question gets asked again or the same mistake repeats.
- **It doesn't depend on which AI you used that day.** If the decision got written down
  while working with Claude Code, and you open Codex the next day, the note still
  shows up — before `synapsis`, each tool had its own silo.
- **Stale memory cleans itself up.** If something got noted and never got used again,
  its weight decays; if a note goes stale or points at code that no longer exists, the
  health checker flags it for review instead of leaving it as silent truth.

## How it does it

Each tool has its own "hook" format (a lifecycle event: a session started, it's about to
use a tool, it finished, etc.) and its own config file. `synapsis` doesn't invent a new
protocol — it translates:

| Tool | Where it writes config | What it translates |
|---|---|---|
| **Claude Code** | `~/.claude/settings.json` | Nothing: it uses the engine's own `hook_*.py` scripts, the same event names. Replaces the marketplace plugin (disables it to avoid duplicate events). |
| **Codex** | `~/.codex/hooks.json` + `config.toml` | 12 lifecycle events (`SessionStart`, `PreToolUse`, `Stop`, etc.) into the shape the engine expects, plus an MCP server (standard protocol) with 7 tools. |
| **Antigravity** | `~/.gemini/config/hooks.json` | 5 events (`PreInvocation`, `PreToolUse`, `PostToolUse`, `PostInvocation`, `Stop`), also translating its own tool names (`run_command` → `Bash`, `view_file` → `Read`, etc.) into the ones the engine recognizes. |

The vendored engine (`engine/`) never knows which of the 3 called it — it just receives
events in the same shape, which is why they all end up in the same place:
`~/.claude/plugins/data/neuromapa-neuromapa/en-vivo/eventos.jsonl` (the log that feeds
the map) and `~/.claude/projects/*/memory/` (the actual notes, which were already
shared per project before `synapsis` existed — see "Myths" below).

## Install

```sh
python3 bin/synapsis install              # interactive selector: shows what can be installed before you choose
python3 bin/synapsis install claude        # Claude Code only
python3 bin/synapsis install codex         # Codex only
python3 bin/synapsis install antigravity   # Antigravity only
```

The selector runs the same check (`--dry-run`) it would use to install, so what you see
in the menu is real, not a guess:

```
¿Dónde instalo Synapsis?
  1) Claude Code  [OK]
  2) Codex        [OK]
  3) Antigravity  [OK]
  4) Todas las que digan OK
```

If something can't be installed (for example, an MCP server from a different config
already occupying the name "neuromapa" in Codex), the reason shows up right there,
before you pick.

Each installer adds the hooks without touching the ones you already have (it backs up
to `~/.claude/neuromapa-backups`, `~/.codex/neuromapa-backups`, or
`~/.gemini/config/neuromapa-backups` before writing, and it's safe to run again if you
install a new tool later). To only check without changing anything, add `--dry-run`.

### The live map as a service (Linux)

By default, the map (the 3D page) only runs while you have it open by hand with
`neuromapa abrir`. On Linux it can be left running on its own, without having to
remember to open it:

```sh
python3 linux/instalar_servicio_mapa.py              # turns it on and sets it to autostart
python3 linux/instalar_servicio_mapa.py --dry-run     # just shows what it would do
python3 linux/instalar_servicio_mapa.py --quitar      # uninstalls it
```

Uses `systemd --user`: starts every time you log in, and if the process dies, it
restarts on its own (`Restart=on-failure`). Actually tested: installed, confirmed
`active (running)` via `systemctl --user status`, killed with `kill -9` and it
recovered on its own within seconds with a new PID; uninstalled and confirmed nothing
was left running and the service file was gone.

To make it start even before logging in (not just at login): `loginctl enable-linger
<your user>`.

**Mac and Windows: not implemented.** They'd need `launchd` and Task Scheduler
respectively — couldn't test either (no access to those machines), so nothing's built
for them yet. Keep using `neuromapa abrir` by hand there.

### After installing

- **Claude Code**: restart the app. If you had the "neuromapa" plugin active, it got
  disabled — you lose `/neuromapa:abrir`, `/neuromapa:salud`, and `/neuromapa:sobre`
  (those are the plugin's); use the scripts in `engine/` directly if you need them.
- **Codex**: restart the app and trust the new hooks with `/hooks` in the CLI — Codex
  doesn't trust new hooks on its own.
- **Antigravity**: restart the app.

If you'd rather use a different copy of the engine, set `NEUROMAPA_ROOT` to that path
before installing; to force the data folder, `NEUROMAPA_DATA`. Both are resolved in
`comun.py`.

## Tests actually run (real numbers from this machine, not estimates)

Measured with `time` on this installation, on 2026-10-11:

| Operation | Real time |
|---|---|
| `install_claude_code.py --dry-run` (validates 17 hooks) | 0.040 s |
| `install_codex.py --dry-run` (validates 12 hooks + MCP) | 0.044 s |
| `install_antigravity.py --dry-run` (validates 5 hooks) | 0.040 s |
| One real Codex hook end-to-end (receives the event, translates it, writes to the log) | 0.119 s |

Functional verification (not just shape): each one was really installed in a separate
test folder, sent a real event with the exact payload each tool actually sends, and
confirmed it showed up in `eventos.jsonl` — for all 3. Since then it's also been
confirmed with all 3 real apps in normal use — see "Verified live" below.

## What each installer does

- **Claude Code** (`claude-code/`): writes the 17 hooks directly into
  `~/.claude/settings.json`, pointing at the `hook_*.py` scripts the engine already
  ships (the same ones the marketplace plugin uses, which is why nothing needs
  translating here).
- **Codex** (`codex/`): translates Codex's 12 lifecycle events into the engine's
  format, and adds the MCP server (`sobre`, `buscar`, `leer_nota`, `avisar_charla`,
  `guardar`, `abrir_mapa`, `salud`) for when the model decides to use them directly.
- **Antigravity** (`antigravity/`): translates its events (`PreInvocation`,
  `PreToolUse`, `PostToolUse`, `PostInvocation`, `Stop`) into the same format.

## The server now detects when it's stale

The live map saved a fingerprint of its code on startup, but never compared it again
when reopened — so if someone patched `engine/` without using `--reiniciar`, the map
kept answering with the old code, silently, forever. The comparison got added: now
`neuromapa abrir` checks whether the code on disk changed since that map started, and
if it did, it restarts itself (same as `--reiniciar`, without having to remember to
pass it). Actually tested: started a map, touched `buscador.py`, and reopening it
printed *"El código de Neuromapa cambió desde que este mapa se prendió: lo reinicio
para usar el nuevo"* and started clean. The official smoke test (753 cases) stayed at
750/753 after this change.

## Synapsis's own tests (not the engine's)

`tests/test_installers.py` (no dependencies, `python3 -m unittest discover -s tests`)
covers our own code: installing twice doesn't duplicate hooks, an old install under
the previous name ("Neuromapa") gets recognized and replaced instead of stacking,
disabling the marketplace plugin doesn't touch other hooks (e.g. Orca's), and
reinstalling Antigravity doesn't overwrite unrelated keys in `hooks.json`. 10/10 pass,
including one that encodes the real Codex duplication bug found and fixed today — if
it ever comes back, this test catches it before a user does.

## Myths worth clearing up

- **"If I never installed Claude Code, I have no memory."** False: the notes folder
  (`~/.claude/projects/.../memory/`) gets created by whoever writes to it first, no
  matter which of the 3 tools that is. What *is* uneven: the *habit* of saving memory on
  its own, without being asked, is an instruction from Claude Code's own product (its
  system prompt), not something the engine enforces — Codex and Antigravity only do it
  if their model decides to call `guardar` on its own.
- **"Memory is stored inside this repo."** No, and it shouldn't be: it lives in a folder
  per project (`~/.claude/projects/<your-project>/memory/`), so one project's memory
  doesn't mix with another's. This repo only holds the engine and the bridges.

## Maintaining the vendored engine

`engine/` is a fixed copy, not a link to the original: if a new version ships upstream,
it doesn't arrive on its own. Instead of copying files by hand (easy to overwrite a
patch without noticing), use `actualizar_motor.py`:

```sh
python3 actualizar_motor.py /path/to/a/fresh/clone/of/neuromapa            # just shows what would change
python3 actualizar_motor.py /path/to/a/fresh/clone/of/neuromapa --aplicar  # actually copies what's safe
```

It auto-copies what changed in files with no patch of ours; for the ones that do have
a patch (`buscador.py`, `servidor.py`) it never overwrites them on its own — it shows
the full diff between what's running here and the new version, so the patch can be
reapplied by hand on top of that. Tested with a real simulated change: it correctly
copied the one unpatched file and left the two patched ones untouched, showing exactly
the expected diff. After updating, run `bin/synapsis install` again on each machine.

**Watch out for 2 local patches**, which don't exist in the original project — if you
update `engine/` by copying in files from a newer version, they get lost and need to
be reapplied by hand:
- `engine/buscador.py`: `PUNTAJE_MINIMO_LEER`, `FRACCION_DEL_MEJOR`, and
  `LARGO_DISTANCIA_2` (the relevance floors and correction limit, see above).
- `engine/servidor.py`: the code-fingerprint comparison on reopen, so the map
  restarts itself if the code changed (see above).

## Verified live

Confirmed with all 3 real apps running (not simulated): using Codex and Antigravity
normally, their actions show up on the live map. One real detail to reproduce it: in
**Codex you have to go through the CLI** (the desktop app isn't enough) and **trust
the hooks by hand** with `/hooks` — otherwise Codex silently ignores them and it
looks like nothing works.

If something doesn't show up on the map, check that first (did you use the CLI? did
you trust the hooks?) before assuming something is broken.

## Real limitation

No bridge gives Codex or Antigravity the exact equivalent of Claude Code's automatic
`UserPromptSubmit` hook for always surfacing context: the bridge calls the engine, but
if that tool's model doesn't use the context the hook injects, there's no way to force
it from here.
