# Corrección del bucle de Stop en Claude Code

## Causa y cambio

`additionalContext` en Stop/SubagentStop solicita continuar al modelo, incluso sin
`decision: block`. Los avisos de ciclos y revisión se devolvían por ese canal sin
comprobar `stop_hook_active`. El resultado podía alcanzar el límite de continuaciones
del host. [Contrato oficial](https://code.claude.com/docs/en/hooks#stop).

El bridge de Claude publica los avisos de cierre en `systemMessage`. El runtime
compartido y los hooks directos de ciclo/guardado omiten reentradas activas antes de
trabajar sobre la memoria o el historial. El ciclo limita el aviso de Stop a una
entrega por turno. Los ciclos abiertos no se cierran por permitir terminar al modelo.
La revisión automática y el registro del primer Stop normal se conservan.

## Comprobación

- 8/8 pruebas de regresión: Stop/SubagentStop, ruta directa de plugin, bridge,
  ausencia de efectos en reentradas, preservación de ciclos, separación por sesión
  y eventos UserPromptSubmit no afectados.
- Suite compartida: 389 pruebas; 387 aprobadas y 2 omitidas por requerir Windows.
- El smoke inicial usaba el formato antiguo de Stop y falló cuatro expectativas;
  se adaptó al contrato informativo y ahora exige ausencia de feedback de continuación.
- Un segundo humo detectó que la adaptación del lector se había insertado en el
  helper de choques. Se restauró ese helper y se acotó el cambio a revisar_guardar.
- Humo final: 767/767 aprobadas; la variante nativa PowerShell se omitió en Linux.
- La matriz de CI incluye las regresiones nuevas; todavía no se ejecutó para este diff.
- Instalación local: el comando configurado apunta al bridge de este checkout, por
  lo que leerá el código corregido en su próxima invocación. No se editaron settings,
  registro, servicios ni ciclos existentes del usuario.
- No se ejecutó una charla interactiva completa de Claude, ni una nueva validación
  nativa Windows/macOS, ni commit/push de esta corrección.

## Cinco preguntas de revisión técnica

1. ¿El canal systemMessage permite mostrar pendientes sin pedir otra generación?
2. ¿Las reentradas Stop/SubagentStop terminan antes de modificar memoria o historial?
3. ¿El primer Stop normal sigue registrando actividad y activando revisión automática?
4. ¿Los ciclos y conflictos permanecen abiertos hasta contar con cierre verificado?
5. ¿El bridge y el plugin directo mantienen la misma política sin mezclar sesiones?
