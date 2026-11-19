/* Assistente de geração por IA integrado aos editores. */
(() => {
  const editor = document.getElementById('editorTexto');
  const modal = document.getElementById('modalIAEditor');
  const promptEl = document.getElementById('iaEditorPrompt');
  const preview = document.getElementById('iaEditorPreview');
  const status = document.getElementById('iaEditorStatus');
  const btnGerar = document.getElementById('btnGerarIAEditor');
  const btnInserir = document.getElementById('btnInserirIAEditor');
  const modoInsercao = () => document.querySelector('input[name="iaEditorModoInsercao"]:checked')?.value || 'cursor';
  const abrir = document.getElementById('btnAbrirIAEditor');
  if (!editor || !modal || !abrir) return;
  const cfg = window.EDITOR_CONFIG || {};
  const isRoteiro = document.body.classList.contains('pagina-editor-roteiro') || Boolean(document.querySelector('.editor-roteiro'));
  let rangeSalva = null;
  let htmlGerado = '';

  function salvarRange() {
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount) return;
    const range = sel.getRangeAt(0);
    if (editor.contains(range.commonAncestorContainer)) rangeSalva = range.cloneRange();
  }
  function restaurarRange() {
    if (!rangeSalva) return false;
    const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(rangeSalva); return true;
  }
  function abrirModal() {
    salvarRange();
    modal.classList.remove('oculto');
    promptEl?.focus();
  }
  function fecharModal() { modal.classList.add('oculto'); }
  function contextoAtual() {
    const html = editor.innerHTML || '';
    return html.length > 24000 ? html.slice(-24000) : html;
  }
  function recursosAtual() {
    const dados = isRoteiro ? {
      personagens: cfg.catalogoPersonagens || [], locais: cfg.catalogoLocais || [], anotacoes: cfg.catalogoAnotacoes || [],
      tipoRoteiro: cfg.tipoRoteiroLabel || cfg.tipoRoteiro || '', titulo: cfg.roteiroTitulo || ''
    } : {
      personagens: cfg.catalogoPersonagens || [], locais: cfg.catalogoLocais || [], anotacoes: cfg.catalogoAnotacoes || []
    };
    return JSON.stringify(dados, null, 2).slice(0, 12000);
  }
  async function gerar() {
    const pedido = promptEl.value.trim();
    if (!pedido) { status.textContent = window.t?.('editor.ai_prompt_required') || 'Escreva um pedido.'; promptEl.focus(); return; }
    btnGerar.disabled = true; btnInserir.disabled = true; status.textContent = window.t?.('editor.ai_generating') || 'Gerando…';
    preview.innerHTML = '';
    try {
      const r = await fetch('/api/ia/editor', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
        modo: isRoteiro ? 'roteiro' : 'epub', prompt: pedido, idioma: cfg.idioma || 'pt-BR', contexto: contextoAtual(), recursos: recursosAtual()
      })});
      const d = await r.json().catch(() => ({}));
      if (!r.ok || !d.html) throw new Error(d.erro || window.t?.('editor.ai_generation_error') || 'Could not generate content.');
      htmlGerado = d.html;
      preview.innerHTML = htmlGerado;
      btnInserir.disabled = false;
      status.textContent = window.t?.('editor.ai_ready') || 'Conteúdo pronto para inserir.';
    } catch (e) { status.textContent = e.message || window.t?.('editor.ai_generation_error') || 'Could not generate content.'; }
    finally { btnGerar.disabled = false; }
  }
  function dispararInput() {
    editor.dispatchEvent(new InputEvent('input', { bubbles:true, inputType:'insertText', data:null }));
    editor.dispatchEvent(new Event('change', { bubbles:true }));
  }
  function fragmentoSeguro(html) {
    const tmp = document.createElement('div'); tmp.innerHTML = html;
    tmp.querySelectorAll('script,style,iframe,object,embed,form').forEach(x => x.remove());
    tmp.querySelectorAll('*').forEach(el => [...el.attributes].forEach(a => {
      if (a.name.toLowerCase().startsWith('on') || a.name.toLowerCase() === 'href' || a.name.toLowerCase() === 'src' || a.name.toLowerCase() === 'style') el.removeAttribute(a.name);
    }));
    return tmp;
  }
  function inserirEpub() {
    const fragRoot = fragmentoSeguro(htmlGerado);
    if (modoInsercao() === 'end') { editor.append(...fragRoot.childNodes); return; }
    if (!restaurarRange()) { editor.append(...fragRoot.childNodes); return; }
    const sel = window.getSelection(); const range = sel.getRangeAt(0);
    if (modoInsercao() === 'replace' && !range.collapsed) range.deleteContents();
    const frag = document.createDocumentFragment(); while (fragRoot.firstChild) frag.appendChild(fragRoot.firstChild);
    const last = frag.lastChild; range.insertNode(frag); sel.removeAllRanges(); const r2=document.createRange(); if(last){r2.setStartAfter(last);r2.collapse(true);sel.addRange(r2);} else {r2.selectNodeContents(editor);r2.collapse(false);sel.addRange(r2);}
  }
  function normalizarBlocosGerados(root) {
    const tipos = new Set(['scene_heading','action','character','dialogue','parenthetical','shot','transition','comment','music','neutral']);
    const candidatos = [...root.children].filter(el => el instanceof HTMLElement && el.classList.contains('roteiro-bloco'));
    return candidatos.map(el => {
      const bloco = document.createElement('div');
      bloco.className = 'roteiro-bloco';
      bloco.dataset.blockType = tipos.has(el.dataset.blockType) ? el.dataset.blockType : 'action';
      bloco.setAttribute('contenteditable', 'true');
      bloco.setAttribute('spellcheck', 'false');
      // Clone apenas o conteúdo permitido; nunca reutilize o nó do preview.
      const conteudo = el.cloneNode(true);
      conteudo.querySelectorAll('*').forEach(node => {
        [...node.attributes].forEach(attr => {
          if (!['class'].includes(attr.name) || !['strong','em','u','br'].includes(node.tagName.toLowerCase())) {
            node.removeAttribute(attr.name);
          }
        });
      });
      bloco.innerHTML = conteudo.innerHTML || '<br>';
      return bloco;
    }).filter(bloco => bloco.textContent.trim() || bloco.querySelector('br'));
  }

  function inserirRoteiro() {
    const root = fragmentoSeguro(htmlGerado);
    let blocos = normalizarBlocosGerados(root);
    if (!blocos.length) throw new Error(window.t?.('editor.ai_invalid_script_blocks') || 'AI did not return valid screenplay blocks. Please generate again.');

    // O editor de roteiro possui páginas e cada página possui seu próprio
    // .roteiro-page-content. Nunca inserimos diretamente em #editorRoteiro.
    if (typeof ensurePageStructure === 'function') ensurePageStructure();
    if (typeof invalidateStructureCaches === 'function') invalidateStructureCaches({ pages: false });

    const inserirDepoisDe = (alvo, novos) => {
      if (!alvo || !alvo.parentNode) return null;
      const parent = alvo.parentNode;
      let referencia = alvo;
      novos.forEach((bloco) => {
        parent.insertBefore(bloco, referencia.nextSibling);
        referencia = bloco;
        if (typeof markBlockDirty === 'function') markBlockDirty(bloco);
      });
      return referencia;
    };

    const modo = modoInsercao();
    let alvo = null;
    if (modo !== 'end') {
      restaurarRange();
      alvo = typeof getCurrentBlock === 'function' ? getCurrentBlock() : null;
      if (!alvo || !editor.contains(alvo)) {
        alvo = typeof getAllBlocks === 'function' ? getAllBlocks().at(-1) : editor.querySelector('.roteiro-bloco:last-of-type');
      }

      // Substituir seleção: apaga somente o conteúdo selecionado, preservando
      // o bloco atual para que a inserção aconteça exatamente naquele ponto lógico.
      const sel = window.getSelection();
      if (modo === 'replace' && sel?.rangeCount && !sel.getRangeAt(0).collapsed) {
        sel.getRangeAt(0).deleteContents();
      }
    }

    if (modo === 'end') {
      const paginas = typeof getPageContents === 'function' ? getPageContents() : [];
      const destino = paginas.at(-1) || editor;
      blocos.forEach((bloco) => {
        destino.appendChild(bloco);
        if (typeof markBlockDirty === 'function') markBlockDirty(bloco);
      });
    } else {
      const ultimo = inserirDepoisDe(alvo, blocos);
      if (!ultimo && editor) {
        const paginas = typeof getPageContents === 'function' ? getPageContents() : [];
        const destino = paginas.at(-1) || editor;
        blocos.forEach((bloco) => destino.appendChild(bloco));
      }
    }

    const primeiro = blocos[0];
    const ultimo = blocos[blocos.length - 1];
    if (ultimo) {
      if (typeof placeCaretAtEnd === 'function') placeCaretAtEnd(ultimo);
      else ultimo.focus();
    }

    // Deixa o pipeline normal do editor cuidar de paginação, numeração,
    // catálogo, visualização e autosave. O input é disparado depois que todos
    // os blocos já estão na árvore, evitando o estado intermediário que causava
    // blocos fora da página ou em ordem invertida.
    if (typeof invalidateStructureCaches === 'function') invalidateStructureCaches({ pages: false });
    if (typeof updateSceneSummary === 'function') updateSceneSummary();
    if (typeof refreshDialogueTimes === 'function') refreshDialogueTimes();
    if (ultimo) {
      editor.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: null }));
    }
    if (typeof scheduleRepagination === 'function') scheduleRepagination({ preserveSelection: true });
    primeiro?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }
  function inserir() {
    if (!htmlGerado) return;
    if (isRoteiro) inserirRoteiro(); else inserirEpub();
    dispararInput(); fecharModal();
    htmlGerado=''; preview.innerHTML=''; status.textContent='';
  }
  abrir.addEventListener('click', abrirModal);
  document.addEventListener('keydown', e => {
    const key = String(e.key || '').toLowerCase();
    if (e.ctrlKey && e.altKey && !e.shiftKey && !e.metaKey && key === 'g') {
      e.preventDefault();
      if (!e.repeat) abrir.click();
    }
  });
  modal.querySelectorAll('[data-fechar-ia-editor="true"]').forEach(el => el.addEventListener('click', fecharModal));
  btnGerar.addEventListener('click', gerar); btnInserir.addEventListener('click', inserir);
  promptEl.addEventListener('keydown', e => { if ((e.ctrlKey||e.metaKey) && e.key === 'Enter') { e.preventDefault(); gerar(); } });
})();
