/** Modal de visualização dos recursos do projeto, usado nos editores. */
(function(){
  const cfg = window.EDITOR_CONFIG || {};
  const slug = cfg.slug || window.PROJETO_SLUG || '';
  if (!slug) return;
  const modal = document.getElementById('modalRecursosProjeto');
  const openButtons = [document.getElementById('btnAbrirRecursosProjeto'), document.getElementById('btnAbrirRecursosProjetoRoteiro')].filter(Boolean);
  if (!modal || !openButtons.length) return;
  const infoDetailModal = document.getElementById('modalRecursosInfoDetalhe');
  const catalogDetailModal = document.getElementById('modalRecursosCatalogoDetalhe');
  let cache = null;
  let activeTab = 'informacoes';
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  function tr(key, vars = {}, fallback = '') {
    const value = typeof window.t === 'function' ? window.t(key, vars) : key;
    return value && value !== key ? value : (fallback || key);
  }
  function escapeHtml(value){ return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
  function safeInfoHtml(value){ return String(value || `<p>${tr('resources.no_content', {}, 'Sem conteúdo.')}</p>`); }
  function openElement(el){ el?.classList.remove('oculto'); }
  function closeElement(el){ el?.classList.add('oculto'); }
  function openModal(tab = ''){ if (tab) switchTab(tab); modal.classList.remove('oculto'); loadResources(); }
  function closeModal(){ modal.classList.add('oculto'); closeElement(infoDetailModal); closeElement(catalogDetailModal); }
  function setStatus(text){ const el = $('#recursosViewStatus'); if (el) el.textContent = text || ''; }
  function switchTab(tab){
    activeTab = tab;
    $$('[data-recursos-view-tab]', modal).forEach(btn => btn.classList.toggle('ativo', btn.dataset.recursosViewTab === tab));
    $$('[data-recursos-view-panel]', modal).forEach(panel => panel.classList.toggle('ativo', panel.dataset.recursosViewPanel === tab));
    if (tab === 'fluxo') requestAnimationFrame(() => renderFlowView(cache?.fluxo || {nodes:[], edges:[]}));
  }
  async function loadResources(){
    if (cache) { renderAll(cache); return; }
    setStatus(tr('resources.loading_project_resources', {}, 'Carregando recursos do projeto...'));
    try {
      const resp = await fetch(`/api/projetos/${encodeURIComponent(slug)}/recursos`, {cache:'no-store'});
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || data.ok === false) throw new Error(data.erro || tr('resources.load_failed', {}, 'Falha ao carregar.'));
      cache = data;
      renderAll(data);
      setStatus('');
    } catch (err) {
      setStatus(err.message || tr('resources.load_failed', {}, 'Falha ao carregar.'));
    }
  }
  function renderAll(data){
    const subtitulo = $('#recursosProjetoSubtitulo');
    if (subtitulo) subtitulo.textContent = data?.projeto?.titulo ? tr('resources.project_prefix', {project: data.projeto.titulo}, `Projeto: ${data.projeto.titulo}`) : tr('resources.hero_desc', {}, 'Informações, fluxo, personagens, lugares e anotações.');
    renderInfo(data.informacoes || []);
    renderFlowView(data.fluxo || {nodes:[], edges:[]});
    renderCatalogCards(data.personagens || [], $('#recursosViewPersonagens'), 'personagens', '👤');
    renderCatalogCards(data.lugares || [], $('#recursosViewLugares'), 'lugares', '📍');
    renderCatalogCards(data.anotacoes || [], $('#recursosViewAnotacoes'), 'anotacoes', '📝');
  }
  function makeButtonCard(title, className = 'recursos-view-title-card'){
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = className;
    btn.title = title || tr('resources.untitled', {}, 'Sem título');
    const h3 = document.createElement('h3');
    h3.textContent = title || tr('resources.untitled', {}, 'Sem título');
    btn.appendChild(h3);
    return btn;
  }
  function renderInfo(pages){
    const box = $('#recursosViewInformacoes');
    if (!box) return;
    box.innerHTML = '';
    if (!pages.length) { box.innerHTML = `<div class="vazio-recursos">${escapeHtml(tr('resources.no_info', {}, 'Nenhuma informação cadastrada.'))}</div>`; return; }
    pages.forEach(page => {
      const card = makeButtonCard(page.titulo || tr('resources.untitled', {}, 'Sem título'), 'recursos-view-title-card recursos-view-info-title-card');
      card.addEventListener('click', () => openInfoDetail(page));
      box.appendChild(card);
    });
  }
  function openInfoDetail(page){
    if (!infoDetailModal) return;
    const titleEl = $('#recursosInfoDetalheTitulo', infoDetailModal);
    const contentEl = $('#recursosInfoDetalheConteudo', infoDetailModal);
    if (titleEl) { titleEl.textContent = page?.titulo || tr('resources.untitled', {}, 'Sem título'); titleEl.title = page?.titulo || tr('resources.untitled', {}, 'Sem título'); }
    if (contentEl) contentEl.innerHTML = safeInfoHtml(page?.html);
    openElement(infoDetailModal);
  }
  function renderCatalogCards(items, box, tipo, emoji){
    if (!box) return;
    box.innerHTML = '';
    if (!items.length) { box.innerHTML = `<div class="vazio-recursos">${escapeHtml(tr('resources.no_items_view', {}, 'Nenhum item cadastrado.'))}</div>`; return; }
    items.forEach(item => {
      const card = makeButtonCard(item.nome || tr('resources.no_item_name', {}, 'Sem nome'), 'recursos-view-title-card recursos-view-catalog-title-card');
      card.dataset.tipo = tipo;
      card.addEventListener('click', () => openCatalogDetail(tipo, item, emoji));
      box.appendChild(card);
    });
  }
  function openCatalogDetail(tipo, item, emoji = ''){
    if (!catalogDetailModal || !item) return;
    const tipoLabel = tipo === 'personagens' ? tr('resources.character', {}, 'Personagem') : (tipo === 'anotacoes' ? tr('resources.note', {}, 'Anotação') : tr('resources.place', {}, 'Lugar'));
    const origem = tipo === 'anotacoes' ? tr('resources.saved_in_project_feminine', {}, 'salva no projeto') : (item.origem === 'roteiro' ? tr('resources.detected_in_script', {}, 'detectado no roteiro') : tr('resources.saved_in_project', {}, 'salvo no projeto'));
    const nome = item.nome || tr('resources.no_item_name', {}, 'Sem nome');
    const descricao = item.descricao || tr('resources.no_description', {}, 'Sem descrição.');
    const fontes = Array.isArray(item.fontes) && item.fontes.length ? `${tr('resources.source', {}, 'Fonte')}: ${item.fontes.join(', ')}` : '';
    const nomeEl = $('#recursosCatalogoDetalheNome', catalogDetailModal);
    const tipoEl = $('#recursosCatalogoDetalheTipo', catalogDetailModal);
    const descEl = $('#recursosCatalogoDetalheDescricao', catalogDetailModal);
    const fontesEl = $('#recursosCatalogoDetalheFontes', catalogDetailModal);
    const imgEl = $('#recursosCatalogoDetalheImagem', catalogDetailModal);
    const semImgEl = $('#recursosCatalogoDetalheSemImagem', catalogDetailModal);
    const descTitleEl = $('#recursosCatalogoDetalheDescricaoTitulo', catalogDetailModal);
    if (nomeEl) { nomeEl.textContent = nome; nomeEl.title = nome; }
    if (tipoEl) tipoEl.textContent = `${tipoLabel} · ${origem}`;
    if (descTitleEl) descTitleEl.textContent = tipo === 'anotacoes' ? tr('resources.note', {}, 'Anotação') : tr('resources.description', {}, 'Descrição');
    if (descEl) descEl.textContent = descricao;
    if (fontesEl) { fontesEl.textContent = fontes; fontesEl.classList.toggle('oculto', !fontes); }
    catalogDetailModal.classList.toggle('catalogo-sem-imagem', tipo === 'anotacoes');
    if (imgEl && semImgEl) {
      const showImage = tipo !== 'anotacoes' && !!item.imagem;
      imgEl.src = showImage ? item.imagem : '';
      imgEl.classList.toggle('oculto', !showImage);
      semImgEl.classList.toggle('oculto', showImage || tipo === 'anotacoes');
      semImgEl.textContent = showImage ? '' : `${tr('resources.no_reference_image', {}, 'Sem imagem de referência')} ${emoji || ''}`.trim();
    }
    openElement(catalogDetailModal);
  }
  function sidePoint(node, side){
    const x = Number(node.x || 0), y = Number(node.y || 0), w = Number(node.width || 240), h = Number(node.height || 150);
    if (side === 'top') return {x: x + w/2, y};
    if (side === 'bottom') return {x: x + w/2, y: y + h};
    if (side === 'left') return {x, y: y + h/2};
    return {x: x + w, y: y + h/2};
  }
  function renderFlowView(flow){
    const box = $('#recursosViewFluxo');
    if (!box) return;
    const nodes = Array.isArray(flow.nodes) ? flow.nodes : [];
    const edges = Array.isArray(flow.edges) ? flow.edges : [];
    if (!nodes.length) { box.innerHTML = `<div class="vazio-recursos">${escapeHtml(tr('resources.no_flow_nodes', {}, 'Nenhum balão no fluxo ainda.'))}</div>`; return; }
    const maxX = Math.max(1200, ...nodes.map(n => Number(n.x || 0) + Number(n.width || 240) + 160));
    const maxY = Math.max(760, ...nodes.map(n => Number(n.y || 0) + Number(n.height || 150) + 160));
    const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
    const paths = edges.map(edge => {
      const a = byId[edge.from], b = byId[edge.to];
      if (!a || !b) return '';
      const p1 = sidePoint(a, edge.fromSide || 'right');
      const p2 = sidePoint(b, edge.toSide || 'left');
      const dx = Math.max(70, Math.abs(p2.x - p1.x) * .45);
      const c1 = (edge.fromSide === 'left') ? {x:p1.x-dx,y:p1.y} : (edge.fromSide === 'right') ? {x:p1.x+dx,y:p1.y} : {x:p1.x,y:p1.y + (edge.fromSide === 'top' ? -dx : dx)};
      const c2 = (edge.toSide === 'left') ? {x:p2.x-dx,y:p2.y} : (edge.toSide === 'right') ? {x:p2.x+dx,y:p2.y} : {x:p2.x,y:p2.y + (edge.toSide === 'top' ? -dx : dx)};
      return `<path class="fluxo-edge" d="M ${p1.x} ${p1.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${p2.x} ${p2.y}"></path>`;
    }).join('');
    const nodeHtml = nodes.map(node => `<article class="fluxo-node" style="left:${Number(node.x || 0)}px;top:${Number(node.y || 0)}px;width:${Number(node.width || 240)}px;min-height:${Number(node.height || 150)}px;cursor:default"><strong class="fluxo-node-title">${escapeHtml(node.titulo || tr('resources.balloon', {}, 'Bloco'))}</strong><div class="fluxo-node-text" style="resize:none;white-space:pre-wrap">${escapeHtml(node.texto || '')}</div></article>`).join('');
    box.innerHTML = `<div class="fluxo-canvas" style="min-width:${maxX}px;min-height:${maxY}px"><svg class="fluxo-svg">${paths}</svg><div class="fluxo-nodes">${nodeHtml}</div></div>`;
  }
  function setupCatalogDetailImagePreview(){
    const img = $('#recursosCatalogoDetalheImagem');
    if (!img) return;
    let preview = null;
    function closePreview(){ preview?.remove(); preview = null; }
    function openPreview(){
      if (!img.src || img.classList.contains('oculto')) return;
      closePreview();
      preview = document.createElement('div');
      preview.className = 'detalhe-catalogo-image-preview recursos-view-image-preview';
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
  window.abrirRecursosProjeto = (tab = '') => openModal(tab);
  window.recarregarRecursosProjeto = () => { cache = null; if (!modal.classList.contains('oculto')) loadResources(); };
  openButtons.forEach(btn => btn.addEventListener('click', () => openModal()));
  document.addEventListener('keydown', (ev) => {
    if (ev.ctrlKey && ev.altKey && String(ev.key || '').toLowerCase() === 'u') {
      ev.preventDefault();
      openModal();
      return;
    }
    if (ev.key === 'Escape') {
      if (catalogDetailModal && !catalogDetailModal.classList.contains('oculto')) { closeElement(catalogDetailModal); return; }
      if (infoDetailModal && !infoDetailModal.classList.contains('oculto')) { closeElement(infoDetailModal); return; }
    }
  });
  modal.querySelectorAll('[data-fechar-recursos-projeto="true"]').forEach(el => el.addEventListener('click', (ev)=>{ ev.preventDefault(); closeModal(); }));
  document.querySelectorAll('[data-fechar-recursos-info-detalhe="true"]').forEach(el => el.addEventListener('click', (ev)=>{ ev.preventDefault(); closeElement(infoDetailModal); }));
  document.querySelectorAll('[data-fechar-recursos-catalogo-detalhe="true"]').forEach(el => el.addEventListener('click', (ev)=>{ ev.preventDefault(); closeElement(catalogDetailModal); }));
  document.querySelectorAll('[data-modal-card="true"]').forEach(el => el.addEventListener('click', (ev)=> ev.stopPropagation()));
  modal.querySelectorAll('[data-recursos-view-tab]').forEach(btn => btn.addEventListener('click', () => switchTab(btn.dataset.recursosViewTab)));
  setupCatalogDetailImagePreview();
})();
