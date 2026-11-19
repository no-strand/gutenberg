"""Parte 5: lock de escritor por documento e regressão de integridade.

No ambiente de testes, a origem about:blank não oferece o Web Locks API.
O gerenciador compartilhado abaixo simula APENAS a sua semântica de
exclusividade e liberação; a implementação nativa será validada no app real.
"""
import json
import shutil
import threading

import pytest

pytest.importorskip('playwright.sync_api')
from playwright.sync_api import sync_playwright
from tests.test_integridade_fase4 import carregar, alterar, navegador


@pytest.fixture
def contexto_com_locks():
    with sync_playwright() as pw:
        args = {'headless': True, 'args': ['--no-sandbox', '--disable-background-networking']}
        exe = shutil.which('chromium') or shutil.which('chromium-browser')
        if exe:
            args['executable_path'] = exe
        browser = pw.chromium.launch(**args)
        ctx = browser.new_context(viewport={'width': 1360, 'height': 900})
        ativos = set()
        mutex = threading.Lock()

        def reservar(name):
            with mutex:
                if name in ativos:
                    return False
                ativos.add(name)
                return True

        def soltar(name):
            with mutex:
                ativos.discard(name)
            return True

        ctx.expose_function('__reservarSessaoTeste', reservar)
        ctx.expose_function('__soltarSessaoTeste', soltar)
        try:
            yield ctx, ativos
        finally:
            browser.close()


def abrir_com_lock(ctx, modo, *, storage=None, slug='projeto-fase4', numero=11):
    page = ctx.new_page()
    erros = []
    page.on('pageerror', lambda error: erros.append(str(error)))
    # O script do editor é carregado pelo helper depois da definição do mock.
    # A requisição ifAvailable permite apenas um escritor por nome de lock.
    page.evaluate('''() => {
      Object.defineProperty(navigator, 'locks', {configurable: true, value: {
        request: async (name, options, callback) => {
          if (!options?.ifAvailable || options.mode !== 'exclusive') throw Error('Uso incorreto do lock');
          const reservado = await window.__reservarSessaoTeste(name);
          try { return await callback(reservado ? {name} : null); }
          finally { if (reservado) await window.__soltarSessaoTeste(name); }
        }
      }});
    }''')
    carregar(page, modo, storage=storage, sessao=True)
    if slug != 'projeto-fase4' or numero != 11:
        # Os dois editores só consultam esta configuração ao carregar;
        # para a prova de isolamento usamos um segundo contexto/editor.
        raise ValueError('Identificação de documento não suportada pelo helper')
    page.wait_for_function("typeof sessaoEpub !== 'undefined' && sessaoEpub || typeof sessaoRoteiro !== 'undefined' && sessaoRoteiro")
    return page, erros


@pytest.mark.parametrize('modo', ['epub', 'roteiro'])
def test_segunda_aba_somente_leitura_sem_autosave_ou_limpeza_do_rascunho(contexto_com_locks, modo):
    ctx, ativos = contexto_com_locks
    primeira, err1 = abrir_com_lock(ctx, modo)
    segunda = None
    try:
        nome = 'sessaoEpub' if modo == 'epub' else 'sessaoRoteiro'
        primeira.wait_for_function(f'{nome}.estado() === "ativo"')
        alterar(primeira, modo, 'RASCUNHO PENDENTE DA PRIMEIRA ABA')
        primeira.evaluate("rascunhoLocal" + ('Roteiro' if modo == 'roteiro' else 'Epub') + '.copiarAgora()')
        copia = primeira.evaluate('window.__draftStore')
        assert len(copia) == 1, copia

        segunda, err2 = abrir_com_lock(ctx, modo, storage=copia)
        segunda.wait_for_function(f'{nome}.estado() === "bloqueado"')
        assert segunda.locator('#editorTexto').get_attribute('contenteditable') == 'false'
        assert segunda.locator('#campoTituloCapitulo').is_disabled()
        assert segunda.locator('.editor-sessao-aviso').count() == 1
        assert segunda.locator('.editor-recuperacao-aviso').count() == 0
        assert 'Recarregar' in segunda.locator('.editor-sessao-aviso').inner_text()
        segunda.evaluate('''() => {window.__envios=[];window.fetch=async(u,opts)=>{
            window.__envios.push(opts.body);return {ok:true,json:async()=>({ok:true})};
        };}''')
        # Mesmo uma chamada programática não pode gravar a versão obsoleta.
        alterar(segunda, modo, 'ALTERAÇÃO QUE NÃO DEVE SER ENVIADA')
        segunda.evaluate('void doAutosave(true)' if modo == 'roteiro' else 'void executarAutosave()')
        segunda.evaluate('window.dispatchEvent(new Event("pagehide"))')
        segunda.wait_for_timeout(80)
        assert segunda.evaluate('window.__envios.length') == 0
        assert segunda.evaluate('window.__draftStore') == copia
        assert not err1 + err2, err1 + err2
    finally:
        if segunda:
            segunda.close()
        primeira.close()


@pytest.mark.parametrize('modo', ['epub', 'roteiro'])
def test_apos_fechar_primeira_aba_nova_abertura_obtem_lock(contexto_com_locks, modo):
    ctx, ativos = contexto_com_locks
    primeira, _ = abrir_com_lock(ctx, modo)
    nome = 'sessaoEpub' if modo == 'epub' else 'sessaoRoteiro'
    try:
        primeira.wait_for_function(f'{nome}.estado() === "ativo"')
        primeira.evaluate("window.dispatchEvent(new Event('pagehide'))")
        primeira.wait_for_function(f'{nome}.estado() === "encerrado"')
        primeira.wait_for_timeout(60)
    finally:
        primeira.close()
    segunda, erros = abrir_com_lock(ctx, modo)
    try:
        segunda.wait_for_function(f'{nome}.estado() === "ativo"')
        assert segunda.locator('#editorTexto').get_attribute('contenteditable') == 'true'
        assert not segunda.locator('#campoTituloCapitulo').is_disabled()
        assert segunda.locator('.editor-sessao-aviso').count() == 0
        assert not erros, erros
    finally:
        segunda.close()


def test_capitulo_epub_e_roteiro_nao_competem_pelo_mesmo_lock(contexto_com_locks):
    ctx, ativos = contexto_com_locks
    epub, ep_err = abrir_com_lock(ctx, 'epub')
    roteiro, rt_err = abrir_com_lock(ctx, 'roteiro')
    try:
        epub.wait_for_function('sessaoEpub.estado() === "ativo"')
        roteiro.wait_for_function('sessaoRoteiro.estado() === "ativo"')
        assert len(ativos) == 2
        assert not ep_err + rt_err
    finally:
        epub.close()
        roteiro.close()


def test_conflito_nao_aplica_recuperacao_antes_de_obter_lock(contexto_com_locks):
    ctx, _ = contexto_com_locks
    primeira, _ = abrir_com_lock(ctx, 'epub')
    segunda = None
    try:
        primeira.wait_for_function('sessaoEpub.estado() === "ativo"')
        primeira.evaluate("editor.querySelector('p').textContent='ORIGINAL DA OUTRA ABA'; markEditorDirty();rascunhoLocalEpub.copiarAgora();")
        copia = primeira.evaluate('window.__draftStore')
        segunda, erros = abrir_com_lock(ctx, 'epub', storage=copia)
        segunda.wait_for_function('sessaoEpub.estado() === "bloqueado"')
        assert segunda.locator('#editorTexto').inner_text() == 'ORIGINAL EPUB'
        # Nem o botão de recuperação deve ser apresentado na aba bloqueada.
        assert segunda.locator('.editor-recuperacao-restaurar').count() == 0
        assert not erros
    finally:
        if segunda: segunda.close()
        primeira.close()


@pytest.mark.parametrize('modo', ['epub', 'roteiro'])
def test_primeira_aba_guarda_copia_no_pagehide_antes_de_soltar_lock(contexto_com_locks, modo):
    ctx, ativos = contexto_com_locks
    page, erros = abrir_com_lock(ctx, modo)
    nome = 'sessaoEpub' if modo == 'epub' else 'sessaoRoteiro'
    try:
        page.wait_for_function(f'{nome}.estado() === "ativo"')
        alterar(page, modo, 'ÚLTIMA DIGITAÇÃO SEM ESPERAR DEBOUNCE')
        # A cópia ainda não existe (menos que os 280 ms de debounce).
        assert len(page.evaluate('window.__draftStore')) == 0
        page.evaluate("window.dispatchEvent(new Event('pagehide'))")
        copia = page.evaluate('window.__draftStore')
        assert len(copia) == 1 and 'ÚLTIMA DIGITAÇÃO' in list(copia.values())[0]
        assert not erros
    finally:
        page.close()


def test_epub_e_roteiro_sobrevivem_reabertura_do_banco(tmp_path):
    """Salva documentos grandes no SQLite real e os relê por outra conexão."""
    from modules import manipulador_capitulos, manipulador_roteiros
    from modules.persistencia_editor_db import BancoEditorLocal

    pasta = tmp_path / 'projeto'
    pasta.mkdir()
    cap = manipulador_capitulos.criar_capitulo(pasta, 'Capítulo original')
    numero_cap = cap['id']
    html_livro = ''.join(
        f'<p class="alinhar-esquerda">Linha {i} com acentuação, <strong>negrito</strong> e café.</p>'
        for i in range(700)
    )
    manipulador_capitulos.salvar_capitulo(pasta, numero_cap, 'Capítulo persistido', html_livro)

    roteiro = manipulador_roteiros.criar_roteiro(pasta, 'Roteiro original')
    numero_roteiro = roteiro.get('id', 1)
    html_roteiro = ''.join(
        f'<div class="roteiro-bloco" data-block-type="action">AÇÃO {i} — acentuação.</div>'
        for i in range(700)
    )
    manipulador_roteiros.salvar_roteiro(pasta, numero_roteiro, 'ROTEIRO PERSISTIDO', html_roteiro)

    # Nova instância: a leitura deve vir do banco persistido, não do DOM ou
    # dos caches de serialização dos navegadores.
    banco = BancoEditorLocal(pasta)
    lido_livro = banco.ler_capitulo(numero_cap)
    lido_roteiro = banco.ler_roteiro(numero_roteiro)
    assert lido_livro['titulo'] == 'Capítulo persistido'
    assert lido_livro['paragrafos'][0] == html_livro
    assert lido_roteiro['titulo'] == 'ROTEIRO PERSISTIDO'
    assert html_roteiro in (lido_roteiro.get('html_editor') or str(lido_roteiro.get('paragrafos', [])))


@pytest.mark.parametrize('modo', ['epub', 'roteiro'])
def test_reabertura_com_lock_oferece_copia_e_restauracao_explicita(contexto_com_locks, modo):
    ctx, _ = contexto_com_locks
    nome = 'sessaoEpub' if modo == 'epub' else 'sessaoRoteiro'
    primeira, erros_primeira = abrir_com_lock(ctx, modo)
    try:
        primeira.wait_for_function(f'{nome}.estado() === "ativo"')
        alterar(primeira, modo, 'ÚLTIMO PARÁGRAFO — NÃO SALVO')
        primeira.evaluate("window.dispatchEvent(new Event('pagehide'))")
        copia = primeira.evaluate('window.__draftStore')
        assert len(copia) == 1
        primeira.wait_for_timeout(50)
    finally:
        primeira.close()
    segunda, erros_segunda = abrir_com_lock(ctx, modo, storage=copia)
    try:
        segunda.wait_for_function(f'{nome}.estado() === "ativo"')
        segunda.wait_for_function("document.querySelectorAll('.editor-recuperacao-aviso').length === 1")
        assert 'ÚLTIMO PARÁGRAFO' not in segunda.locator('#editorTexto').inner_text()
        segunda.evaluate("window.fetch = async () => ({ok:true,json:async()=>({ok:true})})")
        segunda.locator('.editor-recuperacao-restaurar').click()
        assert 'ÚLTIMO PARÁGRAFO' in segunda.locator('#editorTexto').inner_text()
        segunda.evaluate('void doAutosave(true)' if modo=='roteiro' else 'void executarAutosave()')
        segunda.wait_for_function("document.getElementById('statusAutosave').classList.contains('status-salvo')")
        assert not erros_primeira + erros_segunda
    finally:
        segunda.close()


@pytest.mark.parametrize('modo', ['epub', 'roteiro'])
def test_sem_web_locks_editor_permanece_utilizavel(navegador, modo):
    """Compatibilidade: WebViews sem Web Locks não devem travar o editor."""
    page = navegador.new_page()
    try:
        carregar(page, modo, sessao=True)
        var = 'sessaoEpub' if modo == 'epub' else 'sessaoRoteiro'
        assert page.evaluate(var + ' === null')
        assert page.locator('#editorTexto').get_attribute('contenteditable') == 'true'
        page.evaluate('window.fetch = async () => ({ok:true,json:async()=>({ok:true})})')
        alterar(page, modo, 'EDITOR USÁVEL SEM WEB LOCKS')
        page.evaluate('void doAutosave(true)' if modo == 'roteiro' else 'void executarAutosave()')
        page.wait_for_function("document.getElementById('statusAutosave').classList.contains('status-salvo')")
        assert 'EDITOR USÁVEL' in page.locator('#editorTexto').inner_text()
    finally:
        page.close()
