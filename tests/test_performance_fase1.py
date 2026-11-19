"""Fase 1 de desempenho: cenários integrados em Chromium, sem Flask.

Para medições comparativas (não assertions de tempo) execute
`python tests/stress_editores_manual.py --counts 100 500 1500`.
"""
from pathlib import Path
import shutil
import pytest

pytest.importorskip('playwright.sync_api')
from playwright.sync_api import sync_playwright
from tests.stress_editores_manual import mount


def browser_context():
    return sync_playwright()


def launch(p):
    options = {'headless': True, 'args': ['--no-sandbox']}
    executable = shutil.which('chromium') or shutil.which('chromium-browser')
    if executable:
        options['executable_path'] = executable
    return p.chromium.launch(**options)


def test_epub_ler_margens_somente_na_quebra_de_folha():
    with browser_context() as p:
        browser = launch(p)
        try:
            page = browser.new_page(viewport={'width': 1440, 'height': 950})
            errors = []
            page.on('pageerror', lambda exc: errors.append(str(exc)))
            mount(page, 'epub', 600)
            page.wait_for_timeout(380)
            initial = page.evaluate('''() => ({
                html: document.getElementById('editorTexto').innerHTML,
                paginas: document.querySelectorAll('.epub-paper-sheet').length,
                folhas: Array.from(document.querySelectorAll('.epub-paper-sheet')).map(el => [el.style.top,el.style.height])
            })''')
            assert initial['paginas'] > 20
            page.evaluate('''() => {
                window.__styleReads = 0;
                // Uma alteração no atributo class dispara o mesmo observador
                // que formatações comuns, sem alterar o texto.
                editor.lastElementChild.classList.add('fase1-measure');
            }''')
            page.wait_for_timeout(360)
            final = page.evaluate('''() => ({
                html: document.getElementById('editorTexto').innerHTML,
                paginas: document.querySelectorAll('.epub-paper-sheet').length,
                folhas: Array.from(document.querySelectorAll('.epub-paper-sheet')).map(el => [el.style.top,el.style.height]),
                leituras: window.__styleReads
            })''')
            assert final['paginas'] == initial['paginas']
            assert final['folhas'] == initial['folhas']
            assert 'fase1-measure' in final['html']
            assert final['html'].replace(' class="fase1-measure"', '') == initial['html']
            # Em cada quebra há no máximo duas consultas de margem.
            # É um limite estrutural, não um SLA de tempo dependente da CPU.
            assert final['leituras'] <= 2 * final['paginas'] + 12, final
            assert not errors, errors
        finally:
            browser.close()


def test_roteiro_grande_preserva_blocos_e_serializacao():
    with browser_context() as p:
        browser = launch(p)
        try:
            page = browser.new_page(viewport={'width': 1440, 'height': 950})
            errors = []
            page.on('pageerror', lambda exc: errors.append(str(exc)))
            mount(page, 'roteiro', 250)
            page.wait_for_timeout(300)
            before = page.evaluate('''() => ({
                pages: document.querySelectorAll('.roteiro-page').length,
                blocks: document.querySelectorAll('.roteiro-bloco').length,
                text: document.getElementById('editorTexto').textContent.length
            })''')
            assert before['pages'] > 3
            page.evaluate('''() => {
                const blocks = document.querySelectorAll('.roteiro-bloco');
                const last = blocks[blocks.length-1];
                const r = document.createRange();
                r.selectNodeContents(last);r.collapse(false);
                getSelection().removeAllRanges();getSelection().addRange(r);last.focus();
            }''')
            page.keyboard.insert_text('palavraextra')
            page.wait_for_timeout(630)
            after = page.evaluate('''() => ({
                pages: document.querySelectorAll('.roteiro-page').length,
                blocks: document.querySelectorAll('.roteiro-bloco').length,
                containsWord: document.getElementById('editorTexto').textContent.includes('palavraextra'),
                serialized: serialize().includes('palavraextra'),
                activePage: document.querySelector('.roteiro-page.is-active') !== null
            })''')
            assert after['blocks'] >= before['blocks']
            assert after['pages'] > 3
            assert after['containsWord'] and after['serialized']
            assert not errors, errors
        finally:
            browser.close()

def test_epub_3000_blocos_nao_deve_ultrapassar_ultima_folha():
    """Regressão: documentos com mais de 250 folhas não podem transbordar."""
    with browser_context() as p:
        browser = launch(p)
        try:
            page = browser.new_page(viewport={'width': 1440, 'height': 950})
            mount(page, 'epub', 3000)
            page.wait_for_timeout(600)
            last = page.evaluate('''() => ({
                pagina: document.querySelector('.epub-paper-sheet:last-child').getBoundingClientRect().bottom,
                paragrafo: editor.lastElementChild.getBoundingClientRect().bottom
            })''')
            assert page.locator('.epub-paper-sheet').count() > 250
            assert last['paragrafo'] <= last['pagina'] + 2
        finally:
            browser.close()
