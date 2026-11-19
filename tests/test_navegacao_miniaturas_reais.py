"""Miniaturas 1:1 em escala: clones sem edição, com geometria e conteúdo reais.

Executa a janela real no Chromium; não exige rotas Flask.
"""
import pytest
from tests.test_navegacao_folhas import launch, nav, style, playwright, ROOT


def test_epub_previews_real_text_styles_and_image_without_changing_editor():
    with playwright.sync_playwright() as pw:
        browser = launch(pw)
        try:
            page = browser.new_page(viewport={'width': 1400, 'height': 900}, reduced_motion='reduce')
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.set_content('''<html lang="pt-BR"><body class="pagina-editor-app"
              style="--cfg-font-size:20px;--cfg-line-height:1.6;--cfg-espaco-paragrafo:12px">
              <section class="barra-ferramentas barra-word-sticky"></section>
              <section class="painel-word"><div class="pagina-editor">
              <div class="editor-texto" id="editorTexto" contenteditable="true"></div>
              </div></section></body></html>''')
            for css in ('base.css', 'editor.css', 'editorial-polish.css',
                        'atelier-ui.css', 'fontes-editor.css'):
                style(page, css)
            page.evaluate('''() => {
                const image = `<img alt="Imagem de exemplo" style="width:160px;height:55px"
                  src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='55'%3E%3Crect width='160' height='55' fill='red'/%3E%3C/svg%3E">`;
                document.getElementById('editorTexto').innerHTML =
                '<p class="justificar"><strong>Capítulo de exemplo</strong> ' +
                '<span class="tamanho-fonte-24pt">TIPOGRAFIA ESPECIAL</span> e texto. ' +
                'Palavras de exemplo '.repeat(6) + '</p>' +
                '<p>' + image + '</p>' +
                Array.from({length:140},(_,i) => `<p>Bloco do livro ${i}: ` +
                  'Linhas de teste da página. '.repeat(8) + '</p>').join('');
            }''')
            page.add_script_tag(path=str(ROOT/'static/js/epub-pagination.js'))
            page.wait_for_function('document.querySelectorAll(".epub-paper-sheet").length >= 5')
            nav(page)
            before = page.locator('#editorTexto').inner_html()
            page.keyboard.press('Control+Alt+p')
            page.wait_for_function('document.querySelector(".page-jump-card[data-rendered]") !== null')
            data = page.evaluate('''() => {
              const original=document.querySelector('#editorTexto > p');
              const originalSpan=original.querySelector('.tamanho-fonte-24pt');
              const sheet=document.querySelector('.epub-paper-sheet');
              const thumb=document.querySelector('.page-jump-card[data-page-number="1"]');
              const stage=thumb.querySelector('.page-jump-snapshot');
              const duplicate=stage.querySelector('p');
              const span=duplicate.querySelector('.tamanho-fonte-24pt');
              const img=stage.querySelector('img');
              const origRect=original.getBoundingClientRect(), sheetRect=sheet.getBoundingClientRect();
              const cloneRect=duplicate.getBoundingClientRect(), stageRect=stage.getBoundingClientRect();
              return {
                sameText:original.textContent===duplicate.textContent,
                originalSize:getComputedStyle(originalSpan).fontSize,
                previewSize:getComputedStyle(span).fontSize,
                originalAlign:getComputedStyle(original).textAlign,
                previewAlign:getComputedStyle(duplicate).textAlign,
                imageSource:img?.getAttribute('src'),
                originalTop:origRect.top-sheetRect.top,
                scaledTop:(cloneRect.top-stageRect.top)/(stageRect.width/sheetRect.width),
                ids:stage.querySelectorAll('[id]').length,
                editables:stage.querySelectorAll('[contenteditable]').length,
                cardCount:document.querySelectorAll('.page-jump-card').length,
                renderedCount:document.querySelectorAll('.page-jump-card[data-rendered]').length,
              };
            }''')
            assert data['sameText']
            assert data['originalSize'] == data['previewSize']
            assert data['originalAlign'] == data['previewAlign']
            assert data['imageSource'].startswith('data:image/svg+xml')
            assert abs(data['originalTop'] - data['scaledTop']) < 4
            assert data['ids'] == data['editables'] == 0
            assert data['renderedCount'] < data['cardCount']
            page.locator('.page-jump-card[data-page-number="4"]').click()
            assert page.evaluate('window.scrollY') > 1000
            assert page.locator('#editorTexto').inner_html() == before
            assert not errors, errors
        finally:
            browser.close()


def test_info_previews_real_page_and_not_other_tabs():
    from tests.test_editor_v7_regressions import resource_page
    with playwright.sync_playwright() as pw:
        browser = launch(pw)
        try:
            page=browser.new_page(viewport={'width':1400,'height':960}, reduced_motion='reduce')
            paragraphs = '<h1>Título da página de Informações</h1>' + ''.join(
                f'<p>Personagem {i}: '+('História e atributos. '*8)+'</p>' for i in range(130))
            resource_page(page, paragraphs)
            page.wait_for_function('document.querySelectorAll(".info-paper-sheet").length >= 3')
            nav(page)
            initial=page.locator('#editorInfoPagina').inner_html()
            page.keyboard.press('Control+Alt+p')
            page.wait_for_function('document.querySelector(".page-jump-card[data-rendered]") !== null')
            assert 'Título da página de Informações' in page.locator('.page-jump-card[data-page-number="1"] .page-jump-snapshot').inner_text()
            assert page.locator('.page-jump-card[data-page-number="1"] .info-paper-folio').count() == 1
            assert page.locator('.page-jump-card[data-page-number="1"] .info-rich-editor').count() == 1
            assert page.locator('.page-jump-card[data-page-number="1"] [contenteditable]').count() == 0
            page.locator('.page-jump-card[data-page-number="2"]').click()
            assert page.evaluate('window.scrollY') > 250
            assert page.locator('#editorInfoPagina').inner_html() == initial
        finally:
            browser.close()


def test_script_preview_clones_page_structure_not_only_excerpt():
    with playwright.sync_playwright() as pw:
        browser = launch(pw)
        try:
            page = browser.new_page(viewport={'width':1400,'height':950}, reduced_motion='reduce')
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
            for css in ('base.css','editorial-polish.css','atelier-ui.css','editor.css','editor_roteiro.css'):
                style(page,css)
            page.evaluate('''() => {
                window.EDITOR_CONFIG={slug:'teste',numero:1,catalogoPersonagens:[],catalogoLocais:[],catalogoAnotacoes:[]};
                window.fetch=async()=>({ok:true,json:async()=>({ok:true})});
                document.getElementById('editorTexto').innerHTML=Array.from({length:170},(_,i)=>
                  `<div class="roteiro-bloco" data-block-type="action">ROTEIRO ${i}: `+'Texto da cena. '.repeat(12)+'</div>').join('');
            }''')
            page.add_script_tag(path=str(ROOT/'static/js/editor_roteiro.js'))
            page.wait_for_function('document.querySelectorAll("#editorTexto > .roteiro-page").length >= 5',timeout=25000)
            nav(page)
            old=page.locator('#editorTexto').inner_text()
            page.keyboard.press('Control+Alt+p')
            page.wait_for_function('document.querySelector(".page-jump-card[data-rendered]") !== null')
            data=page.evaluate('''() => {
              const original=document.querySelector('#editorTexto > .roteiro-page');
              const copy=document.querySelector('.page-jump-card[data-page-number="1"] .roteiro-page');
              return {
                sameText:original.innerText === copy.innerText,
                sameBlocks:original.querySelectorAll('.roteiro-bloco').length === copy.querySelectorAll('.roteiro-bloco').length,
                copyFont:getComputedStyle(copy.querySelector('.roteiro-bloco')).fontFamily,
                sourceFont:getComputedStyle(original.querySelector('.roteiro-bloco')).fontFamily,
                hasHeader:Boolean(copy.querySelector('.roteiro-page-header')),
                hasFooter:Boolean(copy.querySelector('.roteiro-page-footer')),
                noIds:copy.querySelectorAll('[id]').length === 0,
                noEditables:copy.querySelectorAll('[contenteditable]').length === 0,
              };
            }''')
            assert data['sameText'] and data['sameBlocks']
            assert data['copyFont'] == data['sourceFont']
            assert data['hasHeader'] and data['hasFooter']
            assert data['noIds'] and data['noEditables']
            page.locator('.page-jump-card[data-page-number="3"]').click()
            assert page.evaluate('window.scrollY') > 1000
            assert page.locator('#editorTexto').inner_text() == old
        finally:
            browser.close()


def test_lazy_previews_release_offscreen_and_on_close():
    with playwright.sync_playwright() as pw:
        browser = launch(pw)
        try:
            page=browser.new_page(viewport={'width':1200,'height':780}, reduced_motion='reduce')
            page.set_content('''<html lang="en-US"><body class="pagina-editor-app">
              <div class="painel-word"><div class="pagina-editor">
              <div class="epub-paper-layers"></div>
              <div id="editorTexto" class="editor-texto" contenteditable="true"></div>
              </div></div></body></html>''')
            for css in ('base.css','editor.css','atelier-ui.css'):
                style(page,css)
            page.evaluate('''() => {
              const layer=document.querySelector('.epub-paper-layers');
              for(let i=0;i<140;i++) {
                const div=document.createElement('div');div.className='epub-paper-sheet';
                div.style.top=`${i*832}px`;div.style.height='800px';
                layer.appendChild(div);
              }
              document.getElementById('editorTexto').innerHTML='<p>Conteúdo longo de testes.</p>';
            }''')
            nav(page,locale='en_US')
            page.keyboard.press('Control+Alt+p')
            page.wait_for_function('document.querySelectorAll(".page-jump-card[data-rendered]").length >= 3')
            first=page.locator('.page-jump-card[data-rendered]').count()
            assert first < 30
            page.evaluate('''() => {const l=document.querySelector('#listaNavegacaoFolhas');l.scrollTop=l.scrollHeight;}''')
            page.wait_for_function('''() => Boolean(document.querySelector('.page-jump-card[data-page-number="140"][data-rendered]'))''',timeout=12000)
            assert page.locator('.page-jump-card[data-page-number="1"][data-rendered]').count() == 0
            page.keyboard.press('Escape')
            assert page.locator('.page-jump-snapshot').count() == 0
            page.keyboard.press('Control+Alt+p')
            assert page.locator('.page-jump-card').count() == 140
        finally:
            browser.close()
