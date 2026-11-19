"""Parte 3: resistência de colagem, IME, imagens, histórico e seleção.

Testes em Chromium headless com a interface real dos dois editores, sem Flask.
Não depende dos dados do usuário nem de chamadas à rede.
"""
import shutil

import pytest

pytest.importorskip('playwright.sync_api')
from playwright.sync_api import sync_playwright
from tests.stress_editores_manual import mount


def browser(p):
    opts = {'headless': True, 'args': ['--no-sandbox', '--disable-background-networking']}
    exe = shutil.which('chromium') or shutil.which('chromium-browser')
    if exe:
        opts['executable_path'] = exe
    return p.chromium.launch(**opts)


def new_editor(b, mode, blocks=12):
    page = b.new_page(viewport={'width': 1440, 'height': 950})
    page.set_default_timeout(15000)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    mount(page, mode, blocks)
    page.wait_for_timeout(300)
    return page, errors


def test_epub_colagem_extensa_mantem_ordem_sufixo_e_historico():
    with sync_playwright() as pw:
        b = browser(pw)
        try:
            page, errors = new_editor(b, 'epub')
            page.evaluate('''() => {
              editor.innerHTML='<p>ANTES DEPOIS</p>';
              markEditorDirty(); commitHistory('base',true);
              const r=document.createRange();r.setStart(editor.querySelector('p').firstChild,6);r.collapse(true);
              getSelection().removeAllRanges();getSelection().addRange(r);editor.focus();
            }''')
            result = page.evaluate('''() => {
              const data=new DataTransfer();
              const lines=Array.from({length:300},(_,i)=>`Linha ${i} — café ação`);
              data.setData('text/plain',lines.join('\\r\\n'));
              const evt=new ClipboardEvent('paste',{bubbles:true,cancelable:true,clipboardData:data});
              editor.dispatchEvent(evt);
              return {handled:evt.defaultPrevented,lines};
            }''')
            after = page.evaluate('''() => ({
              blocks:[...editor.querySelectorAll('p')].map(el=>el.textContent),
              selected:editor.contains(getSelection().anchorNode),
              serialized:getHtmlEditorNormalizado()
            })''')
            assert result['handled']
            assert len(after['blocks']) == 300
            assert after['blocks'][0] == 'ANTES Linha 0 — café ação'
            assert after['blocks'][1] == 'Linha 1 — café ação'
            assert after['blocks'][-1] == 'Linha 299 — café açãoDEPOIS'
            assert after['selected'] and 'Linha 299 — café ação' in after['serialized']
            page.wait_for_timeout(240)  # commit debounced (180ms)
            page.evaluate('undoEditor()')
            assert page.locator('#editorTexto').inner_text().strip() == 'ANTES DEPOIS'
            page.evaluate('redoEditor()')
            assert page.locator('#editorTexto > p').count() == 300
            assert page.locator('#editorTexto > p:last-child').inner_text() == 'Linha 299 — café açãoDEPOIS'
            assert not errors, errors
        finally:
            b.close()


def test_epub_imagem_assincrona_respeita_selecao_no_inicio_da_leitura():
    with sync_playwright() as pw:
        b = browser(pw)
        try:
            page, errors = new_editor(b, 'epub')
            page.evaluate('''() => {
              editor.innerHTML='<p id="primeiro">PRIMEIRO</p><p id="segundo">SEGUNDO</p>';
              // Simula uma leitura que só termina após o usuário mover o cursor.
              window.FileReader=class {
                readAsDataURL() {
                  setTimeout(()=> {this.result='data:image/png;base64,iVBORw0KGgo=';this.onload?.();},80);
                }
              };
              const first=document.querySelector('#primeiro');
              const r=document.createRange();r.selectNodeContents(first);r.collapse(false);
              getSelection().removeAllRanges();getSelection().addRange(r);editor.focus();
              insertImageFromFile(new File(['png'],'figura.png',{type:'image/png'}));
              const second=document.querySelector('#segundo');
              const later=document.createRange();later.selectNodeContents(second);later.collapse(false);
              getSelection().removeAllRanges();getSelection().addRange(later);
            }''')
            page.wait_for_timeout(180)
            result = page.evaluate('''() => {
              const img=editor.querySelector('img');
              const blocks=[...editor.children];
              return {prev:img?.previousElementSibling?.textContent,
                next:img?.nextElementSibling?.tagName,
                imgCount:editor.querySelectorAll('img').length,
                idx:blocks.indexOf(img),second:blocks.indexOf(document.querySelector('#segundo')),
                saved:getHtmlEditorNormalizado().includes('data:image/png')};
            }''')
            assert result['imgCount'] == 1, result
            assert result['prev'] == 'PRIMEIRO', result
            assert result['idx'] < result['second'], result
            assert result['next'] == 'P' and result['saved'], result
            assert not errors, errors
        finally:
            b.close()


def test_roteiro_ime_enter_backspace_e_atalhos_nao_interrompem_composicao():
    with sync_playwright() as pw:
        b = browser(pw)
        try:
            page, errors = new_editor(b, 'roteiro')
            result = page.evaluate('''() => {
              const block=document.querySelectorAll('.roteiro-bloco')[3];
              const r=document.createRange();r.selectNodeContents(block);r.collapse(false);
              getSelection().removeAllRanges();getSelection().addRange(r);block.focus();
              const countBefore=editor.querySelectorAll('.roteiro-bloco').length;
              const textBefore=block.textContent;
              block.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true,data:''}));
              const events=[];
              for(const key of ['Enter','Backspace','Escape','z']) {
                const e=new KeyboardEvent('keydown',{key,bubbles:true,cancelable:true,ctrlKey:key==='z'});
                block.dispatchEvent(e);
                events.push(e.defaultPrevented);
              }
              block.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true,data:'ç'}));
              return {events,countBefore,countAfter:editor.querySelectorAll('.roteiro-bloco').length,
                sameText:block.textContent===textBefore,inside:editor.contains(getSelection().anchorNode)};
            }''')
            assert result['events'] == [False]*4, result
            assert result['countAfter'] == result['countBefore'] and result['sameText'] and result['inside'], result
            page.wait_for_timeout(500)
            assert not errors, errors
        finally:
            b.close()


def test_roteiro_colagem_html_extensa_preserva_texto_no_salvamento():
    with sync_playwright() as pw:
        b = browser(pw)
        try:
            page, errors = new_editor(b, 'roteiro', 40)
            result = page.evaluate('''() => {
              const block=document.querySelectorAll('.roteiro-bloco')[5];
              const r=document.createRange();r.selectNodeContents(block);r.collapse(false);
              getSelection().removeAllRanges();getSelection().addRange(r);block.focus();
              const html=Array.from({length:60},(_,i)=>`<p>COLADO ${i} ação e café</p>`).join('');
              return {ok:document.execCommand('insertHTML',false,html)};
            }''')
            page.wait_for_timeout(750)
            saved = page.evaluate('''() => ({
              all:editor.textContent,serialized:serialize(),
              orphanNodes:editor.querySelectorAll('.roteiro-page-content > p, .roteiro-page-content > h1').length,
              selectionInside:editor.contains(getSelection().anchorNode),
              pages:editor.querySelectorAll('.roteiro-page').length
            })''')
            assert result['ok']
            for i in (0, 29, 59):
                assert f'COLADO {i} ação e café' in saved['all']
                assert f'COLADO {i} ação e café' in saved['serialized']
            assert saved['orphanNodes'] == 0, saved
            assert saved['pages'] >= 2
            assert not errors, errors
        finally:
            b.close()


def test_epub_undo_redo_prolongado_sem_perda_de_caret():
    with sync_playwright() as pw:
        b = browser(pw)
        try:
            page, errors = new_editor(b, 'epub', 25)
            page.evaluate('''() => {
              editor.innerHTML='<p>Raiz</p>';markEditorDirty();commitHistory('base',true);
              const r=document.createRange();r.selectNodeContents(editor.firstElementChild);r.collapse(false);
              getSelection().removeAllRanges();getSelection().addRange(r);editor.focus();
            }''')
            for index in range(22):
                page.keyboard.insert_text(f'-{index}')
                page.evaluate('''() => {commitHistory('point', true)}''')
            before = page.locator('#editorTexto').inner_text()
            assert before == 'Raiz'+''.join(f'-{i}' for i in range(22))
            for _ in range(22):
                page.evaluate('undoEditor()')
            after = page.locator('#editorTexto').inner_text()
            assert after == 'Raiz', after
            for _ in range(22):
                page.evaluate('redoEditor()')
            assert page.locator('#editorTexto').inner_text() == before
            assert page.evaluate('editor.contains(getSelection().anchorNode)')
            assert not errors, errors
        finally:
            b.close()


def test_roteiro_desfazer_refazer_nativo_apos_repaginar():
    with sync_playwright() as pw:
        b = browser(pw)
        try:
            page, errors = new_editor(b, 'roteiro', 65)
            page.evaluate('''() => {
              const el=document.querySelectorAll('.roteiro-bloco')[4];
              const r=document.createRange();r.selectNodeContents(el);r.collapse(false);
              getSelection().removeAllRanges();getSelection().addRange(r);el.focus();
            }''')
            original = page.evaluate("document.querySelectorAll('.roteiro-bloco')[4].textContent")
            page.keyboard.insert_text(' ZXCVTEST')
            page.wait_for_timeout(460)
            after = page.evaluate("document.querySelectorAll('.roteiro-bloco')[4].textContent")
            assert after.endswith('ZXCVTEST')
            page.keyboard.press('Control+z')
            page.wait_for_timeout(440)
            assert page.evaluate("document.querySelectorAll('.roteiro-bloco')[4].textContent") == original
            page.keyboard.press('Control+Shift+z')
            page.wait_for_timeout(440)
            assert page.evaluate("document.querySelectorAll('.roteiro-bloco')[4].textContent") == after
            assert page.evaluate("serialize().includes('ZXCVTEST')")
            assert not errors, errors
        finally:
            b.close()


def test_epub_selecao_extensa_mista_preserva_conteudo_e_aplica_formato():
    from tests.test_editor_v8_regressions import make_epub
    with sync_playwright() as pw:
        b = browser(pw)
        try:
            page = b.new_page(viewport={'width': 1440, 'height': 950})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            make_epub(page)
            before = page.evaluate('''() => {
              const lines=Array.from({length:120},(_,i)=>
                `<p>Parte ${i} <strong><span class="tamanho-fonte-${i%2?'15':'60'}pt">ação e café</span></strong> concluído</p>`);
              editor.innerHTML=lines.join('');
              const ps=editor.querySelectorAll('p');
              const r=document.createRange();r.setStart(ps[0],0);r.setEnd(ps[119],ps[119].childNodes.length);
              getSelection().removeAllRanges();getSelection().addRange(r);editor.focus();
              return {text:editor.textContent, selection:getSelection().toString()};
            }''')
            assert 'ação e café' in before['selection']
            page.locator('#seletorTamanhoFonteEditor').select_option('24')
            after = page.evaluate('''() => ({
              text:editor.textContent,selection:getSelection().toString(),
              sizes:[...editor.querySelectorAll('p')].map(p=>[...p.querySelectorAll('span')].map(e=>e.className)),
              strong:editor.querySelectorAll('p strong').length
            })''')
            assert after['text'] == before['text']
            assert after['selection'] == before['selection']
            assert after['strong'] == 120
            assert not page.evaluate("editor.querySelector('.tamanho-fonte-15pt, .tamanho-fonte-60pt') !== null")
            assert page.locator('#editorTexto .tamanho-fonte-24pt').count() >= 120
            assert not errors, errors
        finally:
            b.close()


def test_roteiro_colagem_alterando_bloco_anterior_invalida_cache_seriado():
    with sync_playwright() as pw:
        b = browser(pw)
        try:
            page, errors = new_editor(b, 'roteiro', 15)
            result = page.evaluate('''() => {
              const block=document.querySelectorAll('.roteiro-bloco')[4];
              const originalText=block.textContent;
              const savedBefore=serialize(); // preenche o cache de blocos
              const r=document.createRange();r.selectNodeContents(block);r.collapse(false);
              getSelection().removeAllRanges();getSelection().addRange(r);block.focus();
              block.appendChild(document.createTextNode(' COLAGEM ANTIGA'));
              block.dispatchEvent(new InputEvent('input', {inputType:'insertFromPaste',bubbles:true}));
              const savedAfter=serialize();
              return {hasBefore:savedBefore.includes('COLAGEM ANTIGA'),hasAfter:savedAfter.includes('COLAGEM ANTIGA'),
                blockText:block.textContent, originalText};
            }''')
            assert not result['hasBefore'] and result['hasAfter'], result
            assert 'COLAGEM ANTIGA' in result['blockText']
            page.wait_for_timeout(420)
            assert page.evaluate("serialize().includes('COLAGEM ANTIGA')")
            assert not errors, errors
        finally:
            b.close()


def test_roteiro_substituicao_de_selecao_entre_blocos_preserva_salvamento():
    with sync_playwright() as pw:
        b = browser(pw)
        try:
            page, errors = new_editor(b, 'roteiro', 40)
            initial_blocks = page.locator('.roteiro-bloco').count()
            selection = page.evaluate('''() => {
              const blocks=[...document.querySelectorAll('.roteiro-bloco')];
              const range=document.createRange();
              range.setStart(blocks[4].firstChild,25);
              range.setEnd(blocks[8].firstChild,25);
              getSelection().removeAllRanges();getSelection().addRange(range);
              blocks[4].focus();
              return getSelection().toString();
            }''')
            assert len(selection) > 80
            page.keyboard.insert_text('TROCADO')
            page.wait_for_timeout(460)
            status = page.evaluate('''() => ({
              visible:editor.textContent.includes('TROCADO'),
              saved:serialize().includes('TROCADO'),
              selectedInside:editor.contains(getSelection().anchorNode),
              orphan:editor.querySelectorAll('.roteiro-page-content > p').length,
              blockCount:editor.querySelectorAll('.roteiro-bloco').length
            })''')
            assert status['visible'] and status['saved'] and status['selectedInside'], status
            assert status['orphan'] == 0
            assert status['blockCount'] < initial_blocks
            assert not errors, errors
        finally:
            b.close()
