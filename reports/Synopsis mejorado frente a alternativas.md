# Synopsis frente a alternativas · actualización 0.10

**El ensayo nuevo encontró paridad de precisión y una ventaja acotada de adquisición
sin inferencia.** En cuatro tareas reservadas repetidas dos veces, Synopsis, Mem0
inferred/raw, Graphiti, el perfil de memoria de ShadowFrog e historial completo
obtuvieron 8/8; sin memoria fueron 4/8 por abstenciones en reparaciones sin historia.
Synopsis necesitó 0 llamadas LLM para capturar testigos; Mem0 inferred 8, Graphiti 25
y ShadowFrog 4. Mem0 raw también necesitó 0. Todos usaron 8 llamadas de desarrollo.

La implementación nueva conserva llamadas/salidas observadas y su procedencia,
reproduce casos aunque desaparezca el test original y suspende su aplicación ante
cambios de firma, alcance o contrato explícito. El banco incorpora esas comprobaciones
y el mapa muestra sus resultados. Es una mejora concreta del producto; no demuestra
que el mecanismo jamás haya existido o que elimine alucinaciones.

**Estos son repositorios sintéticos pequeños, no issues OSS o productividad real.**
El controlador de testigos y source-fetch se ofreció a todos. Los controles raw e
historial completo empataron, por lo que no se puede afirmar mayor precisión ni una
superioridad general frente a sus productos. La comparación de ShadowFrog cubre su
skill/viewer/Markdown, no Dream. La conclusión de costes se refiere a los perfiles
y datos medidos, con un solo modelo y límites explícitos.

[Protocolo, resultados y límites completos](../docs/competitive_evaluation.md) ·
[Resumen JSON](../docs/competitive_results.json) ·
[Trazas conservadas](../research_notes/competitive_v10/) ·
[Funcionamiento y diagrama](../docs/behavior_memory.md).

## Informe histórico 0.8, conservado como antecedente

**Synopsis 0.8 cerró dos fallos concretos de recuperación y vigencia, pero todavía no demuestra superioridad frente a Mem0, Graphiti o ShadowFrog.** Ahora recupera los grupos de los casos conocidos y conserva políticas necesarias para resolver cinco pequeñas tareas de programación. El hallazgo decisivo limita esa conclusión: **las cinco soluciones de código usaron notas; sus paquetes tenían `experiences=[]` y `decisions.groups=[]`**. Por tanto, esos éxitos no validan la utilidad de DecisionRAG ni del laboratorio al programar. Frente a Mem0 y Graphiti disminuye la brecha de búsqueda básica; frente a ShadowFrog continúa pendiente la generación de experimentos nuevos. La oportunidad más defendible es evitar aplicar experiencias fuera de contexto mediante condiciones verificables del repositorio. Esa oportunidad está implementada parcialmente y necesita evidencia independiente de beneficio. ([Auditoría actual](../research_notes/Synopsis%20mejorado%20frente%20a%20alternativas/synopsis_evidence.md), [resultados completos](../docs/upgrade_evaluation.json)).

Informe del **17 de octubre de 2026**. Compara el código implementado de Synopsis 0.8 con las revisiones auditadas previamente: Mem0 OSS 2.2.1, `0724291bd864cf807e88ee8981c8226644e8fb42`; Graphiti 0.31.1, `d50741d1bf463cbe3859eb73914cbff1b66839e6`; ShadowFrog, `1f6e615c2ddfeffa8ba709401afafa1e9ffa9452`. Son fotografías fijadas, no una certificación del HEAD público más reciente. Esta actualización sintetiza fuentes y resultados existentes; no ejecutó nuevas inferencias ni pruebas de producción. La auditoría verificó **90/90 hashes** del manifiesto de Synopsis; eso vincula los archivos enumerados con la evidencia, no certifica cada archivo del repositorio ni todos los ensayos preliminares. ([Versiones Mem0](https://github.com/mem0ai/mem0/blob/0724291bd864cf807e88ee8981c8226644e8fb42/pyproject.toml), [Graphiti](https://github.com/getzep/graphiti/blob/d50741d1bf463cbe3859eb73914cbff1b66839e6/pyproject.toml), [ShadowFrog](https://github.com/microsoft/ShadowFrog/blob/1f6e615c2ddfeffa8ba709401afafa1e9ffa9452/README.md), [verificación local](../research_notes/Synopsis%20mejorado%20frente%20a%20alternativas/synopsis_evidence.md)).

## La brecha cambia según qué queramos recordar

Mem0 es una biblioteca general de hechos y recuerdos; Graphiti estructura episodios, entidades y relaciones temporales; ShadowFrog organiza conocimiento del código y genera investigaciones ejecutables. Synopsis se especializa en continuidad por proyecto, notas y experiencias condicionadas. Esta diferencia de propósito impide construir un ranking global contando funcionalidades. La matriz compara rutas auditadas: “sin equivalente localizado” no significa ausencia demostrada en todo un ecosistema. ([Mem0 y Graphiti](../research_notes/Synopsis%20mejorado%20frente%20a%20alternativas/mem0_graphiti.md), [ShadowFrog](../research_notes/Synopsis%20mejorado%20frente%20a%20alternativas/shadowfrog.md)).

| Capacidad | Synopsis 0.8 | Mem0 OSS fijado | Graphiti fijado | ShadowFrog fijado |
|---|---|---|---|---|
| Unidad de memoria | Notas, experiencias y alternativas por proyecto | Hechos por usuario/agente/sesión | Episodios, entidades y relaciones | Hallazgos por archivo/símbolo |
| Recuperación | BM25, anclajes técnicos, vectores y RRF | Semántica, BM25 por backend y entidades | Recetas híbridas, grafo y reranking opcional | Navegación de Markdown y búsqueda textual |
| Vigencia | Guardas actuales, revisiones y hash de soporte independiente | Expiración y APIs update/delete | Validez temporal e invalidación de relaciones | Revisión por agente y recordatorio de cambios |
| Aplicabilidad al repositorio actual | Contrato explícito, acotado a condiciones capturadas | Sin equivalente localizado en memoria auditada | Sin equivalente localizado en ingestión episódica | Juicio del agente y hallazgos vinculados a código |
| Experimentación | Sensibilidad del primer unittest existente | Fuera del núcleo auditado | Fuera del núcleo auditado | Dream implementa y encadena prototipos |
| Integración | Cinco clientes documentados; hooks cooperativos | SDK, skills y plugins | SDK y MCP oficial | Copilot CLI y Claude Code documentados |

Mem0 **ya es híbrido**: sobreextrae candidatos semánticos y combina señales BM25/entidades; en la ruta revisada, los resultados exclusivamente léxicos no se unen como candidatos independientes. Su captura actual añade hechos y mantiene actualización/borrado explícitos: describirla con el antiguo algoritmo automático UPDATE/DELETE sería incorrecto. Graphiti ofrece BM25, coseno, RRF, MMR y otras recetas; no exige un reranker LLM en toda consulta. Su representación temporal y relacional sigue siendo más rica que las revisiones de Synopsis. ([Mem0: búsqueda](https://github.com/mem0ai/mem0/blob/0724291bd864cf807e88ee8981c8226644e8fb42/mem0/memory/main.py#L1642-L1701), [captura](https://github.com/mem0ai/mem0/blob/0724291bd864cf807e88ee8981c8226644e8fb42/mem0/memory/main.py#L918-L1016), [Graphiti: recetas](https://github.com/getzep/graphiti/blob/d50741d1bf463cbe3859eb73914cbff1b66839e6/graphiti_core/search/search_config_recipes.py), [tiempo](https://github.com/getzep/graphiti/blob/d50741d1bf463cbe3859eb73914cbff1b66839e6/graphiti_core/edges.py#L265-L287)).

Synopsis ahora fusiona canales de búsqueda y reobserva condiciones sin invalidar automáticamente una experiencia por cualquier cambio en su archivo de contexto. El soporte independiente permanece ligado a hash. Esto es útil, pero depende de que la captura haya identificado las dependencias correctas: la excepción del hash abarca cualquier ruta usada en guardas, sin descubrir automáticamente su función semántica completa. Las actualizaciones automáticas son conservadoras: requieren revisión observada y preservan acción, alcance, condiciones, pruebas, límites y contraejemplos. No resuelven toda contradicción ni sustituyen automáticamente políticas dañinas. ([Ranking](../engine/experience_retrieval.py), [aplicabilidad](../engine/decision_rag.py), [revisor](../engine/auto_review.py)).

ShadowFrog conserva una ventaja clara en **crear conocimiento mediante código nuevo**. Dream desarrolla prototipos, mantiene ramas y permite continuarlos. ExperienceLab solo ejecuta el primer unittest Python declarado, con contexto base y cambios booleanos JSON individuales, hasta cuatro ejecuciones. Sus snapshots Linux/bwrap permiten detectar una prueba insensible a esos cambios; no generan hipótesis nuevas ni prueban causalidad general. Dream no se ejecutó aquí porque exige commits/push, prohibidos por el usuario: es una limitación de esta auditoría, no del proyecto. ([Dream fijado](https://github.com/microsoft/ShadowFrog/blob/1f6e615c2ddfeffa8ba709401afafa1e9ffa9452/skills/shadow-frog-dream/SKILL.md), [laboratorio](../engine/experience_lab.py), [aislamiento](../engine/experience_runner.py)).

## Los diagnósticos mejoraron; la exactitud QA sigue igual

| Indicador | Synopsis 0.7 | Synopsis 0.8 | Interpretación válida |
|---|---:|---:|---|
| Grupos en consultas diagnósticas | 4/12 | 12/12 | Reparación del recorrido de recuperación conocido |
| Selección en consultas resolubles | 2/6 | 6/6 | Mejora de aplicabilidad en esos escenarios |
| Exactitud QA | 5/6 | 5/6 | Sin mejora demostrada de respuesta final |
| Replay de payloads 0.7, cinco estados por dominio | No medido con ese protocolo | 15/15, incluso sin embeddings | Regresión conocida; no holdout |

Los conteos provienen del piloto anterior y del final 0.8; **no equivalen a productividad triplicada**. El replay mantiene los seis payloads originales y muestra que BM25 sobre contratos y la corrección de guardas explican parte de la mejora sin MiniLM. El modelo exacto no estaba fijado en 0.7; 0.8 usa `gpt-6.1-sol`, por lo que el cambio entre respuestas no identifica un efecto causal exclusivo del código. ([Baseline](Comparación%20técnica%20de%20Synopsis.md), [evaluación 0.8](../docs/upgrade_evaluation.md), [replay](../tools/evaluate_retrieval_upgrade.py)).

| Experimento y procedencia | Synopsis | Sin memoria | Historial pertinente completo | Otros proyectos |
|---|---:|---:|---:|---|
| QA final 0.8, mismos seis casos y corrida local | 5/6 | 5/6 | 6/6 | No reejecutados |
| QA anterior, piloto con SDKs reales | 5/6, versión 0.7 | 5/6 | 6/6 | Mem0 6/6; Graphiti 6/6 |
| Programación sintética 0.8, tres tareas | 3/3 | Abstención correcta 3/3 | 3/3 | No medidos |
| Dos variantes posteriores al congelado | 2/2 | Abstención correcta 2/2 | 2/2 | No medidos |

Cada comparación local usa una ejecución por brazo; los resultados externos son históricos, **no un nuevo head-to-head de programación**. En QA el contrato actual ya revelaba la regla, así que acertar no acredita recordar. El desacuerdo Unicode conserva su respuesta esperada original; no se retiró para mejorar el marcador. Mem0/Graphiti usaron adaptadores Codex, BGE-small CPU y almacenes locales; Mem0 funcionó con su fallback sin spaCy. Es un perfil real reducido, no la mejor configuración certificada de cada producto. ([Datos 0.8](../docs/upgrade_evaluation.json), [protocolo OSS anterior](../research_notes/Comparación%20técnica%20de%20Synopsis/mem0_graphiti.md)).

**Las cinco tareas de código validan continuidad mediante notas, no inteligencia experiencial.** Las políticas numéricas estaban ausentes del código actual; Synopsis las capturó y recuperó en `packet.notes`. En todos los paquetes estaban vacíos tanto experiencias como grupos DecisionRAG. Los controles sin memoria se abstuvieron correctamente: no alucinaron. El historial completo también resolvió todo. Son funciones puras que seleccionan constantes según un booleano; los tests ocultos nacen después de la respuesta y ejecutan en aislamiento. Las dos variantes posteriores al congelado ayudan a comprobar generalización del patrón, pero no representan issues reales ni parches multifichero. Los ensayos fallidos 0/3 y 1/3 se conservaron. ([Diagnósticos y trazas](../docs/upgrade_evaluation.json), [harness](../tools/evaluate_coding_memory.py), [variantes](../tools/evaluate_coding_holdout.py)).

ShadowFrog publica evidencia más amplia: 50 tareas SWE-Bench Verified, doce repositorios y 300 corridas, con 82,0% frente a 77,3%. Sus workflows difieren; los autores identifican influencia del contenido de memoria en una sola tarea. Eso no permite atribuir los 4,7 puntos enteramente a recordar. Tampoco permite comparar su porcentaje con nuestro 5/5 sintético. Nuestra auditoría anterior ejecutó 67 tests puros y cinco probes, sin Dream ni comparación LLM directa. ([Método oficial](https://github.com/microsoft/ShadowFrog/blob/1f6e615c2ddfeffa8ba709401afafa1e9ffa9452/eval/README.md), [dashboard](https://github.com/microsoft/ShadowFrog/blob/1f6e615c2ddfeffa8ba709401afafa1e9ffa9452/eval/results_dashboard.html), [recibo local](../research_notes/Comparación%20técnica%20de%20Synopsis/shadowfrog-audit-probes.json)).

## Instalar fácil no garantiza recordar bien siempre

La semántica CPU local está implementada e instalada: FastEmbed 0.9.0, MiniLM multilingüe ONNX, unos 220 MB de modelo más dependencias. Su entrada es de **128 tokens**; se representan dos fragmentos compactos por experiencia. Procesa hasta 64 fragmentos ausentes por llamada sobre 2048 casos y conserva hasta 8192 vectores por proyecto. Un índice frío puede estar `warming`; texto truncado o candidatos fuera de ese límite pueden perderse. Se probaron seis pares semánticos y consultas ES/EN/PT más abstención ajena, no todos los idiomas anunciados en la ficha ni cualquier modelo consumidor. ([Límites canónicos](../docs/local_semantics.md), [resultados](../docs/upgrade_evaluation.json)).

El worker usa loopback autenticado, archivos privados e inferencia offline; la captura LLM no queda por ello convertida en offline. Mem0 también admite componentes locales y Graphiti ofrece MCP: ni privacidad local ni integración IDE son exclusivas. Cinco conectores documentados tampoco prueban invocación efectiva en cada prompt. Las **323 unitarias y 767/767 comprobaciones Linux** verifican implementación; no miden productividad ni sustituyen Windows nativo pendiente. ([Runtime](../engine/local_semantics.py), [continuidad](../docs/continuity.md), [Graphiti MCP](https://github.com/getzep/graphiti/blob/d50741d1bf463cbe3859eb73914cbff1b66839e6/mcp_server/README.md), [Mem0 integraciones](https://github.com/mem0ai/mem0/blob/0724291bd864cf807e88ee8981c8226644e8fb42/README.md#L183-L209), [verificación](../docs/upgrade_evaluation.md)).

No existe comparación homogénea de tokens facturados, RAM o latencia p95. Incluso en las pequeñas tareas actuales, las peticiones de respuesta Synopsis suman 7594 caracteres frente a 2520 con historial; en las dos variantes, 5055 frente a 1660. **No se demostró ahorro de contexto**; caracteres no son tokens ni dinero. Tampoco sumas históricas de duración LLM equivalen a latencia de recuperación. ([Reanálisis de trazas](../research_notes/Synopsis%20mejorado%20frente%20a%20alternativas/synopsis_evidence.md)).

## La siguiente prioridad es aislar el beneficio diferencial

Recomiendo priorizar evidencia sobre más componentes. Primero, reservar issues reales y separar notas, experiencias y laboratorio mediante ablaciones: sin memoria, historial pertinente, notas recuperadas, Synopsis completo y variantes sin experiencias/laboratorio, junto a los competidores. Deben compartir repos/commits, modelo fijado, workflow, información disponible, presupuestos y repeticiones aleatorizadas. La aceptación exige parches correctos con pruebas ocultas y de regresión, incluyendo casos donde experiencias o intervenciones cambien el resultado frente a notas solas. Si no ocurre, conviene simplificar el producto alrededor de la continuidad que sí ayuda. Es una propuesta pendiente, derivada del vacío observado en los diagnósticos. ([Evidencia del vacío](../research_notes/Synopsis%20mejorado%20frente%20a%20alternativas/synopsis_evidence.md)).

Segundo, probar adquisición y vigencia adversariales: políticas obsoletas, correcciones explícitas, recuerdos falsos, evidencia retirada, dependencias omitidas y alternativas complementarias. Medir pérdida de hechos durables, aplicación indebida, abstenciones correctas y daño inducido. Después, medir búsqueda fría/caliente y distractores alrededor del límite de 2048 casos, texto largo, varios idiomas y eventos reales de los cinco clientes. Registrar captura, mantenimiento, tokens, latencias p50/p95 y recursos completos; separar consumir memoria de financiar su generación, especialmente Dream. Los umbrales deben fijarse antes del ensayo y publicarse todos los fallos. La propuesta anterior de 360 ejecuciones **no se ha realizado**. ([Riesgos de actualización](../engine/auto_review.py), [límites de escala](../docs/local_semantics.md), [protocolo previo](Comparación%20técnica%20de%20Synopsis.md)).

## El diferenciador necesita cambiar decisiones reales

La posición defendible hoy es una herramienta local de continuidad con comprobaciones explícitas de aplicabilidad. Estamos más cerca de recuperación híbrida útil que en 0.7, pero siguen abiertas la ventaja temporal/relacional de Graphiti, la superficie de integración/configuración de Mem0 y la exploración de código de ShadowFrog. No hay base para expresar distancia en meses, porcentajes de madurez o “1000x”, ni para reclamar novedad mundial o erradicación de alucinaciones. ([Síntesis técnica auditada](../research_notes/Synopsis%20mejorado%20frente%20a%20alternativas/mem0_graphiti.md), [contraste experimental](../research_notes/Synopsis%20mejorado%20frente%20a%20alternativas/shadowfrog.md)).

El hito útil consiste en demostrar que una experiencia pertinente evita un parche equivocado cuando cambian sus condiciones, y que esa protección compensa el coste de capturarla y mantenerla. Esa prueba distinguiría una combinación de componentes conocidos de un producto que mejora de forma medible el trabajo del desarrollador.
