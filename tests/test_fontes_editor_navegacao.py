"""Regressão: seletor de fontes, exportação e barra global sem ícones redundantes."""
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]


class SeletorFontesENavegacao(unittest.TestCase):
    def test_fontes_iguais_ao_leitor(self):
        editor = BeautifulSoup((ROOT / 'templates/editor.html').read_text(encoding='utf-8'), 'html.parser')
        reader = BeautifulSoup((ROOT / 'templates/leitor.html').read_text(encoding='utf-8'), 'html.parser')
        select_editor = editor.select_one('#seletorFonteEditor')
        select_leitor = reader.select_one('#controleFonte')
        self.assertIsNotNone(select_editor)
        self.assertIsNotNone(select_leitor)
        self.assertEqual(
            {opt.get('value') for opt in select_editor.select('optgroup option')},
            {'fonte-' + opt.get('value') for opt in select_leitor.select('optgroup option')},
        )
        self.assertEqual(len(select_editor.select('optgroup option')), 17)
        self.assertEqual(len(select_editor.select('optgroup')), 3)

    def test_botoes_superiores_somente_configuracoes_com_icone(self):
        html = (ROOT / 'templates/base.html').read_text(encoding='utf-8')
        nav = html.split('<nav class="app-shell-nav"', 1)[1].split('</nav>', 1)[0]
        self.assertEqual(nav.count('class="icone-svg"'), 1)
        self.assertIn("icon_svg('config')", nav)
        self.assertIn("t('nav.editor')", nav)
        self.assertIn("t('nav.library')", nav)

    def test_parenteticos_preservam_o_tipo_funcional(self):
        html = (ROOT / 'templates/editor_roteiro.html').read_text(encoding='utf-8')
        locale = (ROOT / 'locales/pt_BR.json').read_text(encoding='utf-8')
        self.assertIn('("parenthetical",t("script.editor_block_parenthetical"),t("script.editor_block_parenthetical"),"Alt+S")', html)
        self.assertIn('"script.editor_block_parenthetical": "Parênteses"', locale)

    def test_fontes_novas_incluem_compatibilidade_com_legadas(self):
        from modules.fontes_editor import FONTES_NOMEADAS, CLASSES_FONTES_EDITOR
        from modules.exportador_html import _css_global, CLASSES_ESTILO
        from modules.exportador_documentos import FONTES_DOCX, _classe_fonte, _fonte_rl
        self.assertEqual(len(FONTES_NOMEADAS), 17)
        self.assertTrue({'fonte-sans','fonte-serif','fonte-mono'} <= CLASSES_FONTES_EDITOR)
        for font in FONTES_NOMEADAS:
            self.assertIn(font, CLASSES_ESTILO)
            self.assertIn('span.' + font, _css_global())
            self.assertIn(font, FONTES_DOCX)
            self.assertEqual(_classe_fonte({font}), font)
        self.assertEqual(_fonte_rl('fonte-jetbrains-mono',False,False), 'Courier')

    def test_editor_nao_altera_dom_salvo(self):
        template = (ROOT / 'templates/editor.html').read_text(encoding='utf-8')
        script = (ROOT / 'static/js/editor.js').read_text(encoding='utf-8')
        self.assertEqual(template.count('id="editorTexto"'), 1)
        self.assertIn('const INLINE_FONT_SELECTOR = CLASSES_FONTE.map(', script)
        self.assertIn('function aplicarFonteEmSelecao(range, nomeClasse)', script)
        self.assertIn('seletorFonteEditor?.addEventListener(\'change\',', script)


if __name__ == '__main__':
    unittest.main()
