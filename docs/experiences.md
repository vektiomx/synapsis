# Experiencias de desarrollo

Desde 0.6, Synopsis conserva experiencias estructuradas además de las notas. Una
experiencia contiene situación, acción, motivo, resultado reportado, condiciones,
límites, contraejemplos y archivos de evidencia con SHA-256. Las interpretaciones
permanecen **inferred**, incluso cuando una comprobación pasa. Un check de configuración
no demuestra que una recuperación, migración o despliegue haya funcionado.

## Circuito implementado

1. Los adaptadores abren el turno. PostToolUse puede conservar hasta ocho rutas/huellas
   de archivos del proyecto; no conserva comandos ni salida cruda de herramientas.
2. Stop despierta el revisor independiente. Puede solicitar evidencia y proponer hasta
   dos experiencias. Los archivos citados deben haber sido leídos por el controlador.
3. Se valida todo el lote de propuestas antes de guardarlas. Una propuesta con formato
   incorrecto tiene una única reparación acotada; la reparación vuelve a validar evidencia.
   El modelo puede optar por no proponer ninguna experiencia. No existe un extractor
   infalible que comprenda todos los intentos de programación.
4. Las experiencias viven en `.synopsis/experiences.sqlite3`, dentro de la memoria
   vinculada del proyecto: un único almacén privado con versiones, comprobaciones y
   feedback. No se generan notas Markdown duplicadas. `experience history` permite
   exportar sus versiones en JSON. No hay sincronización automática entre máquinas.
5. Los hooks recuperan experiencias en cada prompt admitido y antes de leer/editar
   archivos cuando el cliente permite ese contexto. La selección considera texto,
   ruta y condiciones declarativas; el feedback solo ajusta candidatos pertinentes.
6. Se comprueban las huellas actuales. Una fuente cambiada produce **stale**, conservando
   el historial. Una observación falsa produce **contradicted**. Los antecedentes sin
   respaldo actual se entregan como historical_lead, nunca como instrucción o verdad.
7. Una actualización exige revisión esperada. Una sustitución explícita puede enlazar
   otro registro mediante supersedes; no borra versiones previas y no admite ciclos.
   El revisor automático no puede declarar esa sustitución por su cuenta.

El núcleo es independiente del proveedor. El éxito de instalación/MCP no prueba
que todos los IDE hayan cargado sus hooks ni que cada modelo aproveche el contexto.
Cursor conserva los límites ya documentados de su evento de envío de prompt.
El modo estricto `synopsis run` mantiene su política extractiva: este cambio no lo
convierte en un generador libre de parches ni permite tratar la experiencia como
una fuente factual admitida automáticamente.

## Comprobaciones y ejecución

`json_equals` comprueba un valor JSON (sin coaccionar booleanos/números ni aceptar
claves repetidas); `text_contains` comprueba un literal de un archivo. Se pueden
usar automáticamente. Solo respaldan la observación declarada, no la explicación.

`python_unittest` reejecuta un caso de tests existente con `experience verify --execute`.
Requiere Linux, bubblewrap funcional y Python del sistema. Usa una copia temporal
acotada y filtrada del proyecto, fuente de solo lectura, sin HOME real, variables
privadas ni red; aplica límites de tiempo, salida, CPU, memoria y descriptores.
No admite shell ni código arbitrario en la definición de la experiencia. No sigue
symlinks y excluye archivos sensibles reconocibles y carpetas privadas/dependencias.
Por ello, una prueba puede resultar unavailable si necesita dependencias excluidas.
No instala bubblewrap ni dependencias automáticamente. Otros entornos conservan la
memoria y las observaciones declarativas; la reproducción ejecutable queda unavailable.
La detección de secretos es heurística, no una garantía de identificar cualquier secreto.

Los resultados de ejecución se conservan con la huella de la copia y sus límites.
La recuperación ordinaria no ejecuta pruebas del repositorio. Muestra que una nueva
prueba puede estar pendiente y conserva last_execution como antecedente histórico.
Este aislamiento no es una certificación formal ni una defensa exhaustiva ante
agotamiento deliberado de recursos. No se ejecutan experimentos sobre producción.

## Uso y clientes

```bash
synopsis experience record --project /ruta/proyecto --name retry-policy --source agent:session < experiencia.json
synopsis experience recall --project /ruta/proyecto --query 'retry provider' --path src/queue.py
synopsis experience verify --project /ruta/proyecto --name retry-policy
synopsis experience verify --project /ruta/proyecto --name recovery-case --execute
synopsis experience history --project /ruta/proyecto --name retry-policy
synopsis experience feedback --project /ruta/proyecto --name retry-policy --revision 1 --outcome useful --event task-123 --source agent:session
```

La herramienta MCP **experiencias** expone record/recall/verify/history/feedback,
sin ejecutar código por MCP. `learn` conserva compatibilidad con experiencias
anteriores y dirige el formato nuevo al almacén estructurado. Las herramientas
nativas de memoria y sus recibos no se sustituyen. Un turno que solo guarda una
experiencia puede cerrar sus notas como no_change: el recibo separado de experiencias
muestra lo que se escribió y no simula una escritura Markdown.

Ejemplo mínimo de experiencia.json:

```json
{
  "situation": "El proveedor agotó los reintentos de la cola.",
  "action": "Conservar el trabajo hasta su vencimiento.",
  "rationale": "Permitir recuperar el trabajo cuando vuelva el proveedor.",
  "outcome": "Se observó la retención habilitada en configuración.",
  "limitations": "Todavía no se comprobó una recuperación real.",
  "when": {"paths": ["src/queue.py"], "keywords": ["retry", "provider"], "conditions": []},
  "checks": [{"kind": "json_equals", "path": "policy.json", "pointer": "/retain", "expected": true}],
  "evidence": [{"path": "policy.json", "sha256": "REEMPLAZAR_POR_LA_HUELLA_ACTUAL"}],
  "counterexamples": ["Los trabajos vencidos sí se descartan."]
}
```

## Recuperación y visibilidad

Se corrigieron tres límites encontrados en 0.5:

- Agotar tres intentos ya no borra una entrada recuperable: se conserva hasta su
  vencimiento de 24 horas y puede reintentarse desde CLI o el mapa. Reintentar no
  extiende la retención; la expiración borra la entrada.
- El inventario del revisor ordena candidatos por relevancia antes de llenar el
  presupuesto, en lugar de quedarse con las primeras notas alfabéticas. Su escaneo
  está acotado a 2.000 notas; el contexto, a 40 notas/10.000 caracteres. Es selección
  textual, no una garantía de equivalencia semántica ni cobertura de corpus ilimitados.
- Un cierre previo del modelo principal recibe una revisión independiente en un
  ciclo estricto enlazado. El cierre anterior se conserva, sin inventarle escrituras.

Mientras el mapa esté activo, un trabajador revisa las colas vinculadas cada 30 s;
permite recuperar trabajos pendientes sin otro evento del IDE. El servicio de usuario
Linux mantiene ese proceso si fue instalado. Sin mapa/servicio, se recuperan mediante
hooks o reintento explícito. Los fallos que agotan intentos requieren reintento; no se
facturan inferencias sin límite intentando reparar una cuenta no autorizada.

El mapa incluye estado de revisiones, experiencias, límites, comprobaciones y botón
para reintentar. La API conserva autenticación, comprobación de origen y acción; no
entrega prompts temporales ni permite pasar carpetas arbitrarias al reintento.

## Qué está demostrado

La batería determinista verifica almacenamiento, vigencia, condiciones, conflictos,
aislamiento, hooks/MCP, recuperación y protección de rutas. Una prueba real de Codex
capturó la experiencia ficticia de 19 horas, la recuperó en otra inferencia y conservó
que solo se había observado configuración. Cambiar el archivo la volvió stale.
Una prueba Linux separada reejecutó un unittest en aislamiento y distinguió un caso
correcto de un control negativo. No demuestran superioridad general frente a otros
productos, mejora estadística de programación ni exclusividad de la combinación.

```bash
python3 -B tools/evaluate_experiences.py
python3 -B tools/evaluate_experiences.py --live --provider codex
```

La primera no utiliza un modelo. La segunda usa datos ficticios y el cliente
actualmente autenticado. Es una prueba acotada de continuidad y límites; no compara
rendimiento de programación entre modelos. La evaluación comparativa sigue pendiente.

## Desde 0.7: comparar decisiones

El campo opcional `decision` permite conservar elecciones opuestas y sus requisitos.
El nuevo circuito, los comandos decide/outcome, la separación entre contexto dinámico
y soporte, y la evaluación se describen en [decision_rag.md](decision_rag.md).
Las experiencias anteriores no se promocionan automáticamente a reglas de decisión.


## Actualización conservadora y laboratorio (0.8)

El revisor recibe inventario relevante con revisiones. Para la misma elección y
alcance puede actualizar resultado o añadir evidencia/límites usando la revisión
esperada; conserva acción, condiciones, checks, límites previos, contraejemplos y
rutas de evidencia. No elimina un reporte de daño automáticamente. Una elección o
condición diferente forma otro caso. Un conflicto de revisión exige conciliación.
No se garantiza que el modelo proponga una actualización en cada ocasión.

Las políticas y preferencias sin intento observado se conservan como notas, no se
fabrican como experimentos. El hook combina notas, experiencias y decisiones: para
evaluar memoria completa se deben consultar los tres canales.

El [laboratorio de decisiones](decision_rag.md#recuperación-híbrida-y-observación-discriminante-08)
solo ejecuta pruebas existentes mediante CLI explícito; guarda sensibilidad histórica,
no promueve relatos a hechos ni aprende causalidad general. La semántica local y sus
límites están descritos [aquí](local_semantics.md).
