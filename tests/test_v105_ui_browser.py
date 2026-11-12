"""V1.0.5: marca sem versão e controle de intensidade em navegador real."""
from pathlib import Path
import shutil
import pytest

pwmod = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]


def test_marca_sem_versao_e_slider_presente():
    base = (ROOT / 'templates' / 'base.html').read_text(encoding='utf-8')
    config = (ROOT / 'templates' / 'configuracoes.html').read_text(encoding='utf-8')
    assert '<strong>Gutenberg</strong></span>' in base
    assert '<small>v{{ app_version }}</small>' not in base
    assert 'id="cfgIntensidadeParticulas"' in config
    assert 'name="intensidade_particulas"' in config


def test_slider_de_particulas_respeita_visual_atual_como_minimo():
    with pwmod.sync_playwright() as p:
        options = {'headless': True, 'args': ['--no-sandbox']}
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if executable:
            options['executable_path'] = executable
        browser = p.chromium.launch(**options)
        try:
            page = browser.new_page(viewport={'width': 1000, 'height': 700})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.set_content('''<html><body><canvas id="bg-canvas" aria-hidden="true"></canvas>
              <input type="range" min="1" max="5" step="1" id="cfgIntensidadeParticulas" value="1">
              <span data-valor="cfgIntensidadeParticulas">1/5</span></body></html>''')
            page.add_style_tag(path=str(ROOT / 'static/css/base.css'))
            page.add_style_tag(path=str(ROOT / 'static/css/atelier-ui.css'))
            page.evaluate('''() => {window.APP_CONFIG={intensidadeParticulas:1};}''')
            page.add_script_tag(path=str(ROOT / 'static/js/particulas.js'))
            page.add_script_tag(path=str(ROOT / 'static/js/configuracoes.js'))
            page.wait_for_timeout(140)
            min_opacity = page.evaluate('''() => Number(getComputedStyle(document.getElementById('bg-canvas')).opacity)''')
            assert abs(min_opacity - 0.08) < 0.01
            page.locator('#cfgIntensidadeParticulas').fill('5')
            max_opacity = page.evaluate('''() => Number(getComputedStyle(document.getElementById('bg-canvas')).opacity)''')
            assert max_opacity > min_opacity + 0.25
            assert page.locator('[data-valor="cfgIntensidadeParticulas"]').inner_text() == '5/5'
            page.locator('#cfgIntensidadeParticulas').fill('1')
            restored = page.evaluate('''() => Number(getComputedStyle(document.getElementById('bg-canvas')).opacity)''')
            assert abs(restored - min_opacity) < .01
            assert not errors, errors
        finally:
            browser.close()
