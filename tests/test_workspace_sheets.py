"""Visual-contract tests: one workspace panel and square-cornered pages."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / 'static/css/atelier-ui.css').read_text(encoding='utf-8')


class SheetWorkspaceStyles(unittest.TestCase):
    def test_workspace_is_shared_by_both_editors(self):
        self.assertIn('--editor-workspace-bg:#eff2f6', CSS)
        for selector in ('.pagina-editor-app .painel-word {', '.pagina-editor-app .painel-roteiro {'):
            block = CSS.split(selector, 1)[1].split('}', 1)[0]
            self.assertIn('background:var(--editor-workspace-bg)!important', block)
            self.assertIn('border:1px solid var(--editor-workspace-border)!important', block)

    def test_epub_sheets_and_roteiro_pages_have_no_corner_radius(self):
        for selector in (
            '.pagina-editor-app .painel-word .epub-paper-sheet {',
            '.pagina-editor-app .painel-roteiro .roteiro-page {',
        ):
            block = CSS.split(selector, 1)[1].split('}', 1)[0]
            self.assertIn('border-radius:0!important', block)
            self.assertIn('box-shadow:var(--editor-paper-shadow)', block)

    def test_no_extra_white_editor_surface(self):
        for selector in (
            '.pagina-editor-app .painel-word > .pagina-editor {',
            '.pagina-editor-app .painel-roteiro > .pagina-roteiro {',
        ):
            block = CSS.split(selector, 1)[1].split('}', 1)[0]
            self.assertIn('background:transparent!important', block)
            self.assertIn('box-shadow:none!important', block)


if __name__ == '__main__':
    unittest.main()
