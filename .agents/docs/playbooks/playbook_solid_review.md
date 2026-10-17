# Revisión de diseño

Aplicar cuando se pide auditar arquitectura/refactorizar o cerrar una capacidad grande.
Leer implementación y consumidores antes de proponer cambios. Detectar responsabilidades
mezcladas, acoplamiento a plataformas, persistencia fuera de sus utilidades, contratos
ambiguos y errores ocultos. Priorizar defectos observables sobre abstracciones nuevas.

Preservar contratos CLI/MCP, datos existentes, rollback y rutas de degradación.
Refactorizar por pasos con pruebas del comportamiento antes/después. No crear interfaces
o capas solo por imitar otro stack. Registrar hallazgos comprobados, riesgos y checks
realmente ejecutados mediante el [loop](playbook_session_loop.md).
