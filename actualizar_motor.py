#!/usr/bin/env python3
"""Actualiza engine/ desde una copia del proyecto original (lumiel777/neuromapa),
sin pisar a ciegas los archivos que synapsis parchó.

Uso:
    python3 actualizar_motor.py /ruta/a/un/clon/nuevo/de/neuromapa
    python3 actualizar_motor.py /ruta/a/un/clon/nuevo/de/neuromapa --aplicar

Sin --aplicar, no escribe nada: solo dice qué archivos copiaría tal cual y para
cuáles archivos parchados hay que revisar el diff a mano (y lo muestra).
"""
import argparse
import filecmp
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ENGINE = BASE / "engine"

# Archivos con cambios propios de synapsis: nunca se pisan solos, se muestra el diff.
PARCHADOS = {"buscador.py", "servidor.py"}

# synapsis no vendoriza esto a propósito (ver README): queda igual aunque cambie upstream.
CARPETAS_EXCLUIDAS = {"demo", "docs", ".github"}


def listar_py(carpeta):
    return {p.relative_to(carpeta) for p in carpeta.rglob("*.py")
            if "__pycache__" not in p.parts and not CARPETAS_EXCLUIDAS & set(p.relative_to(carpeta).parts)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("origen", type=Path, help="Carpeta con un clon nuevo de lumiel777/neuromapa")
    parser.add_argument("--aplicar", action="store_true", help="Copia de verdad los archivos sin cambios propios")
    args = parser.parse_args()
    origen = args.origen.resolve()
    if not (origen / "cerebro.py").is_file():
        sys.exit(f"{origen} no parece un clon de neuromapa (no encontré cerebro.py ahí).")

    propios = listar_py(origen)
    vendorizados = listar_py(ENGINE)
    nuevos = sorted(propios - vendorizados)
    borrados = sorted(vendorizados - propios)
    en_ambos = sorted(propios & vendorizados)

    identicos, distintos_sin_parche, distintos_con_parche = [], [], []
    for rel in en_ambos:
        if filecmp.cmp(origen / rel, ENGINE / rel, shallow=False):
            identicos.append(rel)
        elif rel.name in PARCHADOS:
            distintos_con_parche.append(rel)
        else:
            distintos_sin_parche.append(rel)

    print(f"Sin cambios: {len(identicos)} archivos")
    if nuevos:
        print(f"Nuevos en el original (no vendorizados todavía): {len(nuevos)}")
        for rel in nuevos:
            print(f"  + {rel}")
    if borrados:
        print(f"Ya no existen en el original (quedaron solo en engine/): {len(borrados)}")
        for rel in borrados:
            print(f"  - {rel}")
    if distintos_sin_parche:
        print(f"Cambiaron en el original, sin parche propio — se pueden copiar tal cual: {len(distintos_sin_parche)}")
        for rel in distintos_sin_parche:
            print(f"  ~ {rel}")
    if distintos_con_parche:
        print(f"\nCambiaron en el original Y tienen un parche propio de synapsis — revisar a mano:")
        for rel in distintos_con_parche:
            print(f"\n--- {rel} (original nuevo vs. engine/ actual) ---")
            import difflib
            original = (origen / rel).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            actual = (ENGINE / rel).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            diff = difflib.unified_diff(actual, original, fromfile=f"engine/{rel} (actual)",
                                        tofile=f"original/{rel} (nuevo)")
            sys.stdout.writelines(diff)

    if not args.aplicar:
        print("\n(modo solo-lectura: nada se copió. Corré con --aplicar para copiar lo seguro de verdad)")
        return
    for rel in distintos_sin_parche + nuevos:
        destino = ENGINE / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes((origen / rel).read_bytes())
        print(f"copiado: {rel}")
    if distintos_con_parche:
        print(f"\nNo se tocaron (tienen parche propio, hay que aplicarlos a mano con el diff de arriba): "
              f"{', '.join(str(r) for r in distintos_con_parche)}")


if __name__ == "__main__":
    main()
