"""Revisão editorial: persistência separada, diff, sugestões e integração visual."""
from pathlib import Path
import json
import shutil

import pytest
from jinja2 import Environment, FileSystemLoader

from modules import revisao_editorial as review

ROOT = Path(__file__).resolve().parents[1]


def test_comentarios_sugestoes_estado_isolamento_e_versoes(tmp_path):
    pasta = tmp_path / 'projeto'; pasta.mkdir()
    comment = review.criar_item(pasta, 'livro', 1, {'tipo':'comentario','trecho':'texto', 'nota':'Nota pessoal',
        'inicio': 3, 'prefixo':'um ', 'sufixo':' bom'})
    suggestion = review.criar_item(pasta,'livro',1,{'tipo':'sugestao','trecho':'velho',
        'substituicao':'novo','inicio':10,'nota':'clareza'})
    assert len(review.ler(pasta,'livro',1)['itens']) == 2
    assert not review.ler(pasta,'roteiro',1)['itens']
    assert not review.ler(pasta,'livro',2)['itens']
    assert review.alterar_item(pasta,'livro',1,comment['id'],'resolvido')['estado'] == 'resolvido'
    assert review.alterar_item(pasta,'livro',1,suggestion['id'],'aceito')['estado'] == 'aceito'
    with pytest.raises(ValueError):
        review.alterar_item(pasta,'livro',1,comment['id'],'aceito')
    with pytest.raises(ValueError):
        review.criar_item(pasta,'livro',1,{'tipo':'sugestao','trecho':'x', 'substituicao':'', 'inicio':0})
    v = review.criar_versao(pasta,'livro',1,'Capítulo 1','<p>Uma frase antiga</p>','Rascunho')
    assert v['rotulo'] == 'Rascunho' and 'html' not in v
    assert 'html' not in review.ler(pasta,'livro',1)['versoes'][0]
    assert review.obter_versao(pasta,'livro',1,v['id'])['html'] == '<p>Uma frase antiga</p>'
    assert review.criar_versao(pasta,'livro',1,'Capítulo','<p>Uma frase antiga</p>','Duplicata')['id'] == v['id']
    diff = review.comparar('<p>Uma frase antiga</p>', '<p>Uma frase nova</p>')
    assert any(p['tipo']=='removido' and 'antiga' in p['texto'] for p in diff)
    assert any(p['tipo']=='adicionado' and 'nova' in p['texto'] for p in diff)
    review.apagar_item(pasta,'livro',1,suggestion['id'])
    review.apagar_versao(pasta,'livro',1,v['id'])
    assert len(review.ler(pasta,'livro',1)['itens']) == 1
    assert not review.ler(pasta,'livro',1)['versoes']
    with pytest.raises(ValueError): review.arquivo(pasta,'../../invalid',1)


def test_templates_editorial_duas_linguas_integrado():
    env = Environment(loader=FileSystemLoader(str(ROOT/'templates')))
    for lang in ('pt_BR','en_US'):
        translations = json.loads((ROOT/'locales'/f'{lang}.json').read_text('utf8'))
        html = env.get_template('_revisao_editorial_panel.html').render(t=lambda key: translations.get(key,key))
        assert translations['editorial.title'] in html
        assert 'revListaNotas' in html and 'revListaVersoes' in html
        assert 'revComparacao' in html and 'revTrechoSelecionado' in html
    for name in ('editor.html','editor_roteiro.html'):
        s=(ROOT/'templates'/name).read_text('utf8')
        assert "{% include '_revisao_editorial_panel.html' %}" in s
        assert 'btnAbrirRevisaoEditorial' in s
        assert 'js/revisao_editorial.js' in s
        assert 'css/revisao_editorial.css' in s


def test_interacoes_revisao_editorial_no_chromium():
    sync_api = pytest.importorskip('playwright.sync_api')
    env = Environment(loader=FileSystemLoader(str(ROOT/'templates')))
    translations = json.loads((ROOT/'locales'/'pt_BR.json').read_text('utf8'))
    modal = env.get_template('_revisao_editorial_panel.html').render(t=lambda k: translations.get(k,k))
    chromium = shutil.which('chromium') or shutil.which('chromium-browser')
    with sync_api.sync_playwright() as playwright:
        opts = {'headless':True,'args':['--no-sandbox']}
        if chromium: opts['executable_path'] = chromium
        browser = playwright.chromium.launch(**opts)
        try:
            page = browser.new_page()
            errors=[]; page.on('pageerror', lambda e: errors.append(str(e)))
            page.set_content('''<html lang="pt-BR"><body><div class="painel-word">
              <button id="btnAbrirRevisaoEditorial">Revisão</button><input id="campoTituloCapitulo" value="Capítulo">
              <div id="editorTexto" contenteditable="true"><p>Era uma vez um texto velho.</p><p>Outro bloco.</p></div>
              </div></body></html>''')
            page.evaluate('''(html) => {
                document.body.insertAdjacentHTML('beforeend', html);
                window.EDITOR_CONFIG = {slug:'projeto-teste', numero:1};
                const saved={items:[],versions:[]};
                window.fakeEditorialSaved=saved;
                window.fetch=async (url, options={}) => {
                  const id=url.split('/versoes/')[1]?.split('?')[0];
                  let data = {};
                  if(options.body){const body=JSON.parse(options.body);
                    if(body.acao==='criar') saved.items.push({...body,id:'item'+saved.items.length,estado:'pendente'});
                    if(body.acao==='estado') saved.items.find(x=>x.id===body.id).estado=body.estado;
                    if(body.acao==='apagar') saved.items=saved.items.filter(x=>x.id!==body.id);
                    if(body.acao==='versao') saved.versions.push({id:'versao'+saved.versions.length,rotulo:body.rotulo||'Versão',titulo:'Capítulo',html:'<p>Era uma vez um texto velho.</p>'});
                  }
                  if(id){
                    const versao=saved.versions.find(x=>x.id===id);
                    data=url.includes('comparar=1')?{comparacao:[{tipo:'igual',texto:'Era uma vez'}]}:{versao};
                  }else { data={itens:saved.items,versoes:saved.versions.map(({html,...rest})=>rest)}; }
                  return {ok:true,json:async()=>({ok:true,...data})};
                };
            }''', modal)
            page.evaluate('(translations) => { window.t = (key) => translations[key] || key; }', translations)
            page.add_style_tag(path=str(ROOT/'static/css/revisao_editorial.css'))
            page.add_script_tag(path=str(ROOT/'static/js/revisao_editorial.js'))
            page.evaluate('''() => {
                const n=document.querySelector('#editorTexto p').firstChild;
                const r=document.createRange(); r.setStart(n,15); r.setEnd(n,25);
                getSelection().removeAllRanges(); getSelection().addRange(r);
                document.dispatchEvent(new Event('selectionchange'));
            }''')
            page.locator('#btnAbrirRevisaoEditorial').click()
            assert page.locator('#painelRevisaoEditorial').is_visible()
            page.locator('#revNota').fill('Melhorar essa expressão')
            page.locator('#revSubstituicao').fill('um texto novo')
            # Ajustar trecho por seleção real para evitar offsets frágeis em alterações de HTML.
            page.evaluate('''() => {
                const text=document.querySelector('#editorTexto p').firstChild;
                const r=document.createRange(); r.setStart(text,text.textContent.indexOf('um texto velho'));
                r.setEnd(text,text.textContent.indexOf('um texto velho')+'um texto velho'.length);
                getSelection().removeAllRanges();getSelection().addRange(r);
                document.dispatchEvent(new Event('selectionchange'));
            }''')
            page.locator('#btnRevSugerir').click()
            page.wait_for_function("window.fakeEditorialSaved.items.length === 1")
            assert page.locator('#editorTexto').inner_text().count('um texto velho') == 1
            page.locator('#revListaNotas button').filter(has_text='Aceitar').click()
            page.wait_for_function("document.getElementById('editorTexto').textContent.includes('um texto novo')")
            assert 'velho' not in page.locator('#editorTexto').inner_text()
            assert page.evaluate('window.fakeEditorialSaved.items[0].estado') == 'aceito'
            page.locator('#revAbaVersoes').click()
            page.locator('#revNomeVersao').fill('Revisão de teste')
            page.locator('#btnRevCriarVersao').click()
            page.wait_for_function('window.fakeEditorialSaved.versions.length === 1')
            page.locator('#revListaVersoes button').filter(has_text='Comparar').click()
            assert page.locator('#revComparacao').is_visible()
            assert not errors, errors
        finally:
            browser.close()


def test_revisao_backup_compatibilidade_antiga_e_isolamento(tmp_path):
    pasta=tmp_path/'livro'; pasta.mkdir()
    # Backups de versões anteriores não têm a chave opcional.
    review.importar_estado(pasta,'livro',3,None)
    assert review.ler(pasta,'livro',3)['itens'] == []
    i=review.criar_item(pasta,'livro',3,{'tipo':'comentario','trecho':'uma frase','nota':'ok','inicio':0})
    v=review.criar_versao(pasta,'livro',3,'Cap 3','<p>Acontecimento</p>','V1')
    from_backup=review.ler(pasta,'livro',3,incluir_html=True)
    review.importar_estado(pasta,'livro',7,from_backup)
    replica=review.ler(pasta,'livro',7,incluir_html=True)
    assert replica['itens'][0]['trecho'] == 'uma frase'
    assert replica['itens'][0]['id'] != i['id']
    assert replica['versoes'][0]['html'] == '<p>Acontecimento</p>'
    assert replica['versoes'][0]['id'] != v['id']
    assert not review.ler(pasta,'livro',3)['versoes'][0].get('html')


def test_script_editor_com_revisao_preserva_serializacao():
    sync_api=pytest.importorskip('playwright.sync_api')
    env=Environment(loader=FileSystemLoader(str(ROOT/'templates')))
    translations=json.loads((ROOT/'locales'/'pt_BR.json').read_text('utf8'))
    modal=env.get_template('_revisao_editorial_panel.html').render(t=lambda k:translations.get(k,k))
    chromium=shutil.which('chromium') or shutil.which('chromium-browser')
    with sync_api.sync_playwright() as playwright:
        opts={'headless':True,'args':['--no-sandbox']}
        if chromium: opts['executable_path']=chromium
        browser=playwright.chromium.launch(**opts)
        try:
            page=browser.new_page(viewport={'width':1400,'height':950})
            errors=[];page.on('pageerror', lambda e:errors.append(str(e)))
            page.set_content('''<html lang="pt-BR"><body class="pagina-editor-app">
              <div class="barra-ferramentas barra-roteiro-sticky"></div>
              <div class="roteiro-layout"><aside class="roteiro-sidebar"></aside>
              <section class="painel-editor painel-roteiro"><div class="pagina-editor pagina-roteiro">
              <div class="editor-texto editor-roteiro" id="editorTexto" contenteditable="true"></div></div></section></div>
              <button id="btnAbrirRevisaoEditorial">Revisão</button>
              <input id="campoTituloCapitulo" value="Teste"><span id="statusAutosave"></span>
              <nav id="sumarioRoteiro"></nav><aside id="sidebarCardSumarioRoteiro"></aside>
              <input type="checkbox" id="toggleVisualizacaoRoteiro"><button id="btnToggleVisualizacaoRoteiro"></button>
              </body></html>''')
            from tests.test_navegacao_folhas import style
            for css in ('base.css','editorial-polish.css','atelier-ui.css','editor.css','editor_roteiro.css'):
                style(page, css)
            page.evaluate('''(html)=>{
                document.body.insertAdjacentHTML('beforeend',html);
                window.t=k=>window.ptTranslations[k] || k;
                window.EDITOR_CONFIG={slug:'teste',numero:1,catalogoPersonagens:[],catalogoLocais:[],catalogoAnotacoes:[]};
                window.fetch=async(url,options={}) => {
                    if(String(url).includes('/editorial/')) {
                      const payload=options.body?JSON.parse(options.body):null;
                      const state=window.revDB;
                      const versionId=String(url).split('/versoes/')[1]?.split('?')[0];
                      if(payload?.acao==='criar') state.itens.push({...payload,id:'a'+state.itens.length,estado:'pendente'});
                      if(payload?.acao==='estado') state.itens.find(x=>x.id===payload.id).estado=payload.estado;
                      if(payload?.acao==='versao') state.versoes.push({id:'backup'+state.versoes.length,rotulo:payload.rotulo,html:'<div>ANTES DA RESTAURAÇÃO</div>'});
                      if(versionId) return {ok:true,json:async()=>({ok:true,versao:state.versoes.find(x=>x.id===versionId)})};
                      return {ok:true,json:async()=>({ok:true,itens:state.itens,versoes:state.versoes.map(({html,...meta})=>meta)})};
                    }
                    return {ok:true,json:async()=>({ok:true})};
                };
                window.revDB={itens:[],versoes:[{id:'antiga',rotulo:'Versão anterior',titulo:'ROTEIRO',html:'<div class="roteiro-bloco" data-block-type="action">ROTEIRO RESTAURADO</div>'}]};
                document.getElementById('editorTexto').innerHTML=Array.from({length:40},(_,i)=>
                `<div class="roteiro-bloco" data-block-type="action">CENA ${i} - ESTAVA TUDO VELHO E QUIETO.</div>`).join('');
            }''',modal)
            page.evaluate('(d)=>window.ptTranslations=d',translations)
            page.add_script_tag(path=str(ROOT/'static/js/editor_roteiro.js'))
            page.wait_for_function("document.querySelectorAll('#editorTexto > .roteiro-page').length >= 1",timeout=25000)
            page.add_script_tag(path=str(ROOT/'static/js/revisao_editorial.js'))
            page.evaluate('''() => {
              const block=document.querySelector('.roteiro-bloco');
              const txt=Array.from(block.childNodes).find(x=>x.nodeType===3 && x.textContent.includes('VELHO'));
              const i=txt.textContent.indexOf('VELHO');
              const r=document.createRange();r.setStart(txt,i);r.setEnd(txt,i+5);
              getSelection().removeAllRanges();getSelection().addRange(r);
              document.dispatchEvent(new Event('selectionchange'));
            }''')
            page.locator('#btnAbrirRevisaoEditorial').click()
            page.locator('#revSubstituicao').fill('NOVO')
            page.locator('#btnRevSugerir').click()
            page.wait_for_function('window.revDB.itens.length===1')
            page.locator('#revListaNotas button').filter(has_text='Aceitar').click()
            page.wait_for_function("document.getElementById('editorTexto').textContent.includes('NOVO')")
            assert 'NOVO' in page.evaluate('serialize()')
            assert page.evaluate('window.revDB.itens[0].estado') == 'aceito'
            page.locator('#revAbaVersoes').click()
            page.once('dialog', lambda dialog: dialog.accept())
            page.locator('#revListaVersoes button').filter(has_text='Restaurar').first.click()
            page.wait_for_function("document.getElementById('editorTexto').textContent.includes('ROTEIRO RESTAURADO')")
            assert 'ROTEIRO RESTAURADO' in page.evaluate('serialize()')
            assert not errors,errors
        finally:
            browser.close()


def test_gut_com_revisao_editorial_integridade_e_importacao(tmp_path, monkeypatch):
    from modules import exportador_gut as gut
    origem=tmp_path/'original'; destino=tmp_path/'novo'
    origem.mkdir(); destino.mkdir()
    review.criar_item(origem,'livro',1,{'tipo':'comentario','trecho':'Uma cena','inicio':0,'nota':'Conferir continuidade'})
    review.criar_versao(origem,'livro',1,'Capítulo','<p>Uma cena antiga.</p>','Antes da revisão')
    projeto={'tipo':'livro','slug':'fonte','titulo':'Um livro','autor':'Autor','idioma':'pt-BR',
             'capitulos':[{'id':1}], 'descricao':'', 'tags':[]}
    criado=[]
    monkeypatch.setattr(gut,'obter_projeto',lambda slug: {**projeto,'slug':slug})
    monkeypatch.setattr(gut,'obter_pasta_projeto',lambda slug:origem if slug=='fonte' else destino)
    monkeypatch.setattr(gut,'ler_capitulo',lambda pasta,numero:{'titulo':'Capítulo','paragrafos':['<p>Uma cena atual.</p>']})
    monkeypatch.setattr(gut,'obter_pasta_exportacao_projeto',lambda *_: tmp_path)
    monkeypatch.setattr(gut,'atualizar_metadados_projeto',lambda *_: None)
    monkeypatch.setattr(gut,'criar_capitulo',lambda pasta,titulo:{'id':7,'titulo':titulo})
    monkeypatch.setattr(gut,'salvar_capitulo',lambda pasta,num,titulo,html,**kwargs:criado.append((num,html,kwargs)) or {'id':num,'titulo':titulo,'data_criacao':kwargs.get('data_criacao'),'data_atualizacao':kwargs.get('data_atualizacao')})
    pacote=gut.exportar_gut_capitulos('fonte')
    payload=gut.ler_payload_gut(pacote)
    anexos=payload['conteudo']['capitulos'][0]['revisao_editorial']
    assert anexos['itens'][0]['nota']=='Conferir continuidade'
    assert anexos['versoes'][0]['html']=='<p>Uma cena antiga.</p>'
    resultado=gut.importar_gut_em_projeto('novo',pacote)
    assert resultado['capitulos_importados']==1
    assert criado[0][:2]==(7,'<p>Uma cena atual.</p>')
    rev=review.ler(destino,'livro',7,incluir_html=True)
    assert rev['itens'][0]['trecho']=='Uma cena'
    assert rev['versoes'][0]['html']=='<p>Uma cena antiga.</p>'
    assert not review.ler(destino,'livro',1)['itens']


def test_destaques_sem_cor_personalizada_e_backup_ignora_cor_legada(tmp_path):
    pasta = tmp_path / 'cores'; pasta.mkdir()
    comentario = review.criar_item(pasta, 'livro', 9, {
        'tipo':'comentario', 'trecho':'um trecho', 'nota':'verificar', 'inicio':0
    })
    sugestao = review.criar_item(pasta, 'livro', 9, {
        'tipo':'sugestao', 'trecho':'um trecho', 'nota':'melhorar',
        'substituicao':'outro trecho', 'inicio':0
    })
    assert 'cor' not in comentario and 'cor' not in sugestao
    assert not hasattr(review, 'alterar_cor_item')

    # Backups legados podem conter uma cor customizada, mas a importação
    # não a reaplica: o tipo da anotação determina sua cor na interface.
    destino = tmp_path / 'cores-importadas'; destino.mkdir()
    review.importar_estado(destino, 'livro', 2, {
        'itens':[{**comentario, 'cor':'#12ab34'}], 'versoes':[]
    })
    importado = review.ler(destino, 'livro', 2)['itens'][0]
    assert 'cor' not in importado


def test_highlights_somente_com_revisao_aberta_e_tooltip_no_chromium():
    sync_api = pytest.importorskip('playwright.sync_api')
    env = Environment(loader=FileSystemLoader(str(ROOT/'templates')))
    translations = json.loads((ROOT/'locales'/'pt_BR.json').read_text('utf8'))
    modal = env.get_template('_revisao_editorial_panel.html').render(t=lambda k: translations.get(k,k))
    chromium = shutil.which('chromium') or shutil.which('chromium-browser')
    with sync_api.sync_playwright() as playwright:
        opts = {'headless':True,'args':['--no-sandbox']}
        if chromium: opts['executable_path'] = chromium
        browser = playwright.chromium.launch(**opts)
        try:
            page = browser.new_page(viewport={'width':1200,'height':850})
            errors=[]; page.on('pageerror', lambda e: errors.append(str(e)))
            page.set_content('''<html lang="pt-BR"><body>
              <button id="btnAbrirRevisaoEditorial">Revisão</button>
              <div id="editorTexto" contenteditable="true"><p>Uma passagem importante aparece aqui.</p></div>
              </body></html>''')
            page.evaluate('''(html) => {
              document.body.insertAdjacentHTML('beforeend',html);
              window.EDITOR_CONFIG={slug:'highlight-test',numero:1};
              window.reviewDb={itens:[],versoes:[]};
              window.fetch=async(url,options={})=>{
                if(options.body){const data=JSON.parse(options.body);
                  if(data.acao==='criar') reviewDb.itens.push({...data,id:'review-1',estado:'pendente'});
                  if(data.acao==='estado') Object.assign(reviewDb.itens.find(x=>x.id===data.id),{estado:data.estado});
                  if(data.acao==='apagar') reviewDb.itens=reviewDb.itens.filter(x=>x.id!==data.id);
                }
                return {ok:true,json:async()=>({ok:true,itens:reviewDb.itens,versoes:reviewDb.versoes})};
              };
            }''', modal)
            page.evaluate('(d)=>window.t=k=>d[k]||k', translations)
            page.add_style_tag(path=str(ROOT/'static/css/revisao_editorial.css'))
            page.add_script_tag(path=str(ROOT/'static/js/revisao_editorial.js'))
            original_html = page.locator('#editorTexto').evaluate('(el)=>el.innerHTML')
            page.locator('#btnAbrirRevisaoEditorial').click()
            page.evaluate('''() => {
              const text=document.querySelector('#editorTexto p').firstChild;
              const phrase='passagem importante'; const start=text.textContent.indexOf(phrase);
              const range=document.createRange();range.setStart(text,start);range.setEnd(text,start+phrase.length);
              getSelection().removeAllRanges();getSelection().addRange(range);
              document.dispatchEvent(new Event('selectionchange'));
            }''')
            page.locator('#revNota').fill('Rever a força desta passagem.')
            page.locator('#btnRevComentar').click()
            page.wait_for_function("window.reviewDb.itens.length===1 && CSS.highlights.has('gutenberg-review-review-1')")
            assert page.locator('#editorTexto').evaluate('(el)=>el.innerHTML') == original_html
            # Cor fixa azul para comentários; não existe mais seletor de cor.
            assert page.locator('.editorial-review-color').count() == 0
            assert '#60a5fa' in page.locator('#gutenbergEditorialHighlightStyles').text_content()
            # Hover mostra a anotação sem repetir o texto selecionado e dimensiona a caixa pelo conteúdo.
            rect = page.evaluate('''() => {
              const text=document.querySelector('#editorTexto p').firstChild;
              const start=text.textContent.indexOf('passagem importante');
              const range=document.createRange();range.setStart(text,start+4);range.setEnd(text,start+8);
              const r=range.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};
            }''')
            page.mouse.move(rect['x'],rect['y'])
            page.wait_for_function("!document.querySelector('.editorial-review-tooltip').hidden")
            tooltip = page.locator('.editorial-review-tooltip')
            assert 'Comentário' in tooltip.inner_text()
            assert 'Rever a força desta passagem.' in tooltip.inner_text()
            assert 'passagem importante' not in tooltip.inner_text()
            dimensions = tooltip.evaluate('(el)=>({width:el.getBoundingClientRect().width,height:el.getBoundingClientRect().height})')
            assert dimensions['width'] < 340 and dimensions['height'] < 190

            # Uma anotação maior aumenta a janela sem impor largura ou altura fixas.
            page.evaluate("""() => {
              window.reviewDb.itens[0].nota = 'Esta anotação é propositalmente extensa para comprovar que a janela acompanha o tamanho do conteúdo. '.repeat(8);
              window.GutenbergRevisaoEditorial.load();
            }""")
            page.wait_for_function("document.querySelector('.editorial-review-tooltip').hidden")
            page.mouse.move(rect['x'],rect['y'])
            page.wait_for_function("!document.querySelector('.editorial-review-tooltip').hidden && document.querySelector('.editorial-review-tooltip-note').textContent.length > 500")
            expanded = tooltip.evaluate('(el)=>({width:el.getBoundingClientRect().width,height:el.getBoundingClientRect().height})')
            assert expanded['width'] > dimensions['width']
            assert expanded['height'] > dimensions['height']
            assert expanded['width'] <= 520

            # Sugestões usam verde e destacam a explicação e o texto proposto.
            page.evaluate('''() => {
              const text=document.querySelector('#editorTexto p').firstChild.textContent;
              const trecho='aparece aqui'; const inicio=text.indexOf(trecho);
              window.reviewDb.itens.push({id:'review-2',tipo:'sugestao',estado:'pendente',
                trecho,nota:'Evite uma conclusão abrupta.',substituicao:'abre espaço para a próxima ideia',
                inicio,prefixo:text.slice(0,inicio),sufixo:''});
            }''')
            page.evaluate('window.GutenbergRevisaoEditorial.load()')
            page.wait_for_function("CSS.highlights.has('gutenberg-review-review-2')")
            assert '#4ade80' in page.locator('#gutenbergEditorialHighlightStyles').text_content()
            suggestion_rect = page.evaluate('''() => {
              const text=document.querySelector('#editorTexto p').firstChild;
              const start=text.textContent.indexOf('aparece aqui');
              const range=document.createRange();range.setStart(text,start+2);range.setEnd(text,start+6);
              const r=range.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};
            }''')
            page.mouse.move(suggestion_rect['x'],suggestion_rect['y'])
            page.wait_for_function("document.querySelector('.editorial-review-tooltip').classList.contains('editorial-review-tooltip--suggestion')")
            assert 'Evite uma conclusão abrupta.' in tooltip.inner_text()
            assert 'abre espaço para a próxima ideia' in tooltip.inner_text()
            assert 'aparece aqui' not in tooltip.inner_text()
            # Fechar a janela remove os highlights; reabrir e resolver também os remove.
            page.locator('#btnFecharRevisaoEditorial').click()
            assert page.evaluate("CSS.highlights.has('gutenberg-review-review-1')") is False
            page.locator('#btnAbrirRevisaoEditorial').click()
            page.wait_for_function("CSS.highlights.has('gutenberg-review-review-1')")
            page.evaluate("window.reviewDb.itens[0].estado='resolvido'")
            page.evaluate("window.GutenbergRevisaoEditorial.load()")
            page.wait_for_function("!CSS.highlights.has('gutenberg-review-review-1')")
            assert not errors, errors
        finally:
            browser.close()
