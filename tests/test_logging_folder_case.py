import tempfile
import unittest
from pathlib import Path

from modules.logging_config import NOME_APP, _normalizar_capitalizacao_pasta_gutenberg


class LoggingFolderCaseTests(unittest.TestCase):
    def test_nome_oficial_tem_g_maiusculo(self):
        self.assertEqual(NOME_APP, "Gutenberg")

    def test_migra_pasta_minuscula_para_nome_oficial(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            antiga = base / "gutenberg"
            antiga.mkdir()
            (antiga / "errors.log").write_text("ok", encoding="utf-8")

            destino = _normalizar_capitalizacao_pasta_gutenberg(base)

            self.assertEqual(destino.name, "Gutenberg")
            self.assertTrue((base / "Gutenberg" / "errors.log").exists())
            self.assertFalse((base / "gutenberg").exists())


if __name__ == "__main__":
    unittest.main()
