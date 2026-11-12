"""Regressões de 60->15pt e barra sticky exclusiva de Informações (Chromium)."""
from pathlib import Path
import re
import shutil

import pytest

playwright = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]


def launch(pw):
    executable = shutil.which('chromium') or shutil.which('chromium-browser')
    opts = {'headless': True, 'args': ['--no-sandbox']}
    if executable:
        opts['executable_path'] = executable
    return pw.chromium.launch(**opts)


def load_css(page, *names):
    for name in names:
        css = (ROOT / 'static/css' / name).read_text(encoding='utf-8')
        page.add_style_tag(content=re.sub(r'@import url\([^;]+;', '', css))


def select_text(page, css, first, last):
    page.evaluate('''([selector,first,last])=>{
      const el=document.querySelector(selector),r=document.createRange();
      const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);
      let n,pos=0,start=null,end=null;
      while(n=walker.nextNode()) {
        if(!start && first<=pos+n.length)start=[n,first-pos];
        if(!end && last<=pos+n.length)end=[n,last-pos];
        pos+=n.length;
      }
      if(!start||!end)throw Error('no text offsets');
      r.setStart(...start);r.setEnd(...end);
      const selection=getSelection();selection.removeAllRanges();selection.addRange(r);
      el.closest('[contenteditable]').focus();
    }''', [css, first, last])


def metrics(page, selector):
    return page.evaluate('''selector=>{
      const block=document.querySelector(selector);
      return {height:block.getBoundingClientRect().height,
        text:block.textContent, html:block.outerHTML,
        selected:getSelection().toString(),
        largeAncestors:[...block.querySelectorAll('[class*="tamanho-fonte-60pt"]')].length};
    }''', selector)


def test_large_to_normal_size_restores_spacing_and_preserves_other_formatting():
    with playwright.sync_playwright() as pw:
        browser=launch(pw)
        try:
            page=browser.new_page()
            page.set_content('''<body class="pagina-editor-app" style="--cfg-font-size:20px;--cfg-line-height:1.8;--cfg-espaco-paragrafo:12px">
              <div class="painel-word"><div class="pagina-editor"><div id="editorTexto" class="editor-texto" contenteditable="true">
                <p>Trecho inicial com uma palavra destacada e final.</p><p>Segunda linha normal.</p>
              </div></div></div></body>''')
            load_css(page,'editor.css','atelier-ui.css','fontes-editor.css')
            page.add_script_tag(path=str(ROOT/'static/js/editor_tipografia.js'))
            original=metrics(page,'#editorTexto > p:first-child')
            # Reproduz uma palavra em meio ao parágrafo, preservando vizinhos.
            first=original['text'].index('palavra')
            select_text(page,'#editorTexto > p:first-child',first,first+len('palavra'))
            page.evaluate('''()=>GutenbergTipografia.applyToSelection(document.querySelector('#editorTexto'),getSelection().getRangeAt(0),'tamanho-fonte-60pt',GutenbergTipografia.isSize)''')
            bigger=metrics(page,'#editorTexto > p:first-child')
            assert bigger['height'] > original['height']
            page.evaluate('''()=>GutenbergTipografia.applyToSelection(document.querySelector('#editorTexto'),getSelection().getRangeAt(0),'tamanho-fonte-15pt',GutenbergTipografia.isSize)''')
            final=metrics(page,'#editorTexto > p:first-child')
            assert final['text']==original['text']
            assert final['selected']=='palavra'
            assert 'tamanho-fonte-15pt' in final['html']
            assert not page.locator('#editorTexto .tamanho-fonte-60pt').count()
            assert abs(final['height']-original['height']) < 2, (original,bigger,final)
        finally:
            browser.close()


def test_copied_large_inline_size_is_removed_from_selected_branch_only():
    with playwright.sync_playwright() as pw:
        browser=launch(pw)
        try:
            page=browser.new_page()
            page.set_content('''<body class="pagina-editor-app" style="--cfg-font-size:20px;--cfg-line-height:1.8">
              <div class="painel-word"><div class="pagina-editor"><div id="editorTexto" class="editor-texto" contenteditable="true">
                <p><span class="fonte-georgia" style="font-size:60pt"><strong>texto destacado de origem externa</strong></span></p>
              </div></div></div></body>''')
            load_css(page,'editor.css','atelier-ui.css','fontes-editor.css')
            page.add_script_tag(path=str(ROOT/'static/js/editor_tipografia.js'))
            select_text(page,'#editorTexto p',0,len('texto destacado de origem externa'))
            page.evaluate('''()=>GutenbergTipografia.applyToSelection(document.querySelector('#editorTexto'),getSelection().getRangeAt(0),'tamanho-fonte-15pt',GutenbergTipografia.isSize)''')
            assert page.locator('#editorTexto p').inner_text()=='texto destacado de origem externa'
            assert not page.locator('#editorTexto [style*="font-size"]').count()
            assert page.locator('#editorTexto .fonte-georgia strong').count()==1
            assert abs(float(page.evaluate('getComputedStyle(document.querySelector("#editorTexto .tamanho-fonte-15pt")).fontSize').replace('px',''))-20)<.1
        finally:
            browser.close()


def test_same_selection_60_to_15_preserves_text_and_bold_in_multiple_paragraphs():
    with playwright.sync_playwright() as pw:
        browser=launch(pw)
        try:
            page=browser.new_page()
            page.set_content('''<body class="pagina-editor-app"><div class="painel-word"><div class="pagina-editor">
              <div id="editorTexto" class="editor-texto" contenteditable="true"><p>Primeiro <strong>forte</strong> trecho.</p><p>Segundo texto.</p></div>
              </div></div></body>''')
            load_css(page,'editor.css','atelier-ui.css','fontes-editor.css')
            page.add_script_tag(path=str(ROOT/'static/js/editor_tipografia.js'))
            select_text(page,'#editorTexto p:first-child',0,len('Primeiro forte trecho.'))
            page.evaluate('''()=>{
              const r=getSelection().getRangeAt(0).cloneRange();r.setEnd(document.querySelectorAll('#editorTexto p')[1].firstChild,6);
              getSelection().removeAllRanges();getSelection().addRange(r);
            }''')
            full=page.locator('#editorTexto').inner_text()
            sel=page.evaluate('getSelection().toString()')
            for size in ('60','15'):
                page.evaluate('''size=>GutenbergTipografia.applyToSelection(document.querySelector('#editorTexto'),getSelection().getRangeAt(0),GutenbergTipografia.sizeClass(size),GutenbergTipografia.isSize)''',size)
            assert page.locator('#editorTexto').inner_text()==full
            assert page.evaluate('getSelection().toString()')==sel
            assert page.locator('#editorTexto strong').count()>=1
            assert not page.locator('#editorTexto .tamanho-fonte-60pt').count()
        finally:
            browser.close()


def test_resources_only_format_toolbar_is_sticky_and_has_epub_buttons():
    with playwright.sync_playwright() as pw:
        browser=launch(pw)
        try:
            page=browser.new_page(viewport={'width':1380,'height':800})
            page.set_content('''<body><main class="pagina-recursos-projeto-shell">
              <div class="recursos-workspace"><nav class="recursos-tabs"><button class="recursos-tab ativo">Informações</button></nav>
                <section class="recursos-painel ativo" data-recursos-panel="informacoes">
                <div class="resource-page-shell"><div class="resource-page-bar"><div class="resource-page-tabs">Página inicial</div></div>
                  <div class="info-layout"><aside class="info-sidebar">Páginas</aside><article class="info-editor-card">
                    <div class="info-format-toolbar info-format-toolbar-sticky">
                      <button class="botao-secundario info-format-btn" data-info-comando="bold">N</button>
                      <button class="botao-secundario info-format-btn" data-info-bloco="p">P</button>
                    </div>
                    <div class="info-editor-toolbar"><input id="tituloPaginaInfo" class="info-title-input" value="Compilado de ideias"></div>
                    <div class="info-paper-workspace"><div class="info-paper-stage" style="height:4200px">
                      <div id="editorInfoPagina" class="info-rich-editor"><p>Parágrafo de teste</p></div>
                    </div></div>
                  </article></div></div></section></div></main></body>''')
            load_css(page,'base.css','projeto.css','recursos_projeto.css','fontes-editor.css','ui-system.css','editorial-polish.css','atelier-ui.css')
            initial=page.evaluate('''()=>{
              const toolbar=document.querySelector('.info-format-toolbar'),title=document.querySelector('.info-editor-toolbar');
              return {position:getComputedStyle(toolbar).position, y:toolbar.getBoundingClientRect().top,
                titlePosition:getComputedStyle(title).position, titleY:title.getBoundingClientRect().top,
                btnBg:getComputedStyle(toolbar.firstElementChild).backgroundColor};}''')
            assert initial['position']=='sticky'
            assert initial['titlePosition']=='static'
            page.evaluate("window.scrollTo({top:1200,behavior:'instant'})")
            page.wait_for_timeout(120)
            scrolled=page.evaluate('''()=>({toolbar:document.querySelector('.info-format-toolbar').getBoundingClientRect().top,
              title:document.querySelector('.info-editor-toolbar').getBoundingClientRect().top,
              scrollY:window.scrollY,docHeight:document.documentElement.scrollHeight,bodyHeight:document.body.scrollHeight, bodyOverflow:getComputedStyle(document.body).overflowY,mainOverflow:getComputedStyle(document.querySelector('main')).overflowY})''')
            assert 60<=scrolled['toolbar']<=90,(initial,scrolled)
            assert scrolled['title']<0,(initial,scrolled)
        finally:
            browser.close()


def test_epub_actual_size_selector_60_then_15_restores_line_height():
    with playwright.sync_playwright() as pw:
        browser = launch(pw)
        try:
            page = browser.new_page()
            errors=[]
            page.on('pageerror',lambda err:errors.append(str(err)))
            page.set_content('''<body class="pagina-editor-app" style="--cfg-font-size:20px;--cfg-line-height:1.8;--cfg-espaco-paragrafo:12px">
              <section class="barra-ferramentas barra-word"><select id="seletorTamanhoFonteEditor"><option value="12">12 pt</option><option value="15">15 pt</option><option value="60">60 pt</option></select></section>
              <div class="painel-word"><div class="pagina-editor"><div id="editorTexto" class="editor-texto" contenteditable="true"><p>Parágrafo normal para comparação.</p></div></div></div>
              <input id="campoTituloCapitulo" value="Capítulo"><span id="statusAutosave"></span>
            </body>''')
            page.evaluate('''()=>{
              Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:()=>null,setItem:()=>{}}});
              window.EDITOR_CONFIG={slug:'test',numero:1};
              window.fetch=async()=>({ok:true,json:async()=>({ok:true})});
            }''')
            load_css(page,'editor.css','atelier-ui.css','fontes-editor.css')
            page.add_script_tag(path=str(ROOT/'static/js/editor_tipografia.js'))
            page.add_script_tag(path=str(ROOT/'static/js/editor.js'))
            text=page.locator('#editorTexto > p').inner_text()
            select_text(page,'#editorTexto > p',0,len(text))
            before=metrics(page,'#editorTexto > p')
            page.locator('#seletorTamanhoFonteEditor').select_option('60')
            assert page.locator('#editorTexto .tamanho-fonte-60pt').count()==1
            page.locator('#seletorTamanhoFonteEditor').select_option('15')
            after=metrics(page,'#editorTexto > p')
            assert after['selected']==text
            assert after['text']==text
            assert abs(before['height']-after['height'])<2,(before,after)
            assert not page.locator('#editorTexto .tamanho-fonte-60pt').count(),after
            assert not errors,errors
        finally:
            browser.close()


def test_resources_real_typography_menu_60_then_15_and_active_format_buttons():
    with playwright.sync_playwright() as pw:
        browser=launch(pw)
        try:
            page=browser.new_page(viewport={'width':1400,'height':1000})
            errors=[]
            page.on('pageerror',lambda err:errors.append(str(err)))
            page.set_content('''<body><main class="pagina-recursos-projeto-shell">
              <div class="recursos-workspace"><nav class="recursos-tabs"><button class="recursos-tab ativo" data-recursos-tab="informacoes">Informações</button></nav>
                <section class="recursos-painel ativo" data-recursos-panel="informacoes">
                <div class="resource-page-shell"><div class="resource-page-bar"><div id="tabsPaginasInfo" class="resource-page-tabs"></div><button id="btnNovaPaginaInfo">+</button></div>
                  <div class="info-layout"><aside class="info-sidebar"><div id="listaPaginasInfo"></div></aside><article class="info-editor-card">
                    <div class="info-format-toolbar info-format-toolbar-sticky">
                      <button class="botao-secundario info-format-btn" data-info-comando="bold">N</button>
                      <button class="botao-secundario info-format-btn" data-info-bloco="p">P</button>
                      <select id="seletorFonteInfo" class="editor-font-select"><option value="fonte-arial">Arial</option><option value="fonte-georgia">Georgia</option></select>
                      <select id="seletorTamanhoFonteInfo" class="editor-size-select"><option value="12">12</option><option value="15">15</option><option value="60">60</option></select>
                    </div>
                    <div class="info-editor-toolbar"><input id="tituloPaginaInfo" class="info-title-input"></div>
                    <div class="info-paper-workspace"><div id="infoPaperStage" class="info-paper-stage"><div id="infoPaperLayers" class="info-paper-layers"></div><div id="editorInfoPagina" class="info-rich-editor" contenteditable="true"></div></div></div>
                  </article></div></div></section></div></main></body>''')
            page.evaluate('''()=>{
              window.PROJETO_SLUG='test';
              window.PROJETO_RECURSOS_INITIAL={informacoes_abas:[{id:'tab',titulo:'Página inicial',paginas:[{id:'page',titulo:'Compilado de ideias',html:'<p>Uma frase de exemplo.</p>'}]}]};
              window.fetch=async()=>({ok:true,json:async()=>({ok:true})});
            }''')
            load_css(page,'base.css','projeto.css','recursos_projeto.css','fontes-editor.css','ui-system.css','editorial-polish.css','atelier-ui.css')
            page.add_script_tag(path=str(ROOT/'static/js/editor_tipografia.js'))
            page.add_script_tag(path=str(ROOT/'static/js/recursos_projeto.js'))
            page.wait_for_timeout(150)
            text=page.locator('#editorInfoPagina p').inner_text()
            select_text(page,'#editorInfoPagina > p',0,len(text))
            baseline=metrics(page,'#editorInfoPagina > p')
            page.locator('#seletorTamanhoFonteInfo').select_option('60')
            assert page.locator('#editorInfoPagina .tamanho-fonte-60pt').count()==1
            page.locator('#seletorTamanhoFonteInfo').select_option('15')
            result=metrics(page,'#editorInfoPagina > p')
            assert result['text']==text
            assert result['selected']==text
            assert abs(baseline['height']-result['height'])<2,(baseline,result)
            assert not page.locator('#editorInfoPagina .tamanho-fonte-60pt').count()
            # O modo ativo acompanha seleção e os controles de formatação.
            page.locator('button[data-info-comando="bold"]').click()
            assert page.locator('#editorInfoPagina b, #editorInfoPagina strong').count()>=1
            assert page.locator('button[data-info-comando="bold"]').get_attribute('aria-pressed')=='true'
            assert not errors,errors
        finally:
            browser.close()
