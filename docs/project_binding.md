# Vinculación automática de proyectos

Disponible en la rama de desarrollo desde 0.4. No requiere registrar proyectos por
terminal. Instala Synopsis, reinicia el cliente y usa tu proyecto normalmente.

## Primer uso

Los hooks entregan cwd y, cuando el cliente los proporciona, las raíces del espacio
abierto y la ruta del archivo activo. El resolver reconoce Git, archivos .git de
worktrees, raíces de IDE, marcadores de Synopsis y ubicaciones conocidas. Sin esas
pistas usa un manifiesto de proyecto conocido (por ejemplo pyproject.toml) o cwd.
No recorre el disco para adivinar todos los proyectos del usuario.

El proyecto recibe un UUID local. En Git el marcador está en los metadatos del
checkout (synopsis-workspace.json); fuera de Git, en .synopsis/workspace.json. Las
notas nuevas siguen en ~/.local/share/synopsis/projects/<clave>/memory. El marcador
contiene solo identidad, no notas ni credenciales. En proyectos de solo lectura se
usa un registro privado sin exigir escribir un marcador en el código.

La clave SHA-256 de la ruta sigue siendo el índice de acceso por ubicación. El UUID
identifica el workspace y permite conservar su carpeta de memoria al reconocer un
movimiento; no se presenta la ruta como una identidad portátil.

Subcarpetas, alias simbólicos y clientes distintos reutilizan la raíz reconocida.
En una carpeta sin Git, sin marcador ni raíz de IDE, un primer uso dentro de una
subcarpeta no permite conocer por sí solo dónde termina el proyecto. Synopsis no
promete descubrir ese límite sin evidencia.

## Memoria anterior

Una asignación explícita o un propietario ya verificado conserva prioridad. Para
una carpeta heredada sin propietario se consultan metadatos cwd escritos por el
cliente junto a sus sesiones, nunca el texto de las notas. La ruta codificada de
la carpeta es solo un candidato: no acredita propiedad.

La comprobación se limita a 16 archivos de sesión y a los primeros 64 KiB/256 líneas
de cada uno. Una colección mayor no se adjudica a partir de una muestra. Si la
información comprobada identifica únicamente al proyecto actual, se vincula esa
carpeta sin copiar notas, índices ni historial. Una evidencia ausente, contradictoria
o insuficiente produce una solicitud de elección en el mapa.

Abre `synopsis`. El panel ofrece usar una memoria candidata o crear una memoria
independiente. La elección es persistente. Si hay varias memorias explícitamente
asignadas, se muestran las alternativas; no se fusionan automáticamente.

Cada solicitud tiene un identificador aleatorio y una huella de su carpeta. La acción
HTTP requiere autenticación, origen local coincidente, cabecera propia y cuerpo
acotado. El navegador envía un identificador y una elección; nunca una ruta libre
que el servidor pueda convertir en una escritura arbitraria. Una solicitud obsoleta
o una memoria que cambió exige revisar la elección de nuevo.

## Movimientos, copias y worktrees

- Movimiento con marcador persistente y misma identidad de archivo: conserva UUID,
  notas y revisiones; actualiza propietario, ubicación y proyectos de los turnos.
  El proceso deja una intención recuperable antes de publicar el nuevo propietario.
- Movimiento con marcador recreado, por ejemplo una copia entre sistemas de archivos:
  exige confirmación en el mapa antes de adoptar la memoria anterior.
- Copia mientras la ubicación original existe: recibe otro UUID y memoria independiente.
- Worktrees: comparten un identificador de grupo derivado del directorio Git común,
  pero conservan memorias, turnos y checkpoints separados por checkout. No se ha
  implementado una biblioteca automática de hechos compartidos entre ramas.
- Proyecto de solo lectura: se conserva su registro local. Sin marcador portable,
  una copia o movimiento entre dispositivos no se puede reconocer automáticamente.

El registro es local al usuario: no sincroniza memorias entre computadoras ni adopta
notas de otra persona por tener el mismo remoto Git. Una copia cuyo original ya no
existe puede requerir elección; no se decide por el nombre del repositorio.

Los recibos de versiones anteriores se conservan. Las fuentes de evidencia que
citan una ruta antigua deben volver a validarse: mover un proyecto no certifica
que una cita anterior siga vigente ni elimina la cuarentena del modo estricto.

## Mapa y diagnóstico

Los índices muestran `<proyecto> · Memoria`; una carpeta aún sin propietario se
identifica como memoria sin vincular, sin inventar su proyecto a partir del slug.
La agrupación por proyecto usa propietarios verificados. `synopsis doctor --json`
informa project_binding=automatic_on_first_use y pending_bindings.

La vinculación automática no cambia el contrato de contexto del IDE. Cursor sigue
sin admitir inyección en beforeSubmitPrompt. Los hooks siguen siendo cooperativos;
solo synopsis run controla su propia publicación de respuestas.
