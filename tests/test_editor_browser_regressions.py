"""Regressões visuais/teclado dos editores (Chromium + Playwright opcionais).

Execute com: python -m pytest tests/test_editor_browser_regressions.py -q
Testa a UI real do contenteditable sem servidor Flask ou dados do usuário.
"""
from pathlib import Path
import shutil

import pytest

playwright = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]


def launch_chromium(pw):
    executable = shutil.which('chromium') or shutil.which('chromium-browser')
    options = {'headless': True, 'args': ['--no-sandbox']}
    if executable:
        options['executable_path'] = executable
    return pw.chromium.launch(**options)


@pytest.fixture
def browser_page():
    with playwright.sync_playwright() as pw:
        browser = launch_chromium(pw)
        page = browser.new_page(viewport={'width': 1440, 'height': 960})
        errors = []
        page.on('pageerror', lambda err: errors.append(str(err)))
        page.set_content('''
          <body class="pagina-editor-app" style="--cfg-font-size:18px;--cfg-line-height:1.6;--cfg-espaco-paragrafo:12px">
            <section class="barra-ferramentas"><button data-comando="bold">N</button></section>
            <section class="painel-word"><div class="pagina-editor">
              <div id="editorTexto" class="editor-texto" contenteditable="true"><p>Início</p></div>
            </div></section>
            <input id="campoTituloCapitulo" value="Capítulo">
            <span id="statusAutosave"></span>
          </body>
        ''')
        page.evaluate('''() => {
          Object.defineProperty(window, 'localStorage', {configurable:true, value:{getItem:()=>null,setItem:()=>{}}});
          window.EDITOR_CONFIG = {slug: 'test', numero: 1};
          window.fetch = async () => ({ok: true, json: async () => ({ok: true})});
        }''')
        page.add_style_tag(path=str(ROOT / 'static/css/editor.css'))
        page.add_style_tag(path=str(ROOT / 'static/css/atelier-ui.css'))
        page.add_script_tag(path=str(ROOT / 'static/js/editor.js'))
        page.evaluate('''() => {
          const p = document.querySelector('#editorTexto p');
          const range = document.createRange();
          range.selectNodeContents(p);
          range.collapse(false);
          getSelection().removeAllRanges();
          getSelection().addRange(range);
          editor.focus();
        }''')
        try:
            yield page
            assert not errors, errors
        finally:
            browser.close()


def state(page):
    return page.evaluate('serializeLogicalSelection()')


def test_enter_backspace_repeated_does_not_jump_to_first_paragraph(browser_page):
    page = browser_page
    for _ in range(8):
        page.keyboard.press('Enter')
    assert page.locator('#editorTexto > p').count() == 9
    assert state(page)['startBlockIndex'] == 8
    for i in range(7, -1, -1):
        page.keyboard.press('Backspace')
        assert state(page)['startBlockIndex'] == i
    assert page.locator('#editorTexto > p').count() == 1
    assert state(page)['startTextOffset'] == len('Início.')
    page.keyboard.type(' fim')
    assert page.locator('#editorTexto').inner_text() == 'Início. fim'


def test_backspace_merges_paragraphs_with_stable_caret(browser_page):
    page = browser_page
    page.evaluate('''() => {
      editor.innerHTML = '<p>Primeiro</p><p><br></p><p>Último</p>';
      const block = editor.children[1], r = document.createRange();
      r.selectNodeContents(block); r.collapse(true);
      getSelection().removeAllRanges(); getSelection().addRange(r);
    }''')
    page.keyboard.press('Backspace')
    assert state(page)['startBlockIndex'] == 0
    assert state(page)['startTextOffset'] == 8
    page.keyboard.type(' +')
    assert page.locator('#editorTexto > p').first.inner_text().startswith('Primeiro +')


def test_formatted_typing_reuses_nodes_and_history(browser_page):
    page = browser_page
    page.locator('button[data-comando="bold"]').click()
    page.keyboard.type('palavra longa com estilo')
    assert page.locator('#editorTexto > p strong').count() <= 2
    assert page.locator('#editorTexto > p strong').last.inner_text().endswith('estilo')
    assert state(page)['startBlockIndex'] == 0
    page.keyboard.press('Control+z')
    assert 'palavra longa' not in page.locator('#editorTexto').inner_text()
    page.keyboard.press('Control+y')
    assert 'palavra longa' in page.locator('#editorTexto').inner_text()


def test_multiline_paste_preserves_suffix_and_empty_lines(browser_page):
    page = browser_page
    page.evaluate('''() => {
      editor.innerHTML = '<p>ABCDEF</p>';
      const node = editor.firstElementChild.firstChild;
      const r = document.createRange(); r.setStart(node,3); r.collapse(true);
      getSelection().removeAllRanges(); getSelection().addRange(r);
      const dt = new DataTransfer(); dt.setData('text/plain','um\\ndois\\n\\ntrês');
      editor.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}));
    }''')
    assert [p.inner_text().strip() for p in page.locator('#editorTexto > p').all()] == ['ABCum','dois','','trêsDEF']
    assert state(page)['startBlockIndex'] == 3
    assert state(page)['startTextOffset'] == 4


def test_epub_pagination_keeps_html_and_selection(browser_page):
    page = browser_page
    page.evaluate('''() => {
      editor.innerHTML = Array.from({length:70},(_,i)=>'<p>Parágrafo '+i+' com conteúdo de teste sem alterar o HTML.</p>').join('');
      markEditorDirty();
      const p=editor.children[50], r=document.createRange();
      r.selectNodeContents(p);r.collapse(false);
      getSelection().removeAllRanges();getSelection().addRange(r);
    }''')
    page.add_script_tag(path=str(ROOT / 'static/js/epub-pagination.js'))
    page.wait_for_timeout(400)
    original = page.evaluate('editor.innerHTML')
    assert page.locator('.epub-paper-sheet').count() > 1
    assert state(page)['startBlockIndex'] == 50
    page.keyboard.type(' texto adicional')
    page.wait_for_timeout(400)
    assert state(page)['startBlockIndex'] == 50
    assert len(page.locator('#editorTexto > p').all()) == 70
    assert 'epub-paper-sheet' not in page.evaluate('editor.innerHTML')
    assert original != page.evaluate('editor.innerHTML')


def test_resources_transparent_frame_and_editor_style():
    with playwright.sync_playwright() as pw:
        browser = launch_chromium(pw)
        page = browser.new_page(viewport={'width': 1440, 'height': 1400})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        paragraphs = ''.join(
            f'<p>Parágrafo {i} com texto suficiente para ocupar espaço visual na folha.</p>'
            for i in range(80)
        )
        page.set_content('''<body class="pagina-recursos-projeto-shell">
          <div class="recursos-workspace"><section class="recursos-painel ativo" data-recursos-panel="informacoes">
            <div class="resource-page-shell"><div class="resource-page-bar">
              <div class="resource-page-tabs" id="tabsPaginasInfo"></div>
              <button id="btnNovaPaginaInfo">+</button>
            </div>
            <div class="info-layout"><aside class="info-sidebar">
              <div id="listaPaginasInfo"></div>
            </aside><article class="info-editor-card">
            <div class="info-editor-fixed-top"><div class="info-format-toolbar">Ferramentas</div>
              <div class="info-editor-toolbar"><input id="tituloPaginaInfo" value="Título"></div>
            </div>
            <div class="info-paper-workspace"><div class="info-paper-stage" id="infoPaperStage">
              <div class="info-paper-layers" id="infoPaperLayers"></div>
              <div id="editorInfoPagina" contenteditable="true" class="info-rich-editor"></div>
            </div></div></article></div></div></section></div></body>''')
        page.evaluate('''(html) => {
          window.PROJETO_SLUG = 'test';
          window.PROJETO_RECURSOS_INITIAL = {
            informacoes_abas: [{
              id: 'info-tab', titulo: 'Página inicial',
              paginas: [{id: 'info-page', titulo: 'Compilado de ideias', html}]
            }, {
              id:'other-tab', titulo:'Outras notas',
              paginas:[{id:'other-page',titulo:'Nota extra',html:'<p>Secundário</p>'}]
            }]
          };
          window.resourceWrites = [];
          window.fetch = async (url, options) => {
            window.resourceWrites.push({url, payload: JSON.parse(options.body)});
            return {ok:true, json:async () => ({ok:true})};
          };
        }''', paragraphs)
        for css in ('base.css', 'projeto.css', 'recursos_projeto.css',
                    'ui-system.css', 'editorial-polish.css', 'atelier-ui.css'):
            page.add_style_tag(path=str(ROOT / 'static/css' / css))
        page.add_script_tag(path=str(ROOT / 'static/js/recursos_projeto.js'))
        page.wait_for_timeout(400)

        # Testa a aba realmente gerada pelo JS, não uma aba HTML fictícia.
        tab = page.locator('#tabsPaginasInfo .resource-page-tab.ativo')
        assert tab.locator('.resource-page-tab-title').inner_text() == 'Página inicial'
        assert tab.locator('input').count() == 0
        assert page.locator('#editorInfoPagina > p').count() == 80
        assert page.locator('.info-paper-sheet').count() >= 2
        assert page.locator('.info-paper-folio').first.inner_text() == '01'
        assert page.locator('.info-paper-folio').nth(1).inner_text() == '02'
        info = page.evaluate('''() => {
          const card = getComputedStyle(document.querySelector('.info-editor-card'));
          const bar = getComputedStyle(document.querySelector('.resource-page-bar'));
          const tabs = getComputedStyle(document.querySelector('.resource-page-tabs'));
          const workspace = getComputedStyle(document.querySelector('.info-paper-workspace'));
          const stage = document.querySelector('.info-paper-stage');
          const editor = getComputedStyle(document.querySelector('.info-rich-editor'));
          return {
            card:card.backgroundColor, bar:bar.backgroundColor,
            tabBackground:tabs.backgroundColor, tabBorder:tabs.borderTopWidth,
            workspaceRadius:workspace.borderRadius,
            workspaceBg:workspace.backgroundColor,
            editorBg:editor.backgroundColor, editorRadius:editor.borderRadius,
            stageWidth:stage.getBoundingClientRect().width,
            stageHeight:stage.getBoundingClientRect().height,
          };
        }''')
        assert info['card'] == 'rgba(0, 0, 0, 0)'
        assert info['bar'] == 'rgba(0, 0, 0, 0)'
        assert info['tabBackground'] == 'rgba(0, 0, 0, 0)'
        assert info['tabBorder'] == '0px'
        assert info['workspaceRadius'] == '16px'
        assert info['workspaceBg'] != 'rgba(0, 0, 0, 0)'
        assert info['editorBg'] == 'rgba(0, 0, 0, 0)'
        assert info['editorRadius'] == '0px'
        assert info['stageWidth'] <= 816
        assert info['stageHeight'] > 1056

        # A edição é opcional, aparece sobre a própria aba e nunca cria caixa.
        tab.dblclick()
        rename = tab.locator('input.resource-page-tab-input')
        assert rename.count() == 1
        style = rename.evaluate('''el => {
          const style=getComputedStyle(el);
          const outer=el.parentElement.getBoundingClientRect();
          const inner=el.getBoundingClientRect();
          return {
            background:style.backgroundColor, border:style.borderTopWidth,
            shadow:style.boxShadow, inside:inner.left>=outer.left && inner.right<=outer.right
          };
        }''')
        assert style == {'background':'rgba(0, 0, 0, 0)', 'border':'0px',
                         'shadow':'none', 'inside':True}
        rename.fill('Minhas ideias')
        rename.press('Enter')
        assert tab.locator('input').count() == 0
        assert tab.locator('.resource-page-tab-title').inner_text() == 'Minhas ideias'
        tab.focus()
        tab.press('F2')
        rename = tab.locator('input.resource-page-tab-input')
        rename.fill('Descartar')
        rename.press('Escape')
        assert tab.locator('.resource-page-tab-title').inner_text() == 'Minhas ideias'
        assert tab.locator('input').count() == 0

        # Sair da renomeação clicando noutra aba não deve interceptar o clique.
        tab.dblclick()
        tab.locator('input').fill('Nome definitivo')
        page.locator('#tabsPaginasInfo .resource-page-tab').nth(1).click()
        assert page.locator('#tabsPaginasInfo .resource-page-tab.ativo .resource-page-tab-title').inner_text() == 'Outras notas'
        page.locator('#tabsPaginasInfo .resource-page-tab').first.click()
        assert tab.locator('.resource-page-tab-title').inner_text() == 'Nome definitivo'
        assert page.locator('#editorInfoPagina > p').count() == 80
        page.wait_for_timeout(800)
        writes = page.evaluate('window.resourceWrites')
        assert any(write['payload'].get('informacoes_abas', [{}])[0].get('titulo') == 'Nome definitivo'
                   for write in writes)
        assert not errors, errors
        browser.close()


def test_delete_forward_keeps_caret_at_join(browser_page):
    page = browser_page
    page.evaluate('''() => {
      editor.innerHTML='<p>ABC</p><p>DEF</p>';
      const r=document.createRange();r.selectNodeContents(editor.firstElementChild);r.collapse(false);
      getSelection().removeAllRanges();getSelection().addRange(r);
    }''')
    page.keyboard.press('Delete')
    assert page.locator('#editorTexto > p').count() == 1
    assert page.locator('#editorTexto > p').inner_text() == 'ABCDEF'
    assert state(page)['startTextOffset'] == 3


def test_font_styled_long_typing_does_not_create_wrappers_per_letter(browser_page):
    page = browser_page
    page.evaluate("selecionarFontePreferida('fonte-inter')")
    page.keyboard.type('x' * 120)
    assert page.locator('#editorTexto span.fonte-inter').count() <= 2
    assert page.locator('#editorTexto').inner_text().endswith('x' * 120)
    assert state(page)['startTextOffset'] == len('Início') + 120


def test_format_across_paragraphs_preserves_selection(browser_page):
    page = browser_page
    page.evaluate('''() => {
      editor.innerHTML='<p>Primeiro</p><p>Segundo</p>';
      const r=document.createRange();
      r.setStart(editor.children[0].firstChild,2);
      r.setEnd(editor.children[1].firstChild,4);
      getSelection().removeAllRanges();getSelection().addRange(r);
    }''')
    page.locator('button[data-comando="bold"]').click()
    assert page.evaluate('editor.textContent') == 'PrimeiroSegundo'
    assert page.locator('#editorTexto strong').count() >= 1
    selection = state(page)
    assert selection['startBlockIndex'] == 0
    assert selection['endBlockIndex'] == 1
    assert not selection['collapsed']


def test_single_paragraph_formatting_preserves_text_and_range(browser_page):
    page = browser_page
    page.evaluate('''() => {
      editor.innerHTML='<p>Texto completo</p>';
      const r=document.createRange();r.setStart(editor.firstChild.firstChild,6);
      r.setEnd(editor.firstChild.firstChild,14);
      getSelection().removeAllRanges();getSelection().addRange(r);
    }''')
    page.locator('button[data-comando="bold"]').click()
    assert page.evaluate('editor.textContent') == 'Texto completo'
    assert 'completo' in page.locator('#editorTexto strong').all_inner_texts()
    assert state(page)['startTextOffset'] == 6
    assert state(page)['endTextOffset'] == 14
    page.locator('button[data-comando="bold"]').click()
    assert page.evaluate('editor.textContent') == 'Texto completo'
    assert page.locator('#editorTexto strong').count() == 0


def test_multiblock_toggle_off_without_nested_paragraphs(browser_page):
    page = browser_page
    page.evaluate('''() => {
      editor.innerHTML='<p>Antes depois</p><p>Outra linha</p>';
      const r=document.createRange();r.setStart(editor.children[0].firstChild,6);
      r.setEnd(editor.children[1].firstChild,5);
      getSelection().removeAllRanges();getSelection().addRange(r);
    }''')
    page.locator('button[data-comando="bold"]').click()
    assert page.locator('#editorTexto strong').count() == 2
    assert page.locator('#editorTexto p p').count() == 0
    page.locator('button[data-comando="bold"]').click()
    assert page.evaluate('editor.textContent') == 'Antes depoisOutra linha'
    assert page.locator('#editorTexto strong').count() == 0
    assert page.locator('#editorTexto > p').count() == 2


def test_enter_backspace_in_middle_of_chapter_never_selects_first_block(browser_page):
    page = browser_page
    page.evaluate('''() => {
      editor.innerHTML='<p>Primeiro capítulo</p><p>Segundo capítulo</p><p>Terceiro capítulo</p>';
      const r=document.createRange();r.selectNodeContents(editor.children[1]);r.collapse(false);
      getSelection().removeAllRanges();getSelection().addRange(r);
    }''')
    for _ in range(5):
        page.keyboard.press('Enter')
    assert state(page)['startBlockIndex'] == 6
    for expected_index in range(5, 0, -1):
        page.keyboard.press('Backspace')
        assert state(page)['startBlockIndex'] == expected_index
    assert page.locator('#editorTexto > p').count() == 3
    assert state(page)['startTextOffset'] == len('Segundo capítulo.')
