# Loop de sesión

## 0. Orientar

Leer [AGENTS.md](../../../AGENTS.md), `tasks/current.md` y `progress/decisions.md`.
Si falta estado local, crearlo desde los README de [tasks](../tasks/README.md) y
[progress](../progress/README.md). Retomar la tarea activa desde `Now`.

## 1. Tomar tarea

Registrar Goal, Request y Done when. Incorporar aclaraciones a la tarea activa.
Ante un cambio explícito de objetivo, conservar la tarea previa en backlog.
Preguntar solo si la prioridad es ambigua. No empezar el backlog por cuenta propia.

## 2. Planear

Para tareas no triviales aplicar [discovery](playbook_discovery_first.md), consultar
el [catálogo](../core/catalog.md) y escribir pasos verificables en Plan.
Cambios triviales inequívocos de una línea pueden omitir el plan, nunca la validación.

## 3. Hacer un paso

Actualizar Now antes de editar. Implementar solo el paso previsto, preservando cambios
ajenos y los invariantes de memoria, instalación y aislamiento de Synopsis.

## 4. Validar

Aplicar los checks pertinentes de [definition_of_done](../checks/definition_of_done.md).
Si falla, registrar en Attempts el error, lo cambiado y la hipótesis. Corregir y validar.
Tras tres fallos consecutivos del mismo paso, aplicar [escalation](../checks/escalation.md).
Un check omitido no cuenta como aprobado.

## 5. Registrar

Marcar el paso y actualizar Now. Registrar decisiones durables en decisions y evidencia
en history, en inglés. No esperar al fin de la sesión: el estado debe permitir reanudar.

## 6. Repetir

Si quedan pasos, volver a 3. Si cambia el plan, actualizarlo antes de continuar.
Conservar un checkpoint antes de compactar contexto o interrumpir la sesión.

## 7. Cerrar

Pasar definition_of_done, registrar historial, dejar pendientes en backlog y restablecer
current a Estado: none. Informar cambios, validación real, límites y cinco preguntas
 técnicas de discovery cuando corresponda. No iniciar otra tarea autónomamente.
No hacer commit, push o PR sin pedido explícito del usuario para esa acción y tarea.
