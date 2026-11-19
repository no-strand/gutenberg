"""Navegação por folhas: EPUB, roteiro e Informações, sem aplicação Flask.

A janela é renderizada do include real; os comandos ficam apenas no teclado.
"""
from pathlib import Path
import re
import shutil
import json

import pytest
from jinja2 import Environment, FileSystemLoader

playwright = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]
ENV = Environment(loader=FileSystemLoader(str(ROOT / 'templates')))
TRANSLATIONS = {
    locale: json.loads((ROOT / 'locales' / f'{locale}.json').read_text('utf-8'))
    for locale in ('pt_BR', 'en_US')
}


def parts(locale='pt_BR'):
    def t(key):
        return TRANSLATIONS[locale].get(key, key)
    return ENV.get_template('_navegacao_folhas_modal.html').render(t=t)


def style(page, name):
    css = (ROOT / 'static/css' / name).read_text('utf-8')
    page.add_style_tag(content=re.sub(r'@import url\([^;]+;', '', css))


def nav(page, *, locale='pt_BR'):
    modal = parts(locale)
    page.evaluate('''(modal) => {
      document.body.insertAdjacentHTML('beforeend', modal);
      // Ambos os editores interceptam eventos do cartão dos modais.
      document.querySelector('#modalNavegacaoFolhas [data-modal-card]')
        .addEventListener('click', (event) => event.stopPropagation());
    }''', modal)
    style(page, 'navegacao_folhas.css')
    page.add_script_tag(path=str(ROOT / 'static/js/navegacao_folhas.js'))


def launch(pw):
    options = {'headless': True, 'args':['--no-sandbox']}
    executable = shutil.which('chromium') or shutil.which('chromium-browser')
    if executable: options['executable_path'] = executable
    return pw.chromium.launch(**options)


def test_epub_nav_keeps_selection_and_editor_unchanged():
    with playwright.sync_playwright() as pw:
        browser = launch(pw)
        try:
            page = browser.new_page(viewport={'width':1400,'height':900}, reduced_motion='reduce')
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.set_content('''<html lang="pt-BR"><body class="pagina-editor-app"
              style="--cfg-font-size:19px;--cfg-line-height:1.6;--cfg-espaco-paragrafo:12px">
              <section class="barra-ferramentas barra-word-sticky"></section>
              <section class="painel-word"><div class="pagina-editor">
              <div class="editor-texto" id="editorTexto" contenteditable="true"></div>
              </div></section></body></html>''')
            for name in ('base.css','editor.css','atelier-ui.css','fontes-editor.css'):
                style(page,name)
            page.evaluate('''() => {
              document.getElementById('editorTexto').innerHTML =
              Array.from({length:120},(_,i)=>`<p>Parágrafo ${i}. `+'Um texto longo com palavras. '.repeat(8)+'</p>').join('');
            }''')
            page.add_script_tag(path=str(ROOT / 'static/js/epub-pagination.js'))
            page.wait_for_function("document.querySelectorAll('.epub-paper-sheet').length >= 4")
            nav(page)
            before = page.locator('#editorTexto').inner_html()
            page.evaluate('''() => {
              const text=document.querySelector('#editorTexto p:nth-child(10)').firstChild;
              const r=document.createRange();r.setStart(text,6);r.collapse(true);
              getSelection().removeAllRanges();getSelection().addRange(r);
            }''')
            beforeSelection = page.evaluate('''() => {
              const s=getSelection();return [s.anchorNode.parentElement.closest('p').textContent,s.anchorOffset];
            }''')
            total = page.locator('.epub-paper-sheet').count()
            assert page.locator('.page-jump-controls').count() == 0
            page.keyboard.press('Control+Alt+End')
            assert page.evaluate('window.scrollY') > 1500
            page.keyboard.press('Control+Alt+Home')
            assert page.evaluate('window.scrollY') < 170
            page.keyboard.press('Control+Alt+p')
            assert page.locator('#modalNavegacaoFolhas').is_visible()
            assert page.locator('#tituloModalNavegacaoFolhas').count() == 0
            assert page.locator('#buscaNavegacaoFolhas').count() == 0
            assert page.locator('#listaNavegacaoFolhas .page-jump-card-paper').count() == total
            page.locator(f'#listaNavegacaoFolhas .page-jump-card[data-page-number="{total}"]').click()
            assert not page.locator('#modalNavegacaoFolhas').is_visible()
            assert page.evaluate('window.scrollY') > 1500
            assert page.locator('#editorTexto').inner_html() == before
            assert page.evaluate('''() => {
              const s=getSelection();return [s.anchorNode.parentElement.closest('p').textContent,s.anchorOffset];
            }''') == beforeSelection
            assert not errors, errors
        finally:
            browser.close()


def test_script_nav_lists_real_pages_created_by_editor():
    with playwright.sync_playwright() as pw:
        browser = launch(pw)
        try:
            page = browser.new_page(viewport={'width':1400,'height':950}, reduced_motion='reduce')
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.set_content('''<html lang="pt-BR"><body class="pagina-editor-app">
              <section class="barra-ferramentas barra-roteiro-sticky"></section>
              <section class="roteiro-layout"><aside class="roteiro-sidebar"></aside>
              <section class="painel-editor painel-roteiro"><div class="pagina-editor pagina-roteiro">
              <div class="editor-texto editor-roteiro" id="editorTexto" contenteditable="true"></div>
              </div></section></section>
              <input id="campoTituloCapitulo" value="Roteiro"><span id="statusAutosave"></span>
              <nav id="sumarioRoteiro"></nav><aside id="sidebarCardSumarioRoteiro"></aside>
              <input type="checkbox" id="toggleVisualizacaoRoteiro"><button id="btnToggleVisualizacaoRoteiro"></button>
              </body></html>''')
            for name in ('base.css','editorial-polish.css','atelier-ui.css','editor.css','editor_roteiro.css'):
                style(page,name)
            page.evaluate('''() => {
              window.EDITOR_CONFIG={slug:'teste',numero:1,catalogoPersonagens:[],catalogoLocais:[],catalogoAnotacoes:[]};
              window.fetch=async()=>({ok:true,json:async()=>({ok:true})});
              document.getElementById('editorTexto').innerHTML=Array.from({length:120},(_,i)=>
                `<div class="roteiro-bloco" data-block-type="action">CENA ${i} - `+'Palavras do roteiro. '.repeat(7)+'</div>').join('');
            }''')
            page.add_script_tag(path=str(ROOT / 'static/js/editor_roteiro.js'))
            page.wait_for_function("document.querySelectorAll('#editorTexto > .roteiro-page').length >= 2", timeout=20000)
            nav(page)
            total=page.locator('#editorTexto > .roteiro-page').count()
            initial=page.locator('#editorTexto').inner_text()
            page.keyboard.press('Control+Alt+End')
            assert page.evaluate('window.scrollY') > 250
            page.keyboard.press('Control+Alt+p')
            assert page.locator('#listaNavegacaoFolhas .page-jump-card-paper').count() == total
            page.locator('#listaNavegacaoFolhas .page-jump-card[data-page-number="1"]').click()
            assert page.evaluate('window.scrollY') < 190
            assert page.locator('#editorTexto').inner_text() == initial
            assert not errors, errors
        finally:
            browser.close()


def test_info_nav_only_when_information_tab_is_active():
    from tests.test_editor_v7_regressions import resource_page
    with playwright.sync_playwright() as pw:
        browser = launch(pw)
        try:
            page=browser.new_page(viewport={'width':1400,'height':960}, reduced_motion='reduce')
            errors=[]
            page.on('pageerror', lambda e: errors.append(str(e)))
            paragraphs=''.join(f'<p>Item {i}: '+('Conteúdo do rascunho. '*8)+'</p>' for i in range(120))
            resource_page(page, paragraphs)
            page.evaluate("document.documentElement.lang='pt-BR'")
            nav(page)
            page.wait_for_function("document.querySelectorAll('.info-paper-sheet').length >= 3")
            before=page.locator('#editorInfoPagina').inner_html()
            total=page.locator('.info-paper-sheet').count()
            assert page.locator('[data-page-jump]').count() == 0
            page.keyboard.press('Control+Alt+End')
            assert page.evaluate('window.scrollY') > 250
            page.keyboard.press('Control+Alt+p')
            assert page.locator('#listaNavegacaoFolhas .page-jump-card-paper').count() == total
            # Recursos deve navegar mesmo com stopPropagation no cartão modal.
            page.locator('#listaNavegacaoFolhas .page-jump-card[data-page-number="1"]').click()
            assert not page.locator('#modalNavegacaoFolhas').is_visible()
            assert abs(page.evaluate("document.querySelector('.info-paper-sheet').getBoundingClientRect().top")-24) < 60
            page.keyboard.press('Control+Alt+p')
            page.locator('#modalNavegacaoFolhas .botao-fechar').click()
            assert not page.locator('#modalNavegacaoFolhas').is_visible()
            page.keyboard.press('Control+Alt+p')
            page.keyboard.press('Escape')
            assert not page.locator('#modalNavegacaoFolhas').is_visible()
            page.keyboard.press('Control+Alt+Home')
            assert abs(page.evaluate("document.querySelector('.info-paper-sheet').getBoundingClientRect().top")-24) < 60
            page.evaluate('''() => document.querySelector('[data-recursos-panel="informacoes"]').classList.remove('ativo')''')
            page.keyboard.press('Control+Alt+p')
            assert not page.locator('#modalNavegacaoFolhas').is_visible()
            assert page.locator('#editorInfoPagina').inner_html() == before
            assert not errors, errors
        finally:
            browser.close()


def test_navigation_translations_and_template_integration():
    for locale in ('pt_BR','en_US'):
        modal=parts(locale)
        assert 'data-page-jump-dismiss' in modal
        assert 'data-page-jump="' not in modal
        assert 'role="dialog"' in modal
        assert 'tituloModalNavegacaoFolhas' not in modal
        assert 'buscaNavegacaoFolhas' not in modal
    for name in ('editor.html','editor_roteiro.html','recursos_projeto.html'):
        html=(ROOT/'templates'/name).read_text('utf8')
        assert "{% include '_navegacao_folhas_botoes.html' %}" not in html
        assert 'page-jump-button' not in html
        assert "{% include '_navegacao_folhas_modal.html' %}" in html
        assert "js/navegacao_folhas.js" in html


def test_modal_card_clicks_work_despite_stopped_propagation_and_escape_base_handler():
    with playwright.sync_playwright() as pw:
        browser = launch(pw)
        try:
            page = browser.new_page(viewport={'width':1280,'height':800}, reduced_motion='reduce')
            page.set_content('''<html lang="en-US"><body><section class="barra-ferramentas barra-word-sticky"></section>
              <section class="painel-word"><div class="epub-paper-layers">
              <div class="epub-paper-sheet" style="height:800px"></div>
              <div class="epub-paper-sheet" style="height:800px"></div>
              <div class="epub-paper-sheet" style="height:800px"></div>
              </div><div id="editorTexto" contenteditable="true">Word</div></section></body></html>''')
            for name in ('base.css','editor.css','atelier-ui.css'):
                style(page, name)
            page.evaluate('''() => { window.baseEscapeCount = 0;
                document.addEventListener('keydown', e => {
                  if(e.key === 'Escape') window.baseEscapeCount += 1;
                });
            }''')
            nav(page, locale='en_US')
            page.keyboard.press('Control+Alt+p')
            assert page.locator('#modalNavegacaoFolhas').is_visible()
            page.locator('#modalNavegacaoFolhas .botao-fechar').click()
            assert not page.locator('#modalNavegacaoFolhas').is_visible()

            page.keyboard.press('Control+Alt+p')
            assert page.locator('#listaNavegacaoFolhas .page-jump-card').count() == 3
            page.locator('#listaNavegacaoFolhas button[data-page-number="3"]').click()
            assert not page.locator('#modalNavegacaoFolhas').is_visible()
            assert page.evaluate('window.scrollY') >= 900

            page.keyboard.press('Control+Alt+p')
            page.locator('#modalNavegacaoFolhas .modal-overlay').click(position={'x':4, 'y':4})
            assert not page.locator('#modalNavegacaoFolhas').is_visible()
            page.keyboard.press('Control+Alt+p')
            page.keyboard.press('Escape')
            assert not page.locator('#modalNavegacaoFolhas').is_visible()
            assert page.evaluate('window.baseEscapeCount') == 0
        finally:
            browser.close()
