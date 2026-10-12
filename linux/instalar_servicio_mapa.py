#!/usr/bin/env python3
"""Deja el mapa en vivo de Synapsis prendido solo, sin tener que correr `neuromapa
abrir` a mano cada vez. Solo Linux (usa `systemd --user`).

Uso:
    python3 linux/instalar_servicio_mapa.py              # instala y prende
    python3 linux/instalar_servicio_mapa.py --dry-run    # solo muestra qué haría
    python3 linux/instalar_servicio_mapa.py --quitar     # desinstala el servicio
"""
import argparse
import getpass
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
import comun

NOMBRE_SERVICIO = "synapsis-mapa.service"
CARPETA_SERVICIOS = Path.home() / ".config" / "systemd" / "user"


def unidad():
    bin_neuromapa = comun.raiz_motor() / "bin" / "neuromapa"
    return f"""[Unit]
Description=Synapsis — mapa en vivo de la memoria
After=network.target

[Service]
Type=simple
ExecStart=/bin/sh {bin_neuromapa} abrir --sin-navegador
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quitar", action="store_true")
    args = parser.parse_args()

    if shutil.which("systemctl") is None:
        sys.exit("No encontré systemctl: esto solo funciona en Linux con systemd. "
                 "En Mac o Windows, seguí abriendo el mapa a mano con `neuromapa abrir`.")

    ruta_servicio = CARPETA_SERVICIOS / NOMBRE_SERVICIO

    if args.quitar:
        if args.dry_run:
            print(f"Quitaría el servicio y borraría {ruta_servicio}")
            return
        subprocess.run(["systemctl", "--user", "disable", "--now", NOMBRE_SERVICIO], check=False)
        ruta_servicio.unlink(missing_ok=True)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        print("Servicio quitado. El mapa ya no arranca solo (seguís pudiendo abrirlo a mano).")
        return

    bin_neuromapa = comun.raiz_motor() / "bin" / "neuromapa"
    if not bin_neuromapa.is_file():
        sys.exit(f"No encontré el motor en {bin_neuromapa}. ¿Está bien instalado synapsis?")

    contenido = unidad()
    if args.dry_run:
        print(f"Escribiría {ruta_servicio}:\n\n{contenido}")
        print("Y correría: systemctl --user enable --now " + NOMBRE_SERVICIO)
        return

    CARPETA_SERVICIOS.mkdir(parents=True, exist_ok=True)
    ruta_servicio.write_text(contenido, encoding="utf-8")
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", NOMBRE_SERVICIO], check=True)
    print(f"Listo. El mapa arranca solo cada vez que inicias sesión (servicio: {NOMBRE_SERVICIO}).")
    print("Para verlo ahora: abrí http://127.0.0.1:8765/cerebro.html (con la clave de "
          "en-vivo/clave.txt) o corré `neuromapa abrir` una vez para que te lo abra el navegador.")
    print("Para que arranque incluso antes de iniciar sesión: loginctl enable-linger " + getpass.getuser())
    print("Para quitarlo: python3 linux/instalar_servicio_mapa.py --quitar")


if __name__ == "__main__":
    main()
