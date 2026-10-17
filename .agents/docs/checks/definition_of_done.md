# Definición de terminado

## Automáticos según alcance

- [ ] Revisar diff y `git diff --check`; incluir `--cached` si corresponde.
- [ ] Ejecutar pruebas pertinentes de [testing](../core/testing.md). Código compartido
  requiere la suite completa; instalación requiere contratos de escritorio; empaquetado
  requiere test_release. Para docs puras basta revisión de enlaces y coherencia.
- [ ] Cambios amplios del motor: humo del motor cuando sus contratos estén afectados.
- [ ] Compatibilidad nativa solo se declara con evidencia del sistema/CI correspondiente.
- [ ] No debilitar pruebas ni aislamiento. Un skip se informa como tal.

## Reglas del diff

- [ ] Conserva datos, revisiones, procedencia, conflictos y configuración ajena.
- [ ] Pruebas sin perfiles, credenciales, proveedores o servicios reales del usuario.
- [ ] Instalación reversible, portable y sin privilegios extra por defecto.
- [ ] Sin promesas de veracidad o superioridad no demostradas.
- [ ] Procedimientos en `.agents/docs/`; adaptadores breves; docs de producto enlazadas.
- [ ] Estado local excluido de Git y de archivos de entrega.

## Arnés y reporte

- [ ] current refleja el resultado; historial registra comprobaciones reales en inglés.
- [ ] Decisiones nuevas registradas con status y origen; pendientes conservados sin
  iniciarlos automáticamente. Restablecer current a Estado: none al cerrar.
- [ ] Si se usó memoria Synopsis, comprobar el recibo de cierre con el alcance correcto;
  no duplicar documentación ni mezclar proyectos.
- [ ] No publicar sin instrucción explícita para la tarea actual.

Reportar qué cambió, qué se probó, qué quedó sin validar y supuestos abiertos.
Para tareas no triviales, incluir cinco preguntas técnicas del discovery.
