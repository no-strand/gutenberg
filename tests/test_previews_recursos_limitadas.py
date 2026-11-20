from __future__ import annotations

from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_previa_compartilhada_tem_limite_e_rolagem_externa():
    css = (ROOT / 'static/css/preview_recursos_hover.css').read_text(encoding='utf-8')
    assert 'max-height: min(234px, calc(100vh - 24px));' in css
    assert 'overflow-y: auto;' in css
    assert 'overscroll-behavior: contain;' in css
    assert '.gutenberg-resource-preview-description' in css
    assert 'max-height: none;' in css
    assert 'overflow: visible;' in css


def test_sem_imagem_nao_acrescenta_icones_de_personagem_ou_lugar():
    js = (ROOT / 'static/js/recursos_projeto.js').read_text(encoding='utf-8')
    view_js = (ROOT / 'static/js/recursos_visualizacao.js').read_text(encoding='utf-8')
    assert "renderCatalogList('personagens', currentCatalogItems('personagens'), $('#listaPersonagensProjeto'))" in js
    assert "renderCatalogList('lugares', currentCatalogItems('lugares'), $('#listaLugaresProjeto'))" in js
    assert "function renderCatalogList(tipo, items, container)" in js
    assert "function openCatalogDetail(tipo, item = null)" in js
    assert "function openCatalogDetail(tipo, item)" in view_js
    assert 'emoji ? emoji' not in js
    assert 'emoji ||' not in view_js
    assert 'Sem imagem de referência' in js and 'Sem imagem de referência' in view_js


def test_previa_com_conteudo_grande_fica_limitada_e_rolavel_no_chromium():
    sync_api = pytest.importorskip('playwright.sync_api')
    chromium = shutil.which('chromium') or shutil.which('chromium-browser')

    with sync_api.sync_playwright() as playwright:
        options = {'headless': True, 'args': ['--no-sandbox']}
        if chromium:
            options['executable_path'] = chromium
        browser = playwright.chromium.launch(**options)
        try:
            page = browser.new_page(viewport={'width': 1000, 'height': 720})
            errors: list[str] = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.set_content('''<!doctype html>
              <html lang="pt-BR"><head><meta charset="utf-8"></head><body>
                <button id="personagem">Personagem</button>
                <button id="lugar">Lugar</button>
              </body></html>''')
            page.add_style_tag(path=str(ROOT / 'static/css/preview_recursos_hover.css'))
            page.add_script_tag(path=str(ROOT / 'static/js/preview_recursos_hover.js'))
            page.evaluate('''() => {
              const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="240" height="620"><rect width="240" height="620" fill="#456"/><text x="12" y="600" fill="white">BOTTOM</text></svg>`;
              const image = `data:image/svg+xml,${encodeURIComponent(svg)}`;
              const description = ('Texto longo para testar a rolagem integral da janela de prévia. ').repeat(24);
              window.GutenbergResourcePreview.bind(document.querySelector('#personagem'), {
                nome: 'Personagem com referência', tipo: 'Personagem', descricao: description, imagem: image
              });
              window.GutenbergResourcePreview.bind(document.querySelector('#lugar'), {
                nome: 'Local com referência', tipo: 'Lugar', descricao: description, imagem: image
              });
            }''')

            for selector in ('#personagem', '#lugar'):
                page.locator(selector).hover()
                preview = page.locator('.gutenberg-resource-preview')
                page.wait_for_function("document.querySelector('.gutenberg-resource-preview')?.classList.contains('is-visible')")
                metrics = preview.evaluate('''el => ({
                  height: el.getBoundingClientRect().height,
                  maxHeight: getComputedStyle(el).maxHeight,
                  overflowY: getComputedStyle(el).overflowY,
                  scrollHeight: el.scrollHeight,
                  clientHeight: el.clientHeight,
                  text: el.innerText
                })''')
                assert metrics['height'] <= 234.5, metrics
                assert metrics['overflowY'] == 'auto', metrics
                assert metrics['scrollHeight'] > metrics['clientHeight'], metrics
                assert 'Texto longo para testar' in metrics['text']
                assert 'is-interactive' in preview.get_attribute('class')

                # Move o ponteiro para dentro da janela: ela não deve sumir e
                # a rolagem precisa funcionar com a roda do mouse.
                rect = preview.bounding_box()
                page.mouse.move(rect['x'] + rect['width'] - 14, rect['y'] + rect['height'] / 2, steps=4)
                page.wait_for_function("document.querySelector('.gutenberg-resource-preview')?.matches(':hover')")
                page.mouse.wheel(0, 420)
                page.wait_for_function("document.querySelector('.gutenberg-resource-preview')?.scrollTop > 0")
                assert preview.evaluate('(el) => el.scrollTop > 0')
                page.mouse.move(950, 680)
                page.wait_for_function("!document.querySelector('.gutenberg-resource-preview')?.classList.contains('is-visible')")

            assert not errors, errors
        finally:
            browser.close()
