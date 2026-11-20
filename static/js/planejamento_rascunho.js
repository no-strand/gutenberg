/** Expansão 2: mapa de cenas e biblioteca de pesquisa do Rascunho.
 * Usa os mesmos catálogos e a mesma fila de escrita do módulo Recursos.
 */
(function () {
  'use strict';
  const slug = window.PROJETO_SLUG;
  const modal = document.getElementById('modalPlanejamento');
  if (!slug || !modal || typeof window.GutenbergRecursosPost !== 'function') return;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const tr = (key, fallback = '') => {
    const text = typeof window.t === 'function' ? window.t(`planning.${key}`) : '';
    return text && text !== `planning.${key}` ? text : fallback;
  };
  const statusLabels = {
    planejada: tr('status_planned', 'Planejada'),
    em_andamento: tr('status_progress', 'Em andamento'),
    revisao: tr('status_review', 'Em revisão'),
    concluida: tr('status_done', 'Concluída')
  };
  const typesLabels = {
    pagina_web: tr('type_web', 'Página da web'),
    livro: tr('type_book', 'Livro'),
    artigo: tr('type_article', 'Artigo'),
    entrevista: tr('type_interview', 'Entrevista'),
    arquivo: tr('type_file', 'Documento'),
    outro: tr('type_other', 'Outro')
  };
  const catalogLabels = {
    personagens: tr('characters', 'Personagens'),
    lugares: tr('places', 'Lugares'),
    anotacoes: tr('notes', 'Anotações'),
    referencias: tr('research', 'Pesquisa'),
    paginas_info: tr('info_pages', 'Páginas de Informações'),
    nos_fluxo: tr('flow_nodes', 'Nós do Fluxograma')
  };
  const serverState = () => window.GutenbergRecursosEstado?.() || window.PROJETO_RECURSOS_INITIAL || {};
  const plan = () => serverState().planejamento || {cenas: [], fontes: []};
  const items = (type) => Array.isArray(plan()[type]) ? plan()[type] : [];
  const catalogItems = (type) => {
    const state = serverState();
    if (type === 'referencias') return items('fontes');
    if (type === 'paginas_info') return (state.informacoes_abas || []).flatMap(tab =>
      (tab.paginas || []).map(page => ({...page, label: `${tab.titulo} · ${page.titulo}`})));
    if (type === 'nos_fluxo') return (state.fluxos || []).flatMap(tab =>
      (tab.nodes || []).map(node => ({...node, label: `${tab.titulo} · ${node.titulo}`})));
    return state[type] || [];
  };
  let working = false;
  let lastFocus = null;

  function element(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = String(text);
    return el;
  }
  function button(label, handler, className = 'botao-secundario', disabled = false) {
    const el = element('button', className, label);
    el.type = 'button';
    el.disabled = disabled;
    el.addEventListener('click', handler);
    return el;
  }
  function short(text, limit = 260) {
    const value = String(text || '').trim();
    return value.length > limit ? `${value.slice(0, limit).trim()}…` : value;
  }
  function setSaveStatus(text, error = false) {
    const status = $('#recursosStatus');
    if (status) { status.textContent = text; status.classList.toggle('erro', error); }
  }
  function showMessage(text, error = false) {
    const status = $('#planejamentoFormStatus');
    if (status) { status.textContent = text; status.classList.toggle('erro', error); }
  }
  function safeUrl(text) {
    try {
      const url = new URL(String(text || ''));
      if (url.protocol !== 'http:' && url.protocol !== 'https:') return '';
      if (url.username || url.password) return '';
      return url.href;
    } catch (_) { return ''; }
  }
  function openModal(type, item = null) {
    if (working) return;
    lastFocus = document.activeElement;
    $('#formPlanejamento').reset();
    $('#planejamentoItemTipo').value = type;
    $('#planejamentoItemId').value = item?.id || '';
    $('#planejamentoTitulo').value = item?.titulo || '';
    const isScene = type === 'cenas';
    $('#planejamentoCamposCena').classList.toggle('oculto', !isScene);
    $('#planejamentoCamposFonte').classList.toggle('oculto', isScene);
    $('#planejamentoModalTitulo').textContent = item
      ? tr(isScene ? 'edit_scene' : 'edit_source', isScene ? 'Editar cena' : 'Editar referência')
      : tr(isScene ? 'new_scene' : 'new_source', isScene ? 'Nova cena' : 'Nova referência');
    $('#planejamentoTitulo').maxLength = isScene ? 120 : 160;
    if (isScene) {
      $('#planejamentoStatus').value = item?.status || 'planejada';
      $('#planejamentoResumo').value = item?.resumo || '';
      $('#planejamentoObjetivo').value = item?.objetivo || '';
      $('#planejamentoConflito').value = item?.conflito || '';
      $('#planejamentoDesfecho').value = item?.desfecho || '';
      drawConnections(item || {});
    } else {
      $('#planejamentoTipoFonte').value = item?.tipo || 'pagina_web';
      $('#planejamentoAutor').value = item?.autor || '';
      $('#planejamentoUrl').value = item?.url || '';
      $('#planejamentoCitacao').value = item?.citacao || '';
      $('#planejamentoNotas').value = item?.notas || '';
      $('#planejamentoVerificada').checked = Boolean(item?.verificada);
    }
    showMessage('');
    modal.classList.remove('oculto');
    modal.setAttribute('aria-hidden', 'false');
    $('#planejamentoTitulo').focus();
  }
  function closeModal() {
    if (working) return;
    modal.classList.add('oculto');
    modal.setAttribute('aria-hidden', 'true');
    lastFocus?.focus?.();
  }
  $$('[data-fechar-planejamento]').forEach(el => el.addEventListener('click', closeModal));
  document.addEventListener('keydown', ev => {
    if (ev.key === 'Escape' && !modal.classList.contains('oculto')) {
      ev.preventDefault(); closeModal();
    }
  });

  function drawConnections(item) {
    const holder = $('#planejamentoVinculos');
    holder.replaceChildren();
    for (const type of ['personagens', 'lugares', 'anotacoes', 'referencias', 'paginas_info', 'nos_fluxo']) {
      const group = element('fieldset', 'planejamento-vinculo-grupo');
      const legend = element('legend', '', catalogLabels[type]);
      const box = element('div', 'planejamento-vinculo-opcoes');
      const selected = new Set(item[type] || []);
      const entries = catalogItems(type);
      for (const entry of entries) {
        const label = element('label', 'planejamento-option');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = entry.id;
        checkbox.dataset.planejamentoVinculo = type;
        checkbox.checked = selected.has(entry.id);
        label.append(checkbox, element('span', '', entry.label || entry.nome || entry.titulo));
        window.GutenbergResourcePreview?.bind(label, {
          nome: entry.nome || entry.label || entry.titulo,
          tipo: catalogLabels[type],
          descricao: entry.descricao || entry.notas || entry.citacao || entry.resumo || entry.html || entry.texto || entry.text || '',
          imagem: ['personagens', 'lugares'].includes(type) ? (entry.imagem || '') : '',
        });
        box.appendChild(label);
      }
      if (!entries.length) box.appendChild(element('small', 'planejamento-vazio-vinculos', tr('no_links', 'Nenhum item disponível.')));
      group.append(legend, box);
      holder.appendChild(group);
    }
  }
  function readConnections(type) {
    return $$(`input[data-planejamento-vinculo="${type}"]:checked`, modal).map(el => el.value);
  }
  function formData() {
    const type = $('#planejamentoItemTipo').value;
    const payload = {id: $('#planejamentoItemId').value, titulo: $('#planejamentoTitulo').value.trim()};
    if (type === 'cenas') {
      Object.assign(payload, {
        status: $('#planejamentoStatus').value,
        resumo: $('#planejamentoResumo').value,
        objetivo: $('#planejamentoObjetivo').value,
        conflito: $('#planejamentoConflito').value,
        desfecho: $('#planejamentoDesfecho').value,
        personagens: readConnections('personagens'),
        lugares: readConnections('lugares'),
        anotacoes: readConnections('anotacoes'),
        referencias: readConnections('referencias'),
        paginas_info: readConnections('paginas_info'),
        nos_fluxo: readConnections('nos_fluxo')
      });
    } else {
      Object.assign(payload, {
        tipo: $('#planejamentoTipoFonte').value,
        autor: $('#planejamentoAutor').value,
        url: $('#planejamentoUrl').value.trim(),
        citacao: $('#planejamentoCitacao').value,
        notas: $('#planejamentoNotas').value,
        verificada: $('#planejamentoVerificada').checked
      });
    }
    return {type, payload};
  }
  async function post(type, action, payload) {
    const path = `/api/projetos/${encodeURIComponent(slug)}/recursos/planejamento/${type}/${action}`;
    const response = await window.GutenbergRecursosPost(path, payload);
    // Não re-renderizar o editor Informações enquanto houver texto por salvar.
    // O estado já compartilhado guarda o planejamento para a próxima atualização.
    serverState().planejamento = response.planejamento || {cenas: [], fontes: []};
    render();
  }
  $('#formPlanejamento').addEventListener('submit', async (event) => {
    event.preventDefault();
    if (working) return;
    const {type, payload} = formData();
    if (!payload.titulo) { showMessage(tr('title_required', 'Informe um título.'), true); return; }
    if (type === 'fontes' && payload.url && !safeUrl(payload.url)) {
      showMessage(tr('invalid_url', 'Utilize um endereço HTTP ou HTTPS válido.'), true); return;
    }
    working = true;
    $('#planejamentoBtnSalvar').disabled = true;
    showMessage(tr('saving', 'Salvando…'));
    try {
      await post(type, 'salvar', payload);
      setSaveStatus(tr('saved', 'Planejamento salvo'));
    } catch (err) {
      showMessage(err.message || tr('save_error', 'Não foi possível salvar.'), true);
      setSaveStatus(err.message || tr('save_error', 'Não foi possível salvar.'), true);
      return;
    } finally {
      working = false;
      $('#planejamentoBtnSalvar').disabled = false;
    }
    closeModal();
  });
  async function remove(type, item) {
    if (working || !confirm(`${tr('delete_confirm', 'Excluir permanentemente')} "${item.titulo}"?`)) return;
    working = true;
    try {
      await post(type, 'excluir', {id: item.id});
      setSaveStatus(tr('removed', 'Item removido'));
    } catch (err) {
      setSaveStatus(err.message || tr('save_error', 'Não foi possível salvar.'), true);
    } finally { working = false; }
  }
  async function moveScene(scene, direction) {
    if (working) return;
    const order = items('cenas').map(item => item.id);
    const index = order.indexOf(scene.id);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= order.length) return;
    [order[index], order[target]] = [order[target], order[index]];
    working = true;
    try {
      await post('cenas', 'ordenar', {ordem: order});
      setSaveStatus(tr('reordered', 'Ordem atualizada'));
    } catch (err) { setSaveStatus(err.message || tr('save_error', 'Não foi possível salvar.'), true); }
    finally { working = false; }
  }

  function makeBadge(label, className = '') {
    return element('span', `planejamento-badge ${className}`, label);
  }
  function relationBadges(scene) {
    const container = element('div', 'planejamento-relacoes planejamento-relacoes-blocos');
    for (const type of ['personagens', 'lugares', 'anotacoes', 'referencias', 'paginas_info', 'nos_fluxo']) {
      const available = new Map(catalogItems(type).map(entry => [entry.id, entry]));
      const ids = scene[type] || [];
      const valid = ids.map(id => [id, available.get(id)]).filter(([, related]) => related);
      if (!valid.length) continue;
      const group = element('section', `planejamento-relacao-grupo tipo-${type}`);
      const title = element('h4', 'planejamento-relacao-titulo', catalogLabels[type]);
      const list = element('div', 'planejamento-relacao-chips');
      for (const [id, related] of valid) {
        const label = related.label || related.nome || related.titulo;
        const action = button(label, () => {
          if (type === 'referencias') openModal('fontes', related);
          else if (type === 'paginas_info') window.GutenbergRecursosAbrirPaginaInfo?.(id);
          else if (type === 'nos_fluxo') window.GutenbergRecursosAbrirNoFluxo?.(id);
          else window.GutenbergRecursosAbrirCatalogo?.(type, id);
        }, `planejamento-chip chip-${type}`);
        action.setAttribute('aria-label', `${catalogLabels[type]} · ${label}`);
        window.GutenbergResourcePreview?.bind(action, {
          nome: label,
          tipo: catalogLabels[type],
          descricao: related.descricao || related.notas || related.citacao || related.resumo || related.html || related.texto || related.text || '',
          imagem: ['personagens', 'lugares'].includes(type) ? (related.imagem || '') : '',
        });
        list.appendChild(action);
      }
      group.append(title, list);
      container.appendChild(group);
    }
    return container;
  }
  function sceneCard(scene, absoluteIndex) {
    const card = element('article', 'planejamento-card planejamento-scene-card');
    const top = element('div', 'planejamento-card-top');
    const heading = element('div', 'planejamento-card-heading');
    const number = element('span', 'planejamento-scene-number', String(absoluteIndex + 1).padStart(2, '0'));
    const title = element('h3', '', scene.titulo);
    heading.append(number, title);
    top.append(heading, makeBadge(statusLabels[scene.status] || scene.status, `status-${scene.status}`));
    card.appendChild(top);
    const body = element('div', 'planejamento-card-body');
    const description = short(scene.resumo || scene.objetivo || scene.conflito || scene.desfecho, 400);
    if (description) body.appendChild(element('p', 'planejamento-resumo', description));
    const extras = [
      [tr('goal', 'Objetivo'), scene.objetivo],
      [tr('conflict', 'Conflito'), scene.conflito],
      [tr('outcome', 'Desfecho'), scene.desfecho]
    ].filter(pair => pair[1]);
    if (extras.length) {
      const details = element('details', 'planejamento-detalhes');
      details.appendChild(element('summary', '', tr('view_details', 'Ver estrutura da cena')));
      for (const [key, text] of extras) {
        const para = element('p');
        const strong = element('strong', '', `${key}: `);
        para.append(strong, document.createTextNode(text));
        details.appendChild(para);
      }
      body.appendChild(details);
    }
    body.appendChild(relationBadges(scene));
    card.appendChild(body);
    const actions = element('div', 'planejamento-acoes');
    const list = items('cenas');
    actions.append(
      button('↑', () => moveScene(scene, -1), 'botao-secundario planejamento-move', absoluteIndex === 0),
      button('↓', () => moveScene(scene, 1), 'botao-secundario planejamento-move', absoluteIndex === list.length - 1),
      button(tr('edit', 'Editar'), () => openModal('cenas', scene)),
      button(tr('delete', 'Excluir'), () => remove('cenas', scene), 'botao-perigo')
    );
    actions.firstElementChild.title = tr('move_up', 'Mover para cima');
    actions.children[1].title = tr('move_down', 'Mover para baixo');
    card.appendChild(actions);
    return card;
  }
  function sourceCard(source) {
    const card = element('article', 'planejamento-card planejamento-source-card');
    const top = element('div', 'planejamento-card-top');
    const title = element('h3', '', source.titulo);
    top.append(title, makeBadge(typesLabels[source.tipo] || source.tipo));
    card.appendChild(top);
    const body = element('div', 'planejamento-card-body');
    if (source.autor) body.appendChild(element('p', 'planejamento-fonte-autor', source.autor));
    if (source.citacao) body.appendChild(element('p', 'planejamento-resumo', short(source.citacao, 350)));
    if (source.notas) body.appendChild(element('p', 'planejamento-resumo', short(source.notas, 350)));
    const url = safeUrl(source.url);
    if (url) {
      const anchor = element('a', 'planejamento-fonte-link', tr('open_source', 'Abrir fonte'));
      anchor.href = url;
      anchor.target = '_blank';
      anchor.rel = 'noopener noreferrer';
      body.appendChild(anchor);
    }
    const used = items('cenas').filter(scene => (scene.referencias || []).includes(source.id));
    if (used.length) {
      const links = element('div', 'planejamento-relacoes');
      for (const scene of used) {
        links.appendChild(button(scene.titulo, () => {
          window.GutenbergRecursosAbrirAba?.('cenas');
          $(`[data-planejamento-cena="${scene.id}"]`)?.scrollIntoView({block:'center', behavior:'smooth'});
        }, 'planejamento-chip'));
      }
      body.appendChild(links);
    }
    body.appendChild(makeBadge(source.verificada ? tr('verified', 'Verificada') : tr('unverified', 'Não verificada'), source.verificada ? 'status-concluida' : 'status-planejada'));
    card.appendChild(body);
    const actions = element('div', 'planejamento-acoes');
    actions.append(button(tr('edit', 'Editar'), () => openModal('fontes', source)), button(tr('delete', 'Excluir'), () => remove('fontes', source), 'botao-perigo'));
    card.appendChild(actions);
    return card;
  }
  function matchesSearch(item, text) {
    const base = [item.titulo, item.resumo, item.objetivo, item.conflito, item.desfecho, item.autor, item.notas, item.citacao].join(' ').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase();
    return base.includes(text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase());
  }
  function render() {
    const list = items('cenas');
    const stats = $('#planejamentoEstatisticas');
    if (stats) {
      stats.replaceChildren();
      stats.append(makeBadge(`${list.length} ${tr('scenes_count', 'cenas')}`));
      for (const key of ['planejada', 'em_andamento', 'revisao', 'concluida']) {
        stats.append(makeBadge(`${list.filter(item => item.status === key).length} · ${statusLabels[key]}`, `status-${key}`));
      }
    }
    const search = $('#planejamentoBuscaCenas').value.trim();
    const filter = $('#planejamentoFiltroStatus').value;
    const sceneBox = $('#planejamentoListaCenas');
    sceneBox.replaceChildren();
    list.forEach((scene, index) => {
      if (filter && scene.status !== filter) return;
      if (search && !matchesSearch(scene, search)) return;
      const card = sceneCard(scene, index);
      card.dataset.planejamentoCena = scene.id;
      sceneBox.appendChild(card);
    });
    if (!sceneBox.childElementCount) sceneBox.appendChild(element('p', 'vazio-recursos', list.length ? tr('no_results', 'Nenhum resultado encontrado.') : tr('empty_scenes', 'Crie sua primeira cena para organizar a história.')));

    const sourceSearch = $('#planejamentoBuscaFontes').value.trim();
    const onlyUnverified = $('#planejamentoSomenteNaoVerificadas').checked;
    const sourceBox = $('#planejamentoListaFontes');
    sourceBox.replaceChildren();
    const sources = items('fontes').filter(source => (!onlyUnverified || !source.verificada) && (!sourceSearch || matchesSearch(source, sourceSearch)));
    sources.forEach(source => sourceBox.appendChild(sourceCard(source)));
    if (!sourceBox.childElementCount) sourceBox.appendChild(element('p', 'vazio-recursos', items('fontes').length ? tr('no_results', 'Nenhum resultado encontrado.') : tr('empty_sources', 'Registre uma fonte de pesquisa para vinculá-la às cenas.')));
  }
  $('#btnNovaCena')?.addEventListener('click', () => openModal('cenas'));
  $('#btnNovaFonte')?.addEventListener('click', () => openModal('fontes'));
  ['#planejamentoBuscaCenas','#planejamentoFiltroStatus','#planejamentoBuscaFontes','#planejamentoSomenteNaoVerificadas'].forEach(selector => {
    $(selector)?.addEventListener('input', render);
  });
  $$('[data-recursos-tab]').filter(el => ['cenas', 'pesquisa'].includes(el.dataset.recursosTab)).forEach(el => el.addEventListener('click', render));
  window.addEventListener('hashchange', () => {
    if (['#cenas', '#pesquisa'].includes(window.location.hash)) window.GutenbergRecursosAbrirAba?.(window.location.hash.slice(1));
  });
  if (['#cenas', '#pesquisa'].includes(window.location.hash)) window.GutenbergRecursosAbrirAba?.(window.location.hash.slice(1));
  render();
})();
