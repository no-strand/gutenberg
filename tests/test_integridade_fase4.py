"""Parte 4: salvamento, cópia local, fila de respostas e recuperação.

Os testes exercitam scripts reais em Chromium, sem precisar do Flask em execução.
Não fazem gravações nos arquivos do projeto do usuário.
"""
import json
import shutil

import pytest

pytest.importorskip('playwright.sync_api')
from playwright.sync_api import sync_playwright
from tests.stress_editores_manual import ROOT, css_source


@pytest.fixture
def navegador():
    with sync_playwright() as pw:
        kwargs = {'headless': True, 'args': ['--no-sandbox', '--disable-background-networking']}
        exe = shutil.which('chromium') or shutil.which('chromium-browser')
        if exe:
            kwargs['executable_path'] = exe
        browser = pw.chromium.launch(**kwargs)
        try:
            yield browser
        finally:
            browser.close()


def carregar(page, modo, *, storage=None, sessao=False):
    page.set_content('''
      <!doctype html><html lang="pt-BR"><head></head><body class="pagina-editor-app"
      style="--cfg-font-size:18px;--cfg-line-height:1.6;--cfg-espaco-paragrafo:12px">
      <section class="barra-ferramentas barra-word-sticky"><button data-comando="bold">B</button><span id="indicadorTipoBloco"></span></section>
      <div class="roteiro-layout"><aside class="roteiro-sidebar"></aside><div class="painel-editor painel-word">
      <div class="pagina-editor"><div id="editorTexto" contenteditable="true" class="editor-texto"></div></div></div></div>
      <input id="campoTituloCapitulo" value="Texto original"><span id="statusAutosave"></span>
      <nav id="sumarioRoteiro"></nav><aside id="sidebarCardSumarioRoteiro"></aside>
      <input type="checkbox" id="toggleVisualizacaoRoteiro"><button id="btnToggleVisualizacaoRoteiro"></button>
      </body></html>''')
    page.evaluate('''(storage) => {
      window.__draftStore = Object.assign({}, storage || {});
      Object.defineProperty(window, 'localStorage', {configurable:true,value:{
        getItem:k=>Object.prototype.hasOwnProperty.call(window.__draftStore,k)?window.__draftStore[k]:null,
        setItem:(k,v)=>{window.__draftStore[k]=String(v)},
        removeItem:k=>{delete window.__draftStore[k]},
        clear:()=>{window.__draftStore={}},
      }});
    }''', storage)
    for name in ('editorial-polish.css', 'atelier-ui.css', 'editor.css',
                 'editor_roteiro.css' if modo == 'roteiro' else 'fontes-editor.css',
                 'editor_recuperacao.css'):
        page.add_style_tag(content=css_source(name))
    if modo == 'roteiro':
        page.evaluate('''() => {
          document.querySelector('.painel-word').className = 'painel-editor painel-roteiro';
          document.querySelector('.pagina-editor').className = 'pagina-editor pagina-roteiro';
          const e=document.querySelector('#editorTexto'); e.classList.add('editor-roteiro');
          e.innerHTML='<div class="roteiro-bloco" data-block-type="action">ORIGINAL ROTEIRO</div>';
        }''')
    else:
        page.evaluate("document.querySelector('#editorTexto').innerHTML='<p>ORIGINAL EPUB</p>'")
    page.evaluate("window.EDITOR_CONFIG = {slug:'projeto-fase4',numero:11,catalogoPersonagens:[],catalogoLocais:[],catalogoAnotacoes:[]}")
    if sessao:
        page.add_script_tag(path=str(ROOT / 'static/js/editor_sessao.js'))
    page.add_script_tag(path=str(ROOT / 'static/js/editor_recuperacao.js'))
    page.add_script_tag(path=str(ROOT / ('static/js/editor_roteiro.js' if modo == 'roteiro' else 'static/js/editor.js')))
    if modo == 'epub':
        page.add_script_tag(path=str(ROOT / 'static/js/epub-pagination.js'))
    page.wait_for_timeout(140)


def alterar(page, modo, texto):
    page.evaluate('''({modo,texto}) => {
      if(modo==='epub') {
        editor.querySelector('p').textContent=texto;
        markEditorDirty(); scheduleAutosave();
      } else {
        editor.querySelector('.roteiro-bloco').textContent=texto;
        serializedBlockCache = new WeakMap();
        invalidateStructureCaches();
        serializationDirty=true; scheduleAutosave();
      }
    }''', {'modo': modo, 'texto': texto})


@pytest.mark.parametrize('modo', ['epub', 'roteiro'])
def test_copia_local_persiste_erro_reabre_recupera_e_salva(navegador, modo):
    page = navegador.new_page(viewport={'width':1360,'height':900})
    erros=[]
    page.on('pageerror', lambda error: erros.append(str(error)))
    try:
        carregar(page, modo)
        page.evaluate('window.fetch = async () => ({ok:false,json:async()=>({ok:false,erro:"offline"})})')
        alterar(page, modo, 'CONTEÚDO NÃO SALVO — ação café')
        page.evaluate('''() => document.dispatchEvent(new Event('visibilitychange'))''')  # flush local if hidden only
        page.evaluate("rascunhoLocal" + ("Roteiro" if modo=='roteiro' else "Epub") + ".copiarAgora()")
        page.evaluate('doAutosave(true)' if modo == 'roteiro' else 'executarAutosave()')
        page.wait_for_timeout(110)
        snapshot=page.evaluate('''() => Object.keys(window.__draftStore).filter(k=>k.includes('rascunho-local')).map(k=>JSON.parse(window.__draftStore[k]))''')
        assert len(snapshot) == 1
        assert 'CONTEÚDO NÃO SALVO' in snapshot[0]['payload']
        storage=page.evaluate('window.__draftStore')
        page.close()
        page=navegador.new_page(viewport={'width':1360,'height':900})
        page.on('pageerror', lambda error: erros.append(str(error)))
        carregar(page, modo, storage=storage)
        assert page.locator('.editor-recuperacao-aviso').count() == 1
        assert 'CONTEÚDO NÃO SALVO' not in page.locator('#editorTexto').inner_text()
        page.evaluate('window.fetch=async () => ({ok:true,json:async()=>({ok:true})})')
        page.locator('.editor-recuperacao-restaurar').click()
        assert 'CONTEÚDO NÃO SALVO' in page.locator('#editorTexto').inner_text()
        page.evaluate('doAutosave(true)' if modo=='roteiro' else 'executarAutosave()')
        page.wait_for_timeout(180)
        assert page.evaluate("Object.keys(window.__draftStore).filter(k=>k.includes('rascunho-local')).length") == 0
        assert page.locator('.editor-recuperacao-aviso').count() == 0
        assert page.locator('#statusAutosave').get_attribute('class') and 'status-salvo' in page.locator('#statusAutosave').get_attribute('class')
        assert not erros, erros
    finally:
        page.close()


@pytest.mark.parametrize('modo', ['epub', 'roteiro'])
def test_edicao_enquanto_resposta_antiga_aguarda_nao_exibe_salvo(navegador, modo):
    page = navegador.new_page(viewport={'width':1360,'height':900})
    try:
        carregar(page, modo)
        page.evaluate('''() => {window.requests=[];window.fetch=(url,opts)=>new Promise(resolve=>{
          window.requests.push({payload:opts.body, resolve});
        });}''')
        alterar(page, modo, 'VERSÃO A')
        page.evaluate('() => { if (typeof doAutosave === "function") void doAutosave(true); else void executarAutosave(); }')
        page.wait_for_function('window.requests.length === 1')
        alterar(page, modo, 'VERSÃO B MAIS NOVA')
        page.evaluate('''() => window.requests[0].resolve({ok:true,json:async()=>({ok:true})})''')
        page.wait_for_function('window.requests.length === 2')
        assert 'VERSÃO B' in page.evaluate('window.requests[1].payload')
        assert 'status-salvo' not in page.locator('#statusAutosave').get_attribute('class')
        page.evaluate('''() => window.requests[1].resolve({ok:true,json:async()=>({ok:true})})''')
        page.wait_for_function("document.getElementById('statusAutosave').classList.contains('status-salvo')")
        assert 'VERSÃO B' in page.locator('#editorTexto').inner_text()
    finally:
        page.close()


@pytest.mark.parametrize('modo', ['epub', 'roteiro'])
def test_descartar_copia_nao_altera_servidor(navegador, modo):
    page = navegador.new_page(viewport={'width':1360,'height':900})
    try:
        carregar(page, modo)
        alterar(page, modo, 'NÃO DESCARTADO NO SERVIDOR')
        page.evaluate("rascunhoLocal" + ("Roteiro" if modo=='roteiro' else "Epub") + ".copiarAgora()")
        storage=page.evaluate('window.__draftStore')
        page.close()
        page=navegador.new_page(viewport={'width':1360,'height':900})
        carregar(page, modo, storage=storage)
        page.locator('.editor-recuperacao-descartar').click()
        assert 'ORIGINAL' in page.locator('#editorTexto').inner_text()
        assert page.evaluate("Object.keys(window.__draftStore).filter(k=>k.includes('rascunho-local')).length") == 0
    finally:
        page.close()


def test_copia_local_nao_apaga_versao_mais_nova_por_confirmacao_atrasada(navegador):
    page=navegador.new_page()
    try:
        carregar(page,'epub')
        result=page.evaluate('''() => {
          const r=rascunhoLocalEpub;
          const antigo=JSON.stringify({titulo:'Texto original',html:'<p>ANTIGO</p>'});
          const novo=JSON.stringify({titulo:'Texto original',html:'<p>NOVO</p>'});
          editor.innerHTML='<p>NOVO</p>';markEditorDirty();r.copiarAgora();
          r.confirmarSalvamento(antigo);
          return {draft:r.lerCopia()?.payload, novo};
        }''')
        assert result['draft']==result['novo'], result
    finally:
        page.close()

@pytest.mark.parametrize('modo', ['epub', 'roteiro'])
def test_pagehide_guarda_copia_sem_confiar_no_fetch(navegador, modo):
    page = navegador.new_page()
    try:
        carregar(page, modo)
        alterar(page, modo, 'FECHAMENTO REPENTINO')
        page.evaluate("window.dispatchEvent(new Event('pagehide'))")
        assert 'FECHAMENTO REPENTINO' in page.evaluate('''() =>
          Object.values(window.__draftStore).join('')''')
    finally:
        page.close()


@pytest.mark.parametrize('modo', ['epub', 'roteiro'])
def test_reconexao_refaz_salvamento_e_elimina_copia(navegador, modo):
    page = navegador.new_page()
    try:
        carregar(page, modo)
        page.evaluate('() => { window.fetch=async()=>{throw Error("offline")}; }')
        alterar(page, modo, 'TEXTO OFFLINE E RECONECTADO')
        page.evaluate("rascunhoLocal" + ("Roteiro" if modo=='roteiro' else "Epub") + ".copiarAgora()")
        page.evaluate('doAutosave(true)' if modo=='roteiro' else 'executarAutosave()')
        assert page.evaluate("Object.keys(window.__draftStore).length") == 1
        page.evaluate('''() => {window.__envios=[];window.fetch=async(url,opts)=>{
            window.__envios.push(opts.body);
            return {ok:true,json:async()=>({ok:true})};
          };window.dispatchEvent(new Event('online'));}''')
        page.wait_for_function('window.__envios.length > 0')
        page.wait_for_function('Object.keys(window.__draftStore).length === 0')
        assert 'TEXTO OFFLINE E RECONECTADO' in page.evaluate('window.__envios[0]')
    finally:
        page.close()


def test_aviso_recuperacao_nao_substitui_conteudo_automaticamente(navegador):
    page=navegador.new_page()
    try:
        carregar(page,'epub')
        key='gutenberg:rascunho-local:v1:epub:projeto-fase4:11'
        server=page.locator('#editorTexto').inner_text()
        page.evaluate('''(k) => window.__draftStore[k] = JSON.stringify({
          versao:1,atualizadoEm:Date.now(),
          payload:JSON.stringify({titulo:'Texto anterior',html:'<p>CÓPIA DIVERGENTE</p>'})
        })''',key)
        storage=page.evaluate('window.__draftStore')
        page.close()
        page=navegador.new_page()
        carregar(page,'epub',storage=storage)
        assert page.locator('.editor-recuperacao-aviso').count()==1
        assert page.locator('#editorTexto').inner_text()==server
        page.evaluate("window.dispatchEvent(new Event('pagehide'))")
        assert 'CÓPIA DIVERGENTE' in page.evaluate('Object.values(window.__draftStore).join("")')
    finally:
        page.close()


def test_recuperacao_de_titulo_e_conteudo_epub_mantem_historico(navegador):
    page=navegador.new_page()
    try:
        carregar(page,'epub')
        page.evaluate('''() => {
          editor.querySelector('p').textContent='TEXTO DO RASCUNHO';
          campoTituloCapitulo.value='Título recuperável';
          markEditorDirty();rascunhoLocalEpub.copiarAgora();
        }''')
        storage=page.evaluate('window.__draftStore')
        page.close()
        page=navegador.new_page()
        carregar(page,'epub',storage=storage)
        page.locator('.editor-recuperacao-restaurar').click()
        assert page.locator('#campoTituloCapitulo').input_value() == 'Título recuperável'
        assert page.locator('#editorTexto').inner_text() == 'TEXTO DO RASCUNHO'
        assert page.evaluate('historyStack.length') >= 2
    finally:
        page.close()


def test_falha_de_quota_na_copia_local_nao_impede_editar(navegador):
    page=navegador.new_page()
    try:
        carregar(page,'epub')
        result=page.evaluate('''() => {
          const original=window.localStorage;
          Object.defineProperty(window, 'localStorage', {configurable:true,value:{
            getItem:k=>original.getItem(k),
            setItem:()=>{throw new DOMException('Quota exceeded','QuotaExceededError')},
            removeItem:k=>original.removeItem(k),
          }});
          editor.querySelector('p').textContent='EDIÇÃO SEM ESPAÇO';
          markEditorDirty();rascunhoLocalEpub.copiarAgora();
          return {temAlerta:!!document.querySelector('.editor-recuperacao-erro'),
            texto:editor.textContent};
        }''')
        assert result['temAlerta'] and 'EDIÇÃO SEM ESPAÇO' in result['texto']
    finally:
        page.close()


def test_desfazer_ate_estado_confirmado_descarta_rascunho_antigo(navegador):
    page=navegador.new_page()
    try:
        carregar(page,'epub')
        page.evaluate('''() => {
          editor.querySelector('p').textContent='ALTERADO';
          markEditorDirty();rascunhoLocalEpub.copiarAgora();
        }''')
        assert page.evaluate('Object.keys(window.__draftStore).length') == 1
        page.evaluate('''() => {
          editor.querySelector('p').textContent='ORIGINAL EPUB';
          markEditorDirty();rascunhoLocalEpub.copiarAgora();
        }''')
        assert page.evaluate('Object.keys(window.__draftStore).length') == 0
    finally:
        page.close()
