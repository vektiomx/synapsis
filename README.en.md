# Synopsis

Local, shared memory for AI assistants. Synopsis retrieves project-scoped evidence,
keeps corrections and provenance, and exposes JSON context packets through MCP and CLI.

[Español](README.md) · [Architecture](docs/architecture.md)

## macOS and Windows adaptation (0.11 · development)

Source installers: `install-macos.command` and `install-windows.cmd`, requiring
Python 3.11+. Per-user map autostart, Windows commands without Git Bash, and platform
capability diagnostics. Linux, macOS and Windows CI passed; signed bundled runtimes
remain pending. Isolated experiments still require Linux/bubblewrap.
[Installation, scope and validation](docs/desktop_adaptation.md).

## Verifiable behavioral memory (0.10)

Preserve observed input/output cases after their original test disappears. The
research workbench checks candidates against those cases and current tests, with
signature, scope, retirement and changed-contract boundaries. Prompts and edits
receive provenance hints. Witness capture requires no LLM inference.
[Workflow and diagram](docs/behavior_memory.md) · [Reproducible comparison](docs/competitive_evaluation.md).

## Living memory and research (0.9)

Unified context, explicit validity, and bounded Python function experiments compared
with the original in isolated snapshots. The panel shows evidence and test outcomes.
[Workflow, commands and limits](docs/research_workbench.md).

## Hybrid retrieval and experience lab (0.8)

Installation prepares local multilingual embeddings. Retrieval fuses BM25, technical
anchors and real vectors, then validates current conditions and contrasting cases.
The optional Linux lab challenges an existing named test in disposable snapshots.
[Evaluación 0.8](docs/upgrade_evaluation.md) · [Decision flow](docs/decision_rag.md) · [Runtime and limits](docs/local_semantics.md).

## Install: Linux, macOS and Windows

Requires Python 3.11+ and an installed supported client. Git is used to download
this repository; downloading and extracting its ZIP also works. The core needs no
external Python packages, API keys or administrator permissions. Optional semantic
search downloads dependencies and a model during initial installation and needs
Internet access. Use `--no-semantic` to skip it.

This source installation runs from the downloaded directory: keep it in a stable
location. Python and signed macOS/Windows packages are not bundled.

### Linux

```bash
git clone https://github.com/vektiomx/synapsis.git synopsis
cd synopsis
python3 bin/synopsis install
```

### macOS

Install Python 3.11+ first. In Terminal:

```bash
git clone https://github.com/vektiomx/synapsis.git synopsis
cd synopsis
sh install-macos.command
```

The map uses a per-user LaunchAgent to start at login.

### Windows

Install Python 3.11+ with the `py` launcher or Python available on PATH.
In PowerShell:

```powershell
git clone https://github.com/vektiomx/synapsis.git synopsis
cd synopsis
.\install-windows.cmd
```

In CMD, run `install-windows.cmd` from the same folder. No Git Bash or PowerShell
execution-policy change is needed. The command is installed under
`%LOCALAPPDATA%\Synopsis\bin`; the map starts at login for your user.

### Options and first use

The installer detects available clients and connects hooks, MCP and shared memory.
It preserves unrelated settings and backs up modified files. Linux uses a systemd
user service when available; otherwise open the map manually with `synopsis abrir`.
The isolated experiment lab requires Linux and bubblewrap; memory, MCP and the map
have adapters for all three systems.

In the examples below, on Windows replace `python3 bin/synopsis` with
`py -3 bin/synopsis` (or `python bin/synopsis` without the `py` launcher).

```bash
python3 bin/synopsis install codex --dry-run
python3 bin/synopsis install --all
python3 bin/synopsis install codex --no-service --no-color
```

`--dry-run` writes nothing. The default installation also works noninteractively.
Restart your assistant and open a new shell after installation. Some Codex clients
require trusting lifecycle hooks via `/hooks`.

```bash
synopsis                 # open the authenticated map
synopsis --help
```

`synopsis doctor` (or `doctor --json`) distinguishes transport readiness, installed
configuration and actual IDE activity. A successful probe never fabricates a chat or
claims the host has trusted its hooks. Initial host consent may still be required.

## Store and retrieve memory

```bash
printf '%s\n' 'Redis cache entries expire after 120 seconds.' | \
  synopsis memory save --project /absolute/project --file cache-policy \
  --description 'Redis cache duration' --source 'user:decision' \
  --state confirmed --cue 'cache ttl retention'

synopsis recall 'cache ttl retention' --project /absolute/project --budget 3000
synopsis memory history --project /absolute/project --file cache-policy
```

Markdown remains editable; writes through the API use a project lock, SQLite revision
ledger and recoverable outbox for the note/index pair. Identical retries are idempotent.
Corrections use `--overwrite --expected-revision N` to reject stale writers. Explicit
replacement preserves an existing external file as a historical revision.

States: `inferred` (default), `confirmed`, `archived`. Optional `--expires-at` accepts
an ISO 8601 timestamp with timezone. Expired and archived notes are excluded from
recommendations, not deleted from history. States and provenance are client assertions,
not automatic fact checking. `--cue` supplies retrieval vocabulary, including bilingual
questions, separately from factual content; optional real embeddings add semantic retrieval when available (see [models](docs/models.md)).

Context packets contain file/line citations, hashes, provenance and retrieval reasons.
Their complete serialized JSON is bounded in characters, not estimated tokens. Retrieval
abstains when evidence is missing and rechecks cited passages and lifecycle on disk.
Explicit outcome feedback (`useful`, `irrelevant`, `incorrect`) produces a bounded ranking
adjustment tied to exact file revisions. It evaluates the entire packet, not each excerpt.
It cannot create lexical evidence. Feedback stores hashes and references, not prompts or
passages. Evaluations older than 90 days are ignored and purged when a new packet is registered.

```bash
synopsis feedback PACKET_ID --project /absolute/project --outcome useful --source user:review
```

## Any compatible model client

Launch `python3 /absolute/synopsis/bin/synopsis mcp` as an MCP stdio server. Use
`recordar`, `guardar`, `historial_memoria`, and `evaluar_recuerdo`. Tools expose Spanish
names and structured context output. Clients without MCP can use the CLI JSON interface.
Your client must feed retrieved context into its model; Synopsis does not change weights
or guarantee that every client will honor lifecycle hooks.

State defaults to `~/.local/share/synopsis`; notes remain in the shared
`~/.claude/projects/<encoded-project-path>/memory/` layout, usable without Claude installed.
Override with `SYNOPSIS_ROOT` and `SYNOPSIS_DATA`.

`migrate-data /previous/data` previews a copy of persistent configuration/history to an
empty destination; add `--apply` to execute it. Originals are retained. Live sessions,
map keys and caches are excluded. Existing services and integrations are not disabled;
retire those before activating the replacement installation.

## Validation

```bash
python3 -B -m unittest discover -s tests
python3 -B tools/evaluate_memory.py
python3 -B engine/herramientas/prueba_humo.py
```

The versioned synthetic retrieval suite reports recall@5, MRR, abstention and cross-project
leaks. It does not measure model intelligence or establish LoCoMo performance. The full
engine suite needs localhost sockets and a browser; PowerShell checks need Windows.

Inherited code retains its [MIT license](LICENSE).

## Native OpenCode and Cursor integration

Run `synopsis install opencode` or `synopsis install cursor`, or let the default
installer detect all available clients. OpenCode loads a local plugin that registers
MCP through its configuration hook without rewriting existing JSONC. It uses the
experimental system-context hook. Cursor installs global hooks, MCP and a skill;
context is supported at session start and after tool use. Its documented prompt
submission hook does not support context injection, so the initial guidance asks the
agent to query memory for each task. No cloud or remote-machine configuration is installed.

## Durable task continuity

The shared runtime opens memory turns, retrieves project-scoped evidence and keeps
queued operations across interruptions. Closing a turn requires verified writes or
an explicit no_change reason. Working checkpoints live outside durable knowledge
notes and use optimistic concurrency. `synopsis cycle status --project /path/project`
shows pending work. `synopsis run` provides an additional command-adapter JSON protocol
that withholds the answer until memory reconciliation succeeds. Native IDE hooks
remain cooperative. Scripted adapter tests demonstrate mechanisms, not model quality.
See [protocol and limitations](docs/continuity.md).

## Project identity and existing memories

New memories use a full canonical-root identity under SYNOPSIS_DATA/projects.
Explicitly assigned existing memories are adopted in place, preserving notes and
revision history. Ambiguous unowned legacy folders are never assigned by their lossy
IDE directory name. Inspect them with `synopsis memory-location --project /path`,
then bind the known owner using `--bind /existing/memory --apply`. Working checkpoints
now follow commit order independently of task creation order and wall-clock changes.

## Ready model connectors and hybrid retrieval

`synopsis run --project /absolute/project --prompt 'Remember the retention is 300 seconds'`
now works without a custom adapter. It detects local Ollama and native authenticated
Codex, Claude and OpenCode clients. Use `--provider` and `--model` to select a backend.
OpenAI Responses and compatible chat endpoints are supported through environment
variables. `synopsis providers` reports availability without making inference calls.
Accounts and model access are still required; no API keys are bundled.

Hybrid retrieval fuses lexical evidence and optional real embeddings, cached by
provider/model/content inside each project's state. Only scoped, active notes enter
the embedding provider; remote embedding endpoints require explicit configuration.
Backend failures preserve lexical retrieval. Query vectors are not persisted.

`synopsis reconcile --project /absolute/project --output /tmp/review.json` produces
a semantic review plan. Inspect it, then apply with `--apply /tmp/review.json`.
Changed versions and unresolved contradictions block destructive reconciliation.
`synopsis learn` stores outcome-bearing experiences with local evidence hashes;
these remain inferred observations, not verified universal truths.

See [models, privacy and protocols](docs/models.md). Build a distributable archive
with `python3 tools/build_release.py --output /tmp/synopsis.zip`.

## Strict evidence output (0.3)

`synopsis run` now uses synopsis.run.v2. The model selects source IDs and proposes
literal memory support; the controller builds the factual answer from checked
excerpts, exact JSON observations or bounded decimal arithmetic. Unsupported drafts
are never published as the answer. Missing support produces abstention.

Memory without a durable controller admission is quarantined for strict output,
even when another client labelled it confirmed. Existing notes/history remain in
place. Updates require complete source passages and the current revision.

This checks source fidelity, not universal truth or perfect relevance. Strict mode
trades unrestricted prose for enforceable evidence binding. IDE hooks remain
cooperative; native MCP clients can use responder_con_evidencia and CLI verify.
See [the evidence guard contract and limitations](docs/evidence_guard.md).

## Automatic project binding (0.4 development branch)

The first native hook or memory operation registers the workspace. Existing memories
are reused in place when client metadata proves ownership. Ambiguous migrations are
resolved through the authenticated map panel, without editing configuration files.
Workspace markers preserve local identity across recognized moves; copies and
worktrees retain independent memory. Worktrees have a shared group identifier, not
a shared branch knowledge store. See [the detailed contract](docs/project_binding.md).

## Independent automatic review (0.5)

Native end-of-turn hooks now queue a bounded private turn for background review.
The reviewer uses the same client's CLI or a local Ollama generation model. It admits
source-bound user/file passages, preserves revisions, and checks persistence receipts.
Unsupported assertions and uncertain replacements remain conflicts; unavailable
providers leave work pending. Temporary input expires on the next queue access after
24 hours and is deleted after processing. No full transcripts or tool outputs are
captured. Run `synopsis reviews --project /path/project` to inspect results.
See [the complete lifecycle and limits](docs/continuity.md).


## Scoped development experiences (0.6)

Experiences now retain situation, action, rationale, reported outcome, applicability,
evidence, limits and counterexamples. Native review may capture them automatically;
hooks and the experiencias MCP tool retrieve them by task/path. Checks support only
the declared observation, never the whole inferred narrative. Source drift becomes
stale. Python unittest replay is optional and requires functional Linux isolation.
Pending review recovery and a map status panel are included. See [the contract](docs/experiences.md).

### Decision RAG (0.7)

Synopsis can retrieve contrasting experiences for the same problem, check their
current requirements, and identify the observation needed to distinguish choices.
Use `synopsis experience decide` or the existing `experiencias` MCP tool's `decide`
operation. Hooks include it automatically where the client supports the event.
[Protocol, flow and limitations](docs/decision_rag.md).
