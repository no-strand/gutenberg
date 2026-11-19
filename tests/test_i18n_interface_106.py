"""Internationalization regressions for the 1.0.6 screenplay, EPUB, resource and reader UIs.

No Flask installation is required: we render the actual Jinja templates with both locale catalogs.
"""
from pathlib import Path
import json
import re
from types import SimpleNamespace as NS

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]
PT = json.loads((ROOT / 'locales/pt_BR.json').read_text(encoding='utf-8'))
EN = json.loads((ROOT / 'locales/en_US.json').read_text(encoding='utf-8'))


def render(name, locale):
    def t(key, **values):
        return locale.get(key, key).format(**values)

    env = Environment(loader=FileSystemLoader(str(ROOT / 'templates')), autoescape=True)
    env.filters['data_br'] = str
    env.filters['data_hora_br'] = str
    cfg = NS(efeito_editor=True, intensidade_particulas=1, identacao_paragrafo_em=1,
             identacao_paragrafo_maior_em=2, espaco_paragrafos_em=.5, espaco_linhas=1.6,
             tamanho_fonte_px=16, h1_px=30, h2_px=24, h3_px=20, largura_leitura_px=800,
             leitor_tema='light', leitor_fonte='arial', leitor_tamanho_fonte_px=20,
             leitor_tts_velocidade=1, leitor_tts_volume=100, leitor_largura_percentual=90,
             idioma_tts='en_US' if locale is EN else 'pt_BR')
    context = {
        't': t, 'url_for': lambda name, **kw: '/' + name,
        'icon_svg': lambda name: '', 'config_global': cfg,
        'idioma_app': 'en_US' if locale is EN else 'pt_BR',
        'i18n_catalog': locale, 'request': NS(path='/projetos/demo/roteiro/1'),
        'app_version': '1.0.6', 'projeto': NS(slug='demo', idioma='en_US' if locale is EN else 'pt_BR', descricao='', capitulos=[]),
        'roteiro': {'titulo': 'Test', 'html_editor': '<div class="roteiro-bloco" data-block-type="action">Test</div>',
                    'tipo_roteiro_label': 'Spec Script'},
        'capitulo': NS(titulo='Test', paragrafos=['<p>Text</p>']), 'livro': NS(slug='demo', titulo='Test', progresso_percentual=0, capitulos=[]), 'numero': 1,
        'conteudo_url': '/test.xhtml', 'posicao_inicial': 0, 'capitulo_anterior': None,
        'proximo_capitulo': None, 'recursos': {}, 'estado_recursos': {}, 'projeto_recursos': {},
    }
    return BeautifulSoup(env.get_template(name).render(context), 'html.parser')


def test_all_translations_exist_in_both_languages():
    assert PT.keys() == EN.keys()
    assert len(EN) >= 900
    for key, text in EN.items():
        if isinstance(text, str):
            assert re.search(r'\b(?:Salvar|Excluir|Diálogo|Ação|Música|Tamanho da fonte|Página inicial)\b', text) is None, (key, text)


def test_screenplay_toolbar_captions_and_tooltips_in_english_and_portuguese():
    expected_en = dict(scene_heading='Scene', action='Action', character='Char.', dialogue='Dialogue',
                       parenthetical='Parentheses', shot='Shot', transition='Transition',
                       comment='Note', music='Music', neutral='Free')
    expected_pt = dict(scene_heading='Cena', action='Ação', character='Personagem', dialogue='Diálogo',
                       parenthetical='Parênteses', shot='Plano', transition='Transição',
                       comment='Nota', music='Música', neutral='Livre')
    for locale, expected in [(EN, expected_en), (PT, expected_pt)]:
        page = render('editor_roteiro.html', locale)
        buttons = page.select('.btn-tipo-bloco')
        assert len(buttons) == 10
        for button in buttons:
            kind = button['data-block-type']
            assert button.get_text(strip=True) == expected[kind]
            assert button['title'] == button['aria-label']
            assert 'Alt+' in button['title']
        assert page.select_one('#indicadorTipoBloco').get_text(strip=True) == locale['script.editor_block_action']


def test_epub_and_resources_typography_translated():
    for name in ('editor.html', 'recursos_projeto.html'):
        en_page = render(name, EN)
        pt_page = render(name, PT)
        assert en_page.select_one('.editor-font-picker-label').get_text(strip=True) == 'Font'
        assert en_page.select_one('.editor-size-picker-label').get_text(strip=True) == 'Font size'
        assert [el['label'] for el in en_page.select('.editor-font-select optgroup')] == ['Sans-serif', 'Serif', 'Monospace']
        assert pt_page.select_one('.editor-font-picker-label').get_text(strip=True) == 'Fonte'
        assert [el['label'] for el in pt_page.select('.editor-font-select optgroup')] == ['Sans-serif', 'Serifada', 'Monoespaçada']
        assert en_page.select_one('option[value="10.5"]').get_text(strip=True) == '10.5 pt'
        assert pt_page.select_one('option[value="10.5"]').get_text(strip=True) == '10,5 pt'
    en_epub = render('editor.html', EN)
    pt_epub = render('editor.html', PT)
    for command, expected in [('bold','B'),('italic','I'),('underline','U')]:
        assert en_epub.select_one(f'button[data-comando="{command}"] strong,button[data-comando="{command}"] em,button[data-comando="{command}"] u').get_text(strip=True) == expected
    assert pt_epub.select_one('button[data-comando="bold"] strong').get_text(strip=True) == 'N'
    assert pt_epub.select_one('button[data-comando="underline"] u').get_text(strip=True) == 'S'
    en_page = render('recursos_projeto.html', EN)
    assert [el.get_text(strip=True) for el in en_page.select('.ia-recurso-alvo > span')] == [
        EN['resources.ai_target_info_desc'], EN['resources.ai_target_character_desc'],
        EN['resources.ai_target_place_desc'], EN['resources.ai_target_note_desc'],
    ]


def test_reader_aria_labels_and_settings_translated():
    for name in ('leitor.html', 'leitor_alt.html'):
        en = render(name, EN)
        pt = render(name, PT)
        assert en.select_one('#botaoTtsLeitor')['title'] == 'Read aloud'
        assert en.select_one('#controleVelocidadeTts')['aria-label'] == 'Read aloud speed'
        assert en.select_one('#controleLargura')['aria-label'] == 'Text width'
        assert en.select_one('#valorVelocidadeTts').get_text(strip=True) == '1.00×'
        assert pt.select_one('#valorVelocidadeTts').get_text(strip=True) == '1,00×'
        assert en.select_one('[data-font-size-step="-1"]')['aria-label'] == 'Decrease font size'
        assert en.select_one('[data-font-size-step="1"]')['aria-label'] == 'Increase font size'


def test_runtime_mixed_size_and_tts_are_localized():
    epub = (ROOT/'static/js/editor.js').read_text()
    info = (ROOT/'static/js/recursos_projeto.js').read_text()
    tts = (ROOT/'static/js/leitor_tts.js').read_text()
    assert "i18n('editor.mixed_font_sizes')" in epub
    assert "'editor.mixed_fonts' : 'editor.mixed_font_sizes'" in info
    assert "traduzir('reader.read_aloud'" in tts
    assert "traduzir('reader.pause_aloud'" in tts
    assert EN['editor.mixed_font_sizes'] == 'Multiple sizes'
    assert EN['editor.mixed_fonts'] == 'Multiple fonts'


def test_chromium_epub_mixed_font_selection_uses_english_catalog():
    import shutil
    import pytest
    pw = pytest.importorskip('playwright.sync_api')
    from tests.test_editor_v8_regressions import make_epub, select_epub, browser
    with pw.sync_playwright() as driver:
        chromium = browser(driver)
        try:
            page = chromium.new_page()
            make_epub(page)
            page.evaluate("window.t = (key) => ({'editor.mixed_font_sizes': 'Multiple sizes'})[key] || key")
            select_epub(page, '.tamanho-fonte-15pt', '.tamanho-fonte-60pt')
            assert page.locator('#seletorTamanhoFonteEditor option:checked').inner_text() == 'Multiple sizes'
        finally:
            chromium.close()
