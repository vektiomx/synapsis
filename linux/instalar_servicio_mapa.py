#!/usr/bin/env python3
"""Deja el mapa en vivo de Synopsis prendido solo, sin tener que correr `synopsis
abrir` a mano cada vez. Solo Linux (usa `systemd --user`).

Uso:
    python3 linux/instalar_servicio_mapa.py              # instala y prende
    python3 linux/instalar_servicio_mapa.py --dry-run    # solo muestra qué haría
    python3 linux/instalar_servicio_mapa.py --quitar     # desinstala el servicio
"""
import argparse
import getpass
import json
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
import comun

NOMBRE_SERVICIO = "synopsis-mapa.service"
CARPETA_SERVICIOS = Path.home() / ".config" / "systemd" / "user"


def unidad():
    from desktop_service import command
    arguments=" ".join(json.dumps(value,ensure_ascii=False).replace("%","%%") for value in command())
    return f"""[Unit]
Description=Synopsis — mapa en vivo de la memoria
After=network.target

[Service]
Type=simple
ExecStart={arguments}
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
                 "En Mac o Windows, seguí abriendo el mapa a mano con `synopsis abrir`.")

    ruta_servicio = CARPETA_SERVICIOS / NOMBRE_SERVICIO

    if ruta_servicio.is_symlink():raise ValueError('symlink_service_preserved')
    previous=ruta_servicio.read_bytes() if ruta_servicio.exists() else None
    if previous is not None and not (b'Description=Synopsis' in previous and (b'/bin/synopsis' in previous or b'desktop_map.py' in previous)):
        raise ValueError('foreign_service_preserved')
    if args.quitar:
        if args.dry_run:
            print(f"Quitaría el servicio y borraría {ruta_servicio}")
            return
        subprocess.run(["systemctl", "--user", "disable", "--now", NOMBRE_SERVICIO], check=True)
        ruta_servicio.unlink(missing_ok=True)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        print("Servicio quitado. El mapa ya no arranca solo (seguís pudiendo abrirlo a mano).")
        return

    bin_synopsis = comun.raiz_motor() / "bin" / "synopsis"
    if not bin_synopsis.is_file():
        sys.exit(f"No encontré el motor en {bin_synopsis}. ¿Está bien instalado synopsis?")

    contenido = unidad()
    if args.dry_run:
        print(f"Escribiría {ruta_servicio}:\n\n{contenido}")
        print("Y correría: systemctl --user enable --now " + NOMBRE_SERVICIO)
        return

    CARPETA_SERVICIOS.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0,str(comun.raiz_motor()))
    from archivos import escribir_atomico
    try:
        escribir_atomico(ruta_servicio,contenido)
        subprocess.run(["systemctl", "--user", "daemon-reload"],check=True)
        subprocess.run(["systemctl", "--user", "enable", NOMBRE_SERVICIO],check=True)
        subprocess.run(["systemctl", "--user", "restart", NOMBRE_SERVICIO],check=True)
    except (OSError,subprocess.SubprocessError):
        if previous is None:
            subprocess.run(["systemctl", "--user", "disable", "--now", NOMBRE_SERVICIO],check=False)
            ruta_servicio.unlink(missing_ok=True)
        else:escribir_atomico(ruta_servicio,previous)
        subprocess.run(["systemctl", "--user", "daemon-reload"],check=False)
        if previous is not None:subprocess.run(["systemctl", "--user", "restart", NOMBRE_SERVICIO],check=False)
        raise
    print(f"Listo. El mapa arranca solo cada vez que inicias sesión (servicio: {NOMBRE_SERVICIO}).")
    print("Para verlo ahora: abrí http://127.0.0.1:8765/cerebro.html (con la clave de "
          "en-vivo/clave.txt) o corré `synopsis abrir` una vez para que te lo abra el navegador.")
    print("Para que arranque incluso antes de iniciar sesión: loginctl enable-linger " + getpass.getuser())
    print("Para quitarlo: python3 linux/instalar_servicio_mapa.py --quitar")


if __name__ == "__main__":
    main()
