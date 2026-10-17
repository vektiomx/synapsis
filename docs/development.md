# Desarrollo de Synopsis

## Estado vigente · 2026-10-17 · 0.11 en desarrollo

Primera adaptación de escritorio implementada desde fuentes: entrada macOS .command,
entrada Windows .cmd, comando Windows sin symlinks y PATH de usuario preservado,
LaunchAgent/HKCU Run para mapa persistente, hooks Windows con transporte UTF-8,
CLI de arranque y diagnóstico de capacidades. Memorias/rutas anteriores conservadas.

La validación disponible se ejecutó en Linux. La matriz nativa está preparada en
.github/workflows/desktop-platforms.yml y no fue ejecutada desde esta sesión.
Pendientes ejecución real en Mac/Windows, runtime embebido y paquetes firmados.
Detalles, comandos y alcance en [desktop_adaptation.md](desktop_adaptation.md).

## Entrega anterior · 0.10

Implementada memoria de comportamiento: captura de aserciones literales observadas,
reproducción histórica, alcance y retiro con revisión, integración con investigación,
contexto de prompt/edición, CLI/MCP y panel del mapa. Trabajo local en
`feat/reliable-project-memory`; sin commits, push ni PR. La instalación local apunta
al checkout actual. La validación y comparación completas están en
[competitive_evaluation.md](competitive_evaluation.md) y [behavior_memory.md](behavior_memory.md).

La comparación reservada empató precisión con todos los perfiles de memoria y
evitó las llamadas de captura de los perfiles con inferencia. Mem0 raw e historial
completo también empataron sin esas llamadas. No es una victoria universal ni una
medición de productividad OSS. Trazas y errores iniciales se conservan.

## Historial desde 2026-10-16

Rama: `feat/reliable-project-memory`. Checkout independiente:
`/var/www/html/projects/synopsis`. La instalación en uso y los cambios locales de
`/var/www/html/projects/synapsis` se conservan.

## Trabajo solicitado

- [x] Auditar el guardado y la recomendación de información.
- [x] Cambiar el nombre operativo y los archivos a Synopsis / synopsis.
- [x] Añadir guardado versionado, procedencia, vigencia y recuperación de escrituras.
- [x] Corregir la clasificación de documentación dentro de fuentes mixtas.
- [x] Añadir contexto estructurado por proyecto con citas y presupuesto explícito.
- [x] Añadir claves de recuperación para consultas indirectas y otros idiomas.
- [x] Añadir evaluación de utilidad ligada a las versiones de los recuerdos.
- [x] Exponer las capacidades mediante MCP y CLI para clientes de distintos modelos.
- [x] Tarea extra: mejorar la experiencia del instalador Linux.
- [x] Proporcionar migración de datos con vista previa y sin copiar claves en vivo.
- [x] Crear pruebas de regresión y un evaluador sintético reproducible.

## Hallazgos de la auditoría

- Guardar una nota y actualizar su índice eran escrituras independientes sin bloqueo.
- Reemplazar una nota perdía el contenido anterior y podía duplicar su entrada de índice.
- Agrupar documentación dentro de una fuente de memoria generaba diagnósticos falsos.
- El MCP de consulta no exigía alcance por proyecto ni devolvía paquetes estructurados.
- La lectura posterior de una recomendación no prueba que haya ayudado al resultado.
- Los nombres del producto, los comandos y las rutas de estado estaban mezclados.

## Validación

- Pruebas propias: 63 pruebas aprobadas; incluyen persistencia, concurrencia,
  recuperación, MCP, CLI, caché, migración e instalación.
- Motor y mapa: 767 de 767 comprobaciones aprobadas. Una comprobación de
  PowerShell sin validar en esta máquina Linux.
- Evaluador sintético: 13 consultas; recall@5 = 1.0, MRR = 1.0,
  abstención correcta en 3/3 negativos; cero filtraciones de proyecto o reglas retiradas.
  Estos resultados son del corpus sintético, no de conversaciones reales o LoCoMo.
- Sintaxis Python y whitespace del diff comprobados; finales CRLF conservados para
  los lanzadores Windows. Sin ocurrencias del nombre anterior en los archivos del producto.
- El checkout original conserva exactamente los archivos previos a esta tarea.

La validación integral encontró una regresión en la invalidación de caché: al cambiar
solo la fecha de un archivo se descartaba evidencia cuyo contenido seguía siendo
idéntico. Se corrigió comparando la huella del contenido cuando cambia la firma de
archivo. Las pruebas ahora verifican tanto el índice refrescado como el rechazo de
texto que ya no está en el archivo.

No se hicieron commits, pushes ni cambios en la instalación en uso. La activación de
esta versión queda fuera del cambio local solicitado.


## Seguimiento: instalación plug and play

- [x] Instalación automática predeterminada y selección manual opcional.
- [x] MCP, adaptadores y skill compartida instalados para los cinco clientes.
- [x] Runtime común de eventos y formatos nativos en cada adaptador.
- [x] Transacción compartida para configuración con respaldo y reversión.
- [x] Diagnóstico de transporte, configuración y recepción real de eventos.
- [x] Pruebas con un HOME ficticio: instalación de cinco clientes sin preguntas,
  reinstalación, MCP real y recepción de eventos SessionStart en los cinco adaptadores.
- [x] Verificación final en el checkout de la rama: 75 pruebas propias aprobadas y diff sin errores de whitespace.

No se altera la instalación en uso. La autorización inicial de hooks sigue siendo
responsabilidad del cliente; el instalador no modifica sus decisiones de confianza.

## Seguimiento adicional: OpenCode y Cursor

- Petición explícita: compatibilidad con ambos en la misma instalación automática.
- OpenCode: plugin nativo global sin dependencias; hook config registra MCP sin
  reescribir opencode.jsonc. Los eventos usan el runtime común. El contexto se
  incorpora mediante experimental.chat.system.transform; API experimental.
- Cursor: hooks globales, MCP y skill. beforeSubmitPrompt solo registra actividad;
  su contrato documentado no permite inyectar contexto. sessionStart y postToolUse
  sí lo permiten. La guía inicial pide consultar recordar por tarea.
- La integración local no instala hooks en agentes cloud o máquinas remotas.
- Doctor ampliado a cinco clientes. Pruebas de instalación automática/reinstalación,
  preservación de JSONC, conflictos, contratos de permiso, aislamiento de sesiones
  y transporte real JS → Python.
- En esta etapa previa: 75 pruebas propias aprobadas también en el checkout definitivo.
- Cero ocurrencias del nombre anterior en nombres o contenido de archivos del producto.
- La carga efectiva dentro de las aplicaciones y sus autorizaciones iniciales no
  se simulan: el diagnóstico espera el primer evento real de cada IDE.

## Continuidad y aprendizaje comprobable: primer incremento

El usuario autorizó comenzar la arquitectura propuesta. Primer incremento: núcleo
de ciclos durables, recuperación por tarea, conciliación con revisiones y recibos
verificados. Después: ejecución controlada por Synopsis y evaluación de continuidad.

Decisiones de implementación:
- El modelo propone conocimiento; el núcleo controla persistencia y versiones.
- Las notas recuperadas son evidencia, nunca instrucciones.
- No se guarda el prompt completo en el diario: solo huellas y operaciones propuestas.
- Un turno saved exige escrituras comprobadas; no_change exige motivo.
- Los conflictos se conservan hasta conciliación explícita. No se fuerzan revisiones.
- Recuperación idempotente entre la escritura y su acuse, incluso con cierre abrupto.
- Cursor conserva su contrato: registra el ciclo al enviar y orienta vía MCP.
- La semántica y la veracidad requieren evaluación; no se atribuyen a los recibos.

Validación realizada: regresiones del prototipo corregidas; pruebas de proceso,
concurrencia, MCP, hooks, protocolo controlado y continuidad entre sesiones.
La comprobación final del checkout se registra abajo.

Diseño del modo controlado: adaptador de proceso sin shell con protocolo JSON
synopsis.run.v1. La respuesta solo se entrega después de cumplir el contrato de
memoria. Estado de trabajo breve (checkpoint) separado de las notas, con control
de concurrencia. Los hooks nativos siguen siendo cooperativos: sus permisos y
capacidades no se presentan como una garantía de obediencia del modelo.

Cierre del primer incremento:
- 97 pruebas propias, incluyendo 22 añadidas desde la etapa de integraciones.
- 767/767 comprobaciones integrales del motor/mapa aprobadas (77 segundos).
  PowerShell de Windows sigue sin validar en esta máquina.
- Evaluador sintético de recuperación: 13/13 casos, sin fugas de proyecto ni
  versiones retiradas. No es una evaluación de inteligencia de modelos.
- Tres adaptadores programados en procesos independientes conservan checkpoint,
  corrigen TTL 120 → 300 y recuperan solo el valor vigente.
- El protocolo retiene la respuesta ante contrato ausente o actualización obsoleta.
- Nuevas herramientas MCP: iniciar_turno_memoria, estado_memoria y cerrar_turno_memoria.
- Comandos nuevos: cycle y run; el modo run requiere un adaptador JSON explícito.
- Siguiente etapa: conectores de inferencia y evaluación con modelos reales; después,
  recuperación semántica híbrida y conciliación semántica contrastada.

## Revisión adicional solicitada por el usuario

La suite existente se repite sin cambios de código. Se añadieron comprobaciones
exploratorias en un entorno temporal, fuera de la suite, y se reprodujeron dos
defectos, posteriormente corregidos en la sección siguiente:

1. `_checkpoint` ordena por rowid de apertura del turno. Si un turno anterior cierra
   después de otro más reciente y concilia su checkpoint mediante la revisión
   esperada, `working` todavía devuelve el checkpoint del turno abierto después.
   La selección debe reflejar el orden confirmado de las actualizaciones.
2. `slug_de_proyecto` reemplaza tanto separadores como parte de la estructura por
   guiones. Las raíces `alpha-beta` y `alpha/beta` colisionan en la misma carpeta
   de memoria. Falta una identidad de proyecto sin colisiones y una migración
   compatible de las memorias existentes, sin duplicarlas ni asignarlas por suposición.

Estas comprobaciones no modificaron datos reales. Los hallazgos motivaron la
corrección y las regresiones documentadas en la sección siguiente. Los pendientes de producto anteriores
(conectores de inferencia, modelos reales, semántica e integración efectiva en IDE)
siguen vigentes. Esta revisión informa hallazgos; no los declara corregidos.

## Corrección de la revisión adicional

- Checkpoints: secuencia monotónica de confirmación bajo bloqueo, sin depender del
  orden de apertura ni del reloj para nuevas escrituras. Migración del esquema previo
  con sus timestamps de cierre; desempate estable cuando el histórico no distingue.
- Identidad: raíz canónica + SHA-256 completo y manifiestos con la raíz original.
  Proyectos nuevos usan estado de Synopsis; memorias explícitamente asignadas por
  configuración se vinculan en su ubicación original, sin copiar notas/historial.
- Memorias heredadas sin asignación no se adjudican por el nombre de su carpeta.
  memory-location muestra el candidato y permite vincular una ubicación existente.
- No se modifican memorias ni configuración de la instalación activa.

Validación de la corrección:
- 123 pruebas propias aprobadas también en el checkout definitivo.
- Los casos exploratorios de la revisión ya son regresiones automatizadas.
- MCP real en un único proceso guarda y recupera por separado alpha-beta y alpha/beta.
- Compatibilidad: notas, MEMORY.md e historial SQLite se conservan byte a byte en
  su ubicación; no se generan copias al vincular memorias existentes.
- Nuevas memorias aparecen en procesos nuevos del mapa/buscador; no en demo.
- Las memorias heredadas sin asignación detienen la creación de otro destino hasta
  que se identifica su propietario mediante memory-location.
- Continúan pendientes los conectores de inferencia del modo controlado, evaluación
  con modelos reales, recuperación semántica y validación interactiva en los IDE.

Incidencia encontrada durante la validación integral y corregida:
- La primera corrida dio 766/767: el diagnóstico posterior a partir notas recibía
  una fuente de otra configuración. Reproducción: añadir el corpus principal a
  la configuración de la partición cambia IDF y produce avisos sobre las partes
  nuevas. No era un fallo aleatorio del algoritmo de partición.
- Los registros ahora guardan el archivo de configuración de origen; su descubrimiento
  automático se limita a ese perfil. Demo sigue sin incorporar memorias personales.
- El filtro belongs usado por las búsquedas antiguas dejó de llamar al resolver de
  escritura. Filtrar una nota es de solo lectura y no registra ni adjudica memorias.
- Se retiraron, con respaldo en /tmp, los dos registros globales que las búsquedas
  de prueba habían creado para fixtures; no se tocaron notas ni configuración reales.
- Regresiones añadidas: aislamiento entre archivos de configuración y ausencia de
  escrituras al filtrar contexto. Corrida integral posterior: 767/767 (48,5 s).

Cierre de estas correcciones:
- 123/123 pruebas propias aprobadas en el checkout final.
- Corrida integral final: 767/767 (46,0 s); única omisión, PowerShell de Windows.
- Evaluador de recuperación: 13/13 casos sintéticos, sin fugas entre proyectos ni
  versiones retiradas. Estos resultados no miden calidad de modelos reales.
- Tras la última prueba integral: cero manifiestos de proyectos creados fuera de
  las carpetas temporales de prueba. Sin cambios en notas o configuración reales.
- Sin errores de whitespace, sin nombres anteriores en el producto y sin cambios
  en los archivos del checkout original. No se hicieron commits ni push.
- Los dos defectos reportados quedan corregidos. Los pendientes de producto del
  incremento anterior (inferencia, semántica y validación real en IDE) siguen abiertos.

## Cierre funcional solicitado: inferencia, semántica y conciliación

El usuario pidió completar y pulir todos los pendientes. Trabajo de esta sesión:
- Conectores listos para Ollama, Responses OpenAI, chat compatible y clientes nativos
  Codex/Claude/OpenCode. Sin adaptador propio: `synopsis run --project ... --prompt ...`.
- Recuperación híbrida por reciprocal rank fusion y embeddings reales opcionales.
  Descubrimiento automático solo en Ollama loopback; endpoints externos explícitos.
  Caché por contenido/proveedor/modelo y por proyecto; consultas no persistidas.
- Conciliación semántica asistida por modelo: plan JSON revisable, versiones/huellas,
  conflictos sin ganador automático y archivo de duplicados con superviviente.
- Experiencias con tarea/acción/resultado/evidencia local con huella, siempre inferred.
- Nuevas pruebas de transportes, vectores, citas, conciliación y experiencias.

Validación en curso. La cuenta Go de OpenCode requiere una suscripción activa y
rechazó inferencia: no se contabiliza como éxito. El plugin sí fue cargado por el
cliente real y emitió UserPromptSubmit OK en un HOME temporal. Se detectó que el
cliente puede preferir PWD heredado sobre cwd: conectores ahora pasan proyecto
explícito y PWD coherente. Se está evaluando con modelos gratuitos disponibles.
Todo se desarrolla en /tmp y se sincroniza después a la rama autorizada; no se
modifica la instalación activa, no hay commit ni push.

Comprobación real de continuidad con Codex autenticado: aprobada. Cuatro consultas
independientes: guardado 127 s + código privado aleatorio, corrección 389 s en la
misma nota, recuperación de ambos valores vigentes y referencia sin memoria que
responde desconocido. Dos revisiones, una nota. Es un escenario sintético, no un
benchmark general ni una prueba de transferencia entre dos modelos distintos.
OpenCode real: plugin cargado, UserPromptSubmit OK y respuesta «prueba correcta».
Go exige suscripción; el servicio gratuito rechazó el modo controlado. Ambas
restricciones se respetan y no se contabilizan como pruebas aprobadas de inferencia.

La prueba integral del checkout dio 767/767 (41,9 s); PowerShell de Windows omitido.
La suite tenía 143 pruebas aprobadas; se añadieron después regresiones para reparación
JSON acotada. La validación final de esas adiciones y del ZIP se registra al cierre.

Embeddings reales: BAAI/bge-small-en-v1.5, 384 dimensiones, FastEmbed 0.9.0 instalado
solo en un venv temporal. Transporte HTTP compatible real, caché SQLite y cuatro
consultas sintéticas en inglés. Top-1 correcto en las tres paráfrasis y abstención
en el negativo. Umbral de esa prueba 0.60; el predeterminado sigue en 0.72. Un caso
retuvo además un candidato secundario irrelevante: no se presenta como precisión
perfecta ni como evaluación multilingüe. No se incorporó una dependencia al producto.

La evaluación semántica reveló un fallo de diseño del contrato: pedir al modelo que
fabrique enlaces Markdown genera errores mecánicos aunque el razonamiento sea bueno.
El conciliador ahora pide solo la propuesta de contenido y estado; Synopsis construye
nombre, índice, fuente y revisión a partir del inventario comprobado. La revisión
sigue mostrando el plan completo y nunca elige ganador de contradicciones inciertas.

## Entrega final

- Inferencia lista, búsqueda híbrida, conciliación revisable y experiencias: implementadas.
- Conciliación con Codex real: duplicado semántico y contradicción identificados;
  revisión sin cambios en disco, sin ganador inventado. Plan válido de dos operaciones
  sobre el duplicado; las notas contradictorias quedan intactas.
- Resultados reproducibles y limitaciones: `docs/evaluation_results.json`.
- ZIP reproducible con manifiesto SHA-256, licencias y código; excluye caches/estado.
- Core Python sin dependencias externas. FastEmbed se usó solo para evaluar en /tmp.
- Las restricciones de cuentas se respetan; no se prometen modelos sin autorización.
- Validación interactiva no realizada para Cursor, Antigravity y Claude, ni PowerShell
  de Windows. Sus contratos/adaptadores sí están cubiertos por pruebas automatizadas.
- No se hicieron commits, push, publicaciones ni activación sobre los IDE en uso.

Comprobación final de entrega: 146/146 pruebas aprobadas desde la rama definitiva
(7,22 s). ZIP extraído en un HOME temporal: vista previa sin escrituras y posterior
instalación automática de cinco clientes con MCP/adaptadores comprobados. El original
conserva sus archivos, no hay registros de fixtures en el estado global, no aparecen
nombres anteriores en el producto y el diff pasa whitespace. Rama sincronizada con
el código probado. Los límites de validación de plataformas/cuentas indicados arriba
siguen siendo límites reales, no comprobaciones aprobadas.

## Refuerzo contra respuestas sin respaldo (en curso)

Pedido explícito: priorizar robustez y erradicación de errores posibles. La entrega
anterior completaba memoria/continuidad; no demostraba prevención de alucinaciones.

Plan de esta etapa:
1. Ledger de evidencia con identidad, origen, huellas, alcance y citas revalidadas.
2. Modo controlado v2: borrador del modelo no publicable; respuesta factual estricta
   construida por el controlador a partir de fuentes seleccionadas y comprobadas.
   Abstención determinista ante falta de soporte; hipótesis fuera de los hechos.
3. Herramientas de evidencia acotadas sin shell: lectura local, JSON y cálculo seguro.
4. Admisión de memoria por citas literales seleccionadas, sin promover síntesis del
   modelo a hechos confirmados. Cambios ajenos/revisiones obsoletas bloquean cierre.
5. Pruebas adversariales reproducibles y evaluación real. Ampliar MCP para verificar
   paquetes aunque los hooks no puedan interceptar toda respuesta del IDE.

Decisión: un segundo modelo puede ayudar a juzgar relevancia, pero no sustituye una
comprobación determinista ni se presenta como garantía de verdad. El modo estricto
sacrifica prosa libre para no publicar afirmaciones nuevas del borrador. El texto
citado de una memoria sigue siendo una declaración histórica, no una verdad externa.
No se modifica la instalación activa ni se hace commit/push.

Avance del refuerzo:
- Modo `synopsis.run.v2` implementado: selección de evidencia en vez de publicar
  borrador libre, citas revalidadas, abstención y recibos de escritura separados.
- Ledger con fuentes acotadas; herramientas sin shell para archivos, JSON y cálculo.
- Admisión de párrafos literales completos y normalización de metadatos del agente.
- Política estricta durable por turno y capacidad de admisión interna por operación.
  Reanudar no adopta turnos antiguos ni acepta operaciones nuevas sin admisión.
  Se revalidan archivos de soporte antes de aplicar una operación pendiente.
- Memorias sin admisión durable quedan en cuarentena para el modo estricto, aunque
  un cliente les haya puesto source=user o estado=confirmed. No se borran.
- Superficies CLI verify y MCP responder_con_evidencia; hooks siguen cooperativos.
- Diez escenarios adversariales de proceso aprobados, incluyendo borrador inventado,
  cita falsa, escritura sin apoyo, memoria contaminada, archivo cambiado, comando
  prohibido, rondas ilimitadas, JSON y cálculo. Miden el mecanismo, no una tasa
  universal de alucinación.
- Primera evaluación real v2 se abstuvo tras guardar: todavía se está investigando
  recuperación/cobertura del contenido en una corrección. No se declara aprobada.

Cierre del refuerzo v0.3:
- 173/173 pruebas aprobadas desde la rama sincronizada (10,721 s).
- 767/767 comprobaciones integrales (55,2 s). Se actualizó la lista exacta MCP de
  trece a catorce herramientas; la corrida previa fallaba únicamente por ese cambio
  de contrato. No se retiró ninguna comprobación. PowerShell de Windows sigue omitido.
- Diez escenarios adversariales de proceso aprobados; cero borradores filtrados y
  cero escrituras sin apoyo en esos casos. No son una tasa universal de alucinación.
- Codex real v2: dos decisiones guardadas en una nota, corrección 127 → 389 conservando
  el código aleatorio, recuperación de la versión vigente y abstención en otro proyecto.
  El primer intento mostró una abstención excesiva: el modelo confundía inferred con
  cuarentena. El ledger ahora distingue admisión del controlador y verdad externa;
  se aclaró el contrato sin relajar las comprobaciones. La evaluación posterior aprobó.
- Shell, colaboración y búsqueda se desactivan en esa invocación de Codex; configuración
  personal omitida sin modificarla. Referencia oficial contrastada y flags ejercitados
  por la evaluación real. Gate de publicación sigue siendo propio de synopsis run.
- Los reportes previos en evaluation_results.json son históricos; strict_guard_v03
  contiene esta validación. El modo estricto es extractivo y no publica prosa libre.
- Memorias previas preservadas, sin asignarles una admisión ficticia. No se activó la
  versión en los IDE en uso ni se hizo commit, push o publicación remota.

ZIP v0.3 extraído y probado en un HOME temporal: vista previa sin escrituras,
instalación automática de cinco clientes, doctor con 14 herramientas MCP y comando
verify obteniendo /ttl = 389 desde JSON. El manifiesto coincide con la rama.
La entrega final solo añade esta constancia documental al mismo código probado.

## Requisito confirmado: activación transparente por prompt

El usuario aclaró que instalar debe bastar: cada prompt debe activar Synopsis en
el cliente habitual, sin ejecutar `synopsis run`, pedir recordar ni configurar
adaptadores/proveedores manualmente. El modo controlado opcional no satisface por
sí solo esta experiencia. Esta es una condición de aceptación del producto.

El instalador ya detecta clientes y configura hooks/MCP/skill. El runtime consulta
memoria en UserPromptSubmit para mensajes de usuario admitidos; el guardado de
conocimiento sigue requiriendo una propuesta y recibo, no copia masiva del chat.
Las autorizaciones iniciales que exige el cliente se conservan.

Brechas pendientes, sin declararlas resueltas:
- Cursor ejecuta la consulta al enviar, pero beforeSubmitPrompt solo devuelve
  continue/user_message: no entrega ese contexto al modelo. SessionStart y
  PostToolUse no equivalen a una inyección antes de cada prompt.
- Los clientes nativos no quedan sujetos al gate extractivo de synopsis run.
- Un gateway HTTP fue propuesto como transporte adicional, pero no está implementado
  ni resuelve automáticamente clientes que no permiten cambiar de endpoint.
- No se promete interceptar aplicaciones o modelos externos sin un punto de
  integración soportado. Una marca de actividad no acredita entrega de contexto.

Contrato de Cursor contrastado el 16/10/2026:
https://prod.cursor.com/docs/hooks#beforesubmitprompt
Esta revisión registra el requisito y la brecha; no cambia el runtime ni activa la
instalación en uso. La siguiente implementación debe probar entrega por prompt,
aislamiento de proyecto y continuidad, además del arranque del adaptador.

## Corrección del diagnóstico de enlaces externos

Tras reinstalar, el mapa presentó 98 avisos de enlaces rotos, todos en el índice
meximova-documentation-index.md. Se verificaron los 98 destinos completos: existen.
El analizador confundía ausencia en el grafo con ausencia en disco. Ahora comprueba
la existencia del archivo antes de marcar roto; no lee ni incorpora documentos
externos al grafo por seguir un enlace. Conserva avisos para archivos ausentes y
para directorios con nombre .md. También respeta rutas absolutas locales.

Regresión nueva: enlaces relativos/absolutos, escapes URL y fragmentos, destinos
externos sin lectura de contenido, inexistentes, directorios y aristas indexadas.
Suite propia: 174/174 aprobadas (10,669 s). La aplicación activa se actualizará y
se comprobará la regeneración del diagnóstico; esta constancia no la da por hecha.

Verificación de la instalación activa tras aplicar: servicio synopsis-mapa reiniciado,
problemas.json regenerado con 0 problemas; las notas no fueron modificadas.
Prueba integral posterior: 767/767 (53,5 s), PowerShell de Windows omitido.
El mapa predeterminado muestra dos nodos MEMORY: uno es el índice vacío de
FCSJ-backend y el otro el índice de Meximova. No son copias; la etiqueta común y
la agrupación global Sin proyecto dificultan reconocer su propietario.

## Reparación de hook_cycle tras reinstalar

Causa reproducida: ProjectIdentityConflict al resolver Meximova porque había memoria
heredada sin asignación explícita. El bridge ocultaba la causa como RuntimeError.
Se vinculó explícitamente el proyecto con su carpeta existente, verificada en esta
sesión; no se copiaron notas ni se creó un segundo destino de memoria.
El hook ahora devuelve un código memory_identity_conflict y una indicación para
revisar memory-location, sin mostrar texto arbitrario de excepciones. El runtime
lo registra como fallo para no simular un heartbeat correcto. La resolución de
identidad sigue bloqueando apropiaciones ambiguas; no se relajó esa protección.

## Vinculación automática de proyectos · 0.4

Pedido autorizado: convertir la vinculación puntual de Meximova en una función del
producto, sin registrar manualmente cada proyecto ni copiar memorias.

Implementado:
- Descubrimiento desde cwd, raíces de IDE, Git/worktrees, marcadores y ubicaciones
  conocidas; aislamiento de espacios con varias raíces sin selección inequívoca.
- UUID local por workspace, marcador en metadatos Git o .synopsis fuera de Git,
  registro privado para carpetas de solo lectura y persistencia entre clientes.
- Adopción de memorias anteriores mediante metadatos cwd del cliente, con lectura
  acotada. El nombre codificado de la carpeta sigue sin acreditar propietario.
- Reubicación con conservación de notas/revisiones y actualización de los turnos;
  intención recuperable y rechazo de diarios simbólicos. Las copias son independientes.
- Worktrees asociados por directorio Git común, con almacenes y checkpoints separados.
  Decisión de alcance: no se mezcla conocimiento de ramas automáticamente; una
  biblioteca compartida de hechos entre ramas no forma parte de esta implementación.
- Solicitudes durables de vinculación y elección por mapa autenticado; destinos
  candidatos cerrados, protección de origen, tamaño y solicitudes obsoletas.
- Índices con nombre de proyecto y ruta cuando hay homónimos; agrupación por
  propietario verificado. El mapa detecta registros nuevos y actualiza sus fuentes.
- Diagnóstico de vinculaciones pendientes e instalación que explica el primer uso.
  El plugin declara contexto automático activo por defecto; se respeta desactivarlo.

La versión anterior pasó 196 pruebas propias y 767/767 integrales (46,4 s), después
de corregir una incompatibilidad de respuestas POST para direcciones que no admiten
acciones. Se agregó una última regresión de registros ajenos corruptos; su validación
final se registrará al aplicar la rama. El índice del mapa también se probó después
de elegir memoria, sin reiniciar el proceso de búsqueda.

Contrato detallado y límites: docs/project_binding.md. Sin sincronización entre
máquinas, sin garantía de detectar una raíz sin pistas y sin ampliar el contrato de
inyección por prompt de Cursor. Todo el desarrollo/pruebas previo a la aplicación
usa proyectos temporales. No hay commit ni push.

Cierre de la implementación 0.4:
- 197/197 pruebas propias desde el checkout final (11,800 s).
- 767/767 comprobaciones integrales desde el checkout final (44,6 s).
  Única omisión: PowerShell de Windows no disponible en Linux.
- Veinte regresiones de workspace y dos de HTTP/interfaz añadidas. Incluyen cinco
  bridges reales como procesos, raíz/subcarpeta, metadatos de migración, elección
  autenticada, solicitudes obsoletas, reubicaciones recuperables, copias, concurrencia,
  worktrees, carpetas de solo lectura y registros ajenos corruptos.
- La elección HTTP actualiza las fuentes de búsqueda del proceso del mapa; los
  registros nuevos forman parte de su huella y disparan regeneración.
- Validación real de Meximova: memoria existente reutilizada desde raíz y app,
  UUID único persistente y huellas de las doce notas Markdown intactas.
- Servicio local synopsis-mapa reiniciado sobre la versión 0.4. Sin reinstalar los
  clientes, sin commit, push ni publicación de la rama en GitHub.
- La UI se verificó por contrato de DOM/clic y HTTP real sobre fixtures; no se
  contabiliza como una validación visual interactiva en todos los IDE.

## Recordatorio que ignoraba revisiones · 0.4.1

Reproducción: hook_guardar.py solo consultaba eventos de archivos/notas y desconocía
los cierres del diario MemoryCycle. Por eso una charla revisada con no_change aún
podía recibir el aviso de 22 archivos sin memoria. Además, contaba ediciones de
otros repositorios realizadas desde la misma charla.

Corrección: last_review consulta SQLite en modo ro con proyecto y hash de sesión
completa. saved y no_change fijan un corte para el contador. Los archivos posteriores
siguen contando; el texto dice revisión cuando no puede afirmar una escritura.
Se filtran rutas fuera del proyecto. Los turnos pendientes no se cierran ni se
ocultan por esta consulta. La heurística antigua se conserva cuando no hay diario.

Siete regresiones añadidas: ausencia de DB sin creación, lectura sin cambios,
no_change y saved, aislamiento de sesiones/proyectos, pendientes, archivos nuevos
frente a antiguos/ajenos y hook real usando el diario y eventos de un fixture.

Respuesta a la duda del usuario: el guardado nativo sigue siendo cooperativo. La
propuesta de conocimiento depende del modelo principal; no hay un revisor autónomo
por turno que interprete y guarde conversaciones independientemente de ese modelo.
Esta limitación se documenta; no se presenta el recordatorio como autoguardado.

Validación del cambio de recordatorios: 204/204 pruebas propias (11,606 s) y
767/767 integrales (42,6 s) aprobadas desde staging; PowerShell de Windows omitido.
La corrección no añade un extractor de memoria ni cambia el contrato de admisión.


## 2026-10-16 · Revisor independiente 0.5.0

Petición: que Synopsis escriba sin depender de la iniciativa del modelo principal;
mostrar el funcionamiento mediante un diagrama. Se implementa auto_review.py con
cola privada por proyecto, inferencia separada al Stop, lease/candado, límites de
entrada y expiración, origen de proveedor acotado y estados de fallo visibles.
Los cinco adaptadores identifican el cliente; OpenCode entrega texto del asistente
sin herramientas. Nuevos comandos reviews/retry y diagnóstico de activación.

Se reutiliza EvidenceLedger y la persistencia versionada. Las admisiones se conservan
y revalidan también en ciclos nativos sin rebajar la política estricta existente.
No se permite que una respuesta del asistente sea soporte de su propio guardado.
Las actualizaciones solo preservan y añaden pasajes; reemplazos dudosos y notas
heredadas sin admisión requieren conciliación. Un cierre explícito previo del modelo
principal se respeta; no se reabre. Recuperación automática al próximo evento, sin
promesa de un daemon periódico. Contrato, privacidad y diagrama en continuity.md.

Prueba real con Codex autenticado en fixture temporal: 8,07 s; guardado inferred
con un recibo y una revisión de la decisión del usuario de 47 días. Se rechazó como
soporte la afirmación no verificada del asistente de 999 días. No se modificó la
memoria real de Meximova. Es un caso real, no una medida estadística de calidad.

Las pruebas de cinco bridges usan un proveedor simulado con procesos independientes;
no equivalen a validación interactiva de todos los IDE ni de sus cuentas. No se
verificó inferencia real de Claude/OpenCode/Cursor/Antigravity ni Windows en este cambio.


Validación final 0.5.0: 227 pruebas unitarias (15,46 s) y 767/767
comprobaciones del motor (48,7 s). Los 23 casos nuevos incluyen cinco bridges en
procesos separados, proveedor ficticio, guardado sin herramienta del modelo
principal, append con revisión esperada, duplicados, secretos, expiración,
concurrencia y recuperación de recibos tras agotar intentos. Contrato Node de
OpenCode comprueba que solo entrega texto assistant del turno y excluye tools.
La batería general desactiva inferencia automática real; los casos del revisor
la activan con proveedor aislado. La prueba real de Codex se ejecutó aparte.


## 2026-10-16 · Experiencias con alcance y comprobaciones (0.6.0)

Petición: llevar a código el circuito de experiencias situadas, motivos, resultados,
límites y reutilización entre asistentes; completar las prioridades de la auditoría.

Se implementó experience_engine.py con SQLite versionado por proyecto, observaciones
JSON/texto, condiciones, contraejemplos, sustituciones explícitas sin ciclos, deriva de
fuentes y feedback idempotente por versión. experience_runner.py reejecuta casos Python
existentes en una copia filtrada y un namespace bubblewrap sin red/credenciales, con
límites; unavailable conserva una distinción honesta cuando falta esa capacidad.

La revisión automática incorpora rutas/huellas de PostToolUse, evidencia del controlador,
experiencias pertinentes y una reparación estructural acotada. No captura comandos ni
salida cruda. Los relatos siguen inferred; no se fabrican observaciones de ejecución.
Se conectó recuperación en prompt/pretool, CLI experience/learn, MCP experiencias
(15 herramientas), panel autenticado del mapa y mantenimiento periódico junto al mapa.

Se repararon la pérdida tras tres fallos recuperables, el inventario alfabético y el
bypass de revisión tras un no_change del modelo principal. Los turnos cerrados conservan
su resultado y reciben una revisión estricta enlazada. Las inferencias fallidas siguen
limitadas; el reintento explícito no prolonga la retención de 24 horas.

Prueba real Codex: 17,10 s para captura y segunda inferencia sobre una experiencia
ficticia de 19 horas. Retuvo la limitación de no haber probado recuperación real,
ignorando el reclamo falso del asistente. Cambiar policy.json produjo stale.
Prueba real Linux del ejecutor: aislamiento de HOME y variable privada; un caso
aprobado produjo observed_support y un control negativo contradicted. Ambos casos
son acotados, sin atribuir mejora general ni primacía frente a otros productos.

Se añadió tools/evaluate_experiences.py para reproducir el circuito con fixture y,
opcionalmente, proveedor real. Contrato y límites: docs/experiences.md.


Validación de cierre 0.6.0: **260 pruebas unitarias** (16,308 s),
**767/767 comprobaciones del motor** (44,9 s), **15 herramientas MCP**.
Contratos: 26 casos del motor de experiencias, 29 del revisor (incluyendo una
reparación de formato), HTTP autenticado y DOM del panel con contenido no confiable.
La evaluación publicada tools/evaluate_experiences.py --live --provider codex pasó
por separado en 19,93 s: captura, recuperación, decisión limitada al respaldo,
abstención por ruta y detección de evidencia cambiada. Sin comparativa de calidad
entre productos o modelos. Windows PowerShell no disponible en este entorno.

## Entrega 0.7.0: RAG de decisiones

El usuario autorizó implementar el diseño de recuperación de experiencias opuestas,
comprobación de límites, adquisición de evidencia pendiente y aprendizaje por resultado.

- [x] Campo decision opcional y compatible con registros previos; no se promocionan
  experiencias antiguas a decisiones automáticamente.
- [x] Núcleo decision_rag: grupos de alternativas, contexto actual, soporte por hash,
  abstención explícita, presupuesto sin ocultar competidores y recibos verificables.
- [x] Priorización de observaciones discriminantes; ejecución opt-in de pruebas ya
  existentes, acotada y aislada. Huella común de copia/revalidación en experiment_snapshot.
- [x] Feedback ligado a plan, contexto y revisión; recuperación idempotente entre sus
  escrituras. Reportes harmful suspenden la selección hasta una revisión conciliada.
- [x] Integración en prompt/pretool, revisor, MCP, CLI, modo controlado, skill y mapa.
- [x] Lectura SQL de versiones vigentes sin cargar todo el historial al recuperar.
- [x] Contratos, evaluador comparativo, documentación y diagrama de flujo.

Validación: 296 pruebas unitarias (16,548 s), incluidas 36 del nuevo circuito.
18/18 escenarios sintéticos; dos pruebas Linux aisladas y un control negativo.
Codex real, 45 inferencias en 291,35 s: nuevo RAG 15/15, un caso recuperado 12/15,
contexto de Synopsis anterior 11/15. Los desaciertos de los controles fueron abstenciones.
Los brazos reciben observaciones actuales iguales y un tope de contexto común;
no se midieron tokens/facturación. Las pruebas no son un benchmark de programación real.

Se reforzó el ejecutor con límites de procesos/archivo/espacio temporal, capabilities
retiradas y namespaces adicionales deshabilitados. La prueba real comprobó esas
restricciones, exclusión de HOME/variable privada y el resultado del control negativo.
Sintaxis: 140 archivos Python y cuatro scripts del mapa; sin errores de whitespace.
El contrato y sus límites están en docs/decision_rag.md; resultados de fixtures en
un único docs/decision_evaluation.json. Sin commit, push ni PR.

Límite de investigación: aún no se ha demostrado mejora sostenida en repositorios
reales, causalidad de los relatos, novedad mundial ni obediencia universal del LLM.
La inferencia de límites la propone el revisor; el núcleo solo comprueba observaciones
admitidas y no inventa reglas a partir de un resultado. No hay entrenamiento de pesos.

Verificación integral final desde la rama: 767/767 comprobaciones del motor/mapa
(45,3 s). PowerShell de Windows permanece sin ejecutar en esta máquina Linux.
La instalación enlazada reconoce Synopsis 0.7.0 y doctor devuelve ready=true,
15 herramientas y cero vinculaciones pendientes. El mapa local se reinició para
cargar la versión nueva; los clientes MCP ya abiertos requieren recargar su sesión.

## Trabajo 0.8: recuperación híbrida y aprendizaje con límites

En curso, autorizado por el usuario tras la comparación. El núcleo 0.7 se conservó
sin modificaciones durante la auditoría; esta implementación ocurre después.

Plan y estado:
- [x] Congelar capturas reales de la auditoría y reproducir el fallo dinámico antes del cambio.
- [x] BM25, anclajes técnicos y fusión recíproca con embeddings reales por proyecto.
- [x] Semántica local multilingüe mediante ONNX en venv privado; preparación automática
  de instalación, autenticación local y sin envío a proveedores de inferencia externos.
- [x] Separar guardas dinámicas de soporte estable y eliminar evaluaciones duplicadas.
- [x] Actualizaciones automáticas con revisión visible, sin ampliar alcance ni quitar
  límites, contraejemplos o evidencia; daño reportado exige conciliación.
- [x] Priorización de observaciones por particiones de alternativas.
- [x] Laboratorio de sensibilidad: intervenciones JSON acotadas en copias aisladas,
  sin modificar el checkout ni generar comandos/código arbitrario.
- [x] Evaluación real de captura posterior al cambio y casos de programación.
- [x] Pruebas integrales, documentación, sincronización y paquete con instalación limpia verificada.

Regresión reproducida con capturas intactas: 15/15 estados correctos incluso en modo
léxico mejorado. No es evidencia independiente nueva ni superioridad entre productos.
Modelo local real: seis pares traducción/negativo, tres consultas de idiomas y un
negativo; dos experimentos aislados distinguen test sensible de test que siempre pasa.
La evaluación de productividad y una superioridad global siguen sin estar demostradas.


Checkpoint 0.8 antes del cierre: 323 pruebas unitarias aprobadas y 767/767
comprobaciones del motor/mapa. La prueba inicial de programación consultaba solo
DecisionRAG y perdió las políticas guardadas como notas (0/3). Al consultar los
tres canales del hook recuperó 1/3: el revisor omitía dos políticas complementarias.
Se ajustó la presentación de notas con admisión y la instrucción de conservar
valores de contextos distintos; la nueva evaluación sigue en curso. No atribuir
3/3 al resultado incompleto. El primer piloto congelado dio 5/6 con Synopsis,
5/6 sin memoria y 6/6 con historial completo; el caso Unicode negativo mantiene
la abstención del LLM pese al caso recuperado. No se modificó su respuesta esperada.
La regresión de capturas anteriores pasa 15/15 incluso sin embeddings.


Cierre 0.8: el revisor con notas ya atestadas conservó las seis políticas en tres
proyectos. Synopsis e historial completo pasaron 3/3 tareas de código con pruebas
ocultas; sin memoria se abstuvo en 3/3. Dos variantes posteriores al congelado dieron
2/2 para ambos brazos con memoria y abstención en 2/2 sin ella. El piloto final de
QA mantuvo 5/6, frente a 5/6 sin memoria y 6/6 con historial completo: no demuestra
ventaja competitiva. Se recuperaron 12/12 grupos y seis selecciones resolubles.
Detalles, limitaciones y ensayos fallidos: [evaluación 0.8](upgrade_evaluation.md).
Instalación local actualizada, runtime listo, 15 herramientas y doctor ready=true.
El mapa fue reiniciado y rechazó HTTP sin clave; acceso autenticado 200.
Los clientes MCP abiertos requieren recargar sesión. No se crearon commits ni PR.

Paquete 0.8 verificado: hashes del manifiesto, instalación limpia en HOME temporal
sin red semántica, cinco clientes configurados, 15 herramientas y lanzador 0.8.0.
El setup real del modelo se validó por separado en la cuenta local. La entrega no
contiene el nombre anterior ni runtime, credenciales o datos de usuario.


## Trabajo 0.9: memoria que investiga y conserva vigencia

Autorizado tras comparar Mem0, Graphiti y ShadowFrog. Integración original de ideas,
sin copiar implementaciones ni ejecutar flujos ajenos que publiquen commits.
Plan: 1) estados temporales explícitos y retiro sin borrar historia; 2) paquete
unificado, compacto y diverso para los hooks; 3) descubrimiento de tests Python y
propuestas de código evaluadas contra baseline en snapshots; 4) panel de vigencia
y experimentos; 5) ablaciones que separen notas, experiencias y experimentos.
Los experimentos no modificarán el checkout ni certificarán relatos como hechos.
La inferencia nativa reutilizará proveedores existentes y tendrá presupuesto acotado.


Checkpoint 0.9 implementado en /tmp/synopsis-v09: experience_timeline.py agrega
vigencia, retiros y activación con revisiones; task_context.py unifica contextos y
recupera experimentos como pistas históricas; research_workbench.py descubre tests
por AST y genera funciones con filtro de alcance, compara original y candidatos en
bwrap, guarda contexto/antecedentes y nunca modifica el checkout. Panel Memoria viva
renderizado con Chrome y datos sintéticos en /tmp/synopsis-v09-panel.png.
Pruebas: 340 unitarias aprobadas antes del último caso de conservación de expiración;
18 contratos nuevos pasan. Evaluación real final: 6 llamadas gpt-6.1-sol, dos casos
con experiencias (un grupo y dos alternativas por caso), 2/2 frente a historial2/2;
sin experiencias se abstuvo2/2. Dos negativos detectan regresión. Brazos aislados y
ningún antecedente cruzado. Fixtures de experiencia escritos a mano; no prueba de
adquisición autónoma ni de superioridad OSS. Falta sincronizar, validar instalación,
terminar documentos/recibos y paquete 0.9.


Cierre de implementación 0.9: 341 pruebas unitarias aprobadas. Aplicados 24 archivos
iniciales de la iteración, sin modificar cambios concurrentes. Instalación actualizada,
mapa reiniciado y autenticación HTTP verificada (sin clave rechazado; con clave200).
Doctor ready=true con 15 herramientas; semántica local instalada. Panel comprobado
con Chrome y datos sintéticos, sin exponer notas privadas. Se completan pruebas del
paquete de entrega en HOME temporal; las limitaciones de alcance y pruebas se describen
en [investigación 0.9](research_workbench.md). Sin commits, push ni PR.


## Objetivo activo después de 0.9

El usuario pide continuar hasta demostrar resultados mejores frente a los proyectos
comparados. Objetivo persistente activo; no declarar superioridad sin comparación
homogénea. 0.9 está aplicada y su ZIP pasó instalación limpia (323 archivos, cinco
clientes,15 herramientas). 341 unitarias y767/767 humo; doctorready yHTTP200conclave.
Siguiente dirección desde principios: memoria de comportamiento portable, con
pruebas de datos y oráculo fuera del proceso no confiable, para detectar regresiones
aunque el test original ya no exista. La experiencia observada no se convertirá en
verdad normativa automáticamente. Preparar protocolo y corpus reservado ANTES de
implementar, comparar SDKs reales, memoria de ShadowFrog bajo flujo compatible sin
commits/push, y controles rawnotes/fullhistory. No mezclar ese perfil con Dream completo.
Incluir perfiles competentes y coste de captura, no solo preguntas finales.
