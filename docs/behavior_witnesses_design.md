# Memoria de comportamiento · estado vigente 0.10

Implementación local completa de esta iteración en `feat/reliable-project-memory`.
Se edita directamente /var/www/html/projects/synopsis, nunca sincronizar el staging
antiguo /tmp/synopsis-v09. No commits, push ni PR.

Implementado: captura observada de assertEqual literales, firma/procedencia/alcance,
reproducción tras borrar el test, retiro CAS, suspensión por cambios de contrato,
integración original/candidato, pistas de prompt/edición, CLI/MCP y panel del mapa.
Los tests cubren reparaciones históricas, regresiones nuevas, scopes y guardas,
aserciones nuevas opuestas, historia ajena que supera el límite y ausencia de
ejecución por MCP/contexto. No es un observador resistente a todo Python malicioso.

Validación: 357 pruebas propias aprobadas; humo 767/767 (sin PowerShell Windows).
Instalación limpia del paquete: cinco clientes, 15 herramientas, doctor ready,
launcher Synopsis 0.10.0. La prueba de adaptadores sin red desactiva explícitamente
la instalación semántica; el runtime semántico existente sigue disponible.

Comparación real terminada, corpus/protocolo fijados y todos los intentos conservados:
en reservado, todos los perfiles con memoria 8/8; sin memoria 4/8 por abstención.
Captura LLM: Synopsis0, Mem0 inferred8/raw0, Graphiti25, ShadowFrog4. Ocho llamadas
de uso por perfil. No hay ventaja de precisión ni prueba de productividad OSS.
Resultado acotado: paridad con menos inferencia frente a perfiles que infieren;
raw e historial completo también empatan. Documentación y límites completos en
competitive_evaluation.md; datos en competitive_results.json y research_notes/competitive_v10.

Paquete local: /tmp/synopsis-0.10.0.zip; recibo de entrega fuera del paquete en
/tmp/synopsis-v10-delivery.json. Preview del panel con datos sintéticos en
docs-img/memory_panel_010.png. El servicio local del mapa está actualizado.

Pendiente de investigación de producto: issues reales, sesiones largas, más modelos,
otros lenguajes y mantenimiento a escala. No afirmar superioridad universal, novedad
científica mundial ni eliminación de alucinaciones. No convertir los empates en victoria.

## Anotaciones históricas de construcción (anteriores al estado vigente)

Estado: diseño/implementación, aún sin resultados competitivos. Objetivo persistente:
demostrar una ventaja reproducible frente a perfiles comparables Mem0/Graphiti/ShadowFrog,
con controles raw/full-history, mismo modelo y presupuesto. No commits/push/PR.

Protocolo congelado antes de esta implementación: `competitive_protocol.json`, SHA256
b45ef7d6cca28665d3226994687e10ff97f7c92ab9d6544bd81fd127a4fafb63.
Perfil ShadowFrog = memoria por archivo/símbolo y sus helpers oficiales, NO Dream.
Clones/SDKs y venv ya están disponibles (ver comparaciones previas y scripts locales).

Principio: una experiencia útil conserva un contraejemplo ejecutable, además de texto.
Guardar casos JSON de entradas/salidas observadas de una función y su procedencia.
El oráculo de comparación permanece en el controlador; el hijo no recibe expectativas.
No se presume causalidad ni verdad normativa a partir de una observación.

Implementado inicialmente: `engine/behavior_runner.py`, ejecutor Python en bwrap que
solo devuelve valores/excepciones. Entrada de 1..24 llamadas {args,kwargs}, descriptor
{path,symbol}; límites de tipos/tamaño, bootstrap -I, stdlib cargada antes de sys.path
proyecto, recursos10s/512MB, timeout15s, snapshot origen, sin red/home/credenciales.
No se ha validado todavía. También se endureció el bootstrap de experience_runner.py
con -I para no importar un resource.py/unittest.py del proyecto antes de imponer límites.

Siguiente implementación propuesta:
- BehaviorMemory en SQLite privado por proyecto: descriptor/firma, casos JSON con
  {call,expected:{value|raises}}, referencias a test/line/hash y fuente/snapshot observado.
- Captura automática desde assertEqual de tests AST con inputs/expected literales,
  solamente tras confirmar por ejecución aislada que el prototipo pasa esos ejemplos.
  Vincular al resultado de ResearchWorkbench y a revisiones/guardas de experiencias.
- No archivar código ejecutable de tests ni copiar expectativa al proceso no confiable.
- Conservar casos tras cambio de implementación: reejecutarlos, no descartarlos solo
  porque cambió el .py que se quiere proteger. Mantener guardas y soporte de política
  independiente; retirar si cambian alcance/experiencia/contrato o firma incompatible.
- Integrar casos relevantes en ResearchWorkbench.prepare para el modelo, y ejecución
  original/candidato antes de clasificar ganancia/regresión. Controles compartidos y
  casos históricos se fijan antes de inferencia; modelo no elige solo pruebas fáciles.
- Recordar experimentos anteriores sin promover prototipo a verdad actual ni aplicarlo
  al checkout. Recuperar pistas en task_context y mostrar testigos en Memoria viva.
- API de retiro de testigo con motivo/revisión, sin borrar la procedencia.

Evaluación pendiente:
- Crear corpus a partir de cuatro familias/seeds ya fijados, desarrollo vs reservado,
  gold + extensiones explícitas y tests ocultos. No cambiar etiquetas tras medir.
- SDK reales: /tmp/synopsis-embedding-eval-venv (mem0ai2.2.1,graphiti-core0.31.1,
  fastembed0.9.0,falkordblite0.10.0). Adaptadores nativos base en
  /tmp/synopsis-comparison/run_oss_pilot.py; no copiar sus resultados como nuevos.
- Mem0 inferred y infer=False, Graphiti real, ShadowFrog helpers/skills oficiales,
  raw/fullhistory/no-memory. Provenance source fetch para IDs realmente recuperados
  con un round disponible a todos. Misma generación/executor actuales, casos
  históricos disponibles según recuperación; no regalar información a un brazo.
- Captura, recuperación y respuesta deben medirse por separado. Si raw empata/gana,
  comunicarlo. El objetivo no autoriza inventar una victoria.

Cierre 0.9 ya verificado: /tmp/synopsis-0.9.0.zip SHA256
262172b94ec320c5eed3eda9b02d000fd90c4724efcdbebc543e20272a7fa8b7,
323 archivos, instalación limpia5clientes15tools. 341 unitarias,767/767humo.
Doctor yHTTP autenticado funcionan. Preview /tmp/synopsis-v09-panel.png sintético.
A partir de aquí se edita directamente el repo por acceso completo: NO volver a
sincronizar /tmp/synopsis-v09, pues podría pisar la implementación nueva.

Checkpoint posterior: BehaviorMemory implementada en engine/behavior_memory.py.
Captura assertEqual literal de tests reales, confirma con behavior_runner externo,
persiste casos/procedencia/firma/guardas en SQLite y puede retirar con CAS. Reproduce
casos aun si el test fue borrado; no descarta automáticamente un testigo al cambiar
el .py protegido. Respeta firma, retiro, revisión de experiencia/guardas/contratos y
asserts explícitos nuevos. Ocho tests directos pasan (incluye bwrap real).
ResearchWorkbench ya recibe hasta dos testigos en su contexto, los evalúa con oráculo
externo al comparar candidatos, y captura testigos automáticamente tras una mejora
observada; no permite al modelo elegir solo el test fácil. Le falta validación integral
nueva y superficies CLI/MCP/UI/contexto para los testigos. El bootstrap unittest se
endureció con -I. Los 18 tests de test_memory_research.py siguen pasando.
Todavía NO se ha ejecutado comparación nueva de SDKs ni se ha logrado la meta activa.
