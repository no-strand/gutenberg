from __future__ import annotations

import base64

from modules import exportador_html
from tests.test_support import IsolatedProjectTestCase


class ExportadorHtmlHelpersTests(IsolatedProjectTestCase):
    """Testes dos helpers de XHTML/EPUB usados na exportação de livros."""

    def test_normalizar_conteudo_html_remove_scripts_e_mantem_texto_seguro(self):
        """Sanitização EPUB: remove script/eventos e preserva conteúdo permitido."""
        html = '<p onclick="alert(1)">Texto <strong>seguro</strong></p><script>alert(2)</script>'

        normalizado = exportador_html._normalizar_conteudo_html(html)

        self.assertIn("Texto", normalizado)
        self.assertIn("<strong>seguro</strong>", normalizado)
        self.assertNotIn("script", normalizado.lower())
        self.assertNotIn("onclick", normalizado.lower())

    def test_substituir_imagens_base64_salva_arquivo_e_atualiza_src(self):
        """Imagens EPUB: base64 embutido vira arquivo em Images e referência relativa."""
        pasta_images = self.base / "OEBPS" / "Images"
        raw = b"imagem-falsa"
        data_url = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
        html = f'<p>Capa</p><img alt="x" src="{data_url}">' 

        atualizado, imagens = exportador_html._substituir_imagens_base64(html, pasta_images)

        self.assertEqual(len(imagens), 1)
        arquivo = pasta_images / imagens[0]["href"]
        self.assertTrue(arquivo.exists())
        self.assertEqual(arquivo.read_bytes(), raw)
        self.assertIn('src="Images/', atualizado)
        self.assertNotIn("data:image/png;base64", atualizado)
