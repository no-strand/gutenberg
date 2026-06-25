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
      if (page.id === activeId) {
        const input = document.createElement('input');
        input.className = 'resource-page-tab-input';
        input.value = page.titulo || tab.title;
        input.maxLength = 60;
        input.addEventListener('click', (ev) => ev.stopPropagation());
        input.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') input.blur(); });
        input.addEventListener('input', () => { renameResourcePage(tipo, page.id, input.value, false); });
        input.addEventListener('blur', () => renderResourcePageTabs(tipo));
        tab.appendChild(input);
      } else {
        const span = document.createElement('span');
        span.className = 'resource-page-tab-title';
        span.textContent = page.titulo || tab.title;
        tab.appendChild(span);
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
    setStatus(tr('resources.saving', {}, 'Salvando...'));
    catalogPagesSaveTimers[tipo] = setTimeout(async () => {
      try {
        const data = await postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/catalogo/${encodeURIComponent(tipo)}/paginas`, {paginas: state[catalogPagesKey(tipo)], items: projectCatalogItems(tipo)});
        absorbServer(data);
        setStatus(tr('resources.catalog_saved', {}, 'Catálogo salvo'));
      } catch (err) { setStatus(err.message, 'erro'); }
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
    clearTimeout(infoSaveTimer);
    setStatus(tr('resources.info_saving', {}, 'Salvando informações...'));
    infoSaveTimer = setTimeout(async () => {
      try {
        await postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/informacoes`, infoPayload());
        setStatus(tr('resources.info_saved', {}, 'Informações salvas'));
      } catch (err) { setStatus(err.message, 'erro'); }
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
    Object.values(catalogPagesSaveTimers).forEach(clearTimeout);
    saveCurrentInfoToState();
    setStatus(tr('resources.saving', {}, 'Salvando...'));
    await postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/informacoes`, infoPayload());
    await postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/fluxo`, {fluxos: state.fluxos});
    for (const tipo of CATALOG_TYPES) {
      await postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/catalogo/${encodeURIComponent(tipo)}/paginas`, {paginas: state[catalogPagesKey(tipo)], items: projectCatalogItems(tipo)});
    }
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
    currentFlow().nodes.forEach(node => {
      const el = $(`[data-node-id="${CSS.escape(node.id)}"]`);
      if (el) { node.width = el.offsetWidth || node.width || 240; node.height = el.offsetHeight || node.height || 150; }
    });
    currentFlow().edges.forEach(edge => {
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
    setStatus(tr('resources.flow_saving', {}, 'Salvando fluxo...'));
    flowSaveTimer = setTimeout(async () => {
      try {
        await postJSON(`/api/projetos/${encodeURIComponent(slug)}/recursos/fluxo`, {fluxos: state.fluxos});
        setStatus(tr('resources.flow_saved', {}, 'Fluxo salvo'));
      } catch (err) { setStatus(err.message, 'erro'); }
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
