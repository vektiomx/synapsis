# Arquitectura de Synopsis

## Qué problema resuelve

El modelo no recuerda entre sesiones por sí mismo. Synopsis conserva conocimiento
fuera del modelo y entrega evidencia adecuada al proyecto y al presupuesto disponible.
La recuperación, el guardado y la evaluación se pueden usar sin un proveedor de IA.

## Decisiones de esta versión

1. **Markdown como interfaz humana, SQLite como diario de operaciones.** El texto sigue
   siendo inspeccionable y compatible con las herramientas existentes. La base local
   registra revisiones y una bandeja de proyecciones pendientes. No se mantienen dos
   copias autoritativas sin explicación: Markdown es el estado visible; el diario
   conserva la historia de escrituras realizadas por Synopsis y las reemplazadas.
2. **Confirmación separada de relevancia.** Estado y procedencia no son un puntaje de
   verdad. `inferred` no se convierte en `confirmed` porque una nota se haya leído mucho.
3. **Aislamiento antes del ranking.** El contexto estructurado admite archivos dentro
   del proyecto, su carpeta compartida de memoria o una fuente con propietario
   explícito. No utiliza una inferencia temática como permiso de acceso a otro proyecto.
4. **Recuperación híbrida con evidencia.** BM25 y claves explícitas se fusionan con
   rankings por coseno de embeddings reales mediante reciprocal rank fusion. El
   proveedor se descubre localmente o se configura explícitamente para endpoints
   externos. La ausencia o fallo de embeddings conserva la búsqueda textual. Las
   notas se filtran por propiedad, vigencia y huella antes de vectorizar.
5. **Aprender de resultados, con influencia limitada.** La herramienta de evaluación
   registra una única opinión por paquete. Un prior neutral y un factor entre 0.85 y
   1.15 ajustan el ranking de candidatos que ya tienen evidencia; no eliminan el piso
   de relevancia. El resultado se liga a ruta y SHA-256, por lo que una corrección no
   hereda automáticamente los votos de su versión anterior.
6. **Una agrupación visual no cambia el tipo de sus archivos.** Cada raíz puede declarar
   `memoria: true/false`. Para configuraciones mixtas anteriores se reconoce la raíz
   llamada `memory` o con `MEMORY.md`. Los documentos conservan su clasificación: no
   se les exige frontmatter ni una entrada en el índice de recuerdos, y los procesos
   de mantenimiento no los consideran memorias solo por compartir un grupo.
7. **Sin extracción masiva oculta.** Se guardan decisiones y correcciones relevantes a
   través del cliente. Las claves de API y claves privadas reconocibles se rechazan,
   aunque ese detector no reemplaza una revisión de información sensible.

## Guardado y recuperación tras un fallo

`MemoryStore.save` valida los datos y toma un bloqueo de la carpeta de memoria. Lee la
revisión actual y, si el cliente entregó una revisión esperada, rechaza cambios externos
no conciliados. Los reintentos idénticos devuelven la misma revisión. Una copia exacta
con otro nombre se rechaza para evitar ruido duplicado.

Una transacción SQLite registra la nueva revisión y las proyecciones de nota e índice,
incluidas las huellas previas. Después publica cada archivo con reemplazo atómico,
sincroniza sus datos y el directorio, y elimina la bandeja pendiente en otra transacción.
Si el proceso termina entre ambos pasos, el siguiente guardado o consulta de historial
reanuda las proyecciones. Si alguien editó alguno de esos archivos, se detiene sin
pisarlo: hay que conciliar explícitamente el contenido y la revisión pendiente.

Las modificaciones manuales no se interceptan en el momento de realizarlas. Al
reemplazarlas explícitamente, su contenido previo se importa al historial. El diario
no proporciona una garantía de durabilidad frente a fallos del hardware subyacente.

## Recuperación de contexto

`context_memory.recall` selecciona el alcance y descarta recuerdos archivados, vencidos
y rutas sensibles. Obtiene candidatos del índice léxico y aplica el piso absoluto y
relativo. El feedback puede cambiar el orden, pero nunca crear una coincidencia.
Relee el archivo, valida que el pasaje indexado siga correspondiendo y devuelve texto,
archivo, líneas y huella. Un archivo cambiado se omite hasta refrescar su indexación.

El paquete completo respeta un límite en caracteres; no se presenta una estimación
como si fueran tokens del modelo. Su aviso delimita las notas como datos. Ningún texto
recuperado se ejecuta por el motor; el cliente debe mantener esa separación al construir
su prompt. No se garantiza inmunidad a inyección de instrucciones en un modelo cliente.

El MCP conserva las herramientas de consulta y añade `recordar`, `historial_memoria`
y `evaluar_recuerdo`. `guardar` utiliza el nuevo almacén. La salida estructurada puede
integrarse con cualquier cliente compatible; no requiere que el modelo sea de una
marca determinada. Los hooks conservan el flujo existente de consulta y recordatorio,
con filtrado de vigencia y alcance por proyecto. La evaluación explícita nueva se usa
en los paquetes de `recordar` y de la CLI `recall`.

## Instalación

La CLI ofrece selección guiada, selección múltiple, vista previa, colores opcionales,
resumen de resultados y detalles técnicos a pedido. Los instaladores siguen haciendo
respaldos y conservando configuraciones ajenas. Las rutas de comandos se citan para
admitir espacios. El servicio Linux y la CLI comparten el directorio de estado.

`migrate-data` copia una lista limitada de configuración e historial a un destino vacío.
Excluye estado en vivo y claves. No desactiva instalaciones existentes ni mezcla datos.
La versión en desarrollo vive en un worktree separado para preservar la instalación
actual durante la revisión.

## Medición y límites

Las pruebas propias cubren escrituras concurrentes, interrupciones, recuperación,
revisiones antiguas, ediciones externas, duplicados, permisos, aislamiento, vigencia,
citas, presupuesto, MCP, CLI y feedback. El evaluador sintético versionado agrega
preguntas directas e indirectas, vocabulario bilingüe y abstención. La prueba integral
abarca el motor anterior, el servidor autenticado, el mapa y los lanzadores.

Esas comprobaciones validan mecanismos y regresiones. No demuestran que todos los
modelos razonen mejor, ni que las claves propuestas por un agente sean correctas. No
se han corrido benchmarks externos de conversaciones largas ni pruebas de Windows.

## Fuentes de diseño

- [Transacciones atómicas de SQLite](https://www.sqlite.org/atomiccommit.html).
- [MCP: herramientas y resultados estructurados](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).
- [LoCoMo: evaluación de memoria conversacional](https://aclanthology.org/2024.acl-long.747/), como referencia para evaluaciones externas futuras, sin atribuirnos sus resultados.

## Instalación automática e integraciones

`integration_runtime.py` concentra el registro, el despacho de eventos y la selección
de hooks. Los adaptadores de los cinco clientes conservan únicamente su traducción
de protocolo y las peculiaridades del cliente. Codex preserva su normalización de
parches y su manejo de subagentes. Antigravity no interpreta cada PostInvocation como
el cierre del chat, ni vuelve a inyectar el mismo pedido en invocaciones sucesivas.

`mcp_entry.py` es el punto de entrada común. Los cinco instaladores registran MCP y
skills además de sus hooks. `integration_setup.py` comparte el guardado de configuración
con bloqueo, respaldos y reversión si falla un reemplazo. No reemplaza servidores MCP
ajenos que usen el mismo nombre. El modo predeterminado detecta los clientes y no pide
selección; --interactive mantiene la selección manual opcional.

`integration_health.py` prueba initialize/tools-list y el arranque de cada adaptador.
Verifica rutas, intérprete, estado y configuración instalada. Las marcas de actividad
se escriben solo al recibir eventos, con fecha, evento y resultado, sin guardar el
pedido ni el contenido de las notas. Un sondeo --probe no deja marcas y no suplanta
la aprobación del host. No se modifican archivos de confianza para saltar permisos.

Referencias de los contratos de integración consultadas el 16/10/2026:
- https://developers.openai.com/plugins/build/plugins
- https://www.antigravity.google/docs/hooks
- https://www.antigravity.google/docs/mcp
- https://code.claude.com/docs/en/mcp

OpenCode usa un plugin nativo JavaScript sin dependencias adicionales. Traduce
eventos a Python por stdin sin shell, limita tiempo/salida y conserva el texto del
usuario. Su hook config agrega el MCP en memoria y preserva el JSONC original. El
contexto de cada sesión vive separado en un caché limitado y se descarta al cerrar
o compactar. La API experimental de contexto requiere seguimiento de versiones.

Cursor traduce los nombres de eventos y sus campos propios. No presupone que
beforeSubmitPrompt acepte contexto: registra el evento y devuelve continue. El
contexto inicial guía el uso de recordar; sessionStart y postToolUse usan
additional_context. Ante varias raíces sin cwd explícito se abstiene. Como Cursor
no hace cumplir ask en preToolUse, esa decisión se convierte en deny con motivo.

Fuentes adicionales:
- [Plugins OpenCode](https://opencode.ai/docs/plugins/).
- [Contrato de hooks de OpenCode](https://github.com/anomalyco/opencode/blob/dev/packages/plugin/src/index.ts).
- [MCP de OpenCode](https://opencode.ai/docs/mcp-servers/).
- [Hooks de Cursor](https://cursor.com/docs/hooks).
- [Skills de Cursor](https://cursor.com/help/customization/skills).

## Ciclos de memoria y ejecución controlada

MemoryCycle persiste turnos, operaciones y checkpoints dentro del diario SQLite de
MemoryStore. Un identificador idempotente liga la operación al recibo confirmado en
la misma transacción que la revisión/outbox. Las proyecciones se verifican antes de
marcar applied. Un bloqueo de worker serializa conciliación y descarte. El contrato
no promete atomicidad entre notas ni veracidad semántica.

El runtime invoca hook_cycle.py para consulta con alcance y continuidad. Los avisos
posteriores a herramientas se limitan por turno. controlled_run.py implementa el
protocolo adicional synopsis.run.v2: prepara contexto y estado, ejecuta un adaptador
JSON del usuario o un conector incorporado sin shell y solo entrega answer después de cerrar el ciclo.

Frontmatter se extrajo como parser puro compartido, evitando que guardar memoria
inicialice configuración o cree directorios de la aplicación. Los contratos,
ejemplos y límites están en [continuity.md](continuity.md).

## Identidad y orden de confirmación

project_identity.py es el resolver de carpeta usado por MCP, CLI y ciclos. La clave
es la huella completa de la raíz canónica; los manifiestos conservan esa raíz para
detectar una colisión o manipulación. El registro de ubicación permite adoptar
fuentes existentes explícitamente asignadas sin mover el diario SQLite ni invalidar
sus recibos. Una intención durable precede a propietario/ubicación. El bloqueo de
carpeta evita propietarios concurrentes incluso entre raíces de estado distintas.

Las carpetas heredadas sin asignación no se apropian por su slug ambiguo. El lector
consulta la propiedad del archivo y descarta fuentes de otro proyecto, aun si una
asignación de índice quedó obsoleta. El mapa descubre registros verificados sin
duplicar raíces; demo los excluye. La propiedad se consulta una vez por carpeta
durante cada paquete para evitar repetir I/O por cada nota. El filtro belongs no
registra ubicaciones ni crea estado. Los manifiestos guardan el perfil de configuración
de origen y no se descubren automáticamente desde otros perfiles.

Los checkpoints usan checkpoint_sequence monotónica confirmada bajo el bloqueo del
diario. El control de revisión compara la última confirmación, no el rowid de
apertura del turno. La migración de datos anteriores usa updated_at y rowid como
desempate estable, porque ese histórico no tenía secuencia de confirmación.


## Inferencia y conciliación semántica

model_provider.py ofrece conectores HTTP y clientes nativos, sin dependencias Python.
Las peticiones HTTP tienen límites de tiempo/tamaño, no siguen redirecciones y
exigen HTTPS fuera de loopback. OpenAI usa Responses con store=false. El transporte
nativo limita permisos, salida y procesos; la inferencia controlada no inicia otro
ciclo de hooks de Synopsis. La disponibilidad de cuentas no equivale a un binario instalado.

semantic_memory.py separa la identidad del proveedor/modelo/endpoint y las huellas
de fragmentos en una caché SQLite por proyecto. No persiste consultas; elimina hashes
obsoletos de ese proveedor. Limita el trabajo por recuperación y declara ready,
warming, unavailable o degraded. Los scores semánticos no certifican relevancia ni verdad.

reconciliation.py entrega hallazgos con nombres/versiones y un plan revisable.
Antes de aplicar valida huellas y revisiones, impide confirmar inferencias del
conciliador y bloquea notas con contradicciones reportadas. Usa el diario de ciclos
para que los lotes parcialmente aplicados sigan visibles. Las propuestas del modelo
requieren revisión: la validación estructural no demuestra equivalencia semántica.

experience_memory.py conserva tarea/acción/resultado y evidencias locales con huellas.
Las experiencias siguen siendo inferred; un hash comprueba la versión del archivo,
no prueba que el relato del agente sea correcto.


## Puerta de evidencia v2

EvidenceLedger separa el borrador libre de la respuesta publicable. Mantiene snapshots
por proyecto, origen, huella y tramo. Los ids son emitidos por el controlador; las
peticiones del modelo no pueden introducir fuentes arbitrarias ni ejecutar comandos.
La respuesta se construye con texto literal y se vuelve a comprobar antes de cerrar.
El estado evidence_bound expresa fidelidad a la fuente, nunca verdad universal.

MemoryCycle conserva cycle_policies y cycle_admissions junto al diario existente.
Las admisiones se ligan al contenido canónico de la operación y se guardan al encolar,
antes del commit de la nota. La recuperación comprueba soporte o recupera el recibo
ya confirmado. La política no se rebaja al retomar un turno. El lector exige tanto
una admisión como el recibo de la versión actual y revalida su cadena de soporte.

La interfaz inferida/confirmada de clientes anteriores sigue siendo declarativa.
Las notas antiguas no se borran; el guard las clasifica unverified_memory hasta una
nueva admisión. MCP responder_con_evidencia y CLI verify permiten pedir una salida
extractiva; solo el modo run controla la publicación completa de su propia respuesta.
Detalles, límites y evaluación: [evidence_guard.md](evidence_guard.md).

## Registro automático de workspaces (0.4)

workspace_registry.py descubre raíces sin recorrer el disco y conserva un UUID
local por checkout. project_identity.py mantiene el índice por ruta y el propietario
del almacén, reconoce reubicaciones y conserva una intención recuperable. Las notas
no se copian al adoptar memoria anterior. La evidencia de migración procede de
metadatos cwd del cliente; los casos ambiguos se resuelven por una solicitud
persistente y una elección autenticada en el mapa. Copias y worktrees tienen
almacenes separados. Véase [project_binding.md](project_binding.md).


## Recuperación local y laboratorio (0.8)

experience_retrieval.py fusiona BM25, anclajes técnicos y vectores por proyecto
para recall de experiencias y DecisionRAG. local_semantics.py y semantic_worker.py
separan el núcleo sin dependencias del venv ONNX preparado por semantic_setup.py.
La revisión presenta notas relevantes con admisión para actualizar sin perder
políticas complementarias. experience_lab.py interviene guardas en snapshots y
reutiliza el runner bwrap; MCP solo planea.
[Contratos y diagrama](decision_rag.md), [runtime y límites](local_semantics.md),
[evaluación reproducible](upgrade_evaluation.md).
