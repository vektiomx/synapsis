# Adopción del arnés de desarrollo

Se adoptó la estructura de Meximova con reglas de Synopsis: `.agents/docs/`, loop,
discovery-first, tareas, decisiones, historial, catálogo, checks y adaptadores breves.
El contenido Python y multiplataforma reemplaza las normas Laravel del proyecto origen.
`docs/` conserva la documentación canónica de producto.

El estado por desarrollador queda fuera de Git mediante el exclude resuelto por Git,
y fuera del ZIP mediante el generador de entregas. Las plantillas sí se distribuyen.
No se copiaron datos o decisiones de Meximova. No se hicieron commit, push ni PR.

## Validación ejecutada

- Empaquetado: 2/2 tests, reproducibilidad/manifiesto y exclusión de estado local.
- Enlaces: 64 rutas relativas en 23 documentos antes de este informe, todas resueltas.
- Adaptadores: nueve skills válidas de cinco líneas y tres comandos TOML válidos.
- Exclusiones locales y revisión de espacios: correctas.
- No ejecutado: descubrimiento/recarga dentro de cada IDE; suite completa y humo no
  requeridos porque no se modificó el runtime, los instaladores ni el motor de memoria.

## Cinco preguntas para revisión técnica

1. ¿La separación entre procedimientos en `.agents/docs/` y documentación de producto
   enlazada en `docs/` conserva una fuente única para cada tema?
2. ¿El inicio de sesión desde `tasks/current.md`, `Now` y `progress/decisions.md`
   permite retomar el trabajo sin depender de la conversación anterior?
3. ¿Los checks de Python y escritorio cubren el alcance real sin heredar obligaciones
   Laravel que Synopsis no utiliza?
4. ¿La exclusión independiente en Git y ZIP protege el estado local y mantiene las
   plantillas disponibles para otros desarrolladores?
5. ¿Los adaptadores breves y el catálogo hacen visible dónde cambiar cada procedimiento
   sin duplicarlo entre asistentes?
