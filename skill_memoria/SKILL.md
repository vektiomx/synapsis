---
name: memoria-synapsis
description: >-
  Memoria persistente entre charlas, compartida con las demás herramientas de IA que
  uses en este equipo (Claude Code, Codex, Antigravity). Úsala para consultar lo que ya
  se decidió antes de responder, y para guardar algo que convenga recordar en charlas
  futuras — una decisión, un porqué, una regla de negocio no obvia, una corrección que
  te hicieron. No es solo para este chat: lo que guardes aquí lo va a ver cualquiera de
  las 3 herramientas la próxima vez.
---

# Memoria compartida (Synapsis)

## Antes de responder sobre algo que puede tener historia

Si el pedido puede tocar una decisión ya tomada, una regla de negocio, o algo que ya se
discutió antes (en este chat o en otro, con esta herramienta o con otra), consultá
primero:

```sh
neuromapa --sobre "<tema, en pocas palabras>"
```

Te dice qué notas leer primero, si hay datos que pueden estar viejos, y qué decisiones
anotadas tocan el tema. Si no tenés `neuromapa` en el PATH, buscá a mano en
`~/.claude/projects/*/memory/` (son archivos `.md`).

## Cuándo guardar algo nuevo

Guardá una nota cuando:
- El usuario te corrige algo y te dice cómo debería haber sido ("no, eso no, hacelo
  así porque...").
- El usuario confirma que un enfoque poco obvio estuvo bien (una decisión que no
  volverías a adivinar sola).
- Aprendés una regla de negocio, una convención del proyecto, o un motivo detrás de
  una decisión que no está en el código ni en la documentación.

No guardes: detalles de la tarea de ahora, nada que ya esté en el código o en los
archivos de documentación del proyecto, ni nada que puedas derivar leyendo el repo.

## Cómo guardar (un archivo .md, nada más)

1. Elegí la memoria del proyecto correcto: `~/.claude/projects/<carpeta-con-guiones>/memory/`,
   donde `<carpeta-con-guiones>` es la ruta absoluta del proyecto con cada `/`
   cambiado por `-` (ej. `/var/www/proyecto` → `-var-www-proyecto`). Si la carpeta
   `memory/` no existe, creala.
2. Escribí un archivo nuevo ahí, `<nombre-corto>.md`, con este formato:

   ```markdown
   ---
   name: nombre-corto
   description: "una línea: para qué sirve esta memoria"
   metadata:
     type: feedback   # o: user, project, reference
   ---

   La regla o decisión en sí. Después:

   **Por qué:** el motivo que dio el usuario.

   **Cómo aplicarla:** cuándo usar esto en el futuro.
   ```
3. Sumá una línea al índice `~/.claude/projects/<carpeta>/memory/MEMORY.md`:
   `- [Título](nombre-corto.md) — gancho corto de una línea`. Si `MEMORY.md` no
   existe, creala con ese formato.

No hace falta ninguna herramienta especial para esto — es un archivo de texto normal,
con las herramientas de archivo que ya tenés.
