# Mem0 OSS y Graphiti frente a Synopsis 0.8

## ¿Qué brechas cerró Synopsis y cuáles siguen abiertas?

### Takeaway
Synopsis 0.8 dejó atrás dos deficiencias concretas de 0.7: recuperación de experiencias dependiente de coincidencia léxica y caducidad por cambios irrelevantes en el archivo de contexto. Esto aproxima sus mecanismos de búsqueda a alternativas existentes; no demuestra que su recuperación general sea mejor. La combinación con comprobaciones del repositorio es una especialización distinta del recuerdo conversacional de Mem0 y el grafo temporal de Graphiti.

### Cited Findings
- Revisiones efectivamente releídas, sin actualizar clones: Mem0 OSS 2.2.1, `0724291bd864cf807e88ee8981c8226644e8fb42`; Graphiti 0.31.1, `d50741d1bf463cbe3859eb73914cbff1b66839e6`. Consulta web oficial realizada el 17 de octubre de 2026; las capacidades detalladas siguientes corresponden a esas revisiones congeladas, no a una promesa sobre la última versión futura. [Mem0 pyproject](https://github.com/mem0ai/mem0/blob/0724291bd864cf807e88ee8981c8226644e8fb42/pyproject.toml), [Graphiti pyproject](https://github.com/getzep/graphiti/blob/d50741d1bf463cbe3859eb73914cbff1b66839e6/pyproject.toml).
- Mem0 combina semántica, keyword/BM25 y boost de entidades. Su conjunto candidato se origina en resultados semánticos sobreextraídos: los resultados exclusivamente keyword no se unen como candidatos independientes en esa ruta. No es correcto llamarlo RAG puramente vectorial. [Código de búsqueda](https://github.com/mem0ai/mem0/blob/0724291bd864cf807e88ee8981c8226644e8fb42/mem0/memory/main.py#L1642-L1701).
- Graphiti ya incluye recetas BM25/coseno/RRF, MMR, cercanía a nodos, menciones de episodios y, opcionalmente, BFS/crossencoder. No toda búsqueda invoca un LLM ni toda consulta recorre el grafo. [Recetas](https://github.com/getzep/graphiti/blob/d50741d1bf463cbe3859eb73914cbff1b66839e6/graphiti_core/search/search_config_recipes.py#L33-L153).
- Synopsis fusiona BM25, anclajes técnicos y vectores reales mediante RRF; filtra alcance por rutas y presenta señales separadas. El umbral semántico 0.48 es heurístico y no una probabilidad de verdad. [Código local](../../engine/experience_retrieval.py:90), [semántica local](../../docs/local_semantics.md).
- Mem0 adquiere hechos de forma aditiva con una llamada LLM en su ruta actual; conserva APIs explícitas de actualización y borrado. No se debe comparar contra la vieja descripción de una llamada LLM que siempre decide UPDATE/DELETE. [Captura](https://github.com/mem0ai/mem0/blob/0724291bd864cf807e88ee8981c8226644e8fb42/mem0/memory/main.py#L918-L1016).
- Graphiti extrae y resuelve nodos y relaciones, invalida relaciones y conserva procedencia de episodios. Sus aristas incluyen tiempos de validez e invalidación: representación temporal más rica que las revisiones de notas de Synopsis. [Pipeline](https://github.com/getzep/graphiti/blob/d50741d1bf463cbe3859eb73914cbff1b66839e6/graphiti_core/graphiti.py#L1468-L1529), [modelo temporal](https://github.com/getzep/graphiti/blob/d50741d1bf463cbe3859eb73914cbff1b66839e6/graphiti_core/edges.py#L265-L287).
- Synopsis reevalúa condiciones presentes y conserva el hash de soportes independientes. El autorevisor exige revisión previamente observada y no permite cambiar automáticamente acción, alcance, checks ni retirar límites/contraejemplos; un resultado dañino exige conciliación. Es actualización conservadora, no resolución general automática de contradicciones. [Evaluación actual](../../engine/decision_rag.py:136), [validación de propuestas](../../engine/auto_review.py:350).
- El laboratorio de Synopsis ejecuta el primer test Python declarado existente, en snapshots, con contexto base y cambios de una condición booleana JSON por vez; máximo cuatro ejecuciones. Distingue prueba sensible y prueba que siempre pasa; no genera libremente hipótesis ni aprende causalidad. [Código del laboratorio](../../engine/experience_lab.py:60).

| Eje | Synopsis 0.8 observado | Mem0 OSS congelado | Graphiti congelado |
|---|---|---|---|
| Recuperación | BM25 + anclajes + embeddings + RRF | Semántica + BM25 por backend + entidades | Híbrido con varias recetas y estructura relacional |
| Unidad principal | Notas y experiencias/decisiones por proyecto | Hechos con ámbito usuario/agente/sesión | Episodios, entidades y relaciones temporales |
| Cambio de conocimiento | Revisiones y actualización acotada | ADD automático; update/delete explícitos | Dedupe e invalidación de relaciones |
| Aplicabilidad contra archivos actuales | Guardas y soportes observados | No se localizó equivalente en la ruta de memoria auditada | No se localizó equivalente en la ruta episódica auditada |
| Desafiar una prueba existente cambiando contexto | Laboratorio acotado explícito | No se localizó equivalente en rutas auditadas | No se localizó equivalente en rutas auditadas |
| Relaciones indirectas y temporalidad | No implementa grafo bitemporal equivalente | Temporal reference_date es Platform-only; expiración OSS sí existe | Fortaleza estructural explícita |

La matriz sintetiza el código citado arriba; “no localizado” no certifica ausencia en todo el ecosistema o plugins.

### Inferences
- Ya no corresponde decir que Synopsis solo busca palabras. Tampoco que híbrido, embeddings locales, versiones o MCP sean inventos propios.
- El diferenciador defendible es continuidad de trabajo entre clientes más decisiones condicionadas por estado verificable del repositorio y sensibilidad de tests. Es una combinación útil y evaluable, no prueba de novedad mundial.
- Para búsquedas relacionales/temporales generales, Graphiti conserva una ventaja de representación. Para integrar memoria en aplicaciones y proveedores, Mem0 ofrece más superficie configurable; eso no implica ganar cada tarea de desarrollo.

### Gaps
- No existe comparación nueva de recall@k, MRR, distractores, contradicciones prolongadas o grafos multi-salto bajo idénticos modelos y corpus para los tres.
- No auditamos exhaustivamente cada integración ni backend: no convertir la matriz en afirmaciones universales de ausencia.

## ¿Qué cambia en instalación, privacidad y coste?

### Takeaway
Synopsis ofrece un perfil local preparado para el desarrollador, pero 0.8 añade una descarga inicial y un worker residente. Mem0 y Graphiti también pueden usar componentes locales: “local” por sí solo no los diferencia. No hay datos suficientes para declarar ganador de coste o latencia.

### Cited Findings
- Synopsis prepara FastEmbed 0.9.0 y MiniLM multilingüe ONNX (~220 MB más dependencias), CPU, 384 dimensiones y 128 tokens de entrada. Falla de descarga deja alternativa léxica. Indexa hasta 64 fragmentos ausentes por llamada sobre 2048 experiencias; guarda hasta 8192 vectores por proyecto. Los textos largos pueden perder detalles y el índice puede estar `warming`. [Documentación del runtime](../../docs/local_semantics.md).
- Mem0 puede usar Qdrant embebido: no exige servidor vectorial externo en todos los despliegues. Qdrant sparse BM25 requiere FastEmbed y colección compatible; una colección vieja degrada. [Provider Qdrant](https://github.com/mem0ai/mem0/blob/0724291bd864cf807e88ee8981c8226644e8fb42/mem0/vector_stores/qdrant.py#L27-L153).
- Graphiti dispone de varios backends y un MCP con proveedores de embeddings incluido Sentence Transformers; su guía ofrece contenedor FalkorDB+MCP y configuración del cliente. No requiere Zep SaaS para tener MCP. [README Graphiti](https://github.com/getzep/graphiti/blob/d50741d1bf463cbe3859eb73914cbff1b66839e6/README.md), [MCP oficial](https://github.com/getzep/graphiti/blob/d50741d1bf463cbe3859eb73914cbff1b66839e6/mcp_server/README.md#L14-L83).
- Mem0 también publica skills para asistentes y plugins. Ese soporte no debe confundirse con garantizar captura en cada prompt; algunas rutas del CLI usan la plataforma con API key. No adjudicar a Synopsis exclusividad de integración IDE. [Catálogo README](https://github.com/mem0ai/mem0/blob/0724291bd864cf807e88ee8981c8226644e8fb42/README.md#L183-L209), [skill CLI](https://github.com/mem0ai/mem0/blob/0724291bd864cf807e88ee8981c8226644e8fb42/skills/mem0-cli/SKILL.md#L18-L24).
- Mem0 OSS rechaza `reference_date`, aunque permite expiración. Los scores recientes de su README corresponden explícitamente a la plataforma gestionada y optimizaciones propietarias, no directamente al SDK probado. [Validación OSS](https://github.com/mem0ai/mem0/blob/0724291bd864cf807e88ee8981c8226644e8fb42/mem0/memory/main.py#L1393-L1447), [distinción oficial](https://github.com/mem0ai/mem0/blob/0724291bd864cf807e88ee8981c8226644e8fb42/README.md#L20-L38).

### Inferences
- La descarga/worker es un coste real de plug-and-play; sin red el comportamiento cambia. Recuperación local no implica que la captura LLM posterior sea offline.
- La adquisición relacional de Graphiti realiza más etapas; puede costar más en cierto perfil, pero la cantidad real depende de proveedor, duplicados y configuración. Las recetas de búsqueda no autorizan afirmar que paga un LLM en cada consulta.

### Gaps
- No hay comparación medida de RAM, RSS del worker, arranque frío/caliente, p50/p95, factura de tokens, instalación Windows ni corpus grandes. Los límites explícitos de Synopsis no son evidencia de escalabilidad empresarial.

## ¿Qué podemos concluir de los resultados existentes?

### Takeaway
La mejora demostrada es interna y acotada. No hay victoria competitiva demostrada: los SDK rivales no se volvieron a ejecutar después de 0.8 y las nuevas tareas de programación no los incluyen.

### Cited Findings
- Piloto previo con frameworks reales: Mem0 6/6 decisiones, Graphiti 6/6; seis capturas cada uno. Mem0 usó 12 llamadas Codex y Graphiti 18. Sumadas las duraciones LLM fueron 75.545 s y 156.060 s, respectivamente: totales de adquisición/respuesta, no latencia pura de retrieval ni coste facturado. Se usó Qdrant local/FalkorLite y BGE-small-en CPU, con spaCy ausente en Mem0. Perfil válido reducido, no óptimo certificado. [Notas y resultados previos](../Comparación%20técnica%20de%20Synopsis/mem0_graphiti.md).
- Synopsis 0.8 pasó 15 estados de regresión conservando payloads de 0.7, incluso sin embeddings: parte de la ganancia es BM25 sobre soporte y separación de contexto dinámico. En piloto final recuperó 12/12 grupos y seleccionó seis casos resolubles; QA siguió 5/6 versus historial completo 6/6 y sin memoria 5/6. [Evaluación 0.8](../../docs/upgrade_evaluation.md), [resultados completos](../../docs/upgrade_evaluation.json).
- Programación sintética 0.8: tres tareas finales y dos posteriores al congelado fueron resueltas tanto por Synopsis como por todo el historial pertinente; sin memoria se abstuvo. La auditoría de resultados identifica las políticas recuperadas en notas, con `experiences=[]` y `decisions.groups=[]`: ese 5/5 evidencia utilidad de notas/captura y no demuestra utilidad adicional de DecisionRAG, embeddings de experiencias o laboratorio. El informe conserva ensayos fallidos 0/3 y 1/3 previos. No fueron issues OSS reales ni head-to-head contra Mem0/Graphiti. [Protocolo y límites](../../docs/upgrade_evaluation.md), [datos de cada brazo](../../docs/upgrade_evaluation.json).

### Inferences
- La corrección de recuperación sí es tangible; accuracy final 5/6 recuerda que recuperar un caso no garantiza que el modelo elija la respuesta esperada.
- No combinar 6/6 rival previo con 5/5 coding propio como si fueran tareas equivalentes; tampoco presentar mejora interna como superioridad x1000.
- Próxima comparación decisiva: mismos repos congelados y errores reales, historias necesarias para parchear, tests ocultos, distractores y cambios de política, varios modelos/repeticiones y presupuesto común. Incluir búsqueda, captura, utilización, resultados dañinos, coste total y latencia. Publicar todos los perfiles y ejecuciones.

### Gaps
- No es posible asignar porcentaje de madurez, meses de ventaja, ahorro económico ni reducción universal de alucinaciones con estos datos.
