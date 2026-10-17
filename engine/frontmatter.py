"""Pure frontmatter parsing; importing storage must not initialize the application."""
import json
import re


def desentrecomillar(valor):
    v = valor.strip()
    if len(v) >= 2 and v[0] == v[-1] == '"':
        try:
            return json.loads(v)
        except ValueError:
            return v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if len(v) >= 2 and v[0] == v[-1] == "'":
        return v[1:-1].replace("''", "'")
    return v


def separar_frontmatter(texto):
    lineas = texto.split("\n")
    if not lineas or lineas[0].strip() != "---":
        return {}, texto
    fin = None
    for i in range(1, len(lineas)):
        if lineas[i].strip() in ("---", "..."):
            fin = i
            break
    if fin is None:
        return {}, texto
    datos = {}
    padre = None
    for linea in lineas[1:fin]:
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        m = re.match(r"^(\s*)([\w\-]+)\s*:\s*(.*)$", linea)
        if not m:
            continue
        sangria, clave, valor = m.groups()
        if not sangria:
            if valor.strip() == "":
                datos[clave] = {}
                padre = clave
            else:
                datos[clave] = desentrecomillar(valor)
                padre = None
        elif padre is not None:
            datos[padre][clave] = desentrecomillar(valor)
    if not datos:
        return {}, texto
    return datos, "\n".join(lineas[fin + 1:])
