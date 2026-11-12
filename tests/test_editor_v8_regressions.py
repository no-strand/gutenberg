"""V8: seletor contextual de tamanho no EPUB e realce dos toggles em Informações."""
from pathlib import Path
import re
import shutil

import pytest

pwmod = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]


def browser(pw):
    binary = shutil.which('chromium') or shutil.which('chromium-browser')
    options = {'headless': True, 'args': ['--no-sandbox']}
    if binary:
        options['executable_path'] = binary
    return pw.chromium.launch(**options)


def css(page, *files):
    for name in files:
        style = (ROOT / 'static/css' / name).read_text(encoding='utf-8')
        page.add_style_tag(content=re.sub(r'@import url\([^;]+;', '', style))


def make_epub(page):
    page.set_content('''<body class="pagina-editor-app" style="--cfg-font-size:20px;--cfg-line-height:1.6">
      <section class="barra-ferramentas barra-word">
        <select id="seletorTamanhoFonteEditor">
          <option value="12">12 pt</option><option value="15">15 pt</option>
          <option value="20">20 pt</option><option value="24">24 pt</option><option value="60">60 pt</option>
        </select>
      </section><section class="painel-word"><div class="pagina-editor">
        <div id="editorTexto" class="editor-texto" contenteditable="true">
          <p>Normal <span class="tamanho-fonte-15pt">quinze</span> e <span class="tamanho-fonte-60pt">sessenta</span> texto.</p>
        </div></div></section><input id="campoTituloCapitulo"><span id="statusAutosave"></span>
    </body>''')
    page.evaluate('''() => {
      Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:()=>null,setItem:()=>{}}});
      window.EDITOR_CONFIG={slug:'test',numero:1};
      window.fetch=async()=>({ok:true,json:async()=>({ok:true})});
    }''')
    css(page, 'editor.css', 'atelier-ui.css', 'fontes-editor.css')
    page.add_script_tag(path=str(ROOT / 'static/js/editor_tipografia.js'))
    page.add_script_tag(path=str(ROOT / 'static/js/editor.js'))


def select_epub(page, start_selector, end_selector=None):
    page.evaluate('''([a,b]) => {
      const first=document.querySelector(a),last=document.querySelector(b);
      const r=document.createRange(); r.selectNodeContents(first);
      if(a!==b) r.setEndAfter(last);
      getSelection().removeAllRanges();getSelection().addRange(r);
      document.getElementById('editorTexto').focus();
    }''', [start_selector, end_selector or start_selector])


def test_epub_size_follows_selection_even_after_previous_choice():
    with pwmod.sync_playwright() as pw:
        b = browser(pw)
        try:
            page = b.new_page()
            errors = []
            page.on('pageerror', lambda err: errors.append(str(err)))
            make_epub(page)
            select_epub(page, '.tamanho-fonte-15pt')
            assert page.locator('#seletorTamanhoFonteEditor').input_value() == '15'
            select_epub(page, '.tamanho-fonte-60pt')
            assert page.locator('#seletorTamanhoFonteEditor').input_value() == '60'
            select_epub(page, '.tamanho-fonte-15pt', '.tamanho-fonte-60pt')
            assert page.locator('#seletorTamanhoFonteEditor').input_value() == ''
            assert page.locator('#seletorTamanhoFonteEditor option:checked').inner_text() == 'Vários tamanhos'
            selected_text = page.evaluate('getSelection().toString()')
            page.locator('#seletorTamanhoFonteEditor').select_option('24')
            assert page.evaluate('getSelection().toString()') == selected_text
            assert page.locator('#editorTexto .tamanho-fonte-60pt').count() == 0
            assert page.locator('#editorTexto .tamanho-fonte-15pt').count() == 0
            assert page.locator('#seletorTamanhoFonteEditor').input_value() == '24'
            assert not errors, errors
        finally:
            b.close()


def test_epub_size_at_caret_uses_actual_text_not_old_preference():
    with pwmod.sync_playwright() as pw:
        b = browser(pw)
        try:
            page = b.new_page()
            make_epub(page)
            select_epub(page, '.tamanho-fonte-15pt')
            page.locator('#seletorTamanhoFonteEditor').select_option('24')
            # O tamanho escolhido aparece ao formatar a seleção.
            assert page.locator('#seletorTamanhoFonteEditor').input_value() == '24'
            # Ao mover o cursor para outro span, a escolha anterior não mascara o tamanho real.
            page.evaluate('''() => {
              const text=document.querySelector('#editorTexto .tamanho-fonte-60pt').firstChild;
              const r=document.createRange();r.setStart(text,3);r.collapse(true);
              getSelection().removeAllRanges();getSelection().addRange(r);
              editor.focus();
            }''')
            assert page.locator('#seletorTamanhoFonteEditor').input_value() == '60'
        finally:
            b.close()


def test_info_button_highlight_follows_caret_and_is_visible():
    # Mantém a montagem do editor real de Informações usada na suíte anterior.
    import sys
    sys.path.insert(0, str(ROOT / 'tests'))
    from test_editor_v7_regressions import resource_page, select_whole_editor
    with pwmod.sync_playwright() as pw:
        b = browser(pw)
        try:
            page = b.new_page()
            errors = []
            page.on('pageerror', lambda err: errors.append(str(err)))
            resource_page(page, '<p>Antes texto em negrito e depois.</p>')
            select_whole_editor(page)
            bold = page.locator('[data-info-comando="bold"]')
            bold.click()
            assert bold.get_attribute('aria-pressed') == 'true'
            assert bold.evaluate('(el)=>getComputedStyle(el).backgroundColor') != 'rgba(0, 0, 0, 0)'
            page.evaluate('''() => {
              const root=document.getElementById('editorInfoPagina');
              const strong=root.querySelector('strong,b');
              const r=document.createRange();r.setStart(strong.firstChild,5);r.collapse(true);
              getSelection().removeAllRanges();getSelection().addRange(r);root.focus();
            }''')
            assert bold.get_attribute('aria-pressed') == 'true'
            assert bold.evaluate('(el)=>getComputedStyle(el).backgroundColor') != 'rgba(0, 0, 0, 0)'
            # Fora do trecho em negrito, o realce deve desaparecer.
            page.evaluate('''() => {
              const root=document.getElementById('editorInfoPagina');
              root.innerHTML='<p>Normal <b>negrito</b> texto normal</p>';
              const node=root.querySelector('p').lastChild;
              const r=document.createRange();r.setStart(node,4);r.collapse(true);
              getSelection().removeAllRanges();getSelection().addRange(r);root.focus();
            }''')
            assert bold.get_attribute('aria-pressed') == 'false'
            page.mouse.move(4, 4)  # separar hover do estado toggle
            assert bold.evaluate('(el)=>getComputedStyle(el).backgroundColor') == 'rgba(0, 0, 0, 0)'
            assert not errors, errors
        finally:
            b.close()
