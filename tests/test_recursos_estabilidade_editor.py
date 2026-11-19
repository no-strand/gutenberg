"""Regressões do editor de Informações e otimizações do fluxo.

Usa Chromium real e DOM compatível com a página de Rascunho, sem exigir Flask.
"""
import shutil
from pathlib import Path

import pytest

pwlib = pytest.importorskip('playwright.sync_api')
from tests.test_editor_v7_regressions import resource_page, start_browser, bounds, assert_blocks_on_paper

ROOT = Path(__file__).resolve().parents[1]


def mock_storage(page):
    # Sobre about:blank, armazenamento nativo pode não estar disponível.
    page.evaluate('''''''''() => {
      window.__infoStore={};
      Object.defineProperty(window,'localStorage',{configurable:true,value:{
        getItem:key=>Object.prototype.hasOwnProperty.call(window.__infoStore,key)?window.__infoStore[key]:null,
        setItem:(key,value)=>{window.__infoStore[key]=String(value);},
        removeItem:key=>{delete window.__infoStore[key];}
      }});
    }''''''''' )



def test_informacoes_2700_paragrafos_sem_limite_de_folhas():
    with pwlib.sync_playwright() as pw:
        browser = start_browser(pw)
        try:
            page = browser.new_page(viewport={'width': 1400, 'height': 950})
            errors = []
            page.on('pageerror', lambda err: errors.append(str(err)))
            html = ''.join(f'<p>Parágrafo número {i} com conteúdo de teste, acentuação, e elementos de escrita.</p>' for i in range(2700))
            resource_page(page, html)
            page.wait_for_timeout(500)
            result = page.evaluate('''() => {
              const stage=document.getElementById('infoPaperStage');
              const sheets=[...stage.querySelectorAll('.info-paper-sheet')];
              const end=document.querySelector('#editorInfoPagina > p:last-child').getBoundingClientRect();
              const last=sheets.at(-1).getBoundingClientRect();
              return {sheets:sheets.length,maxHeight:Math.max(...sheets.map(x=>x.getBoundingClientRect().height)),
                lastInside:end.bottom<=last.bottom+5 && end.top>=last.top-5,
                contentElements:document.querySelectorAll('#editorInfoPagina > p').length};
            }''')
            assert result['sheets'] > 250, result
            assert result['maxHeight'] < 2000, result
            assert result['lastInside'] and result['contentElements'] == 2700, result
            assert not errors, errors
        finally:
            browser.close()


def test_salvamentos_info_ficam_em_fila_e_indicador_nao_antecipa_sucesso():
    with pwlib.sync_playwright() as pw:
        browser = start_browser(pw)
        try:
            page = browser.new_page()
            resource_page(page, '<p>Inicial</p>')
            page.evaluate('''() => {
              window.__sent=[];window.__pending=[];
              window.fetch=(url, options)=>new Promise(resolve=>{
                window.__sent.push({url, text:JSON.parse(options.body).informacoes_abas[0].paginas[0].html});
                window.__pending.push(()=>resolve({ok:true,json:async()=>({ok:true})}));
              });
              window.__edit=(value)=>{
                const editor=document.getElementById('editorInfoPagina');
                editor.innerHTML='<p>'+value+'</p>';
                editor.dispatchEvent(new Event('input',{bubbles:true}));
              };
            }''')
            page.evaluate("window.__edit('VERSAO_A')")
            page.wait_for_function('window.__sent.length===1', timeout=5000)
            page.evaluate("window.__edit('VERSAO_B')")
            page.wait_for_timeout(850)
            assert page.evaluate('window.__sent.length') == 1, 'A versão B não pode ultrapassar A.'
            page.evaluate('window.__pending.shift()()')
            page.wait_for_function('window.__sent.length===2', timeout=5000)
            assert 'VERSAO_B' in page.evaluate('window.__sent[1].text')
            # A segunda requisição existe, mas não foi confirmada.
            assert page.evaluate('window.__pending.length') == 1
            page.evaluate('window.__pending.shift()()')
            page.wait_for_timeout(50)
            assert page.evaluate('window.__sent.length') == 2
        finally:
            browser.close()


def test_copia_local_info_e_restauracao_explicita():
    with pwlib.sync_playwright() as pw:
        browser = start_browser(pw)
        try:
            page = browser.new_page()
            mock_storage(page)
            key = 'gutenberg:recursos-info:v1:browser:tab:page'
            page.evaluate('''([key,value]) => localStorage.setItem(key,JSON.stringify(value))''', [key, {
                'version': 1, 'title': 'Título recuperado', 'html': '<p>Texto não salvo: versão local.</p>', 'time': 123
            }])
            resource_page(page,'<p>Conteúdo salvo no servidor.</p>')
            assert page.locator('.info-recuperacao-aviso').count() == 1
            assert 'Conteúdo salvo' in page.locator('#editorInfoPagina').inner_text()
            page.locator('.info-recuperacao-acoes button').first.click()
            assert 'Texto não salvo' in page.locator('#editorInfoPagina').inner_text()
            assert page.locator('#tituloPaginaInfo').input_value() == 'Título recuperado'
            assert page.locator('.info-recuperacao-aviso').count() == 0
            page.wait_for_timeout(900)
            assert page.evaluate('(key)=>localStorage.getItem(key)',key) is None
        finally:
            browser.close()


def test_copia_local_permanece_na_pagina_de_origem_ao_trocar_rapidamente():
    with pwlib.sync_playwright() as pw:
        browser = start_browser(pw)
        try:
            page = browser.new_page()
            mock_storage(page)
            page.set_content('''<body><main class="pagina-recursos-projeto-shell">
            <div class="recursos-workspace"><section data-recursos-panel="informacoes" class="recursos-painel ativo">
              <div class="resource-page-shell"><div id="tabsPaginasInfo"></div><div class="info-layout"><aside><div id="listaPaginasInfo"></div></aside>
              <article class="info-editor-card"><input id="tituloPaginaInfo"><div class="info-paper-workspace">
              <div class="info-paper-stage" id="infoPaperStage"><div class="info-paper-layers" id="infoPaperLayers"></div><div id="editorInfoPagina" class="info-rich-editor" contenteditable="true"></div>
              </div></div></article></div></div></section></div></main><div id="recursosStatus"></div></body>''')
            page.evaluate('''() => {
              window.PROJETO_SLUG='browser';
              window.PROJETO_RECURSOS_INITIAL={informacoes_abas:[{id:'tab',titulo:'Aba',paginas:[
                {id:'page',titulo:'Primeira',html:'<p>Primeira</p>'},
                {id:'second',titulo:'Segunda',html:'<p>Segunda</p>'}
              ]}]};
              window.fetch=async()=>({ok:true,json:async()=>({ok:true})});
            }''')
            page.add_script_tag(path=str(ROOT/'static/js/recursos_projeto.js'))
            page.evaluate('''() => {
              const editor=document.getElementById('editorInfoPagina');
              editor.innerHTML='<p>Texto da primeira sem salvar</p>';
              editor.dispatchEvent(new Event('input',{bubbles:true}));
            }''')
            page.locator('#listaPaginasInfo button').last.click()
            page.wait_for_timeout(350)
            keys = page.evaluate('''() => Object.keys(window.__infoStore).filter(key=>key.includes('recursos-info'))''')
            assert any(key.endswith(':page') for key in keys), keys
            assert 'Segunda' in page.locator('#editorInfoPagina').inner_text()
        finally:
            browser.close()


def test_estado_anterior_de_toggles_e_selecao_permanece():
    with pwlib.sync_playwright() as pw:
        browser = start_browser(pw)
        try:
            page=browser.new_page()
            resource_page(page,'<p>Normal <b>forte</b> e <span class="tamanho-fonte-60pt">grande</span>.</p>')
            page.evaluate('''() => {
              const root=document.getElementById('editorInfoPagina');
              const txt=root.querySelector('b').firstChild;
              const range=document.createRange();range.setStart(txt,3);range.collapse(true);
              getSelection().removeAllRanges();getSelection().addRange(range);root.focus();
            }''')
            assert page.locator('[data-info-comando="bold"]').get_attribute('aria-pressed') == 'true'
            assert page.locator('#seletorTamanhoFonteInfo').input_value() != '60'
        finally:
            browser.close()


def test_fluxo_mantem_conexoes_durante_atualizacao_de_baloes():
    with pwlib.sync_playwright() as pw:
        browser = start_browser(pw)
        try:
            page = browser.new_page()
            errors=[]
            page.on('pageerror',lambda error: errors.append(str(error)))
            page.set_content('''<main class="pagina-recursos-projeto-shell"><span id="recursosStatus"></span>
              <div id="fluxoCanvasWrap"><div id="fluxoCanvas"><svg id="fluxoSvg"></svg>
              <div id="fluxoNodes"></div></div></div>
              <div id="tabsPaginasFluxo"></div>
              </main>''')
            page.evaluate('''() => {
              window.PROJETO_SLUG='fluxo-test';
              window.PROJETO_RECURSOS_INITIAL={fluxos:[{id:'fluxo_principal',titulo:'Fluxo',
                nodes:[{id:'a',titulo:'A',texto:'Primeiro',x:20,y:25,width:240,height:150},
                       {id:'b',titulo:'B',texto:'Segundo',x:320,y:25,width:240,height:150}],
                edges:[{from:'a',to:'b',fromSide:'right',toSide:'left'}]}]};
              window.fetch=async()=>({ok:true,json:async()=>({ok:true})});
            }''')
            page.add_script_tag(path=str(ROOT/'static/js/recursos_projeto.js'))
            page.wait_for_timeout(100)
            assert page.locator('#fluxoNodes .fluxo-node').count()==2
            assert page.locator('#fluxoSvg path.fluxo-edge').count()==1
            before=page.locator('#fluxoSvg path').first.get_attribute('d')
            page.evaluate('''() => {
              const node=document.querySelector('.fluxo-node[data-node-id="a"]');
              node.style.left='95px';
              node.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,button:0,clientX:20,clientY:20,pointerId:1}));
              node.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,button:0,clientX:70,clientY:60,pointerId:1}));
            }''')
            page.wait_for_timeout(80)
            assert page.locator('#fluxoSvg path.fluxo-edge').count()==1
            assert page.locator('#fluxoSvg path').first.get_attribute('d') != before
            assert not errors, errors
        finally:
            browser.close()


def test_imagem_assincrona_informacoes_respeita_cursor_salvo_e_pagina():
    with pwlib.sync_playwright() as pw:
        browser = start_browser(pw)
        try:
            page = browser.new_page()
            errors=[]
            page.on('pageerror',lambda error: errors.append(str(error)))
            page.set_content('''<main class="pagina-recursos-projeto-shell"><span id="recursosStatus"></span>
              <div class="info-layout"><div id="tabsPaginasInfo"></div><div id="listaPaginasInfo"></div>
                <div><input id="tituloPaginaInfo"><button id="btnInserirImagemInfo">Imagem</button>
                <input id="inputImagemInfo" type="file" accept="image/*"/>
                <div id="infoPaperStage"><div id="infoPaperLayers"></div>
                  <div id="editorInfoPagina" contenteditable="true"></div>
                </div></div></div></main>''')
            page.evaluate('''() => {
              window.PROJETO_SLUG='browser';
              window.PROJETO_RECURSOS_INITIAL={informacoes_abas:[{id:'tab',titulo:'Info',paginas:[
                 {id:'page',titulo:'Exemplo',html:'<p>PRIMEIRO</p><p>SEGUNDO</p>'}]}]};
              window.fetch=async()=>({ok:true,json:async()=>({ok:true})});
              window.FileReader = class {
                readAsDataURL(){window.__resolveImage=()=>{this.result='data:image/png;base64,iVBORw0KGgo=';this.onload();};}
              };
            }''')
            page.add_script_tag(path=str(ROOT/'static/js/recursos_projeto.js'))
            page.evaluate('''() => {
              const editor=document.getElementById('editorInfoPagina');
              const text=editor.querySelector('p').firstChild;
              const range=document.createRange();range.setStart(text,4);range.collapse(true);
              getSelection().removeAllRanges();getSelection().addRange(range);editor.focus();
            }''')
            page.locator('#btnInserirImagemInfo').click()
            page.locator('#inputImagemInfo').set_input_files({'name':'foto.png','mimeType':'image/png','buffer':b'png'})
            page.wait_for_function('typeof window.__resolveImage === "function"')
            page.evaluate('''() => {
              const editor=document.getElementById('editorInfoPagina');
              const last=editor.querySelectorAll('p')[1].firstChild;
              const r=document.createRange();r.setStart(last,3);r.collapse(true);
              getSelection().removeAllRanges();getSelection().addRange(r);editor.focus();
              window.__resolveImage();
            }''')
            page.wait_for_timeout(90)
            assert page.locator('#editorInfoPagina img').count()==1
            assert page.evaluate('''() => {
              const root=document.getElementById('editorInfoPagina');
              return root.querySelector('p').contains(root.querySelector('img'));
            }''')
            assert not errors, errors
        finally:
            browser.close()


def test_postagens_de_secoes_diferentes_nao_disputam_sqlite():
    with pwlib.sync_playwright() as pw:
        browser = start_browser(pw)
        try:
            page = browser.new_page()
            page.set_content('''<main class="pagina-recursos-projeto-shell"><span id="recursosStatus"></span>
              <div id="tabsPaginasInfo"></div><div id="listaPaginasInfo"></div>
              <input id="tituloPaginaInfo"><div id="infoPaperStage"><div id="infoPaperLayers"></div>
              <div id="editorInfoPagina" contenteditable="true"></div></div>
              <button id="btnNovaPaginaFluxo">Novo fluxo</button><div id="tabsPaginasFluxo"></div>
              <div id="fluxoNodes"></div><svg id="fluxoSvg"></svg></main>''')
            page.evaluate('''() => {
              window.PROJETO_SLUG='browser';
              window.PROJETO_RECURSOS_INITIAL={informacoes_abas:[{id:'tab',titulo:'Info',paginas:[
                {id:'page',titulo:'Exemplo',html:'<p>Inicial</p>'}]}]};
              window.__sent=[];window.__pending=[];
              window.fetch=(url, options)=>new Promise(resolve=>{
                window.__sent.push(url);
                window.__pending.push(()=>resolve({ok:true,json:async()=>({ok:true})}));
              });
            }''')
            page.add_script_tag(path=str(ROOT/'static/js/recursos_projeto.js'))
            page.locator('#btnNovaPaginaFluxo').click()
            page.evaluate('''() => {
              const editor=document.getElementById('editorInfoPagina');
              editor.innerHTML='<p>ALTERADO</p>';
              editor.dispatchEvent(new Event('input',{bubbles:true}));
            }''')
            page.wait_for_function('window.__sent.length===1', timeout=4500)
            page.wait_for_timeout(850)
            assert page.evaluate('window.__sent.length') == 1
            page.evaluate('window.__pending.shift()()')
            page.wait_for_function('window.__sent.length===2', timeout=4500)
            sent=page.evaluate('window.__sent')
            assert any('/fluxo' in u for u in sent) and any('/informacoes' in u for u in sent)
            page.evaluate('window.__pending.shift()()')
            page.wait_for_timeout(80)
            assert page.evaluate('window.__pending.length') == 0
        finally:
            browser.close()


def test_falha_de_rede_preserva_copia_local_de_informacoes():
    with pwlib.sync_playwright() as pw:
        browser = start_browser(pw)
        try:
            page = browser.new_page()
            mock_storage(page)
            resource_page(page,'<p>Conteúdo persistido.</p>')
            page.evaluate('''() => {
              window.fetch=async()=>{throw Error('Sem conexão');};
              const editor=document.getElementById('editorInfoPagina');
              editor.innerHTML='<p>Alteração importante sem conexão</p>';
              editor.dispatchEvent(new Event('input',{bubbles:true}));
            }''')
            page.wait_for_timeout(920)
            saved=page.evaluate('window.__infoStore["gutenberg:recursos-info:v1:browser:tab:page"]')
            assert saved and 'Alteração importante' in saved
            assert 'Alteração importante' in page.locator('#editorInfoPagina').inner_text()
        finally:
            browser.close()


def test_colagem_extensa_mantem_todos_os_paragrafos_serializados():
    with pwlib.sync_playwright() as pw:
        browser = start_browser(pw)
        try:
            page = browser.new_page()
            resource_page(page,'<p>Inicio.</p>')
            page.evaluate('''() => {
              const editor=document.getElementById('editorInfoPagina');
              const r=document.createRange();r.selectNodeContents(editor);r.collapse(false);
              getSelection().removeAllRanges();getSelection().addRange(r);editor.focus();
              const html=Array.from({length:300},(_,i)=>`<p>Colagem ${i} — ação e café</p>`).join('');
              document.execCommand('insertHTML',false,html);
              editor.dispatchEvent(new Event('input',{bubbles:true}));
            }''')
            page.wait_for_timeout(480)
            result=page.evaluate('''() => ({
              total:document.querySelectorAll('#editorInfoPagina > p').length,
              first:document.getElementById('editorInfoPagina').innerHTML.includes('Colagem 0'),
              last:document.getElementById('editorInfoPagina').innerHTML.includes('Colagem 299'),
              pages:document.querySelectorAll('.info-paper-sheet').length,
            })''')
            assert result['total'] >= 300, result
            assert result['first'] and result['last'] and result['pages'] > 5, result
        finally:
            browser.close()


def test_copia_recuperada_nao_some_ao_trocar_pagina_antes_do_salvamento():
    with pwlib.sync_playwright() as pw:
        browser=start_browser(pw)
        try:
            page=browser.new_page()
            mock_storage(page)
            key='gutenberg:recursos-info:v1:browser:tab:page'
            page.evaluate('''(key) => localStorage.setItem(key,JSON.stringify({
              version:1,title:'Primeira',html:'<p>CÓPIA RECUPERADA E PENDENTE</p>',time:123
            }))''',key)
            page.set_content('''<main class="pagina-recursos-projeto-shell"><div class="recursos-workspace">
              <section class="recursos-painel ativo" data-recursos-panel="informacoes">
              <div id="tabsPaginasInfo"></div><div id="listaPaginasInfo"></div><input id="tituloPaginaInfo">
              <div id="infoPaperStage"><div id="infoPaperLayers"></div>
                <div id="editorInfoPagina" contenteditable="true"></div></div>
              </section></div></main>''')
            page.evaluate('''() => {
              window.PROJETO_SLUG='browser';
              window.PROJETO_RECURSOS_INITIAL={informacoes_abas:[{id:'tab',titulo:'Info',paginas:[
                {id:'page',titulo:'Primeira',html:'<p>Texto do servidor</p>'},
                {id:'second',titulo:'Segunda',html:'<p>Outra página</p>'}
              ]}]};
              window.fetch=async()=>new Promise(()=>{}); // nenhum ack até o fim do teste
            }''')
            page.add_script_tag(path=str(ROOT/'static/js/recursos_projeto.js'))
            assert page.locator('.info-recuperacao-aviso').count()==1
            page.locator('.info-recuperacao-acoes button').first.click()
            page.locator('#listaPaginasInfo button').last.click()
            page.locator('#listaPaginasInfo button').first.click()
            assert 'CÓPIA RECUPERADA' in page.locator('#editorInfoPagina').inner_text()
            assert page.evaluate('(key)=>localStorage.getItem(key)',key) is not None
            assert page.locator('.info-recuperacao-aviso').count()==0
        finally:
            browser.close()
