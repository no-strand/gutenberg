/**
 * Paginação VISUAL dos EPUBs: a única árvore contenteditable permanece intacta.
 * As quebras são margens de apresentação, nunca nós inseridos nos parágrafos.
 * Leituras de geometria são feitas juntas; a folha CSS é escrita uma única vez.
 */
(() => {
  'use strict';
  const editor = document.querySelector('.painel-word #editorTexto');
  const paper = editor?.closest('.pagina-editor');
  if (!editor || !paper) return;

  paper.classList.add('epub-paginated');
  const layers = document.createElement('div');
  layers.className = 'epub-paper-layers';
  layers.setAttribute('aria-hidden', 'true');
  paper.insertBefore(layers, editor);
  const sheet = document.createElement('style');
  sheet.id = 'epub-visual-page-breaks';
  document.head.appendChild(sheet);

  const MAX_PAGES = 250;
  const GAP = 32;
  const DEBOUNCE_MS = 90;
  let pages = 0;
  let pageBoxes = [];
  let pageGeometryKey = '';
  let lastActiveIndex = -1;
  let resizeWidth = 0;
  let scheduledFrame = 0;
  let debounceTimer = 0;
  let selectionFrame = 0;
  let running = false;
  let composing = false;

  function measure() {
    const width = paper.clientWidth;
    const paperHeight = width * (1056 / 816);
    const padding = parseFloat(getComputedStyle(editor).paddingTop) || 80;
    return {width, paperHeight, padding, step: paperHeight + GAP, contentHeight: paperHeight - padding * 2};
  }

  function createSheets(boxes) {
    const key = boxes.map((item) => `${item.top.toFixed(2)}:${item.height.toFixed(2)}`).join('|');
    if (key === pageGeometryKey) return;
    pages = boxes.length;
    pageBoxes = boxes;
    pageGeometryKey = key;
    lastActiveIndex = -1;
    const fragment = document.createDocumentFragment();
    boxes.forEach((box, i) => {
      const item = document.createElement('div');
      item.className = 'epub-paper-sheet';
      item.style.top = `${box.top}px`;
      item.style.height = `${box.height}px`;
      const folio = document.createElement('span');
      folio.className = 'epub-paper-folio';
      folio.textContent = String(i + 1).padStart(2, '0');
      item.appendChild(folio);
      fragment.appendChild(item);
    });
    layers.replaceChildren(fragment);
    const last = boxes[boxes.length - 1];
    paper.style.minHeight = `${last.top + last.height}px`;
  }
  function updateActiveSheet() {
    if (running || !pages) return;
    const selection = window.getSelection();
    if (!selection?.rangeCount || !editor.contains(selection.anchorNode)) return;
    const range = selection.getRangeAt(0).cloneRange();
    range.collapse(true);
    const rect = range.getClientRects()[0];
    const node = selection.anchorNode;
    const el = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
    const block = el?.closest('#editorTexto > *') || el;
    const top = rect?.height ? rect.top : (block?.getBoundingClientRect().top || 0);
    const offset = Math.max(0, top - paper.getBoundingClientRect().top);
    const located = pageBoxes.findIndex((box) => offset < box.top + box.height + GAP / 2);
    const index = located < 0 ? pages - 1 : located;
    if (index === lastActiveIndex) return;
    lastActiveIndex = index;
    Array.from(layers.children).forEach((item, i) => item.classList.toggle('is-active', i === index));
  }

  function recalculate() {
    scheduledFrame = 0;
    if (running || composing || !editor.isConnected) return;
    running = true;
    try {
      const metrics = measure();
      if (!metrics.width || metrics.contentHeight < 120) return;
      // O documento continua com UMA árvore editável. As quebras são
      // margens CSS descartáveis, não nós persistidos no conteúdo.
      if (sheet.textContent) sheet.textContent = '';
      const blocks = Array.from(editor.children).filter((el) => el instanceof HTMLElement);
      const editorTop = editor.getBoundingClientRect().top;
      const boxes = [{top: 0, height: metrics.paperHeight}];
      let pageIndex = 0;
      let extraBefore = 0;
      let previousBottomMargin = 0;
      const rules = [];
      for (let i = 0; i < blocks.length; i += 1) {
        const block = blocks[i];
        const rect = block.getBoundingClientRect();
        const height = rect.height;
        const css = getComputedStyle(block);
        const ownMargin = parseFloat(css.marginTop) || 0;
        const bottomMargin = parseFloat(css.marginBottom) || 0;
        let top = rect.top - editorTop + extraBefore;
        let bottom = rect.bottom - editorTop + extraBefore;
        let box = boxes[pageIndex];
        const bottomLimit = box.top + box.height - metrics.padding;
        const oversized = height > metrics.contentHeight + 2;
        if (bottom > bottomLimit + 2 && boxes.length < MAX_PAGES &&
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
            const margin = Math.max(ownMargin, previousBottomMargin) + push;
            rules.push(`.pagina-editor-app .painel-word #editorTexto > :nth-child(${i + 1}) { margin-top: ${Math.ceil(margin)}px !important; }`);
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
        previousBottomMargin = bottomMargin;
      }
      sheet.textContent = rules.join('\n');
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
  function schedule(immediate = false) {
    if (composing) return;
    if (debounceTimer) clearTimeout(debounceTimer);
    if (scheduledFrame) cancelAnimationFrame(scheduledFrame);
    if (immediate) scheduledFrame = requestAnimationFrame(recalculate);
    else debounceTimer = setTimeout(() => {
      debounceTimer = 0;
      scheduledFrame = requestAnimationFrame(recalculate);
    }, DEBOUNCE_MS);
  }
  function scheduleActiveSheet() {
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
      const width = paper.clientWidth;
      if (Math.abs(width - resizeWidth) > 1) { resizeWidth = width; schedule(true); }
    });
    resize.observe(paper);
  } else window.addEventListener('resize', () => schedule(), {passive: true});
  if (document.fonts?.ready) document.fonts.ready.then(() => schedule(true));
  schedule(true);
})();
