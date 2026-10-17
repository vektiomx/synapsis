# Adaptación de escritorio · macOS y Windows

Trabajo local en feat/reliable-project-memory, sin commits/push/PR.

## Plan y decisiones

1. Mantener rutas actuales de datos y overrides SYNOPSIS_ROOT/SYNOPSIS_DATA para no
   crear otra memoria al actualizar. Esta fase adapta instalación desde fuentes;
   runtime embebido y paquetes firmados son una entrega posterior.
2. Corregir apertura del mapa sin /bin/sh en Windows; exponer CLI .cmd sin symlinks,
   PATH solo de usuario y respeto de comandos ajenos. Conservar soporte zsh de Mac.
3. Unificar generación de comandos de hooks; Windows requiere sintaxis y codificación
   propias y debe conservar JSON Unicode/espacios sin depender de Git Bash.
4. Arranque de mapa por usuario: LaunchAgent en Mac, HKCU Run en Windows; sin sudo,
   contraseñas ni servicios globales. Entrypoint persistente separado del modo
   interactivo que se apaga cuando no quedan pestañas. Retiro conserva los datos.
5. Diagnóstico explícito de capacidades: memoria, MCP y mapa; laboratorio aislado
   requiere Linux+bwrap. No ejecutar prototipos en host como fallback.
6. Probar contratos/rollback en Linux y añadir matriz nativa macOS/Windows. Los
   resultados de mocks no se presentan como ejecución en esos sistemas.

Fuentes: [LaunchAgents de Apple](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html),
[Run de usuario en Windows](https://learn.microsoft.com/windows/win32/setupapi/run-and-runonce-registry-keys).

## Instalar esta adaptación desde fuentes

Necesita Python 3.11 o superior y conservar el checkout en su ubicación. No incluye
todavía Python embebido, instalador gráfico firmado, notarización o MSI.

macOS: abrir `install-macos.command`, o desde la carpeta descargada:

```sh
sh install-macos.command
```

Windows: abrir `install-windows.cmd`, o desde CMD/PowerShell en esa carpeta:

```powershell
.\install-windows.cmd
```

Ambos detectan asistentes disponibles, configuran sus adaptadores, preparan la
semántica local y activan el mapa al iniciar sesión. La primera descarga semántica
requiere red y puede tardar. Si falla, la búsqueda léxica sigue disponible y el
resumen muestra el componente pendiente. Los permisos de confianza del IDE siguen
bajo control de ese IDE; no se prometen conexiones autorizadas solo por instalar.

Para previsualizar sin escribir, agregar `--dry-run`. Para excluir el arranque,
`--no-service`. Para omitir descarga semántica, `--no-semantic`.

```sh
synopsis service status
synopsis service install --dry-run
synopsis service remove
synopsis doctor --json
```

`service remove` quita el arranque automático y conserva notas/configuración. En
Windows no detiene una instancia que ya estaba ejecutándose. El backend es HKCU
Run, no un servicio de Windows con autoreinicio: inicia al entrar a la cuenta y
puede ser deshabilitado desde las aplicaciones de inicio del sistema.

Windows instala `synopsis.cmd` en `%LOCALAPPDATA%\Synopsis\bin` y agrega esa carpeta
al PATH del usuario, conservando sus entradas. Usar terminal/IDE nuevos después.
El registro Run admite comandos de hasta 260 caracteres; un launcher privado corto
evita repetir allí las rutas del motor/datos. Si aun así excede el límite, informa
el error sin registrar un comando truncado.

macOS instala `~/Library/LaunchAgents/com.synopsis.map.plist`. No modifica servicios
globales. El proceso recibe intérprete y rutas absolutos para no depender de cargar
el perfil de la terminal. Configuración previa ajena se conserva y produce aviso.

## Capacidades y validación

`doctor --json` incluye `capabilities`, backend de arranque y disponibilidad del
laboratorio. La memoria/MCP/mapa son rutas portables; ejecutar experimentos exige
Linux y bwrap. No se usa ejecución desprotegida como alternativa en los escritorios.

`tests/test_desktop_platforms.py` comprueba transporte MCP real de cinco clientes en
HOME privado, mapa HTTP autenticado privado, comandos, preservación y rollback de
registro/LaunchAgent. Hay pruebas adicionales que ejecutan PowerShell y CMD reales
solo en Windows. `.github/workflows/desktop-platforms.yml` define una matriz para
Linux, macOS y Windows; agregar el archivo no significa que ya se haya ejecutado CI.

La matriz nativa aprobó en Linux, macOS y Windows: 22 casos por sistema,
20 aprobados en Linux/macOS y 21 en Windows; los omitidos requieren otro sistema
o permisos de enlaces simbólicos. Incluye mapa privado HTTP autenticado, cinco
transportes MCP y ejecución real CMD/PowerShell en Windows. El registro de arranque
se prueba mediante dobles controlados, sin modificar el inicio de sesión del runner.
[CI y resultados](https://github.com/vektiomx/synapsis/actions/runs/39048577583).
Falta probar suspensión/reinicio, cobertura Intel/Apple Silicon, runtime semántico
y firmas antes de anunciar distribución plug and play completa.

Validación de esta iteración en Linux: 380 pruebas, 378 aprobadas y 2 omitidas
por requerir CMD/PowerShell nativos de Windows; humo 767/767, sin la variante nativa
PowerShell. Se comprobó un mapa privado HTTP autenticado y el transporte MCP de los
cinco adaptadores. [Recibo y hashes de fuentes](desktop_validation.json).

## Auditoría de instalación multiplataforma

El README principal y su traducción incluyen instalación desde fuentes para Linux,
macOS y Windows, requisitos, descarga semántica opcional y reinicio del cliente.
El servicio Linux usa la entrada persistente `desktop_map.py`, escapa los
especificadores de systemd y recarga/reinicia su definición al actualizarla.
Los instaladores rechazan archivos y registros ajenos. La actualización del comando
Windows es atómica y recupera el archivo previo si falla el PATH; rechaza enlaces
simbólicos, incluso rotos, y tipos de registro incompatibles. macOS escribe la nueva
definición antes de detener la anterior y recupera la configuración ante un fallo.
Estas garantías cuentan con pruebas de fallos inducidos; no sustituyen pruebas
manuales de inicio de sesión, suspensión o reinicio de cada sistema.
