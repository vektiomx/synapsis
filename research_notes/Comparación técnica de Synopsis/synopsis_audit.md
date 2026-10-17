# Auditoría de Synopsis 0.7 y primer piloto reservado

## ¿Qué demuestra realmente la evaluación anterior?

### Takeaway
La evaluación anterior demuestra cumplimiento de condiciones declaradas en tres fixtures sintéticos. No demuestra superioridad contra productos externos, productividad sobre repositorios reales ni aprendizaje automático de esas condiciones.

### Cited Findings
- El evaluador escribe manualmente las dos experiencias, el discriminador booleano, las condiciones `requires` y los checks a partir del mismo diccionario de dominio que determina la respuesta esperada. La extracción automática no interviene. — [Evaluador](../../tools/evaluate_decision_rag.py)
- El control determinista `lexical_top1` escoge por nombre alfabético, sin puntuación BM25 ni embeddings. El brazo live usa `rows[0]`, otro orden. No es una implementación de un RAG híbrido competitivo. — [Evaluador](../../tools/evaluate_decision_rag.py)
- Tres escenarios de cinco por dominio esperan abstención: unknown, invalid-type y changed-contract. Un sistema que siempre se abstuviera lograría 9/15 en esos casos; no se presenta ese control. La puntuación 18/18 del motor incluye tres escenarios adicionales que los controles no reciben. — [Evaluador](../../tools/evaluate_decision_rag.py)
- Las ablaciones son otra función Python que reproduce parte de las reglas del motor; no entrenamiento o experimentación con modelos externos. Los resultados live no instrumentan tokens facturados ni identidad exacta del modelo. — [Evaluador](../../tools/evaluate_decision_rag.py)

### Inferences
- La caída del control alfabético no permite estimar ventaja sobre un RAG competente.
- No hay evidencia suficiente para cuantificar porcentaje de cercanía respecto a Mem0, Graphiti o ShadowFrog a partir de esas puntuaciones.

### Gaps
- Faltan tareas de parches con pruebas ocultas, múltiples repositorios, repeticiones, modelos fijados e intervalos de incertidumbre.

## ¿Qué pasó al dejar que Synopsis aprendiera desde historial bruto?

### Takeaway
Se ejecutó el revisor real sobre seis episodios nuevos en tres dominios distintos de los fixtures anteriores: artefactos/hardlinks, orden de eventos y equivalencia Unicode. Las condiciones y experiencias no fueron escritas a mano para Synopsis.

### Cited Findings
- El corpus, harness, prompts y respuestas completos quedan preservados. Todos los brazos de respuesta reciben el mismo contrato y configuración actuales. El control de archivos recibe todos los historiales pertinentes; no se elimina un contraejemplo por top-1. — [Corpus](corpus.json); [Harness](run_pilot.py); [Resultados](synopsis_pilot_results.json); [Trazas](synopsis_pilot_trace.jsonl)
- Se conservaron por separado los fallos iniciales de ejecución del sandbox; el piloto que informa resultados del modelo fue repetido fuera del sandbox. — [Fallos infraestructura](synopsis_pilot_sandbox_failures.json)
- Resumen medido: `{"source_sha256": {"engine/decision_rag.py": "fd9f322e1c5c9f89ee6b3b0b7466c097dba4aafc7c2ab283e9914878f5f32f74", "engine/auto_review.py": "31d740b690f6d5fe2938fad5ce5dd0bc2e7e5a54d03b4ecbc381e377172afe4f", "engine/experience_engine.py": "3239792cf73297aa15251976ca7ab2cf0c1a69ca3d67f7d365806c47971b20c4", "engine/model_provider.py": "3f3f54b368465cb5035ad5b8a76df632eb5a73761649401a0fc931b29f18abd8"}, "calls": 24, "scores": {"file-memory-all-relevant": {"correct": 6, "total": 6}, "no-memory": {"correct": 5, "total": 6}, "synopsis": {"correct": 5, "total": 6}}, "capture_summary": {"episodes": 6, "experiences": 6, "decision_cases": 6}, "capture_seconds": 81.83921377400111, "inference_seconds": 119.29559166895342, "retrieval_seconds": 0.03097198203613516, "retrieval_with_groups": 4, "retrieval_total": 12, "retrieval_selected": 2, "captures_failed": 0, "codex_version": "codex-cli 0.162.0-alpha.17.2", "model_identity": "native default, not instrumented; no model pin", "external_frameworks_in_this_report": false}`. — [Resumen](synopsis_pilot_summary.json)

- El motor contrastivo utiliza intersección de palabras y coincidencia de rutas; no llama al módulo semántico. Las notas generales sí pueden usar embeddings opcionales, pero estos no están conectados a DecisionRAG. — [DecisionRAG](../../engine/decision_rag.py); [Embeddings opcionales](../../engine/semantic_memory.py)
- Las capturas generaron texto y claves predominantemente en español. El inglés de las consultas no necesariamente comparte tokens; el diagnóstico mantiene la consulta original intacta para el resultado principal y prueba por separado traducción y ayuda mediante ruta. — [Trazas](synopsis_pilot_trace.jsonl); [Diagnósticos fuera de puntuación](synopsis_pilot_diagnostics.json)
- El revisor puede colocar el mismo archivo de contexto dinámico tanto en `requires` como en `checks`. En ese caso `_assess` exige la huella completa del archivo: añadir un campo irrelevante invalida el soporte, aunque el discriminador no cambie. Los fixtures manuales del evaluador original no colocan el contexto en checks y no detectan este desajuste de la adquisición real. — [Revisor](../../engine/auto_review.py); [Evaluación de vigencia](../../engine/decision_rag.py); [Diagnósticos](synopsis_pilot_diagnostics.json)

- El único desacuerdo del modelo con el oracle ocurre en Unicode negativo: la configuración niega equivalencia canónica, pero el contrato menciona preservar bytes para identificadores firmados sensibles a bytes. Dos brazos consideran insuficiente esa condición adicional. Una adjudicación independiente, ciega a las respuestas y realizada sobre contrato, flag y opciones, sostiene el gold preserve-bytes: el flag false prohíbe equivalencia canónica y NFC puede colapsarla; la firma es una obligación adicional y no un requisito necesario. El gold original se conserva. Se informa además sensibilidad sobre los otros cinco casos: todos los brazos 5/5. Este caso no permite declarar que el control de archivos sea superior. — [Respuestas literales](synopsis_pilot_results.json); [Análisis de sensibilidad](synopsis_pilot_summary.json)

### Inferences
- Un acierto del modelo con acceso a un contrato que contiene la regla no demuestra aporte causal de memoria. Si no-memory empata, el caso es un control negativo de utilidad, no una victoria de Synopsis.
- La fiabilidad de extremo a extremo requiere mejorar recuperación entre idiomas, relación entre contexto dinámico y evidencia fija, y consistencia de la adquisición automática. No se corrigió el núcleo durante esta medición.

### Gaps
- El piloto es sintético, un solo backend Codex por defecto, una repetición y orden fijo de brazos. No ejecuta código generado ni mide productividad real.
- La línea base de archivos incluye todo el corpus pertinente, equivalente a recuperación de recall completo para ese corpus pequeño; no se ejecutó un índice híbrido escalable en este brazo.

## ¿Qué está operativo y qué queda por demostrar?

### Takeaway
Synopsis tiene un motor local implementado con procedencia, condiciones declaradas y aislamiento opcional. Su estado no equivale todavía a un sistema que descubre y valida automáticamente límites de comportamiento en repositorios arbitrarios.

### Cited Findings
| Capacidad | Estado observado | Evidencia |
|---|---|---|
| Memoria por proyecto, revisiones e integridad | Implementada | [Store](../../engine/experience_engine.py) |
| Captura automática desde episodios | Ejecutada en piloto | [Resultados](synopsis_pilot_results.json) |
| Generación automática de requisitos contrastivos | Ejecutada, calidad variable | [Capturas y traces](synopsis_pilot_trace.jsonl) |
| Recuperación contrastiva entre idiomas | Insuficiente en consultas reservadas | [Resultados](synopsis_pilot_results.json) |
| Comprobación declarativa de condiciones | Implementada; depende de cómo se extraigan | [Motor](../../engine/decision_rag.py) |
| Invalidez por cambios de fuente | Implementada; puede ser excesiva | [Diagnósticos](synopsis_pilot_diagnostics.json) |
| Propuestas de observación discriminante | Calculadas de requisitos existentes; no descubre requisitos nuevos | [Motor](../../engine/decision_rag.py) |
| Pruebas Python aisladas | Implementadas, explícitas; fuera de este piloto | [Runner](../../engine/experience_runner.py) |
| Feedback de utilidad/daño | Reportado por cliente; no atribución causal automática | [Outcome](../../engine/decision_rag.py) |
| Grafo temporal de hechos | No aparece en el motor auditado | [Motor y store](../../engine/decision_rag.py) |
| Descubrimiento experimental automático de límites nuevos | No implementado como ciclo de investigación autónomo | [Motor](../../engine/decision_rag.py) |
| Superioridad externa y mejora de tareas reales | No demostrada por este piloto | [Protocolo y limitaciones](synopsis_pilot_results.json) |

### Inferences
- La mayor distancia competitiva es evidencia de utilidad, calidad de extracción y cobertura de recuperación. Añadir más mecanismos antes de corregir esas debilidades no garantiza mejoras.

### Gaps
- Este informe no contiene puntuaciones de Mem0/Graphiti. Sus ejecuciones se documentan por separado y no deben inferirse a partir del análisis de fuentes.
- Python3.14.4 y CodexCLI disponibles; Docker29.9.1 accesible fuera del sandbox. El primer permission-denied era restricción del sandbox, no ausencia de Docker. No hubo GPU operativa ni Ollama disponible; se encontró FastEmbed/ONNX CPU y un modelo en caché en un venv temporal.
