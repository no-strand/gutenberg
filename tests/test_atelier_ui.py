"""Protect DOM and persistence invariants of the 1.0.4 Atelier redesign."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AtelierUiContracts(unittest.TestCase):
    def test_atelier_layer_loaded_after_old_layers(self):
        html = (ROOT / 'templates/base.html').read_text(encoding='utf-8')
        self.assertLess(html.index('css/ui-system.css'), html.index('css/editorial-polish.css'))
        self.assertLess(html.index('css/editorial-polish.css'), html.index('css/atelier-ui.css'))

    def test_epub_editor_remains_a_single_editable_root(self):
        html = (ROOT / 'templates/editor.html').read_text(encoding='utf-8')
        self.assertEqual(html.count('id="editorTexto"'), 1)
        self.assertIn('id="editorTexto" class="editor-texto" contenteditable="true"', html)
        self.assertLess(html.index('js/editor.js'), html.index('js/epub-pagination.js'))

    def test_pages_do_not_modify_saved_epub_structure(self):
        script = (ROOT / 'static/js/epub-pagination.js').read_text(encoding='utf-8')
        self.assertIn('paper.insertBefore(layers, editor)', script)
        self.assertIn("document.createElement('style')", script)
        self.assertNotIn('editor.appendChild(', script)
        self.assertNotIn('editor.innerHTML =', script)
        self.assertNotIn('block.style.', script)

    def test_screenplay_actions_and_theme_values_preserved(self):
        html = (ROOT / 'templates/editor_roteiro.html').read_text(encoding='utf-8')
        self.assertEqual(html.count('id="selectTemaRoteiro"'), 1)
        self.assertIn('data-block-type="{{ tipo }}"', html)
        self.assertIn('id="btnUndo"', html)
        self.assertIn('id="btnRedo"', html)
        for value in ['light', 'dark', 'serpia', 'dark-blue', 'terminal-calm', 'warm-brown', 'sunset-mode', 'frost', 'pastel-pink', 'code-like']:
            self.assertIn(f'value="{value}"', html)

    def test_reader_progress_has_no_gradient_on_inner_span(self):
        css = (ROOT / 'static/css/atelier-ui.css').read_text(encoding='utf-8')
        self.assertIn('.pagina-leitor-app .indicador-progresso-leitura > span', css)
        self.assertIn('background-image:none!important;', css)
        self.assertIn('box-shadow:none!important;border:0!important;', css)


if __name__ == '__main__':
    unittest.main()
