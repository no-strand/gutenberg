"""Parte 2: paginação EPUB sem limite artificial e digitação estável em roteiros longos.

Sem Flask: simula o DOM dos dois editores com CSS de folha real no Chromium.
Os tempos são medidos no benchmark manual, não usados como SLA nestes testes.
"""
import shutil
import pytest

pytest.importorskip('playwright.sync_api')
from playwright.sync_api import sync_playwright
from tests.stress_editores_manual import mount


def launch(p):
    kw = {'headless': True, 'args': ['--no-sandbox', '--disable-background-networking']}
    binary = shutil.which('chromium') or shutil.which('chromium-browser')
    if binary:
        kw['executable_path'] = binary
    return p.chromium.launch(**kw)


def focus_block(page, idx=1):
    page.evaluate('''(idx) => {
      const block = document.querySelectorAll('.roteiro-bloco')[idx];
      const range = document.createRange();
      range.selectNodeContents(block);
      range.collapse(false);
      getSelection().removeAllRanges();
      getSelection().addRange(range);
      block.focus();
      window.__phase2Repaginations = 0;
      const previous = window.repaginateEditor;
      window.repaginateEditor = function(...args) {
        window.__phase2Repaginations++;
        return previous(...args);
      };
    }''', idx)


def test_epub_3000_paragrafos_continuam_sobre_papel():
    with sync_playwright() as p:
        browser = launch(p)
        try:
            page = browser.new_page(viewport={'width': 1440, 'height': 950})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            mount(page, 'epub', 3000)
            page.wait_for_timeout(500)
            result = page.evaluate('''() => {
              const sheets = [...document.querySelectorAll('.epub-paper-sheet')];
              const editor = document.querySelector('#editorTexto');
              const last = editor.lastElementChild.getBoundingClientRect();
              const pageLast = sheets.at(-1).getBoundingClientRect();
              const paper = editor.closest('.pagina-editor').getBoundingClientRect();
              return {
                sheets: sheets.length,
                lastInside: last.bottom <= pageLast.bottom - 20 && last.top >= pageLast.top,
                paperContainsLast: last.bottom <= paper.bottom,
                lastSheetHeight: pageLast.height,
                paragraphs: editor.children.length,
                folio: sheets.at(-1).querySelector('.epub-paper-folio').textContent
              };
            }''')
            assert result['sheets'] > 250, result
            assert result['paragraphs'] == 3000
            assert result['lastInside'] and result['paperContainsLast'], result
            assert result['lastSheetHeight'] < 1500, result
            assert result['folio'] == str(result['sheets']).zfill(2)
            assert not errors, errors
        finally:
            browser.close()


def test_epub_ao_repaginar_reutiliza_folhas_sem_modificar_arvore_editavel():
    with sync_playwright() as p:
        browser = launch(p)
        try:
            page = browser.new_page(viewport={'width': 1440, 'height': 950})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            mount(page, 'epub', 500)
            page.wait_for_timeout(350)
            before = page.evaluate('''() => {
              window.__phase2FirstSheet = document.querySelector('.epub-paper-sheet');
              window.__phase2FirstBlock = document.querySelector('#editorTexto').firstElementChild;
              const before = document.querySelector('#editorTexto').innerHTML;
              window.__phase2FirstBlock.textContent += (' TEXTOESTENDIDO '.repeat(130));
              document.querySelector('#editorTexto').dispatchEvent(new Event('input',{bubbles:true}));
              return { before, after:document.querySelector('#editorTexto').innerHTML };
            }''')
            page.wait_for_timeout(460)
            after = page.evaluate('''() => ({
              firstSheetReused: window.__phase2FirstSheet === document.querySelector('.epub-paper-sheet'),
              firstBlockUnchanged: window.__phase2FirstBlock === document.querySelector('#editorTexto').firstElementChild,
              html: document.querySelector('#editorTexto').innerHTML,
              count:document.querySelectorAll('.epub-paper-sheet').length,
              last:document.querySelector('.epub-paper-sheet:last-child').getBoundingClientRect().bottom,
              paragraph:document.querySelector('#editorTexto').lastElementChild.getBoundingClientRect().bottom
            })''')
            assert before['before'] != before['after']
            assert after['firstSheetReused'] and after['firstBlockUnchanged']
            assert after['html'] == before['after']
            assert after['count'] > 20
            assert after['paragraph'] < after['last']
            assert not errors, errors
        finally:
            browser.close()


def test_roteiro_digitacao_simples_na_primeira_folha_nao_reconstroi_paginas():
    with sync_playwright() as p:
        browser = launch(p)
        try:
            page = browser.new_page(viewport={'width': 1440, 'height': 950})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            mount(page, 'roteiro', 1500)
            page.wait_for_timeout(350)
            focus_block(page)
            page.keyboard.insert_text('z')
            page.keyboard.press('Backspace')
            page.keyboard.insert_text('z')
            page.wait_for_timeout(460)
            result = page.evaluate('''() => ({
              repagination:window.__phase2Repaginations,
              pages:document.querySelectorAll('.roteiro-page').length,
              value:document.querySelectorAll('.roteiro-bloco')[1].textContent,
              saved:serialize().includes('z'),
              selectionInside:document.querySelector('#editorTexto').contains(getSelection().anchorNode)
            })''')
            assert result['repagination'] == 0, result
            assert result['pages'] > 100
            assert result['value'].endswith('z') and result['saved'] and result['selectionInside']
            assert not errors, errors
        finally:
            browser.close()


def test_roteiro_quando_texto_aumenta_de_altura_pagina_normalmente():
    with sync_playwright() as p:
        browser = launch(p)
        try:
            page = browser.new_page(viewport={'width': 1440, 'height': 950})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            mount(page, 'roteiro', 500)
            page.wait_for_timeout(350)
            focus_block(page)
            original_height = page.evaluate("document.querySelectorAll('.roteiro-bloco')[1].getBoundingClientRect().height")
            page.keyboard.insert_text(' TESTEFRASEQUEDEVEMUDARALTURA ' * 18)
            page.wait_for_timeout(680)
            result = page.evaluate('''() => ({
              repagination:window.__phase2Repaginations,
              currentHeight:document.querySelectorAll('.roteiro-bloco')[1].getBoundingClientRect().height,
              pages:document.querySelectorAll('.roteiro-page').length,
              preserved:serialize().includes('TESTEFRASEQUEDEVEMUDARALTURA')
            })''')
            assert result['repagination'] > 0, result
            assert result['pages'] > 30 and result['preserved']
            assert not errors, errors
        finally:
            browser.close()


def test_roteiro_enter_apos_tecla_simples_mantem_paginacao_e_cursor():
    with sync_playwright() as p:
        browser = launch(p)
        try:
            page = browser.new_page(viewport={'width': 1440, 'height': 950})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            mount(page, 'roteiro', 250)
            page.wait_for_timeout(350)
            focus_block(page)
            before = page.locator('.roteiro-bloco').count()
            page.keyboard.insert_text('z')
            page.keyboard.press('Enter')
            page.wait_for_timeout(480)
            result = page.evaluate('''() => ({
              repagination:window.__phase2Repaginations,
              blocks:document.querySelectorAll('.roteiro-bloco').length,
              saved:serialize().includes('z'),
              selectionInside:document.querySelector('#editorTexto').contains(getSelection().anchorNode),
              pages:document.querySelectorAll('.roteiro-page').length
            })''')
            assert result['repagination'] > 0, result
            assert result['blocks'] >= before
            assert result['saved'] and result['selectionInside'] and result['pages'] > 4
            assert not errors, errors
        finally:
            browser.close()
