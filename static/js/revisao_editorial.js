/* Revisão editorial: comentários, sugestões e versões fora do HTML exportável. */
(() => {
  'use strict';
  const panel = document.getElementById('painelRevisaoEditorial');
  const open = document.getElementById('btnAbrirRevisaoEditorial');
  const editor = document.getElementById('editorTexto');
  const cfg = window.EDITOR_CONFIG || {};
  if (!panel || !open || !editor || !cfg.slug || !cfg.numero) return;
  const script = !!document.querySelector('.painel-roteiro #editorTexto');
  const path = `/api/projetos/${encodeURIComponent(cfg.slug)}/editorial/${script ? 'roteiro' : 'livro'}/${encodeURIComponent(cfg.numero)}`;
  const $ = (id) => document.getElementById(id);
  const messages = {
    noSelection: 'editorial.no_selection', stale: 'editorial.stale', error: 'editorial.error',
    saved: 'editorial.saved', readOnly: 'editorial.read_only', applied: 'editorial.applied'
  };
  const english = document.documentElement.lang.toLowerCase().startsWith('en');
  const fallback = {
    'editorial.no_selection': english ? 'Select a passage in the editor.' : 'Selecione um trecho no editor.',
    'editorial.stale': english ? 'Passage changed or ambiguous. Nothing replaced.' : 'Trecho alterado ou ambíguo. Nada foi substituído.',
    'editorial.error': english ? 'Could not save.' : 'Não foi possível salvar.',
    'editorial.saved': english ? 'Review saved.' : 'Revisão salva.',
    'editorial.read_only': english ? 'Read-only tab.' : 'Esta aba está em modo de leitura.',
    'editorial.applied': english ? 'Suggestion applied.' : 'Sugestão aplicada.'
  };
  const tr = (key) => window.t?.(key) || fallback[key] || key;
  let items = [], versions = [], lastSelection = null, busy = false, currentTab = 'notes';
  let activeHighlights = [], highlightNames = [], highlightStyle = null, refreshTimer = null;
  const quoteBox = $('revTrechoSelecionado');
  function message(value, error = false) {
    const node = $('revMensagem'); node.textContent = value || '';
    node.classList.toggle('erro', error);
  }
  function editable() { return editor.isContentEditable; }
  function checkCanRestore() {
    const chip = $('statusAutosave');
    if (chip && (chip.classList.contains('status-salvando') || chip.classList.contains('status-erro'))) {
      throw new Error(tr('editorial.restore_pending'));
    }
  }

  async function api(payload, suffix = '') {
    const res = await fetch(path + suffix, {
      method: payload === null ? 'GET' : 'POST',
      cache: 'no-store', credentials: 'same-origin',
      headers: payload === null ? {} : {'Content-Type':'application/json'},
      ...(payload === null ? {} : {body:JSON.stringify(payload)})
    });
    const obj = await res.json().catch(() => ({}));
    if (!res.ok || obj.ok === false) throw new Error(obj.erro || tr('editorial.error'));
    return obj;
  }
  async function guarded(callback) {
    if (busy) return;
    busy = true;
    try { await callback(); }
    catch (e) { message(e.message || tr('editorial.error'), true); }
    finally { busy = false; }
  }
  async function load() {
    const data = await api(null);
    items = data.itens || [];
    versions = data.versoes || [];
    renderItems(); renderVersions(); renderHighlights();
  }
  function closePanel() {
    panel.classList.add('oculto'); panel.setAttribute('aria-hidden', 'true');
    open.setAttribute('aria-expanded', 'false');
    clearHighlights();
    open.focus({preventScroll:true});
  }
  open.setAttribute('aria-expanded', 'false');
  open.setAttribute('aria-controls', 'painelRevisaoEditorial');
  open.addEventListener('click', () => {
    if (!panel.classList.contains('oculto')) return closePanel();
    panel.classList.remove('oculto'); panel.setAttribute('aria-hidden', 'false');
    open.setAttribute('aria-expanded', 'true');
    guarded(load);
  });
  $('btnFecharRevisaoEditorial').addEventListener('click', closePanel);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !panel.classList.contains('oculto')) {
      const otherModal = document.querySelector('.modal:not(.oculto)');
      if (!otherModal) { event.stopPropagation(); closePanel(); }
    }
  }, true);

  function textNodes() {
    const nodes = [];
    const walker = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (node.parentElement?.closest('script,style,noscript')) continue;
      nodes.push(node);
    }
    return nodes;
  }
  function documentText(nodes) { return nodes.map(n => n.nodeValue).join(''); }
  function rangeAt(nodes, start, end) {
    const result = document.createRange();
    let offset = 0, began = false;
    for (const node of nodes) {
      const next = offset + node.nodeValue.length;
      if (!began && start >= offset && start <= next) {
        result.setStart(node, start - offset); began = true;
      }
      if (began && end >= offset && end <= next) {
        result.setEnd(node, end - offset); return result;
      }
      offset = next;
    }
    return null;
  }
  function blockOf(node) {
    const element = node?.nodeType === 1 ? node : node?.parentElement;
    return element?.closest?.('.roteiro-bloco, p, h1, h2, h3, li, blockquote') || null;
  }
  function captureSelection() {
    if (document.activeElement && panel.contains(document.activeElement)) return;
    const selection = window.getSelection();
    if (!selection?.rangeCount || selection.isCollapsed || !editor.contains(selection.anchorNode) ||
        !editor.contains(selection.focusNode)) return;
    const range = selection.getRangeAt(0);
    const trecho = range.toString();
    if (!trecho || trecho.length > 2000) {
      lastSelection = null; quoteBox.textContent = tr('editorial.no_selection'); return;
    }
    const pre = range.cloneRange(); pre.selectNodeContents(editor); pre.setEnd(range.startContainer, range.startOffset);
    const start = pre.toString().length;
    const all = documentText(textNodes());
    lastSelection = {trecho, inicio:start, prefixo:all.slice(Math.max(0,start - 80),start),
      sufixo:all.slice(start + trecho.length,start + trecho.length + 80),
      sameBlock: !!blockOf(range.startContainer) && blockOf(range.startContainer) === blockOf(range.endContainer)};
    quoteBox.textContent = trecho;
  }
  document.addEventListener('selectionchange', captureSelection);
  editor.addEventListener('keyup', captureSelection);
  editor.addEventListener('mouseup', captureSelection);

  function activeTab(which) {
    currentTab = which;
    const notes = which === 'notes';
    $('revPainelNotas').classList.toggle('oculto', !notes);
    $('revPainelNotas').hidden = !notes;
    $('revPainelVersoes').classList.toggle('oculto', notes);
    $('revPainelVersoes').hidden = notes;
    $('revAbaNotas').classList.toggle('ativo', notes);
    $('revAbaNotas').setAttribute('aria-selected', String(notes));
    $('revAbaVersoes').classList.toggle('ativo', !notes);
    $('revAbaVersoes').setAttribute('aria-selected', String(!notes));
  }
  $('revAbaNotas').addEventListener('click', () => activeTab('notes'));
  $('revAbaVersoes').addEventListener('click', () => activeTab('versions'));

  function node(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  // Cores sem personalização: azul para comentários e verde para sugestões.
  const highlightColors = Object.freeze({ comentario: '#60a5fa', sugestao: '#4ade80' });
  function itemColor(item) { return highlightColors[item?.tipo] || highlightColors.comentario; }
  const hoverTooltip = node('div', 'editorial-review-tooltip');
  hoverTooltip.setAttribute('role', 'tooltip');
  hoverTooltip.hidden = true;
  document.body.appendChild(hoverTooltip);

  function hideTooltip() { hoverTooltip.hidden = true; }
  function clearHighlights() {
    if (window.CSS?.highlights) for (const name of highlightNames) window.CSS.highlights.delete(name);
    highlightNames = []; activeHighlights = [];
    if (highlightStyle) highlightStyle.textContent = '';
    hideTooltip();
  }
  function textOffsetAt(container, offset) {
    try {
      if (!container || !editor.contains(container)) return null;
      const prefix = document.createRange();
      prefix.selectNodeContents(editor);
      prefix.setEnd(container, offset);
      return prefix.toString().length;
    } catch (_) { return null; }
  }
  function renderHighlights() {
    clearHighlights();
    if (panel.classList.contains('oculto')) return;
    if (!window.CSS?.highlights || typeof window.Highlight !== 'function') {
      message(tr('editorial.highlight_unsupported'), true);
      return;
    }
    if (!highlightStyle) {
      highlightStyle = document.createElement('style');
      highlightStyle.id = 'gutenbergEditorialHighlightStyles';
      document.head.appendChild(highlightStyle);
    }
    const rules = [];
    for (const item of items) {
      if (item.estado !== 'pendente') continue;
      const range = locate(item);
      if (!range || !range.toString()) continue;
      const safeId = String(item.id || '').replace(/[^a-zA-Z0-9_-]/g, '');
      if (!safeId) continue;
      const name = `gutenberg-review-${safeId}`;
      const color = itemColor(item);
      try {
        window.CSS.highlights.set(name, new window.Highlight(range));
        highlightNames.push(name);
        rules.push(`::highlight(${name}){background-color:${color}66;text-decoration:underline 2px ${color};text-underline-offset:2px}`);
        const start = textOffsetAt(range.startContainer, range.startOffset);
        if (start !== null) activeHighlights.push({item, start, end:start + range.toString().length, length:range.toString().length});
      } catch (_) { /* Um trecho inválido não deve interromper os demais destaques. */ }
    }
    highlightStyle.textContent = rules.join('\n');
  }
  function showTooltip(item, event) {
    if (!item || panel.classList.contains('oculto')) { hideTooltip(); return; }
    const type = tr(item.tipo === 'sugestao' ? 'editorial.suggestion' : 'editorial.comment');
    hoverTooltip.classList.toggle('editorial-review-tooltip--suggestion', item.tipo === 'sugestao');
    hoverTooltip.classList.toggle('editorial-review-tooltip--comment', item.tipo !== 'sugestao');
    hoverTooltip.replaceChildren();
    hoverTooltip.appendChild(node('strong','editorial-review-tooltip-title',type));
    if (item.nota) hoverTooltip.appendChild(node('p','editorial-review-tooltip-note',item.nota));
    if (item.tipo === 'sugestao' && item.substituicao) {
      const replacement = node('div','editorial-review-tooltip-replacement');
      replacement.appendChild(node('span','',tr('editorial.replacement')));
      replacement.appendChild(node('strong','',item.substituicao));
      hoverTooltip.appendChild(replacement);
    }
    hoverTooltip.hidden = false;
    const rect = hoverTooltip.getBoundingClientRect();
    const left = Math.max(10, Math.min(event.clientX + 14, window.innerWidth - rect.width - 10));
    const top = Math.max(10, Math.min(event.clientY + 18, window.innerHeight - rect.height - 10));
    hoverTooltip.style.left = `${left}px`;
    hoverTooltip.style.top = `${top}px`;
  }
  function itemAtPoint(event) {
    if (!activeHighlights.length || panel.classList.contains('oculto')) return null;
    let range = document.caretRangeFromPoint?.(event.clientX, event.clientY) || null;
    if (!range && document.caretPositionFromPoint) {
      const position = document.caretPositionFromPoint(event.clientX, event.clientY);
      if (position) { range = document.createRange(); range.setStart(position.offsetNode, position.offset); range.collapse(true); }
    }
    if (!range || !editor.contains(range.startContainer)) return null;
    const offset = textOffsetAt(range.startContainer, range.startOffset);
    if (offset === null) return null;
    const matches = activeHighlights.filter(entry => offset >= entry.start && offset < entry.end);
    matches.sort((a,b) => a.length - b.length);
    return matches[0]?.item || null;
  }
  editor.addEventListener('pointermove', (event) => showTooltip(itemAtPoint(event), event));
  editor.addEventListener('pointerleave', hideTooltip);
  window.addEventListener('scroll', hideTooltip, true);
  editor.addEventListener('input', () => {
    if (panel.classList.contains('oculto')) return;
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(renderHighlights, 160);
  });
  function button(label, handler, strong=false) {
    const btn = node('button', strong ? 'editorial-review-primary' : '', label);
    btn.type = 'button'; btn.addEventListener('click', () => guarded(handler));
    return btn;
  }
  function labelState(item) {
    return tr('editorial.' + ({pendente:'pending', aceito:'accepted', rejeitado:'rejected', resolvido:'resolved'}[item.estado] || 'pending'));
  }
  function renderItems() {
    const list = $('revListaNotas');
    const frag = document.createDocumentFragment();
    if (!items.length) frag.appendChild(node('p', 'editorial-review-muted', tr('editorial.no_items')));
    for (const item of [...items].reverse()) {
      const card = node('article', 'editorial-review-card');
      const meta = node('div','editorial-review-meta');
      meta.appendChild(node('strong','editorial-review-type',tr('editorial.'+(item.tipo === 'sugestao'?'suggestion':'comment'))));
      meta.appendChild(node('span','editorial-review-state',labelState(item)));
      card.appendChild(meta);
      card.appendChild(node('blockquote','',item.trecho));
      if (item.nota) card.appendChild(node('p','',item.nota));
      if (item.tipo === 'sugestao') card.appendChild(node('p','editorial-review-change',item.substituicao));
      const actions = node('div','editorial-review-card-actions');
      actions.appendChild(button(tr('editorial.locate'), async () => {
        const range = locate(item);
        if (!range) throw new Error(tr('editorial.stale'));
        editor.scrollIntoView({block:'nearest'});
        range.startContainer.parentElement?.scrollIntoView({block:'center',behavior:'smooth'});
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(range);
        message('');
      }));
      if (item.estado === 'pendente') {
        if (item.tipo === 'sugestao') {
          actions.appendChild(button(tr('editorial.accept'), () => accept(item), true));
          actions.appendChild(button(tr('editorial.reject'), () => change(item,'rejeitado')));
        } else actions.appendChild(button(tr('editorial.resolve'), () => change(item,'resolvido')));
      } else if (item.tipo === 'comentario') {
        actions.appendChild(button(tr('editorial.reopen'), () => change(item,'pendente')));
      }
      actions.appendChild(button(tr('editorial.delete'), async () => {
        if (!confirm(tr('editorial.delete_confirm'))) return;
        await api({acao:'apagar',id:item.id}); await load(); message(tr('editorial.saved'));
      }));
      card.appendChild(actions); frag.appendChild(card);
    }
    list.replaceChildren(frag);
  }
  async function change(item, estado) {
    await api({acao:'estado',id:item.id,estado}); await load(); message(tr('editorial.saved'));
  }
  function locate(item) {
    const nodes = textNodes();
    const text = documentText(nodes);
    const quote = item.trecho;
    if (!quote) return null;
    const candidates = [];
    let start = -1;
    while ((start = text.indexOf(quote, start + 1)) >= 0) {
      let score = 0;
      const before = text.slice(Math.max(0, start - (item.prefixo || '').length),start);
      const after = text.slice(start + quote.length,start + quote.length + (item.sufixo || '').length);
      if (item.prefixo) for (let j = 1; j <= before.length; j++) {
        if (before.slice(-j) === item.prefixo.slice(-j)) score = j;
        else break;
      }
      if (item.sufixo) for (let j = 1; j <= after.length; j++) {
        if (after.slice(0,j) === item.sufixo.slice(0,j)) score += 1;
        else break;
      }
      candidates.push({start, score, distance:Math.abs(start-(item.inicio||0))});
      if (candidates.length > 100) return null;
    }
    if (!candidates.length) return null;
    candidates.sort((a,b) => b.score-a.score || a.distance-b.distance);
    // Não alterar automaticamente passagens repetidas sem contexto distintivo.
    if (candidates.length > 1 && candidates[0].score === candidates[1].score) return null;
    return rangeAt(nodes,candidates[0].start,candidates[0].start+quote.length);
  }
  async function accept(item) {
    if (!editable()) throw new Error(tr('editorial.read_only'));
    const range = locate(item);
    if (!range || range.toString() !== item.trecho) throw new Error(tr('editorial.stale'));
    if (!blockOf(range.startContainer) || blockOf(range.startContainer) !== blockOf(range.endContainer)) {
      throw new Error(tr('editorial.single_block'));
    }
    editor.focus({preventScroll:true});
    const sel = getSelection(); sel.removeAllRanges(); sel.addRange(range);
    // execCommand preserva a pilha nativa de desfazer e emite o input para os
    // editores acionarem paginação, autosave e invalidação de cache normais.
    if (!document.execCommand('insertText', false, item.substituicao)) {
      throw new Error(tr('editorial.error'));
    }
    await api({acao:'estado',id:item.id,estado:'aceito'});
    await load(); message(tr('editorial.applied'));
  }
  async function create(kind) {
    if (!editable()) throw new Error(tr('editorial.read_only'));
    if (!lastSelection || !lastSelection.trecho || lastSelection.trecho.length > 2000) {
      throw new Error(tr('editorial.selection_limit'));
    }
    if (kind === 'sugestao' && !lastSelection.sameBlock) {
      throw new Error(tr('editorial.single_block'));
    }
    const data = {...lastSelection, tipo:kind,
      nota:$('revNota').value, substituicao:$('revSubstituicao').value};
    await api({acao:'criar', ...data});
    $('revNota').value=''; $('revSubstituicao').value='';
    await load(); message(tr('editorial.saved'));
  }
  $('btnRevComentar').addEventListener('click', () => guarded(() => create('comentario')));
  $('btnRevSugerir').addEventListener('click', () => guarded(() => create('sugestao')));

  function renderVersions() {
    const list = $('revListaVersoes');
    const frag = document.createDocumentFragment();
    if (!versions.length) frag.appendChild(node('p','editorial-review-muted',tr('editorial.no_versions')));
    for (const version of [...versions].reverse()) {
      const card = node('article','editorial-review-card');
      const date = version.criado_em ? new Date(version.criado_em).toLocaleString() : '';
      card.appendChild(node('strong','editorial-review-type',version.rotulo || date));
      card.appendChild(node('p','editorial-review-muted',date));
      const actions = node('div','editorial-review-card-actions');
      actions.appendChild(button(tr('editorial.compare'), async () => {
        const response = await api(null,`/versoes/${encodeURIComponent(version.id)}?comparar=1`);
        const diff = $('revComparacao'); diff.replaceChildren();
        const parts = response.comparacao || [];
        for (const part of parts) {
          const el = node(part.tipo === 'adicionado' ? 'ins' : part.tipo === 'removido' ? 'del' : 'span', '', part.texto);
          diff.appendChild(el);
        }
        if (!diff.childNodes.length) diff.appendChild(node('span','',tr('editorial.diff_same')));
        diff.classList.remove('oculto'); diff.scrollIntoView({block:'nearest'});
      }));
      actions.appendChild(button(tr('editorial.preview'), async () => {
        const result = await api(null,`/versoes/${encodeURIComponent(version.id)}`);
        const el = $('revComparacao');
        // Pré-visualização exclusivamente textual; não interpretar HTML salvo,
        // pois documentos importados podem conter atributos/eventos externos.
        el.textContent = result.versao?.texto || '';
        el.classList.remove('oculto');
        el.scrollIntoView({block:'nearest'});
      }));
      actions.appendChild(button(tr('editorial.restore'), async () => {
        if (!editable()) throw new Error(tr('editorial.read_only'));
        checkCanRestore();
        if (!confirm(tr('editorial.restore_confirm'))) return;
        const result = await api(null,`/versoes/${encodeURIComponent(version.id)}`);
        const html = result.versao?.html;
        if (typeof html !== 'string') throw new Error(tr('editorial.error'));
        // Garante ponto de retorno do último conteúdo efetivamente persistido.
        await api({acao:'versao',rotulo:english ? 'Before restoration' : 'Antes da restauração'});
        checkCanRestore();
        editor.innerHTML = html;
        const title = $('campoTituloCapitulo');
        if (title && result.versao.titulo && title.value !== result.versao.titulo) {
          title.value = result.versao.titulo;
          title.dispatchEvent(new Event('input',{bubbles:true}));
        }
        // Avisar os controladores existentes — jamais chamar a exportação.
        editor.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertReplacementText'}));
        lastSelection = null; quoteBox.textContent=tr('editorial.no_selection');
        $('revComparacao').classList.add('oculto');
        await load(); message(tr('editorial.restore_done'));
      }));
      actions.appendChild(button(tr('editorial.delete'), async () => {
        if (!confirm(tr('editorial.version_delete_confirm'))) return;
        await api({acao:'apagar_versao',id:version.id}); await load(); message(tr('editorial.saved'));
      }));
      card.appendChild(actions); frag.appendChild(card);
    }
    list.replaceChildren(frag);
  }
  $('btnRevCriarVersao').addEventListener('click', () => guarded(async () => {
    checkCanRestore();
    await api({acao:'versao',rotulo:$('revNomeVersao').value});
    $('revNomeVersao').value=''; await load(); message(tr('editorial.saved'));
  }));
  // API limitada para testes/integrações; não altera o modo de edição normal.
  window.GutenbergRevisaoEditorial = {load, locate, renderHighlights, get state(){ return {items,versions}; }};
})();
