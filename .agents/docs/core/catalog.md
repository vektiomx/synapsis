# Catálogo de Synopsis

Índice de entradas existentes, no certificación de corrección ni de pruebas ejecutadas.
Las rutas de producto son fuentes canónicas: actualizar allí el comportamiento.

| Necesidad | Código o procedimiento | Documentación |
|---|---|---|
| Empezar o retomar | [Loop](../playbooks/playbook_session_loop.md) | [Tareas](../tasks/README.md), [decisiones](../progress/README.md) |
| Planear y revisar | [Discovery](../playbooks/playbook_discovery_first.md), [revisión](../playbooks/playbook_solid_review.md) | [Cierre](../checks/definition_of_done.md) |
| Arquitectura | `engine/`, `comun.py`, `integration_setup.py` | [Arquitectura](../../../docs/architecture.md) |
| Memoria y vinculación | `engine/memory_store.py`, `engine/memory_cycle.py` | [Continuidad](../../../docs/continuity.md), [proyectos](../../../docs/project_binding.md) |
| Evidencia y modelos | `engine/controlled_run.py`, `engine/model_provider.py` | [Evidencia](../../../docs/evidence_guard.md), [modelos](../../../docs/models.md) |
| Recuperación y experiencias | `engine/decision_rag.py`, `engine/behavior_memory.py` | [DecisionRAG](../../../docs/decision_rag.md), [comportamiento](../../../docs/behavior_memory.md) |
| Investigación | `engine/research_workbench.py` | [Workbench](../../../docs/research_workbench.md) |
| Semántica | `semantic_setup.py`, `engine/semantic_memory.py` | [Semántica local](../../../docs/local_semantics.md) |
| Clientes e instalación | `integration_setup.py`, `integration_health.py`, `desktop_service.py` | [Instalación](../../../README.md), [escritorio](../../../docs/desktop_adaptation.md) |
| Pruebas | `tests/`, `engine/herramientas/prueba_humo.py` | [Testing](testing.md) |
| Entrega | `tools/build_release.py` | [Estado](../../../docs/development.md), [evaluación](../../../docs/competitive_evaluation.md) |

Al cambiar un recurso, comprobar su definición y consumidor antes de actualizar
esta ficha. No copiar informes ni decisiones históricas como reglas vigentes.
