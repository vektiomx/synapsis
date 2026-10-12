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

## Cómo busca y aprende el motor, en corto

No es indexación semántica ni usa embeddings: es búsqueda léxica por palabras (estilo
BM25, con corrección de errores de tipeo), combinada con un grafo de qué notas y
archivos se usan juntos. Ese grafo se poda de verdad — las conexiones débiles se
olvidan solas con el tiempo, no quedan acumuladas para siempre.

**Lo que aprendió solo**, sin que nadie le dijera qué archivos iban juntos (salida real
de `cerebro.py --aprendido`, sacada después de la sesión donde agregamos una categoría
nueva al catálogo de servicios — los archivos que tocamos juntos son justo los que
conectó):

![Peso aprendido de coocurrencia entre archivos](docs-img/coocurrencia-aprendida.svg)

**Qué tan bien funciona en la práctica, sin maquillar el número:** de las notas que
recomendó, esto es cuántas veces se terminaron leyendo después (de cada 10 veces que
las recomendó):

![Efectividad de las recomendaciones](docs-img/efectividad-pistas.svg)

Esto es honesto a propósito: unas notas se usan después casi siempre, otras casi nunca.
No es una cifra de marketing — es la métrica real que el propio motor guarda
(`aprendido.json`) para calibrarse.

**Por qué pasaba eso, y el arreglo real.** Investigando el 0 de 10 encontramos la
causa exacta: el motor siempre intentaba rellenar un cupo fijo de 4 notas por
respuesta, aunque ninguna fuera realmente relevante — y el corrector de errores de
tipeo a veces "corrige" una palabra a otra palabra real pero sin relación (ambas
válidas, a 1-2 letras de distancia). Resultado medido en esta misma sesión, con la
misma pregunta, antes y después de agregar un puntaje mínimo para entrar al cupo:

| | Antes | Después |
|---|---|---|
| Avisos para una pregunta sin relación con ninguna nota | 3 (2 eran ruido puro) | 1 |
| Una pregunta genuinamente relacionada | 3 notas correctas | 3 notas correctas (sin cambio) |

Se corrió además la prueba de humo oficial del motor (753 casos): 750 pasaron, 3 son
específicos de Windows/PowerShell y no aplican en esta máquina — ninguna falla real.

**Segunda vuelta: el piso fijo no alcanzaba.** Probando con más preguntas reales
encontramos un caso que el piso de 1.0 no atrapaba: preguntar por nómina también traía
"Landing design direction" (puntaje 2.1, por encima del piso, pero solo el 18% del
puntaje de la nota que sí correspondía, 11.38). Se agregó una segunda regla: además del
piso fijo, descartar lo que no llegue al 30 % del mejor puntaje de esa consulta.

| Pregunta real | Antes (solo piso fijo) | Después (+ piso relativo) |
|---|---|---|
| "cómo va la nómina de esta semana" | Nómina + Branch switcher | Solo Nómina |
| "landing en remotion" | Landing + Nómina | Solo Landing |

Confirmado otra vez contra la prueba de humo oficial (750/753, sin cambios) y la propia
de `synapsis` (10/10).

**Tercera vuelta: el corrector de errores seguía inventando relaciones.** El caso
"readme"→"read" (seis letras, dos de distancia) pasaba porque el corrector permitía
corregir a 2 letras de distancia para cualquier palabra, sin importar qué tan corta
fuera. Se restringió: a 2 letras de distancia solo se corrigen palabras de 8+ letras;
las más cortas, solo a 1 letra. Confirmado: "readme" ya no se "corrige" a "read".

**Lo que queda, honesto:** "nuevo"→"nueve" y "trae"→"true" siguen pasando — son dos
palabras reales del idioma a 1 letra de distancia, la distancia mínima que existe. Sin
un diccionario completo (que no tiene este proyecto, a propósito, para seguir siendo
simple y sin dependencias pesadas) no hay forma genérica de saber que la palabra
original ya era válida. El piso relativo de la vuelta anterior sigue siendo la defensa
real contra el daño que esto causa, no el corrector en sí.

**Segundo hallazgo, verificando el arreglo por el camino real (no la consola):**
probando desde el servidor MCP tal como lo usa Claude Code de verdad, el arreglo no
se aplicaba — el servidor del mapa en vivo tenía el código viejo cargado en memoria
desde antes de parchar `buscador.py`. **Si cambias algo en `engine/`, hay que
reiniciar ese servidor** (`neuromapa abrir --reiniciar`) para que lo tome; si no,
sigue corriendo el código anterior indefinidamente, sin avisar que está desactualizado.
Después de reiniciarlo, el camino real (servidor MCP → `sobre`) da el mismo resultado
que la prueba directa: 1 nota, no 3.

## Qué beneficio real tiene esto para un proyecto

- **Menos "esto ya lo decidimos" repetido.** Una decisión de arquitectura, una regla de
  negocio no obvia, un gotcha de testing — quedan como nota ligada al código que tocan.
  La próxima vez que alguien (o cualquiera de las 3 IAs) toque ese código, la nota
  aparece sola, antes de que se vuelva a preguntar o se repita el mismo error.
- **No depende de qué IA usaste ese día.** Si la decisión quedó en una nota mientras
  trabajabas con Claude Code, y al día siguiente abres Codex, la nota sigue
  apareciendo — hoy, sin `synapsis`, eso no pasaba: cada herramienta tenía su propio
  silo.
- **El historial de mala memoria se auto-limpia.** Si algo se anotó y nunca se volvió
  a usar, su peso decae; si una nota queda vieja o apunta a código que ya no existe, el
  "médico" lo marca para revisión en vez de dejarlo como verdad silenciosa.

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
y confirmé que apareció en `eventos.jsonl` — para las 3. Desde entonces se confirmó
también con las 3 apps reales en uso normal — ver "Verificado en vivo" más abajo.

## Qué hace cada instalador

- **Claude Code** (`claude-code/`): escribe los 17 hooks directo en
  `~/.claude/settings.json`, apuntando a los `hook_*.py` que ya trae el motor (son los
  mismos que usa el plugin del marketplace, por eso no hace falta traducir nada acá).
- **Codex** (`codex/`): traduce los 12 eventos del ciclo de vida de Codex al formato del
  motor, y agrega el servidor MCP (`sobre`, `buscar`, `leer_nota`, `avisar_charla`,
  `guardar`, `abrir_mapa`, `salud`) para cuando el modelo decide usarlos directamente.
- **Antigravity** (`antigravity/`): traduce sus eventos (`PreInvocation`, `PreToolUse`,
  `PostToolUse`, `PostInvocation`, `Stop`) al mismo formato.

## El servidor ahora se autodetecta desactualizado

El mapa en vivo guardaba una huella del código al prender, pero nunca la volvía a
comparar al abrirlo de nuevo — así que si alguien parchaba `engine/` sin usar
`--reiniciar`, el mapa seguía respondiendo con el código viejo, en silencio, para
siempre. Se agregó la comparación: ahora `neuromapa abrir` revisa si el código en disco
cambió desde que ese mapa prendió, y si cambió, se reinicia solo (igual que
`--reiniciar`, sin tener que acordarse de pasarlo). Probado de verdad: se prendió un
mapa, se tocó `buscador.py`, y al volver a abrir avisó *"El código de Neuromapa cambió
desde que este mapa se prendió: lo reinicio para usar el nuevo"* y arrancó limpio. La
prueba de humo oficial (753 casos) sigue en 750/753 después de este cambio.

## Pruebas propias de synapsis (no del motor)

`tests/test_installers.py` (sin dependencias, `python3 -m unittest discover -s tests`)
cubre lo nuestro: que instalar dos veces no duplique hooks, que una instalación vieja
con el nombre anterior ("Neuromapa") se reconozca y reemplace en vez de sumarse, que
desactivar el plugin del marketplace no toque hooks de otros (ej. Orca), y que
reinstalar Antigravity no pise claves ajenas en `hooks.json`. 10/10 pasan, incluida una
que codifica el bug real de duplicación de Codex que encontramos y arreglamos hoy — si
vuelve a pasar, esta prueba lo atrapa antes que un usuario.

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

**Ojo con 2 parches locales**, que no existen en el proyecto original — si actualizan
`engine/` copiando archivos de una versión nueva, se pierden y hay que reaplicarlos a
mano:
- `engine/buscador.py`: `PUNTAJE_MINIMO_LEER`, `FRACCION_DEL_MEJOR` y `LARGO_DISTANCIA_2`
  (los tres pisos/límites de relevancia y corrección, ver más arriba).
- `engine/servidor.py`: la comparación de huella de código al reabrir el mapa, para
  que se reinicie solo si el código cambió (ver más arriba).

## Verificado en vivo

Confirmado con las 3 apps reales corriendo (no simulado): usando Codex y Antigravity
normalmente, sus acciones aparecen en el mapa en vivo. Un detalle real para
reproducirlo: en **Codex hay que entrar por la CLI** (no alcanza con la app de
escritorio) y **confiar los hooks a mano** con `/hooks` — si no, Codex los ignora en
silencio y parece que no funciona.

Si algo no anota en el mapa, revisá primero eso (¿entraste por la CLI? ¿confiaste los
hooks?) antes de asumir que algo está roto.

## Límite real

Ningún bridge le da a Codex o Antigravity el equivalente exacto del hook
`UserPromptSubmit` automático que tiene Claude Code para avisar contexto siempre: el
bridge llama al motor, pero si el modelo de esa herramienta no usa el contexto que le
inyecta el hook, no hay manera de forzarlo desde acá.
