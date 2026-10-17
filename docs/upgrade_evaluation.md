# Evaluación de la mejora 0.8

La comparación previa detectó dos fallos concretos: ranking léxico de experiencias
que no recuperaba relatos de otro idioma y soporte dinámico invalidado por cambios
ajenos a la condición. La mejora combina recuperación híbrida local, condiciones
actuales, actualización conservadora y pruebas de sensibilidad en snapshots.
No se promete un factor 1000 ni superioridad universal.

## Diseño y crítica

1. Recuperar candidatos por significado y términos técnicos; después validar alcance,
   fuentes y conflictos. La similitud no sustituye evidencia.
2. Conservar alternativas opuestas y sugerir la observación que más las distingue.
   Las particiones son declaradas: no se conoce su distribución real.
3. Actualizar con revisión esperada y conservar límites; notas relevantes ya admitidas
   se presentan como fuentes para evitar perder políticas complementarias.
   El revisor sigue siendo un LLM y puede omitir conocimiento.
4. Desafiar tests existentes bajo cambios acotados del contexto. Una prueba que siempre
   pasa es poco discriminante; una sensible tampoco demuestra causalidad general.
5. Preparar semántica en la instalación, con inferencia local y alternativa léxica.
   El primer uso necesita descargar modelo/dependencias; índices grandes calientan por lotes.

El diferenciador que se persigue es memoria de decisiones con condiciones que se
reobservan y tests que se pueden desafiar, dentro de la continuidad automática entre
clientes. BM25, embeddings, RRF, versiones y pruebas de sensibilidad son técnicas
existentes. Esta entrega no establece novedad mundial ni patenta un nuevo paradigma.

## Protocolo y resultados

323 pruebas unitarias y 767/767 comprobaciones integrales aprobadas en Linux.
PowerShell de Windows no se ejecutó en esta máquina. El setup real descargó y cargó
el modelo, aparte de la suite sin red.

La repetición de capturas 0.7 conserva los seis payloads y hashes originales; no
regenera casos a partir de la respuesta esperada. Los 15 estados pasan incluso sin
embeddings: parte de la mejora proviene de BM25 sobre contratos y de separar guardas
dinámicas. Es regresión conocida, no holdout independiente.

El modelo local real separó seis traducciones de negativos y resolvió consultas
ES/EN/PT más abstención ajena al tema (4/4). Dos pruebas reales en bwrap distinguieron
sensibilidad al contexto de una prueba que siempre pasa. Son mecanismos sintéticos
pequeños, no una evaluación de todos los idiomas o repositorios reales.

Las tareas de programación requieren valores de políticas ausentes del código actual.
Se capturan dos turnos por proyecto. Cada brazo genera solo una función pura; el AST
rechaza imports, herramientas, decoradores y acceso a oráculos. Las pruebas ocultas
se crean después de la respuesta y corren sin red en un snapshot. Se comparan tres
brazos: sin memoria, historial pertinente completo y los tres canales de Synopsis.

Los ensayos de desarrollo se conservan: consultar solo DecisionRAG produjo 0/3 porque
las políticas estaban en notas. Con el contexto completo inicialmente dio 1/3 por
omisión de políticas complementarias en la captura. Tras corregir el revisor,
Synopsis y el historial completo resolvieron 3/3; sin memoria se abstuvo en 3/3.
Esto demuestra utilidad en estos casos, no ventaja frente a usar todo el historial
cuando cabe en contexto. Dos tareas adicionales se definieron después de congelar
el código: Synopsis e historial completo resolvieron 2/2 y sin memoria se abstuvo
en 2/2, sin ajustar de nuevo el revisor. Son variantes del mismo mecanismo.

El primer piloto congelado de QA obtuvo Synopsis 5/6, sin memoria 5/6 e historial
completo 6/6. Se mantuvo la respuesta esperada del caso Unicode donde el modelo se
abstuvo. No se descartó ni cambió la etiqueta para mejorar el resultado.

El piloto final mantuvo 5/6 con Synopsis, 5/6 sin memoria y 6/6 con historial
completo. Recuperó 12/12 grupos diagnósticos y seleccionó los seis casos resolubles,
con abstención por falta de contexto o soporte retirado en los otros seis.
Los resultados completos se entregan en `upgrade_evaluation.json`.
Se conservan los ensayos fallidos y los dos pilotos congelados, sin elegir solo la mejor ejecución. El modelo de revisión
y respuesta fue gpt-6.1-sol; el baseline 0.7 anterior no fijaba el modelo del CLI, por
lo que sus diferencias de respuesta no permiten atribución causal solo al código.
Los SDK Mem0/Graphiti no se volvieron a medir en esta entrega: sus resultados siguen
en el informe de comparación previo y no se presenta una victoria sobre ellos.

## Reproducir

```sh
SYNOPSIS_AUTO_REVIEW=0 SYNOPSIS_EMBEDDINGS=off SYNOPSIS_SEMANTIC_SETUP=off python3 -B -m unittest discover -s tests -q
SYNOPSIS_EMBEDDINGS=off python3 -B tools/evaluate_retrieval_upgrade.py --output /tmp/retrieval.json
python3 -B bin/synopsis semantic setup
python3 -B tools/evaluate_local_semantics.py --execute --output /tmp/local.json
python3 -B tools/evaluate_coding_memory.py --model gpt-6.1-sol --output /tmp/coding.json
python3 -B tools/evaluate_coding_holdout.py --model gpt-6.1-sol --output /tmp/holdout.json
python3 -B tools/evaluate_capture_pilot.py /tmp/capture-pilot
```

Las tres últimas pruebas usan inferencia real y la cuenta del CLI configurado; los
números son de una ejecución por brazo, sin intervalos de confianza. Para demostrar
productividad general falta una muestra de issues reales con repositorios congelados,
varios modelos y repeticiones, mismo presupuesto y versiones/perfiles publicados de
cada competidor. El agente sigue siendo responsable de comprobar fuentes y límites.
