"""V7: toggles e tamanho misto de Informações; texto grande contido nas folhas."""
from pathlib import Path
import re
import shutil

import pytest

playwright = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]


def start_browser(pw):
    executable = shutil.which('chromium') or shutil.which('chromium-browser')
    options = {'headless': True, 'args': ['--no-sandbox']}
    if executable:
        options['executable_path'] = executable
    return pw.chromium.launch(**options)


def add_css(page, *files):
    for name in files:
        css = (ROOT/'static/css'/name).read_text(encoding='utf-8')
        page.add_style_tag(content=re.sub(r'@import url\([^;]+;', '', css))


def resource_page(page, html):
    page.set_content('''<body><main class="pagina-recursos-projeto-shell">
      <div class="recursos-workspace"><nav class="recursos-tabs"><button class="recursos-tab ativo">Informações</button></nav>
      <section class="recursos-painel ativo" data-recursos-panel="informacoes">
        <div class="resource-page-shell"><div class="resource-page-bar"><div class="resource-page-tabs" id="tabsPaginasInfo"></div></div>
          <div class="info-layout"><aside class="info-sidebar"><div id="listaPaginasInfo"></div></aside>
            <article class="info-editor-card"><div class="info-format-toolbar">
              <button class="info-format-btn" data-info-comando="bold">N</button>
              <button class="info-format-btn" data-info-comando="italic">I</button>
              <button class="info-format-btn" data-info-comando="underline">S</button>
              <button class="info-format-btn" data-info-bloco="p">P</button>
              <button class="info-format-btn" data-info-bloco="h1">H1</button>
              <button class="info-format-btn" data-info-bloco="h2">H2</button>
              <button class="info-format-btn" data-info-bloco="h3">H3</button>
              <button class="info-format-btn" data-info-comando="insertUnorderedList">•</button>
              <select id="seletorFonteInfo"><option value="fonte-arial">Arial</option><option value="fonte-georgia">Georgia</option></select>
              <select id="seletorTamanhoFonteInfo"><option value="10">10pt</option><option value="12">12pt</option><option value="15">15pt</option><option value="24">24pt</option><option value="60">60pt</option></select>
            </div><div class="info-editor-toolbar"><input id="tituloPaginaInfo" /></div>
            <div class="info-paper-workspace"><div class="info-paper-stage" id="infoPaperStage">
              <div class="info-paper-layers" id="infoPaperLayers"></div>
              <div class="info-rich-editor" id="editorInfoPagina" contenteditable="true"></div>
            </div></div></article></div></div></section></div></main></body>''')
    page.evaluate('''html => {
      window.PROJETO_SLUG='browser';
      window.PROJETO_RECURSOS_INITIAL={informacoes_abas:[{id:'tab',titulo:'Página inicial',paginas:[{id:'page',titulo:'Ideias',html}]}]};
      window.fetch=async()=>({ok:true,json:async()=>({ok:true})});
    }''', html)
    add_css(page, 'base.css','projeto.css','recursos_projeto.css','fontes-editor.css','ui-system.css','editorial-polish.css','atelier-ui.css')
    page.add_script_tag(path=str(ROOT/'static/js/editor_tipografia.js'))
    page.add_script_tag(path=str(ROOT/'static/js/recursos_projeto.js'))
    page.wait_for_timeout(250)


def select_whole_editor(page):
    page.evaluate('''() => {
      const root=document.getElementById('editorInfoPagina');
      const range=document.createRange(); range.selectNodeContents(root);
      const selection=getSelection();selection.removeAllRanges();selection.addRange(range);
      root.focus();
    }''')


def bounds(page, container, sheet, block):
    return page.evaluate('''([container,sheet,block]) => {
      const stage=document.querySelector(container),base=stage.getBoundingClientRect(),
        pages=[...stage.querySelectorAll(sheet)].map(n=>{
          const r=n.getBoundingClientRect();return {top:r.top-base.top,bottom:r.bottom-base.top,height:r.height};
        }),blocks=[...stage.querySelectorAll(block)].map(n=>{
          const r=n.getBoundingClientRect();return {top:r.top-base.top,bottom:r.bottom-base.top,height:r.height};
        });
      return {pages,blocks};
    }''', [container,sheet,block])


def assert_blocks_on_paper(layout, tolerance=7):
    assert layout['pages'], layout
    # Cada bloco deve ficar sobre uma única folha, sem atravessar o vão cinza.
    for block in layout['blocks']:
        assert any(block['top'] >= sheet['top'] - tolerance and block['bottom'] <= sheet['bottom'] + tolerance
                   for sheet in layout['pages']), (block,layout)
    for i in range(1,len(layout['pages'])):
        assert layout['pages'][i]['top'] >= layout['pages'][i-1]['bottom'] + 25, layout


def test_info_mixed_size_same_first_value_applies_to_all_and_remains_selected():
    with playwright.sync_playwright() as pw:
        browser=start_browser(pw)
        try:
            page=browser.new_page(viewport={'width':1300,'height':900})
            resource_page(page, '<p>Antes <span class="tamanho-fonte-15pt">quinze</span> e <span class="tamanho-fonte-60pt">sessenta</span> e <span class="tamanho-fonte-10pt">dez</span>.</p>')
            select_whole_editor(page)
            expected=page.evaluate('getSelection().toString()')
            assert page.locator('#seletorTamanhoFonteInfo').input_value() == ''
            assert page.locator('#seletorTamanhoFonteInfo option:checked').inner_text() == 'Vários tamanhos'
            page.locator('#seletorTamanhoFonteInfo').select_option('15')
            assert page.evaluate('getSelection().toString()') == expected
            assert not page.locator('#editorInfoPagina [class*="tamanho-fonte-60pt"]').count()
            assert not page.locator('#editorInfoPagina [class*="tamanho-fonte-10pt"]').count()
            assert page.locator('#editorInfoPagina .tamanho-fonte-15pt').count() >= 1
            assert page.locator('#editorInfoPagina').inner_text() == 'Antes quinze e sessenta e dez.'
        finally:
            browser.close()


def test_info_format_toggles_heading_bold_and_list():
    with playwright.sync_playwright() as pw:
        browser=start_browser(pw)
        try:
            page=browser.new_page()
            resource_page(page,'<p>Uma frase inteira.</p>')
            select_whole_editor(page)
            page.locator('[data-info-bloco="h1"]').click()
            assert page.locator('#editorInfoPagina > h1').count()==1
            assert page.locator('[data-info-bloco="h1"]').get_attribute('aria-pressed')=='true'
            page.locator('[data-info-bloco="h1"]').click()
            assert page.locator('#editorInfoPagina > p').count()==1
            select_whole_editor(page)
            page.locator('[data-info-comando="bold"]').click()
            assert page.locator('#editorInfoPagina strong, #editorInfoPagina b').count() >= 1
            assert page.locator('[data-info-comando="bold"]').get_attribute('aria-pressed')=='true'
            page.locator('[data-info-comando="bold"]').click()
            assert page.locator('#editorInfoPagina strong, #editorInfoPagina b').count()==0
            select_whole_editor(page)
            page.locator('[data-info-comando="insertUnorderedList"]').click()
            assert page.locator('#editorInfoPagina ul > li').count() == 1
            page.locator('[data-info-comando="insertUnorderedList"]').click()
            assert page.locator('#editorInfoPagina ul > li').count() == 0
        finally:
            browser.close()


def test_epub_large_paragraph_never_floats_across_paper_gap():
    with playwright.sync_playwright() as pw:
        browser=start_browser(pw)
        try:
            page=browser.new_page(viewport={'width':1400,'height':1000})
            large=' '.join(['dentro, pensou, examinando os rótulos da embalagem']*9)
            page.set_content(f'''<body class="pagina-editor-app" style="--cfg-font-size:20px;--cfg-line-height:1.8">
              <section class="painel-word"><div class="pagina-editor"><div class="editor-texto" id="editorTexto" contenteditable="true">
                <p><span class="tamanho-fonte-60pt">{large}</span></p>
                <p>Um parágrafo pequeno depois do texto muito grande.</p>
              </div></div></section></body>''')
            add_css(page,'editor.css','atelier-ui.css','fontes-editor.css')
            page.add_script_tag(path=str(ROOT/'static/js/epub-pagination.js'))
            page.wait_for_timeout(450)
            layout=bounds(page,'.pagina-editor','.epub-paper-sheet','#editorTexto > p')
            assert len(layout['pages']) >= 2, layout
            assert layout['pages'][0]['height'] >= 1056
            assert_blocks_on_paper(layout)
            assert 'epub-paper-sheet' not in page.locator('#editorTexto').inner_html()
            # Continuar digitando não cria páginas dentro do conteúdo editável.
            page.locator('#editorTexto > p').last.click()
            page.keyboard.type(' Um complemento.')
            page.wait_for_timeout(250)
            assert_blocks_on_paper(bounds(page,'.pagina-editor','.epub-paper-sheet','#editorTexto > p'))
        finally:
            browser.close()


def test_info_large_paragraph_is_inside_its_sheet_and_page_numbers_remain():
    with playwright.sync_playwright() as pw:
        browser=start_browser(pw)
        try:
            page=browser.new_page(viewport={'width':1400,'height':1000})
            large=' '.join(['examinar um texto em letra muito grande para testar as margens']*9)
            resource_page(page,f'<p><span class="tamanho-fonte-60pt">{large}</span></p><p>Outro parágrafo normal.</p>')
            page.wait_for_timeout(300)
            layout=bounds(page,'#infoPaperStage','.info-paper-sheet','#editorInfoPagina > p')
            assert len(layout['pages']) >= 2, layout
            assert_blocks_on_paper(layout)
            assert page.locator('#infoPaperStage .info-paper-folio').count() == len(layout['pages'])
            assert page.locator('#infoPaperStage .info-paper-folio').first.inner_text() == '01'
            assert 'info-paper-sheet' not in page.locator('#editorInfoPagina').inner_html()
        finally:
            browser.close()


def test_info_mixed_sizes_across_paragraphs_and_existing_bold():
    with playwright.sync_playwright() as pw:
        browser=start_browser(pw)
        try:
            page=browser.new_page(viewport={'width':1350,'height':940})
            resource_page(page, '<p><strong>Início</strong> <span class="tamanho-fonte-15pt">normal</span>.</p>'
                                '<p><span class="tamanho-fonte-60pt">Enorme</span> e <span class="tamanho-fonte-10pt"><em>pequeno</em></span>.</p>')
            select_whole_editor(page)
            text=page.evaluate('getSelection().toString()')
            assert page.locator('#seletorTamanhoFonteInfo').input_value()==''
            page.locator('#seletorTamanhoFonteInfo').select_option('24')
            assert page.evaluate('getSelection().toString()')==text
            assert page.locator('#editorInfoPagina > p').count()==2
            assert page.locator('#editorInfoPagina strong').count()==1
            assert page.locator('#editorInfoPagina em').count()==1
            assert page.locator('#editorInfoPagina [class*="tamanho-fonte-60pt"]').count()==0
            assert page.locator('#editorInfoPagina [class*="tamanho-fonte-10pt"]').count()==0
            assert page.locator('#editorInfoPagina [class*="tamanho-fonte-15pt"]').count()==0
            assert page.locator('#editorInfoPagina .tamanho-fonte-24pt').count()>=2
        finally:
            browser.close()
