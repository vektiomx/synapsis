# Synopsis

Memoria local y compartida para asistentes de IA. Recupera conocimiento por proyecto,
conserva correcciones y devuelve contexto con evidencia verificable. Funciona con
Claude Code, Codex, Antigravity, OpenCode y Cursor; otros clientes pueden conectarse por MCP o CLI JSON.

[English](README.en.md) · [Arquitectura y límites](docs/architecture.md) · [Estado del trabajo](docs/development.md) · [Continuidad](docs/continuity.md) · [Salida con evidencia](docs/evidence_guard.md)

## Adaptación macOS y Windows (0.11 · desarrollo)

Instaladores desde fuentes: `install-macos.command` e `install-windows.cmd`, con
Python 3.11 o superior. Arranque del mapa por usuario, comando Windows sin Git Bash
y diagnóstico de capacidades. CI aprobada en Linux, macOS y Windows; los paquetes
con runtime firmado siguen pendientes. El laboratorio aislado requiere Linux/bwrap.
[Instalación, alcance y validación](docs/desktop_adaptation.md).

## Memoria de comportamiento verificable (0.10)

Conserva casos de entrada/salida observados aunque desaparezca el test original.
El banco compara candidatos contra esos casos y los tests actuales; respeta firmas,
guardas, retiros y contratos cambiados. Los prompts y las ediciones reciben pistas
con procedencia. Capturar los testigos no requiere inferencia.
[Funcionamiento y diagrama](docs/behavior_memory.md) · [Comparación reproducible](docs/competitive_evaluation.md).

## Memoria viva e investigación (0.9)

Contexto unificado, vigencia explícita y prototipos de funciones Python comparados
contra el original en copias aisladas. El panel muestra evidencia, retiros y resultados.
[Flujo, comandos, vista y resultados](docs/research_workbench.md).

## Recuperación y laboratorio de experiencias (0.8)

La instalación prepara semántica multilingüe local. La recuperación combina BM25,
anclajes técnicos y vectores reales, comprueba condiciones actuales y conserva
alternativas con límites. El laboratorio puede desafiar una prueba existente en
copias aisladas para mostrar si distingue los contextos declarados.
[Evaluación 0.8](docs/upgrade_evaluation.md) · [Flujo de decisiones](docs/decision_rag.md) · [Semántica y requisitos](docs/local_semantics.md).

## Experiencias de desarrollo (0.6)

Synopsis conserva situación, acción, motivo, resultado, evidencia y límites de una
experiencia. La recupera por tarea y archivo, comprueba condiciones y marca el
respaldo desactualizado cuando cambian sus fuentes. Las interpretaciones siguen
siendo inferencias; un check aprobado no certifica todo el relato.

Incluye captura por el revisor independiente, versiones, MCP, un panel de estado y
reproducción aislada opcional de pruebas Python en Linux. [Funcionamiento, ejemplo
y límites](docs/experiences.md).

## Guardado automático al terminar cada turno

Desde 0.5 un revisor en segundo plano selecciona información durable sin depender
exclusivamente de que el modelo principal invoque herramientas de memoria. Comprueba
las citas, evita duplicados literales, conserva versiones y verifica el recibo.
Reutiliza el CLI del mismo cliente o un Ollama local disponible. Sin proveedor
accesible deja el trabajo pendiente; las contradicciones requieren conciliación.

Consulta `synopsis reviews --project /ruta/proyecto` para ver resultados. La entrada
del turno se conserva temporalmente en privado; no se archivan herramientas ni
conversaciones completas. [Flujo, privacidad y límites](docs/continuity.md#revisión-automática-independiente-050).

## Proyectos vinculados automáticamente

Desde 0.4, el primer uso registra el proyecto y reutiliza su memoria entre clientes.
Reconoce raíces de Git, worktrees, espacios del IDE y subcarpetas ya conocidas.
Conserva la memoria al reconocer una ubicación movida; una copia conserva su
independencia. Las memorias anteriores se reutilizan con evidencia de propiedad,
sin copiar notas. Si la asociación es ambigua, el mapa ofrece una elección una vez.

Los índices muestran el nombre del proyecto. Consulta [vinculación, migración y
límites de detección](docs/project_binding.md). Los worktrees mantienen memorias
separadas: no se mezclan automáticamente decisiones de ramas distintas.

## Salida estricta con respaldo

En la versión 0.3, `synopsis run` publica extractos comprobados y recibos del
controlador; el borrador libre del modelo queda fuera de la respuesta factual.
Sin respaldo se abstiene. Las memorias sin admisión durable quedan en cuarentena
para ese modo, aunque otro cliente las haya marcado como confirmadas. Se conservan
sus archivos e historial.

Esto verifica fidelidad a fuentes y persistencia, no verdad universal ni relevancia
perfecta. El modo estricto sacrifica prosa libre; los hooks del IDE siguen siendo
cooperativos. Consulta [el contrato v2, garantías y límites](docs/evidence_guard.md).

## Instalación: Linux, macOS y Windows

Requiere Python 3.11 o superior y al menos un cliente compatible instalado. Git se
usa para descargar el repositorio; también puedes descargar y extraer su ZIP.
El núcleo no requiere paquetes Python externos, claves API ni permisos de administrador.
La búsqueda semántica opcional descarga sus dependencias y modelo en la primera
instalación: necesita conexión a Internet. Puedes omitirla con `--no-semantic`.

Esta instalación ejecuta el código desde la carpeta descargada: consérvala en una
ubicación estable. No incluye Python ni un paquete firmado para macOS o Windows.

### Linux

```bash
git clone https://github.com/vektiomx/synapsis.git synopsis
cd synopsis
python3 bin/synopsis install
```

### macOS

Instala Python 3.11+ antes de comenzar. En Terminal:

```bash
git clone https://github.com/vektiomx/synapsis.git synopsis
cd synopsis
sh install-macos.command
```

El mapa se registra como LaunchAgent del usuario y arranca al iniciar sesión.

### Windows

Instala Python 3.11+ con el lanzador `py` o con Python disponible en el PATH.
En PowerShell:

```powershell
git clone https://github.com/vektiomx/synapsis.git synopsis
cd synopsis
.\install-windows.cmd
```

Desde CMD puedes ejecutar `install-windows.cmd` en esa misma carpeta. No requiere
Git Bash ni cambiar la política de ejecución de PowerShell. Instala el comando en
`%LOCALAPPDATA%\Synopsis\bin` y registra el mapa al iniciar sesión para tu usuario.

### Opciones y primer uso

Los tres instaladores detectan los clientes disponibles y conectan hooks, MCP y
memoria compartida. Conservan los ajustes de otras herramientas y respaldan los
archivos que modifican. En Linux con systemd configuran el servicio del usuario;
sin systemd puedes abrir el mapa manualmente con `synopsis abrir`.
El laboratorio de experimentos aislados requiere Linux y bubblewrap; la memoria,
MCP y el mapa tienen adaptadores para los tres sistemas.

En los ejemplos siguientes, en Windows sustituye `python3 bin/synopsis` por
`py -3 bin/synopsis` (o `python bin/synopsis` si no tienes `py`).

Si prefieres seleccionar manualmente, usa `--interactive` (números separados por
coma, `a` para todos, `q` para salir).

```bash
python3 bin/synopsis install codex --dry-run  # ver los cambios antes de aplicar
python3 bin/synopsis install                 # automático, sin preguntas
python3 bin/synopsis install --interactive   # selección manual opcional
python3 bin/synopsis install codex --no-service
python3 bin/synopsis install codex --no-color --verbose
```

Reinicia el asistente después de instalar. Codex puede requerir confiar los hooks
con `/hooks`, según el cliente. Abre una terminal nueva para cargar el PATH y ejecuta:

```bash
synopsis                    # abre el mapa autenticado
synopsis abrir
synopsis --help
```

`--dry-run` no instala nada. La salida no interactiva evita códigos de color; también
respeta `NO_COLOR`. La instalación predeterminada funciona también desde scripts y sin terminal interactiva.

## Comprobar la conexión

```bash
synopsis doctor
synopsis doctor --json
```

El diagnóstico distingue transporte MCP, adaptadores, configuración instalada y
eventos recibidos de cada cliente. Una prueba local correcta no significa que el IDE
ya haya cargado o autorizado sus hooks. No genera conversaciones ficticias para
simular actividad. Volver a ejecutar el instalador es seguro e idempotente.

## Integraciones nativas

| Cliente | Integración local |
|---|---|
| Claude Code | Hooks, MCP y skill global |
| Codex | Hooks, MCP y skill global |
| Antigravity | Hooks, MCP y skill global |
| OpenCode | Plugin nativo, MCP y skill global; conserva `opencode.jsonc` |
| Cursor | Hooks, MCP y skill global |

También puedes instalar solo uno con `synopsis install opencode` o
`synopsis install cursor`. Todos comparten el mismo almacén de memoria por proyecto.
OpenCode usa una API experimental para añadir contexto al sistema. Cursor recibe
contexto al iniciar la conversación y después de herramientas; la guía inicial
indica consultar `recordar` por tarea. Su hook de envío de mensajes solo registra
actividad porque el contrato documentado no admite contexto adicional.

Estas integraciones son locales. Los agentes cloud o una sesión SSH en otra máquina
necesitan Synopsis instalado en el entorno donde corren.

## Continuidad entre tareas y modelos

Synopsis abre ciclos de memoria por tarea, recupera evidencia del proyecto y conserva
operaciones pendientes ante interrupciones. Los agentes cierran cada ciclo guardando
cambios durables o indicando que no hubo nada nuevo. Los conflictos permanecen visibles.
El estado temporal del trabajo se conserva separado de las notas de conocimiento.

```bash
synopsis cycle status --project /ruta/proyecto
```

Puedes consultar un modelo directamente, sin programar adaptadores:

```bash
synopsis run --project /ruta/proyecto --prompt 'Recuerda que la retención es 300 segundos'
synopsis run --project /ruta/proyecto --prompt '¿Qué retención decidimos?'
synopsis providers
```

Detecta Ollama local y clientes instalados (Codex, Claude, OpenCode). Usa el modelo
predeterminado del cliente autenticado; `--provider` y `--model` permiten elegirlo.
Las cuentas y disponibilidad de los proveedores siguen siendo necesarias. Para una
API externa usa las variables descritas en [Modelos y semántica](docs/models.md).
El modo controlado comprueba el cierre de memoria antes de entregar la respuesta. Las capacidades y límites de los hooks,
el protocolo y las pruebas están en [Continuidad](docs/continuity.md).

Las memorias nuevas tienen una identidad de proyecto independiente del IDE. Las
existentes con propietario explícito se reutilizan en su ubicación. Si Synopsis
encuentra una carpeta antigua sin propietario identificado, `synopsis memory-location
--project /ruta/proyecto` muestra el caso para vincularla sin copiarla. Consulta la
[compatibilidad de memorias existentes](docs/continuity.md#identidad-y-compatibilidad-de-proyectos).

## Una memoria que admite correcciones

Los recuerdos siguen siendo archivos Markdown editables. Las escrituras por CLI o
MCP tienen bloqueo por proyecto, historial SQLite y recuperación si se interrumpe la
actualización de la nota o su índice. Los reintentos idénticos no duplican entradas.

```bash
printf '%s\n' 'La caché Redis caduca a los 120 segundos.' | \
  synopsis memory save --project /ruta/proyecto --file cache-policy \
  --description 'Duración de caché Redis' --source 'user:decision-2026-10-16' \
  --state confirmed --cue 'redis cache ttl retention'

synopsis recall 'redis cache ttl retention' --project /ruta/proyecto --budget 3000
synopsis memory history --project /ruta/proyecto --file cache-policy
```

Para corregir una nota existente usa `--overwrite --expected-revision N`. La revisión
esperada impide reemplazar cambios que no has leído. Si una nota externa se reemplaza
explícitamente sin revisión esperada, su texto previo también queda en el historial.

Cada recuerdo declara procedencia y estado: `inferred` por defecto, `confirmed` si el
usuario lo confirmó, o `archived`. `--expires-at` admite una fecha ISO 8601 con zona
horaria. Los recuerdos archivados o vencidos dejan de recomendarse; su historial se
conserva. Estas etiquetas son declaraciones del cliente, no verificaciones de verdad.

`--cue` agrega sinónimos o preguntas de recuperación en cualquier idioma. Las claves
ayudan a encontrar el contenido y quedan separadas de los hechos. Son pistas explícitas. La búsqueda híbrida añade embeddings cuando hay un proveedor disponible; consulta [Modelos y semántica](docs/models.md).

## Contexto medido y aprendizaje por resultados

`recall` devuelve JSON con citas de archivo y líneas, huella SHA-256, procedencia,
razón de recuperación y un presupuesto para el paquete completo **en caracteres**.
Se abstiene cuando no encuentra evidencia suficiente; no rellena un cupo de notas.
Excluye proyectos ajenos y verifica en disco la vigencia y el pasaje antes de citarlo.
Si cambió desde la indexación, lo omite hasta que el índice se actualice.

Un paquete con evidencia incluye `feedback_id`. Evalúa su utilidad después de resolver
el pedido, no solo por haber abierto una nota:

```bash
synopsis feedback ID --project /ruta/proyecto --outcome useful --source 'user:review'
```

También admite `irrelevant` e `incorrect`. La evaluación se aplica al paquete completo,
no identifica cuál fragmento fue incorrecto. Ajusta el orden dentro de límites pequeños;
no convierte un recuerdo en un hecho verificado ni agrega coincidencias sin evidencia.
Cada paquete recibe una sola evaluación, ligada al proyecto y a las huellas de sus
archivos. El registro no conserva la consulta ni los fragmentos, solo su hash y las
referencias; ignora evaluaciones de más de 90 días y las purga al registrar un nuevo paquete.

## Conectar otro modelo

Configura un cliente MCP compatible con transporte stdio:

```json
{
  "mcpServers": {
    "synopsis": {
      "command": "python3",
      "args": ["/ruta/synopsis/bin/synopsis", "mcp"]
    }
  }
}
```

El ciclo recomendado es `recordar` → consultar la evidencia → responder →
`evaluar_recuerdo`; usa `guardar` para conocimiento durable y `historial_memoria`
para revisar correcciones. La CLI permite integrar ese mismo ciclo en un cliente
sin MCP. La integración debe incorporar el contexto a la petición de su modelo;
Synopsis no modifica los pesos ni garantiza que un cliente obedezca sus hooks.

## Configuración y migración

Estado propio: `~/.local/share/synopsis`; recuerdos compatibles con las herramientas:
`~/.claude/projects/<ruta-del-proyecto-con-guiones>/memory/`. No hace falta instalar
Claude para utilizar esa carpeta. Puedes cambiar el motor y su estado con
`SYNOPSIS_ROOT` y `SYNOPSIS_DATA`.

Para copiar configuración e historial desde otra instalación a un destino vacío:

```bash
python3 bin/synopsis migrate-data /ruta/datos-anteriores           # vista previa
python3 bin/synopsis migrate-data /ruta/datos-anteriores --apply   # copia local
```

No copia sesiones, claves del mapa ni cachés y conserva el origen. No reemplaza un
destino existente ni desactiva servicios o integraciones anteriores. Para cambiar una
instalación en uso, desactiva primero su integración y servicio; después instala esta
versión. Un comando existente que pertenezca a otra instalación no se reemplaza solo.

Una fuente visual puede contener memoria y documentación sin mezclarlas. Configura
las raíces explícitamente cuando no usen una carpeta `memory`:

```json
{"raices": [
  {"ruta": "/ruta/memoria", "recursivo": false, "alias": "memory", "memoria": true},
  {"ruta": "/ruta/proyecto/docs", "recursivo": true, "alias": "docs", "memoria": false}
]}
```

## Comprobarlo

```bash
python3 -B -m unittest discover -s tests
python3 -B tools/evaluate_memory.py
python3 -B engine/herramientas/prueba_humo.py
```

El evaluador usa un corpus sintético versionado: preguntas directas e indirectas,
claves bilingües, reglas retiradas, caducidad, aislamiento y consultas sin respuesta.
Reporta recall@5, MRR, abstención y filtraciones entre proyectos. No mide la inteligencia
del modelo ni acredita resultados sobre LoCoMo u otros benchmarks externos.

Las pruebas integrales requieren poder abrir puertos locales y ejecutar un navegador;
las comprobaciones de PowerShell requieren Windows. Para explorar sin tus datos:

```bash
sh engine/bin/synopsis abrir --demo
```

El código incorporado conserva su [licencia MIT](LICENSE).

## Conciliar y aprender de resultados

```bash
synopsis reconcile --project /ruta/proyecto --output /tmp/revision.json
# Revisa findings y actions del archivo antes de aplicar:
synopsis reconcile --project /ruta/proyecto --apply /tmp/revision.json
```

La revisión detecta duplicados y contradicciones de significado mediante el modelo.
Un plan desactualizado se rechaza. Una contradicción sin resolver no elige ganador;
archivar un duplicado conserva su historial y exige otro recuerdo superviviente.
`synopsis learn` registra experiencias con resultado y evidencia local: [formato](docs/models.md#experiencias).

Para generar un ZIP distribuible, con manifiesto SHA-256 y sin estado personal:
`python3 tools/build_release.py --output /tmp/synopsis.zip`.

### RAG de decisiones (0.7)

Synopsis puede recuperar experiencias opuestas de un mismo problema, comprobar sus
requisitos actuales y mostrar la observación que falta para decidir. Una configuración
parecida no basta para aplicar una solución antigua. Usa `synopsis experience decide`
o la operación `decide` de la herramienta MCP `experiencias`; los hooks lo incorporan
automáticamente cuando el cliente admite el evento. [Funcionamiento, diagrama y
límites](docs/decision_rag.md).

## Desarrollo con asistentes

El arnés compartido vive en [AGENTS.md](AGENTS.md) y [.agents/docs/](.agents/docs/README.md).
Al iniciar, lee la tarea activa y las decisiones locales; sigue el ciclo de descubrir,
planear, implementar, validar y registrar. Las plantillas permiten inicializar el
estado de cada desarrollador sin copiar memorias ni datos de otros proyectos.
