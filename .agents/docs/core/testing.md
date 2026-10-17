# Pruebas y aislamiento

Ejecutar desde la raíz del repositorio con Python 3.11+. En Windows usar `py -3` o
`python` en lugar de `python3`. No ejecutar instaladores contra el HOME real como test.

| Cambio | Comando |
|---|---|
| Módulo acotado | `python3 -m unittest discover -s tests -p 'test_<area>.py' -v` |
| Motor o integración compartida | `python3 -m unittest discover -s tests -v` |
| Contratos de escritorio | `python3 -m unittest discover -s tests -p test_desktop_platforms.py -v` |
| Empaquetado | `python3 -m unittest discover -s tests -p test_release.py -v` |
| Contratos amplios del motor | `python3 engine/herramientas/prueba_humo.py` |
| Espacios y conflictos del diff | `git diff --check` (también `--cached` si hay stage) |

La matriz [.github/workflows/desktop-platforms.yml](../../../.github/workflows/desktop-platforms.yml)
ejecuta contratos de escritorio y transportes en Linux/macOS/Windows. Informar
por separado pruebas aprobadas, omitidas y comprobaciones manuales no ejecutadas.
Las pruebas nativas CMD/PowerShell necesitan Windows. Semántica real, login,
suspensión/reinicio y paquetes firmados no se deducen del éxito de los contratos.

Usar fixtures sintéticos y directorios temporales. Aislar HOME, configuración,
datos, proveedores, arranque y servicios externos. El laboratorio requiere bwrap
funcional; no sustituirlo por ejecución desprotegida. No cambiar el aislamiento para
obtener verde. Para documentación pura, comprobar enlaces, coherencia y diff; no se
requiere ejecutar toda la suite si no cambia comportamiento.
