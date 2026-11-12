"""Integração da tipografia entre EPUB/Informações (Chromium)."""
from pathlib import Path
import shutil
import re
import pytest

playwright = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]


def _browser(pw):
    executable = shutil.which('chromium') or shutil.which('chromium-browser')
    args = {'headless': True, 'args': ['--no-sandbox']}
    if executable:
        args['executable_path'] = executable
    return pw.chromium.launch(**args)


def _select_text(page, selector, start, end):
    page.evaluate('''([selector,start,end]) => {
      const p=document.querySelector(selector);
      const node=p.firstChild;
      const range=document.createRange();
      range.setStart(node,start);range.setEnd(node,end);
      const s=window.getSelection();s.removeAllRanges();s.addRange(range);
      p.closest('[contenteditable="true"]').focus();
    }''', [selector, start, end])


def test_epub_font_size_selects_only_text_and_keeps_caret():
    with playwright.sync_playwright() as pw:
        browser = _browser(pw)
        try:
            page = browser.new_page()
            errors=[]
            page.on('pageerror',lambda e: errors.append(str(e)))
            page.set_content('''<body class="pagina-editor-app" style="--cfg-font-size:18px;--cfg-line-height:1.6">
              <section class="barra-ferramentas barra-word">
                <select id="seletorFonteEditor"><option value="fonte-arial">Arial</option><option value="fonte-inter">Inter</option></select>
                <select id="seletorTamanhoFonteEditor"><option value="12">12 pt</option><option value="24">24 pt</option></select>
              </section>
              <section class="painel-word"><div class="pagina-editor"><div id="editorTexto" class="editor-texto" contenteditable="true"><p>Olá mundo bonito.</p><p>Outro parágrafo de teste.</p></div></div></section>
              <input id="campoTituloCapitulo" value="Capítulo"><span id="statusAutosave"></span>
            </body>''')
            page.evaluate('''() => {
              Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:()=>null,setItem:()=>{}}});
              window.EDITOR_CONFIG={slug:'test',numero:1};
              window.fetch=async()=>({ok:true,json:async()=>({ok:true})});
            }''')
            for name in ('editor.css','atelier-ui.css','fontes-editor.css'):
                page.add_style_tag(content=re.sub(r'@import url\([^;]+;', '', (ROOT/'static/css'/name).read_text('utf-8')))
            page.add_script_tag(path=str(ROOT/'static/js/editor_tipografia.js'))
            page.add_script_tag(path=str(ROOT/'static/js/editor.js'))
            _select_text(page,'#editorTexto > p:first-child',4,9)  # mundo
            assert page.evaluate('window.getSelection().toString()') == 'mundo'
            page.locator('#seletorTamanhoFonteEditor').select_option('24')
            assert page.evaluate('window.getSelection().toString()') == 'mundo'
            assert page.locator('#editorTexto span.tamanho-fonte-24pt').count()==1
            assert page.locator('#editorTexto').inner_text().replace('\n','').startswith('Olá mundo bonito.')
            assert page.evaluate('''() => getComputedStyle(document.querySelector('#editorTexto .tamanho-fonte-24pt')).fontSize''')=='32px'
            # Aplicar fonte depois não destrói a formatação de tamanho.
            page.locator('#seletorFonteEditor').select_option('fonte-inter')
            assert page.evaluate('window.getSelection().toString()') == 'mundo'
            assert page.locator('#editorTexto .tamanho-fonte-24pt').count()==1
            assert page.locator('#editorTexto .fonte-inter').count()>=1
            # Cursor no meio de um parágrafo não salta ao escrever.
            page.evaluate('''() => {
              const text=editor.querySelector('.tamanho-fonte-24pt').firstChild;
              const range=document.createRange();range.selectNodeContents(text);range.collapse(false);
              getSelection().removeAllRanges();getSelection().addRange(range);editor.focus();
            }''')
            page.keyboard.type('!')
            assert 'mundo!' in page.locator('#editorTexto').inner_text()
            assert page.locator('#editorTexto .tamanho-fonte-24pt').count() >= 1
            assert not errors,errors
        finally:
            browser.close()


def test_resources_background_and_text_formatting_persist_between_pages():
    with playwright.sync_playwright() as pw:
        browser = _browser(pw)
        try:
            page=browser.new_page(viewport={'width':1440,'height':900})
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.set_content('''<body><main class="pagina-recursos-projeto-shell">
              <div class="recursos-workspace"><nav class="recursos-tabs"><button class="recursos-tab ativo">Informações</button><button class="recursos-tab">Fluxo</button></nav>
                <section class="recursos-painel ativo" data-recursos-panel="informacoes">
                <div class="resource-page-shell"><div class="resource-page-bar"><div id="tabsPaginasInfo" class="resource-page-tabs"></div><button id="btnNovaPaginaInfo">+</button></div>
                  <div class="info-layout"><aside class="info-sidebar"><div id="listaPaginasInfo"></div></aside><article class="info-editor-card">
                    <div class="info-editor-fixed-top"><div class="info-format-toolbar">
                      <select id="seletorFonteInfo" class="editor-font-select"><option value="fonte-arial">Arial</option><option value="fonte-georgia">Georgia</option></select>
                      <select id="seletorTamanhoFonteInfo" class="editor-size-select"><option value="12">12 pt</option><option value="24">24 pt</option></select>
                    </div><div class="info-editor-toolbar"><input id="tituloPaginaInfo"></div></div>
                    <div class="info-paper-workspace"><div id="infoPaperStage" class="info-paper-stage"><div id="infoPaperLayers" class="info-paper-layers"></div><div id="editorInfoPagina" class="info-rich-editor" contenteditable="true"></div></div></div>
                  </article></div></div></section></div></main></body>''')
            page.evaluate('''() => {
              window.PROJETO_SLUG='test';
              window.PROJETO_RECURSOS_INITIAL={informacoes_abas:[{id:'tab1',titulo:'Página inicial',paginas:[
                {id:'page1',titulo:'Primeira',html:'<p>Um exemplo muito bonito.</p>'},
                {id:'page2',titulo:'Segunda',html:'<p>Outra página.</p>'}
              ]}]};
              window.fetch=async()=>({ok:true,json:async()=>({ok:true})});
            }''')
            for name in ('base.css','projeto.css','recursos_projeto.css','fontes-editor.css','ui-system.css','editorial-polish.css','atelier-ui.css'):
                page.add_style_tag(content=re.sub(r'@import url\([^;]+;', '', (ROOT/'static/css'/name).read_text('utf-8')))
            page.add_script_tag(path=str(ROOT/'static/js/editor_tipografia.js'))
            page.add_script_tag(path=str(ROOT/'static/js/recursos_projeto.js'))
            page.wait_for_timeout(150)
            assert page.evaluate('getComputedStyle(document.querySelector(".recursos-workspace > .recursos-tabs")).backgroundColor')=='rgba(0, 0, 0, 0)'
            _select_text(page,'#editorInfoPagina > p:first-child',3,10) # exemplo
            assert page.evaluate('getSelection().toString()')=='exemplo'
            page.locator('#seletorFonteInfo').select_option('fonte-georgia')
            assert page.evaluate('getSelection().toString()')=='exemplo'
            assert page.locator('#editorInfoPagina span.fonte-georgia').count()==1
            page.locator('#seletorTamanhoFonteInfo').select_option('24')
            assert page.evaluate('getSelection().toString()')=='exemplo'
            assert page.locator('#editorInfoPagina span.tamanho-fonte-24pt').count()==1
            assert page.locator('#editorInfoPagina span.fonte-georgia').count()==1
            assert page.evaluate("getComputedStyle(document.querySelector('#editorInfoPagina .tamanho-fonte-24pt')).fontSize")=='32px'
            # Switching sidebar page stores formatting without sheet nodes in HTML.
            page.locator('#listaPaginasInfo .info-page-item').nth(1).click()
            assert page.locator('#editorInfoPagina').inner_text()=='Outra página.'
            page.locator('#listaPaginasInfo .info-page-item').first.click()
            assert page.locator('#editorInfoPagina span.tamanho-fonte-24pt').count()==1
            assert page.locator('#editorInfoPagina span.fonte-georgia').count()==1
            assert page.locator('#editorInfoPagina .info-paper-sheet').count()==0
            assert not errors,errors
        finally:
            browser.close()


def test_inline_typography_multi_paragraph_selection_is_stable():
    """Aplicar a vários blocos sem serializar 'folhas' no documento e sem perder texto."""
    with playwright.sync_playwright() as pw:
        browser=_browser(pw)
        try:
            page=browser.new_page()
            page.set_content('''<div id="page" contenteditable="true"><p>Primeiro parágrafo</p><p>Segundo parágrafo</p><p>Terceiro parágrafo</p></div>''')
            page.add_script_tag(path=str(ROOT/'static/js/editor_tipografia.js'))
            result=page.evaluate('''() => {
              const editor=document.querySelector('#page');
              const p=editor.querySelectorAll('p');
              const range=document.createRange();
              range.setStart(p[0].firstChild,4);
              range.setEnd(p[2].firstChild,7);
              const before=editor.textContent;
              const selection=getSelection();selection.removeAllRanges();selection.addRange(range);
              const done=GutenbergTipografia.applyToSelection(editor,range,'tamanho-fonte-16pt',GutenbergTipografia.isSize);
              return {done,before,after:editor.textContent,selection:selection.toString(),classes:editor.querySelectorAll('span.tamanho-fonte-16pt').length};
            }''')
            assert result['done'] is True
            assert result['before'] == result['after']
            assert result['classes'] == 3
            assert result['selection'].startswith('eiro parágrafo')
            assert result['selection'].endswith('Terceir')
        finally:
            browser.close()


def test_font_size_typing_reuses_single_span_and_does_not_jump():
    """A digitação formatada deve reutilizar nós em vez de criar um por letra."""
    with playwright.sync_playwright() as pw:
        browser=_browser(pw)
        try:
            page=browser.new_page()
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.set_content('''<body class="pagina-editor-app"><section class="barra-ferramentas barra-word"><select id="seletorTamanhoFonteEditor"><option value="12">12</option><option value="22">22</option></select></section><section class="painel-word"><div class="pagina-editor"><div id="editorTexto" class="editor-texto" contenteditable="true"><p>Começo</p></div></div></section><input id="campoTituloCapitulo" value="A"><span id="statusAutosave"></span></body>''')
            page.evaluate('''() => {Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:()=>null,setItem:()=>{}}});window.EDITOR_CONFIG={slug:'test',numero:1};window.fetch=async()=>({ok:true,json:async()=>({ok:true})});}''')
            page.add_script_tag(path=str(ROOT/'static/js/editor_tipografia.js'))
            page.add_script_tag(path=str(ROOT/'static/js/editor.js'))
            page.evaluate('''() => {
              const p=editor.firstElementChild,r=document.createRange();
              r.selectNodeContents(p);r.collapse(false);
              getSelection().removeAllRanges();getSelection().addRange(r);editor.focus();
            }''')
            page.locator('#seletorTamanhoFonteEditor').select_option('22')
            page.keyboard.type('x'*45)
            assert page.locator('#editorTexto span.tamanho-fonte-22pt').count() <= 2
            assert page.locator('#editorTexto').inner_text().endswith('x'*45)
            assert page.evaluate('serializeLogicalSelection().startBlockIndex') == 0
            page.keyboard.press('Enter')
            assert page.evaluate('serializeLogicalSelection().startBlockIndex') == 1
            page.keyboard.type('mais')
            assert page.locator('#editorTexto > p').count() == 2
            assert not errors,errors
        finally:
            browser.close()
