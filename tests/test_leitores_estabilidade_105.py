"""Regressão de leitores Biblioteca/EPUB e conversão PDF para leitura.

Executa JS real do Gutenberg em Chromium, com requisições de progresso simuladas.
"""
from __future__ import annotations

import html
import shutil
import zipfile
from pathlib import Path

import pytest

pwlib = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]


def start_browser(pw):
    binary = shutil.which('chromium') or shutil.which('chromium-browser')
    return pw.chromium.launch(headless=True, executable_path=binary, args=['--no-sandbox']) if binary else pw.chromium.launch(headless=True)


def prepare_reader(page, reader_file: str):
    # É o mesmo contrato DOM usado tanto pelo leitor da Biblioteca quanto pelo EPUB.
    content = ''.join(f'<p id="p{i}">Linha {i} de leitura com mais conteúdo para medir as linhas e os espaços.</p>' for i in range(130))
    frame_html = f'<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>{content}</body></html>'
    page.set_content(f'''<!DOCTYPE html><html><body style="margin:0;">
    <div style="height:180px">Cabeçalho do leitor</div>
    <section id="areaLeitura" style="width:100%;max-width:960px;">
      <iframe id="epubFrame" sandbox="allow-same-origin" srcdoc="{html.escape(frame_html,quote=True)}" data-posicao-inicial="0" style="display:block;width:100%;border:0;"></iframe>
    </section>
    <span id="indicadorProgressoLivro"></span>
    <div class="leitor-config-anchor">
      <button id="abrirConfiguracoesLeitor"></button><div class="oculto" id="configuracoesLeitor"><button id="fecharConfiguracoesLeitor"></button></div>
      <select id="controleTema"><option value="light">light</option><option value="dark">dark</option></select>
      <select id="controleFonte"><option value="literata">Literata</option><option value="arial">Arial</option></select>
      <input id="controleTamanho" type="number" value="20"><input id="controleLargura" type="range" min="30" max="90" value="90">
      <span id="valorLarguraLeitura"></span><span id="valorMaxLarguraLeitura"></span>
      <select id="controleIdiomaTts"><option value="pt_BR">PT</option></select>
      <input id="controleVelocidadeTts" value="1"><input id="controleVolumeTts" value="100">
      <span id="valorVelocidadeTts"></span><span id="valorVolumeTts"></span>
    </div><button id="abrirSumario"></button><div id="modalSumario" class="oculto"></div>
    </body></html>''')
    page.evaluate('''() => {
      window.LEITOR_CONFIG={slug:'livroTeste',base:'biblioteca',numero:1,overrides:{espacoLinhas:1.5},salvarPosicaoUrl:'/api/teste/posicao',posicaoInicial:0};
      Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:()=>null,setItem:()=>{}}});
      window.__postos=[];window.__pendentes=[];window.__configCount=0;window.__holdPosicoes=false;
      window.fetch=(url,config={})=>{
        if(String(url).includes('/configuracoes/')){ window.__configCount++;return Promise.resolve({ok:true}); }
        if(String(url).includes('/api/teste/posicao')){
          window.__postos.push(JSON.parse(config.body));
          if(!window.__holdPosicoes) return Promise.resolve({ok:true});
          return new Promise((resolve,reject)=>window.__pendentes.push({resolve,reject}));
        }
        return Promise.resolve({ok:true});
      };
      const RO=window.ResizeObserver;
      window.__observers=0;
      if(RO) window.ResizeObserver=class extends RO {constructor(cb){super(cb);window.__observers++;}};
    }''')
    page.add_script_tag(path=str(ROOT / 'static/js' / reader_file))
    page.wait_for_function("document.getElementById('epubFrame').contentDocument?.getElementById('epubplus-overrides') !== null", timeout=15000)
    page.wait_for_timeout(120)


@pytest.mark.parametrize('reader_file', ['leitor.js', 'leitor_alt.js'])
def test_leitor_reutiliza_observadores_e_nao_regrava_css_igual(reader_file):
    with pwlib.sync_playwright() as pw:
        browser=start_browser(pw)
        try:
            page=browser.new_page(viewport={'width':1100,'height':700})
            errors=[]
            page.on('pageerror', lambda e: errors.append(str(e)))
            prepare_reader(page,reader_file)
            result=page.evaluate('''() => {
              const frame=document.getElementById('epubFrame');
              const doc=frame.contentDocument;
              const el=doc.getElementById('epubplus-overrides');
              const texto=el.firstChild;
              const antes=window.__observers;
              for(let n=0;n<25;n++) aplicarPreferenciasNoIframe();
              const mesmosObservadores=window.__observers === antes;
              const mesmoTexto=el.firstChild === texto;
              document.getElementById('controleTamanho').value='32';
              aplicarPreferenciasNoIframe();
              return {mesmosObservadores,mesmoTexto,observers:window.__observers,antes, cssMudou:el.firstChild!==texto, altura:frame.getBoundingClientRect().height};
            }''')
            assert result['mesmosObservadores'], result
            assert result['mesmoTexto'], result
            assert result['cssMudou'], result
            assert result['altura']>700, result
            assert not errors, errors
        finally:
            browser.close()


@pytest.mark.parametrize('reader_file', ['leitor.js', 'leitor_alt.js'])
def test_leitor_gravacao_fila_nao_perde_ultima_posicao(reader_file):
    with pwlib.sync_playwright() as pw:
        browser=start_browser(pw)
        try:
            page=browser.new_page(viewport={'width':1100,'height':700})
            errors=[]
            page.on('pageerror', lambda e: errors.append(str(e)))
            prepare_reader(page,reader_file)
            # Aguarda a restauração antes de rolar para não competir com ela.
            page.wait_for_timeout(400)
            page.evaluate('window.__postos=[];window.__holdPosicoes=true')
            page.evaluate('''() => {window.scrollTo({top:480,behavior:'instant'});enviarPosicaoLeitura(false);}''')
            page.wait_for_function('window.__postos.length>=1', timeout=6000)
            page.evaluate('''() => {window.scrollTo({top:1100,behavior:'instant'});enviarPosicaoLeitura(false);}''')
            page.wait_for_timeout(70)
            assert page.evaluate('window.__postos.length') == 1, 'Posições não podem ultrapassar requisições pendentes.'
            page.evaluate('window.__pendentes.shift().resolve({ok:true})')
            page.wait_for_function('window.__postos.length>=2', timeout=6000)
            enviados=page.evaluate('window.__postos')
            assert enviados[1]['posicao']>enviados[0]['posicao'], enviados
            page.evaluate('window.__pendentes.shift().resolve({ok:true})')
            page.wait_for_timeout(250)
            assert not errors, errors
        finally:
            browser.close()


@pytest.mark.parametrize('reader_file', ['leitor.js', 'leitor_alt.js'])
def test_falha_na_posicao_nao_marca_sucesso_e_permite_tentar_novamente(reader_file):
    with pwlib.sync_playwright() as pw:
        browser=start_browser(pw)
        try:
            page=browser.new_page(viewport={'width':1100,'height':700})
            prepare_reader(page,reader_file)
            page.wait_for_timeout(400)
            page.evaluate('window.__postos=[];window.__holdPosicoes=true')
            page.evaluate('''() => {window.scrollTo({top:560,behavior:'instant'});enviarPosicaoLeitura(false);}''')
            page.wait_for_function('window.__postos.length>=1', timeout=5000)
            page.evaluate("window.__pendentes.shift().reject(new Error('offline'))")
            page.wait_for_timeout(60)
            page.evaluate('enviarPosicaoLeitura(false)')
            page.wait_for_function('window.__postos.length>=2', timeout=5000)
            enviados=page.evaluate('window.__postos')
            assert enviados[1]['posicao'] == enviados[0]['posicao'], enviados
            page.evaluate('window.__pendentes.shift().resolve({ok:true})')
        finally:
            browser.close()


def test_pdf_importado_e_lido_como_epub_refluivel(tmp_path):
    fitz = pytest.importorskip('fitz')
    from modules.conversor_pdf_epub import converter_pdf_para_epub3
    arquivo=tmp_path/'livro.pdf'
    doc=fitz.open()
    for i in range(3):
        folha=doc.new_page(width=595,height=842)
        folha.insert_text((65,80),f'Capítulo {i+1}',fontsize=19)
        folha.insert_text((65,145),f'Texto de leitura da página {i+1}, com acentuação e conteúdo.',fontsize=12)
    doc.save(arquivo)
    doc.close()
    saida=tmp_path/'livro.epub'
    resultado=converter_pdf_para_epub3(arquivo,saida)
    assert resultado['paginas']==3
    assert saida.exists()
    with zipfile.ZipFile(saida) as z:
        assert z.testzip() is None
        assert z.read('mimetype')==b'application/epub+zip'
        items=[name for name in z.namelist() if name.endswith('.xhtml') and 'chapter_' in name]
        assert items, z.namelist()
        conteudo=''.join(z.read(item).decode('utf-8') for item in items)
        assert 'Texto de leitura da página' in conteudo
        assert 'acentuação' in conteudo


def test_iframe_epub_impede_script_embutido_sem_impedir_tipografia():
    # EPUBs de terceiros podem conter scripts. O leitor deve poder ajustar o
    # estilo sem executar código do próprio livro com privilégios do aplicativo.
    for template in ('leitor.html', 'leitor_alt.html'):
        texto = (ROOT / 'templates' / template).read_text(encoding='utf-8')
        assert '<iframe id="epubFrame" sandbox="allow-same-origin"' in texto
        assert 'allow-scripts' not in texto.split('<iframe id="epubFrame"', 1)[1].split('>', 1)[0]
    with pwlib.sync_playwright() as pw:
        browser=start_browser(pw)
        try:
            page=browser.new_page()
            page.set_content('''<iframe id="frame" sandbox="allow-same-origin"
              srcdoc="&lt;h2 id='capitulo'&gt;Capítulo&lt;/h2&gt;&lt;script&gt;parent.executouScriptMalicioso=true&lt;/script&gt;"></iframe>''')
            page.wait_for_function("document.getElementById('frame').contentDocument?.getElementById('capitulo') !== null")
            result=page.evaluate('''() => {
              const doc=document.getElementById('frame').contentDocument;
              const estilo=doc.createElement('style');estilo.textContent='h2{color:rgb(200,0,0)}';doc.head.appendChild(estilo);
              return {executou:!!window.executouScriptMalicioso, titulo:doc.getElementById('capitulo').textContent,
                cor:doc.defaultView.getComputedStyle(doc.getElementById('capitulo')).color};
            }''')
            assert result == {'executou':False,'titulo':'Capítulo','cor':'rgb(200, 0, 0)'}, result
        finally:
            browser.close()


def test_pdf_escaneado_sem_texto_mantem_imagem_em_epub(tmp_path):
    fitz=pytest.importorskip('fitz')
    from PIL import Image, ImageDraw
    import io
    from modules.conversor_pdf_epub import converter_pdf_para_epub3
    img=Image.new('RGB',(380,500),'white')
    desenho=ImageDraw.Draw(img)
    desenho.rectangle((30,30,350,455),outline='#333333',width=5)
    desenho.text((60,80),'Pagina digitalizada',fill='black')
    arquivo_imagem=io.BytesIO();img.save(arquivo_imagem,format='PNG')
    doc=fitz.open();pagina=doc.new_page(width=500,height=700)
    pagina.insert_image(fitz.Rect(45,40,455,650),stream=arquivo_imagem.getvalue())
    pdf=tmp_path/'digitalizado.pdf';doc.save(pdf);doc.close()
    saida=tmp_path/'digitalizado.epub'
    resultado=converter_pdf_para_epub3(pdf,saida)
    assert resultado['paginas']==1
    with zipfile.ZipFile(saida) as z:
        assert z.testzip() is None
        imagens=[n for n in z.namelist() if n.startswith('OEBPS/images/') and n.endswith('.jpg')]
        assert imagens, z.namelist()
        capitulos=[n for n in z.namelist() if n.endswith('.xhtml') and 'chapter_' in n]
        texto=''.join(z.read(n).decode('utf-8') for n in capitulos)
        assert '<img' in texto
        from lxml import etree
        for c in capitulos:
            etree.fromstring(z.read(c))


@pytest.mark.parametrize('reader_file', ['leitor.js', 'leitor_alt.js'])
def test_leitor_muda_tema_e_fonte_sem_perder_documento(reader_file):
    with pwlib.sync_playwright() as pw:
        browser=start_browser(pw)
        try:
            page=browser.new_page(viewport={'width':1180,'height':700})
            errors=[]
            page.on('pageerror', lambda e: errors.append(str(e)))
            prepare_reader(page,reader_file)
            page.locator('#controleTema').select_option('dark')
            page.locator('#controleFonte').select_option('arial')
            page.locator('#controleTamanho').fill('26')
            page.locator('#controleTamanho').dispatch_event('input')
            result=page.evaluate('''() => {
              const f=document.getElementById('epubFrame'),doc=f.contentDocument;
              const p=doc.getElementById('p0');
              const ultimo=doc.getElementById('p129');
              return {tag:p.textContent.includes('Linha 0'),count:doc.querySelectorAll('p').length,
                cor:doc.defaultView.getComputedStyle(p).color,
                altura: f.getBoundingClientRect().height,
                ultimoY:ultimo.getBoundingClientRect().bottom,
                fonte:doc.defaultView.getComputedStyle(p).fontFamily};
            }''')
            assert result['tag'] and result['count']==130, result
            assert result['altura']>700 and result['ultimoY']<=result['altura']+4, result
            assert 'Arial' in result['fonte'], result
            assert not errors, errors
        finally:
            browser.close()


@pytest.mark.parametrize('reader_file', ['leitor.js', 'leitor_alt.js'])
def test_leitor_dicionario_conecta_com_iframe_isolado(reader_file):
    with pwlib.sync_playwright() as pw:
        browser=start_browser(pw)
        try:
            page=browser.new_page()
            errors=[]
            page.on('pageerror', lambda e: errors.append(str(e)))
            prepare_reader(page,reader_file)
            page.add_script_tag(path=str(ROOT/'static/js/leitor_dicionario.js'))
            page.evaluate('''() => document.getElementById('epubFrame').dispatchEvent(new Event('load'))''')
            page.wait_for_function("document.getElementById('epubFrame').contentDocument.documentElement.dataset.dictionaryAltClickBound==='true'")
            assert not errors, errors
        finally:
            browser.close()


def test_tts_funciona_no_iframe_isolado_e_troca_destaque_sem_varredura_total():
    with pwlib.sync_playwright() as pw:
        browser=start_browser(pw)
        try:
            page=browser.new_page(viewport={'width':1050,'height':760})
            errors=[]
            page.on('pageerror',lambda e: errors.append(str(e)))
            prepare_reader(page,'leitor.js')
            page.evaluate('''() => {
              const btn=document.createElement('button');btn.id='botaoTtsLeitor';
              const span=document.createElement('span');span.className='icone-svg';btn.appendChild(span);
              document.body.appendChild(btn);
              window.__audios=[];
              window.Audio=class {
                constructor(){this.paused=true;this.ended=false;this.volume=1;this.error=null;this.readyState=3;window.__audios.push(this);}
                async play(){this.paused=false;this.onplay?.();return undefined;}
                pause(){this.paused=true;this.onpause?.();}
                removeAttribute(){} load(){}
              };
              const original=DOMTokenList.prototype.remove;
              window.__destaquesRemovidos=0;
              DOMTokenList.prototype.remove=function(...args){if(args.includes('tts-atual'))window.__destaquesRemovidos++;return original.apply(this,args);};
              window.fetch=async (url) => {
                if(String(url).includes('/api/tts/modelos/status')) return {ok:true,json:async()=>({ok:true,estado:{instalado:true}})};
                if(String(url).includes('/api/tts/kokoro')) return {ok:true,status:200,headers:{get:()=>null},blob:async()=>new Blob(['RIFF'],{type:'audio/wav'})};
                return {ok:true,json:async()=>({ok:true})};
              };
            }''')
            page.add_script_tag(path=str(ROOT/'static/js/leitor_tts.js'))
            page.locator('#botaoTtsLeitor').click()
            page.wait_for_function("document.getElementById('epubFrame').contentDocument.querySelectorAll('.tts-trecho').length > 40",timeout=7000)
            page.wait_for_function("window.__audios.length>0 && document.getElementById('epubFrame').contentDocument.querySelectorAll('.tts-atual').length===1",timeout=7000)
            before=page.evaluate('window.__destaquesRemovidos')
            page.evaluate('window.__audios[0].onended?.()')
            page.wait_for_function('window.__audios.length>1',timeout=5000)
            page.wait_for_timeout(750)
            result=page.evaluate('''() => ({
              total:document.getElementById('epubFrame').contentDocument.querySelectorAll('.tts-trecho').length,
              destacados:document.getElementById('epubFrame').contentDocument.querySelectorAll('.tts-atual').length,
              removidos:window.__destaquesRemovidos
            })''')
            assert result['destacados']==1 and result['total']>=40,result
            assert result['removidos']-before<=3,result
            assert not errors,errors
        finally:
            browser.close()
