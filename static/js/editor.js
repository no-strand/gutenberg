/**
 * Editor EPUB refeito com separação entre propriedades inline e de bloco,
 * estado de digitação e preservação estável da seleção.
 */

const i18n = (key, vars = {}) => (window.t ? window.t(key, vars) : key);

const editor = document.getElementById('editorTexto');
const campoTituloCapitulo = document.getElementById('campoTituloCapitulo');
const statusAutosave = document.getElementById('statusAutosave');
const botoesComando = document.querySelectorAll('.barra-ferramentas button[data-comando]');
const botoesBlocoClasse = document.querySelectorAll('.barra-ferramentas button[data-bloco-classe]');
const botoesSpanClasse = document.querySelectorAll('.barra-ferramentas button[data-span-classe]');
const btnInserirImagem = document.getElementById('btnInserirImagem');
const inputImagemEditor = document.getElementById('inputImagemEditor');
const btnLimparEdicao = document.getElementById('btnLimparEdicao');
const btnInserirLinhaHorizontal = document.getElementById('btnInserirLinhaHorizontal');
const btnInserirSeparadorDecorativo = document.getElementById('btnInserirSeparadorDecorativo');
const btnInserirDelimitadorDecorativo = document.getElementById('btnInserirDelimitadorDecorativo');
const valorSeparadorDecorativo = document.getElementById('valorSeparadorDecorativo');
const valorDelimitadorDecorativo = document.getElementById('valorDelimitadorDecorativo');
const menuSeparadorDecorativo = document.getElementById('menuSeparadorDecorativo');
const menuDelimitadorDecorativo = document.getElementById('menuDelimitadorDecorativo');
const btnAbrirRevisaoOrtografica = document.getElementById('btnAbrirRevisaoOrtografica');
const btnUndoEditor = document.getElementById('btnUndoEditor');
const btnRedoEditor = document.getElementById('btnRedoEditor');
const modalRevisaoOrtografica = document.getElementById('modalRevisaoOrtografica');
const revisaoTextoOriginal = document.getElementById('revisaoTextoOriginal');
const revisaoTextoCorrigido = document.getElementById('revisaoTextoCorrigido');
const revisaoSubtitulo = document.getElementById('revisaoSubtitulo');
const revisaoStatus = document.getElementById('revisaoStatus');
const btnIgnorarBlocoRevisao = document.getElementById('btnIgnorarBlocoRevisao');
const btnRevisarBlocoRevisao = document.getElementById('btnRevisarBlocoRevisao');
const btnAceitarBlocoRevisao = document.getElementById('btnAceitarBlocoRevisao');

if (!editor) {
  console.warn('Editor EPUB não encontrado na página.');
}

const requestIdle = window.requestIdleCallback || ((cb) => setTimeout(() => cb({ didTimeout: false, timeRemaining: () => 0 }), 1));
const cancelIdle = window.cancelIdleCallback || clearTimeout;

const STORAGE_SEPARADOR_DECORATIVO = `editor:separador-decorativo:${window.EDITOR_CONFIG?.slug || 'global'}`;
const STORAGE_DELIMITADOR_DECORATIVO = `editor:delimitador-decorativo:${window.EDITOR_CONFIG?.slug || 'global'}`;
const SEPARADORES_DECORATIVOS = ['◆◆◆', '◇◇◇', '✦✦✦', '★★★', '☆☆☆', '❖❖❖', '✥✥✥'];
const DELIMITADORES_DECORATIVOS = [
  { abertura: '『', fechamento: '』' },
  { abertura: '《', fechamento: '》' },
  { abertura: '【', fechamento: '】' },
  { abertura: '｢', fechamento: '｣' },
  { abertura: '〈', fechamento: '〉' },
  { abertura: '〔', fechamento: '〕' },
  { abertura: '〖', fechamento: '〗' },
  { abertura: '〘', fechamento: '〙' },
  { abertura: '〚', fechamento: '〛' },
  { abertura: '«', fechamento: '»' },
];

const SELECTOR_BLOCOS = 'p,h1,h2,h3,blockquote,li';
const TAGS_INLINE_FORMATO = ['STRONG', 'EM', 'U'];
const CLASSES_ALINHAMENTO = ['alinhar-a-esquerda', 'alinhar-centro', 'alinhar-a-direita', 'justificar'];
const CLASSES_RECUO = ['recuo-a-esquerda', 'recuo-a-direita'];
const CLASSES_FONTE = ['fonte-sans', 'fonte-serif', 'fonte-mono'];
const INLINE_FONT_SELECTOR = 'span.fonte-sans, span.fonte-serif, span.fonte-mono';

let ultimoRangeEditor = null;
let autosaveTimer = null;
let autosaveRetryTimer = null;
let autosaveEmAndamento = false;
let tentativaPendente = false;
let idleAutosaveHandle = null;
let htmlCacheDirty = true;
let htmlEditorCache = '<p><br></p>';
let ultimaCargaEnviada = null;
let ultimaAssinaturaCargaEnviada = '';
let isEditorComposing = false;
let estadoRevisaoOrtografica = { blocos: [], indice: -1, carregando: false };
let historyStack = [];
let historyIndex = -1;
let historySuspend = false;
let historyCommitTimer = null;
const HISTORY_LIMIT = 120;

const typingState = {
  bold: false,
  italic: false,
  underline: false,
  font: null,
};

const MAPA_ATALHOS = {
  ALT: {
    e: () => alternarClasseDeBloco('alinhar-a-esquerda'),
    c: () => alternarClasseDeBloco('alinhar-centro'),
    d: () => alternarClasseDeBloco('alinhar-a-direita'),
    j: () => alternarClasseDeBloco('justificar'),
    b: () => alternarFormatacaoInline('bold'),
    i: () => alternarFormatacaoInline('italic'),
    u: () => alternarFormatacaoInline('underline'),
    '1': () => aplicarFormatoDeBloco('h1'),
    '2': () => aplicarFormatoDeBloco('h2'),
    '3': () => aplicarFormatoDeBloco('h3'),
    l: () => alternarListaNaoOrdenada(),
    q: () => inserirDelimitadorDecorativoNoCursorOuSelecao(),
    r: () => inserirLinhaHorizontalNoCursor(),
    p: () => aplicarFormatoDeBloco('p'),
  },
  CTRL_ALT: {
    e: () => alternarClasseDeBloco('recuo-a-esquerda'),
    d: () => alternarClasseDeBloco('recuo-a-direita'),
    x: () => aplicarFonte('fonte-sans'),
    s: () => aplicarFonte('fonte-serif'),
    m: () => aplicarFonte('fonte-mono'),
    l: () => limparTodaEdicaoEditor(),
    q: () => inserirSeparadorDecorativoNoCursor(),
    i: () => inputImagemEditor?.click(),
    r: () => iniciarRevisaoOrtografica(),
  },
};


function getNodePathFromRoot(node, root = editor) {
  if (!node || !root || node === root) return [];
  const path = [];
  let current = node;
  while (current && current !== root) {
    const parent = current.parentNode;
    if (!parent) break;
    path.unshift(Array.prototype.indexOf.call(parent.childNodes, current));
    current = parent;
  }
  return path;
}

function getNodeByPath(path = [], root = editor) {
  let current = root;
  for (const index of path) {
    if (!current?.childNodes?.[index]) return current || root;
    current = current.childNodes[index];
  }
  return current || root;
}

function serializeSelection() {
  const range = getCurrentRange() || ultimoRangeEditor;
  if (!range || !editor) return null;
  return {
    startPath: getNodePathFromRoot(range.startContainer),
    startOffset: range.startOffset,
    endPath: getNodePathFromRoot(range.endContainer),
    endOffset: range.endOffset,
    collapsed: range.collapsed,
  };
}

function clampOffset(node, offset) {
  if (!node) return 0;
  if (node.nodeType === Node.TEXT_NODE) return Math.max(0, Math.min(offset, node.textContent.length));
  return Math.max(0, Math.min(offset, node.childNodes.length));
}

function restoreSerializedSelection(snapshot) {
  if (!snapshot || !editor) return false;
  try {
    const startNode = getNodeByPath(snapshot.startPath, editor);
    const endNode = getNodeByPath(snapshot.endPath, editor);
    const range = document.createRange();
    range.setStart(startNode, clampOffset(startNode, snapshot.startOffset));
    range.setEnd(endNode, clampOffset(endNode, snapshot.endOffset));
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    ultimoRangeEditor = range.cloneRange();
    return true;
  } catch {
    return false;
  }
}

function commitHistory(reason = 'change', force = false) {
  if (!editor || historySuspend) return;
  if (!force && isEditorComposing) return;
  const html = getHtmlEditorNormalizado();
  const title = String(campoTituloCapitulo?.value || '');
  const previous = historyStack[historyIndex];
  if (previous && previous.html === html && previous.title === title) return;
  const snapshot = {
    html,
    selection: serializeSelection(),
    logicalSelection: serializeLogicalSelection(),
    title,
    reason,
  };
  historyStack = historyStack.slice(0, historyIndex + 1);
  historyStack.push(snapshot);
  if (historyStack.length > HISTORY_LIMIT) historyStack.shift();
  historyIndex = historyStack.length - 1;
  updateHistoryButtons();
}

function scheduleHistoryCommit(reason = 'change') {
  if (historySuspend) return;
  if (historyCommitTimer) clearTimeout(historyCommitTimer);
  historyCommitTimer = setTimeout(() => {
    historyCommitTimer = null;
    commitHistory(reason);
  }, 180);
}

function applyHistorySnapshot(snapshot) {
  if (!snapshot || !editor) return;
  historySuspend = true;
  try {
    editor.innerHTML = snapshot.html || '<p><br></p>';
    if (campoTituloCapitulo) campoTituloCapitulo.value = snapshot.title || '';
    normalizeBlocks();
    ensureEditorHasContent();
    if (!restoreLogicalSelection(snapshot.logicalSelection)) restoreSerializedSelection(snapshot.selection);
    syncTypingStateFromCaret();
    updateToolbarState();
    markEditorDirty();
    scheduleAutosave();
  } finally {
    historySuspend = false;
    updateHistoryButtons();
  }
}

function undoEditor() {
  if (historyIndex <= 0) return;
  historyIndex -= 1;
  applyHistorySnapshot(historyStack[historyIndex]);
}

function redoEditor() {
  if (historyIndex >= historyStack.length - 1) return;
  historyIndex += 1;
  applyHistorySnapshot(historyStack[historyIndex]);
}

function updateHistoryButtons() {
  if (btnUndoEditor) btnUndoEditor.disabled = historyIndex <= 0;
  if (btnRedoEditor) btnRedoEditor.disabled = historyIndex >= historyStack.length - 1 || historyIndex < 0;
}

function getSelectionSafe() {
  const sel = window.getSelection();
  return sel && sel.rangeCount ? sel : null;
}

function getCurrentRange() {
  const sel = getSelectionSafe();
  if (!sel) return null;
  const range = sel.getRangeAt(0);
  if (!editor?.contains(range.startContainer) || !editor.contains(range.endContainer)) return null;
  return range;
}

function focusEditor() {
  if (!editor) return;
  editor.focus({ preventScroll: true });
}

function ensureEditorSelectionForAction() {
  if (!editor) return false;
  const current = getCurrentRange();
  if (current) {
    ultimoRangeEditor = current.cloneRange();
    return true;
  }
  const restored = restoreSavedRange();
  if (restored) {
    const range = getCurrentRange();
    if (range) ultimoRangeEditor = range.cloneRange();
  }
  return restored;
}

function saveCurrentRange() {
  const range = getCurrentRange();
  if (range) ultimoRangeEditor = range.cloneRange();
}

function restoreSavedRange() {
  if (!editor || !ultimoRangeEditor) return false;
  const range = ultimoRangeEditor.cloneRange();
  try {
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    return true;
  } catch {
    return false;
  }
}

function createEmptyParagraph() {
  const p = document.createElement('p');
  p.appendChild(document.createElement('br'));
  return p;
}

function ensureEditorHasContent() {
  if (!editor) return;
  const meaningful = Array.from(editor.childNodes).some((node) => {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent.trim().length > 0;
    if (node.nodeType !== Node.ELEMENT_NODE) return false;
    if (node.matches('img,hr')) return true;
    if (node.matches(SELECTOR_BLOCOS)) return true;
    return node.textContent.trim().length > 0;
  });
  if (!meaningful) {
    editor.innerHTML = '';
    editor.appendChild(createEmptyParagraph());
    htmlCacheDirty = true;
  }
}

function getBlock(node) {
  if (!node || !editor) return null;
  if (node === editor) return editor.querySelector(SELECTOR_BLOCOS);
  if (node.nodeType === Node.TEXT_NODE) return node.parentElement?.closest(SELECTOR_BLOCOS) || null;
  return node.closest?.(SELECTOR_BLOCOS) || null;
}

function getSelectedBlocks() {
  const range = getCurrentRange() || ultimoRangeEditor;
  if (!range || !editor) return [];
  if (range.collapsed) {
    const block = getBlock(range.startContainer);
    return block ? [block] : [];
  }
  const blocks = Array.from(editor.querySelectorAll(SELECTOR_BLOCOS)).filter((block) => range.intersectsNode(block));
  return blocks.length ? blocks : (getBlock(range.commonAncestorContainer) ? [getBlock(range.commonAncestorContainer)] : []);
}

function getEditableBlocks() {
  if (!editor) return [];
  const blocks = [];
  Array.from(editor.childNodes).forEach((node) => {
    if (!(node instanceof HTMLElement)) return;
    if (node.matches('ul,ol')) {
      blocks.push(...Array.from(node.children).filter((child) => child.tagName === 'LI'));
      return;
    }
    if (node.matches(SELECTOR_BLOCOS)) blocks.push(node);
  });
  return blocks;
}

function getBlockIndex(block) {
  return getEditableBlocks().indexOf(block);
}

function getTextOffsetWithin(container, offset, block) {
  if (!block) return 0;
  const range = document.createRange();
  range.selectNodeContents(block);
  try {
    range.setEnd(container, offset);
  } catch {
    return 0;
  }
  return String(range.toString() || '').length;
}

function createRangeFromTextOffsets(block, startOffset, endOffset = startOffset) {
  const range = document.createRange();
  const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT, null);
  let cursor = 0;
  let startNode = null;
  let endNode = null;
  let startNodeOffset = 0;
  let endNodeOffset = 0;
  let current = walker.nextNode();
  while (current) {
    const len = current.textContent.length;
    if (!startNode && startOffset <= cursor + len) {
      startNode = current;
      startNodeOffset = Math.max(0, startOffset - cursor);
    }
    if (!endNode && endOffset <= cursor + len) {
      endNode = current;
      endNodeOffset = Math.max(0, endOffset - cursor);
      break;
    }
    cursor += len;
    current = walker.nextNode();
  }
  if (!startNode) {
    if (!block.lastChild) block.appendChild(document.createElement('br'));
    range.selectNodeContents(block);
    range.collapse(false);
    return range;
  }
  if (!endNode) {
    endNode = startNode;
    endNodeOffset = startNode.textContent.length;
  }
  range.setStart(startNode, Math.min(startNodeOffset, startNode.textContent.length));
  range.setEnd(endNode, Math.min(endNodeOffset, endNode.textContent.length));
  return range;
}

function serializeLogicalSelection() {
  const range = getCurrentRange() || ultimoRangeEditor;
  if (!range) return null;
  const startBlock = getBlock(range.startContainer);
  const endBlock = getBlock(range.endContainer);
  if (!startBlock || !endBlock) return null;
  return {
    startBlockIndex: getBlockIndex(startBlock),
    endBlockIndex: getBlockIndex(endBlock),
    startTextOffset: getTextOffsetWithin(range.startContainer, range.startOffset, startBlock),
    endTextOffset: getTextOffsetWithin(range.endContainer, range.endOffset, endBlock),
    collapsed: range.collapsed,
  };
}

function restoreLogicalSelection(snapshot) {
  if (!snapshot || !editor) return false;
  const blocks = getEditableBlocks();
  const startBlock = blocks[snapshot.startBlockIndex];
  const endBlock = blocks[snapshot.endBlockIndex] || startBlock;
  if (!startBlock || !endBlock) return false;
  try {
    const startRange = createRangeFromTextOffsets(startBlock, snapshot.startTextOffset);
    const endRange = createRangeFromTextOffsets(endBlock, snapshot.endTextOffset);
    const range = document.createRange();
    range.setStart(startRange.startContainer, startRange.startOffset);
    range.setEnd(endRange.startContainer, endRange.startOffset);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    ultimoRangeEditor = range.cloneRange();
    return true;
  } catch {
    return false;
  }
}

function getDocumentModel() {
  return getEditableBlocks().map((block) => ({
    tag: block.tagName.toLowerCase(),
    classes: Array.from(block.classList).filter((cls) => CLASSES_ALINHAMENTO.includes(cls) || CLASSES_RECUO.includes(cls)),
    html: block.innerHTML,
  }));
}

function getInlineStateFromNode(node) {
  const state = { bold: false, italic: false, underline: false, font: null };
  let current = node?.nodeType === Node.TEXT_NODE ? node.parentElement : node;
  while (current && current !== editor) {
    const tag = current.tagName;
    if (tag === 'STRONG' || tag === 'B') state.bold = true;
    if (tag === 'EM' || tag === 'I') state.italic = true;
    if (tag === 'U') state.underline = true;
    const fontClass = CLASSES_FONTE.find((cls) => current.classList?.contains(cls));
    if (!state.font && fontClass) state.font = fontClass;
    current = current.parentElement;
  }
  return state;
}

function getIntersectingTextNodes(range) {
  if (!range || !editor) return [];
  const root = range.commonAncestorContainer.nodeType === Node.ELEMENT_NODE
    ? range.commonAncestorContainer
    : range.commonAncestorContainer.parentElement;
  if (!root) return [];

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.textContent || !node.textContent.length) return NodeFilter.FILTER_REJECT;
      if (!editor.contains(node)) return NodeFilter.FILTER_REJECT;
      try {
        return range.intersectsNode(node) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      } catch {
        return NodeFilter.FILTER_REJECT;
      }
    },
  });

  const nodes = [];
  let current = walker.nextNode();
  while (current) {
    nodes.push(current);
    current = walker.nextNode();
  }
  return nodes;
}

function getRangeInlineState(range) {
  if (!range) return { bold: false, italic: false, underline: false, font: null };
  if (range.collapsed) return getInlineStateFromNode(range.startContainer);

  const textNodes = getIntersectingTextNodes(range);
  if (!textNodes.length) return getInlineStateFromNode(range.startContainer);

  const states = textNodes.map(getInlineStateFromNode);
  const font = states.every((state) => state.font === states[0].font) ? states[0].font : null;
  return {
    bold: states.every((state) => state.bold),
    italic: states.every((state) => state.italic),
    underline: states.every((state) => state.underline),
    font,
  };
}

function syncTypingStateFromCaret() {
  const range = getCurrentRange();
  if (!range || !range.collapsed) return;
  const state = getInlineStateFromNode(range.startContainer);
  typingState.bold = state.bold;
  typingState.italic = state.italic;
  typingState.underline = state.underline;
  typingState.font = state.font;
}

function normalizeInline(root = editor) {
  if (!root) return;

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, null);
  const elements = [];
  let current = walker.currentNode;
  while (current) {
    if (current !== root) elements.push(current);
    current = walker.nextNode();
  }

  elements.reverse().forEach((el) => {
    if (!(el instanceof HTMLElement)) return;

    if (el.matches('b')) {
      const strong = document.createElement('strong');
      strong.innerHTML = el.innerHTML;
      el.replaceWith(strong);
      el = strong;
    }
    if (el.matches('i')) {
      const em = document.createElement('em');
      em.innerHTML = el.innerHTML;
      el.replaceWith(em);
      el = em;
    }
    if (el.matches('span.editor-formatacao')) {
      const classes = Array.from(el.classList);
      const fontClass = classes.find((cls) => CLASSES_FONTE.includes(cls));
      const parentBlock = getBlock(el);
      const blockClasses = classes.filter((cls) => CLASSES_ALINHAMENTO.includes(cls) || CLASSES_RECUO.includes(cls));
      if (parentBlock && blockClasses.length) {
        CLASSES_ALINHAMENTO.concat(CLASSES_RECUO).forEach((cls) => {
          if (blockClasses.includes(cls)) parentBlock.classList.add(cls);
        });
      }
      if (fontClass) {
        el.className = fontClass;
      } else {
        while (el.firstChild) el.parentNode.insertBefore(el.firstChild, el);
        el.remove();
      }
      return;
    }

    if (el.matches('span') && !el.classList.length && !el.attributes.length) {
      while (el.firstChild) el.parentNode.insertBefore(el.firstChild, el);
      el.remove();
      return;
    }

    if (el.matches(INLINE_FONT_SELECTOR)) {
      CLASSES_FONTE.forEach((cls) => {
        if (cls !== Array.from(el.classList).find((item) => CLASSES_FONTE.includes(item))) el.classList.remove(cls);
      });
      if (!el.textContent && !el.querySelector('img,br')) {
        el.remove();
        return;
      }
    }

    const tag = el.tagName;
    const isMergeable = tag === 'STRONG' || tag === 'EM' || tag === 'U' || el.matches(INLINE_FONT_SELECTOR);
    if (!isMergeable || !el.parentNode) return;

    let next = el.nextSibling;
    while (next && next.nodeType === Node.TEXT_NODE && !next.textContent.length) next = next.nextSibling;
    const sameFont = el.matches(INLINE_FONT_SELECTOR)
      ? (next instanceof HTMLElement && next.tagName === 'SPAN' && CLASSES_FONTE.find((c) => el.classList.contains(c)) === CLASSES_FONTE.find((c) => next.classList.contains(c)))
      : false;
    const sameTag = !el.matches(INLINE_FONT_SELECTOR) && next instanceof HTMLElement && next.tagName === tag;
    if (sameTag || sameFont) {
      while (next.firstChild) el.appendChild(next.firstChild);
      next.remove();
    }
  });
}

function normalizeBlocks() {
  if (!editor) return;

  Array.from(editor.childNodes).forEach((node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      if (!node.textContent.trim()) {
        node.remove();
        return;
      }
      const p = document.createElement('p');
      p.textContent = node.textContent;
      node.replaceWith(p);
      return;
    }

    if (!(node instanceof HTMLElement)) return;

    if (!node.matches(`${SELECTOR_BLOCOS},img,hr,ul,ol`)) {
      const p = document.createElement('p');
      while (node.firstChild) p.appendChild(node.firstChild);
      node.replaceWith(p);
      return;
    }

    if (node.matches('ul,ol')) {
      Array.from(node.children).forEach((li) => {
        if (li.tagName !== 'LI') {
          const novoLi = document.createElement('li');
          while (li.firstChild) novoLi.appendChild(li.firstChild);
          li.replaceWith(novoLi);
        }
      });
      if (!node.children.length) {
        const li = document.createElement('li');
        li.appendChild(document.createElement('br'));
        node.appendChild(li);
      }
      return;
    }

    if (node.matches(SELECTOR_BLOCOS)) {
      if (!node.textContent.trim() && !node.querySelector('img,br')) node.appendChild(document.createElement('br'));
      CLASSES_FONTE.forEach((cls) => {
        if (node.classList.contains(cls)) {
          node.classList.remove(cls);
          if (node.textContent.trim()) {
            const span = document.createElement('span');
            span.className = cls;
            while (node.firstChild) span.appendChild(node.firstChild);
            node.appendChild(span);
          }
        }
      });
    }
  });

  ensureEditorHasContent();
  normalizeInline(editor);
}

function withSelectionMarkers(callback) {
  const range = getCurrentRange() || (restoreSavedRange() ? getCurrentRange() : null);
  if (!range) {
    callback(null, null);
    normalizeBlocks();
    saveCurrentRange();
    updateToolbarState();
    markEditorDirty();
    scheduleAutosave();
    return;
  }

  focusEditor();
  const collapsed = range.collapsed;
  const startMarker = document.createElement('span');
  startMarker.dataset.selMarker = 'start';
  startMarker.style.display = 'none';
  startMarker.appendChild(document.createTextNode('\u200b'));

  const endMarker = collapsed ? null : document.createElement('span');
  if (endMarker) {
    endMarker.dataset.selMarker = 'end';
    endMarker.style.display = 'none';
    endMarker.appendChild(document.createTextNode('\u200b'));
  }

  const endRange = range.cloneRange();
  endRange.collapse(false);
  if (endMarker) endRange.insertNode(endMarker);

  const startRange = range.cloneRange();
  startRange.collapse(true);
  startRange.insertNode(startMarker);

  callback(startMarker, endMarker);
  normalizeBlocks();

  const sel = window.getSelection();
  const newRange = document.createRange();
  if (endMarker?.isConnected) {
    newRange.setStartAfter(startMarker);
    newRange.setEndBefore(endMarker);
  } else {
    newRange.setStartAfter(startMarker);
    newRange.collapse(true);
  }
  sel.removeAllRanges();
  sel.addRange(newRange);

  if (endMarker?.isConnected) endMarker.remove();
  if (startMarker.isConnected) startMarker.remove();

  saveCurrentRange();
  updateToolbarState();
  markEditorDirty();
  scheduleAutosave();
}

function buildInlineWrapperChain(text) {
  let node = document.createTextNode(text);
  if (typingState.font) {
    const span = document.createElement('span');
    span.className = typingState.font;
    span.appendChild(node);
    node = span;
  }
  if (typingState.underline) {
    const u = document.createElement('u');
    u.appendChild(node);
    node = u;
  }
  if (typingState.italic) {
    const em = document.createElement('em');
    em.appendChild(node);
    node = em;
  }
  if (typingState.bold) {
    const strong = document.createElement('strong');
    strong.appendChild(node);
    node = strong;
  }
  return node;
}

function insertStyledText(text) {
  const range = getCurrentRange() || (restoreSavedRange() ? getCurrentRange() : null);
  if (!range) return;
  range.deleteContents();
  const node = buildInlineWrapperChain(text);
  range.insertNode(node);
  const sel = window.getSelection();
  const newRange = document.createRange();
  newRange.setStartAfter(node);
  newRange.collapse(true);
  sel.removeAllRanges();
  sel.addRange(newRange);
  if (!isEditorComposing && /\s/u.test(String(text || ''))) capitalizeFirstWordWhenCompleted(newRange);
  normalizeBlocks();
  saveCurrentRange();
  updateToolbarState();
  markEditorDirty();
  scheduleAutosave();
}

function surroundMarkerContents(startMarker, endMarker, wrapperFactory) {
  if (!startMarker || !endMarker || !startMarker.parentNode || !endMarker.parentNode) return;
  const range = document.createRange();
  range.setStartAfter(startMarker);
  range.setEndBefore(endMarker);
  if (range.collapsed) return;
  const fragment = range.extractContents();
  const wrapper = wrapperFactory();
  wrapper.appendChild(fragment);
  range.insertNode(wrapper);
}

function getMatchingElementsInRange(range, predicate) {
  if (!range) return [];
  const root = range.commonAncestorContainer.nodeType === Node.ELEMENT_NODE
    ? range.commonAncestorContainer
    : range.commonAncestorContainer.parentElement;
  if (!root) return [];

  const matches = [];
  const maybePush = (node) => {
    if (!(node instanceof HTMLElement)) return;
    try {
      if (!editor.contains(node)) return;
      if (range.intersectsNode(node) && predicate(node)) matches.push(node);
    } catch {
      // noop
    }
  };

  maybePush(root);

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT, {
    acceptNode(node) {
      try {
        if (!editor.contains(node)) return NodeFilter.FILTER_REJECT;
        return range.intersectsNode(node) && predicate(node) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
      } catch {
        return NodeFilter.FILTER_SKIP;
      }
    },
  });

  let current = walker.nextNode();
  while (current) {
    if (!matches.includes(current)) matches.push(current);
    current = walker.nextNode();
  }
  return matches;
}

function unwrapNodesInsideRange(startMarker, endMarker, predicate) {
  if (!startMarker?.parentNode || !endMarker?.parentNode) return;
  const range = document.createRange();
  range.setStartAfter(startMarker);
  range.setEndBefore(endMarker);

  const nodes = getMatchingElementsInRange(range, predicate);
  nodes.reverse().forEach((node) => {
    while (node.firstChild) node.parentNode.insertBefore(node.firstChild, node);
    node.remove();
  });
}


function splitTextBoundariesForRange(range) {
  if (!range || range.collapsed) return range;
  const local = range.cloneRange();
  if (local.endContainer.nodeType === Node.TEXT_NODE) {
    const text = local.endContainer;
    if (local.endOffset > 0 && local.endOffset < text.textContent.length) {
      text.splitText(local.endOffset);
      local.setEnd(text, text.textContent.length);
    }
  }
  if (local.startContainer.nodeType === Node.TEXT_NODE) {
    const text = local.startContainer;
    if (local.startOffset > 0 && local.startOffset < text.textContent.length) {
      const newNode = text.splitText(local.startOffset);
      local.setStart(newNode, 0);
    }
  }
  return local;
}

function unwrapSelectionPrecisely(startMarker, endMarker, predicate) {
  if (!startMarker?.parentNode || !endMarker?.parentNode) return;
  const baseRange = document.createRange();
  baseRange.setStartAfter(startMarker);
  baseRange.setEndBefore(endMarker);
  const range = splitTextBoundariesForRange(baseRange);
  const nodes = getMatchingElementsInRange(range, predicate);

  nodes.reverse().forEach((node) => {
    const local = document.createRange();
    local.selectNodeContents(node);
    const startsBefore = range.compareBoundaryPoints(Range.START_TO_START, local) > 0;
    const endsAfter = range.compareBoundaryPoints(Range.END_TO_END, local) < 0;
    if (!startsBefore && !endsAfter) {
      while (node.firstChild) node.parentNode.insertBefore(node.firstChild, node);
      node.remove();
      return;
    }

    if (startsBefore) {
      const beforeClone = node.cloneNode(false);
      const beforeRange = document.createRange();
      beforeRange.selectNodeContents(node);
      beforeRange.setEnd(range.startContainer, range.startOffset);
      beforeClone.appendChild(beforeRange.extractContents());
      node.parentNode.insertBefore(beforeClone, node);
    }

    if (endsAfter) {
      const afterClone = node.cloneNode(false);
      const afterRange = document.createRange();
      afterRange.selectNodeContents(node);
      afterRange.setStart(range.endContainer, range.endOffset);
      afterClone.appendChild(afterRange.extractContents());
      insertNodeAfter(node, afterClone);
    }

    while (node.firstChild) node.parentNode.insertBefore(node.firstChild, node);
    node.remove();
  });
}


function getPreviousEditableBlock(block) {
  const blocks = getEditableBlocks();
  const index = blocks.indexOf(block);
  return index > 0 ? blocks[index - 1] : null;
}

function getNextEditableBlock(block) {
  const blocks = getEditableBlocks();
  const index = blocks.indexOf(block);
  return index >= 0 && index < blocks.length - 1 ? blocks[index + 1] : null;
}


function getTopLevelContainer(node) {
  if (!node || !editor) return null;
  let current = node;
  while (current && current.parentNode && current.parentNode !== editor) current = current.parentNode;
  return current && current.parentNode === editor ? current : null;
}

function getAdjacentHorizontalRule(block, direction = 'previous') {
  const container = getTopLevelContainer(block);
  if (!(container instanceof HTMLElement)) return null;
  let sibling = direction === 'previous' ? container.previousSibling : container.nextSibling;
  while (sibling && sibling.nodeType === Node.TEXT_NODE && !String(sibling.textContent || '').trim()) {
    sibling = direction === 'previous' ? sibling.previousSibling : sibling.nextSibling;
  }
  return sibling instanceof HTMLElement && sibling.tagName === 'HR' ? sibling : null;
}

function removeAdjacentHorizontalRule(block, direction = 'previous') {
  const hr = getAdjacentHorizontalRule(block, direction);
  if (!hr) return false;
  hr.remove();
  normalizeBlocks();
  if (direction === 'previous') placeCaretAtStart(block);
  else placeCaretAtEnd(block);
  return true;
}

function isCaretAtEndOfBlock(range, block) {
  if (!range?.collapsed || !block) return false;
  const probe = range.cloneRange();
  probe.selectNodeContents(block);
  probe.setStart(range.startContainer, range.startOffset);
  return !String(probe.toString() || '').length;
}

function getTextUntilCaretInBlock(block, range = getCurrentRange()) {
  if (!block || !range?.collapsed) return '';
  const probe = document.createRange();
  probe.selectNodeContents(block);
  try {
    probe.setEnd(range.startContainer, range.startOffset);
  } catch {
    return '';
  }
  return String(probe.toString() || '');
}

function blockEndsWithLetterOrNumber(block) {
  const text = String(block?.textContent || '').trimEnd();
  return /[\p{L}\p{N}]$/u.test(text);
}

function appendPeriodToBlock(block) {
  if (!block || !block.isConnected || !blockEndsWithLetterOrNumber(block)) return false;
  const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT, null);
  let lastText = null;
  while (walker.nextNode()) lastText = walker.currentNode;
  if (lastText) {
    lastText.textContent = `${String(lastText.textContent || '').trimEnd()}.`;
    return true;
  }
  block.appendChild(document.createTextNode('.'));
  return true;
}

function getTextNodeAndOffsetAtTextIndex(block, textIndex) {
  if (!block) return null;
  const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      return String(node.textContent || '').length ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
    },
  });
  let cursor = 0;
  let current = walker.nextNode();
  while (current) {
    const len = current.textContent.length;
    if (textIndex < cursor + len) {
      return { node: current, offset: Math.max(0, textIndex - cursor) };
    }
    cursor += len;
    current = walker.nextNode();
  }
  return null;
}

function replaceCharacterAtTextIndex(block, textIndex, replacement) {
  const hit = getTextNodeAndOffsetAtTextIndex(block, textIndex);
  if (!hit?.node) return false;
  const currentChar = hit.node.textContent?.charAt(hit.offset) || '';
  if (!currentChar || currentChar === replacement) return false;
  hit.node.textContent = `${hit.node.textContent.slice(0, hit.offset)}${replacement}${hit.node.textContent.slice(hit.offset + 1)}`;
  return true;
}

function capitalizeLeadingCharacterInBlock(block, restoreLogical = null) {
  if (!block || !['P', 'H1', 'H2', 'H3', 'LI', 'BLOCKQUOTE'].includes(block.tagName)) return false;
  const fullText = String(block.textContent || '');
  const match = fullText.match(/^(\s*)(\p{Ll})/u);
  if (!match) return false;
  const index = match[1].length;
  const currentChar = fullText.charAt(index);
  const upperChar = currentChar.toLocaleUpperCase('pt-BR');
  if (!currentChar || currentChar === upperChar) return false;
  const changed = replaceCharacterAtTextIndex(block, index, upperChar);
  if (changed && restoreLogical) {
    restoreLogicalSelection(restoreLogical);
    saveCurrentRange();
  }
  return changed;
}

function capitalizeFirstWordWhenCompleted(range = getCurrentRange()) {
  if (!range?.collapsed) return false;
  const block = getBlock(range.startContainer);
  if (!block || !['P', 'H1', 'H2', 'H3', 'LI', 'BLOCKQUOTE'].includes(block.tagName)) return false;
  const caretOffset = getTextOffsetWithin(range.startContainer, range.startOffset, block);
  const textBeforeCaret = String(block.textContent || '').slice(0, caretOffset);
  if (!/^\s*[^\s]+\s$/u.test(textBeforeCaret)) return false;
  return capitalizeLeadingCharacterInBlock(block, serializeLogicalSelection());
}

function placeCaretAtEnd(node) {
  if (!node) return;
  const range = document.createRange();
  range.selectNodeContents(node);
  range.collapse(false);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
  saveCurrentRange();
}

function mergeAdjacentBlocks(previousBlock, currentBlock) {
  if (!previousBlock || !currentBlock) return null;
  const previousTextLength = String(previousBlock.innerText || previousBlock.textContent || '').length;
  if (previousBlock.querySelector('br') && !previousBlock.textContent.trim()) previousBlock.innerHTML = '';
  if (currentBlock.querySelector('br') && !currentBlock.textContent.trim()) {
    currentBlock.remove();
    return previousBlock;
  }
  while (currentBlock.firstChild) previousBlock.appendChild(currentBlock.firstChild);
  const listParent = currentBlock.parentElement;
  currentBlock.remove();
  if (listParent?.matches('ul,ol') && !listParent.children.length) listParent.remove();
  normalizeBlocks();
  const range = createRangeFromTextOffsets(previousBlock, previousTextLength);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
  saveCurrentRange();
  return previousBlock;
}

function handleStructuralKeydown(event) {
  const range = getCurrentRange();
  if (!range?.collapsed) return false;
  const block = getBlock(range.startContainer);
  if (!block) return false;

  if (event.key === 'Enter' && block.tagName !== 'LI') {
    event.preventDefault();
    const caretOffset = getTextOffsetWithin(range.startContainer, range.startOffset, block);
    const wasAtEnd = isCaretAtEndOfBlock(range, block);
    capitalizeLeadingCharacterInBlock(block);
    let splitOffset = caretOffset;
    if (wasAtEnd && appendPeriodToBlock(block)) splitOffset += 1;
    const refreshedRange = createRangeFromTextOffsets(block, splitOffset);
    const sel = window.getSelection();
    if (sel) {
      sel.removeAllRanges();
      sel.addRange(refreshedRange);
      saveCurrentRange();
    }
    const newBlock = splitBlockAtRange(block, refreshedRange.cloneRange());
    insertNodeAfter(block, newBlock);
    normalizeBlocks();
    placeCaretAtStart(newBlock);
    syncTypingStateFromCaret();
    markEditorDirty();
    scheduleAutosave();
    scheduleHistoryCommit('enter-split');
    return true;
  }

  if (event.key === 'Backspace' && isCaretAtStartOfBlock(range, block) && block.tagName !== 'LI') {
    const adjacentHr = getAdjacentHorizontalRule(block, 'previous');
    if (adjacentHr) {
      event.preventDefault();
      removeAdjacentHorizontalRule(block, 'previous');
      syncTypingStateFromCaret();
      markEditorDirty();
      scheduleAutosave();
      scheduleHistoryCommit('remove-horizontal-rule-backward');
      return true;
    }
    const previousBlock = getPreviousEditableBlock(block);
    if (!previousBlock || previousBlock.tagName === 'LI') return false;
    event.preventDefault();
    mergeAdjacentBlocks(previousBlock, block);
    markEditorDirty();
    scheduleAutosave();
    scheduleHistoryCommit('merge-backward');
    return true;
  }

  if (event.key === 'Delete' && isCaretAtEndOfBlock(range, block) && block.tagName !== 'LI') {
    const adjacentHr = getAdjacentHorizontalRule(block, 'next');
    if (adjacentHr) {
      event.preventDefault();
      removeAdjacentHorizontalRule(block, 'next');
      syncTypingStateFromCaret();
      markEditorDirty();
      scheduleAutosave();
      scheduleHistoryCommit('remove-horizontal-rule-forward');
      return true;
    }
    const nextBlock = getNextEditableBlock(block);
    if (!nextBlock || nextBlock.tagName === 'LI') return false;
    event.preventDefault();
    mergeAdjacentBlocks(block, nextBlock);
    markEditorDirty();
    scheduleAutosave();
    scheduleHistoryCommit('merge-forward');
    return true;
  }

  return false;
}

function insertPlainTextAsSemanticBlocks(text) {
  const normalized = String(text || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  const paragraphs = normalized.split(/\n{2,}/).map((part) => part.split('\n').join(' '));
  const range = getCurrentRange() || (restoreSavedRange() ? getCurrentRange() : null);
  if (!range) return;
  focusEditor();

  if (!range.collapsed) {
    range.deleteContents();
    range.collapse(true);
  }

  const anchorBlock = getBlock(range.startContainer) || createEmptyParagraph();
  const blocks = paragraphs.length ? paragraphs : [''];
  let insertionPoint = anchorBlock;

  blocks.forEach((paragraph, index) => {
    if (index === 0) {
      if (paragraph) {
        range.insertNode(buildInlineWrapperChain(paragraph));
      } else {
        range.insertNode(document.createElement('br'));
      }
      return;
    }
    const newBlock = document.createElement(anchorBlock.tagName.toLowerCase());
    Array.from(anchorBlock.classList).forEach((cls) => newBlock.classList.add(cls));
    if (paragraph) newBlock.appendChild(buildInlineWrapperChain(paragraph));
    else newBlock.appendChild(document.createElement('br'));
    insertNodeAfter(insertionPoint, newBlock);
    insertionPoint = newBlock;
  });

  normalizeBlocks();
  placeCaretAtEnd(insertionPoint);
  markEditorDirty();
  scheduleAutosave();
  scheduleHistoryCommit('paste');
}
function resetTypingState() {
  typingState.bold = false;
  typingState.italic = false;
  typingState.underline = false;
  typingState.font = null;
}

function isCaretAtStartOfBlock(range, block) {
  if (!range?.collapsed || !block) return false;
  const probe = range.cloneRange();
  probe.selectNodeContents(block);
  probe.setEnd(range.startContainer, range.startOffset);
  return !probe.toString().length;
}

function isListItemVisuallyEmpty(li) {
  const clone = li.cloneNode(true);
  clone.querySelectorAll('br').forEach((br) => br.remove());
  return !String(clone.textContent || '').trim() && !clone.querySelector('img,hr');
}

function unwrapListItem(li) {
  if (!li || li.tagName !== 'LI') return null;
  const list = li.parentElement;
  const p = document.createElement('p');
  while (li.firstChild) p.appendChild(li.firstChild);
  if (!p.childNodes.length) p.appendChild(document.createElement('br'));
  list.parentNode.insertBefore(p, list.nextSibling);
  li.remove();
  if (!list.children.length) list.remove();
  return p;
}

function limparFormatacaoAtual() {
  const range = getCurrentRange() || (restoreSavedRange() ? getCurrentRange() : null);
  if (!range) return;
  focusEditor();

  if (range.collapsed) {
    resetTypingState();
    const block = getBlock(range.startContainer);
    if (block) {
      CLASSES_ALINHAMENTO.concat(CLASSES_RECUO).forEach((cls) => block.classList.remove(cls));
    }
    saveCurrentRange();
    updateToolbarState();
    scheduleHistoryCommit('delimiter');
    return;
  }

  const blocks = getSelectedBlocks();
  withSelectionMarkers((startMarker, endMarker) => {
    unwrapSelectionPrecisely(startMarker, endMarker, (node) => node instanceof HTMLElement && (
      node.tagName === 'STRONG' || node.tagName === 'B' ||
      node.tagName === 'EM' || node.tagName === 'I' ||
      node.tagName === 'U' ||
      node.matches(INLINE_FONT_SELECTOR)
    ));

    blocks.forEach((block) => {
      CLASSES_ALINHAMENTO.concat(CLASSES_RECUO).forEach((cls) => block.classList.remove(cls));
      if (block.tagName !== 'P' && block.tagName !== 'LI' && block.tagName !== 'BLOCKQUOTE') substituirTagDoBloco(block, 'p');
    });
  });
  resetTypingState();
}

function handleListKeydown(event) {
  const range = getCurrentRange();
  if (!range?.collapsed) return false;
  const li = getBlock(range.startContainer);
  if (!li || li.tagName !== 'LI' || li.parentElement?.tagName !== 'UL') return false;

  if (event.key === 'Enter') {
    if (isListItemVisuallyEmpty(li)) {
      event.preventDefault();
      const p = unwrapListItem(li);
      normalizeBlocks();
      placeCaretAtStart(p);
      markEditorDirty();
      scheduleAutosave();
      scheduleHistoryCommit('list-exit');
      return true;
    }
    return false;
  }

  if (event.key === 'Backspace' && isCaretAtStartOfBlock(range, li) && isListItemVisuallyEmpty(li)) {
    event.preventDefault();
    const p = unwrapListItem(li);
    normalizeBlocks();
    placeCaretAtStart(p);
    markEditorDirty();
    scheduleAutosave();
    scheduleHistoryCommit('list-backspace-exit');
    return true;
  }

  return false;
}

function alternarFormatacaoInline(comando) {
  const range = getCurrentRange() || (restoreSavedRange() ? getCurrentRange() : null);
  if (!range) return;
  focusEditor();

  const key = comando === 'bold' ? 'bold' : comando === 'italic' ? 'italic' : 'underline';
  if (!key) return;

  if (range.collapsed) {
    syncTypingStateFromCaret();
    typingState[key] = !typingState[key];
    saveCurrentRange();
    updateToolbarState();
    scheduleHistoryCommit('delimiter');
    return;
  }

  const state = getRangeInlineState(range);
  const isActive = Boolean(state[key]);
  withSelectionMarkers((startMarker, endMarker) => {
    const predicate = (node) => {
      if (!(node instanceof HTMLElement)) return false;
      if (key === 'bold') return node.tagName === 'STRONG' || node.tagName === 'B';
      if (key === 'italic') return node.tagName === 'EM' || node.tagName === 'I';
      return node.tagName === 'U';
    };
    if (isActive) {
      unwrapSelectionPrecisely(startMarker, endMarker, predicate);
      return;
    }
    surroundMarkerContents(startMarker, endMarker, () => {
      if (key === 'bold') return document.createElement('strong');
      if (key === 'italic') return document.createElement('em');
      return document.createElement('u');
    });
  });
}

function aplicarFonte(nomeClasse) {
  const range = getCurrentRange() || (restoreSavedRange() ? getCurrentRange() : null);
  if (!range) return;
  focusEditor();

  if (range.collapsed) {
    syncTypingStateFromCaret();
    typingState.font = typingState.font === nomeClasse ? null : nomeClasse;
    saveCurrentRange();
    updateToolbarState();
    scheduleHistoryCommit('delimiter');
    return;
  }

  const state = getRangeInlineState(range);
  const isActive = state.font === nomeClasse;
  withSelectionMarkers((startMarker, endMarker) => {
    unwrapSelectionPrecisely(startMarker, endMarker, (node) => node instanceof HTMLElement && node.matches(INLINE_FONT_SELECTOR));
    if (isActive) return;
    surroundMarkerContents(startMarker, endMarker, () => {
      const span = document.createElement('span');
      span.className = nomeClasse;
      return span;
    });
  });
}

function substituirTagDoBloco(bloco, novaTag) {
  if (!bloco || bloco.tagName === String(novaTag).toUpperCase()) return bloco;
  const novo = document.createElement(novaTag);
  Array.from(bloco.attributes).forEach((attr) => {
    if (attr.name === 'id') return;
    novo.setAttribute(attr.name, attr.value);
  });
  while (bloco.firstChild) novo.appendChild(bloco.firstChild);
  bloco.replaceWith(novo);
  return novo;
}

function aplicarFormatoDeBloco(tag) {
  const blocos = getSelectedBlocks();
  if (!blocos.length) return;
  withSelectionMarkers(() => {
    blocos.forEach((bloco) => {
      if (bloco.tagName === 'LI' && tag !== 'li') {
        const novo = substituirTagDoBloco(bloco, tag);
        if (novo.parentElement?.matches('ul,ol') && !novo.parentElement.children.length) novo.parentElement.remove();
        return;
      }
      substituirTagDoBloco(bloco, tag);
    });
  });
}

function alternarClasseDeBloco(nomeClasse) {
  const blocos = getSelectedBlocks();
  if (!blocos.length) return;
  withSelectionMarkers(() => {
    blocos.forEach((bloco) => {
      const grupo = CLASSES_ALINHAMENTO.includes(nomeClasse) ? CLASSES_ALINHAMENTO : CLASSES_RECUO;
      if (grupo.includes(nomeClasse)) {
        const ativar = !bloco.classList.contains(nomeClasse);
        grupo.forEach((cls) => bloco.classList.remove(cls));
        if (ativar) bloco.classList.add(nomeClasse);
      }
    });
  });
}

function alternarListaNaoOrdenada() {
  const blocos = getSelectedBlocks();
  if (!blocos.length) return;
  const todosLi = blocos.every((bloco) => bloco.tagName === 'LI' && bloco.parentElement?.tagName === 'UL');

  withSelectionMarkers(() => {
    if (todosLi) {
      const ulSet = new Set(blocos.map((bloco) => bloco.parentElement));
      blocos.forEach((li) => {
        const p = document.createElement('p');
        while (li.firstChild) p.appendChild(li.firstChild);
        li.replaceWith(p);
      });
      ulSet.forEach((ul) => { if (ul && !ul.children.length) ul.remove(); });
      return;
    }

    const primeiro = blocos[0];
    const ul = document.createElement('ul');
    primeiro.parentNode.insertBefore(ul, primeiro);
    blocos.forEach((bloco) => {
      const li = bloco.tagName === 'LI' ? bloco : document.createElement('li');
      if (bloco !== li) {
        while (bloco.firstChild) li.appendChild(bloco.firstChild);
        bloco.remove();
      }
      ul.appendChild(li);
    });
  });
}

function splitBlockAtRange(block, range) {
  const afterRange = range.cloneRange();
  afterRange.selectNodeContents(block);
  afterRange.setStart(range.startContainer, range.startOffset);
  const fragmentAfter = afterRange.extractContents();

  const cloned = document.createElement(block.tagName.toLowerCase());
  Array.from(block.attributes).forEach((attr) => {
    if (attr.name !== 'id') cloned.setAttribute(attr.name, attr.value);
  });
  if (fragmentAfter.childNodes.length) cloned.appendChild(fragmentAfter);
  else cloned.appendChild(document.createElement('br'));

  if (!block.textContent.trim() && !block.querySelector('img,br')) block.appendChild(document.createElement('br'));
  return cloned;
}

function insertNodeAfter(referenceNode, newNode) {
  if (!referenceNode?.parentNode) return;
  if (referenceNode.nextSibling) referenceNode.parentNode.insertBefore(newNode, referenceNode.nextSibling);
  else referenceNode.parentNode.appendChild(newNode);
}

function placeCaretAtStart(node) {
  if (!node) return;
  const range = document.createRange();
  range.selectNodeContents(node);
  range.collapse(true);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
  saveCurrentRange();
}

function insertHorizontalRuleAtRange(range) {
  if (!range.collapsed) {
    range.deleteContents();
    range.collapse(true);
  }
  const block = getBlock(range.startContainer);
  const hr = document.createElement('hr');
  hr.className = 'editor-divider';

  if (!block) {
    range.insertNode(hr);
    const p = createEmptyParagraph();
    insertNodeAfter(hr, p);
    placeCaretAtStart(p);
    return;
  }

  const newBlock = splitBlockAtRange(block, range);
  insertNodeAfter(block, hr);
  insertNodeAfter(hr, newBlock);
  normalizeBlocks();
  placeCaretAtStart(newBlock);
}

function inserirLinhaHorizontalNoCursor() {
  const range = getCurrentRange() || (restoreSavedRange() ? getCurrentRange() : null);
  if (!range) return;
  focusEditor();
  insertHorizontalRuleAtRange(range.cloneRange());
  normalizeBlocks();
  updateToolbarState();
  markEditorDirty();
  scheduleAutosave();
  scheduleHistoryCommit('horizontal-rule');
}

function getSeparadorDecorativoAtual() {
  const salvo = localStorage.getItem(STORAGE_SEPARADOR_DECORATIVO);
  return SEPARADORES_DECORATIVOS.includes(salvo) ? salvo : SEPARADORES_DECORATIVOS[0];
}

function getDelimitadorDecorativoAtual() {
  const salvo = localStorage.getItem(STORAGE_DELIMITADOR_DECORATIVO);
  return DELIMITADORES_DECORATIVOS.find((item) => `${item.abertura}${item.fechamento}` === salvo) || DELIMITADORES_DECORATIVOS[0];
}

function updateDecorativeMenus() {
  const separadorAtual = getSeparadorDecorativoAtual();
  const delimitadorAtual = getDelimitadorDecorativoAtual();
  if (valorSeparadorDecorativo) valorSeparadorDecorativo.textContent = separadorAtual;
  if (valorDelimitadorDecorativo) valorDelimitadorDecorativo.textContent = `${delimitadorAtual.abertura}${delimitadorAtual.fechamento}`;
  document.querySelectorAll('.menu-insercao-opcao[data-tipo-menu="separador"]').forEach((btn) => btn.classList.toggle('ativo', btn.dataset.valor === separadorAtual));
  document.querySelectorAll('.menu-insercao-opcao[data-tipo-menu="delimitador"]').forEach((btn) => btn.classList.toggle('ativo', btn.dataset.abertura === delimitadorAtual.abertura && btn.dataset.fechamento === delimitadorAtual.fechamento));
}

function closeDecorativeMenus() {
  document.querySelectorAll('.controle-menu-insercao').forEach((controle) => controle.classList.remove('aberto'));
  document.querySelectorAll('.menu-insercao').forEach((menu) => menu.classList.add('oculto'));
}

function toggleDecorativeMenu(menuId) {
  const menu = document.getElementById(menuId);
  const controle = menu?.closest('.controle-menu-insercao');
  if (!menu || !controle) return;
  const abrir = menu.classList.contains('oculto');
  closeDecorativeMenus();
  if (abrir) {
    menu.classList.remove('oculto');
    controle.classList.add('aberto');
  }
}

function inserirSeparadorDecorativoNoCursor() {
  const range = getCurrentRange() || (restoreSavedRange() ? getCurrentRange() : null);
  if (!range) return;
  const simbolo = getSeparadorDecorativoAtual();
  const effectiveRange = range.cloneRange();
  if (!effectiveRange.collapsed) {
    effectiveRange.deleteContents();
    effectiveRange.collapse(true);
  }
  const block = getBlock(effectiveRange.startContainer);
  const p = document.createElement('p');
  p.className = 'editor-separador-decorativo';
  p.textContent = simbolo;
  if (!block) {
    effectiveRange.insertNode(p);
    const novo = createEmptyParagraph();
    insertNodeAfter(p, novo);
    normalizeBlocks();
    placeCaretAtStart(novo);
  } else {
    const novo = splitBlockAtRange(block, effectiveRange);
    insertNodeAfter(block, p);
    insertNodeAfter(p, novo);
    normalizeBlocks();
    placeCaretAtStart(novo);
  }
  updateToolbarState();
  markEditorDirty();
  scheduleAutosave();
  scheduleHistoryCommit('separator');
}

function inserirDelimitadorDecorativoNoCursorOuSelecao() {
  const range = getCurrentRange() || (restoreSavedRange() ? getCurrentRange() : null);
  if (!range) return;
  const delimitador = getDelimitadorDecorativoAtual();
  focusEditor();

  if (range.collapsed) {
    const node = document.createTextNode(`${delimitador.abertura}${delimitador.fechamento}`);
    const localRange = range.cloneRange();
    localRange.insertNode(node);
    const sel = window.getSelection();
    const cursor = document.createRange();
    cursor.setStart(node, delimitador.abertura.length);
    cursor.collapse(true);
    sel.removeAllRanges();
    sel.addRange(cursor);
    saveCurrentRange();
    markEditorDirty();
    scheduleAutosave();
    updateToolbarState();
    scheduleHistoryCommit('delimiter');
    return;
  }

  withSelectionMarkers((startMarker, endMarker) => {
    const startText = document.createTextNode(delimitador.abertura);
    const endText = document.createTextNode(delimitador.fechamento);
    startMarker.parentNode.insertBefore(startText, startMarker.nextSibling);
    endMarker.parentNode.insertBefore(endText, endMarker);
  });
  scheduleHistoryCommit('delimiter');
}

function limparInline(node) {
  if (!(node instanceof HTMLElement)) return;
  const wrappers = node.querySelectorAll('strong,em,u,b,i,span.fonte-sans,span.fonte-serif,span.fonte-mono,span.editor-formatacao');
  Array.from(wrappers).reverse().forEach((wrapper) => {
    while (wrapper.firstChild) wrapper.parentNode.insertBefore(wrapper.firstChild, wrapper);
    wrapper.remove();
  });
}

function limparTodaEdicaoEditor() {
  const blocos = getSelectedBlocks();
  if (!blocos.length) return;
  withSelectionMarkers(() => {
    blocos.forEach((bloco) => {
      CLASSES_ALINHAMENTO.concat(CLASSES_RECUO).forEach((cls) => bloco.classList.remove(cls));
      limparInline(bloco);
      if (!bloco.textContent.trim() && !bloco.querySelector('img,br')) bloco.appendChild(document.createElement('br'));
      if (bloco.tagName !== 'P' && bloco.tagName !== 'LI' && bloco.tagName !== 'BLOCKQUOTE') substituirTagDoBloco(bloco, 'p');
    });
  });
}

function insertImageFromFile(file) {
  if (!file || !editor) return;
  const reader = new FileReader();
  reader.onload = () => {
    focusEditor();
    const range = getCurrentRange() || (restoreSavedRange() ? getCurrentRange() : null);
    const img = document.createElement('img');
    img.src = String(reader.result || '');
    img.alt = file.name || 'imagem';

    if (!range) {
      editor.appendChild(img);
      const p = createEmptyParagraph();
      editor.appendChild(p);
      normalizeBlocks();
      placeCaretAtStart(p);
      markEditorDirty();
      scheduleAutosave();
      updateToolbarState();
      scheduleHistoryCommit('image');
      return;
    }

    let block = getBlock(range.startContainer);
    let insertionReference = null;
    let trailingBlock = null;
    const localRange = range.cloneRange();

    if (block) {
      if (!localRange.collapsed) {
        localRange.deleteContents();
        localRange.collapse(true);
        block = getBlock(localRange.startContainer) || block;
      }
      trailingBlock = splitBlockAtRange(block, localRange);
      insertionReference = block.tagName === 'LI' ? (getTopLevelContainer(block) || block) : block;
      if (trailingBlock.tagName === 'LI') {
        const converted = document.createElement('p');
        while (trailingBlock.firstChild) converted.appendChild(trailingBlock.firstChild);
        if (!converted.childNodes.length) converted.appendChild(document.createElement('br'));
        trailingBlock = converted;
      }
    } else {
      const container = getTopLevelContainer(localRange.startContainer) || editor.lastElementChild;
      insertionReference = container || null;
    }

    if (insertionReference) insertNodeAfter(insertionReference, img);
    else editor.appendChild(img);

    const p = createEmptyParagraph();
    insertNodeAfter(img, p);

    if (trailingBlock) {
      const trailingText = String(trailingBlock.textContent || '').trim();
      const hasMeaningfulTrailingContent = Boolean(trailingText) || Boolean(trailingBlock.querySelector('img,hr,br'));
      if (hasMeaningfulTrailingContent && !(trailingBlock.tagName === 'P' && trailingBlock.innerHTML === '<br>')) {
        insertNodeAfter(p, trailingBlock);
      }
    }

    normalizeBlocks();
    placeCaretAtStart(p);
    markEditorDirty();
    scheduleAutosave();
    updateToolbarState();
    scheduleHistoryCommit('image');
  };
  reader.readAsDataURL(file);
}

function updateToolbarState() {
  if (!editor) return;
  const range = getCurrentRange() || ultimoRangeEditor;
  const inlineState = range && range.collapsed ? typingState : getRangeInlineState(range);
  const currentBlock = range ? getBlock(range.startContainer) : null;
  const selectedBlocks = range ? getSelectedBlocks() : [];

  botoesComando.forEach((btn) => {
    const comando = btn.dataset.comando;
    const valor = btn.dataset.valor;
    let ativo = false;
    if (comando === 'bold') ativo = Boolean(inlineState.bold);
    else if (comando === 'italic') ativo = Boolean(inlineState.italic);
    else if (comando === 'underline') ativo = Boolean(inlineState.underline);
    else if (comando === 'formatBlock') ativo = currentBlock ? currentBlock.tagName === String(valor).toUpperCase() : false;
    else if (comando === 'insertUnorderedList') ativo = currentBlock ? currentBlock.tagName === 'LI' && currentBlock.parentElement?.tagName === 'UL' : false;
    btn.classList.toggle('ativo', ativo);
    btn.setAttribute('aria-pressed', ativo ? 'true' : 'false');
  });

  botoesBlocoClasse.forEach((btn) => {
    const cls = btn.dataset.blocoClasse;
    const activeCount = selectedBlocks.filter((block) => block.classList.contains(cls)).length;
    const ativo = activeCount > 0 && activeCount === selectedBlocks.length;
    const misto = activeCount > 0 && activeCount < selectedBlocks.length;
    btn.classList.toggle('ativo', ativo);
    btn.classList.toggle('misto', misto);
    btn.setAttribute('aria-pressed', ativo ? 'true' : 'false');
  });

  botoesSpanClasse.forEach((btn) => {
    const cls = btn.dataset.spanClasse;
    const ativo = inlineState.font === cls;
    btn.classList.toggle('ativo', ativo);
    btn.setAttribute('aria-pressed', ativo ? 'true' : 'false');
  });
}

function getHtmlEditorNormalizado() {
  if (!editor) return '<p><br></p>';
  if (!htmlCacheDirty) return htmlEditorCache;
  normalizeBlocks();
  htmlEditorCache = editor.innerHTML.trim() || '<p><br></p>';
  htmlCacheDirty = false;
  return htmlEditorCache;
}

function setStatusAutosave(tipo, texto) {
  if (!statusAutosave) return;
  statusAutosave.textContent = texto;
  statusAutosave.classList.remove('status-salvando', 'status-salvo', 'status-erro');
  if (tipo) statusAutosave.classList.add(tipo);
}

function markEditorDirty() {
  htmlCacheDirty = true;
  setStatusAutosave('status-salvando', i18n('js.saving'));
}

async function executarAutosave() {
  if (!editor || autosaveEmAndamento) {
    tentativaPendente = true;
    return;
  }

  autosaveEmAndamento = true;
  const payload = {
    titulo: String(campoTituloCapitulo?.value || '').trim(),
    html: getHtmlEditorNormalizado(),
  };
  const payloadSerializado = JSON.stringify(payload);

  if (ultimaAssinaturaCargaEnviada && payloadSerializado === ultimaAssinaturaCargaEnviada) {
    autosaveEmAndamento = false;
    setStatusAutosave('status-salvo', i18n('js.saved'));
    return;
  }

  try {
    const resposta = await fetch(`/api/projetos/${window.EDITOR_CONFIG.slug}/capitulos/${window.EDITOR_CONFIG.numero}/autosave`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payloadSerializado,
    });
    const dados = await resposta.json().catch(() => ({}));
    if (!resposta.ok || dados?.ok === false) throw new Error(dados?.erro || i18n('js.api_consult_error_now'));
    ultimaCargaEnviada = payload;
    ultimaAssinaturaCargaEnviada = payloadSerializado;
    setStatusAutosave('status-salvo', dados?.mensagem || i18n('js.saved'));
    if (autosaveRetryTimer) {
      clearTimeout(autosaveRetryTimer);
      autosaveRetryTimer = null;
    }
  } catch (erro) {
    setStatusAutosave('status-erro', erro?.message || i18n('js.api_consult_error_now'));
    if (!autosaveRetryTimer) {
      autosaveRetryTimer = setTimeout(() => {
        autosaveRetryTimer = null;
        executarAutosave();
      }, 2000);
    }
  } finally {
    autosaveEmAndamento = false;
    if (tentativaPendente) {
      tentativaPendente = false;
      executarAutosave();
    }
  }
}

function scheduleAutosave() {
  if (autosaveTimer) clearTimeout(autosaveTimer);
  if (idleAutosaveHandle) cancelIdle(idleAutosaveHandle);
  autosaveTimer = setTimeout(() => {
    idleAutosaveHandle = requestIdle(() => executarAutosave());
  }, 500);
}

function scheduleEnsureCaretVisible(force = false) {
  if (!editor) return;
  const range = getCurrentRange();
  if (!range || (!force && !range.collapsed)) return;
  const marker = document.createElement('span');
  marker.style.display = 'inline-block';
  marker.style.width = '0';
  marker.style.height = '1px';
  const clone = range.cloneRange();
  clone.collapse(true);
  clone.insertNode(marker);
  marker.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  marker.remove();
}

function handleToolbarAction(event) {
  const button = event.currentTarget;
  const comando = button.dataset.comando;
  const valor = button.dataset.valor;
  if (!comando) return;
  if (!ensureEditorSelectionForAction()) {
    focusEditor();
    ensureEditorHasContent();
    placeCaretAtEnd(editor.lastElementChild || editor);
  }

  if (comando === 'bold' || comando === 'italic' || comando === 'underline') alternarFormatacaoInline(comando);
  else if (comando === 'formatBlock') aplicarFormatoDeBloco(valor || 'p');
  else if (comando === 'insertUnorderedList') alternarListaNaoOrdenada();
  scheduleHistoryCommit(`toolbar-${comando}`);
}

function handleBlockClassAction(event) {
  const cls = event.currentTarget.dataset.blocoClasse;
  if (!cls) return;
  if (!ensureEditorSelectionForAction()) {
    focusEditor();
    ensureEditorHasContent();
    placeCaretAtEnd(editor.lastElementChild || editor);
  }
  alternarClasseDeBloco(cls);
  scheduleHistoryCommit(`block-class-${cls}`);
}

function handleFontAction(event) {
  const cls = event.currentTarget.dataset.spanClasse;
  if (!cls) return;
  if (!ensureEditorSelectionForAction()) {
    focusEditor();
    ensureEditorHasContent();
    placeCaretAtEnd(editor.lastElementChild || editor);
  }
  aplicarFonte(cls);
  scheduleHistoryCommit(`font-${cls}`);
}

function handleBeforeInput(event) {
  if (!editor) return;
  const range = getCurrentRange();
  if (!range) return;

  if (event.inputType === 'insertParagraph') {
    syncTypingStateFromCaret();
    return;
  }

  if (event.inputType === 'insertFromPaste') {
    event.preventDefault();
    return;
  }

  const hasTypingStyle = Boolean(typingState.bold || typingState.italic || typingState.underline || typingState.font);
  if (!hasTypingStyle) return;

  if (event.inputType === 'insertText' && typeof event.data === 'string') {
    event.preventDefault();
    insertStyledText(event.data);
    return;
  }
}


function handlePaste(event) {
  const text = event.clipboardData?.getData('text/plain');
  if (typeof text !== 'string') return;
  event.preventDefault();
  insertPlainTextAsSemanticBlocks(text);
}

function handleInput(event) {
  if (!isEditorComposing && event?.inputType === 'insertText' && /\s/u.test(String(event.data || ''))) {
    capitalizeFirstWordWhenCompleted();
  }
  normalizeBlocks();
  markEditorDirty();
  saveCurrentRange();
  updateToolbarState();
  scheduleAutosave();
  scheduleHistoryCommit('input');
}

function handleSelectionMutation() {
  saveCurrentRange();
  syncTypingStateFromCaret();
  updateToolbarState();
}

function applyShortcutHandler(event) {
  const key = String(event.key || '').toLowerCase();
  const mapa = event.altKey && event.ctrlKey ? MAPA_ATALHOS.CTRL_ALT : (event.altKey ? MAPA_ATALHOS.ALT : null);
  if (!mapa || !mapa[key]) return false;
  event.preventDefault();
  mapa[key]();
  scheduleHistoryCommit(`shortcut-${key}`);
  return true;
}

function capitalizarPrimeiraPalavraDeNovaLinha() {
  return capitalizeFirstWordWhenCompleted(getCurrentRange());
}

function abrirModalRevisaoOrtografica() { modalRevisaoOrtografica?.classList.remove('oculto'); }
function fecharModalRevisaoOrtografica() { modalRevisaoOrtografica?.classList.add('oculto'); }
function contarPalavrasRevisao(texto = '') { return (String(texto).trim().match(/\S+/g) || []).length; }
function textoLimpoDoBlocoRevisao(bloco) { return String(bloco?.innerText || bloco?.textContent || '').replace(/\r/g, '').trim(); }
function blocoJaRevisadoPelaIA(bloco) { return Boolean(bloco?.dataset?.revisadoIa === 'true' || bloco?.classList?.contains('bloco-revisado-ia')); }
function marcarBlocoComoRevisadoPelaIA(bloco) { if (bloco) { bloco.dataset.revisadoIa = 'true'; bloco.classList.add('bloco-revisado-ia'); } }

function montarBlocosDeRevisao() {
  return Array.from(editor.querySelectorAll(SELECTOR_BLOCOS)).filter((bloco) => !blocoJaRevisadoPelaIA(bloco) && contarPalavrasRevisao(textoLimpoDoBlocoRevisao(bloco)) > 0).map((bloco) => ({
    blocos: [bloco],
    original: textoLimpoDoBlocoRevisao(bloco),
    corrigido: '',
    revisado: false,
  }));
}

async function solicitarCorrecaoOrtografica(texto) {
  const resposta = await fetch('/api/revisao/gemini', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ texto, idioma: window.EDITOR_CONFIG?.idioma || 'pt-BR' }),
  });
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados?.erro || i18n('js.api_consult_error_now'));
  return String(dados?.texto_corrigido || texto);
}

function preencherEtapaRevisaoAtual() {
  const etapa = estadoRevisaoOrtografica.blocos[estadoRevisaoOrtografica.indice];
  if (!etapa) {
    revisaoSubtitulo.textContent = i18n('editor.review_done');
    revisaoStatus.textContent = i18n('editor.review_all_processed');
    revisaoTextoOriginal.textContent = i18n('editor.review_no_pending_blocks');
    revisaoTextoCorrigido.textContent = i18n('editor.review_you_can_close');
    btnIgnorarBlocoRevisao.disabled = true;
    btnRevisarBlocoRevisao.disabled = true;
    btnAceitarBlocoRevisao.disabled = true;
    return;
  }
  revisaoSubtitulo.textContent = i18n('editor.review_block_counter', { current: estadoRevisaoOrtografica.indice + 1, total: estadoRevisaoOrtografica.blocos.length });
  revisaoTextoOriginal.textContent = etapa.original;
  revisaoTextoCorrigido.textContent = etapa.revisado ? (etapa.corrigido || etapa.original) : i18n('editor.review_click_start_this_block');
  revisaoStatus.textContent = etapa.revisado ? i18n('editor.review_suggestion_ready') : i18n('editor.review_click_start');
  btnIgnorarBlocoRevisao.disabled = estadoRevisaoOrtografica.carregando;
  btnRevisarBlocoRevisao.disabled = estadoRevisaoOrtografica.carregando;
  btnAceitarBlocoRevisao.disabled = estadoRevisaoOrtografica.carregando || !etapa.revisado;
}

async function revisarBlocoAtualDaRevisao() {
  const etapa = estadoRevisaoOrtografica.blocos[estadoRevisaoOrtografica.indice];
  if (!etapa || estadoRevisaoOrtografica.carregando) return;
  estadoRevisaoOrtografica.carregando = true;
  revisaoTextoCorrigido.textContent = i18n('editor.review_consulting');
  revisaoStatus.textContent = i18n('editor.review_fetching_suggestion');
  try {
    etapa.corrigido = await solicitarCorrecaoOrtografica(etapa.original);
    etapa.revisado = true;
    revisaoTextoCorrigido.textContent = etapa.corrigido;
    revisaoStatus.textContent = etapa.corrigido === etapa.original ? i18n('editor.review_no_corrections') : i18n('editor.review_suggestion_ready');
  } catch (erro) {
    revisaoTextoCorrigido.textContent = i18n('editor.review_could_not_generate');
    revisaoStatus.textContent = erro?.message || i18n('editor.review_service_failure');
  } finally {
    estadoRevisaoOrtografica.carregando = false;
    preencherEtapaRevisaoAtual();
  }
}

function avancarRevisaoOrtografica() {
  estadoRevisaoOrtografica.indice += 1;
  preencherEtapaRevisaoAtual();
}

function aceitarEtapaRevisaoAtual() {
  const etapa = estadoRevisaoOrtografica.blocos[estadoRevisaoOrtografica.indice];
  if (!etapa?.revisado) return;
  etapa.blocos.forEach((bloco) => {
    bloco.textContent = etapa.corrigido || etapa.original;
    marcarBlocoComoRevisadoPelaIA(bloco);
  });
  normalizeBlocks();
  markEditorDirty();
  scheduleAutosave();
  avancarRevisaoOrtografica();
  scheduleHistoryCommit('review-accept');
}

function iniciarRevisaoOrtografica() {
  estadoRevisaoOrtografica = { blocos: montarBlocosDeRevisao(), indice: 0, carregando: false };
  abrirModalRevisaoOrtografica();
  preencherEtapaRevisaoAtual();
}

function initDecorativeMenuEvents() {
  document.querySelectorAll('.controle-menu-seta').forEach((seta) => {
    seta.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopPropagation();
      toggleDecorativeMenu(seta.dataset.toggleMenu);
    });
  });

  document.querySelectorAll('.menu-insercao-opcao[data-tipo-menu="separador"]').forEach((btn) => {
    btn.addEventListener('click', () => {
      localStorage.setItem(STORAGE_SEPARADOR_DECORATIVO, btn.dataset.valor || SEPARADORES_DECORATIVOS[0]);
      updateDecorativeMenus();
      closeDecorativeMenus();
      inserirSeparadorDecorativoNoCursor();
    });
  });

  document.querySelectorAll('.menu-insercao-opcao[data-tipo-menu="delimitador"]').forEach((btn) => {
    btn.addEventListener('click', () => {
      localStorage.setItem(STORAGE_DELIMITADOR_DECORATIVO, `${btn.dataset.abertura || '『'}${btn.dataset.fechamento || '』'}`);
      updateDecorativeMenus();
      closeDecorativeMenus();
      inserirDelimitadorDecorativoNoCursorOuSelecao();
    });
  });

  document.addEventListener('click', (event) => {
    if (!event.target.closest('.controle-menu-insercao')) closeDecorativeMenus();
  });
}

function initializeEditor() {
  if (!editor) return;
  normalizeBlocks();
  ensureEditorHasContent();
  updateDecorativeMenus();
  saveCurrentRange();
  syncTypingStateFromCaret();
  updateToolbarState();
  setStatusAutosave('status-salvo', i18n('common.ready'));
  commitHistory('init', true);

  const preserveEditorSelectionOnPointerDown = (event) => {
    if (!editor) return;
    const target = event.currentTarget;
    if (!(target instanceof HTMLElement)) return;
    if (document.activeElement === target) return;
    event.preventDefault();
    ensureEditorSelectionForAction();
  };

  botoesComando.forEach((btn) => {
    btn.addEventListener('mousedown', preserveEditorSelectionOnPointerDown);
    btn.addEventListener('click', handleToolbarAction);
  });
  botoesBlocoClasse.forEach((btn) => {
    btn.addEventListener('mousedown', preserveEditorSelectionOnPointerDown);
    btn.addEventListener('click', handleBlockClassAction);
  });
  botoesSpanClasse.forEach((btn) => {
    btn.addEventListener('mousedown', preserveEditorSelectionOnPointerDown);
    btn.addEventListener('click', handleFontAction);
  });
  btnUndoEditor?.addEventListener('click', undoEditor);
  btnRedoEditor?.addEventListener('click', redoEditor);

  btnInserirLinhaHorizontal?.addEventListener('click', inserirLinhaHorizontalNoCursor);
  btnInserirSeparadorDecorativo?.addEventListener('click', inserirSeparadorDecorativoNoCursor);
  btnInserirDelimitadorDecorativo?.addEventListener('click', inserirDelimitadorDecorativoNoCursorOuSelecao);
  btnLimparEdicao?.addEventListener('click', () => { limparFormatacaoAtual(); scheduleHistoryCommit('clear-format'); });
  btnInserirImagem?.addEventListener('click', () => inputImagemEditor?.click());
  inputImagemEditor?.addEventListener('change', (event) => {
    const arquivo = event.target.files?.[0];
    if (arquivo) insertImageFromFile(arquivo);
    event.target.value = '';
  });

  campoTituloCapitulo?.addEventListener('input', () => {
    markEditorDirty();
    scheduleAutosave();
    scheduleHistoryCommit('title');
  });

  editor.addEventListener('beforeinput', handleBeforeInput);
  editor.addEventListener('paste', handlePaste);
  editor.addEventListener('input', handleInput);
  editor.addEventListener('focus', () => { handleSelectionMutation(); scheduleEnsureCaretVisible(true); });
  editor.addEventListener('click', () => { handleSelectionMutation(); scheduleEnsureCaretVisible(true); });
  editor.addEventListener('keyup', () => { handleSelectionMutation(); scheduleEnsureCaretVisible(true); });
  editor.addEventListener('mouseup', handleSelectionMutation);
  editor.addEventListener('keydown', (event) => {
    const isMod = event.ctrlKey || event.metaKey;
    if (isMod && !event.altKey && String(event.key).toLowerCase() === 'z') {
      event.preventDefault();
      if (event.shiftKey) redoEditor();
      else undoEditor();
      return;
    }
    if (isMod && !event.altKey && String(event.key).toLowerCase() === 'y') {
      event.preventDefault();
      redoEditor();
      return;
    }
    if (applyShortcutHandler(event) === true) return;
    if (handleListKeydown(event)) return;
    if (handleStructuralKeydown(event)) return;
  });
  editor.addEventListener('compositionstart', () => { isEditorComposing = true; });
  editor.addEventListener('compositionend', () => {
    isEditorComposing = false;
    handleInput();
    handleSelectionMutation();
  });

  document.addEventListener('selectionchange', () => {
    const sel = getSelectionSafe();
    if (!sel?.rangeCount) return;
    const range = sel.getRangeAt(0);
    if (editor.contains(range.startContainer) && editor.contains(range.endContainer)) handleSelectionMutation();
  });

  initDecorativeMenuEvents();

  btnAbrirRevisaoOrtografica?.addEventListener('click', iniciarRevisaoOrtografica);
  modalRevisaoOrtografica?.querySelectorAll('[data-fechar-revisao="true"]').forEach((el) => el.addEventListener('click', fecharModalRevisaoOrtografica));
  btnIgnorarBlocoRevisao?.addEventListener('click', avancarRevisaoOrtografica);
  btnRevisarBlocoRevisao?.addEventListener('click', revisarBlocoAtualDaRevisao);
  btnAceitarBlocoRevisao?.addEventListener('click', aceitarEtapaRevisaoAtual);
}

initializeEditor();
