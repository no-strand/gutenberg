/** Tipografia inline compartilhada entre editor EPUB e páginas de Informações. */
(() => {
  'use strict';
  const sizes = ['6', '7', '8', '9', '10', '10.5', '11', '12', '13', '14', '15', '16', '18', '20', '21', '22', '24', '26', '28', '32', '36', '40', '42', '44', '48', '60'];
  const fonts = ['fonte-atkinson-hyperlegible','fonte-inter','fonte-source-sans-3','fonte-noto-sans',
    'fonte-ibm-plex-sans','fonte-arial','fonte-roboto','fonte-literata','fonte-source-serif-4',
    'fonte-noto-serif','fonte-georgia','fonte-times-new-roman','fonte-ibm-plex-mono',
    'fonte-jetbrains-mono','fonte-source-code-pro','fonte-consolas','fonte-courier-new',
    'fonte-sans','fonte-serif','fonte-mono'];
  const sizeClass = (value) => sizes.includes(String(value))
    ? `tamanho-fonte-${String(value).replace('.', '-')}pt` : null;
  const classes = sizes.map(sizeClass);
  const isSize = (cls) => classes.includes(cls);
  const isFont = (cls) => fonts.includes(cls);
  function classAt(node, root, predicate) {
    let el = node?.nodeType === Node.TEXT_NODE ? node.parentElement : node;
    while (el && el !== root) {
      const match = [...(el.classList || [])].find(predicate);
      if (match) return match;
      el = el.parentElement;
    }
    return null;
  }
  function nearestSizeInPoints(node, root) {
    const cls = classAt(node, root, isSize);
    if (cls) return sizes.find((s) => sizeClass(s) === cls) || '12';
    const px = parseFloat(getComputedStyle(node?.nodeType === Node.ELEMENT_NODE ? node : (node?.parentElement || root)).fontSize);
    const pts = Number.isFinite(px) ? px * .75 : 12;
    return sizes.reduce((a, b) => Math.abs(+b - pts) < Math.abs(+a - pts) ? b : a, '12');
  }
  /** Valores de tipografia presentes de fato na seleção, inclusive se um
   * mesmo parágrafo contém vários tamanhos. Não conta nós apenas tangenciados
   * nas bordas do Range (ex.: seleção terminando antes do próximo span). */
  function selectionValues(root, range, kind = 'size') {
    const values = new Set();
    if (!root || !range || range.collapsed ||
        !root.contains(range.startContainer) || !root.contains(range.endContainer)) return values;
    const common = range.commonAncestorContainer;
    const scope = common.nodeType === Node.TEXT_NODE ? common.parentNode : common;
    if (!scope) return values;
    const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (!node.textContent?.length || !root.contains(node)) continue;
      const nodeRange = document.createRange();
      nodeRange.selectNodeContents(node);
      if (range.compareBoundaryPoints(Range.START_TO_END, nodeRange) <= 0 ||
          range.compareBoundaryPoints(Range.END_TO_START, nodeRange) >= 0) continue;
      const value = kind === 'font'
        ? (classAt(node, root, isFont) || 'fonte-arial')
        : nearestSizeInPoints(node, root);
      values.add(value);
      if (values.size > 1) return values;
    }
    return values;
  }
  // Isola a seleção das formatações anteriores (inclusive ancestrais).
  // Sem isso, 48 pt -> 15 pt deixa o span de 48 pt por fora do de 15 pt:
  // sua caixa inline continua podendo aumentar a entrelinha.
  function isolateInlineTypography(wrapper, block, predicate) {
    let branch = wrapper;
    while (branch.parentElement && branch.parentElement !== block) {
      const parent = branch.parentElement;
      if (!(parent instanceof HTMLElement)) break;
      const grandparent = parent.parentNode;
      if (!grandparent) break;
      const before = parent.cloneNode(false);
      const selected = parent.cloneNode(false);
      const after = parent.cloneNode(false);
      while (parent.firstChild && parent.firstChild !== branch) before.appendChild(parent.firstChild);
      if (parent.firstChild !== branch) break;
      parent.removeChild(branch);
      while (parent.firstChild) after.appendChild(parent.firstChild);
      for (const cls of [...selected.classList]) {
        if (predicate(cls)) selected.classList.remove(cls);
      }
      if (predicate === isSize) { selected.style.removeProperty('font-size'); if (selected.tagName === 'FONT') selected.removeAttribute('size'); }
      if (predicate === isFont) { selected.style.removeProperty('font-family'); if (selected.tagName === 'FONT') selected.removeAttribute('face'); }
      if (!selected.classList.length) selected.removeAttribute('class');
      if (!selected.getAttribute('style')) selected.removeAttribute('style');
      selected.appendChild(branch);
      if (before.hasChildNodes()) grandparent.insertBefore(before, parent);
      grandparent.insertBefore(selected, parent);
      if (after.hasChildNodes()) grandparent.insertBefore(after, parent);
      parent.remove();
      branch = selected;
    }
    // Remover recipientes vazios de estilos evita novas caixas aninhadas.
    let el = branch;
    while (el && el !== wrapper) {
      const child = el.firstChild;
      const parent = el.parentElement;
      if (el.tagName === 'SPAN' && el.childNodes.length === 1 && !el.attributes.length && parent) {
        parent.replaceChild(child, el);
      }
      el = child instanceof HTMLElement ? child : null;
    }
  }
  function applyToSelection(root, range, className, predicate) {
    if (!root || !range || range.collapsed || !className || !root.contains(range.startContainer) || !root.contains(range.endContainer)) return false;
    const blocks = Array.from(root.querySelectorAll('p,h1,h2,h3,blockquote,li'))
      .filter((el) => !el.closest('blockquote p,blockquote li'));
    function blockFor(node, offset) {
      if (node === root) return root.children[offset] || root.children[offset - 1] || null;
      const el = node.nodeType === Node.TEXT_NODE ? node.parentElement : node;
      return el?.closest('p,h1,h2,h3,blockquote,li') || null;
    }
    const startBlock = blockFor(range.startContainer, range.startOffset);
    const endBlock = blockFor(range.endContainer, range.endOffset);
    const startIndex = blocks.indexOf(startBlock);
    const endIndex = blocks.indexOf(endBlock);
    if (startIndex < 0 || endIndex < startIndex) return false;
    function textOffset(block, node, offset) {
      try { const r = document.createRange(); r.selectNodeContents(block); r.setEnd(node, offset); return r.toString().length; }
      catch (_) { return 0; }
    }
    const startOffset = textOffset(startBlock, range.startContainer, range.startOffset);
    const endOffset = textOffset(endBlock, range.endContainer, range.endOffset);
    function rangeFor(block, start, end) {
      const r = document.createRange();
      const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
      let cursor = 0, first = null, last = null;
      while (walker.nextNode()) {
        const n = walker.currentNode, next = cursor + n.length;
        if (!first && start <= next) first = {n, offset: Math.max(0, start-cursor)};
        if (!last && end <= next) last = {n, offset: Math.max(0, end-cursor)};
        cursor = next;
      }
      if (!first || !last) { r.selectNodeContents(block); r.collapse(start <= 0); return r; }
      r.setStart(first.n, Math.min(first.offset, first.n.length));
      r.setEnd(last.n, Math.min(last.offset, last.n.length));
      return r;
    }
    let changed = false;
    for (let i = endIndex; i >= startIndex; --i) {
      const block = blocks[i];
      const size = (block.textContent || '').length;
      const a = i === startIndex ? startOffset : 0;
      const b = i === endIndex ? endOffset : size;
      if (b <= a) continue;
      const r = rangeFor(block, a, b);
      if (r.collapsed) continue;
      const fragment = r.extractContents();
      // Retira SOMENTE a classe da categoria editada, preservando a outra
      // (fonte ou tamanho), negrito, itálico, links e demais elementos.
      fragment.querySelectorAll('*').forEach((node) => {
        [...node.classList].filter(predicate).forEach((cls) => node.classList.remove(cls));
        if (predicate === isSize) { node.style.removeProperty('font-size'); if (node.tagName === 'FONT') node.removeAttribute('size'); }
        if (predicate === isFont) { node.style.removeProperty('font-family'); if (node.tagName === 'FONT') node.removeAttribute('face'); }
        if (!node.getAttribute('style')) node.removeAttribute('style');
        if (!node.classList.length) node.removeAttribute('class');
        if (node.tagName === 'SPAN' && !node.attributes.length) node.replaceWith(...node.childNodes);
      });
      const wrapper = document.createElement('span');
      wrapper.className = className;
      wrapper.appendChild(fragment);
      r.insertNode(wrapper);
      isolateInlineTypography(wrapper, block, predicate);
      changed = true;
    }
    if (!changed) return false;
    blocks.forEach((block) => {
      // extractContents pode deixar wrappers vazios das seleções anteriores.
      block.querySelectorAll('span,strong,em,u').forEach((el) => {
        if (!el.textContent && !el.querySelector('img,br')) el.remove();
      });
      block.normalize();
    });
    const sel = window.getSelection();
    const a = rangeFor(blocks[startIndex], startOffset, startOffset);
    const b = rangeFor(blocks[endIndex], endOffset, endOffset);
    const result = document.createRange();
    result.setStart(a.startContainer, a.startOffset);
    result.setEnd(b.startContainer, b.startOffset);
    sel.removeAllRanges(); sel.addRange(result);
    return true;
  }
  window.GutenbergTipografia = Object.freeze({sizes, fonts, classes, sizeClass, isSize, isFont, classAt, nearestSizeInPoints, selectionValues, applyToSelection});
})();
