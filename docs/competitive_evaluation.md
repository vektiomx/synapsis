# Comparación reproducible de memoria de comportamiento · 0.10

**Synopsis igualó los aciertos de los perfiles con memoria y evitó la inferencia de
captura que usaron Mem0 inferred, Graphiti y ShadowFrog en este ensayo.** Mem0 raw
también evitó esas llamadas e igualó la precisión. El historial completo empató.
Esto demuestra una ventaja concreta de adquisición frente a los perfiles con
inferencia; no una superioridad general de precisión o productividad.

Evaluación ejecutada el 17 de octubre de 2026. Modelo nativo `gpt-6.1-sol`, con
herramientas desactivadas. Los perfiles comparten generador, ejecutor, presupuesto,
fuentes históricas y recuperación de artefactos citados. Cada brazo y repetición
usa memoria independiente. Ningún candidato se aplica al checkout.

## Resultado reservado

Cuatro identidades de tarea reservadas, dos ejecuciones cada una. Dos tareas exigen
reparación compatible y dos abstención por política retirada o firma cambiada.
Son ocho ejecuciones, no ocho problemas independientes.

| Perfil | Correctas | Reparaciones correctas | Abstenciones correctas | Parches incorrectos | Llamadas LLM de captura¹ | Llamadas LLM de uso |
|---|---:|---:|---:|---:|---:|---:|
| Synopsis, testigos | 8/8 | 4/4 | 4/4 | 0 | 0 | 8 |
| Mem0, inferencia | 8/8 | 4/4 | 4/4 | 0 | 8 | 8 |
| Mem0, raw | 8/8 | 4/4 | 4/4 | 0 | 0 | 8 |
| Graphiti, híbrido RRF | 8/8 | 4/4 | 4/4 | 0 | 25 | 8 |
| ShadowFrog, archivo/símbolo | 8/8 | 4/4 | 4/4 | 0 | 4 | 8 |
| Historial completo | 8/8 | 4/4 | 4/4 | 0 | 0² | 8 |
| Sin memoria | 4/8 | 0/4 | 4/4 | 0 | 0 | 8 |

¹ Captura una vez por tarea; reutilizada en ambas repeticiones. Las llamadas no son
tokens ni dólares. ² El historial ya se suministra como un array; no medimos su
adquisición real. Cero regresiones escapadas en los siete brazos. El brazo sin
memoria se abstuvo en todas las tareas; sus cuatro fallos son reparaciones ausentes,
no parches dañinos. El piloto de desarrollo tuvo 4/4 en todos los brazos con memoria
y 0/4 sin memoria. Se conserva completo y se considera exploratorio.

La captura observada de los cuatro testigos reservados tomó 0,149 s; Mem0 raw
0,617 s, Mem0 inferred 61,391 s, Graphiti 210,454 s y ShadowFrog 36,442 s en sus
rutas de adquisición medidas. Son observaciones de una máquina compartida, con
cachés y ejecuciones concurrentes; no constituyen una clasificación estable de
velocidad. El JSON incluye tiempos de recuperación p50/p95 y fases por separado.

## Qué se comparó realmente

- **Mem0 OSS 2.2.1**, revisión auditada `0724291bd864cf807e88ee8981c8226644e8fb42`:
  SDK real, Qdrant local y FastEmbed, tanto `infer=True` como `infer=False`.
  Procedencia en metadata, búsqueda con `explain=True`. Sin extra spaCy; se registró
  el fallback. No extrapolar al servicio administrado o a otra configuración.
- **Graphiti 0.31.1**, revisión auditada `d50741d1bf463cbe3859eb73914cbff1b66839e6`:
  SDK real, FalkorDB embebido independiente, `search_` con receta híbrida RRF de
  episodios, nodos y aristas. Los UUID de episodio permiten recuperar la fuente.
  El wrapper embebido emitió una advertencia de cleanup asíncrono; no hubo errores
  de adquisición/recuperación ni inferencia en las tareas completadas.
- **ShadowFrog**, revisión `1f6e615c2ddfeffa8ba709401afafa1e9ffa9452`: captura nativa
  siguiendo su skill oficial, Markdown por archivo/símbolo, viewer oficial y lectura
  del archivo relevante. Adaptador acotado; no ejecutamos init, hooks del IDE ni Dream.
  No hubo commits, pushes o publicación. No es una comparación del producto completo.
- **Synopsis**: captura observada desde aserciones reales y búsqueda por función,
  revisión del alcance y reproducción. El contrato y fuentes históricos se ofrecen
  a todos mediante la misma ronda de recuperación de fuente. Todos pueden usar el
  mismo controlador de testigos; no atribuimos su beneficio solo al buscador.

Mem0 y Graphiti usan el mismo modelo multilingüe MiniLM de 384 dimensiones. Cada
framework conserva sus algoritmos reales con un adaptador del proveedor LLM nativo.
No empleamos un simulador de recuperación ni respuestas de otro brazo.

## Protocolo y limitaciones

El [protocolo](competitive_protocol.json) se congeló antes de implementar los
testigos: SHA256 `b45ef7d6cca28665d3226994687e10ff97f7c92ab9d6544bd81fd127a4fafb63`.
El [corpus](competitive_corpus.json) se congeló antes de adquirir/evaluar memoria:
SHA256 `5732263daf32b563237eefb873eb6ebb0bba8d7bb31909a276695b2293c88ec7`.
Incluye cuatro familias: números por modo, secuencias estables, límites de identidad
de texto y merge parcial. Los inputs/expectativas ocultos solo entran al evaluador
del host; el ejecutor recibe llamadas, no sus resultados esperados.

Las tareas son sintéticas y pequeñas; hay solo cuatro identidades reservadas, todas
de familias conocidas. Tres familias mantienen el mismo algoritmo entre semillas.
Las fuentes relevantes son explícitas y la ronda de source-fetch es competente:
no mide descubrir conocimiento remoto entre millones de documentos. El orden del
corpus coloca el artefacto del componente antes de los distractores. No hay
significación estadística, issues OSS reales, ensayo longitudinal o trabajo en equipo.

En desarrollo detectamos que `--top` del viewer de ShadowFrog solo muestra bug/security;
se corrigió a búsqueda y lectura del archivo antes de evaluar sus parches. Conservamos
el recibo inicial. También eliminamos texto duplicado de recuperación/fuente antes de
las tareas reservadas; todos sus brazos usan el mismo controlador corregido. Las
primeras trazas de desarrollo se conservan con esa diferencia documentada.

La conclusión práctica es **usar captura estructurada sin inferencia cuando existen
observaciones y alcance concretos**. Mem0 raw y el historial completo muestran que
almacenar bien el contexto ya resuelve estos casos. Los testigos añaden reproducción,
procedencia y control de regresión al producto; aquí no obtuvieron más aciertos que
esos controles. No afirmamos que el mecanismo nunca haya existido ni que erradique
alucinaciones. Para demostrar superioridad más amplia faltan tareas reales y largas,
costes de mantenimiento y mediciones con distintos modelos y lenguajes.

## Reproducir y auditar

[Resumen JSON](competitive_results.json) · [Recibos y trazas completas](../research_notes/competitive_v10/)
con manifiesto SHA256, propuestas, resultados originales/candidatos, errores y límites.
El repositorio incluye generador de corpus, adaptadores y controlador. Las versiones
de SDK son las auditadas arriba; no se instalan al usar Synopsis.

```sh
python3 tools/competitive_benchmark.py prepare --base /tmp/synopsis-eval-nuevo
# Repetir para mem0-inferred, mem0-raw, graphiti, shadowfrog-file-symbol y ambos splits:
/ruta/venv/bin/python tools/competitive_sdk.py --base /tmp/synopsis-eval-nuevo --profile mem0-raw --split reserved
# Repetir para los siete perfiles (preparar antes el SDK correspondiente):
python3 tools/competitive_benchmark.py evaluate --base /tmp/synopsis-eval-nuevo --profile mem0-raw --split reserved --repetitions 2
python3 tools/summarize_competitive.py --base /tmp/synopsis-eval-nuevo
```

Los adaptadores del experimento señalan las rutas locales de caché/clones usadas;
hay que ajustarlas en otra máquina. La captura SDK permite hasta 40 llamadas por
perfil. Todos los intentos quedan registrados; repetir no pisa resultados existentes.
