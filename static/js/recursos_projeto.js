/** Recursos criativos por projeto: informações, fluxo, personagens, lugares e anotações. */
(function(){
  const slug = window.PROJETO_SLUG || '';
  const MAX_RESOURCE_PAGES = 7;
  const CATALOG_TYPES = ['personagens', 'lugares', 'anotacoes'];
  const PAGE_TABS = {
    informacoes: {container:'#tabsPaginasInfo', add:'#btnNovaPaginaInfo'},
    fluxo: {container:'#tabsPaginasFluxo', add:'#btnNovaPaginaFluxo'},
    personagens: {container:'#tabsPaginasPersonagens', add:'#btnNovaPaginaPersonagens'},
    lugares: {container:'#tabsPaginasLugares', add:'#btnNovaPaginaLugares'},
    anotacoes: {container:'#tabsPaginasAnotacoes', add:'#btnNovaPaginaAnotacoes'},
  };
  let state = normalizeState(window.PROJETO_RECURSOS_INITIAL || {});
  let activeTab = 'informacoes';
  let activeInfoTabId = state.informacoes_abas[0]?.id || null;
  let activeInfoPageIds = Object.fromEntries((state.informacoes_abas || []).map(tab => [tab.id, tab.paginas?.[0]?.id || null]));
  let activeInfoId = activeInfoPageIds[activeInfoTabId] || null;
  let activeFlowId = state.fluxos[0]?.id || null;
  let activeCatalogPageIds = {
    personagens: state.personagens_paginas[0]?.id || null,
    lugares: state.lugares_paginas[0]?.id || null,
    anotacoes: state.anotacoes_paginas[0]?.id || null,
  };
  let infoSaveTimer = null;
  let flowSaveTimer = null;
  const catalogPagesSaveTimers = {};
  let selectedHandle = null;
  let dragState = null;
  let resizeState = null;
  let flowPanState = null;
  let flowSpacePanActive = false;
  let imageCatalogoAtual = '';
  let detalheCatalogoAtual = null;
  let lastInfoRange = null;
  // Persistência serial por recurso: um POST obsoleto não pode terminar
  // depois de um POST novo e sobrescrever uma versão mais recente.
  const resourceWrites = new Map();
  function writeState(channel){
    if (!resourceWrites.has(channel)) resourceWrites.set(channel, {revision:0, savedRevision:0, task:null});
    return resourceWrites.get(channel);
  }
  function markResourceDirty(channel){
    writeState(channel).revision += 1;
  }
  async function persistResource(channel, send, successText){
    const entry = writeState(channel);
    if (entry.task) return entry.task;
    const task = (async () => {
      while (entry.savedRevision < entry.revision) {
        const revision = entry.revision;
        try {
          await send();
          entry.savedRevision = revision;
          if (entry.savedRevision === entry.revision) setStatus(successText);
        } catch (err) {
          setStatus(err?.message || String(err), 'erro');
          throw err;
        }
      }
    })();
    entry.task = task;
    try { await task; } finally { if (entry.task === task) entry.task = null; }
  }

  // Backup local independente para cada folha de Informações. Cópias só
  // são oferecidas ao reabrir a página, nunca restauradas silenciosamente.
  const infoRecovery = (() => {
    const prefix = `gutenberg:recursos-info:v1:${encodeURIComponent(slug)}:`;
    const isPortuguese = (document.documentElement.lang || 'pt').toLowerCase().startsWith('pt');
    const storageWarnings = {
      tooLarge: isPortuguese ? 'A cópia local desta página excedeu o limite do navegador.' : 'The local copy of this page exceeds the browser storage limit.',
      unavailable: isPortuguese ? 'Não foi possível armazenar uma cópia local da página.' : 'Unable to store a local copy of this page.'
    };
    const checked = new Set();
    const baselines = new Map();
    let timer = 0;
    let notice = null;
    let pending = null;
    const pendingWrites = new Map();
    const keyFor = (tabId, pageId) => `${prefix}${encodeURIComponent(tabId)}:${encodeURIComponent(pageId)}`;
    const signature = (page) => JSON.stringify([page?.titulo || '', page?.html || '']);
    function findPage(tabId, pageId) {
      return state.informacoes_abas.find(tab => tab.id === tabId)?.paginas?.find(page => page.id === pageId);
    }
    (state.informacoes_abas || []).forEach(tab => (tab.paginas || []).forEach(page => {
      baselines.set(keyFor(tab.id, page.id), signature(page));
    }));
    function read(key) {
      try {
        const raw = localStorage.getItem(key);
        const value = raw ? JSON.parse(raw) : null;
        return value?.version === 1 && typeof value.html === 'string' && typeof value.title === 'string' ? value : null;
      } catch (_) { return null; }
    }
    function clearNotice(){
      if (pending) checked.delete(pending.key); // Permite decidir ao voltar à página.
      notice?.remove(); notice = null; pending = null;
    }
    function writeNow(){
      clearTimeout(timer); timer = 0;
      for (const [key, saved] of pendingWrites) {
        pendingWrites.delete(key);
        if (pending?.key === key) continue; // Não sobrepor uma decisão pendente.
        if (saved.signature === baselines.get(key)) {
          try { localStorage.removeItem(key); } catch (_) {}
          continue;
        }
        const payload = JSON.stringify({version:1, title:saved.title, html:saved.html, time:Date.now()});
        if (payload.length > 3 * 1024 * 1024) {
          setStatus(storageWarnings.tooLarge, 'erro');
          continue;
        }
        try { localStorage.setItem(key, payload); }
        catch (_) { setStatus(storageWarnings.unavailable, 'erro'); }
      }
    }
    function schedule(){
      const page=findPage(activeInfoTabId,activeInfoId);
      if (page) pendingWrites.set(keyFor(activeInfoTabId,activeInfoId), {
        title:page.titulo, html:page.html, signature:signature(page)
      });
      clearTimeout(timer); timer = setTimeout(writeNow, 260);
    }
    function show(page){
      clearNotice();
      if (!page || !activeInfoTabId) return;
      const tabId=activeInfoTabId, pageId=page.id, key=keyFor(tabId,pageId);
      if (checked.has(key)) return;
      checked.add(key);
      const copy=read(key);
      if (!copy) return;
      const savedCopy = JSON.stringify([copy.title,copy.html]);
      if (savedCopy === baselines.get(key)) {
        // Só eliminar quando a mesma versão já foi confirmada pelo servidor.
        try { localStorage.removeItem(key); } catch (_) {}
        return;
      }
      if (savedCopy === signature(page)) return; // Já recuperada nesta sessão, ainda não confirmada.
      pending = {key, tabId, pageId, copy};
      const pt=isPortuguese;
      const box=document.createElement('aside');
      box.className='info-recuperacao-aviso';
      box.setAttribute('role','status');
      const message=document.createElement('p');
      message.textContent=pt ? 'Há uma cópia local não confirmada desta página de Informações.' : 'An unsaved local copy of this Information page is available.';
      const actions=document.createElement('div');
      actions.className='info-recuperacao-acoes';
      const recover=document.createElement('button');
      recover.type='button';recover.textContent=pt ? 'Recuperar cópia' : 'Restore copy';
      const discard=document.createElement('button');
      discard.type='button';discard.textContent=pt ? 'Descartar cópia' : 'Discard copy';
      recover.addEventListener('click',()=>{
        if (!pending || pending.key!==key || activeInfoTabId!==tabId || activeInfoId!==pageId) return;
        const current=findPage(tabId,pageId);
        if (!current) return;
        const title=$('#tituloPaginaInfo'), editor=$('#editorInfoPagina');
        if (!title || !editor) return;
        if (signature({titulo:title.value,html:editor.innerHTML}) !== signature(page) &&
            !confirm(pt ? 'Substituir as mudanças desta sessão pela cópia local?' : 'Replace the changes in this session with the local copy?')) return;
        current.titulo=copy.title;current.html=copy.html;
        title.value=copy.title;editor.innerHTML=copy.html;
        clearNotice();
        infoVisualPagination?.schedule(true);
        scheduleInfoSave({rerenderSidebar:true});
      });
      discard.addEventListener('click',()=>{
        if (!pending || pending.key!==key) return;
        try { localStorage.removeItem(key); } catch (_) {}
        clearNotice();
        // Mudanças feitas após a abertura continuam protegidas.
        schedule();
      });
      actions.append(recover,discard);box.append(message,actions);
      ($('#infoPaperStage')?.parentElement || document.body).prepend(box);
      notice=box;
    }
    function confirm(snapshot){
      snapshot.forEach(({key, value})=>{
        baselines.set(key,value);
        const copy=read(key);
        if (copy && JSON.stringify([copy.title,copy.html])===value) {
          try { localStorage.removeItem(key); } catch (_) {}
        }
      });
    }
    function snapshot(){
      return (state.informacoes_abas || []).flatMap(tab => (tab.paginas || []).map(page => ({
        key:keyFor(tab.id,page.id),value:signature(page)
      })));
    }
    // Em fechamento/ocultação, sincronizar o editor visível antes da cópia.
    function emergency(){
      if (!$('#editorInfoPagina')) return;
      saveCurrentInfoToState();
      schedule();
      writeNow();
    }
    window.addEventListener('pagehide', emergency);
    document.addEventListener('visibilitychange',()=>{if (document.hidden) emergency();});
    window.addEventListener('online',()=>{if (writeState('informacoes').revision > writeState('informacoes').savedRevision) scheduleInfoSave({captureEditor:true,rerenderSidebar:false});});
    return {schedule,writeNow,show,confirm,snapshot,emergency};
  })();

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

  function defaultPageTitle(tipo){
    if (tipo === 'fluxo') return tr('resources.flow', {}, 'Fluxo');
    if (tipo === 'personagens') return tr('resources.characters', {}, 'Personagens');
    if (tipo === 'lugares') return tr('resources.places', {}, 'Lugares');
    if (tipo === 'anotacoes') return tr('resources.notes', {}, 'Anotações');
    return tr('resources.default_page_title', {}, 'Página inicial');
  }
  function catalogPagesKey(tipo){ return `${tipo}_paginas`; }
  function resourcePages(tipo){
    if (tipo === 'informacoes') return state.informacoes_abas || [];
    if (tipo === 'fluxo') return state.fluxos;
    return state[catalogPagesKey(tipo)] || [];
  }
  function activeResourcePageId(tipo){
    if (tipo === 'informacoes') return activeInfoTabId;
    if (tipo === 'fluxo') return activeFlowId;
    return activeCatalogPageIds[tipo];
  }
  function setActiveResourcePageId(tipo, id){
    if (tipo === 'informacoes') activeInfoTabId = id;
    else if (tipo === 'fluxo') activeFlowId = id;
    else activeCatalogPageIds[tipo] = id;
  }
  function normalizeResourcePages(value, tipo){
    const raw = Array.isArray(value) ? value : [];
    const pages = [];
    const seen = new Set();
    raw.forEach((page) => {
      if (!page || typeof page !== 'object' || pages.length >= MAX_RESOURCE_PAGES) return;
      const id = String(page.id || uid(tipo));
      if (seen.has(id)) return;
      seen.add(id);
      pages.push({
        id,
        titulo: String(page.titulo || page.nome || defaultPageTitle(tipo)).slice(0, tipo === 'informacoes' ? 90 : 60),
        data_criacao: page.data_criacao || '',
        data_atualizacao: page.data_atualizacao || '',
      });
    });
    if (!pages.length) pages.push({id: `${tipo}_principal`, titulo: defaultPageTitle(tipo), data_criacao:'', data_atualizacao:''});
    return pages.slice(0, MAX_RESOURCE_PAGES);
  }
  function defaultInfoPage(){
    const now = new Date().toISOString();
    return {
      id: uid('info'),
      titulo: tr('resources.default_page_title', {}, 'Página inicial'),
      html: tr('resources.default_page_html', {}, '<p></p>'),
      data_criacao: now,
      data_atualizacao: now,
    };
  }
  function normalizeInfoPages(value){
    const raw = Array.isArray(value) ? value : [];
    const pages = [];
    const seen = new Set();
    raw.forEach((page) => {
      if (!page || typeof page !== 'object') return;
      const id = String(page.id || uid('info'));
      if (seen.has(id)) return;
      seen.add(id);
      pages.push({
        id,
        titulo: String(page.titulo || tr('resources.untitled', {}, 'Sem título')).slice(0, 90),
        html: String(page.html || '<p></p>'),
        data_criacao: page.data_criacao || '',
        data_atualizacao: page.data_atualizacao || '',
      });
    });
    if (!pages.length) pages.push(defaultInfoPage());
    return pages;
  }
  function normalizeInfoTabs(value, legacyPages){
    const raw = Array.isArray(value) ? value : [];
    const looksLikeTabs = raw.some(tab => tab && typeof tab === 'object' && (Array.isArray(tab.paginas) || Array.isArray(tab.pages) || Array.isArray(tab.informacoes)));
    const sourceTabs = looksLikeTabs ? raw : [{
      id: 'informacoes_principal',
      titulo: tr('resources.default_page_title', {}, 'Página inicial'),
      paginas: normalizeInfoPages(legacyPages),
    }];
    const tabs = [];
    const seen = new Set();
    sourceTabs.forEach((tab) => {
      if (!tab || typeof tab !== 'object' || tabs.length >= MAX_RESOURCE_PAGES) return;
      const id = String(tab.id || uid('info_tab'));
      if (seen.has(id)) return;
      seen.add(id);
      tabs.push({
        id,
        titulo: String(tab.titulo || tab.nome || defaultPageTitle('informacoes')).slice(0, 60),
        paginas: normalizeInfoPages(tab.paginas || tab.informacoes || tab.pages),
        data_criacao: tab.data_criacao || '',
        data_atualizacao: tab.data_atualizacao || '',
      });
    });
    if (!tabs.length) tabs.push({id: 'informacoes_principal', titulo: defaultPageTitle('informacoes'), paginas: [defaultInfoPage()], data_criacao:'', data_atualizacao:''});
    return tabs.slice(0, MAX_RESOURCE_PAGES);
  }
  function flattenInfoTabs(tabs){
    const flat = [];
    (tabs || []).forEach(tab => {
      (tab.paginas || []).forEach(page => {
        flat.push({...page, aba_id: tab.id, aba_titulo: tab.titulo});
      });
    });
    return flat;
  }
  function syncFlatInfo(){
    state.informacoes = flattenInfoTabs(state.informacoes_abas || []);
  }
  function normalizeFlow(flow){
    const src = flow && typeof flow === 'object' ? flow : {};
    return {
      nodes: Array.isArray(src.nodes) ? src.nodes : [],
      edges: Array.isArray(src.edges) ? src.edges : [],
    };
  }
  function normalizeFlowPages(value, legacyFlow){
    const raw = Array.isArray(value) && value.length ? value : [{id:'fluxo_principal', titulo: defaultPageTitle('fluxo'), ...normalizeFlow(legacyFlow)}];
    const pages = [];
    const seen = new Set();
    raw.forEach((page) => {
      if (!page || typeof page !== 'object' || pages.length >= MAX_RESOURCE_PAGES) return;
      const id = String(page.id || uid('fluxo'));
      if (seen.has(id)) return;
      seen.add(id);
      const flow = normalizeFlow(page.fluxo || page);
      pages.push({
        id,
        titulo: String(page.titulo || page.nome || defaultPageTitle('fluxo')).slice(0, 60),
        nodes: flow.nodes,
        edges: flow.edges,
        data_criacao: page.data_criacao || '',
        data_atualizacao: page.data_atualizacao || '',
      });
    });
    if (!pages.length) pages.push({id:'fluxo_principal', titulo: defaultPageTitle('fluxo'), nodes:[], edges:[], data_criacao:'', data_atualizacao:''});
    return pages;
  }
  function normalizeCatalogItems(value, tipo, pages){
    const raw = Array.isArray(value) ? value : [];
    const valid = new Set((pages || []).map(p => p.id));
    const fallbackPage = pages?.[0]?.id || `${tipo}_principal`;
    return raw.map((item) => {
      const pageId = valid.has(String(item?.pagina_id || '')) ? String(item.pagina_id) : fallbackPage;
      return {...item, pagina_id: pageId};
    });
  }
  function normalizeState(data){
    const informacoes_abas = normalizeInfoTabs(data.informacoes_abas || data.abas_informacoes, data.informacoes);
    const informacoes = flattenInfoTabs(informacoes_abas);
    const fluxos = normalizeFlowPages(data.fluxos, data.fluxo);
    const personagens_paginas = normalizeResourcePages(data.personagens_paginas || data.paginas_personagens, 'personagens');
    const lugares_paginas = normalizeResourcePages(data.lugares_paginas || data.paginas_lugares, 'lugares');
    const anotacoes_paginas = normalizeResourcePages(data.anotacoes_paginas || data.paginas_anotacoes, 'anotacoes');
    return {
      informacoes_abas,
      informacoes,
      fluxos,
      fluxo: normalizeFlow(data.fluxo || fluxos[0]),
      personagens_paginas,
      lugares_paginas,
      anotacoes_paginas,
      personagens: normalizeCatalogItems(data.personagens, 'personagens', personagens_paginas),
      lugares: normalizeCatalogItems(data.lugares, 'lugares', lugares_paginas),
      anotacoes: normalizeCatalogItems(data.anotacoes, 'anotacoes', anotacoes_paginas),
      personagens_projeto: Array.isArray(data.personagens_projeto) ? data.personagens_projeto : [],
      lugares_projeto: Array.isArray(data.lugares_projeto) ? data.lugares_projeto : [],
      anotacoes_projeto: Array.isArray(data.anotacoes_projeto) ? data.anotacoes_projeto : []
    };
  }
  function absorbServer(data){
    state = normalizeState(data || state);
    if (!state.informacoes_abas.some(tab => tab.id === activeInfoTabId)) activeInfoTabId = state.informacoes_abas[0]?.id || null;
    state.informacoes_abas.forEach(tab => { if (!activeInfoPageIds[tab.id]) activeInfoPageIds[tab.id] = tab.paginas?.[0]?.id || null; });
    const activeInfoTab = state.informacoes_abas.find(tab => tab.id === activeInfoTabId) || state.informacoes_abas[0];
    if (!activeInfoTab?.paginas?.some(page => page.id === activeInfoId)) {
      const remembered = activeInfoPageIds[activeInfoTab?.id];
      activeInfoId = activeInfoTab?.paginas?.some(page => page.id === remembered) ? remembered : (activeInfoTab?.paginas?.[0]?.id || null);
    }
    if (activeInfoTab?.id) activeInfoPageIds[activeInfoTab.id] = activeInfoId;
    syncFlatInfo();
    if (!state.fluxos.some(p => p.id === activeFlowId)) activeFlowId = state.fluxos[0]?.id || null;
    CATALOG_TYPES.forEach((tipo) => {
      const pages = state[catalogPagesKey(tipo)] || [];
      if (!pages.some(p => p.id === activeCatalogPageIds[tipo])) activeCatalogPageIds[tipo] = pages[0]?.id || null;
    });
    renderAllPageTabs();
    loadActiveInfo();
    renderFlow();
    renderCatalogs();
  }
  // Todas as seções de Rascunho compartilham um mesmo registro no SQLite.
  // Ordenar os POSTs de Informações, Fluxo e Catálogos evita que operações
  // read-modify-write concorrentes sobrescrevam outras seções do projeto.
  let projectWriteQueue = Promise.resolve();
  function postJSON(url, payload){
    const body = JSON.stringify(payload || {});
    const request = projectWriteQueue.then(async () => {
      const resp = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body});
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || data.ok === false) throw new Error(data.erro || tr('editor.save_failed', {}, 'Não foi possível salvar.'));
      return data;
    });
    projectWriteQueue = request.catch(() => {});
    return request;
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

  function currentInfoTab(){ return state.informacoes_abas.find(tab => tab.id === activeInfoTabId) || state.informacoes_abas[0]; }
  function currentInfoPages(){ return currentInfoTab()?.paginas || []; }
  function ensureActiveInfoPage(){
    const tab = currentInfoTab();
    if (!tab) { activeInfoId = null; return null; }
    const pages = tab.paginas || [];
    if (!pages.some(page => page.id === activeInfoId)) {
      const remembered = activeInfoPageIds[tab.id];
      activeInfoId = pages.some(page => page.id === remembered) ? remembered : (pages[0]?.id || null);
    }
    activeInfoPageIds[tab.id] = activeInfoId;
    return activeInfoId;
  }
  function currentInfo(){ const pages = currentInfoPages(); ensureActiveInfoPage(); return pages.find(p => p.id === activeInfoId) || pages[0]; }
  function currentFlow(){ return state.fluxos.find(p => p.id === activeFlowId) || state.fluxos[0] || {nodes:[], edges:[], titulo: defaultPageTitle('fluxo')}; }
  function currentCatalogItems(tipo){
    const pageId = activeCatalogPageIds[tipo] || state[catalogPagesKey(tipo)]?.[0]?.id || '';
    return (state[tipo] || []).filter(item => String(item.pagina_id || '') === String(pageId));
  }
  function projectCatalogItems(tipo){
    return (state[tipo] || []).filter(item => item?.origem !== 'roteiro' && !item?.somente_leitura);
  }
  function renderInfoList(){
    renderResourcePageTabs('informacoes');
    const list = $('#listaPaginasInfo');
    const pages = currentInfoPages();
    ensureActiveInfoPage();
    const activeId = activeInfoId || pages[0]?.id;
    const sideAddButton = $('#btnNovaPaginaInfoLateral');
    if (sideAddButton) sideAddButton.disabled = false;
    if (!list) return;
    list.innerHTML = '';
    pages.forEach((page, idx) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `info-page-item${page.id === activeId ? ' ativo' : ''}`;
      const titulo = page.titulo || `${tr('resources.pages', {}, 'Página')} ${idx + 1}`;
      btn.title = titulo;
      btn.innerHTML = `<strong>${escapeHtml(titulo)}</strong>`;
      btn.addEventListener('click', () => switchInfoSidePage(page.id));
      list.appendChild(btn);
    });
  }
  function renderAllPageTabs(){
    renderInfoList();
    ['fluxo', ...CATALOG_TYPES].forEach(renderResourcePageTabs);
  }
  function renderResourcePageTabs(tipo){
    const config = PAGE_TABS[tipo];
    const container = $(config?.container || '');
    const addButton = $(config?.add || '');
    if (!container) return;
    const pages = resourcePages(tipo);
    const activeId = activeResourcePageId(tipo) || pages[0]?.id;
    container.innerHTML = '';
    pages.forEach((page, idx) => {
      const tab = document.createElement('button');
      tab.type = 'button';
      tab.className = `resource-page-tab${page.id === activeId ? ' ativo' : ''}`;
      tab.title = page.titulo || `${tr('resources.pages', {}, 'Página')} ${idx + 1}`;
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-selected', page.id === activeId ? 'true' : 'false');
      // O título deve parecer texto da aba, nunca um input permanente.
      // Renomear continua disponível por duplo clique ou F2.
      const span = document.createElement('span');
      span.className = 'resource-page-tab-title';
      span.textContent = page.titulo || tab.title;
      tab.appendChild(span);
      if (page.id === activeId) {
        tab.title = `${tab.title} — duplo clique ou F2 para renomear`;
        const beginRename = (ev) => {
          if (tab.querySelector('.resource-page-tab-input') || ev?.target?.closest('.resource-page-remove')) return;
          ev?.preventDefault();
          ev?.stopPropagation();
          const input = document.createElement('input');
          input.type = 'text';
          input.className = 'resource-page-tab-input';
          input.value = page.titulo || '';
          input.maxLength = 60;
          input.setAttribute('aria-label', tr('resources.page_title_placeholder', {}, 'Nome da aba'));
          // Isolar o campo para não disparar seleção de outras abas.
          input.addEventListener('click', (event) => event.stopPropagation());
          input.addEventListener('dblclick', (event) => event.stopPropagation());
          input.addEventListener('keydown', (event) => {
            event.stopPropagation();
            if (event.key === 'Enter' || event.key === 'Escape') {
              event.preventDefault();
              if (event.key === 'Escape') input.dataset.cancelRename = '1';
              input.blur();
            }
          });
          input.addEventListener('blur', () => {
            const novoTitulo = input.value.trim() || tr('resources.untitled', {}, 'Sem título');
            if (!input.dataset.cancelRename && novoTitulo !== page.titulo) {
              renameResourcePage(tipo, page.id, novoTitulo, false);
            }
            // Repor apenas o texto: reconstruir todas as abas durante o blur
            // intercepta o clique do usuário na aba vizinha.
            span.textContent = page.titulo || tab.title;
            tab.title = `${page.titulo || ''} — duplo clique ou F2 para renomear`;
            if (input.isConnected) tab.replaceChild(span, input);
          }, {once:true});
          tab.replaceChild(input, span);
          input.focus();
          input.select();
        };
        tab.addEventListener('dblclick', beginRename);
        tab.addEventListener('keydown', (ev) => { if (ev.key === 'F2') beginRename(ev); });
      }
      if (pages.length > 1) {
        const remove = document.createElement('span');
        remove.className = 'resource-page-remove';
        remove.textContent = '×';
        remove.title = tr('resources.delete_page', {}, 'Excluir página');
        remove.addEventListener('click', (ev) => { ev.preventDefault(); ev.stopPropagation(); deleteResourcePage(tipo, page.id); });
        tab.appendChild(remove);
      }
      tab.addEventListener('click', () => switchResourcePage(tipo, page.id));
      container.appendChild(tab);
    });
    if (addButton) addButton.disabled = pages.length >= MAX_RESOURCE_PAGES;
  }
  function switchResourcePage(tipo, id){
    if (activeResourcePageId(tipo) === id) return;
    if (tipo === 'informacoes') {
      saveCurrentInfoToState();
      if (activeInfoTabId) activeInfoPageIds[activeInfoTabId] = activeInfoId;
      clearSelectedFlowHandle();
      activeInfoTabId = id;
      const tab = currentInfoTab();
      const remembered = activeInfoPageIds[id];
      activeInfoId = tab?.paginas?.some(page => page.id === remembered) ? remembered : (tab?.paginas?.[0]?.id || null);
      renderInfoList();
      loadActiveInfo();
      return;
    }
    clearSelectedFlowHandle();
    setActiveResourcePageId(tipo, id);
    renderResourcePageTabs(tipo);
    if (tipo === 'fluxo') { renderFlow(); scheduleFlowSave(); }
    if (CATALOG_TYPES.includes(tipo)) renderCatalogs();
  }
  function switchInfoSidePage(id){
    if (activeInfoId === id) return;
    saveCurrentInfoToState();
    activeInfoId = id;
    if (activeInfoTabId) activeInfoPageIds[activeInfoTabId] = id;
    renderInfoList();
    loadActiveInfo();
  }
  function renameResourcePage(tipo, id, rawTitle, rerender = true){
    const title = String(rawTitle || '').trim() || tr('resources.untitled', {}, 'Sem título');
    const page = resourcePages(tipo).find(p => p.id === id);
    if (!page) return;
    page.titulo = title.slice(0, 60);
    page.data_atualizacao = new Date().toISOString();
    if (rerender) renderResourcePageTabs(tipo);
    if (tipo === 'informacoes') scheduleInfoSave({rerenderSidebar:false});
    else if (tipo === 'fluxo') scheduleFlowSave();
    else scheduleCatalogPagesSave(tipo);
  }
  function addResourcePage(tipo){
    const pages = resourcePages(tipo);
    if (pages.length >= MAX_RESOURCE_PAGES) return;
    const page = {id: uid(tipo === 'informacoes' ? 'info' : tipo), titulo: tr('resources.new_page', {}, 'Nova página'), data_criacao: new Date().toISOString(), data_atualizacao: new Date().toISOString()};
    if (tipo === 'informacoes') {
      saveCurrentInfoToState();
      const infoPage = {
        id: uid('info'),
        titulo: tr('resources.default_page_title', {}, 'Página inicial'),
        html: tr('resources.new_page_html', {}, '<h2>Nova página</h2><p></p>'),
        data_criacao: page.data_criacao,
        data_atualizacao: page.data_atualizacao,
      };
      const tab = {...page, paginas: [infoPage]};
      state.informacoes_abas.push(tab);
      activeInfoTabId = tab.id;
      activeInfoId = infoPage.id;
      activeInfoPageIds[tab.id] = infoPage.id;
      syncFlatInfo();
      renderInfoList(); loadActiveInfo(); scheduleInfoSave({rerenderSidebar:false});
      return;
    }
    if (tipo === 'fluxo') {
      state.fluxos.push({...page, nodes: [], edges: []});
      activeFlowId = page.id;
      renderResourcePageTabs('fluxo'); renderFlow(); scheduleFlowSave();
      return;
    }
    state[catalogPagesKey(tipo)].push(page);
    activeCatalogPageIds[tipo] = page.id;
    renderResourcePageTabs(tipo); renderCatalogs(); scheduleCatalogPagesSave(tipo);
  }
  function deleteResourcePage(tipo, id){
    const pages = resourcePages(tipo);
    if (pages.length <= 1) { alert(tr('resources.keep_one_page', {}, 'Mantenha pelo menos uma página.')); return; }
    const page = pages.find(p => p.id === id);
    const title = page?.titulo || tr('resources.untitled', {}, 'Sem título');
    if (!confirm(tr('resources.delete_page_confirm', {title}, `Excluir a página "${title}"?`))) return;
    if (tipo === 'informacoes') {
      state.informacoes_abas = state.informacoes_abas.filter(tab => tab.id !== id);
      delete activeInfoPageIds[id];
      activeInfoTabId = state.informacoes_abas[0]?.id || null;
      activeInfoId = state.informacoes_abas[0]?.paginas?.[0]?.id || null;
      if (activeInfoTabId) activeInfoPageIds[activeInfoTabId] = activeInfoId;
      syncFlatInfo();
      renderInfoList(); loadActiveInfo(); scheduleInfoSave({rerenderSidebar:false});
      return;
    }
    if (tipo === 'fluxo') {
      state.fluxos = state.fluxos.filter(p => p.id !== id);
      activeFlowId = state.fluxos[0]?.id || null;
      renderResourcePageTabs('fluxo'); renderFlow(); scheduleFlowSave();
      return;
    }
    state[catalogPagesKey(tipo)] = state[catalogPagesKey(tipo)].filter(p => p.id !== id);
    state[tipo] = (state[tipo] || []).filter(item => String(item.pagina_id || '') !== String(id));
    activeCatalogPageIds[tipo] = state[catalogPagesKey(tipo)][0]?.id || null;
    renderResourcePageTabs(tipo); renderCatalogs(); scheduleCatalogPagesSave(tipo);
  }
  function addInfoSidePage(){
    const tab = currentInfoTab();
    if (!tab) return;
    saveCurrentInfoToState();
    const now = new Date().toISOString();
    const page = {id: uid('info'), titulo: tr('resources.new_page', {}, 'Nova página'), html: tr('resources.new_page_html', {}, '<h2>Nova página</h2><p></p>'), data_criacao: now, data_atualizacao: now};
    tab.paginas = Array.isArray(tab.paginas) ? tab.paginas : [];
    tab.paginas.push(page);
    tab.data_atualizacao = now;
    activeInfoId = page.id;
    activeInfoPageIds[tab.id] = page.id;
    syncFlatInfo();
    renderInfoList();
    loadActiveInfo();
    scheduleInfoSave();
  }
  function deleteInfoSidePage(id){
    const tab = currentInfoTab();
    const pages = tab?.paginas || [];
    if (!tab || pages.length <= 1) { alert(tr('resources.keep_one_page', {}, 'Mantenha pelo menos uma página.')); return; }
    const page = pages.find(p => p.id === id) || currentInfo();
    const title = page?.titulo || tr('resources.untitled', {}, 'Sem título');
    if (!confirm(tr('resources.delete_page_confirm', {title}, `Excluir a página "${title}"?`))) return;
    tab.paginas = pages.filter(p => p.id !== page.id);
    tab.data_atualizacao = new Date().toISOString();
    activeInfoId = tab.paginas[0]?.id || null;
    activeInfoPageIds[tab.id] = activeInfoId;
    syncFlatInfo();
    renderInfoList();
    loadActiveInfo();
    scheduleInfoSave();
  }
  function scheduleCatalogPagesSave(tipo){
    clearTimeout(catalogPagesSaveTimers[tipo]);
    markResourceDirty(`catalogo:${tipo}`);
    setStatus(tr('resources.saving', {}, 'Salvando...'));
    catalogPagesSaveTimers[tipo] = setTimeout(() => {
      void persistResource(`catalogo:${tipo}`, async () => {
        // Absorver somente quando não houve outra edição durante o POST.
        const revision=writeState(`catalogo:${tipo}`).revision;
        const data=await postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/catalogo/${encodeURIComponent(tipo)}/paginas`, {paginas: state[catalogPagesKey(tipo)], items: projectCatalogItems(tipo)});
        if (revision===writeState(`catalogo:${tipo}`).revision &&
            [...resourceWrites].every(([name, write]) => name === `catalogo:${tipo}` || write.savedRevision === write.revision)) absorbServer(data);
      },tr('resources.catalog_saved', {}, 'Catálogo salvo')).catch(()=>{});
    }, 520);
  }
  function loadActiveInfo(){
    const page = currentInfo();
    const title = $('#tituloPaginaInfo');
    const editor = $('#editorInfoPagina');
    if (!page || !title || !editor) return;
    title.value = page.titulo || '';
    editor.innerHTML = page.html || '<p></p>';
    lastInfoRange = null;
    infoTyping.font = null;
    infoTyping.size = null;
    refreshInfoTypographyControls();
    infoVisualPagination?.schedule?.(true);
    infoRecovery.show(page);
    updateInfoToolbarState();
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
  function infoPayload(){
    syncFlatInfo();
    return {informacoes_abas: state.informacoes_abas, informacoes: state.informacoes};
  }
  function scheduleInfoSave(options = {}){
    const {captureEditor = true, rerenderSidebar = true} = options;
    if (captureEditor) saveCurrentInfoToState();
    if (rerenderSidebar) renderInfoList();
    infoRecovery.schedule();
    markResourceDirty('informacoes');
    clearTimeout(infoSaveTimer);
    setStatus(tr('resources.info_saving', {}, 'Salvando informações...'));
    infoSaveTimer = setTimeout(() => {
      void persistResource('informacoes', async () => {
        const snapshot=infoRecovery.snapshot();
        await postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/informacoes`, infoPayload());
        infoRecovery.confirm(snapshot);
      },tr('resources.info_saved', {}, 'Informações salvas')).catch(()=>{});
    }, 620);
  }
  $('#btnNovaPaginaInfo')?.addEventListener('click', () => addResourcePage('informacoes'));
  $('#btnNovaPaginaInfoLateral')?.addEventListener('click', () => addInfoSidePage());
  $('#btnNovaPaginaFluxo')?.addEventListener('click', () => addResourcePage('fluxo'));
  $('#btnNovaPaginaPersonagens')?.addEventListener('click', () => addResourcePage('personagens'));
  $('#btnNovaPaginaLugares')?.addEventListener('click', () => addResourcePage('lugares'));
  $('#btnNovaPaginaAnotacoes')?.addEventListener('click', () => addResourcePage('anotacoes'));
  $('#btnExcluirPaginaInfo')?.addEventListener('click', () => deleteInfoSidePage(activeInfoId));
  $('#tituloPaginaInfo')?.addEventListener('input', scheduleInfoSave);
  $('#editorInfoPagina')?.addEventListener('input', () => scheduleInfoSave({rerenderSidebar:false}));
  let imageInfoDestination = null;
  $('#btnInserirImagemInfo')?.addEventListener('click', () => {
    const range = getInfoSelectionRange() || lastInfoRange;
    imageInfoDestination = {
      tabId: activeInfoTabId, pageId: activeInfoId,
      range: range?.cloneRange() || null,
    };
    $('#inputImagemInfo')?.click();
  });
  function initInfoVisualPagination(){
    const editor = $('#editorInfoPagina');
    const stage = $('#infoPaperStage');
    const layers = $('#infoPaperLayers');
    if (!editor || !stage || !layers) return null;
    stage.classList.add('info-paginated');
    const GAP = 32;
    const DEBOUNCE_MS = 90;
    let pages = 0;
    let pageBoxes = [];
    let geometryKey = '';
    let lastActiveIndex = -1;
    let resizeWidth = 0;
    let scheduledFrame = 0;
    let debounceTimer = 0;
    let selectionFrame = 0;
    let running = false;
    let composing = false;

    function measure(){
      const width = stage.clientWidth;
      const paperHeight = width * (1056 / 816);
      const padding = parseFloat(getComputedStyle(editor).paddingTop) || 80;
      return {width, paperHeight, padding, step: paperHeight + GAP, contentHeight: paperHeight - padding * 2};
    }
    function createSheets(boxes) {
      const key = boxes.map((item) => `${item.top.toFixed(2)}:${item.height.toFixed(2)}`).join('|');
      if (key === geometryKey) return;
      pages = boxes.length;
      pageBoxes = boxes;
      geometryKey = key;
      lastActiveIndex = -1;
      // Reutilizar as folhas já existentes; substituir 300+ elementos em cada
      // recálculo causava custo de DOM e perda do destaque ativo.
      const existing = Array.from(layers.children);
      const extra = document.createDocumentFragment();
      boxes.forEach((box, i) => {
        let item = existing[i];
        if (!item) {
          item = document.createElement('div');
          item.className = 'info-paper-sheet';
          const folio = document.createElement('span');
          folio.className = 'info-paper-folio';
          folio.textContent = String(i + 1).padStart(2, '0');
          item.appendChild(folio);
          extra.appendChild(item);
        }
        if (item.style.top !== `${box.top}px`) item.style.top = `${box.top}px`;
        if (item.style.height !== `${box.height}px`) item.style.height = `${box.height}px`;
        item.classList.remove('is-active');
      });
      if (extra.childNodes.length) layers.appendChild(extra);
      while (layers.children.length > pages) layers.lastElementChild.remove();
      const last = boxes[boxes.length - 1];
      stage.style.minHeight = `${last.top + last.height}px`;
    }
    function updateActiveSheet(){
      if (running || !pages) return;
      const selection = window.getSelection();
      if (!selection?.rangeCount || !editor.contains(selection.anchorNode)) return;
      const range = selection.getRangeAt(0).cloneRange();
      range.collapse(true);
      const rect = range.getClientRects()[0];
      const node = selection.anchorNode;
      const el = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
      const block = el?.closest('#editorInfoPagina > *') || el;
      const top = rect?.height ? rect.top : (block?.getBoundingClientRect().top || 0);
      const offset = Math.max(0, top - stage.getBoundingClientRect().top);
      const located = pageBoxes.findIndex((box) => offset < box.top + box.height + GAP / 2);
      const index = located < 0 ? pages - 1 : located;
      if (index === lastActiveIndex) return;
      const previousIndex = lastActiveIndex;
      lastActiveIndex = index;
      // Atualiza apenas a folha anterior e a atual, não todas as folhas.
      if (previousIndex >= 0) layers.children[previousIndex]?.classList.remove('is-active');
      layers.children[index]?.classList.add('is-active');
    }
    const blocksSheet = document.createElement('style');
    blocksSheet.id = 'info-visual-page-breaks';
    document.head.appendChild(blocksSheet);
    function recalculate() {
      scheduledFrame = 0;
      if (running || composing || !editor.isConnected) return;
      running = true;
      try {
        const metrics = measure();
        if (!metrics.width || metrics.contentHeight < 120) return;
        // O documento continua com UMA árvore editável. As quebras são
        // margens CSS descartáveis, não nós persistidos no conteúdo.
        if (blocksSheet.textContent) blocksSheet.textContent = '';
        const blocks = Array.from(editor.children).filter((el) => el instanceof HTMLElement);
        const editorTop = editor.getBoundingClientRect().top;
        const boxes = [{top: 0, height: metrics.paperHeight}];
        let pageIndex = 0;
        let extraBefore = 0;
        const rules = [];
        for (let i = 0; i < blocks.length; i += 1) {
          const block = blocks[i];
          const rect = block.getBoundingClientRect();
          const height = rect.height;
          let top = rect.top - editorTop + extraBefore;
          let bottom = rect.bottom - editorTop + extraBefore;
          let box = boxes[pageIndex];
          const bottomLimit = box.top + box.height - metrics.padding;
          const oversized = height > metrics.contentHeight + 2;
          if (bottom > bottomLimit + 2 &&
              (!oversized || top > box.top + metrics.padding + 3)) {
            // Parágrafos que cabem numa folha são movidos por inteiro.
            // Parágrafos maiores que a folha ganham uma folha elástica:
            // nunca atravessam o vão cinza entre duas páginas.
            const next = {top: box.top + box.height + GAP, height: metrics.paperHeight};
            boxes.push(next);
            pageIndex = boxes.length - 1;
            box = next;
            const push = Math.max(0, box.top + metrics.padding - top);
            if (push > 0) {
              // Considerar colapso de margens adjacentes no HTML original.
              // Consultar margem só nas quebras de folha, sem alterar
              // a regra original de colapso das margens adjacentes.
              const ownMargin = parseFloat(getComputedStyle(block).marginTop) || 0;
              const previous = blocks[i - 1];
              const previousBottomMargin = previous ? (parseFloat(getComputedStyle(previous).marginBottom) || 0) : 0;
              const margin = Math.max(ownMargin, previousBottomMargin) + push;
              rules.push(`.pagina-recursos-projeto-shell #editorInfoPagina > :nth-child(${i + 1}) { margin-top: ${Math.ceil(margin)}px !important; }`);
              extraBefore += push;
              top += push;
              bottom += push;
            }
          }
          // Bloco muito alto não pode ser cortado porque isso deslocaria
          // a seleção, o histórico e a digitação dentro de contenteditable.
          // Aumentar APENAS sua folha mantém todas as linhas sobre papel.
          if (bottom > box.top + box.height - metrics.padding) {
            box.height = Math.max(box.height, Math.ceil(bottom - box.top + metrics.padding + 2));
          }
        }
        blocksSheet.textContent = rules.join('\n');
        const actualBottom = blocks.length
          ? blocks[blocks.length - 1].getBoundingClientRect().bottom - editor.getBoundingClientRect().top
          : metrics.padding;
        const last = boxes[boxes.length - 1];
        if (actualBottom + metrics.padding > last.top + last.height) {
          last.height = Math.ceil(actualBottom + metrics.padding - last.top + 2);
        }
        createSheets(boxes);
      } finally {
        running = false;
        updateActiveSheet();
      }
    }
    function schedule(immediate = false){
      if (composing) return;
      if (debounceTimer) clearTimeout(debounceTimer);
      if (scheduledFrame) cancelAnimationFrame(scheduledFrame);
      if (immediate) scheduledFrame = requestAnimationFrame(recalculate);
      else debounceTimer = setTimeout(() => {
        debounceTimer = 0;
        scheduledFrame = requestAnimationFrame(recalculate);
      }, DEBOUNCE_MS);
    }
    function scheduleActiveSheet(){
      if (selectionFrame) return;
      selectionFrame = requestAnimationFrame(() => {
        selectionFrame = 0;
        updateActiveSheet();
      });
    }
    editor.addEventListener('input', () => schedule());
    editor.addEventListener('paste', () => schedule());
    editor.addEventListener('keyup', scheduleActiveSheet);
    editor.addEventListener('click', scheduleActiveSheet);
    editor.addEventListener('compositionstart', () => { composing = true; });
    editor.addEventListener('compositionend', () => { composing = false; schedule(); });
    document.addEventListener('selectionchange', scheduleActiveSheet);
    const observer = new MutationObserver(() => schedule());
    observer.observe(editor, {childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['class', 'style']});
    if (window.ResizeObserver) {
      const resize = new ResizeObserver(() => {
        const width = stage.clientWidth;
        if (Math.abs(width - resizeWidth) > 1) { resizeWidth = width; schedule(true); }
      });
      resize.observe(stage);
    } else {
      window.addEventListener('resize', () => schedule(), {passive: true});
    }
    if (document.fonts?.ready) document.fonts.ready.then(() => schedule(true));
    schedule(true);
    return { schedule, updateActiveSheet };
  }
  const infoVisualPagination = initInfoVisualPagination();

  $('#inputImagemInfo')?.addEventListener('change', async (ev) => {
    const file = ev.target.files?.[0];
    ev.target.value = '';
    if (!file) return;
    const destination = imageInfoDestination;
    imageInfoDestination = null;
    try {
      const dataUrl = await fileToDataUrl(file);
      const editor = $('#editorInfoPagina');
      if (!editor || !destination || activeInfoTabId !== destination.tabId || activeInfoId !== destination.pageId) {
        const message = (document.documentElement.lang || 'pt').toLowerCase().startsWith('pt')
          ? 'A página mudou antes da imagem terminar de carregar; selecione a imagem novamente.'
          : 'The page changed before the image finished loading; please select the image again.';
        setStatus(message, 'erro');
        return;
      }
      if (destination.range && editor.contains(destination.range.startContainer) && editor.contains(destination.range.endContainer)) {
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(destination.range);
      }
      editor.focus({preventScroll:true});
      document.execCommand('insertImage', false, dataUrl);
      scheduleInfoSave();
    } catch (err) { setStatus(err.message || String(err),'erro'); }
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
    Object.values(catalogPagesSaveTimers).forEach(clearTimeout);
    saveCurrentInfoToState();
    setStatus(tr('resources.saving', {}, 'Salvando...'));
    infoRecovery.writeNow();
    markResourceDirty('informacoes');
    await persistResource('informacoes', async () => {
      const snapshot=infoRecovery.snapshot();
      await postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/informacoes`, infoPayload());
      infoRecovery.confirm(snapshot);
    },tr('resources.info_saved', {}, 'Informações salvas'));
    markResourceDirty('fluxo');
    await persistResource('fluxo',()=>postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/fluxo`, {fluxos: state.fluxos}),tr('resources.flow_saved', {}, 'Fluxo salvo'));
    for (const tipo of CATALOG_TYPES) {
      markResourceDirty(`catalogo:${tipo}`);
      await persistResource(`catalogo:${tipo}`,()=>postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/catalogo/${encodeURIComponent(tipo)}/paginas`, {paginas: state[catalogPagesKey(tipo)], items: projectCatalogItems(tipo)}),tr('resources.catalog_saved', {}, 'Catálogo salvo'));
    }
  }

  async function salvarBlobComJanelaDoNavegador(blob, nomeArquivo, opcoes = {}){
    if (typeof window.showSaveFilePicker !== 'function' || !window.isSecureContext) return false;
    const extensao = opcoes.extensao || '.gutr';
    const mime = opcoes.mime || 'application/octet-stream';
    const descricao = opcoes.descricao || 'Gutenberg Resources';
    try {
      const handle = await window.showSaveFilePicker({
        id: opcoes.id || 'gutenberg-recursos',
        suggestedName: nomeArquivo,
        types: [{ description: descricao, accept: { [mime]: [extensao] } }],
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

  async function baixarBlobComFallback(blob, nomeArquivo, opcoes = {}){
    const picker = await salvarBlobComJanelaDoNavegador(blob, nomeArquivo, opcoes);
    if (picker === true) return {ok:true};
    if (picker === 'cancelado' && !opcoes.fallbackAoCancelar) return {ok:false, cancelado:true};
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

  async function exportarRecursosPdf(){
    try {
      await flushResourceAutosaves();
      setStatus(tr('resources.export_pdf_preparing', {}, 'Preparando PDF de recursos...'));
      const isDesktopSave = Boolean(window.pywebview?.api?.saveExportedFile);
      const url = `/projetos/${encodeURIComponent(slug)}/recursos/exportar-pdf${isDesktopSave ? '?desktop_save=1' : ''}`;
      const resp = await fetch(url);
      if (!resp.ok) {
        let mensagem = tr('resources.export_pdf_error', {}, 'Não foi possível exportar os recursos em PDF.');
        try { const erro = await resp.json(); mensagem = erro.erro || erro.mensagem || mensagem; } catch (_) {}
        throw new Error(mensagem);
      }
      if (isDesktopSave) {
        const dados = await resp.json();
        if (!dados?.ok || !dados?.arquivo) throw new Error(dados?.erro || tr('resources.export_pdf_error', {}, 'Não foi possível exportar os recursos em PDF.'));
        const resultado = await window.pywebview.api.saveExportedFile(dados.arquivo, dados.nome, dados.pasta_inicial);
        if (!resultado?.ok) {
          if (resultado?.cancelado) { setStatus(tr('js.export_cancelled', {}, 'Exportação cancelada')); return; }
          throw new Error(resultado?.erro || tr('resources.export_pdf_error', {}, 'Não foi possível exportar os recursos em PDF.'));
        }
      } else {
        const blob = await resp.blob();
        const dispo = resp.headers.get('Content-Disposition') || '';
        const m = dispo.match(/filename\*?=(?:UTF-8''|\")?([^";]+)/i);
        const nomeArquivo = m ? decodeURIComponent(m[1].replace(/"/g,'')) : `${slug || 'projeto'}_recursos.pdf`;
        const download = await baixarBlobComFallback(blob, nomeArquivo, {id:'gutenberg-recursos-pdf', extensao:'.pdf', mime:'application/pdf', descricao:'PDF', fallbackAoCancelar:true});
        if (download?.cancelado) { setStatus(tr('js.export_cancelled', {}, 'Exportação cancelada')); return; }
      }
      setStatus(tr('resources.export_pdf_success', {}, 'Recursos exportados em PDF'));
    } catch (err) {
      setStatus(err.message || tr('resources.export_pdf_error', {}, 'Não foi possível exportar os recursos em PDF.'), 'erro');
      alert(err.message || tr('resources.export_pdf_error', {}, 'Não foi possível exportar os recursos em PDF.'));
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
  function selectedInfoBlocks(range){
    const editor = getInfoEditor();
    if (!editor || !range) return [];
    if (range.collapsed) {
      const node = range.startContainer;
      const el = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
      const block = el?.closest('p,h1,h2,h3,li');
      return block && editor.contains(block) ? [block] : [];
    }
    return [...editor.querySelectorAll('p,h1,h2,h3,li')].filter((block) => range.intersectsNode(block));
  }
  function applyInfoFormat({command = '', block = ''} = {}){
    const editor = getInfoEditor();
    if (!editor) return;
    restoreInfoRange();
    editor.focus({preventScroll:true});
    const range = getInfoSelectionRange();
    if (block) {
      const selected = selectedInfoBlocks(range);
      // Como no roteiro: clicar no tipo já ativo devolve ao parágrafo.
      const allActive = block !== 'p' && selected.length > 0 && selected.every((el) => el.tagName.toLowerCase() === block);
      document.execCommand('formatBlock', false, allActive ? 'p' : block);
    }
    // Os comandos nativos de negrito/itálico/sublinhado/lista são toggles.
    if (command) document.execCommand(command, false, null);
    saveInfoRange();
    scheduleInfoSave();
    updateInfoToolbarState();
  }
  const infoTipografia = window.GutenbergTipografia;
  const infoFonteSelect = $('#seletorFonteInfo');
  const infoTamanhoSelect = $('#seletorTamanhoFonteInfo');
  const infoTyping = {font:null, size:null};
  function selectionHasMixedTypography(range, kind){
    const editor = getInfoEditor();
    if (!editor || !range || range.collapsed) return false;
    const values = new Set();
    // Percorrer só o ancestral comum da seleção: evita varrer o documento
    // inteiro enquanto o usuário move o cursor numa página longa.
    const common = range.commonAncestorContainer;
    const scope = common.nodeType === Node.TEXT_NODE ? common.parentNode : common;
    const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (!node.textContent?.trim() || !range.intersectsNode(node)) continue;
      const value = kind === 'font'
        ? (infoTipografia.classAt(node,editor,infoTipografia.isFont) || 'fonte-arial')
        : infoTipografia.nearestSizeInPoints(node,editor);
      values.add(value);
      if (values.size > 1) return true;
    }
    return false;
  }
  function ensureInfoMixedPlaceholder(select, kind){
    if (!select || select.querySelector('option[value=""]')) return;
    const option = document.createElement('option');
    option.value = '';
    option.disabled = true;
    option.textContent = kind === 'font' ? 'Várias fontes' : 'Vários tamanhos';
    select.prepend(option);
  }
  function refreshInfoTypographyControls(){
    const editor = getInfoEditor();
    if (!editor || !infoTipografia) return;
    const range = getInfoSelectionRange() || lastInfoRange;
    const node = range?.startContainer || editor;
    if (infoFonteSelect && document.activeElement !== infoFonteSelect) {
      if (range && selectionHasMixedTypography(range,'font')) {
        ensureInfoMixedPlaceholder(infoFonteSelect,'font');
        infoFonteSelect.value = '';
      } else {
        const font = infoTipografia.classAt(node,editor,infoTipografia.isFont) || infoTyping.font || 'fonte-arial';
        if (infoTipografia.fonts.includes(font)) infoFonteSelect.value = font;
      }
    }
    if (infoTamanhoSelect && document.activeElement !== infoTamanhoSelect) {
      if (range && selectionHasMixedTypography(range,'size')) {
        ensureInfoMixedPlaceholder(infoTamanhoSelect,'size');
        infoTamanhoSelect.value = '';
      } else {
        const size = infoTipografia.nearestSizeInPoints(node,editor);
        if (infoTipografia.sizeClass(size)) infoTamanhoSelect.value = size;
      }
    }
  }
  function changeInfoTypography(kind, value, savedRange){
    const editor = getInfoEditor();
    const klass = kind === 'font' ? (infoTipografia?.isFont(value) ? value : null) : infoTipografia?.sizeClass(value);
    if (!editor || !klass) return;
    const range = savedRange || lastInfoRange || getInfoSelectionRange();
    if (range && editor.contains(range.startContainer) && editor.contains(range.endContainer)) {
      const sel = window.getSelection();
      sel.removeAllRanges();sel.addRange(range.cloneRange());
      editor.focus({preventScroll:true});
      const current = getInfoSelectionRange();
      const otherPredicate = kind === 'font' ? infoTipografia.isSize : infoTipografia.isFont;
      const other = infoTipografia.classAt(current?.startContainer,editor,otherPredicate);
      if (kind === 'font') { infoTyping.font = klass; if (other) infoTyping.size = other; }
      else { infoTyping.size = klass; if (other) infoTyping.font = other; }
      if (current && !current.collapsed) {
        if (infoTipografia.applyToSelection(editor,current,klass,kind==='font' ? infoTipografia.isFont : infoTipografia.isSize)) {
          // A paginação é apenas visual: não inserir páginas no HTML persistido.
          editor.dispatchEvent(new Event('input',{bubbles:true}));
        }
      }
      saveInfoRange();
    } else if (kind === 'font') infoTyping.font = klass;
    else infoTyping.size = klass;
    refreshInfoTypographyControls();
  }
  function insertInfoStyledText(text){
    const editor = getInfoEditor();
    const range = getInfoSelectionRange();
    if (!editor || !range || !text) return false;
    if (!range.collapsed) {range.deleteContents();range.collapse(true);}
    const desiredFont=infoTyping.font, desiredSize=infoTyping.size;
    const matches = (node) => node?.nodeType===Node.TEXT_NODE &&
      infoTipografia.classAt(node,editor,infoTipografia.isFont)===desiredFont &&
      infoTipografia.classAt(node,editor,infoTipografia.isSize)===desiredSize;
    let target=null,offset=0;
    const node=range.startContainer;
    if (matches(node)) {target=node;offset=range.startOffset;}
    else if (node.nodeType===Node.ELEMENT_NODE) {
      const before=node.childNodes[range.startOffset-1];
      const after=node.childNodes[range.startOffset];
      const leaf=(root,first)=>{while(root&&(first?root.firstChild:root.lastChild))root=first?root.firstChild:root.lastChild;return root;};
      const prev=leaf(before,false),next=leaf(after,true);
      if(matches(prev)){target=prev;offset=prev.length;}
      else if(matches(next)){target=next;offset=0;}
    }
    const nextRange=document.createRange();
    if(target){target.insertData(offset,text);nextRange.setStart(target,offset+text.length);}
    else {
      const span=document.createElement('span');
      span.className=[desiredFont,desiredSize].filter(Boolean).join(' ');
      const textNode=document.createTextNode(text);
      span.appendChild(textNode);
      range.insertNode(span);
      nextRange.setStart(textNode,text.length);
    }
    nextRange.collapse(true);
    const selection=window.getSelection();selection.removeAllRanges();selection.addRange(nextRange);
    editor.dispatchEvent(new InputEvent('input',{inputType:'insertText',data:text,bubbles:true}));
    saveInfoRange();
    return true;
  }
  function bindInfoTypography(){
    if (!infoTipografia) return;
    [ [infoFonteSelect, 'font'],[infoTamanhoSelect,'size'] ].forEach(([select,kind])=>{
      if (!select) return;
      let captured=null;
      function capture(){const range=getInfoSelectionRange();if(range){captured=range.cloneRange();lastInfoRange=range.cloneRange();}}
      select.addEventListener('pointerdown',capture);
      select.addEventListener('focus',()=>{if(!captured)capture();});
      select.addEventListener('change',()=>{
        const range=captured||lastInfoRange;
        captured=null;
        changeInfoTypography(kind,select.value,range);
      });
    });
    getInfoEditor()?.addEventListener('beforeinput',(ev)=>{
      if (ev.isComposing || ev.inputType!=='insertText' || typeof ev.data!=='string') return;
      if (!infoTyping.font && !infoTyping.size) return;
      ev.preventDefault();
      insertInfoStyledText(ev.data);
    });
    getInfoEditor()?.addEventListener('keyup',refreshInfoTypographyControls);
    getInfoEditor()?.addEventListener('mouseup',refreshInfoTypographyControls);
    document.addEventListener('selectionchange',()=>{
      if (getInfoSelectionRange()) refreshInfoTypographyControls();
    });
    refreshInfoTypographyControls();
  }
  function updateInfoToolbarState(){
    const editor = getInfoEditor();
    const range = getInfoSelectionRange();
    if (!editor || !range) return;
    const blocks = selectedInfoBlocks(range);
    $$('[data-info-comando], [data-info-bloco]').forEach(btn => {
      const command = btn.dataset.infoComando;
      let pressed = false;
      if (btn.dataset.infoBloco) pressed = blocks.length > 0 && blocks.every((b) => b.tagName.toLowerCase() === btn.dataset.infoBloco.toLowerCase());
      else if (command === 'insertUnorderedList') pressed = blocks.length > 0 && blocks.every((b) => b.tagName === 'LI' && b.parentElement?.tagName === 'UL');
      else if (['bold','italic','underline'].includes(command)) {
        // O comando nativo pode devolver false após voltar o foco do toolbar.
        // No cursor, a estrutura HTML determina o estado real da formatação.
        const tags = command === 'bold' ? ['B','STRONG']
          : command === 'italic' ? ['I','EM'] : ['U'];
        const isFormatted = (node) => {
          let el = node?.nodeType === Node.TEXT_NODE ? node.parentElement : node;
          while (el && el !== editor) {
            if (tags.includes(el.tagName)) return true;
            el = el.parentElement;
          }
          return false;
        };
        if (range.collapsed) {
          const container = range.startContainer;
          const node = container.nodeType === Node.ELEMENT_NODE && container.childNodes.length
            ? (container.childNodes[Math.max(0, range.startOffset - 1)] || container.childNodes[range.startOffset] || container)
            : container;
          pressed = isFormatted(node);
          if (!pressed) {
            try { pressed = document.queryCommandState(command); } catch (_) { pressed = false; }
          }
        } else {
          const scope = range.commonAncestorContainer;
          const walker = document.createTreeWalker(scope.nodeType === Node.TEXT_NODE ? scope.parentNode : scope, NodeFilter.SHOW_TEXT);
          const nodes = [];
          let node;
          while ((node = walker.nextNode())) {
            if (!node.textContent?.length || !range.intersectsNode(node)) continue;
            nodes.push(node);
          }
          pressed = nodes.length > 0 && nodes.every(isFormatted);
          if (!nodes.length) {
            try { pressed = document.queryCommandState(command); } catch (_) { pressed = false; }
          }
        }
      }
      btn.classList.toggle('ativo', !!pressed);
      btn.setAttribute('aria-pressed', pressed ? 'true' : 'false');
    });
  }
  function bindInfoToolbar(){
    $$('[data-info-comando], [data-info-bloco]').forEach(btn => {
      btn.addEventListener('mousedown', (ev) => { ev.preventDefault(); restoreInfoRange(); });
      btn.addEventListener('click', () => {
        applyInfoFormat({command: btn.dataset.infoComando || '', block: btn.dataset.infoBloco || ''});
        updateInfoToolbarState();
      });
    });
    const editor = getInfoEditor();
    if (!editor) return;
    editor.addEventListener('keyup', () => {saveInfoRange();updateInfoToolbarState();});
    editor.addEventListener('mouseup', () => {saveInfoRange();updateInfoToolbarState();});
    editor.addEventListener('focus', () => {saveInfoRange();updateInfoToolbarState();});
    editor.addEventListener('input', updateInfoToolbarState);
    editor.addEventListener('keydown', (ev) => {
      if (!ev.altKey || ev.ctrlKey || ev.metaKey || ev.shiftKey) return;
      const key = ev.key.toLowerCase();
      const commands = {b:{command:'bold'},i:{command:'italic'},u:{command:'underline'},l:{command:'insertUnorderedList'},
        p:{block:'p'},'1':{block:'h1'},'2':{block:'h2'},'3':{block:'h3'}};
      if (!commands[key]) return;
      ev.preventDefault();
      applyInfoFormat(commands[key]);
      updateInfoToolbarState();
    });
    document.addEventListener('selectionchange', () => {
      const range = getInfoSelectionRange();
      if (range) {lastInfoRange = range.cloneRange();updateInfoToolbarState();}
    });
    bindInfoTypography();
    updateInfoToolbarState();
  }

  function nodeById(id){ return currentFlow().nodes.find(n => n.id === id); }
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
  let flowLinesFrame = 0;
  function scheduleFlowLines(){
    if (flowLinesFrame) return;
    flowLinesFrame = requestAnimationFrame(() => {
      flowLinesFrame = 0;
      renderFlowLines();
    });
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
    el.querySelector('.fluxo-node-text')?.addEventListener('input', (ev) => { node.texto = ev.target.value; scheduleFlowSave(); scheduleFlowLines(); });
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
      scheduleFlowLines();
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
    scheduleFlowLines();
  }
  function renderFlow(){
    const wrap = $('#fluxoNodes');
    if (!wrap) return;
    wrap.innerHTML = '';
    currentFlow().nodes.forEach(node => wrap.appendChild(createNodeElement(node)));
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
    const flow = currentFlow();
    const elements = new Map($$('.fluxo-node', $('#fluxoNodes')).map(el => [el.dataset.nodeId, el]));
    const nodes = new Map();
    flow.nodes.forEach(node => {
      const el = elements.get(node.id);
      if (el) { node.width = el.offsetWidth || node.width || 240; node.height = el.offsetHeight || node.height || 150; }
      nodes.set(node.id,node);
    });
    const fragment = document.createDocumentFragment();
    flow.edges.forEach(edge => {
      const a = nodes.get(edge.from), b = nodes.get(edge.to);
      if (!a || !b) return;
      const p1 = sidePoint(a, edge.fromSide || 'right');
      const p2 = sidePoint(b, edge.toSide || 'left');
      const dx = Math.max(70, Math.abs(p2.x - p1.x) * .45);
      const c1 = (edge.fromSide === 'left') ? {x:p1.x-dx,y:p1.y} : (edge.fromSide === 'right') ? {x:p1.x+dx,y:p1.y} : {x:p1.x,y:p1.y + (edge.fromSide === 'top' ? -dx : dx)};
      const c2 = (edge.toSide === 'left') ? {x:p2.x-dx,y:p2.y} : (edge.toSide === 'right') ? {x:p2.x+dx,y:p2.y} : {x:p2.x,y:p2.y + (edge.toSide === 'top' ? -dx : dx)};
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('class','fluxo-edge');
      path.setAttribute('d', `M ${p1.x} ${p1.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${p2.x} ${p2.y}`);
      fragment.appendChild(path);
    });
    svg.appendChild(fragment);
    updateFlowHandleStates();
  }
  function edgeUsesHandle(edge, nodeId, side){
    return (edge.from === nodeId && (edge.fromSide || 'right') === side) || (edge.to === nodeId && (edge.toSide || 'left') === side);
  }
  function handleHasEdge(nodeId, side){
    return currentFlow().edges.some(edge => edgeUsesHandle(edge, nodeId, side));
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
    const before = currentFlow().edges.length;
    currentFlow().edges = currentFlow().edges.filter(edge => !edgeUsesHandle(edge, nodeId, side));
    return before - currentFlow().edges.length;
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
      const exists = currentFlow().edges.some(e => e.from === selectedHandle.nodeId && e.to === nodeId && e.fromSide === selectedHandle.side && e.toSide === side);
      if (!exists) currentFlow().edges.push({id: uid('edge'), from: selectedHandle.nodeId, to: nodeId, fromSide: selectedHandle.side, toSide: side});
      renderFlowLines(); scheduleFlowSave();
    }
    selectedHandle = null;
  }
  $('#btnLimparConexaoFluxo')?.addEventListener('click', () => {
    const removed = currentFlow().edges.length;
    clearSelectedFlowHandle();
    if (!removed) {
      updateFlowHandleStates();
      setStatus(tr('resources.no_connections_to_cancel', {}, 'Nenhuma ligação para cancelar'));
      return;
    }
    currentFlow().edges = [];
    renderFlowLines();
    scheduleFlowSave();
    setStatus(tr('resources.all_connections_cancelled', {}, 'Todas as ligações foram canceladas'));
  });
  $('#btnNovoNodeFluxo')?.addEventListener('click', () => {
    const wrap = $('#fluxoCanvasWrap');
    const node = {id: uid('node'), x: (wrap?.scrollLeft || 0) + 120, y: (wrap?.scrollTop || 0) + 120, width: 240, height: 150, titulo: tr('resources.new_balloon', {}, 'Novo balão'), texto: ''};
    currentFlow().nodes.push(node);
    renderFlow(); scheduleFlowSave();
  });
  function deleteNode(id){
    if (!confirm(tr('resources.delete_balloon_confirm', {}, 'Excluir este balão e suas ligações?'))) return;
    currentFlow().nodes = currentFlow().nodes.filter(n => n.id !== id);
    currentFlow().edges = currentFlow().edges.filter(e => e.from !== id && e.to !== id);
    renderFlow(); scheduleFlowSave();
  }
  function scheduleFlowSave(){
    clearTimeout(flowSaveTimer);
    markResourceDirty('fluxo');
    setStatus(tr('resources.flow_saving', {}, 'Salvando fluxo...'));
    flowSaveTimer = setTimeout(() => {
      void persistResource('fluxo',()=>postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/fluxo`, {fluxos: state.fluxos}),tr('resources.flow_saved', {}, 'Fluxo salvo')).catch(()=>{});
    }, 520);
  }

  function renderCatalogs(){
    renderCatalogList('personagens', currentCatalogItems('personagens'), $('#listaPersonagensProjeto'), '👤');
    renderCatalogList('lugares', currentCatalogItems('lugares'), $('#listaLugaresProjeto'), '📍');
    renderCatalogList('anotacoes', currentCatalogItems('anotacoes'), $('#listaAnotacoesProjeto'), '📝');
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
    const payload = {id: $('#catalogoRecursosId').value, pagina_id: activeCatalogPageIds[tipo], nome: $('#catalogoRecursosNome').value.trim(), descricao: $('#catalogoRecursosDescricao').value.trim(), imagem: tipo === 'anotacoes' ? '' : imageCatalogoAtual};
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
      const data = await postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/catalogo/${encodeURIComponent(tipo)}/excluir`, {id: item.id, nome: item.nome, pagina_id: item.pagina_id || activeCatalogPageIds[tipo]});
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
  $('#btnExportarRecursosPdf')?.addEventListener('click', exportarRecursosPdf);
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

  renderAllPageTabs();
  loadActiveInfo();
  renderFlow();
  renderCatalogs();
})();
