"""V9: naming and editor workspace styling regression checks."""
from pathlib import Path
import json
import re
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_labels_pt_and_en_are_consistent():
    pt = json.loads((ROOT / 'locales/pt_BR.json').read_text(encoding='utf-8'))
    en = json.loads((ROOT / 'locales/en_US.json').read_text(encoding='utf-8'))
    assert pt['index.workspace_desc'] == 'Escreva, organize e exporte livros e roteiros.'
    assert pt['library.workspace_desc'] == 'Organize, acompanhe e leia livros em EPUBs e PDFs.'
    assert pt['resources.title'] == 'Rascunho'
    assert en['resources.title'] == 'Outline'
    assert pt['resources.project_resources'] == 'Rascunho do projeto'
    assert en['resources.project_resources'] == 'Project outline'
    assert pt['resources.hero_desc'] == 'Crie e organize os aspectos do projeto.'
    assert en['resources.hero_desc'] == 'Create and organize the elements of your project.'
    for catalog in (pt, en):
        assert 'Ctrl+Alt+U' in catalog['resources.project_resources_shortcut']


def test_font_label_and_template_hero():
    book = (ROOT / 'templates/editor.html').read_text(encoding='utf-8')
    resources = (ROOT / 'templates/recursos_projeto.html').read_text(encoding='utf-8')
    options = (ROOT / 'templates/_editor_font_options.html').read_text(encoding='utf-8')
    for text in (book, options):
        assert '>Arial</option>' in text
        assert 'Arial (padrão)' not in text
    assert "{{ t('resources.project_resources') }}" in resources
    assert "{{ t('resources.hero_desc') }}" in resources
    assert "{{ t('resources.project_prefix', project=projeto.titulo) }}" in resources
    assert "{% include '_editor_font_options.html' %}" in resources
    assert 'id="editorInfoPagina"' in resources


def test_browser_inner_shadows_and_pages_unmodified():
    pw = pytest.importorskip('playwright.sync_api')
    executable = shutil.which('chromium') or shutil.which('chromium-browser')
    with pw.sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=executable, args=['--no-sandbox']) if executable else p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content('''<body class="pagina-editor-app">
              <section class="painel-word"><div class="pagina-editor"><div class="epub-paper-sheet"></div></div></section>
              <section class="painel-roteiro"><div class="pagina-roteiro"><div class="roteiro-page"></div></div></section>
              <main class="pagina-recursos-projeto-shell"><section class="recursos-painel ativo" data-recursos-panel="informacoes">
                <article class="info-editor-card"><div class="info-paper-workspace"><div class="info-paper-stage">
                  <div class="info-paper-sheet"></div></div></div></article>
              </section></main></body>''')
            for name in ('base.css', 'projeto.css', 'editor.css', 'editor_roteiro.css',
                         'recursos_projeto.css', 'ui-system.css', 'editorial-polish.css', 'atelier-ui.css'):
                css = (ROOT / 'static/css' / name).read_text(encoding='utf-8')
                # External font imports are not required for computing workspace shadows.
                page.add_style_tag(content=re.sub(r'@import url\([^;]+;', '', css))
            data = page.evaluate('''() => Object.fromEntries(
               ['.painel-word', '.painel-roteiro', '.info-paper-workspace',
                '.epub-paper-sheet', '.roteiro-page', '.info-paper-sheet'].map(sel => {
                  const css=getComputedStyle(document.querySelector(sel));
                  return [sel, {shadow:css.boxShadow, radius:css.borderRadius}];
                }))''')
            for sel in ('.painel-word','.painel-roteiro','.info-paper-workspace'):
                assert 'inset' in data[sel]['shadow'], (sel, data[sel])
                assert data[sel]['radius'] == '16px', (sel, data[sel])
            for sel in ('.epub-paper-sheet','.roteiro-page','.info-paper-sheet'):
                assert 'inset' not in data[sel]['shadow'], (sel, data[sel])
        finally:
            browser.close()

def test_nome_revisao_editorial_e_visual_do_modal_rascunho():
    pt = json.loads((ROOT / 'locales' / 'pt_BR.json').read_text(encoding='utf-8'))
    en = json.loads((ROOT / 'locales' / 'en_US.json').read_text(encoding='utf-8'))
    assert pt['editorial.open'] == 'Revisão Editorial'
    assert pt['editorial.title'] == 'Revisão Editorial'
    assert en['editorial.open'] == 'Editorial Review'
    assert en['editorial.title'] == 'Editorial Review'
    for template_name in ('editor.html', 'editor_roteiro.html'):
        template = (ROOT / 'templates' / template_name).read_text(encoding='utf-8')
        assert "t('editorial.open')" in template
    css = (ROOT / 'static/css/rascunho_modal_visual.css').read_text(encoding='utf-8')
    assert 'modal-recursos-visualizacao .modal-recursos-projeto-card' in css
    assert 'modal-recursos-visualizacao .recursos-tabs-modal .recursos-tab.ativo' in css
    base = (ROOT / 'templates/base.html').read_text(encoding='utf-8')
    assert 'css/rascunho_modal_visual.css' in base
    assert base.index('css/atelier-ui.css') < base.index('css/rascunho_modal_visual.css')
    modal = (ROOT / 'templates/_recursos_visualizacao_modal.html').read_text(encoding='utf-8')
    assert 'id="modalRecursosProjeto"' in modal
    js = (ROOT / 'static/js/recursos_visualizacao.js').read_text(encoding='utf-8')
    assert "ev.ctrlKey && ev.altKey && String(ev.key || '').toLowerCase() === 'u'" in js

