/* Navegação entre folhas visuais sem alterar o DOM editável, seleção ou histórico. */
(() => {
  'use strict';
  const dialog = document.getElementById('modalNavegacaoFolhas');
  if (!dialog) return;
  const list = document.getElementById('listaNavegacaoFolhas');
  const empty = document.getElementById('semNavegacaoFolhas');
  const dialogCard = dialog.querySelector('.page-jump-dialog');
  const overlay = dialog.querySelector('.modal-overlay');
  const infoPanel = document.querySelector('[data-recursos-panel="informacoes"]');
  const isInfo = Boolean(infoPanel);
  const isScript = !isInfo && Boolean(document.querySelector('.painel-roteiro #editorTexto'));
  const pageSelector = isInfo ? '#infoPaperLayers > .info-paper-sheet'
    : isScript ? '#editorTexto > .roteiro-page'
    : '.painel-word .epub-paper-layers > .epub-paper-sheet';
  const english = document.documentElement.lang?.toLowerCase().startsWith('en');
  const pageLabel = english ? 'Page' : 'Página';
  function translate(key, fallback, vars = {}) {
    return typeof window.t === 'function' ? window.t(key, vars) : fallback;
  }
  let returnFocus = null;
  const editorRoot = document.getElementById(isInfo ? 'editorInfoPagina' : 'editorTexto');
  let lastEditorRange = null;

  function captureEditorSelection() {
    const selection = window.getSelection();
    if (selection?.rangeCount && editorRoot?.contains(selection.anchorNode)) {
      lastEditorRange = selection.getRangeAt(0).cloneRange();
    }
  }
  function restoreEditorSelection() {
    if (!lastEditorRange || !editorRoot?.contains(lastEditorRange.startContainer)
        || !editorRoot.contains(lastEditorRange.endContainer)) return;
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(lastEditorRange.cloneRange());
  }
  document.addEventListener('selectionchange', captureEditorSelection);

  function isActive() {
    return !isInfo || (infoPanel.classList.contains('ativo') &&
      getComputedStyle(infoPanel).display !== 'none');
  }
  function getPages() {
    return isActive() ? [...document.querySelectorAll(pageSelector)] : [];
  }
  function offsetForToolbar() {
    const bar = document.querySelector(isInfo ? '.info-format-toolbar-sticky'
      : isScript ? '.barra-roteiro-sticky' : '.barra-word-sticky');
    const rect = bar?.getBoundingClientRect();
    return rect && rect.bottom > 0 && rect.top < 80 && rect.bottom < innerHeight * .5
      ? Math.ceil(rect.bottom + 16) : 24;
  }
  function scrollToSheet(number) {
    const pages = getPages();
    const target = pages[number - 1];
    if (!target) return false;
    let ancestor = target.parentElement;
    while (ancestor && ancestor !== document.body && ancestor !== document.documentElement) {
      const style = getComputedStyle(ancestor);
      if (/(auto|scroll)/.test(style.overflowY) && ancestor.scrollHeight > ancestor.clientHeight + 1) break;
      ancestor = ancestor.parentElement;
    }
    const smooth = !matchMedia('(prefers-reduced-motion: reduce)').matches;
    const behavior = smooth ? 'smooth' : 'instant';
    if (ancestor && ancestor !== document.body && ancestor !== document.documentElement) {
      const delta = target.getBoundingClientRect().top - ancestor.getBoundingClientRect().top;
      ancestor.scrollTo({top: Math.max(0, ancestor.scrollTop + delta - 20), behavior});
    } else {
      const top = target.getBoundingClientRect().top + window.scrollY - offsetForToolbar();
      window.scrollTo({top: Math.max(0, top), behavior});
    }
    return true;
  }
  function closeDialog() {
    if (dialog.classList.contains('oculto')) return;
    dialog.classList.add('oculto');
    dialog.setAttribute('aria-hidden', 'true');
    clearPreviewObserver();
    if (returnFocus?.isConnected && typeof returnFocus.focus === 'function') {
      returnFocus.focus({preventScroll: true});
    }
    returnFocus = null;
    restoreEditorSelection();
  }
  // As folhas EPUB e Informações são camadas de fundo; os textos pertencem a
  // uma única árvore editável. Projetamos as coordenadas reais dos blocos numa
  // cópia não editável da folha. Roteiro já contém o texto dentro de cada folha.
  // Nenhuma operação modifica o documento original ou seus dados de salvamento.
  let previewObserver = null;
  let scrollFallbackBound = false;
  let previewFrame = 0;
  let previewQueue = new Set();
  const previewCache = new Map();
  const MAX_CACHED_PREVIEWS = 12;
  let layout = null;

  function clearPreviewObserver() {
    previewObserver?.disconnect();
    previewObserver = null;
    previewQueue.clear();
    previewCache.clear();
    if (previewFrame) cancelAnimationFrame(previewFrame);
    previewFrame = 0;
    layout = null;
    // A janela não retém centenas de árvores DOM quando é fechada.
    list.replaceChildren();
  }

  function sanitizeClone(clone) {
    // Retirar IDs e atributos editáveis impede duplicação de identificadores,
    // foco acidental, envio de formulários e confusão com os editores originais.
    const nodes = [clone, ...clone.querySelectorAll('*')];
    for (const node of nodes) {
      node.removeAttribute('id');
      node.removeAttribute('contenteditable');
      node.removeAttribute('tabindex');
      node.removeAttribute('autofocus');
      node.removeAttribute('draggable');
      for (const attribute of [...node.attributes]) {
        if (/^on/i.test(attribute.name)) node.removeAttribute(attribute.name);
      }
      if (node.matches('script,iframe,video,audio,form,button,input,textarea,select,object,embed')) {
        // Retirar interativos e scripts das miniaturas. Imagens e texto são mantidos.
        node.remove();
      }
    }
    return clone;
  }

  function copyStyles(source, target, names) {
    const computed = getComputedStyle(source);
    for (const property of names) {
      const value = computed.getPropertyValue(property);
      if (value) target.style.setProperty(property, value, 'important');
    }
  }

  const TEXT_STYLES = [
    'font-family', 'font-size', 'font-weight', 'font-style', 'font-variant',
    'line-height', 'letter-spacing', 'word-spacing', 'text-align', 'text-indent',
    'text-decoration-line', 'text-decoration-color', 'text-transform', 'color',
    'direction', 'white-space', 'word-break', 'overflow-wrap', 'hyphens',
    'background-color', 'border-top-width', 'border-bottom-width',
    'border-top-style', 'border-bottom-style', 'border-top-color', 'border-bottom-color',
    'padding-top', 'padding-bottom', 'padding-left', 'padding-right'
  ];

  function copyTypography(source, clone) {
    copyStyles(source, clone, TEXT_STYLES);
    const originalNodes = source.querySelectorAll('*');
    const cloneNodes = clone.querySelectorAll('*');
    // Reproduzir estilos computados das fontes e tamanhos por trecho.
    // Fontes especiais têm seletores CSS ligados ao ID do editor original.
    for (let i = 0; i < originalNodes.length && i < cloneNodes.length; i += 1) {
      const sourceNode = originalNodes[i];
      const cloneNode = cloneNodes[i];
      if (!(sourceNode instanceof HTMLElement) || !(cloneNode instanceof HTMLElement)) continue;
      if (sourceNode.matches('span,strong,em,b,i,u,s,small,mark,font,code,img') ||
          sourceNode.hasAttribute('style')) {
        copyStyles(sourceNode, cloneNode, [
          'font-family', 'font-size', 'font-weight', 'font-style',
          'line-height', 'letter-spacing', 'word-spacing', 'color',
          'text-decoration-line', 'text-decoration-color', 'vertical-align'
        ]);
        if (sourceNode instanceof HTMLImageElement) {
          const rect = sourceNode.getBoundingClientRect();
          if (rect.width && rect.height) {
            cloneNode.style.setProperty('width', `${rect.width}px`, 'important');
            cloneNode.style.setProperty('height', `${rect.height}px`, 'important');
          }
        }
      }
    }
  }

  function pageMetrics(page) {
    const box = page.getBoundingClientRect();
    return {page, left:box.left, top:box.top, width:box.width, height:box.height,
      bottom:box.bottom};
  }
  function collectLayout(pages) {
    const sheets = pages.map(pageMetrics);
    if (isScript) return {sheets, blocks:[]};
    const blocks = [];
    // Uma leitura geométrica por bloco ao abrir o modal, não por miniatura.
    for (const element of editorRoot.children) {
      if (!(element instanceof HTMLElement)) continue;
      const box = element.getBoundingClientRect();
      if (!box.height && !box.width) continue;
      blocks.push({element, top:box.top, bottom:box.bottom,
        left:box.left, width:box.width});
    }
    return {sheets, blocks};
  }

  function positionStage(stage, pageIndex, paper) {
    const source = layout.sheets[pageIndex];
    if (!source || !source.width || !source.height) return false;
    const {width, height} = source;
    const bounds = paper.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return false;
    const scale = Math.min(bounds.width / width, bounds.height / height);
    stage.style.width = `${width}px`;
    stage.style.height = `${height}px`;
    stage.style.left = `${Math.max(0, (bounds.width - width * scale) / 2)}px`;
    stage.style.transform = `scale(${scale})`;
    return true;
  }
  function makeStage(pageIndex, paper) {
    const stage = document.createElement('div');
    stage.className = 'page-jump-snapshot';
    stage.setAttribute('aria-hidden', 'true');
    return positionStage(stage, pageIndex, paper) ? stage : null;
  }

  function renderScriptPreview(pageIndex, stage) {
    const source = layout.sheets[pageIndex];
    const wrapper = document.createElement('div');
    wrapper.className = 'painel-roteiro page-jump-script-context';
    const flow = document.createElement('div');
    flow.className = 'editor-texto editor-roteiro page-jump-script-flow';
    const originalFlow = editorRoot;
    if (originalFlow.dataset.theme) flow.dataset.theme = originalFlow.dataset.theme;
    // Herdar as variáveis de tema do próprio roteiro, inclusive temas personalizados.
    const originalStyles = getComputedStyle(originalFlow);
    for (const variable of [
      '--roteiro-page-bg', '--roteiro-page-ink', '--roteiro-page-muted',
      '--roteiro-page-border', '--roteiro-page-chrome', '--roteiro-comment-text',
      '--roteiro-comment-bg', '--roteiro-comment-border', '--roteiro-dialog-time'
    ]) {
      const value = originalStyles.getPropertyValue(variable);
      if (value) flow.style.setProperty(variable, value);
    }
    copyStyles(originalFlow, flow, ['font-family', 'font-size', 'line-height', 'color']);
    const page = sanitizeClone(source.page.cloneNode(true));
    page.classList.remove('is-current-page');
    page.style.setProperty('width', `${source.width}px`, 'important');
    page.style.setProperty('height', `${source.height}px`, 'important');
    page.style.setProperty('margin', '0', 'important');
    page.style.setProperty('min-height', '0', 'important');
    // Não forçar cor de fundo: os temas do roteiro continuam sendo aplicados.
    flow.appendChild(page);
    wrapper.appendChild(flow);
    stage.appendChild(wrapper);
  }

  function renderFlowPreview(pageIndex, stage) {
    const source = layout.sheets[pageIndex];
    const context = document.createElement('div');
    if (isInfo) {
      context.className = 'recursos-painel ativo page-jump-info-context';
      context.dataset.recursosPanel = 'informacoes';
    } else {
      context.className = 'painel-word page-jump-epub-context';
    }
    const sheet = sanitizeClone(source.page.cloneNode(true));
    sheet.classList.remove('is-active');
    sheet.style.setProperty('top', '0px', 'important');
    sheet.style.setProperty('left', '0px', 'important');
    sheet.style.setProperty('width', `${source.width}px`, 'important');
    sheet.style.setProperty('height', `${source.height}px`, 'important');
    sheet.style.setProperty('box-shadow', 'none', 'important');
    context.appendChild(sheet);

    const flow = document.createElement('div');
    flow.className = `${editorRoot.className} page-jump-projected-flow`;
    flow.classList.remove('editor-sessao-bloqueada');
    const editorRect = editorRoot.getBoundingClientRect();
    flow.style.setProperty('left', `${editorRect.left - source.left}px`, 'important');
    flow.style.setProperty('top', `${editorRect.top - source.top}px`, 'important');
    flow.style.setProperty('width', `${editorRect.width}px`, 'important');
    copyStyles(editorRoot, flow, [
      'font-family', 'font-size', 'font-weight', 'font-style', 'line-height',
      'letter-spacing', 'word-spacing', 'color', 'text-align',
      'direction', 'white-space', 'overflow-wrap', 'word-break'
    ]);
    // Apenas os blocos que aparecem nesta folha, incluindo blocos altos
    // que começam em uma e terminam em outra. O corte é feito no papel.
    const maxTop = source.bottom + 1;
    for (const block of layout.blocks) {
      if (block.bottom < source.top - 1) continue;
      if (block.top > maxTop) break;
      const clone = block.element.cloneNode(true);
      if (!(clone instanceof HTMLElement)) continue;
      copyTypography(block.element, clone);
      sanitizeClone(clone);
      clone.style.setProperty('position', 'absolute', 'important');
      clone.style.setProperty('left', `${block.left - editorRect.left}px`, 'important');
      clone.style.setProperty('top', `${block.top - editorRect.top}px`, 'important');
      clone.style.setProperty('width', `${block.width}px`, 'important');
      clone.style.setProperty('margin', '0', 'important');
      clone.style.setProperty('max-width', `${block.width}px`, 'important');
      clone.style.setProperty('box-sizing', 'border-box', 'important');
      flow.appendChild(clone);
    }
    context.appendChild(flow);
    stage.appendChild(context);
  }

  function renderCard(card) {
    if (!card.isConnected || dialog.classList.contains('oculto') || card.dataset.rendered) return;
    const index = Number(card.dataset.pageNumber) - 1;
    const paper = card.querySelector('.page-jump-card-paper');
    let stage = previewCache.get(index);
    if (stage) {
      previewCache.delete(index);
      if (!positionStage(stage, index, paper)) return;
    } else {
      stage = makeStage(index, paper);
      if (!stage) return;
      if (isScript) renderScriptPreview(index, stage);
      else renderFlowPreview(index, stage);
    }
    paper.replaceChildren(stage);
    card.dataset.rendered = 'true';
  }

  function flushPreviewQueue() {
    previewFrame = 0;
    if (dialog.classList.contains('oculto')) return;
    // Até 4 folhas por quadro: exibir rapidamente as prévias visíveis sem
    // renderizar centenas de cópias simultaneamente.
    let count = 0;
    for (const card of previewQueue) {
      previewQueue.delete(card);
      if (card.isConnected) renderCard(card);
      if (++count >= 4) break;
    }
    if (previewQueue.size) previewFrame = requestAnimationFrame(flushPreviewQueue);
  }
  function queueRender(card) {
    if (card.dataset.rendered) return;
    previewQueue.add(card);
    if (!previewFrame) previewFrame = requestAnimationFrame(flushPreviewQueue);
  }
  function disposeCard(card) {
    previewQueue.delete(card);
    if (!card.dataset.rendered) return;
    const paper = card.querySelector('.page-jump-card-paper');
    const stage = paper.querySelector('.page-jump-snapshot');
    if (stage) {
      const number = Number(card.dataset.pageNumber) - 1;
      previewCache.delete(number);
      previewCache.set(number, stage);
      while (previewCache.size > MAX_CACHED_PREVIEWS) {
        previewCache.delete(previewCache.keys().next().value);
      }
    }
    paper.replaceChildren();
    delete card.dataset.rendered;
  }
  function refreshVisibleCards() {
    if (dialog.classList.contains('oculto')) return;
    const scroller = list.getBoundingClientRect();
    const top = scroller.top - 350;
    const bottom = scroller.bottom + 350;
    for (const card of list.children) {
      const rect = card.getBoundingClientRect();
      if (rect.bottom >= top && rect.top <= bottom) queueRender(card);
      else disposeCard(card);
    }
  }
  function createCard(number, source) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'page-jump-card';
    button.dataset.pageNumber = String(number);
    button.setAttribute('aria-label', translate('navigation.page_label', `${pageLabel} ${number}`, {number}));
    const paper = document.createElement('span');
    paper.className = 'page-jump-card-paper';
    paper.setAttribute('aria-hidden', 'true');
    // Correspondência de proporção com a folha original, sem alongar uma
    // miniatura em caso excepcional de parágrafo maior que uma folha inteira.
    if (source.width && source.height) {
      paper.style.aspectRatio = `${source.width} / ${Math.min(source.height, source.width * 1.75)}`;
    }
    const badge = document.createElement('span');
    badge.className = 'page-jump-card-badge';
    badge.textContent = String(number);
    badge.setAttribute('aria-hidden', 'true');
    button.append(paper, badge);
    return button;
  }
  function renderList() {
    clearPreviewObserver();
    const pages = getPages();
    layout = collectLayout(pages);
    const fragment = document.createDocumentFragment();
    for (let i = 0; i < pages.length; i += 1) {
      fragment.appendChild(createCard(i + 1, layout.sheets[i]));
    }
    list.replaceChildren(fragment);
    empty.classList.toggle('oculto', pages.length > 0);
  }
  function observeCards() {
    if (typeof IntersectionObserver !== 'undefined') {
      previewObserver = new IntersectionObserver((entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) queueRender(entry.target);
          else disposeCard(entry.target);
        }
      }, {root: list, rootMargin:'260px 0px', threshold:0});
      for (const card of list.children) previewObserver.observe(card);
    } else {
      // Fallback para WebViews antigos sem IntersectionObserver.
      if (!scrollFallbackBound) {
        list.addEventListener('scroll', refreshVisibleCards, {passive:true});
        scrollFallbackBound = true;
      }
      refreshVisibleCards();
    }
  }
  function openDialog() {
    if (!isActive() || !dialog.classList.contains('oculto')) return;
    captureEditorSelection();
    returnFocus = document.activeElement;
    renderList();
    dialog.classList.remove('oculto');
    dialog.setAttribute('aria-hidden', 'false');
    observeCards();
    (list.querySelector('[data-page-number]') || dialog.querySelector('[data-page-jump-dismiss]'))?.focus?.({preventScroll: true});
  }
  function action(command) {
    if (!isActive()) return;
    captureEditorSelection();
    if (command === 'list') openDialog();
    else if (command === 'first') scrollToSheet(1);
    else if (command === 'last') scrollToSheet(getPages().length);
    if (command !== 'list') restoreEditorSelection();
  }
  dialogCard.addEventListener('click', (event) => {
    if (event.target.closest('[data-page-jump-dismiss]')) {
      closeDialog();
      return;
    }
    const pageButton = event.target.closest('.page-jump-card[data-page-number]');
    if (!pageButton || !list.contains(pageButton)) return;
    const number = Number(pageButton.dataset.pageNumber);
    closeDialog();
    scrollToSheet(number);
  });
  overlay.addEventListener('click', closeDialog);
  document.addEventListener('keydown', (event) => {
    if (!dialog.classList.contains('oculto')) {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopImmediatePropagation();
        closeDialog();
        return;
      }
      if (event.key === 'Tab') {
        const focusable = [...dialog.querySelectorAll('button:not([disabled]):not(.oculto)')]
          .filter((el) => el.getClientRects().length > 0);
        if (focusable.length) {
          const first = focusable[0], last = focusable[focusable.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
          else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
      }
      return;
    }
    if (event.repeat || event.isComposing || event.keyCode === 229 ||
        !event.ctrlKey || !event.altKey || event.metaKey || event.shiftKey) return;
    const command = event.key === 'Home' ? 'first'
      : event.key === 'End' ? 'last'
      : event.key.toLowerCase() === 'p' ? 'list' : null;
    if (!command || !isActive()) return;
    if (document.querySelector('.modal:not(.oculto)')) return;
    event.preventDefault();
    event.stopPropagation();
    action(command);
  }, true);
  window.GutenbergNavegacaoFolhas = {scrollToSheet, getPages, openDialog};
})();
