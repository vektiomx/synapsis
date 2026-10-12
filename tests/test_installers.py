#!/usr/bin/env python3
"""Pruebas propias de synapsis (los puentes/instaladores, no el motor vendorizado).

Corren sin dependencias externas: python3 -m unittest discover -s tests
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "codex"))
sys.path.insert(0, str(RAIZ / "claude-code"))
sys.path.insert(0, str(RAIZ / "antigravity"))


class SkillMemoriaTest(unittest.TestCase):
    def test_instalar_skill_memoria_copia_el_archivo(self):
        import comun
        with tempfile.TemporaryDirectory() as tmp:
            destino = comun.instalar_skill_memoria(Path(tmp))
            self.assertTrue(destino.is_file())
            contenido = destino.read_text(encoding="utf-8")
            self.assertIn("name: memoria-synapsis", contenido)
            self.assertIn("guardar", contenido.lower())


class ComunTest(unittest.TestCase):
    def test_raiz_motor_por_defecto_es_engine(self):
        import comun
        os.environ.pop("NEUROMAPA_ROOT", None)
        self.assertEqual(comun.raiz_motor(), RAIZ / "engine")

    def test_raiz_motor_respeta_override(self):
        import comun
        os.environ["NEUROMAPA_ROOT"] = "/una/ruta/cualquiera"
        try:
            self.assertEqual(comun.raiz_motor(), Path("/una/ruta/cualquiera"))
        finally:
            os.environ.pop("NEUROMAPA_ROOT", None)

    def test_carpeta_datos_respeta_override(self):
        import comun
        os.environ["NEUROMAPA_DATA"] = "/otra/ruta"
        try:
            self.assertEqual(comun.carpeta_datos(), Path("/otra/ruta"))
        finally:
            os.environ.pop("NEUROMAPA_DATA", None)


class InstalarCodexTest(unittest.TestCase):
    def test_prepare_es_idempotente(self):
        """Instalar dos veces no debe duplicar hooks (el bug real que encontramos)."""
        import install_codex
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            hp, cp, hooks_1, config_1 = install_codex.prepare(config_dir)
            hp.write_text(hooks_1, encoding="utf-8")
            cp.write_text(config_1, encoding="utf-8")
            _, _, hooks_2, _ = install_codex.prepare(config_dir)
            datos_1 = json.loads(hooks_1)
            datos_2 = json.loads(hooks_2)
            for evento in install_codex.EVENTS:
                self.assertEqual(len(datos_1["hooks"][evento]), 1, f"duplicado en la 1a pasada: {evento}")
                self.assertEqual(len(datos_2["hooks"][evento]), 1, f"duplicado en la 2a pasada: {evento}")

    def test_reconoce_marca_vieja_neuromapa_y_la_reemplaza(self):
        """La marca tiene que reconocer instalaciones viejas (statusMessage "Neuromapa: ...")
        además de la nueva ("Synapsis: ..."), para no duplicar al migrar el nombre."""
        import install_codex
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            viejo = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "algo/viejo/bridge.py",
                                                     "statusMessage": "Neuromapa: Stop"}]}]}}
            (config_dir / "hooks.json").write_text(json.dumps(viejo), encoding="utf-8")
            _, _, hooks_nuevo, _ = install_codex.prepare(config_dir)
            datos = json.loads(hooks_nuevo)
            self.assertEqual(len(datos["hooks"]["Stop"]), 1)
            self.assertIn("Synapsis: Stop", datos["hooks"]["Stop"][0]["hooks"][0]["statusMessage"])


class InstalarClaudeCodeTest(unittest.TestCase):
    def test_preparar_es_idempotente(self):
        import install_claude_code
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "settings.json"
            contenido_1, _ = install_claude_code.preparar(ruta)
            ruta.write_text(contenido_1, encoding="utf-8")
            contenido_2, _ = install_claude_code.preparar(ruta)
            datos_2 = json.loads(contenido_2)
            total_propios = sum(
                1 for grupos in datos_2["hooks"].values() for g in grupos
                for h in g.get("hooks", [])
                if any(s in h.get("command", "") for _, _, s, _ in install_claude_code.HOOKS)
            )
            self.assertEqual(total_propios, len(install_claude_code.HOOKS),
                             "se duplicaron hooks propios en la segunda instalación")

    def test_desactiva_plugins_neuromapa_activos(self):
        import install_claude_code
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "settings.json"
            ruta.write_text(json.dumps({"enabledPlugins": {"neuromapa@neuromapa": True, "otro@plugin": True}}),
                            encoding="utf-8")
            contenido, desactivados = install_claude_code.preparar(ruta)
            datos = json.loads(contenido)
            self.assertEqual(datos["enabledPlugins"]["neuromapa@neuromapa"], False)
            self.assertEqual(datos["enabledPlugins"]["otro@plugin"], True)
            self.assertIn("neuromapa@neuromapa", desactivados)

    def test_conserva_hooks_de_otros(self):
        """No debe borrar hooks que no son nuestros (ej. los de Orca)."""
        import install_claude_code
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "settings.json"
            ajeno = {"type": "command", "command": "/algo/de/orca.sh"}
            ruta.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [ajeno]}]}}), encoding="utf-8")
            contenido, _ = install_claude_code.preparar(ruta)
            datos = json.loads(contenido)
            comandos = [h["command"] for g in datos["hooks"]["Stop"] for h in g["hooks"]]
            self.assertIn("/algo/de/orca.sh", comandos)


class InstalarAntigravityTest(unittest.TestCase):
    def test_preparar_remplaza_sin_duplicar(self):
        import install_antigravity
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "hooks.json"
            contenido_1 = install_antigravity.preparar(ruta)
            ruta.write_text(contenido_1, encoding="utf-8")
            contenido_2 = install_antigravity.preparar(ruta)
            self.assertEqual(json.loads(contenido_1), json.loads(contenido_2))

    def test_conserva_otras_claves(self):
        import install_antigravity
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "hooks.json"
            ruta.write_text(json.dumps({"orca-status": {"Stop": []}}), encoding="utf-8")
            contenido = install_antigravity.preparar(ruta)
            datos = json.loads(contenido)
            self.assertIn("orca-status", datos)
            self.assertIn("neuromapa", datos)


if __name__ == "__main__":
    unittest.main()
