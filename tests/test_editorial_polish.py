"""Regressões da camada visual; contratos de edição e de leitura permanecem intactos."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / 'static' / 'css' / 'editorial-polish.css'


class EditorialPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.styles = CSS.read_text(encoding='utf-8')
        cls.base = (ROOT / 'templates' / 'base.html').read_text(encoding='utf-8')
        cls.script_template = (ROOT / 'templates' / 'editor_roteiro.html').read_text(encoding='utf-8')
        cls.script_js = (ROOT / 'static' / 'js' / 'editor_roteiro.js').read_text(encoding='utf-8')

    def test_global_layer_is_last_and_local_badge_removed(self):
        self.assertIn("css/editorial-polish.css", self.base)
        self.assertLess(self.base.index('css/ui-system.css'), self.base.index('css/editorial-polish.css'))
        self.assertNotIn('<span>Local</span>', self.base)
        self.assertIn('class="app-shell-nav"', self.base)

    def test_two_readers_keep_progress_id_but_not_badge_background(self):
        for template in ('leitor.html', 'leitor_alt.html'):
            text = (ROOT / 'templates' / template).read_text(encoding='utf-8')
            self.assertIn('id="indicadorProgressoLivro"', text)
        self.assertIn('.pagina-leitor-app .indicador-progresso-leitura-topo', self.styles)
        self.assertRegex(self.styles, r'\.pagina-leitor-app \.indicador-progresso-leitura-topo\s*\{[^}]*background:transparent!important;')
        for module in ('leitor.js', 'leitor_alt.js'):
            source = (ROOT / 'static' / 'js' / module).read_text(encoding='utf-8')
            self.assertIn("document.getElementById('indicadorProgressoLivro')", source)

    def test_book_editor_has_paper_margins_without_touching_content(self):
        editor_html = (ROOT / 'templates' / 'editor.html').read_text(encoding='utf-8')
        self.assertIn('id="editorTexto" class="editor-texto" contenteditable="true"', editor_html)
        self.assertIn('.painel-word > .pagina-editor', self.styles)
        self.assertRegex(self.styles, r'padding:clamp\(42px,6vw,88px\)!important')
        self.assertIn('.painel-word #editorTexto', self.styles)
        self.assertIn('overflow-wrap:anywhere', self.styles)

    def test_screenplay_controls_and_pagination_contracts_preserved(self):
        for block in ('scene_heading','action','character','dialogue','parenthetical',
                      'shot','transition','comment','music','neutral'):
            self.assertIn(f'"{block}"', self.script_template)
        for key in ('btnUndo', 'btnRedo', 'selectTemaRoteiro', 'editorTexto',
                    'btnToggleVisualizacaoRoteiro', 'indicadorTipoBloco'):
            self.assertIn(f'id="{key}"', self.script_template)
        self.assertIn('createPage(pageNumber = 1)', self.script_js)
        self.assertIn('scheduleRepagination(', self.script_js)
        self.assertIn('updateActiveScriptPage(block)', self.script_js)
        self.assertIn('is-current-page', self.styles)
        self.assertIn('getCurrentBlock()', self.script_js)
        self.assertRegex(self.styles, r'\.painel-roteiro\s*\{[^}]*background:transparent!important;')
        self.assertIn('background:var(--roteiro-page-bg)!important;', self.styles)
        self.assertIn('select.theme-select', self.styles)


if __name__ == '__main__':
    unittest.main()
