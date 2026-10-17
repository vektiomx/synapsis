---
description: Busca en la memoria y en las notas del proyecto qué se sabe de un tema, dice qué leer primero y avisa los datos viejos. Usalo antes de empezar una tarea sobre algo que puede estar anotado, y cuando el usuario pregunte qué se sabía de un tema.
argument-hint: "[tema]"
allowed-tools:
  - Bash(synopsis --sobre*)
  - Bash(sh "${CLAUDE_PLUGIN_ROOT}/bin/synopsis" --sobre*)
  - PowerShell(synopsis --sobre*)
  - PowerShell(& "${CLAUDE_PLUGIN_ROOT}/bin/synopsis.cmd" --sobre*)
---

Buscá el tema en las notas con Synopsis:

```
synopsis --sobre "$ARGUMENTS"
```

Si la consola no encuentra `synopsis`, corré `sh "${CLAUDE_PLUGIN_ROOT}/bin/synopsis" --sobre "$ARGUMENTS"`, o en PowerShell
`& "${CLAUDE_PLUGIN_ROOT}/bin/synopsis.cmd" --sobre "$ARGUMENTS"`.

Cómo usar lo que devuelve:

- **Para leer primero:** abrí esas notas con Read desde la línea que indica, antes de tocar nada.
- **⚠ dato viejo:** el médico comprobó que ese dato ya no vale y dice el actual. Usá el actual y, si importa, confirmalo
  en el código.
- **⚠ puede que ya esté resuelto:** un commit posterior toca lo mismo que ese renglón, pero nadie lo comprobó. Mirá el
  código antes de dar el dato por bueno o por viejo.
- **cambió el 6/10 a las 08:55 (línea 84); antes decía: «…»:** ese renglón se reescribió ese día y eso es lo que
  decía antes. Vale lo que dice hoy; si otra nota o tu resumen todavía tienen el dato de antes, es el viejo.
- **Para comprobar en el código:** son los archivos que nombran esas notas, con la ruta entera. Abrí el que venga al
  caso; si ninguno es, seguí buscando.
- Si no encontró nada, decilo en una línea y seguí con la tarea.
- Si el usuario se acuerda de algo anotado que ya no aparece, puede haberse borrado: `synopsis --historial "texto"`
  dice cuándo se borró, de qué nota y qué decía.
- Si pregunta qué se sabía un día («¿qué decíamos de esto la semana pasada?»), `synopsis --sobre "tema" --al 6/10`
  responde con la memoria como estaba ese día (la fecha va como `2026-10-06`, `6/10` o `"6/10 18:30"`).
- Si pregunta desde cuándo un dato es así o qué decía antes una nota, `synopsis --cambios NOTA` lo saca del
  historial: qué decía, qué pasó a decir y cuándo (sin nota, qué notas cambiaron en los últimos 2 días).
- Si se acuerda de algo que se habló en una charla pero nunca se anotó, `synopsis --charlas "palabras"` lo busca en
  las charlas viejas (lo que escribió el usuario y lo que respondió Claude).

No copies en tu respuesta el texto entero de la salida: usalo para trabajar.
