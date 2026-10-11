# Synapsis — una sola memoria para Claude Code, Codex y Antigravity

*[English version](README.en.md)*

Synapsis conecta Claude Code, Codex y Antigravity a la misma memoria viva: cada
herramienta queda con hooks reales de verdad (no solo una herramienta MCP que el modelo
puede decidir usar o no), apuntando al mismo motor y al mismo mapa 3D en vivo.

![El mapa en vivo](docs-img/mapa-en-vivo.gif)

## Qué hace

- **Un mapa de tus notas.** Junta la memoria de cada proyecto
  (`~/.claude/projects/*/memory/`) y la dibuja como un cerebro: cada nota es una
  neurona, y cada vez que una nota nombra a otra, una conexión.
- **En vivo.** Mientras trabajas (desde cualquiera de los 3), se ve qué nota se lee, qué
  archivo se edita, qué agente se lanzó y en qué chat — todo en la misma página, sin
  importar con cuál de las 3 herramientas lo generaste.
- **Un médico.** Revisa la memoria: enlaces a notas que ya no existen, notas que nadie
  nombra, memorias repetidas, encabezados incompletos.
- **Un buscador.** Dice qué notas leer primero para un tema, avisa los datos que pueden
  estar viejos, y junta las decisiones anotadas que lo tocan — antes de responder.
- **Aprende de tu uso.** Lo que se usa junto se conecta; lo que no se repite se olvida.
  Cada máquina aprende de su propio uso.

Lo que agrega `synapsis` sobre eso: que las tres herramientas (Claude Code, Codex,
Antigravity) alimenten y lean **el mismo** cerebro, con hooks reales en las 3 — no solo
en la que tiene el plugin oficial.

## Cómo lo hace

Cada herramienta tiene su propio formato de "hook" (evento de su ciclo de vida: empezó
una sesión, va a usar una herramienta, terminó, etc.) y su propio archivo de
configuración. `synapsis` no inventa un protocolo nuevo — traduce:

| Herramienta | Dónde escribe la config | Qué traduce |
|---|---|---|
| **Claude Code** | `~/.claude/settings.json` | Nada: usa los mismos `hook_*.py` del motor, los mismos nombres de evento. Reemplaza al plugin del marketplace (lo desactiva para no duplicar). |
| **Codex** | `~/.codex/hooks.json` + `config.toml` | 12 eventos (`SessionStart`, `PreToolUse`, `Stop`, etc.) a la forma que el motor espera, más un servidor MCP (protocolo estándar) con 7 herramientas. |
| **Antigravity** | `~/.gemini/config/hooks.json` | 5 eventos (`PreInvocation`, `PreToolUse`, `PostToolUse`, `PostInvocation`, `Stop`), traduciendo también los nombres de sus herramientas propias (`run_command` → `Bash`, `view_file` → `Read`, etc.) a los que el motor reconoce. |

El motor vendorizado (`engine/`) nunca se entera de cuál de las 3 lo llamó — solo recibe
eventos con la misma forma, y por eso todos terminan en el mismo lugar:
`~/.claude/plugins/data/neuromapa-neuromapa/en-vivo/eventos.jsonl` (el registro que
alimenta el mapa) y `~/.claude/projects/*/memory/` (las notas reales, que ya eran
compartidas por proyecto antes de que existiera `synapsis` — ver "Mitos" más abajo).

## Instalar

```sh
python3 bin/synapsis install              # selector interactivo: muestra qué se puede instalar antes de elegir
python3 bin/synapsis install claude        # solo Claude Code
python3 bin/synapsis install codex         # solo Codex
python3 bin/synapsis install antigravity   # solo Antigravity
```

El selector corre el mismo chequeo (`--dry-run`) que usaría para instalar, así que lo
que ves en el menú es real, no una suposición:

```
¿Dónde instalo Synapsis?
  1) Claude Code  [OK]
  2) Codex        [OK]
  3) Antigravity  [OK]
  4) Todas las que digan OK
```

Si algo no se puede instalar (por ejemplo, un servidor MCP de otra configuración ya
ocupando el nombre "neuromapa" en Codex), el motivo aparece ahí mismo, antes de elegir.

Cada instalador agrega los hooks sin tocar los que ya tengas (hace una copia de
seguridad en `~/.claude/neuromapa-backups`, `~/.codex/neuromapa-backups` o
`~/.gemini/config/neuromapa-backups` antes de escribir, y es seguro de correr de nuevo
si instalás una herramienta nueva más adelante). Para solo revisar sin cambiar nada,
agregá `--dry-run`.

### Después de instalar

- **Claude Code**: reiniciá la app. Si tenías el plugin "neuromapa" activo, quedó
  desactivado — perdés `/neuromapa:abrir`, `/neuromapa:salud` y `/neuromapa:sobre` (son
  del plugin); usá los scripts de `engine/` directo si los necesitás.
- **Codex**: reiniciá la app y confiá los hooks nuevos con `/hooks` en la CLI — Codex no
  confía en hooks nuevos solo.
- **Antigravity**: reiniciá la app.

Si preferís usar otra copia del motor, fijá `NEUROMAPA_ROOT` con esa ruta antes de
instalar; para forzar la carpeta de datos, `NEUROMAPA_DATA`. Ambas se resuelven en
`comun.py`.

## Pruebas que corrí (números reales de esta máquina, no estimados)

Medido con `time` sobre esta instalación, el 2026-10-11:

| Operación | Tiempo real |
|---|---|
| `install_claude_code.py --dry-run` (valida 17 hooks) | 0.040 s |
| `install_codex.py --dry-run` (valida 12 hooks + MCP) | 0.044 s |
| `install_antigravity.py --dry-run` (valida 5 hooks) | 0.040 s |
| Un hook real de Codex de punta a punta (recibe el evento, lo traduce, escribe en el registro) | 0.119 s |

Verificación funcional (no solo de forma): instalé de verdad cada una en una carpeta de
prueba aparte, le mandé un evento real con el payload exacto que cada herramienta envía,
y confirmé que apareció en `eventos.jsonl` — para las 3. El detalle completo de qué se
probó y qué falta probar en vivo (dentro de la app real, no simulado) está en
"Qué falta verificar" más abajo.

## Qué hace cada instalador

- **Claude Code** (`claude-code/`): escribe los 17 hooks directo en
  `~/.claude/settings.json`, apuntando a los `hook_*.py` que ya trae el motor (son los
  mismos que usa el plugin del marketplace, por eso no hace falta traducir nada acá).
- **Codex** (`codex/`): traduce los 12 eventos del ciclo de vida de Codex al formato del
  motor, y agrega el servidor MCP (`sobre`, `buscar`, `leer_nota`, `avisar_charla`,
  `guardar`, `abrir_mapa`, `salud`) para cuando el modelo decide usarlos directamente.
- **Antigravity** (`antigravity/`): traduce sus eventos (`PreInvocation`, `PreToolUse`,
  `PostToolUse`, `PostInvocation`, `Stop`) al mismo formato.

## Mitos que vale la pena aclarar

- **"Si nunca instalé Claude Code, no tengo memoria."** Falso: la carpeta de notas
  (`~/.claude/projects/.../memory/`) la crea quien sea que escriba primero, sin importar
  cuál de las 3 herramientas sea. Lo que sí es desigual: el *hábito* de guardar memoria
  sola, sin que se lo pidan, es una instrucción del propio producto Claude Code (su
  "system prompt"), no algo que el motor imponga — Codex y Antigravity solo lo hacen si
  el modelo decide llamar a `guardar` por su cuenta.
- **"La memoria se guarda dentro de este repo."** No, y no debería: vive en una carpeta
  por proyecto (`~/.claude/projects/<tu-proyecto>/memory/`), para que no se mezcle la de
  un proyecto con la de otro. Este repo solo tiene el motor y los puentes.

## Mantenimiento del motor vendorizado

`engine/` es una copia fija, no un enlace al original: si sale una versión nueva, no
llega sola. Para actualizarla: clonar de nuevo el proyecto de origen (ver
`engine/LICENSE` para la atribución), copiar los `.py` sobre `engine/` (sin pisar nada
propio de `synapsis/`, que vive afuera de esa carpeta), y volver a correr
`bin/synapsis install` en cada máquina.

## Qué falta verificar

El bridge de Codex pasó pruebas de lógica para los 12 eventos, pero solo 2
(`SessionStart`, `Interrupt`) se confirmaron con eventos reales de la app real en algún
momento (no simulados a mano, como hice yo en las pruebas de arriba). El de Antigravity
y el de Claude Code (escribir directo en `settings.json` en vez de usar el plugin)
tampoco se probaron con la app real corriendo — solo con payloads simulados a mano,
idénticos en forma a los reales. Si algo no anota en el mapa, revisá primero si el hook
corrió antes de asumir que algo está roto.

## Límite real

Ningún bridge le da a Codex o Antigravity el equivalente exacto del hook
`UserPromptSubmit` automático que tiene Claude Code para avisar contexto siempre: el
bridge llama al motor, pero si el modelo de esa herramienta no usa el contexto que le
inyecta el hook, no hay manera de forzarlo desde acá.
