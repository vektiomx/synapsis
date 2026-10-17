# progress/ — qué recuerda el agente

Memoria entre sesiones. Un agente no recuerda conversaciones anteriores: lo que no quede escrito aquí se pierde.

| Archivo | Contenido | Cuándo se lee | Cuándo se escribe |
|---|---|---|---|
| [decisions.md](decisions.md) | Decisiones **vigentes**: qué se eligió, por qué, si está confirmado o es supuesto | Al empezar cualquier tarea no trivial | Cuando el usuario confirma algo o se elige entre alternativas |
| [history.md](history.md) | Bitácora cronológica: qué se hizo, qué se validó, qué quedó pendiente | Solo cuando hace falta contexto de una sesión anterior | Al cerrar cada vuelta del [loop](../playbooks/playbook_session_loop.md) |

Los dos se escriben **en inglés**. No incluyen secretos, credenciales, teléfonos ni datos operativos sensibles.

## Versionado

`decisions.md` e `history.md` son **por desarrollador** y están fuera de git mediante `.git/info/exclude`. Este README sí se versiona. En un clon nuevo, si no existen, el agente los crea vacíos con el encabezado y formato de abajo.

## Qué va en cada uno

- **Decisión** (`decisions.md`): algo que debe seguir siendo cierto en la próxima tarea. "Los recordatorios solo van a RRHH." Si deja de ser cierto, se marca `superseded` y se enlaza a la nueva; no se borra.
- **Historial** (`history.md`): algo que pasó. "Se corrieron 19 tests, pasaron." "Se movió X a Y." No se reescribe; solo se agrega al final.
- Si dudas: si un agente futuro podría tomar una mala decisión por no saberlo, es decisión.

## Formatos

### Decision entry

```markdown
### D-0NN · Título corto
- **Decision:** qué se decidió, concreto y verificable.
- **Status:** confirmed | assumption | superseded · YYYY-MM-DD · (supersedes D-0XX / superseded by D-0YY)
```

Numeración correlativa; nunca reutilizar un número.

### History entry

```markdown
## YYYY-MM-DD · Título de la tarea

- Done: qué cambió (archivos/capas, no el diff completo).
- Validated: comandos ejecutados de verdad y resultado. Nunca inventar cifras.
- Not validated: qué no se pudo comprobar y por qué.
- Pending: lo que quedó abierto (también va a `tasks/`).
- Decisions: D-0NN añadidas o modificadas.
```

## Mantenimiento

Cuando `history.md` supere ~40 KB (unos 20,000 tokens, debajo del tope de lectura de un agente), mover las entradas más viejas, completas y sin reescribirlas, a `history_YYYY-MM.md` en esta misma carpeta (el mes de las entradas movidas; si ya existe, agregarlas al final). Dejar en `history.md` al menos los dos últimos días y una línea de enlace al inicio. Los archivos `history_*.md` también son por desarrollador y van en `.git/info/exclude`. Los informes largos de una tarea (diagnósticos, planes por fases) no van aquí: van a [archive/](../archive/README.md).
