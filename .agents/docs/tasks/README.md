# tasks/ — qué está haciendo el agente

| Archivo | Contenido |
|---|---|
| [current.md](current.md) | **Una sola** tarea activa: objetivo, criterio de terminado, pasos y en cuál va |
| [backlog.md](backlog.md) | Tareas pendientes, en orden de prioridad |

Antes de crear el estado en un clon nuevo, resolver `git rev-parse --git-path info/exclude`
y añadir sin sobrescribir las entradas existentes:

```gitignore
/.agents/docs/tasks/current.md
/.agents/docs/tasks/backlog.md
/.agents/docs/progress/decisions.md
/.agents/docs/progress/history.md
/.agents/docs/progress/history_*.md
```

Usar la ruta devuelta por Git: un worktree puede tener `.git` como archivo. El generador
`tools/build_release.py` excluye estos mismos archivos del ZIP, independientemente del ignore.

Este README se versiona. `current.md` y `backlog.md` son **locales** (`.git/info/exclude`): cada desarrollador tiene su propio estado. En un clon nuevo el agente los crea con las plantillas de abajo.

## Reglas

1. **Una tarea activa a la vez.** Incorporar aclaraciones a la tarea activa. Si el usuario cambia expresamente de objetivo, conservar el estado anterior en backlog; preguntar solo cuando la prioridad sea ambigua.
2. **El agente actualiza `current.md` al terminar cada paso**, no al final de la sesión. Si la sesión se corta, el siguiente agente retoma desde el último paso marcado.
3. **El agente no toma tareas del backlog por su cuenta.** Solo el usuario decide qué pasa a `current.md`.
4. Al terminar, la tarea se resume en [progress/history.md](../progress/history.md) y `current.md` vuelve a la plantilla vacía.
5. Sin secretos, credenciales ni datos personales.

El ciclo completo está en [playbook_session_loop.md](../playbooks/playbook_session_loop.md).

## Plantilla de `current.md`

```markdown
# Current task

> Estado: none | discovery | in_progress | blocked | done

## Goal
Una oración: qué tiene que existir o funcionar al terminar.

## Request
Pedido literal del usuario (y aclaraciones confirmadas).

## Done when
- [ ] Criterio verificable 1
- [ ] Checks de checks/definition_of_done.md que aplican

## Plan
1. [ ] Paso
2. [ ] Paso

## Now
Paso en curso y siguiente acción concreta.

## Attempts
Fallos de validación en el paso actual (máximo 3 antes de escalar).

## Open questions
Lo que hay que preguntar al usuario. Vacío = nada bloquea.
```

## Plantilla de `backlog.md`

```markdown
# Backlog

Orden = prioridad. El agente no inicia nada de aquí sin que el usuario lo pida.

- [ ] Título · contexto en una línea · origen (fecha / pedido)
```
