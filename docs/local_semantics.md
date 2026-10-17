# Semántica local de Synopsis 0.8

`sh bin/synopsis install --all` prepara por defecto los conectores y un venv privado
con FastEmbed 0.9.0 y el modelo ONNX cuantizado
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. La primera preparación
requiere internet y descarga aproximadamente 220 MB de modelo más dependencias.
La inferencia posterior funciona en CPU sin claves ni proveedor remoto.

El modelo representa 50 idiomas en 384 dimensiones y limita cada entrada a 128
tokens ([ficha oficial](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)).
Son capacidades del modelo, no resultados de Synopsis en todos esos idiomas. Cada
experiencia tiene dos fragmentos compactos; texto largo puede perder detalles.

`--no-semantic` omite la preparación; `SYNOPSIS_SEMANTIC_SETUP=off` permite instalar
sin red. Un fallo de descarga deja recuperación léxica y un diagnóstico pendiente,
no impide usar el resto. `synopsis semantic setup` reintenta y `synopsis semantic status`
consulta la instalación. `SYNOPSIS_EMBEDDINGS=off` desactiva embeddings. El modo auto
prefiere este runtime y conserva la alternativa Ollama local ya compatible.

El runtime vive en `~/.local/share/synopsis/semantic`, independiente de la carpeta
configurable de datos; `SYNOPSIS_SEMANTIC_HOME` permite reubicarlo. No se instala en
el Python del sistema. Los pesos y dependencias no se incluyen en el ZIP de código.
Las huellas de los archivos de modelo y versiones del entorno forman la identidad
del índice. El worker comprueba las huellas al arrancar y carga sin red.

El worker escucha solo en 127.0.0.1 con puerto efímero, token privado y sin proxy HTTP.
Los metadatos y token se escriben con modo 0600, carpeta 0700; las solicitudes están
acotadas y serializan inferencia. No registra consultas ni las envía a un servicio
externo. Se apaga tras 30 minutos de inactividad y vuelve a arrancar bajo demanda.
No ofrece aislamiento frente a otro proceso que ya controle la misma cuenta.

Las experiencias mantienen vectores por proyecto, identidad de backend y hash del
fragmento en SQLite privado. No guardan consultas ni sus vectores. Cada llamada
prepara hasta 64 fragmentos ausentes sobre un máximo de 2048 casos; puede responder
`warming`. El mantenimiento del mapa recorre hasta cuatro proyectos por pasada de
30 segundos. Conserva hasta 8192 vectores por proyecto con LRU. Los hashes de texto
actual evitan reutilizar un fragmento viejo; una consulta por archivo no elimina
los vectores vigentes de otros archivos.

BM25 y anclajes técnicos siguen disponibles durante preparación o fallo. El umbral
coseno 0.48 solo admite candidatos semánticos; no es probabilidad de corrección.
La fusión RRF ordena relevancia. La validación de condiciones, fuentes y conflictos
se realiza después e independientemente. Ninguna similitud certifica una decisión.

FastEmbed y el modelo son componentes existentes con licencia Apache-2.0;
[FastEmbed oficial](https://github.com/qdrant/fastembed). La contribución de Synopsis
es su integración local, recuperación con límites y ciclo de experiencia comprobable;
no se reivindica haber inventado embeddings, BM25 o RRF.
