# Reglas de desarrollo

La norma general está en [AGENTS.md](../../../AGENTS.md). Este documento concreta
las operaciones de desarrollo, no añade permisos de publicación o instalación.

## Descubrir antes de editar

Leer el módulo y sus consumidores, localizar sus pruebas y consultar el [catálogo](catalog.md).
Distinguir comportamiento actual de intención documentada; si discrepan, comprobar
fuentes y registrar el hallazgo. Evitar refactors o dependencias fuera del objetivo.

## Datos y efectos externos

Usar directorios temporales, HOME y variables de configuración privados para pruebas.
No iniciar semántica que descargue modelos ni revisiones que invoquen proveedores reales
sin que la tarea lo requiera. No mostrar claves de mapa, tokens ni archivos de credenciales.
Las pruebas de instaladores simulan registro/launchd/systemd; las de transporte y mapa
pueden usar procesos reales con datos privados y deben terminarlos al acabar.
Una prueba simulada de registro no equivale a una prueba de login/reinicio real.

## Persistencia y compatibilidad

Cambios de formato deben conservar datos existentes, revisiones y recuperación.
No mover ni borrar memorias del usuario para arreglar una prueba. Conservar degradación
explícita cuando semántica, un proveedor o aislamiento no estén disponibles.
Verificar rutas, UTF-8 y contratos de adaptadores sin suponer que todos los clientes
admiten los mismos eventos o permisos. Los hooks son cooperativos, no control total del modelo.

## Ediciones y validación

Respetar el estilo del módulo, usar biblioteca estándar donde baste y tipos cuando
aclaren contratos. Evitar escrituras directas sobre configuración compartida si existe
una utilidad atómica/transaccional. Validar según [testing.md](testing.md), sin ejecutar
instalaciones globales o repetir benchmarks costosos para un cambio puramente documental.
