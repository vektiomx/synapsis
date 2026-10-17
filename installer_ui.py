"""Small accessible terminal UI; plain output for pipes, CI and NO_COLOR."""
import os
import shutil
import sys


class InstallerUI:
    def __init__(self, stream=None):
        self.stream = stream or sys.stdout
        self.color = self.stream.isatty() and os.environ.get('TERM', '') not in ('', 'dumb') and 'NO_COLOR' not in os.environ
        self.width = max(32, min(76, shutil.get_terminal_size((76, 24)).columns))

    def line(self, text='', style=''):
        if self.color and style:
            text = f'\033[{style}m{text}\033[0m'
        print(text, file=self.stream)

    def banner(self, preview=False):
        self.line()
        self.line('  S Y N O P S I S', '1;36')
        self.line('  Memoria compartida para tus asistentes de IA')
        self.line('  Instalación de usuario · sin sudo · conserva otros ajustes')
        self.line('─' * self.width, '2')
        if preview:
            self.line('  VISTA PREVIA: no se escribirá ningún archivo.', '1;33')

    def choice(self, number, name, available, detail=''):
        state = 'DISPONIBLE' if available else 'NO DISPONIBLE'
        self.line(f'  {number}. {name:<14} {state}', '32' if available else '2')
        if detail:
            self.line(f'     {detail}')

    def step(self, current, total, name):
        self.line()
        self.line(f'  [{current}/{total}] {name}', '1;36')

    def summary(self, results, preview=False):
        self.line()
        self.line('─' * self.width, '2')
        self.line('  Resumen de la vista previa' if preview else '  Resumen de instalación', '1')
        for name, success in results:
            self.line(f'  {"OK" if success else "PENDIENTE":<10} {name}', '32' if success else '33')
        if preview:
            self.line('  No se aplicaron cambios. Repite el comando sin --dry-run para instalar.')
        elif results and all(ok for _, ok in results):
            self.line('  Siguiente paso: reinicia tu asistente y abre una terminal nueva.')
            self.line('  Abre el mapa con: synopsis')
            self.line('  Tus proyectos se vinculan automáticamente al usarlos.')
            self.line('  Si una memoria anterior es ambigua, podrás elegirla desde el mapa.')
        else:
            self.line('  Revisa el error de cada paso pendiente; puedes repetir la instalación.')
        self.line('  Consulta memoria con: synopsis recall "tema" --project /ruta/proyecto')
