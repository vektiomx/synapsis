# Corrección del contrato PreCompact de Claude Code

## Causa

El bridge y hook_cycle construían hookSpecificOutput para casi cualquier evento.
PreCompact no admite ese sobre de contexto; el host rechazaba el JSON antes de
procesar el aviso. Las referencias a documentos de gastos eran contexto de la
sesión y no la causa del fallo de esquema.

## Cambio

hooks_comun.context_output centraliza la salida por evento. PreCompact, Stop y
SubagentStop usan systemMessage; los eventos sin contexto admitido y desconocidos
usan el mismo canal informativo. El bridge conserva el control de permisos solo en
PreToolUse. Los consumidores de contexto del motor, el plugin directo y el bridge
comparten el formateador. No se cierra ningún ciclo por permitir compactar.

[Contrato oficial](https://code.claude.com/docs/en/hooks).

## Validación

- Seis regresiones de contratos por evento y ocho de Stop: aprobadas.
- Pruebas reales del bridge y hook_cycle en HOME privado: PreCompact emite solo
  systemMessage y preserva el ciclo abierto. Permisos de PreToolUse conservados.
- Suite completa: 395 casos, 393 aprobados y 2 omitidos por requerir Windows.
- Humo: 767/767 aprobadas; variante PowerShell nativa omitida en Linux.
- El PreCompact configurado localmente apunta al bridge de este checkout.
- git diff --check: correcto.
- No ejecutado: sesión interactiva completa de Claude ni CI nativa para este diff.
- No se modifican documentos de Meximova, configuración del usuario o ciclos previos.
- Cambios locales; sin commit, push ni PR.

## Cinco preguntas de revisión técnica

1. ¿PreCompact evita el campo hookSpecificOutput que el host rechazó?
2. ¿El plugin directo y el bridge usan el mismo criterio de salida por evento?
3. ¿Los eventos compatibles siguen entregando contexto y los permisos se conservan?
4. ¿Compactar deja los ciclos pendientes intactos y disponibles para reanudación?
5. ¿Las pruebas de Stop siguen impidiendo continuaciones y trabajo en reentradas?
