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
  const CATALOG_TYPES = ['personagens', 'lugares', 'anotacoes'];
  const VIEW_PAGE_TABS = {
    informacoes: '#recursosViewTabsInformacoes',
    fluxo: '#recursosViewTabsFluxo',
    personagens: '#recursosViewTabsPersonagens',
    lugares: '#recursosViewTabsLugares',
    anotacoes: '#recursosViewTabsAnotacoes',
  };
  let cache = null;
  let activeTab = 'informacoes';
  const activeResourcePageIds = {
    informacoes: null,
    fluxo: null,
    personagens: null,
    lugares: null,
    anotacoes: null,
  };
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
  function defaultPageTitle(tipo){
    if (tipo === 'fluxo') return tr('resources.flow', {}, 'Fluxo');
    if (tipo === 'personagens') return tr('resources.characters', {}, 'Personagens');
    if (tipo === 'lugares') return tr('resources.places', {}, 'Lugares');
    if (tipo === 'anotacoes') return tr('resources.notes', {}, 'Anotações');
    return tr('resources.default_page_title', {}, 'Página inicial');
  }
  function normalizeText(value, fallback = ''){ return String(value ?? '').trim() || fallback; }
  function fallbackPageId(tipo, idx){ return `${tipo || 'pagina'}_${idx + 1}`; }
  function switchTab(tab){
    activeTab = tab;
    $$('[data-recursos-view-tab]', modal).forEach(btn => btn.classList.toggle('ativo', btn.dataset.recursosViewTab === tab));
    $$('[data-recursos-view-panel]', modal).forEach(panel => panel.classList.toggle('ativo', panel.dataset.recursosViewPanel === tab));
    if (tab === 'fluxo') requestAnimationFrame(() => renderFlowView(activeFlowPage()));
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
  function normalizeInfoPages(value){
    const raw = Array.isArray(value) ? value : [];
    return raw.filter(page => page && typeof page === 'object').map((page, idx) => ({
      id: String(page.id || fallbackPageId('info', idx)),
      titulo: normalizeText(page.titulo || page.nome, tr('resources.untitled', {}, 'Sem título')),
      html: String(page.html || page.conteudo || '<p></p>'),
      data_criacao: page.data_criacao || '',
      data_atualizacao: page.data_atualizacao || '',
    }));
  }
  function normalizeInfoTabs(data){
    const raw = Array.isArray(data?.informacoes_abas || data?.abas_informacoes) ? (data.informacoes_abas || data.abas_informacoes) : [];
    const looksLikeTabs = raw.some(tab => tab && typeof tab === 'object' && (Array.isArray(tab.paginas) || Array.isArray(tab.pages) || Array.isArray(tab.informacoes)));
    if (!looksLikeTabs) {
      const legacyPages = normalizeInfoPages(data?.informacoes || []);
      return legacyPages.length ? [{
        id: 'informacoes_principal',
        titulo: defaultPageTitle('informacoes'),
        paginas: legacyPages,
        data_criacao: '',
        data_atualizacao: '',
      }] : [];
    }
    return raw.filter(tab => tab && typeof tab === 'object').map((tab, idx) => ({
      id: String(tab.id || fallbackPageId('info_tab', idx)),
      titulo: normalizeText(tab.titulo || tab.nome, defaultPageTitle('informacoes')),
      paginas: normalizeInfoPages(tab.paginas || tab.pages || tab.informacoes),
      data_criacao: tab.data_criacao || '',
      data_atualizacao: tab.data_atualizacao || '',
    }));
  }
  function normalizeFlow(flow){
    const src = flow && typeof flow === 'object' ? flow : {};
    return {
      nodes: Array.isArray(src.nodes) ? src.nodes : [],
      edges: Array.isArray(src.edges) ? src.edges : [],
    };
  }
  function normalizeFlowPages(data){
    const raw = Array.isArray(data?.fluxos) ? data.fluxos : [];
    if (raw.length) {
      return raw.filter(page => page && typeof page === 'object').map((page, idx) => {
        const flow = normalizeFlow(page.fluxo || page);
        return {
          id: String(page.id || fallbackPageId('fluxo', idx)),
          titulo: normalizeText(page.titulo || page.nome, defaultPageTitle('fluxo')),
          nodes: flow.nodes,
          edges: flow.edges,
          data_criacao: page.data_criacao || '',
          data_atualizacao: page.data_atualizacao || '',
        };
      });
    }
    const legacy = normalizeFlow(data?.fluxo);
    return (legacy.nodes.length || legacy.edges.length) ? [{id:'fluxo_principal', titulo:defaultPageTitle('fluxo'), ...legacy}] : [];
  }
  function catalogPagesKey(tipo){ return `${tipo}_paginas`; }
  function normalizeCatalogPages(data, tipo){
    const raw = Array.isArray(data?.[catalogPagesKey(tipo)]) ? data[catalogPagesKey(tipo)] : [];
    const pages = raw.filter(page => page && typeof page === 'object').map((page, idx) => ({
      id: String(page.id || fallbackPageId(tipo, idx)),
      titulo: normalizeText(page.titulo || page.nome, defaultPageTitle(tipo)),
      data_criacao: page.data_criacao || '',
      data_atualizacao: page.data_atualizacao || '',
    }));
    if (!pages.length && Array.isArray(data?.[tipo]) && data[tipo].length) {
      pages.push({id:`${tipo}_principal`, titulo:defaultPageTitle(tipo), data_criacao:'', data_atualizacao:''});
    }
    return pages;
  }
  function normalizeCatalogItems(items, pages){
    const raw = Array.isArray(items) ? items : [];
    const valid = new Set((pages || []).map(page => String(page.id)));
    const fallback = pages?.[0]?.id || '';
    return raw.map(item => {
      const pageId = String(item?.pagina_id || '');
      return {...(item || {}), pagina_id: valid.has(pageId) ? pageId : fallback};
    });
  }
  function ensureActiveResourcePage(tipo, pages){
    const list = Array.isArray(pages) ? pages : [];
    if (!list.length) { activeResourcePageIds[tipo] = null; return null; }
    if (!list.some(page => String(page.id) === String(activeResourcePageIds[tipo]))) {
      activeResourcePageIds[tipo] = list[0].id;
    }
    return activeResourcePageIds[tipo];
  }
  function activePage(tipo, pages){
    const activeId = ensureActiveResourcePage(tipo, pages);
    return (pages || []).find(page => String(page.id) === String(activeId)) || (pages || [])[0] || null;
  }
  function activeFlowPage(){
    if (!cache) return {nodes: [], edges: []};
    const pages = normalizeFlowPages(cache);
    return activePage('fluxo', pages) || {nodes: [], edges: []};
  }
  function renderViewPageTabs(tipo, pages, onSwitch){
    const box = $(VIEW_PAGE_TABS[tipo] || '');
    if (!box) return;
    const bar = box.closest('.resource-page-bar');
    const list = Array.isArray(pages) ? pages : [];
    box.innerHTML = '';
    bar?.classList.toggle('oculto', !list.length);
    if (!list.length) return;
    const activeId = ensureActiveResourcePage(tipo, list);
    list.forEach((page, idx) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `resource-page-tab recursos-view-page-tab${String(page.id) === String(activeId) ? ' ativo' : ''}`;
      btn.title = page.titulo || `${tr('resources.pages', {}, 'Página')} ${idx + 1}`;
      btn.setAttribute('role', 'tab');
      btn.setAttribute('aria-selected', String(page.id) === String(activeId) ? 'true' : 'false');
      const span = document.createElement('span');
      span.className = 'resource-page-tab-title';
      span.textContent = page.titulo || btn.title;
      btn.appendChild(span);
      btn.addEventListener('click', () => {
        if (String(activeResourcePageIds[tipo]) === String(page.id)) return;
        activeResourcePageIds[tipo] = page.id;
        onSwitch?.();
      });
      box.appendChild(btn);
    });
  }
  function renderAll(data){
    const subtitulo = $('#recursosProjetoSubtitulo');
    if (subtitulo) subtitulo.textContent = data?.projeto?.titulo ? tr('resources.project_prefix', {project: data.projeto.titulo}, `Projeto: ${data.projeto.titulo}`) : tr('resources.hero_desc', {}, 'Informações, fluxo, personagens, lugares e anotações.');
    renderInfo(data);
    renderFlow(data);
    renderCatalog(data, 'personagens', $('#recursosViewPersonagens'));
    renderCatalog(data, 'lugares', $('#recursosViewLugares'));
    renderCatalog(data, 'anotacoes', $('#recursosViewAnotacoes'));
    renderPlanning(data);
  }
  function renderPlanning(data){
    const planning = data?.planejamento || {};
    const scenes = Array.isArray(planning.cenas) ? planning.cenas : [];
    const sources = Array.isArray(planning.fontes) ? planning.fontes : [];
    const sceneBox = $('#recursosViewCenas');
    const sourceBox = $('#recursosViewPesquisa');
    if (!sceneBox || !sourceBox) return;
    sceneBox.replaceChildren(); sourceBox.replaceChildren();
    const catalogs = {
      personagens: data?.personagens || [],
      lugares: data?.lugares || [],
      anotacoes: data?.anotacoes || [],
      referencias: sources
    };
    function paragraph(title, text){
      const p = document.createElement('p');
      const strong = document.createElement('strong');
      strong.textContent = `${title}: `;
      p.append(strong, document.createTextNode(String(text || '')));
      return p;
    }
    const relationTypes = ['personagens', 'lugares', 'anotacoes', 'referencias'];
    const relationLabels = {
      personagens: tr('planning.characters', {}, 'Personagens'),
      lugares: tr('planning.places', {}, 'Lugares'),
      anotacoes: tr('planning.notes', {}, 'Anotações'),
      referencias: tr('planning.research', {}, 'Pesquisa'),
    };
    scenes.forEach((scene, index) => {
      const card = document.createElement('article');
      card.className = 'recursos-view-info-card planejamento-read-card';
      const title = document.createElement('h3');
      title.textContent = `${index+1}. ${scene.titulo || tr('resources.untitled', {}, 'Sem título')}`;
      card.appendChild(title);
      card.append(paragraph(tr('planning.status', {}, 'Situação'), tr({
        planejada:'planning.status_planned', em_andamento:'planning.status_progress',
        revisao:'planning.status_review', concluida:'planning.status_done'
      }[scene.status] || '', {}, scene.status || '')));
      for (const [key, label] of [
        ['resumo', tr('planning.summary', {}, 'Resumo')],
        ['objetivo', tr('planning.goal', {}, 'Objetivo')],
        ['conflito', tr('planning.conflict', {}, 'Conflito')],
        ['desfecho', tr('planning.outcome', {}, 'Desfecho')]
      ]) if (scene[key]) card.appendChild(paragraph(label, scene[key]));
      for (const type of relationTypes) {
        const available = new Map((catalogs[type] || []).map(entry => [String(entry.id), entry]));
        const related = (scene[type] || []).map(id => available.get(String(id))).filter(Boolean);
        if (!related.length) continue;
        const line = document.createElement('p');
        const strong = document.createElement('strong');
        strong.textContent = `${relationLabels[type]}: `;
        line.appendChild(strong);
        related.forEach((entry, relatedIndex) => {
          if (relatedIndex) line.appendChild(document.createTextNode(', '));
          const link = document.createElement('button');
          link.type = 'button';
          link.className = 'recursos-scene-resource-link';
          const name = entry.nome || entry.titulo || entry.label || tr('resources.untitled', {}, 'Sem título');
          link.textContent = name;
          link.setAttribute('aria-label', `${relationLabels[type]} · ${name}`);
          window.GutenbergResourcePreview?.bind(link, {
            nome: name,
            tipo: relationLabels[type],
            descricao: entry.descricao || entry.notas || entry.citacao || entry.resumo || entry.html || entry.texto || entry.text || '',
            imagem: ['personagens', 'lugares'].includes(type) ? (entry.imagem || '') : '',
          });
          if (CATALOG_TYPES.includes(type)) link.addEventListener('click', () => openCatalogDetail(type, entry));
          line.appendChild(link);
        });
        card.appendChild(line);
      }
      sceneBox.appendChild(card);
    });
    sources.forEach(source => {
      const card = document.createElement('article');
      card.className = 'recursos-view-info-card planejamento-read-card';
      const title = document.createElement('h3');
      title.textContent = source.titulo || tr('resources.untitled', {}, 'Sem título');
      card.appendChild(title);
      if (source.autor) card.appendChild(paragraph(tr('planning.author', {}, 'Autor'), source.autor));
      if (source.citacao) card.appendChild(paragraph(tr('planning.citation', {}, 'Citação'), source.citacao));
      if (source.notas) card.appendChild(paragraph(tr('planning.research_notes', {}, 'Notas'), source.notas));
      if (source.url) {
        try {
          const url = new URL(source.url);
          if (['http:', 'https:'].includes(url.protocol) && !url.username && !url.password) {
            const link = document.createElement('a');
            link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
            link.textContent = tr('planning.open_source', {}, 'Abrir fonte');
            card.appendChild(link);
          }
        } catch (_) { /* Fonte antiga sem URL HTTP(S) */ }
      }
      sourceBox.appendChild(card);
    });
    if (!scenes.length) sceneBox.innerHTML = `<p class="vazio-recursos">${escapeHtml(tr('planning.empty_scenes', {}, 'Nenhuma cena planejada.'))}</p>`;
    if (!sources.length) sourceBox.innerHTML = `<p class="vazio-recursos">${escapeHtml(tr('planning.empty_sources', {}, 'Nenhuma fonte cadastrada.'))}</p>`;
  }

  function makeButtonCard(title, className = 'recursos-view-title-card'){
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = className;
    btn.setAttribute('aria-label', title || tr('resources.untitled', {}, 'Sem título'));
    const h3 = document.createElement('h3');
    h3.textContent = title || tr('resources.untitled', {}, 'Sem título');
    btn.appendChild(h3);
    return btn;
  }
  function renderInfo(data){
    const tabs = normalizeInfoTabs(data || {});
    renderViewPageTabs('informacoes', tabs, () => renderInfo(cache || data));
    const tab = activePage('informacoes', tabs);
    renderInfoPages(tab?.paginas || [], tab);
  }
  function renderInfoPages(pages, tab){
    const box = $('#recursosViewInformacoes');
    if (!box) return;
    const list = Array.isArray(pages) ? pages : [];
    box.innerHTML = '';
    if (!list.length) { box.innerHTML = `<div class="vazio-recursos">${escapeHtml(tr('resources.no_info', {}, 'Nenhuma informação cadastrada.'))}</div>`; return; }
    list.forEach(page => {
      const card = makeButtonCard(page.titulo || tr('resources.untitled', {}, 'Sem título'), 'recursos-view-title-card recursos-view-info-title-card');
      card.addEventListener('click', () => openInfoDetail(page, tab));
      box.appendChild(card);
    });
  }
  function openInfoDetail(page, tab){
    if (!infoDetailModal) return;
    const titleEl = $('#recursosInfoDetalheTitulo', infoDetailModal);
    const subtitleEl = $('#recursosInfoDetalheSubtitulo', infoDetailModal);
    const contentEl = $('#recursosInfoDetalheConteudo', infoDetailModal);
    if (titleEl) { titleEl.textContent = page?.titulo || tr('resources.untitled', {}, 'Sem título'); titleEl.title = page?.titulo || tr('resources.untitled', {}, 'Sem título'); }
    if (subtitleEl) subtitleEl.textContent = tab?.titulo ? `${tr('resources.info', {}, 'Informações')} · ${tab.titulo}` : tr('resources.info_saved_in_project', {}, 'Informação salva no projeto');
    if (contentEl) contentEl.innerHTML = safeInfoHtml(page?.html);
    openElement(infoDetailModal);
  }
  function renderFlow(data){
    const pages = normalizeFlowPages(data || {});
    renderViewPageTabs('fluxo', pages, () => renderFlow(cache || data));
    const page = activePage('fluxo', pages);
    renderFlowView(page || {nodes: [], edges: []});
  }
  function renderCatalog(data, tipo, box){
    const pages = normalizeCatalogPages(data || {}, tipo);
    renderViewPageTabs(tipo, pages, () => renderCatalog(cache || data, tipo, box));
    const page = activePage(tipo, pages);
    const items = normalizeCatalogItems(data?.[tipo] || [], pages).filter(item => !page || String(item.pagina_id || '') === String(page.id));
    renderCatalogCards(items, box, tipo);
  }
  function renderCatalogCards(items, box, tipo){
    if (!box) return;
    box.innerHTML = '';
    if (!items.length) { box.innerHTML = `<div class="vazio-recursos">${escapeHtml(tr('resources.no_items_view', {}, 'Nenhum item cadastrado.'))}</div>`; return; }
    items.forEach(item => {
      const card = makeButtonCard(item.nome || tr('resources.no_item_name', {}, 'Sem nome'), 'recursos-view-title-card recursos-view-catalog-title-card');
      card.dataset.tipo = tipo;
      window.GutenbergResourcePreview?.bind(card, {
        nome: item.nome,
        tipo: tipo === 'personagens' ? tr('resources.character', {}, 'Personagem') : (tipo === 'anotacoes' ? tr('resources.note', {}, 'Anotação') : tr('resources.place', {}, 'Lugar')),
        descricao: item.descricao,
        imagem: tipo === 'anotacoes' ? '' : item.imagem,
      });
      card.addEventListener('click', () => openCatalogDetail(tipo, item));
      box.appendChild(card);
    });
  }
  function openCatalogDetail(tipo, item){
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
      semImgEl.textContent = showImage ? '' : (item.imagem_necessita_reenvio
        ? tr('resources.reference_image_needs_reupload', {}, 'Esta imagem foi danificada pelo limite antigo. Anexe o arquivo original novamente.')
        : tr('resources.no_reference_image', {}, 'Sem imagem de referência'));
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
    const normalized = normalizeFlow(flow);
    const nodes = Array.isArray(normalized.nodes) ? normalized.nodes : [];
    const edges = Array.isArray(normalized.edges) ? normalized.edges : [];
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
