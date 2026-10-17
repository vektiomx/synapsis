# Modelos, semántica y conciliación

## Uso sin adaptador

```bash
synopsis run --project /ruta/proyecto --prompt 'Recuerda la decisión sobre caché'
synopsis run --project /ruta/proyecto --provider codex --prompt '¿Qué decidimos?'
synopsis run --project /ruta/proyecto --provider ollama --model qwen3 --prompt 'Continúa'
synopsis providers
```

`auto` respeta SYNOPSIS_PROVIDER, busca un modelo generativo instalado en Ollama y,
si no existe, un cliente Codex, Claude u OpenCode instalado. Cada cliente usa su cuenta
actual. Codex utiliza el modelo predeterminado de la CLI o --model; los otros
conectores usan el modelo del cliente o --model. Detectar el ejecutable no demuestra autenticación.
No instala modelos, compra suscripciones ni cambia el modelo de tu IDE. Puedes usar
`--model` para elegir entre los modelos habilitados por tu proveedor.

Los conectores nativos son inferencia sin edición de archivos: Codex usa sandbox de
lectura y desactiva shell, colaboración y búsqueda; omite la configuración personal
para esa inferencia, manteniendo autenticación y --model; Claude desactiva herramientas; OpenCode deniega permisos y excluye plugins
externos. Synopsis aplica las operaciones de memoria después de validarlas. El
proyecto y PWD se pasan explícitamente para evitar mezclar raíces. La disponibilidad
varía por cliente, cuenta y versión; un endpoint puede restringir usos específicos.
`provider_subscription_required` y `provider_usage_restricted` indican una restricción
del servicio, no una escritura fallida. El turno queda visible para recuperarlo.

También puedes usar APIs directamente:

| Proveedor | Variables necesarias | Protocolo |
|---|---|---|
| openai | OPENAI_API_KEY, SYNOPSIS_MODEL | Responses; store=false |
| compatible | SYNOPSIS_API_BASE, SYNOPSIS_MODEL; SYNOPSIS_API_KEY si requiere clave | Chat Completions JSON |
| ollama | Modelo local; OLLAMA_HOST opcional | /api/chat, sin streaming |

Elige `--provider openai` o `--provider compatible` para APIs remotas. Los secretos
se leen del entorno; no se escriben en la memoria ni aparecen en providers/doctor.
Fuera de loopback se exige HTTPS. No se siguen redirecciones con credenciales. Se
aplican límites de tiempo y salida; los errores no imprimen respuestas crudas del
proveedor. `--timeout` acepta 1–600 segundos.

Los conectores entregan evidencia, estado de trabajo e inventario de notas actuales
al modelo. Un modelo puede incumplir el contrato o proponer información incorrecta;
Synopsis valida la estructura y permite una única corrección dentro del tiempo restante,
antes de escribir. No reintenta errores de cuenta, red o disponibilidad.
En v2 el borrador no se publica: el controlador construye una salida extractiva
con citas comprobadas o se abstiene. Retiene la salida si no puede cerrar el ciclo. Los recibos prueban la
persistencia de las propuestas, no su veracidad. No se reintenta una inferencia en
otro proveedor automáticamente después de enviar datos a uno.

## Recuperación híbrida

El modo textual funciona sin modelos ni dependencias externas. La búsqueda añade
embeddings reales si descubre en Ollama local un modelo de embeddings instalado.
No descarga modelos sin avisar ni envía notas a un servidor remoto por defecto.
BM25 y similitud coseno se fusionan por posiciones (reciprocal rank fusion). La
utilidad histórica solo ajusta candidatos con evidencia.

Configuración opcional:

| Variable | Valor |
|---|---|
| SYNOPSIS_EMBEDDINGS | auto (predeterminado), off, ollama o compatible |
| SYNOPSIS_EMBEDDING_MODEL | Nombre del modelo; auto descubre embed/nomic/bge locales |
| SYNOPSIS_EMBEDDING_BASE | Endpoint compatible, con base /v1 cuando corresponda |
| SYNOPSIS_EMBEDDING_KEY | Clave para embeddings compatibles; no se guarda |
| SYNOPSIS_SEMANTIC_THRESHOLD | Coseno mínimo, 0.3–1; predeterminado 0.72 |

Para Ollama remoto, selecciona explícitamente ollama y define OLLAMA_HOST con HTTPS.
Para un servicio externo compatible, selecciona compatible, base y modelo. Esta
configuración autoriza que las notas elegibles y consultas del proyecto se envíen
al proveedor elegido. La política de datos del proveedor también aplica.

La caché SQLite vive en la memoria del proyecto, dentro de `.synopsis/vectors.sqlite3`.
Se separa por proveedor/modelo/endpoint y SHA-256 del fragmento. Los vectores de las
consultas no se persisten. Notas ajenas, vencidas, archivadas o editadas desde el
índice no entran al proveedor. Se vuelven a comprobar antes de emitir sus citas.

Cada recuperación procesa hasta 512 secciones y calienta hasta 64 vectores nuevos.
La primera consulta a un corpus grande puede declarar warming; ready indica que los
fragmentos elegidos ya están disponibles. unavailable o degraded conserva la búsqueda
textual. El límite por petición de embeddings es de tres segundos para no bloquear
los hooks; un modelo local frío puede necesitar otra consulta tras cargar.

El umbral predeterminado es conservador, no una calibración universal. Cada modelo
de embeddings requiere evaluar recuperación y abstención con su corpus. Las pruebas
con vectores controlados verifican el algoritmo, no certifican comprensión del modelo.

## Conciliación revisable

```bash
synopsis reconcile --project /ruta/proyecto --output /tmp/conciliacion.json
# Inspecciona el resumen, findings y cada reemplazo completo en actions.
synopsis reconcile --project /ruta/proyecto --apply /tmp/conciliacion.json
```

La primera operación consulta un modelo y genera un plan; no modifica notas.
Reutiliza --provider, --model y --timeout. El inventario está limitado a 100 notas
activas, versionadas y sin ediciones externas, con un presupuesto de 48 000 caracteres.
No es una auditoría exhaustiva de corpus mayores. Las notas excluidas no se atribuyen
al modelo como si las hubiera revisado.

El plan cita archivos, revisiones y huellas. Aplicar comprueba el proyecto, las
versiones y la huella de cada nota afectada. Las contradicciones reportadas bloquean
cambios sobre sus notas; no se escoge un ganador sin una corrección explícita. Archivar
un duplicado exige otra nota superviviente. Ninguna operación elimina el historial ni
convierte la inferencia del conciliador en confirmación del usuario.

La equivalencia de significado es una propuesta del modelo y debe revisarse. Las
comprobaciones estructurales impiden cambios obsoletos y algunos errores de plan;
no prueban que una fusión conserve todas las sutilezas. Los lotes se aplican por
operación: si una parte falla, `cycle status` muestra lo aplicado y lo pendiente.
Un plan totalmente aplicado no se vuelve a aplicar sobre sus nuevas revisiones.

## Experiencias

`synopsis learn --project /ruta/proyecto --file test-experience --source agent:test`
lee JSON por stdin:

```json
{
  "task": "Validar la retención de caché",
  "action": "Ejecutar las pruebas de caducidad",
  "outcome": "Las pruebas aprobaron con 300 segundos",
  "evidence": [{"path": "artifacts/test-result.txt", "sha256": "HUELLA_SHA256_REAL_DEL_ARCHIVO"}],
  "limitations": "Resultado de este entorno; no demuestra el rendimiento en producción."
}
```

La evidencia debe estar dentro del proyecto, no ser sensible, medir hasta 2 MB y
coincidir con su SHA-256. El resultado se conserva como referencia inferred, con
procedencia y límites. No se almacenan archivos completos ni se transforma el relato
del agente en verdad universal. La huella registra la versión observada; revisa la
evidencia antes de extrapolar una experiencia a otra tarea.

## Verificar

```bash
python3 -B -m unittest discover -s tests
python3 -B tools/evaluate_memory.py
python3 -B tools/evaluate_continuity.py --provider codex
python3 -B tools/evaluate_reconciliation.py --provider codex
# O elige dos modelos habilitados de un proveedor:
python3 -B tools/evaluate_continuity.py --provider opencode --model proveedor/modelo-a --second-model proveedor/modelo-b
```

La evaluación real usa cuatro ejecuciones con rondas acotadas de evidencia,
hechos ficticios, HOME temporal y una
comparación sin memoria. Copia temporalmente las credenciales nativas necesarias,
con permisos privados, y las elimina al terminar. No accede al contenido de proyectos
reales ni modifica su configuración. No es un benchmark general de inteligencia.
Los errores de cuenta o contrato hacen fallar la evaluación; no se cuentan como éxitos.

Referencias de implementación:
[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[OpenAI Embeddings](https://developers.openai.com/api/reference/resources/embeddings/methods/create),
[Ollama Chat](https://docs.ollama.com/api/chat),
[Ollama Embeddings](https://docs.ollama.com/api/embed),
[OpenCode CLI](https://opencode.ai/docs/cli/),
[Codex no interactivo](https://learn.chatgpt.com/docs/non-interactive-mode).


Para comprobar el transporte de embeddings con inferencia local real, existe
`tools/evaluate_embeddings.py`. Requiere FastEmbed en un entorno de pruebas aparte y
un `--cache` explícito; la descarga del modelo es deliberada. No es una dependencia
del producto. La corrida BGE-small de esta versión aprobó cuatro consultas en inglés
con umbral 0.60, distinto del predeterminado conservador 0.72. Ese resultado no implica
calidad multilingüe ni calibración para cualquier otro modelo.


El protocolo controlado actual es v2, con grounding y support por párrafos literales.
La cuarentena, las herramientas y la distinción entre fidelidad a fuentes y verdad
están documentadas en [evidence_guard.md](evidence_guard.md). Los adaptadores v1 deben
actualizarse; no existe una degradación silenciosa que omita la comprobación.
