"""Regressões V5: abas, configurações, tipografia EPUB e Recursos (Chromium)."""
from pathlib import Path
import re
import shutil
import pytest

playwright = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]


def load_css(page, *names):
    for name in names:
        css = (ROOT / 'static' / 'css' / name).read_text(encoding='utf-8')
        page.add_style_tag(content=re.sub(r'@import url\([^;]+;', '', css))


def browser_launch(pw):
    name = shutil.which('chromium') or shutil.which('chromium-browser')
    kwargs = {'headless': True, 'args': ['--no-sandbox']}
    if name:
        kwargs['executable_path'] = name
    return pw.chromium.launch(**kwargs)


def test_recursos_faixa_sem_borda_apos_todos_estilos():
    with playwright.sync_playwright() as pw:
        browser=browser_launch(pw)
        try:
            page=browser.new_page()
            page.set_content('''<body><main class="pagina-recursos-projeto-shell"><div class="recursos-workspace">
              <nav class="recursos-tabs"><button class="recursos-tab ativo">Informações</button><button class="recursos-tab">Fluxo</button></nav>
              </div></main></body>''')
            load_css(page, 'base.css','projeto.css','recursos_projeto.css','ui-system.css','editorial-polish.css','atelier-ui.css')
            values=page.evaluate('''() => {
              const nav=getComputedStyle(document.querySelector('.recursos-tabs'));
              const tab=getComputedStyle(document.querySelector('.recursos-tab'));
              return {bg:nav.backgroundColor,border:nav.borderTopWidth,bottom:nav.borderBottomWidth,
                shadow:nav.boxShadow,tabBorder:tab.borderTopWidth};
            }''')
            assert values['bg']=='rgba(0, 0, 0, 0)'
            assert values['border']=='0px'
            assert values['bottom']=='0px'
            assert values['shadow']=='none'
            assert values['tabBorder']!='0px'
        finally:
            browser.close()


def test_configuracoes_botao_branco_e_titulos_escuros():
    with playwright.sync_playwright() as pw:
        browser=browser_launch(pw)
        try:
            page=browser.new_page()
            page.set_content('''<body><section class="painel-configuracoes"><form class="form-config-grid"><button class="botao-primario botao-config-modal"><span class="icone-svg"><svg></svg></span><span>Salvar configurações</span></button></form>
            <div class="preview-folha" id="previewFolha"><h1>Título 1</h1><h2>Título 2</h2><h3>Título 3</h3><p>Texto</p></div></section></body>''')
            load_css(page,'base.css','configuracoes.css','ui-system.css','editorial-polish.css','atelier-ui.css')
            values=page.evaluate('''() => ({btn:getComputedStyle(document.querySelector('.botao-config-modal span:last-child')).color,
                icon:getComputedStyle(document.querySelector('.botao-config-modal svg')).color,
                headers:[...document.querySelectorAll('.preview-folha h1,.preview-folha h2,.preview-folha h3')].map(el=>getComputedStyle(el).color)})''')
            assert values['btn']=='rgb(255, 255, 255)'
            assert values['icon']=='rgb(255, 255, 255)'
            assert values['headers']==['rgb(17, 24, 39)']*3
        finally:
            browser.close()


def test_recursos_regras_globais_e_correcoes_de_entrelinha():
    with playwright.sync_playwright() as pw:
        browser=browser_launch(pw)
        try:
            page=browser.new_page()
            page.set_content('''<body style="--cfg-indent:2.5em;--cfg-indent-maior:4em;--cfg-espaco-paragrafo:1.4em;--cfg-line-height:2.2;--cfg-font-size:23px;--cfg-h1:39px;--cfg-h2:31px;--cfg-h3:25px;">
              <main class="pagina-recursos-projeto-shell"><div class="recursos-workspace"><section class="recursos-painel ativo" data-recursos-panel="informacoes">
                <div class="resource-page-shell"><div class="info-layout"><article class="info-editor-card"><div class="info-paper-workspace"><div class="info-paper-stage">
                <div id="editorInfoPagina" class="info-rich-editor" contenteditable="true">
                  <h1>Primeiro</h1><h2>Segundo</h2><h3>Terceiro</h3><p>Parágrafo <span class="fonte-georgia" style="line-height:4">importado</span></p>
                  <p class="recuo-a-esquerda">Sem recuo</p><p class="recuo-a-direita">Com recuo maior</p>
                </div></div></div></article></div></div></section></div></main></body>''')
            load_css(page,'base.css','projeto.css','recursos_projeto.css','fontes-editor.css','ui-system.css','editorial-polish.css','atelier-ui.css')
            values=page.evaluate('''() => {
              const root=document.querySelector('#editorInfoPagina');
              const ps=[...root.querySelectorAll('p')];
              return {rootSize:getComputedStyle(root).fontSize,rootLine:getComputedStyle(root).lineHeight,
                headings:[...root.querySelectorAll('h1,h2,h3')].map(x=>getComputedStyle(x).fontSize),
                pSpacing:getComputedStyle(ps[0]).marginBottom,
                pIndent:getComputedStyle(ps[0]).textIndent,
                noIndent:getComputedStyle(ps[1]).textIndent,
                bigIndent:getComputedStyle(ps[2]).textIndent,
                spanLine:getComputedStyle(root.querySelector('span')).lineHeight,
                pLine:getComputedStyle(ps[0]).lineHeight,
                }; }''')
            assert values['rootSize']=='23px'
            assert values['rootLine']=='50.6px'
            assert values['headings']==['39px','31px','25px']
            assert values['pSpacing']=='32.2px'
            assert values['pIndent']=='57.5px'
            assert values['noIndent']=='0px'
            assert values['bigIndent']=='92px'
            assert values['spanLine']==values['pLine']=='50.6px'
        finally:
            browser.close()


def test_epub_fonte_colada_mantem_entrelinha_e_tamanho_funciona_na_selecao():
    with playwright.sync_playwright() as pw:
        browser=browser_launch(pw)
        try:
            page=browser.new_page()
            errors=[]
            page.on('pageerror', lambda err: errors.append(str(err)))
            page.set_content('''<body class="pagina-editor-app" style="--cfg-font-size:18px;--cfg-line-height:1.75;--cfg-espaco-paragrafo:12px">
              <section class="barra-ferramentas barra-word"><select id="seletorFonteEditor"><option value="fonte-arial">Arial</option><option value="fonte-georgia">Georgia</option></select>
              <select id="seletorTamanhoFonteEditor"><option value="12">12 pt</option><option value="20">20 pt</option></select></section>
              <section class="painel-word"><div class="pagina-editor"><div id="editorTexto" class="editor-texto" contenteditable="true"><p>Texto copiado com espaçamento</p><p>Outro parágrafo</p></div></div></section>
              <input id="campoTituloCapitulo" value="Capítulo"><span id="statusAutosave"></span></body>''')
            page.evaluate('''() => {
              Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:()=>null,setItem:()=>{}}});
              window.EDITOR_CONFIG={slug:'test',numero:1};window.fetch=async()=>({ok:true,json:async()=>({ok:true})});
            }''')
            load_css(page,'editor.css','atelier-ui.css','fontes-editor.css')
            page.add_script_tag(path=str(ROOT/'static/js/editor_tipografia.js'))
            page.add_script_tag(path=str(ROOT/'static/js/editor.js'))
            page.evaluate('''() => {
              const p=editor.firstElementChild, range=document.createRange();range.setStart(p.firstChild,6);range.setEnd(p.firstChild,13);
              const selection=getSelection();selection.removeAllRanges();selection.addRange(range);editor.focus();
            }''')
            page.locator('#seletorFonteEditor').select_option('fonte-georgia')
            assert page.evaluate('getSelection().toString()')=='copiado'
            page.locator('#seletorTamanhoFonteEditor').select_option('20')
            assert page.evaluate('getSelection().toString()')=='copiado'
            assert page.locator('#editorTexto span.fonte-georgia').count()>=1
            assert page.locator('#editorTexto span.tamanho-fonte-20pt').count()>=1
            vals=page.evaluate('''() => {
              const p=editor.querySelector('p'),span=p.querySelector('.fonte-georgia');
              return {block:getComputedStyle(p).lineHeight,span:getComputedStyle(span).lineHeight,
                size:getComputedStyle(editor.querySelector('.tamanho-fonte-20pt')).fontSize};
            }''')
            assert vals['block']=='31.5px'
            # Aumento intencional do corpo do texto muda a altura de linha desse trecho.
            assert vals['size']=='26.6667px'
            assert vals['span'] in ('31.5px','46.6667px')
            assert not errors,errors
        finally:
            browser.close()
