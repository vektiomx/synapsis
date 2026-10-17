# Cambios

Las versiones siguen el número de `.claude-plugin/plugin.json` (`claude plugin list` lo muestra, y Claude lo ve con `synopsis --version`). Cada versión que
sale sube ese número; si no, la actualización puede no traer nada (ver [CONTRIBUTING.md](CONTRIBUTING.md)).

## 0.11.0 — adaptación de escritorio en desarrollo

- Instalación desde fuentes para macOS/Windows con accesos dedicados y comando
  Windows sin symlinks; conserva el PATH del usuario y configuraciones ajenas.
- Apertura del mapa en Windows sin /bin/sh; hooks PowerShell con JSON UTF-8,
  argumentos absolutos y soporte de rutas con espacios/apóstrofes.
- LaunchAgent de usuario en macOS y arranque HKCU Run en Windows; retiro del
  arranque sin borrar memorias. Entrypoint persistente independiente del interactivo.
- La entrada de escritorio prepara la clave privada aun sin abrir un navegador.
- Diagnóstico de capacidades por plataforma y matriz CI nativa preparada.
- Pendientes runtime embebido, paquetes firmados y validación nativa de escritorio;
  los experimentos aislados siguen requiriendo Linux/bwrap.

## 0.10.0 — rama de desarrollo

- Testigos JSON de comportamiento: captura de assertEqual literales confirmados
  mediante observación aislada, con firma, procedencia y alcance versionado.
- Reproducción de casos conservados aunque se borre el test original; retiro con
  secuencia esperada y suspensión por cambio de firma, guardas o contrato explícito.
- Banco original/candidato con tests actuales y testigos históricos, sin aplicar
  prototipos al checkout ni aceptar controles omitidos como una mejora comprobada.
- Pistas automáticas por prompt y antes de editar; inspección CLI/MCP y panel del mapa.
- Comparación real fijada con Mem0 inferred/raw, Graphiti y perfil de memoria
  ShadowFrog; empates de precisión y costes de captura publicados con sus límites.

## 0.9.0 — rama de desarrollo

- Contexto unificado con diversificación de notas y grupos de decisiones indivisibles.
- Intervalos de vigencia, retiro/activación versionados y trazabilidad sin borrar historia.
- Descubrimiento de unittest por AST y propuestas acotadas de funciones Python.
- Comparación original/candidato con controles fijados, aislamiento y detección de drift.
- Investigación persistente, antecedentes para nuevas propuestas y pistas en cada prompt.
- Panel Memoria viva con evidencia, estados, línea de cambios y resultados experimentales.

## 0.8.0 — rama de desarrollo

- Recuperación de experiencias por BM25, anclajes y embeddings multilingües locales;
  preparación automática del runtime privado durante instalación, con modo sin red.
- Guardas dinámicas deduplicadas y soporte independiente ligado a hashes.
- Actualización automática con revisión esperada y conservación de límites.
- Priorización de observaciones por particiones de alternativas.
- Laboratorio de sensibilidad de tests existentes con intervenciones JSON aisladas.
- Evaluaciones reproducibles de capturas congeladas, semántica y programación sintética.

## 0.4.1 — rama de desarrollo

- El recordatorio por archivos consulta cierres saved/no_change de su proyecto y
  sesión: no vuelve a pedir guardar cambios ya revisados.
- Los cambios posteriores siguen contando, con un texto que distingue revisión
  de escritura. Las ediciones de otro proyecto no inflan el contador de la charla.
- Consulta del cierre en SQLite de solo lectura; no crea memorias ni da por
  resueltos turnos abiertos o conflictos.

## 0.4.0 — rama de desarrollo

- Vinculación de proyectos al primer uso desde los cinco conectores y CLI/MCP.
- Registro de workspace con identidad local persistente, descubrimiento de raíces,
  reubicación recuperable y aislamiento de copias y worktrees.
- Adopción de memoria anterior mediante metadatos cwd del cliente; los casos
  ambiguos se eligen desde el mapa autenticado, sin comandos de reparación.
- Índices de memoria con el nombre de su proyecto y agrupación por propietario.
- Corrección de enlaces válidos fuera del grafo y diagnóstico de identidad explícito.

## 0.3.0 — rama de desarrollo

- Modo controlado synopsis.run.v2: respuesta factual extractiva construida por el
  controlador, citas revalidadas y abstención; el borrador libre no se publica.
- Admisión durable de memoria por párrafos literales completos; metadatos del modelo
  no añaden afirmaciones. Los ciclos estrictos no admiten operaciones sin evidencia.
- Cuarentena para recuerdos sin admisión comprobada, sin borrar archivos anteriores.
- Herramientas acotadas de archivos, JSON y cálculo; CLI verify y MCP
  responder_con_evidencia. Protección de rutas, fuentes cambiadas y contenido sensible.
- Shell, colaboración y búsqueda desactivados en el conector de inferencia Codex.
- Evaluación adversarial de proceso y continuidad con modelo real. La fidelidad a
  una fuente no demuestra verdad externa ni garantiza comprensión de toda pregunta.

## 0.1.4 — en prueba

Para ordenar la memoria cuando crece:

- `--partir NOTA` y `--renombrar NOTA NUEVO`: para la nota que ya no entra en una lectura y para cambiarle el nombre a
  una sin dejar enlaces rotos. Muestran primero el plan y lo hacen recién con el código de ese plan (`--confirmar`);
  antes copian las notas como estaban a `respaldos/` y comprueban que no se pierda un renglón.
- `partir_sola` en el `config.json` (viene apagado): la pasada de cada día parte sola las memorias que están por
  llenarse, con ese mismo cuidado, lo anota en `respaldos/partidas.log` y se lo avisa a Claude. `--por-partir` dice qué
  haría y `--partir-llenas` lo hace en el momento. El médico avisa antes con la regla nueva «casi llena».
- Las notas de archivo se reconocen también por su descripción («(archivo) …»), no solo por el título del índice, y
  pesan apenas menos que las vigentes (0,95 en vez de 0,85), porque muchas guardan datos que siguen valiendo. El médico
  deja «para revisar» la que parece de archivo y no lo dice.
- Una memoria que el índice nombra en un renglón junto con otras («Historias: [1](…); [2](…)») toma el proyecto de su
  sección. Antes quedaba sin proyecto y la pista la ofrecía en chats de otro.
- [docs/obsidian.md](docs/obsidian.md): cómo abrir la memoria en Obsidian sin que los dos se pisen.

Para ver qué hay y qué falta:

- El mapa se puede pintar por proyecto: el botón «Grupos / Proyectos», la lista «Proyectos» y la ficha de cada nota.
  Cada proyecto puede llevar `nombre` y `color` en el `config.json`.
- `--pendientes`: junta lo que las memorias dicen que falta (probar, decidir, commit, hacer), con su nota, su renglón y
  su fecha. Solo lee.
- `--reglas` y `--regla NOTA`: proponen qué memorias convienen como regla por carpeta de Claude Code (`.claude/rules/`
  con `paths:`), que se carga sola al tocar un archivo de esa carpeta. `--recetas` y `--receta NOTA:N` hacen lo mismo
  con los tramos «Cómo se hace…», que pueden ser skills. Escriben recién con `--confirmar` y no pisan lo que no
  escribieron. El registro anota cuándo Claude Code carga una de esas reglas (su ruta, nunca su texto), y `--reglas`
  dice cuántas veces cargó cada una.

Para saber qué cambió:

- `--sobre "tema" --al 6/10` (y `--buscar`): responde con la memoria como estaba ese día, sacada del historial.
- `--cambios NOTA`: qué dato de una nota cambió y cuándo: qué decía antes y qué pasó a decir, sin contar lo que solo se
  mudó tal cual a otra nota. Sin nota, qué notas cambiaron en los últimos días.
- `--sobre`, por la consola, avisa debajo de lo que manda a leer si el renglón citado cambió y qué decía antes.

Arreglos:

- El médico ya no toma por commits las huellas de archivos de una lista («SHA OK (motor `…`, lanzador `…`)»).
- Lo aprendido del uso no guarda ni sugiere archivos temporales (`.tmp` o `.temp` en el nombre, `~$`, `.swp`).

## 0.1.3 — en prueba

- En Mac y Linux, el médico no encontraba el archivo de una cita con carpeta (`app/models/cosa.py:564`) cuando ese
  nombre de archivo existe en más de una carpeta: la daba «sin un archivo de código con ese nombre», y dar la carpeta
  dejaba peor que no darla. Ahora la carpeta elige el archivo justo, como en Windows. Lo reportó jroberto1386 en el
  [issue #1](https://github.com/vektiomx/synapsis/issues/1), con la causa y cómo reproducirlo.

## 0.1.2 — en prueba

- En Windows con Python 3.10 a 3.12, lo aprendido a veces se volvía a repasar enseguida y el índice de búsqueda se
  podía rearmar dos veces seguidas: el reloj de esas versiones va a saltos y una marca recién puesta parecía estar
  unos milisegundos en el futuro. Ahora se acepta esa diferencia, y un reloj atrasado de verdad sigue sin trabar nada.
- Las pruebas de GitHub también corren solas cada lunes y con el botón «Run workflow».

## 0.1.1 — en prueba

- El mapa arranca sin preguntarle a la red el nombre de la computadora, que no usaba. En algunas Mac esa pregunta
  hacía esperar unos 35 segundos cada vez que se abría el mapa.
- Las pruebas automáticas de GitHub: Chrome tiene de nuevo 3 minutos para abrir la página. Si en una máquina de
  GitHub se cuelga igual, esa prueba se saltea con el motivo; en una computadora común sigue siendo una prueba. Además,
  el arranque doble tiene más tiempo en máquinas lentas, cada prueba se ve con su hora y todo se corta a los 30 minutos.

## 0.1.0 — en prueba

Primera versión, para los primeros probadores.

- El mapa en vivo: la memoria de Claude Code y tus `CLAUDE.md` como un cerebro 3D, con lo que hacen los chats y los
  agentes en este momento, la lista, el panel de salud y la copia «Sin notas» para mostrarlo sin enseñar nada. Con
  500 notas o más, la lista dibuja solo las filas que se ven, así abre y reordena al instante. Abajo, el río del tiempo:
  los últimos 10 minutos, una línea por chat, con lo que hizo, tus mensajes, sus agentes y la espera de tu OK.
- El médico (`/synopsis:salud`): rutas y enlaces que ya no existen, anclas `archivo:línea` corridas, commits que no
  existen, problemas anotados que un commit posterior parece haber resuelto, cifras viejas cargadas en `hechos.json`,
  memorias sin índice, repetidas o que copian el `CLAUDE.md`, y un `MEMORY.md` que pasa lo que Claude lee al arrancar
  (200 líneas o 25 KB, lo que llegue antes). Un «para revisar» ya comprobado se calla con `--descartar-aviso` y vuelve
  solo si ese renglón cambia.
- Historial de la memoria (`--historial`): cada vez que la memoria cambia, al terminar una respuesta, guarda una
  versión con git en la carpeta de datos, sin tocar la carpeta de la memoria. Si un chat (o el ordenado automático de
  Claude Code) borra algo, `--historial "texto"` dice cuándo se borró y qué decía.
- Buscar en las charlas viejas (`--charlas "palabras"`): lo que se habló con Claude y nunca se anotó. Busca en el
  momento en lo que escribiste vos y lo que respondió Claude (nunca en lo que devolvieron las herramientas), sin
  guardar copia, y tapa lo que parece una clave. Si un pedido nombra algo dicho antes («lo que te dije», «como
  quedamos») y la memoria no tiene nada seguro, la pista sugiere buscar ahí y en el historial.
- El buscador (`/synopsis:sobre`): qué se sabe de un tema, qué leer primero, las decisiones anotadas que lo tocan y
  el código que esas notas citan para comprobarlo (con la línea y la función, aunque la nota no ponga la línea, si
  escribe al lado con qué buscarla), en español y en inglés, con los datos viejos marcados. En las notas largas sin
  títulos busca por pasajes, así un dato del medio no se pierde entre el resto. Una nota con un dato viejo comprobado
  (una ruta que ya no existe, una cifra o un commit) pasa detrás de las limpias, con su ⚠.
- Revisar al guardar: si Claude corrige un dato en una nota («92 de 111» → «93 de 111») y otra nota todavía dice el de
  antes, se lo avisa en el momento, con la nota y la línea.
- Dormir: una vez por día, con el primer pedido, repasa las notas de fondo y propone arreglos (líneas de código
  corridas, cifras viejas), sin tocarlas; Claude te avisa una vez y se aplican solo los que apruebes
  (`--propuestas`, `--aplicar`, `--descartar`). Con `dormir_con_claude` (apagado de fábrica, con tope de gasto por
  día) también le pregunta a Claude si lo que parece resuelto lo está de verdad, con una línea del código de hoy como
  prueba, y qué notas se contradicen.
- Fichas (`--fichas USD`, con tope de gasto): Claude arma una ficha por nota con otras formas de nombrar lo que dice y
  las preguntas que responde, así el buscador la encuentra aunque la busques con otras palabras. Solo se rehacen las
  de las notas que cambian; nunca toca las notas.
- Por qué eligió cada nota: los rayos de la pista salen de un color según el motivo (las palabras del pedido, un índice
  que la nombra o lo aprendido), la fila de «Ahora» lo resume y el panel de la nota dice por qué y en qué renglones.
  El registro guarda solo el motivo, los números de renglón y las rutas, nunca el texto del pedido.
- Modo de comparación (`comparar_aprendido`, apagado de fábrica): una parte de los pedidos va sin lo aprendido y
  `--aprendido` compara cuántas pistas sirvieron con y sin, para saber si aprender del uso ayuda de verdad.
- La primera vez que se abre Claude Code después de instalarlo, avisa que quedó instalado y cómo abrir el mapa.
- Aprende del uso, en tu computadora: qué archivos se abren juntos (se refuerza con la repetición y se olvida a la mitad
  cada 14 días) y si las notas que recomendó se leyeron. Con eso la pista suma código y notas, y el mapa engrosa las
  conexiones que más se usan (los pulsos corren más rápido por ellas, saltando de cuenta en cuenta), muestra las
  conexiones «Aprendida» y el bloque «Lo que aprendió», que se ve aprender en vivo: el camino que recorre un chat se
  ilumina y los caminos nacen, se engrosan y se apagan sin recargar la página. Lee una vez las charlas guardadas
  de antes (solo rutas) y las usa de respaldo. No sugiere código de un proyecto donde ese chat casi nunca trabaja, ni a
  partir de un `CLAUDE.md` o un `MEMORY.md`, y lo que la pista misma sugirió cuenta la mitad, para que no se refuerce
  solo. De los agentes no une notas con notas, y no aprende acciones que fallaron ni archivos de librerías o
  generados. `--aprendido` lo cuenta (con un archivo, con qué se usa ese), `--olvidar` borra una unión o todo lo de
  un archivo sin que vuelva al rearmar, y `"aprender": false` lo apaga.
- Avisos automáticos a Claude: memoria parecida a otra, dos chats editando el mismo archivo, rutas y enlaces rotos al
  escribirlos y problemas nuevos en tus notas. Con el contexto automático prendido, al editar un archivo de código le
  recuerda la nota que se suele leer con él (de lo aprendido), una vez por archivo y por chat, si todavía no la leyó.
  Y le recuerda guardar: al volver de compactar, que pase a la memoria lo decidido que todavía no esté escrito (si no,
  se pierde en la próxima compactación); al terminar una respuesta, si cambió 5 archivos o hizo un commit sin escribir
  nada en sus notas, una vez cada 15 minutos como mucho. El mapa lo muestra como «guardar».
- `--choques`, `--gasto` y el freno de agentes, `--lecciones`, `--aprendido`, `--proponer-hechos`, `--entidad`, `--mapa`.
- Un conector opcional para el modo Chat de la app de escritorio de Claude (`conector_mcp.py`, se registra a mano en
  `claude_desktop_config.json`): esas charlas pueden consultar y leer tus notas, en solo lectura, y se ven en el mapa
  como «Chat de la app»; nunca guarda lo que se preguntó.
- Anda con Git Bash y con PowerShell, en Windows y en Linux; sin internet (d3 y marked vienen adentro). Con 10.000
  notas, el mapa se arma en ~20 s; sin el mapa abierto, la pista no se traba armando el índice (lo arma de fondo).
- Seguridad: lo que guarda en la carpeta de datos son solo datos (el índice de búsqueda va en JSON, no en un formato
  que pueda correr código al cargarse); las carpetas que crea nacen cerradas para tu cuenta y `--salud` avisa si otra
  cuenta de la PC puede escribir en la carpeta de datos o en la del programa. El hook no le manda la clave al mapa: el
  mapa primero demuestra que la sabe y el pedido va firmado. El navegador entra con un número de un solo uso y queda
  con una galleta propia: la clave no queda en el historial ni en la galleta.


## 0.5.0 — Revisión automática independiente

- Cola privada por proyecto y revisor al cierre nativo, independiente de las llamadas
  de memoria del modelo principal; respeta turnos ya cerrados con recibo.
- Evidencia literal, actualizaciones conservadoras, historial y recibos; conflictos
  abiertos en vez de reemplazos inciertos. No admite afirmaciones del asistente.
- Proveedor del mismo cliente o generación local de Ollama; pendientes explícitos
  cuando no hay acceso. Diagnóstico y comando synopsis reviews.
- Entradas temporales limitadas, rechazo de secretos reconocibles, expiración y
  recuperación de operaciones tras interrupción. Flujo documentado en continuity.md.


## 0.6.0 — Experiencias situadas

- Situación, acción, motivo, resultado reportado, condiciones, evidencia, límites y contraejemplos.
- Versiones, observaciones JSON/texto, detección de fuentes cambiadas y feedback por revisión.
- Reejecución opcional de unittest Python bajo aislamiento Linux; no ejecución por MCP.
- Captura automática acotada, recuperación por tarea/ruta, CLI experience, MCP experiencias y panel.
- Recuperación periódica junto al mapa; reintentos recuperables sin perder entrada antes de vencer.
- Revisión independiente de cierres previos y contexto ordenado por relevancia.

## 0.7.0 — RAG de decisiones con límites observables

- Recuperación de alternativas por problema, incluidos casos de resultado opuesto.
- Requisitos actuales separados de soporte ligado al contenido; abstención por
  conflicto, dato ausente, evidencia cambiada, presupuesto o exceso de alternativas.
- Selección de observaciones discriminantes y reproducción explícita de pruebas
  existentes con presupuesto de ejecución y comprobación de deriva de la copia.
- Recibos de decisión y utilidad reportada ligada a contexto/revisión; una revisión
  señalada como dañina queda suspendida hasta conciliación.
- Integración en hooks, revisor automático, MCP, CLI, modo controlado y panel.
- Evaluador sintético con controles transparentes, ablaciones y modo de proveedor real.
