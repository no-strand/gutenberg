"""Benchmark manual dos editores em Chromium, sem Flask.

Uso: python tests/stress_editores_manual.py --counts 100 500 1500 --output result.json
Números são BLOCOS, não páginas reais. O teste usa o mesmo ambiente para
comparar alterações e não é prova de desempenho em projetos reais.
"""
import argparse
import json
import re
import shutil
import statistics
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def css_source(filename):
    css = (ROOT / 'static' / 'css' / filename).read_text(encoding='utf-8')
    # Playwright não deve esperar a rede por fontes externas.
    return re.sub(r'@import\s+url\([^;]+;', '', css)


def mount(page, mode, paragraphs):
    cls = 'painel-word' if mode == 'epub' else 'painel-editor painel-roteiro'
    papercls = 'pagina-editor' if mode == 'epub' else 'pagina-editor pagina-roteiro'
    editorcls = 'editor-texto' if mode == 'epub' else 'editor-texto editor-roteiro'
    page.set_content(f'''<html><head></head><body class="pagina-editor-app"
       style="--cfg-font-size:18px;--cfg-line-height:1.6;--cfg-espaco-paragrafo:12px">
        <section class="barra-ferramentas {'barra-roteiro barra-roteiro-sticky' if mode == 'roteiro' else 'barra-word-sticky'}">
          <button data-comando="bold" data-valor="bold">Negrito</button>
          <span id="indicadorTipoBloco"></span>
        </section>
        <div class="roteiro-layout">{'<aside class="roteiro-sidebar"></aside>' if mode == 'roteiro' else ''}<div class="{cls}"><div class="{papercls}">
          <div id="editorTexto" class="{editorcls}" contenteditable="true"></div>
        </div></div></div>
        <input id="campoTituloCapitulo" value="Teste">
        <span id="statusAutosave"></span><nav id="sumarioRoteiro"></nav>
        <aside id="sidebarCardSumarioRoteiro"></aside>
        <input type="checkbox" id="toggleVisualizacaoRoteiro">
        <button id="btnToggleVisualizacaoRoteiro"></button>
      </body></html>''')
    page.evaluate('''() => {
      window.__rafSamples = [];
      window.__longTasks = [];
      window.__styleReads = 0;
      const originalComputedStyle = window.getComputedStyle;
      window.getComputedStyle = function(...args) {
        window.__styleReads += 1;
        return originalComputedStyle.apply(this, args);
      };
      const rafOriginal = window.requestAnimationFrame.bind(window);
      window.requestAnimationFrame = function(fn) {
        return rafOriginal(function(t) {
          const start = performance.now();
          try { return fn(t); } finally {
            window.__rafSamples.push({nome: fn.name || 'anonimo', ms:performance.now()-start});
          }
        });
      };
      try {
        new PerformanceObserver(list => list.getEntries().forEach(e =>
          window.__longTasks.push(e.duration))).observe({entryTypes:['longtask']});
      } catch (_) {}
      window.EDITOR_CONFIG = {slug:'stress', numero:1, numeracaoInicial:1,
        catalogoPersonagens:[], catalogoLocais:[], catalogoAnotacoes:[]};
      Object.defineProperty(window, 'localStorage', {configurable:true,
        value:{getItem:()=>null,setItem:()=>{}}});
      window.fetch = async () => ({ok:true, json:async () => ({ok:true})});
    }''')
    # Layout real: base.html carrega estes dois temas ANTES do CSS do editor.
    # Sem atelier-ui, .epub-paper-layers deixa de ser absoluta e o teste
    # confunde a altura das folhas com transbordamento de texto.
    for name in ('editorial-polish.css', 'atelier-ui.css', 'editor.css',
                 'editor_roteiro.css' if mode == 'roteiro' else 'fontes-editor.css'):
        page.add_style_tag(content=css_source(name))
    if mode == 'epub':
        page.evaluate('''(n) => {document.getElementById('editorTexto').innerHTML =
          Array.from({length:n},(_,i)=>`<p>Parágrafo ${i}: `+'palavras de teste '.repeat(12)+'</p>').join('');}''', paragraphs)
        page.add_script_tag(path=str(ROOT / 'static/js/editor.js'))
        page.add_script_tag(path=str(ROOT / 'static/js/epub-pagination.js'))
    else:
        page.evaluate('''(n) => {document.getElementById('editorTexto').innerHTML =
          Array.from({length:n},(_,i)=>`<div class="roteiro-bloco" data-block-type="${i%17===0?'scene_heading':'action'}">`+
          'TEXTO DE CENA PARA MEDIR O EDITOR. '.repeat(5)+'</div>').join('');}''', paragraphs)
        page.add_script_tag(path=str(ROOT / 'static/js/editor_roteiro.js'))


def run(counts, output):
    records = []
    with sync_playwright() as p:
        options = {'headless':True, 'args':['--no-sandbox','--disable-background-networking']}
        executable = shutil.which('chromium') or shutil.which('chromium-browser')
        if executable: options['executable_path'] = executable
        browser = p.chromium.launch(**options)
        try:
            for mode in ('epub', 'roteiro'):
                for count in counts:
                    page = browser.new_page(viewport={'width':1440,'height':950})
                    page.set_default_timeout(20000)
                    errors = []
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    started = time.perf_counter()
                    mount(page, mode, count)
                    ready_ms = (time.perf_counter()-started)*1000
                    if mode == 'epub':
                        page.wait_for_timeout(360)
                    else:
                        page.wait_for_timeout(360)
                    info = page.evaluate('''() => ({
                      blocks: document.querySelectorAll('#editorTexto > p, .roteiro-bloco').length,
                      pages: document.querySelectorAll('.epub-paper-sheet,.roteiro-page').length,
                      htmlLength:document.querySelector('#editorTexto').innerHTML.length
                    })''')
                    timings = []
                    page.evaluate('''() => {window.__rafSamples = [];window.__longTasks = [];window.__styleReads=0}''')
                    for trial in range(3):
                        # Digita no fim (caminho de entrada mais comum em documentos longos).
                        page.evaluate('''() => {
                          const root = document.getElementById('editorTexto');
                          const last = root.querySelector('.roteiro-bloco:last-of-type') || root.lastElementChild;
                          const r = document.createRange();
                          r.selectNodeContents(last); r.collapse(false);
                          getSelection().removeAllRanges(); getSelection().addRange(r); last.focus();
                        }''')
                        started = time.perf_counter()
                        page.keyboard.insert_text('x')
                        elapsed = (time.perf_counter() - started)*1000
                        timings.append(round(elapsed, 2))
                        page.wait_for_timeout(270)
                    snapshot = page.evaluate('''() => ({
                      blocks: document.querySelectorAll('#editorTexto > p, .roteiro-bloco').length,
                      pages: document.querySelectorAll('.epub-paper-sheet,.roteiro-page').length,
                      hasX:document.getElementById('editorTexto').textContent.includes('x'),
                      composing: typeof isEditorComposing === 'boolean' ? isEditorComposing : null
                    })''')
                    traces = page.evaluate('''() => ({
                      raf:window.__rafSamples, longtasks:window.__longTasks,
                      styleReads:window.__styleReads,
                      maxScroll:document.documentElement.scrollHeight
                    })''')
                    raf_ms = sorted([e['ms'] for e in traces['raf']],reverse=True)
                    record = {'editor':mode,'blocos_iniciais':count,
                        'montagem_ms':round(ready_ms,1),'digitacao_ms':timings,
                        'mediana_digitacao_ms':round(statistics.median(timings),2),
                        'inicial':info,'apos':snapshot,'erros':errors,
                        'raf_ms_max':round(raf_ms[0],2) if raf_ms else None,
                        'raf_ms_total':round(sum(raf_ms),2),
                        'longtasks_ms': [round(v,1) for v in traces['longtasks']],
                        'leituras_de_estilo':traces['styleReads']}
                    records.append(record)
                    print(json.dumps(record,ensure_ascii=False),flush=True)
                    page.close()
        finally:
            browser.close()
    if output:
        Path(output).write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    return records


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--counts',type=int,nargs='+',default=[100,500,1500])
    ap.add_argument('--output',type=str,default='')
    args=ap.parse_args()
    run(args.counts,args.output)
