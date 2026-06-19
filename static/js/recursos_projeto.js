/** Recursos criativos por projeto: informações, fluxo, personagens, lugares e anotações. */
(function(){
  const slug = window.PROJETO_SLUG || '';
  let state = normalizeState(window.PROJETO_RECURSOS_INITIAL || {});
  let activeTab = 'informacoes';
  let activeInfoId = state.informacoes[0]?.id || null;
  let infoSaveTimer = null;
  let flowSaveTimer = null;
  let selectedHandle = null;
  let dragState = null;
  let resizeState = null;
  let flowPanState = null;
  let flowSpacePanActive = false;
  let imageCatalogoAtual = '';
  let detalheCatalogoAtual = null;
  let lastInfoRange = null;

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const statusEl = $('#recursosStatus');
  function tr(key, vars = {}, fallback = '') {
    const value = typeof window.t === 'function' ? window.t(key, vars) : key;
    return value && value !== key ? value : (fallback || key);
  }

  function uid(prefix){ return `${prefix}_${Math.random().toString(16).slice(2)}${Date.now().toString(16).slice(-5)}`; }
  function escapeHtml(value){ return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
  function stripHtml(value){ const div = document.createElement('div'); div.innerHTML = String(value || ''); return (div.textContent || '').replace(/\s+/g,' ').trim(); }
  function setStatus(text, tone = ''){
    if (!statusEl) return;
    statusEl.textContent = text || tr('resources.ready', {}, 'Pronto');
    statusEl.dataset.tone = tone;
  }
  function normalizeState(data){
    const informacoes = Array.isArray(data.informacoes) && data.informacoes.length ? data.informacoes : [{id: uid('info'), titulo: tr('resources.default_page_title', {}, 'Página inicial'), html: '<p></p>'}];
    return {
      informacoes: informacoes.map(p => ({id: String(p.id || uid('info')), titulo: String(p.titulo || tr('resources.untitled', {}, 'Sem título')), html: String(p.html || '<p></p>'), data_atualizacao: p.data_atualizacao || ''})),
      fluxo: {nodes: Array.isArray(data.fluxo?.nodes) ? data.fluxo.nodes : [], edges: Array.isArray(data.fluxo?.edges) ? data.fluxo.edges : []},
      personagens: Array.isArray(data.personagens) ? data.personagens : [],
      lugares: Array.isArray(data.lugares) ? data.lugares : [],
      anotacoes: Array.isArray(data.anotacoes) ? data.anotacoes : [],
      personagens_projeto: Array.isArray(data.personagens_projeto) ? data.personagens_projeto : [],
      lugares_projeto: Array.isArray(data.lugares_projeto) ? data.lugares_projeto : [],
      anotacoes_projeto: Array.isArray(data.anotacoes_projeto) ? data.anotacoes_projeto : []
    };
  }
  function absorbServer(data){
    state = normalizeState(data || state);
    if (!state.informacoes.some(p => p.id === activeInfoId)) activeInfoId = state.informacoes[0]?.id || null;
    renderInfoList();
    loadActiveInfo();
    renderFlow();
    renderCatalogs();
  }
  async function postJSON(url, payload){
    const resp = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload || {})});
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || data.ok === false) throw new Error(data.erro || tr('editor.save_failed', {}, 'Não foi possível salvar.'));
    return data;
  }
  function switchTab(tab){
    if (tab !== 'fluxo') resetFlowCanvasPan();
    activeTab = tab;
    $$('[data-recursos-tab]').forEach(btn => btn.classList.toggle('ativo', btn.dataset.recursosTab === tab));
    $$('[data-recursos-panel]').forEach(panel => panel.classList.toggle('ativo', panel.dataset.recursosPanel === tab));
    if (tab === 'fluxo') requestAnimationFrame(renderFlowLines);
  }

  $$('[data-recursos-tab]').forEach(btn => btn.addEventListener('click', () => switchTab(btn.dataset.recursosTab)));
  $$('[data-recursos-tab-target]').forEach(btn => btn.addEventListener('click', () => switchTab(btn.dataset.recursosTabTarget)));

  function currentInfo(){ return state.informacoes.find(p => p.id === activeInfoId) || state.informacoes[0]; }
  function renderInfoList(){
    const list = $('#listaPaginasInfo');
    if (!list) return;
    list.innerHTML = '';
    state.informacoes.forEach((page, idx) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `info-page-item${page.id === activeInfoId ? ' ativo' : ''}`;
      const titulo = page.titulo || `${tr('resources.pages', {}, 'Página')} ${idx + 1}`;
      btn.title = titulo;
      btn.innerHTML = `<strong>${escapeHtml(titulo)}</strong>`;
      btn.addEventListener('click', () => { saveCurrentInfoToState(); activeInfoId = page.id; renderInfoList(); loadActiveInfo(); });
      list.appendChild(btn);
    });
  }
  function loadActiveInfo(){
    const page = currentInfo();
    const title = $('#tituloPaginaInfo');
    const editor = $('#editorInfoPagina');
    if (!page || !title || !editor) return;
    title.value = page.titulo || '';
    editor.innerHTML = page.html || '<p></p>';
    lastInfoRange = null;
  }
  function saveCurrentInfoToState(){
    const page = currentInfo();
    if (!page) return;
    const title = $('#tituloPaginaInfo');
    const editor = $('#editorInfoPagina');
    page.titulo = (title?.value || '').trim() || tr('resources.untitled', {}, 'Sem título');
    page.html = editor?.innerHTML || '<p></p>';
    page.data_atualizacao = new Date().toISOString();
  }
  function scheduleInfoSave(){
    saveCurrentInfoToState();
    renderInfoList();
    clearTimeout(infoSaveTimer);
    setStatus(tr('resources.info_saving', {}, 'Salvando informações...'));
    infoSaveTimer = setTimeout(async () => {
      try {
        await postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/informacoes`, {informacoes: state.informacoes});
        setStatus(tr('resources.info_saved', {}, 'Informações salvas'));
      } catch (err) { setStatus(err.message, 'erro'); }
    }, 620);
  }
  $('#btnNovaPaginaInfo')?.addEventListener('click', () => {
    saveCurrentInfoToState();
    const page = {id: uid('info'), titulo: tr('resources.new_page', {}, 'Nova página'), html: tr('resources.new_page_html', {}, '<h2>Nova página</h2><p></p>'), data_atualizacao: new Date().toISOString()};
    state.informacoes.push(page);
    activeInfoId = page.id;
    renderInfoList(); loadActiveInfo(); scheduleInfoSave();
  });
  $('#btnExcluirPaginaInfo')?.addEventListener('click', () => {
    if (state.informacoes.length <= 1) { alert(tr('resources.keep_one_page', {}, 'Mantenha pelo menos uma página.')); return; }
    const page = currentInfo();
    if (!page || !confirm(tr('resources.delete_page_confirm', {title: page.titulo}, `Excluir a página "${page.titulo}"?`))) return;
    state.informacoes = state.informacoes.filter(p => p.id !== page.id);
    activeInfoId = state.informacoes[0]?.id || null;
    renderInfoList(); loadActiveInfo(); scheduleInfoSave();
  });
  $('#tituloPaginaInfo')?.addEventListener('input', scheduleInfoSave);
  $('#editorInfoPagina')?.addEventListener('input', scheduleInfoSave);
  $('#btnInserirImagemInfo')?.addEventListener('click', () => $('#inputImagemInfo')?.click());
  $('#inputImagemInfo')?.addEventListener('change', async (ev) => {
    const file = ev.target.files?.[0];
    ev.target.value = '';
    if (!file) return;
    const dataUrl = await fileToDataUrl(file);
    const editor = $('#editorInfoPagina');
    editor?.focus();
    document.execCommand('insertImage', false, dataUrl);
    scheduleInfoSave();
  });

  function fileToDataUrl(file){
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(new Error(tr('resources.image_read_failed', {}, 'Falha ao ler imagem.')));
      reader.readAsDataURL(file);
    });
  }


  async function flushResourceAutosaves(){
    clearTimeout(infoSaveTimer);
    clearTimeout(flowSaveTimer);
    saveCurrentInfoToState();
    setStatus(tr('resources.saving', {}, 'Salvando...'));
    await postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/informacoes`, {informacoes: state.informacoes});
    await postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/fluxo`, {fluxo: state.fluxo});
  }

  async function salvarBlobComJanelaDoNavegador(blob, nomeArquivo){
    if (typeof window.showSaveFilePicker !== 'function' || !window.isSecureContext) return false;
    try {
      const handle = await window.showSaveFilePicker({
        id: 'gutenberg-recursos',
        suggestedName: nomeArquivo,
        types: [{ description: 'Gutenberg Resources', accept: { 'application/octet-stream': ['.gutr'] } }],
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      return true;
    } catch (err) {
      if (err && (err.name === 'AbortError' || err.name === 'SecurityError')) return 'cancelado';
      console.warn('Falha ao salvar .gutr com showSaveFilePicker:', err);
      return false;
    }
  }

  async function baixarBlobComFallback(blob, nomeArquivo){
    const picker = await salvarBlobComJanelaDoNavegador(blob, nomeArquivo);
    if (picker === true) return {ok:true};
    if (picker === 'cancelado') return {ok:false, cancelado:true};
    const dl = document.createElement('a');
    dl.href = URL.createObjectURL(blob);
    dl.download = nomeArquivo;
    document.body.appendChild(dl);
    dl.click();
    dl.remove();
    URL.revokeObjectURL(dl.href);
    return {ok:true};
  }

  async function salvarRecursosGutr(){
    try {
      await flushResourceAutosaves();
      setStatus(tr('resources.export_preparing', {}, 'Preparando arquivo de recursos...'));
      const isDesktopSave = Boolean(window.pywebview?.api?.saveExportedFile);
      const url = `/projetos/${encodeURIComponent(slug)}/salvar-recursos${isDesktopSave ? '?desktop_save=1' : ''}`;
      const resp = await fetch(url);
      if (!resp.ok) {
        let mensagem = tr('resources.export_error', {}, 'Não foi possível salvar os recursos.');
        try { const erro = await resp.json(); mensagem = erro.erro || erro.mensagem || mensagem; } catch (_) {}
        throw new Error(mensagem);
      }
      if (isDesktopSave) {
        const dados = await resp.json();
        if (!dados?.ok || !dados?.arquivo) throw new Error(dados?.erro || tr('resources.export_error', {}, 'Não foi possível salvar os recursos.'));
        const resultado = await window.pywebview.api.saveExportedFile(dados.arquivo, dados.nome, dados.pasta_inicial);
        if (!resultado?.ok) {
          if (resultado?.cancelado) { setStatus(tr('js.export_cancelled', {}, 'Exportação cancelada')); return; }
          throw new Error(resultado?.erro || tr('resources.export_error', {}, 'Não foi possível salvar os recursos.'));
        }
      } else {
        const blob = await resp.blob();
        const dispo = resp.headers.get('Content-Disposition') || '';
        const m = dispo.match(/filename\*?=(?:UTF-8''|\")?([^";]+)/i);
        const nomeArquivo = m ? decodeURIComponent(m[1].replace(/"/g,'')) : `${slug || 'projeto'}_recursos.gutr`;
        const download = await baixarBlobComFallback(blob, nomeArquivo);
        if (download?.cancelado) { setStatus(tr('js.export_cancelled', {}, 'Exportação cancelada')); return; }
      }
      setStatus(tr('resources.export_success', {}, 'Recursos salvos em .gutr'));
    } catch (err) {
      setStatus(err.message || tr('resources.export_error', {}, 'Não foi possível salvar os recursos.'), 'erro');
      alert(err.message || tr('resources.export_error', {}, 'Não foi possível salvar os recursos.'));
    }
  }

  async function importarRecursosGutrViaUpload(arquivo){
    const fd = new FormData();
    fd.append('arquivo', arquivo);
    setStatus(tr('resources.importing', {}, 'Importando recursos...'));
    const resposta = await fetch(`/projetos/${encodeURIComponent(slug)}/importar-recursos`, {method:'POST', body:fd});
    const dados = await resposta.json().catch(() => ({}));
    if (!resposta.ok || dados.ok === false) throw new Error(dados.erro || tr('resources.import_error', {}, 'Não foi possível importar recursos.'));
    absorbServer(dados);
    setStatus(dados.mensagem || tr('resources.import_success', {}, 'Recursos importados'));
  }

  async function importarRecursosGutrViaDesktop(){
    const seletor = await window.pywebview?.api?.openGutrFileDialog?.();
    if (!seletor?.ok) {
      if (seletor?.erro && !seletor?.cancelado) throw new Error(seletor.erro);
      return false;
    }
    setStatus(tr('resources.importing', {}, 'Importando recursos...'));
    const resposta = await fetch(`/projetos/${encodeURIComponent(slug)}/importar-recursos-desktop`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({caminho: seletor.caminho}),
    });
    const dados = await resposta.json().catch(() => ({}));
    if (!resposta.ok || dados.ok === false) throw new Error(dados.erro || tr('resources.import_error', {}, 'Não foi possível importar recursos.'));
    absorbServer(dados);
    setStatus(dados.mensagem || tr('resources.import_success', {}, 'Recursos importados'));
    return true;
  }

  async function iniciarImportacaoRecursosGutr(){
    try {
      if (window.pywebview?.api?.openGutrFileDialog) {
        await importarRecursosGutrViaDesktop();
        return;
      }
      const input = $('#inputGutrImportacao');
      if (!input) throw new Error(tr('resources.import_error', {}, 'Não foi possível importar recursos.'));
      input.value = '';
      input.click();
    } catch (err) {
      setStatus(err.message || tr('resources.import_error', {}, 'Não foi possível importar recursos.'), 'erro');
      alert(err.message || tr('resources.import_error', {}, 'Não foi possível importar recursos.'));
    }
  }


  function getInfoEditor(){ return $('#editorInfoPagina'); }
  function getInfoSelectionRange(){
    const editor = getInfoEditor();
    const sel = window.getSelection();
    if (!editor || !sel || !sel.rangeCount) return null;
    const range = sel.getRangeAt(0);
    return editor.contains(range.startContainer) && editor.contains(range.endContainer) ? range : null;
  }
  function saveInfoRange(){
    const range = getInfoSelectionRange();
    if (range) lastInfoRange = range.cloneRange();
  }
  function restoreInfoRange(){
    const editor = getInfoEditor();
    if (!editor || !lastInfoRange) return false;
    try {
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(lastInfoRange);
      editor.focus({preventScroll:true});
      return true;
    } catch (_) { return false; }
  }
  function applyInfoFormat({command = '', block = ''} = {}){
    const editor = getInfoEditor();
    if (!editor) return;
    restoreInfoRange();
    editor.focus({preventScroll:true});
    if (block) document.execCommand('formatBlock', false, block);
    if (command) document.execCommand(command, false, null);
    saveInfoRange();
    scheduleInfoSave();
  }
  function bindInfoToolbar(){
    $$('[data-info-comando], [data-info-bloco]').forEach(btn => {
      btn.addEventListener('mousedown', (ev) => { ev.preventDefault(); restoreInfoRange(); });
      btn.addEventListener('click', () => applyInfoFormat({command: btn.dataset.infoComando || '', block: btn.dataset.infoBloco || ''}));
    });
    const editor = getInfoEditor();
    if (!editor) return;
    editor.addEventListener('keyup', saveInfoRange);
    editor.addEventListener('mouseup', saveInfoRange);
    editor.addEventListener('focus', saveInfoRange);
    document.addEventListener('selectionchange', () => {
      const range = getInfoSelectionRange();
      if (range) lastInfoRange = range.cloneRange();
    });
  }

  function nodeById(id){ return state.fluxo.nodes.find(n => n.id === id); }
  function isSpacePanKey(ev){
    return ev?.code === 'Space' || ev?.key === ' ' || ev?.key === 'Spacebar';
  }
  function isEditableFlowTarget(target){
    const el = target instanceof Element ? target : target?.parentElement;
    return !!el?.closest('input,textarea,select,button,[contenteditable="true"],[contenteditable=""]');
  }
  function updateFlowCanvasPanClass(){
    const wrap = $('#fluxoCanvasWrap');
    if (!wrap) return;
    wrap.classList.toggle('space-pan-ready', flowSpacePanActive && activeTab === 'fluxo');
    wrap.classList.toggle('space-panning', !!flowPanState);
  }
  function endFlowCanvasPan(){
    if (flowPanState?.wrap && flowPanState.pointerId != null) {
      try { flowPanState.wrap.releasePointerCapture(flowPanState.pointerId); } catch (_) {}
    }
    flowPanState = null;
    updateFlowCanvasPanClass();
  }
  function resetFlowCanvasPan(){
    flowSpacePanActive = false;
    endFlowCanvasPan();
  }
  function beginFlowCanvasPan(ev){
    const wrap = $('#fluxoCanvasWrap');
    if (!wrap || activeTab !== 'fluxo' || !flowSpacePanActive || ev.button !== 0 || isEditableFlowTarget(ev.target)) return;
    ev.preventDefault();
    ev.stopPropagation();
    if (dragState) dragState = null;
    if (resizeState) resizeState = null;
    flowPanState = {
      wrap,
      pointerId: ev.pointerId,
      startX: ev.clientX,
      startY: ev.clientY,
      startLeft: wrap.scrollLeft,
      startTop: wrap.scrollTop,
    };
    wrap.setPointerCapture?.(ev.pointerId);
    updateFlowCanvasPanClass();
  }
  function moveFlowCanvasPan(ev){
    if (!flowPanState || ev.pointerId !== flowPanState.pointerId) return;
    ev.preventDefault();
    ev.stopPropagation();
    const dx = ev.clientX - flowPanState.startX;
    const dy = ev.clientY - flowPanState.startY;
    flowPanState.wrap.scrollLeft = flowPanState.startLeft - dx;
    flowPanState.wrap.scrollTop = flowPanState.startTop - dy;
  }
  function setupFlowCanvasPanning(){
    const wrap = $('#fluxoCanvasWrap');
    if (!wrap) return;
    wrap.addEventListener('pointerdown', beginFlowCanvasPan, true);
    wrap.addEventListener('pointermove', moveFlowCanvasPan, true);
    wrap.addEventListener('pointerup', endFlowCanvasPan, true);
    wrap.addEventListener('pointercancel', endFlowCanvasPan, true);
    document.addEventListener('keydown', (ev) => {
      if (activeTab !== 'fluxo' || !isSpacePanKey(ev) || isEditableFlowTarget(ev.target)) return;
      ev.preventDefault();
      flowSpacePanActive = true;
      updateFlowCanvasPanClass();
    });
    document.addEventListener('keyup', (ev) => {
      if (!isSpacePanKey(ev)) return;
      flowSpacePanActive = false;
      endFlowCanvasPan();
    });
    window.addEventListener('blur', resetFlowCanvasPan);
  }
  function createNodeElement(node){
    const el = document.createElement('article');
    el.className = 'fluxo-node';
    el.dataset.nodeId = node.id;
    el.style.left = `${Number(node.x || 0)}px`;
    el.style.top = `${Number(node.y || 0)}px`;
    el.style.width = `${Number(node.width || 240)}px`;
    el.style.height = `${Number(node.height || 150)}px`;
    el.innerHTML = `
      <button type="button" class="fluxo-node-delete" title="${tr('common.delete', {}, 'Excluir')}">×</button>
      <input class="fluxo-node-title" value="${escapeHtml(node.titulo || tr('resources.new_block', {}, 'Novo bloco'))}" maxlength="120">
      <textarea class="fluxo-node-text" maxlength="4000">${escapeHtml(node.texto || '')}</textarea>
      <span class="flow-handle" data-side="top" title="${tr('resources.connect_top', {}, 'Ligar pelo topo')}"></span>
      <span class="flow-handle" data-side="right" title="${tr('resources.connect_right', {}, 'Ligar pela direita')}"></span>
      <span class="flow-handle" data-side="bottom" title="${tr('resources.connect_bottom', {}, 'Ligar pela base')}"></span>
      <span class="flow-handle" data-side="left" title="${tr('resources.connect_left', {}, 'Ligar pela esquerda')}"></span>
      ${['n','e','s','w','ne','nw','se','sw'].map(dir => `<span class="fluxo-resize-handle" data-resize="${dir}" title="${tr('resources.resize', {}, 'Redimensionar')}"></span>`).join('')}`;
    el.querySelector('.fluxo-node-delete')?.addEventListener('click', (ev) => { ev.stopPropagation(); deleteNode(node.id); });
    el.querySelector('.fluxo-node-title')?.addEventListener('input', (ev) => { node.titulo = ev.target.value; scheduleFlowSave(); });
    el.querySelector('.fluxo-node-text')?.addEventListener('input', (ev) => { node.texto = ev.target.value; scheduleFlowSave(); renderFlowLines(); });
    el.querySelectorAll('.flow-handle').forEach(handle => handle.addEventListener('click', (ev) => { ev.preventDefault(); ev.stopPropagation(); onHandleClick(node.id, handle.dataset.side, handle, ev); }));
    el.querySelectorAll('.fluxo-resize-handle').forEach(handle => handle.addEventListener('pointerdown', (ev) => beginNodeResize(ev, node, el, handle.dataset.resize || 'se')));
    el.addEventListener('pointerdown', (ev) => {
      if (ev.button !== 0 || ev.target.closest('input,textarea,button,.flow-handle,.fluxo-resize-handle')) return;
      dragState = {id: node.id, startX: ev.clientX, startY: ev.clientY, origX: Number(node.x || 0), origY: Number(node.y || 0)};
      el.setPointerCapture(ev.pointerId);
      el.classList.add('selecionado');
    });
    el.addEventListener('pointermove', (ev) => {
      if (resizeState?.id === node.id) {
        applyNodeResize(ev, node, el);
        return;
      }
      if (!dragState || dragState.id !== node.id) return;
      node.x = Math.max(0, dragState.origX + ev.clientX - dragState.startX);
      node.y = Math.max(0, dragState.origY + ev.clientY - dragState.startY);
      el.style.left = `${node.x}px`; el.style.top = `${node.y}px`;
      renderFlowLines();
    });
    const finalizarPointer = () => {
      if (resizeState?.id === node.id) {
        normalizeNodeDimensionsFromElement(node, el);
        resizeState = null;
        el.classList.remove('redimensionando');
        scheduleFlowSave();
        renderFlowLines();
      }
      if (dragState?.id === node.id) { dragState = null; el.classList.remove('selecionado'); scheduleFlowSave(); }
    };
    el.addEventListener('pointerup', finalizarPointer);
    el.addEventListener('pointercancel', finalizarPointer);
    return el;
  }
  function normalizeNodeDimensionsFromElement(node, el){
    node.width = Math.max(170, Math.round(el.offsetWidth || Number(node.width || 240)));
    node.height = Math.max(130, Math.round(el.offsetHeight || Number(node.height || 150)));
  }
  function beginNodeResize(ev, node, el, dir){
    if (ev.button !== 0) return;
    ev.preventDefault();
    ev.stopPropagation();
    normalizeNodeDimensionsFromElement(node, el);
    resizeState = {
      id: node.id,
      dir,
      startX: ev.clientX,
      startY: ev.clientY,
      origX: Number(node.x || 0),
      origY: Number(node.y || 0),
      startWidth: Number(node.width || el.offsetWidth || 240),
      startHeight: Number(node.height || el.offsetHeight || 150),
    };
    el.setPointerCapture(ev.pointerId);
    el.classList.add('redimensionando');
  }
  function applyNodeResize(ev, node, el){
    if (!resizeState || resizeState.id !== node.id) return;
    const minW = 170, minH = 130, maxW = 760, maxH = 620;
    const dx = ev.clientX - resizeState.startX;
    const dy = ev.clientY - resizeState.startY;
    const dir = resizeState.dir || 'se';
    let x = resizeState.origX;
    let y = resizeState.origY;
    let width = resizeState.startWidth;
    let height = resizeState.startHeight;
    if (dir.includes('e')) width = resizeState.startWidth + dx;
    if (dir.includes('s')) height = resizeState.startHeight + dy;
    if (dir.includes('w')) {
      width = resizeState.startWidth - dx;
      x = resizeState.origX + dx;
      if (width < minW) { x = resizeState.origX + resizeState.startWidth - minW; width = minW; }
    }
    if (dir.includes('n')) {
      height = resizeState.startHeight - dy;
      y = resizeState.origY + dy;
      if (height < minH) { y = resizeState.origY + resizeState.startHeight - minH; height = minH; }
    }
    width = Math.max(minW, Math.min(maxW, width));
    height = Math.max(minH, Math.min(maxH, height));
    x = Math.max(0, x);
    y = Math.max(0, y);
    node.x = Math.round(x);
    node.y = Math.round(y);
    node.width = Math.round(width);
    node.height = Math.round(height);
    el.style.left = `${node.x}px`;
    el.style.top = `${node.y}px`;
    el.style.width = `${node.width}px`;
    el.style.height = `${node.height}px`;
    renderFlowLines();
  }
  function renderFlow(){
    const wrap = $('#fluxoNodes');
    if (!wrap) return;
    wrap.innerHTML = '';
    state.fluxo.nodes.forEach(node => wrap.appendChild(createNodeElement(node)));
    requestAnimationFrame(renderFlowLines);
  }
  function sidePoint(node, side){
    const x = Number(node.x || 0), y = Number(node.y || 0), w = Number(node.width || 240), h = Number(node.height || 150);
    if (side === 'top') return {x: x + w/2, y};
    if (side === 'bottom') return {x: x + w/2, y: y + h};
    if (side === 'left') return {x, y: y + h/2};
    return {x: x + w, y: y + h/2};
  }
  function renderFlowLines(){
    const svg = $('#fluxoSvg');
    if (!svg) return;
    svg.innerHTML = '';
    state.fluxo.nodes.forEach(node => {
      const el = $(`[data-node-id="${CSS.escape(node.id)}"]`);
      if (el) { node.width = el.offsetWidth || node.width || 240; node.height = el.offsetHeight || node.height || 150; }
    });
    state.fluxo.edges.forEach(edge => {
      const a = nodeById(edge.from), b = nodeById(edge.to);
      if (!a || !b) return;
      const p1 = sidePoint(a, edge.fromSide || 'right');
      const p2 = sidePoint(b, edge.toSide || 'left');
      const dx = Math.max(70, Math.abs(p2.x - p1.x) * .45);
      const c1 = (edge.fromSide === 'left') ? {x:p1.x-dx,y:p1.y} : (edge.fromSide === 'right') ? {x:p1.x+dx,y:p1.y} : {x:p1.x,y:p1.y + (edge.fromSide === 'top' ? -dx : dx)};
      const c2 = (edge.toSide === 'left') ? {x:p2.x-dx,y:p2.y} : (edge.toSide === 'right') ? {x:p2.x+dx,y:p2.y} : {x:p2.x,y:p2.y + (edge.toSide === 'top' ? -dx : dx)};
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('class','fluxo-edge');
      path.setAttribute('d', `M ${p1.x} ${p1.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${p2.x} ${p2.y}`);
      svg.appendChild(path);
    });
    updateFlowHandleStates();
  }
  function edgeUsesHandle(edge, nodeId, side){
    return (edge.from === nodeId && (edge.fromSide || 'right') === side) || (edge.to === nodeId && (edge.toSide || 'left') === side);
  }
  function handleHasEdge(nodeId, side){
    return state.fluxo.edges.some(edge => edgeUsesHandle(edge, nodeId, side));
  }
  function clearSelectedFlowHandle(){
    selectedHandle?.handle?.classList.remove('ativo');
    selectedHandle = null;
  }
  function updateFlowHandleStates(){
    $$('.flow-handle').forEach(handle => {
      const nodeEl = handle.closest('.fluxo-node');
      const nodeId = nodeEl?.dataset?.nodeId || '';
      const side = handle.dataset.side || '';
      handle.classList.toggle('conectado', !!nodeId && !!side && handleHasEdge(nodeId, side));
    });
  }
  function removeEdgesForHandle(nodeId, side){
    const before = state.fluxo.edges.length;
    state.fluxo.edges = state.fluxo.edges.filter(edge => !edgeUsesHandle(edge, nodeId, side));
    return before - state.fluxo.edges.length;
  }
  function onHandleClick(nodeId, side, handle, event = null){
    if (event?.altKey) {
      const removed = removeEdgesForHandle(nodeId, side);
      if (selectedHandle?.nodeId === nodeId && selectedHandle?.side === side) clearSelectedFlowHandle();
      if (removed > 0) {
        renderFlowLines();
        scheduleFlowSave();
        setStatus(tr('resources.connection_removed', {}, 'Ligação desfeita'));
      } else {
        setStatus(tr('resources.no_connection_on_handle', {}, 'Nenhuma ligação nessa ponta'));
      }
      return;
    }
    if (!selectedHandle) {
      selectedHandle = {nodeId, side, handle};
      handle.classList.add('ativo');
      setStatus(tr('resources.choose_handle', {}, 'Escolha outra alça para conectar'));
      return;
    }
    selectedHandle.handle?.classList.remove('ativo');
    if (selectedHandle.nodeId !== nodeId) {
      const exists = state.fluxo.edges.some(e => e.from === selectedHandle.nodeId && e.to === nodeId && e.fromSide === selectedHandle.side && e.toSide === side);
      if (!exists) state.fluxo.edges.push({id: uid('edge'), from: selectedHandle.nodeId, to: nodeId, fromSide: selectedHandle.side, toSide: side});
      renderFlowLines(); scheduleFlowSave();
    }
    selectedHandle = null;
  }
  $('#btnLimparConexaoFluxo')?.addEventListener('click', () => {
    const removed = state.fluxo.edges.length;
    clearSelectedFlowHandle();
    if (!removed) {
      updateFlowHandleStates();
      setStatus(tr('resources.no_connections_to_cancel', {}, 'Nenhuma ligação para cancelar'));
      return;
    }
    state.fluxo.edges = [];
    renderFlowLines();
    scheduleFlowSave();
    setStatus(tr('resources.all_connections_cancelled', {}, 'Todas as ligações foram canceladas'));
  });
  $('#btnNovoNodeFluxo')?.addEventListener('click', () => {
    const wrap = $('#fluxoCanvasWrap');
    const node = {id: uid('node'), x: (wrap?.scrollLeft || 0) + 120, y: (wrap?.scrollTop || 0) + 120, width: 240, height: 150, titulo: tr('resources.new_balloon', {}, 'Novo balão'), texto: ''};
    state.fluxo.nodes.push(node);
    renderFlow(); scheduleFlowSave();
  });
  function deleteNode(id){
    if (!confirm(tr('resources.delete_balloon_confirm', {}, 'Excluir este balão e suas ligações?'))) return;
    state.fluxo.nodes = state.fluxo.nodes.filter(n => n.id !== id);
    state.fluxo.edges = state.fluxo.edges.filter(e => e.from !== id && e.to !== id);
    renderFlow(); scheduleFlowSave();
  }
  function scheduleFlowSave(){
    clearTimeout(flowSaveTimer);
    setStatus(tr('resources.flow_saving', {}, 'Salvando fluxo...'));
    flowSaveTimer = setTimeout(async () => {
      try {
        await postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/fluxo`, {fluxo: state.fluxo});
        setStatus(tr('resources.flow_saved', {}, 'Fluxo salvo'));
      } catch (err) { setStatus(err.message, 'erro'); }
    }, 520);
  }

  function renderCatalogs(){
    renderCatalogList('personagens', state.personagens, $('#listaPersonagensProjeto'), '👤');
    renderCatalogList('lugares', state.lugares, $('#listaLugaresProjeto'), '📍');
    renderCatalogList('anotacoes', state.anotacoes, $('#listaAnotacoesProjeto'), '📝');
  }
  function renderCatalogList(tipo, items, container, emoji){
    if (!container) return;
    container.innerHTML = '';
    if (!items.length) { container.innerHTML = `<div class="vazio-recursos">${escapeHtml(tr('resources.no_items', {}, 'Nenhum item cadastrado ainda.'))}</div>`; return; }
    items.forEach(item => {
      const card = document.createElement('article');
      card.className = 'recurso-card';
      card.tabIndex = 0;
      card.setAttribute('role', 'button');
      card.title = item.nome || tr('resources.no_item_name', {}, 'Sem nome');
      card.innerHTML = `<h3 class="recurso-card-nome">${escapeHtml(item.nome || tr('resources.no_item_name', {}, 'Sem nome'))}</h3>`;
      card.addEventListener('click', () => openCatalogDetail(tipo, item, emoji));
      card.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          openCatalogDetail(tipo, item, emoji);
        }
      });
      container.appendChild(card);
    });
  }
  function catalogTypeLabel(tipo, singular = true){
    if (tipo === 'personagens') return singular ? tr('resources.character', {}, 'personagem') : tr('resources.characters', {}, 'Personagens');
    if (tipo === 'lugares') return singular ? tr('resources.place', {}, 'lugar') : tr('resources.places', {}, 'Lugares');
    if (tipo === 'anotacoes') return singular ? tr('resources.note', {}, 'anotação') : tr('resources.notes', {}, 'Anotações');
    return singular ? tr('resources.item', {}, 'item') : tr('resources.items', {}, 'Itens');
  }
  function catalogNewLabel(tipo){
    if (tipo === 'personagens') return tr('resources.new_character', {}, 'Novo personagem');
    if (tipo === 'lugares') return tr('resources.new_place', {}, 'Novo lugar');
    if (tipo === 'anotacoes') return tr('resources.new_note', {}, 'Nova anotação');
    return tr('resources.new_item', {}, 'Novo item');
  }
  function catalogTitleLabel(tipo){ return tipo === 'anotacoes' ? tr('resources.title_label', {}, 'Título') : tr('resources.name', {}, 'Nome'); }
  function catalogDescriptionLabel(tipo){ return tipo === 'anotacoes' ? tr('resources.note', {}, 'Anotação') : tr('resources.description', {}, 'Descrição'); }
  function updateCatalogFormMode(tipo){
    const isNote = tipo === 'anotacoes';
    const nomeLabel = $('#catalogoRecursosNomeLabel');
    const descLabel = $('#catalogoRecursosDescricaoLabel');
    const nomeInput = $('#catalogoRecursosNome');
    const descInput = $('#catalogoRecursosDescricao');
    const imageLabel = $('#catalogoRecursosImagemLabel');
    const imageWrap = document.querySelector('.imagem-preview-wrap');
    if (nomeLabel && nomeInput) { nomeLabel.firstChild.textContent = catalogTitleLabel(tipo); }
    if (descLabel && descInput) { descLabel.firstChild.textContent = catalogDescriptionLabel(tipo); }
    if (nomeInput) nomeInput.placeholder = isNote ? tr('resources.note_title_placeholder', {}, 'Título da anotação') : tr('resources.name', {}, 'Nome');
    if (descInput) descInput.placeholder = isNote ? tr('resources.note_placeholder', {}, 'Escreva o texto da anotação...') : tr('resources.description_placeholder', {}, 'Descreva aparência, função narrativa, história, personalidade, detalhes visuais...');
    imageLabel?.classList.toggle('oculto', isNote);
    imageWrap?.classList.toggle('oculto', isNote);
  }
  function openCatalogModal(tipo, item = null){
    updateCatalogFormMode(tipo);
    $('#catalogoRecursosTipo').value = tipo;
    $('#catalogoRecursosId').value = item?.origem === 'projeto' ? (item?.id || '') : '';
    $('#catalogoRecursosNome').value = item?.nome || '';
    $('#catalogoRecursosDescricao').value = item?.descricao || '';
    imageCatalogoAtual = tipo === 'anotacoes' ? '' : (item?.imagem || '');
    const img = $('#catalogoRecursosImagemPreview');
    if (img) { img.src = imageCatalogoAtual || ''; img.classList.toggle('oculto', !imageCatalogoAtual); }
    $('#tituloModalCatalogoRecursos').textContent = item ? tr('resources.edit_item', {type: catalogTypeLabel(tipo)}, `Editar ${catalogTypeLabel(tipo)}`) : catalogNewLabel(tipo);
    $('#statusCatalogoRecursos').textContent = '';
    openModal($('#modalCatalogoRecursos'));
  }
  $$('[data-novo-catalogo]').forEach(btn => btn.addEventListener('click', () => openCatalogModal(btn.dataset.novoCatalogo)));
  $('#catalogoRecursosImagemInput')?.addEventListener('change', async (ev) => {
    const file = ev.target.files?.[0];
    ev.target.value = '';
    if (!file) return;
    imageCatalogoAtual = await fileToDataUrl(file);
    const img = $('#catalogoRecursosImagemPreview');
    if (img) { img.src = imageCatalogoAtual; img.classList.remove('oculto'); }
  });
  $('#btnRemoverImagemCatalogo')?.addEventListener('click', () => {
    imageCatalogoAtual = '';
    const img = $('#catalogoRecursosImagemPreview');
    if (img) { img.src = ''; img.classList.add('oculto'); }
  });
  $('#formCatalogoRecursos')?.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const tipo = $('#catalogoRecursosTipo').value;
    const payload = {id: $('#catalogoRecursosId').value, nome: $('#catalogoRecursosNome').value.trim(), descricao: $('#catalogoRecursosDescricao').value.trim(), imagem: tipo === 'anotacoes' ? '' : imageCatalogoAtual};
    if (!payload.nome) { $('#statusCatalogoRecursos').textContent = tipo === 'anotacoes' ? tr('resources.title_required', {}, 'Informe um título.') : tr('resources.name_required', {}, 'Informe um nome.'); return; }
    $('#statusCatalogoRecursos').textContent = tr('resources.saving', {}, 'Salvando...');
    try {
      const data = await postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/catalogo/${encodeURIComponent(tipo)}`, payload);
      closeModal($('#modalCatalogoRecursos'));
      absorbServer(data);
      setStatus(tr('resources.catalog_saved', {}, 'Catálogo salvo'));
    } catch (err) { $('#statusCatalogoRecursos').textContent = err.message; }
  });
  function openCatalogDetail(tipo, item = null, emoji = ''){
    if (!item) return;
    detalheCatalogoAtual = {tipo, item, emoji};
    const tipoLabel = tipo === 'personagens' ? tr('resources.character', {}, 'Personagem') : (tipo === 'anotacoes' ? tr('resources.note', {}, 'Anotação') : tr('resources.place', {}, 'Lugar'));
    const origem = tipo === 'anotacoes' ? tr('resources.saved_in_project_feminine', {}, 'salva no projeto') : (item.origem === 'roteiro' ? tr('resources.detected_in_script', {}, 'detectado no roteiro') : tr('resources.saved_in_project', {}, 'salvo no projeto'));
    const nome = item.nome || tr('resources.no_item_name', {}, 'Sem nome');
    const descricao = item.descricao || tr('resources.no_description', {}, 'Sem descrição.');
    const fontes = Array.isArray(item.fontes) && item.fontes.length ? `${tr('resources.source', {}, 'Fonte')}: ${item.fontes.join(', ')}` : '';
    const nomeEl = $('#detalheCatalogoNome');
    const tipoEl = $('#detalheCatalogoTipo');
    const descEl = $('#detalheCatalogoDescricao');
    const fontesEl = $('#detalheCatalogoFontes');
    const imgEl = $('#detalheCatalogoImagem');
    const semImgEl = $('#detalheCatalogoSemImagem');
    const descTitleEl = $('#detalheCatalogoDescricaoTitulo');
    const detailModalEl = $('#modalDetalheCatalogoRecursos');
    if (nomeEl) { nomeEl.textContent = nome; nomeEl.title = nome; }
    if (tipoEl) tipoEl.textContent = `${tipoLabel} · ${origem}`;
    if (descTitleEl) descTitleEl.textContent = catalogDescriptionLabel(tipo);
    if (descEl) descEl.textContent = descricao;
    if (fontesEl) { fontesEl.textContent = fontes; fontesEl.classList.toggle('oculto', !fontes); }
    if (detailModalEl) detailModalEl.classList.toggle('catalogo-sem-imagem', tipo === 'anotacoes');
    if (imgEl && semImgEl) {
      const showImage = tipo !== 'anotacoes' && !!item.imagem;
      imgEl.src = showImage ? item.imagem : '';
      imgEl.classList.toggle('oculto', !showImage);
      semImgEl.classList.toggle('oculto', showImage || tipo === 'anotacoes');
      semImgEl.textContent = showImage ? '' : `${tr('resources.no_reference_image', {}, 'Sem imagem de referência')} ${emoji ? emoji : ''}`.trim();
    }
    openModal($('#modalDetalheCatalogoRecursos'));
  }


  function setupCatalogDetailImagePreview(){
    const img = $('#detalheCatalogoImagem');
    if (!img) return;
    let preview = null;
    function closePreview(){
      preview?.remove();
      preview = null;
    }
    function openPreview(){
      if (!img.src || img.classList.contains('oculto')) return;
      closePreview();
      preview = document.createElement('div');
      preview.className = 'detalhe-catalogo-image-preview';
      const image = document.createElement('img');
      image.src = img.src;
      image.alt = img.alt || tr('resources.reference_image', {}, 'Imagem de referência');
      preview.appendChild(image);
      const w = img.naturalWidth || 0;
      const h = img.naturalHeight || 0;
      if (w && h) {
        const label = document.createElement('span');
        label.className = 'detalhe-catalogo-image-preview-label';
        label.textContent = `${w} × ${h}`;
        preview.appendChild(label);
      }
      document.body.appendChild(preview);
    }
    img.addEventListener('mouseenter', openPreview);
    img.addEventListener('mouseleave', closePreview);
    img.addEventListener('error', closePreview);
    document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') closePreview(); });
  }

  async function deleteCatalogItem(tipo, item){
    if (!confirm(tr('resources.delete_hide_confirm', {name: item.nome}, `Excluir/ocultar "${item.nome}" deste painel?`))) return false;
    try {
      const data = await postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/catalogo/${encodeURIComponent(tipo)}/excluir`, {id: item.id, nome: item.nome});
      absorbServer(data);
      setStatus(tr('resources.item_removed', {}, 'Item removido'));
      return true;
    } catch (err) { setStatus(err.message, 'erro'); return false; }
  }

  function openModal(el){ el?.classList.remove('oculto'); }
  function closeModal(el){ el?.classList.add('oculto'); }
  document.querySelectorAll('[data-fechar-modal="true"]').forEach(el => el.addEventListener('click', (ev)=>{ ev.preventDefault(); closeModal(el.closest('.modal')); }));
  document.querySelectorAll('[data-modal-card="true"]').forEach(el => el.addEventListener('click', (ev)=> ev.stopPropagation()));
  $('#btnEditarDetalheCatalogo')?.addEventListener('click', () => {
    if (!detalheCatalogoAtual) return;
    const {tipo, item} = detalheCatalogoAtual;
    closeModal($('#modalDetalheCatalogoRecursos'));
    openCatalogModal(tipo, item);
  });
  $('#btnExcluirDetalheCatalogo')?.addEventListener('click', async () => {
    if (!detalheCatalogoAtual) return;
    const {tipo, item} = detalheCatalogoAtual;
    const removed = await deleteCatalogItem(tipo, item);
    if (removed) closeModal($('#modalDetalheCatalogoRecursos'));
  });
  $('#btnSalvarRecursosGutr')?.addEventListener('click', salvarRecursosGutr);
  $('#btnImportarRecursosGutr')?.addEventListener('click', iniciarImportacaoRecursosGutr);
  $('#inputGutrImportacao')?.addEventListener('change', async (ev) => {
    const arquivo = ev.target?.files?.[0];
    ev.target.value = '';
    if (!arquivo) return;
    try {
      if (!String(arquivo.name || '').toLowerCase().endsWith('.gutr')) {
        throw new Error(tr('resources.invalid_gutr', {}, 'Selecione um arquivo .gutr.'));
      }
      await importarRecursosGutrViaUpload(arquivo);
    } catch (err) {
      setStatus(err.message || tr('resources.import_error', {}, 'Não foi possível importar recursos.'), 'erro');
      alert(err.message || tr('resources.import_error', {}, 'Não foi possível importar recursos.'));
    }
  });
  window.addEventListener('resize', () => { if (activeTab === 'fluxo') renderFlowLines(); });
  bindInfoToolbar();
  setupCatalogDetailImagePreview();
  setupFlowCanvasPanning();

  renderInfoList();
  loadActiveInfo();
  renderFlow();
  renderCatalogs();
})();
