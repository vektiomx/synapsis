#!/usr/bin/env python3
"""Pruebas propias de synopsis (los puentes/instaladores, no el motor vendorizado).

Corren sin dependencias externas: python3 -m unittest discover -s tests
"""
import json
import os
import sys
import tempfile
import tomllib
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
            self.assertIn("name: memoria-synopsis", contenido)
            self.assertIn("guardar", contenido.lower())


class ComunTest(unittest.TestCase):
    def test_raiz_motor_por_defecto_es_engine(self):
        import comun
        os.environ.pop("SYNOPSIS_ROOT", None)
        self.assertEqual(comun.raiz_motor(), RAIZ / "engine")

    def test_raiz_motor_respeta_override(self):
        import comun
        os.environ["SYNOPSIS_ROOT"] = "/una/ruta/cualquiera"
        try:
            self.assertEqual(comun.raiz_motor(), Path("/una/ruta/cualquiera"))
        finally:
            os.environ.pop("SYNOPSIS_ROOT", None)

    def test_carpeta_datos_respeta_override(self):
        import comun
        os.environ["SYNOPSIS_DATA"] = "/otra/ruta"
        try:
            self.assertEqual(comun.carpeta_datos(), Path("/otra/ruta"))
        finally:
            os.environ.pop("SYNOPSIS_DATA", None)


class InstalarCodexTest(unittest.TestCase):
    def test_desactiva_plugin_crudo_y_conserva_otros_ajustes(self):
        import install_codex
        original = ('# Configuración del usuario\nmodel = "test"\n'
                    '[plugins."synopsis@synopsis"] # plugin anterior\n'
                    'enabled = true # comentario conservado\n'
                    'custom_setting = "preservar"\n'
                    '[plugins."otro@plugin"]\nenabled = true\n')
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            (carpeta / 'config.toml').write_text(original)
            hp, cp, hooks, config = install_codex.prepare(carpeta)
            parsed = tomllib.loads(config)
            self.assertFalse(parsed['plugins']['synopsis@synopsis']['enabled'])
            self.assertTrue(parsed['plugins']['otro@plugin']['enabled'])
            self.assertEqual(parsed['plugins']['synopsis@synopsis']['custom_setting'], 'preservar')
            self.assertIn('enabled = false # comentario conservado', config)
            self.assertEqual((carpeta / 'config.toml').read_text(), original)
            stop = json.loads(hooks)['hooks']['Stop']
            self.assertEqual(len(stop), 1)
            self.assertIn('bridge.py', stop[0]['hooks'][0]['command'])
            hp.write_text(hooks)
            cp.write_text(config)
            self.assertEqual(install_codex.prepare(carpeta)[3], config)

    def test_plugin_ausente_desactivado_y_sin_enabled(self):
        import install_codex
        for config in ('', '[plugins."synopsis@synopsis"]\nenabled = false\n',
                       "[plugins.'synopsis@synopsis']\n# comentario\n"):
            with self.subTest(config=config):
                result = install_codex.desactivar_plugin_duplicado(config)
                parsed = tomllib.loads(result)
                if config:
                    self.assertFalse(parsed['plugins']['synopsis@synopsis']['enabled'])
                else:
                    self.assertEqual(result, config)
                self.assertEqual(install_codex.desactivar_plugin_duplicado(result), result)

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

    def test_reconoce_marca_vieja_synopsis_y_la_reemplaza(self):
        """La marca tiene que reconocer instalaciones viejas (statusMessage "Synopsis: ...")
        además de la nueva ("Synopsis: ..."), para no duplicar al migrar el nombre."""
        import install_codex
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            viejo = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "algo/viejo/bridge.py",
                                                     "statusMessage": "Synopsis: Stop"}]}]}}
            (config_dir / "hooks.json").write_text(json.dumps(viejo), encoding="utf-8")
            _, _, hooks_nuevo, _ = install_codex.prepare(config_dir)
            datos = json.loads(hooks_nuevo)
            self.assertEqual(len(datos["hooks"]["Stop"]), 1)
            self.assertIn("Synopsis: Stop", datos["hooks"]["Stop"][0]["hooks"][0]["statusMessage"])


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

    def test_desactiva_plugins_synopsis_activos(self):
        import install_claude_code
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "settings.json"
            ruta.write_text(json.dumps({"enabledPlugins": {"synopsis@synopsis": True, "otro@plugin": True}}),
                            encoding="utf-8")
            contenido, desactivados = install_claude_code.preparar(ruta)
            datos = json.loads(contenido)
            self.assertEqual(datos["enabledPlugins"]["synopsis@synopsis"], False)
            self.assertEqual(datos["enabledPlugins"]["otro@plugin"], True)
            self.assertIn("synopsis@synopsis", desactivados)

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
            self.assertIn("synopsis", datos)


if __name__ == "__main__":
    unittest.main()
