/**
 * Controla o editor de roteiros com paginação visual, navegação por cenas e recursos específicos do formato.
 */

/** I18n. Usada pelo fluxo principal da aplicação. */
const i18n = (key, vars = {}) => (window.t ? window.t(key, vars) : key);
const i18nData = (key, fallback = null) => ((window.APP_CONFIG && window.APP_CONFIG.i18n && Object.prototype.hasOwnProperty.call(window.APP_CONFIG.i18n, key)) ? window.APP_CONFIG.i18n[key] : fallback);

const editor = document.getElementById('editorTexto');
const campoTituloCapitulo = document.getElementById('campoTituloCapitulo');
const statusAutosave = document.getElementById('statusAutosave');
const sumarioRoteiro = document.getElementById('sumarioRoteiro');
const sidebarCardSumarioRoteiro = document.getElementById('sidebarCardSumarioRoteiro');
const indicadorTipoBloco = document.getElementById('indicadorTipoBloco');
const selectTemaRoteiro = document.getElementById('selectTemaRoteiro');
const autocomplete = document.getElementById('autocompleteRoteiro');
const toggleVisualizacao = document.getElementById('toggleVisualizacaoRoteiro');
const btnToggleVisualizacao = document.getElementById('btnToggleVisualizacaoRoteiro');
const iconeToggleVisualizacao = document.getElementById('iconeToggleVisualizacaoRoteiro');
const modalCatalogo = document.getElementById('modalCatalogo');
const modalCatalogoEditor = document.getElementById('modalCatalogoEditor');
const catalogoLista = document.getElementById('catalogoLista');
const tituloModalCatalogo = document.getElementById('tituloModalCatalogo');
const tituloModalCatalogoEditor = document.getElementById('tituloModalCatalogoEditor');
const formCatalogoEditor = document.getElementById('formCatalogoEditor');
const statusCatalogo = document.getElementById('statusCatalogo');
const catalogoTipo = document.getElementById('catalogoTipo');
const catalogoNome = document.getElementById('catalogoNome');
const catalogoNomeOriginal = document.getElementById('catalogoNomeOriginal');
const catalogoDescricao = document.getElementById('catalogoDescricao');
const modalEstatisticasRoteiro = document.getElementById('modalEstatisticasRoteiro');
const estatisticasRoteiroConteudo = document.getElementById('estatisticasRoteiroConteudo');
const barraRoteiroSticky = document.querySelector('.barra-roteiro-sticky');
const roteiroSidebar = document.querySelector('.roteiro-sidebar');

const cfg = window.EDITOR_CONFIG || {};
let autosaveTimer = null;
let autosaveRetryTimer = null;
let salvando = false;
let salvarDepois = false;
let payloadAnterior = '';
let autocompleteState = { items: [], active: -1, block: null, mode: '', context: {} };
let catalogos = {
  personagens: Array.isArray(cfg.catalogoPersonagens) ? [...cfg.catalogoPersonagens] : [],
  locais: Array.isArray(cfg.catalogoLocais) ? [...cfg.catalogoLocais] : [],
  anotacoes: Array.isArray(cfg.catalogoAnotacoes) ? [...cfg.catalogoAnotacoes] : [],
};
let pendingPersistCatalog = new Map();
let parentheticalNormalizeTimer = null;
let altLinkModeEnabled = false;
let savedSelection = null;
let catalogoLinkAtivo = null;
let catalogoItemAtivo = null;
let infoHoverTooltip = null;
let repaginationFrame = 0;
let repaginationQueuedPreserveSelection = true;
let deferredUiFrame = 0;
let needsDeferredSceneSummary = false;
let needsDeferredVisualization = false;
let softRepaginationTimer = 0;
let currentSceneCache = null;
let sceneSummarySignature = '';
let visualizationStateCache = null;
let selectionChangeFrame = 0;
let isEditorComposing = false;
let hoverFrame = 0;
let lastHoverEvent = null;
let cachedPageContents = null;
let cachedAllBlocks = null;
let cachedSceneBlocks = null;
let serializedHtmlCache = '';
let serializationDirty = true;
let idleAutosaveHandle = 0;
let cachedPageElements = null;
let cachedBlockIndexMap = null;
let cachedBlockPageIndexMap = null;
let cachedBlockToSceneMap = null;
let savedSelectionSignature = '';
let lastChangedBlock = null;
let autoCorretorSimples = null;
const serializedBlockCache = new WeakMap();
const SPLIT_BOUNDARY_REGEX = /\s|[,.!?;:-]/;

function performNativeUndo() {
  document.execCommand('undo');
}

function performNativeRedo() {
  document.execCommand('redo');
}

const BLOCK_PLACEHOLDERS = {
  neutral: '',
  scene_heading: i18n('script.placeholder_scene_heading'),
  action: i18n('script.placeholder_action'),
  character: i18n('script.placeholder_character'),
  dialogue: i18n('script.placeholder_dialogue'),
  parenthetical: i18n('script.placeholder_parenthetical'),
  shot: i18n('script.placeholder_shot'),
  transition: i18n('script.placeholder_transition'),
  comment: i18n('script.placeholder_comment'),
  music: i18n('script.placeholder_music')
};
const BLOCK_LABELS = {
  neutral: i18n('script.editor_block_neutral'),
  scene_heading: i18n('script.editor_block_scene_heading'),
  action: i18n('script.editor_block_action'),
  character: i18n('script.editor_block_character'),
  dialogue: i18n('script.editor_block_dialogue'),
  parenthetical: i18n('script.editor_block_parenthetical'),
  shot: i18n('script.editor_block_shot'),
  transition: i18n('script.editor_block_transition'),
  comment: i18n('script.editor_block_comment'),
  music: i18n('script.editor_block_music')
};
const NEXT_BLOCK = { scene_heading: 'action', character: 'dialogue' };
const UPPERCASE_BLOCK_TYPES = new Set(['scene_heading', 'character', 'shot', 'transition']);
const PERIODOS_CENA = i18nData('script.scene_periods', []);
const PREFIXOS_CENA_FIXOS = ['INT.', 'EXT.', 'INT./EXT.'];
const TRANSITIONS = i18nData('script.transitions', []);
const PAGE_MARGIN_TOP = 48;
const PAGE_MARGIN_RIGHT = 72;
const PAGE_MARGIN_BOTTOM = 48;
const PAGE_MARGIN_LEFT = 96;
const WORD_LIKE_SPLIT_SCAN = 120;
const SCRIPT_THEME_STORAGE_KEY = `roteiro-theme:${cfg.slug || 'global'}:${cfg.numero || 1}`;
const SCRIPT_THEMES = new Set(['light','dark','serpia','dark-blue','terminal-calm','warm-brown','sunset-mode','frost','pastel-pink','code-like']);
const requestIdle = window.requestIdleCallback || ((cb) => setTimeout(() => cb({ didTimeout: false, timeRemaining: () => 0 }), 1));
const cancelIdle = window.cancelIdleCallback || clearTimeout;


/** Getviewportsafearea. Usada pelo fluxo principal da aplicação. */
function getViewportSafeArea() {
  const sticky = document.querySelector('.barra-roteiro-sticky, .barra-word-sticky');
  const top = sticky ? Math.max(0, sticky.getBoundingClientRect().bottom) + 18 : 18;
  return { top, bottom: Math.max(top + 80, window.innerHeight - 28) };
}
/** Getselectioncaretrect. Usada pelo fluxo principal da aplicação. */
function getSelectionCaretRect() {
  const sel = window.getSelection();
  if (!sel || !sel.rangeCount) return null;
  const range = sel.getRangeAt(0).cloneRange();
  range.collapse(false);
  let rect = range.getBoundingClientRect();
  if ((!rect || (!rect.width && !rect.height)) && sel.focusNode) {
    const node = sel.focusNode.nodeType === Node.TEXT_NODE ? sel.focusNode.parentElement : sel.focusNode;
    rect = node?.getBoundingClientRect?.() || rect;
  }
  return rect && (rect.height || rect.width || rect.top || rect.bottom) ? rect : null;
}
let caretViewportFrame = 0;
/** Ensurescriptcaretvisible. Usada pelo fluxo principal da aplicação. */
function ensureScriptCaretVisible(force = false) {
  if (!editor) return;
  const sel = window.getSelection();
  if (!sel || !sel.rangeCount) return;
  const anchorNode = sel.anchorNode?.nodeType === Node.TEXT_NODE ? sel.anchorNode.parentElement : sel.anchorNode;
  if (!force && anchorNode && !editor.contains(anchorNode)) return;
  const rect = getSelectionCaretRect() || getCurrentBlock()?.getBoundingClientRect?.();
  if (!rect) return;
  const safe = getViewportSafeArea();
  if (rect.bottom > safe.bottom) {
    window.scrollBy({ top: rect.bottom - safe.bottom, behavior: 'auto' });
  } else if (rect.top < safe.top) {
    window.scrollBy({ top: rect.top - safe.top, behavior: 'auto' });
  }
}
/** Scheduleensurescriptcaretvisible. Usada pelo fluxo principal da aplicação. */
function scheduleEnsureScriptCaretVisible(force = false) {
  if (caretViewportFrame) cancelAnimationFrame(caretViewportFrame);
  caretViewportFrame = requestAnimationFrame(() => {
    caretViewportFrame = 0;
    ensureScriptCaretVisible(force);
  });
}
/** Invalidatestructurecaches. Usada pelo fluxo principal da aplicação. */
function invalidateStructureCaches({ pages = true, blocks = true, scenes = true, serialization = true } = {}) {
  if (pages) {
    cachedPageContents = null;
    cachedPageElements = null;
    cachedBlockPageIndexMap = null;
  }
  if (blocks) {
    cachedAllBlocks = null;
    cachedBlockIndexMap = null;
    cachedBlockToSceneMap = null;
  }
  if (scenes) {
    cachedSceneBlocks = null;
    cachedBlockToSceneMap = null;
  }
  if (serialization) serializationDirty = true;
}

/** Markblockdirty. Usada pelo fluxo principal da aplicação. */
function markBlockDirty(block) {
  if (!block) return;
  serializedBlockCache.delete(block);
  serializationDirty = true;
  lastChangedBlock = block;
}

/** Openmodal. Usada pelo fluxo principal da aplicação. */
function openModal(el) { el?.classList.remove('oculto'); }
function closeModal(el) { el?.classList.add('oculto'); }

/** Getpageoverflowamount. Usada pelo fluxo principal da aplicação. */
function getPageOverflowAmount(content) {
  if (!content) return 0;
  return Math.max(0, (content.scrollHeight || 0) - (content.clientHeight || 0));
}
/** Pageisoverflowing. Usada pelo fluxo principal da aplicação. */
function pageIsOverflowing(content) {
  return getPageOverflowAmount(content) > 1;
}
/** Blockplaintext. Usada pelo fluxo principal da aplicação. */
function blockPlainText(block) {
  return String(block?.textContent || '').replace(/\r/g, '');
}
/** Blocoterminacomletraounumero. Usada pelo fluxo principal da aplicação. */
function blocoTerminaComLetraOuNumero(block) {
  const texto = blockPlainText(block).trimEnd();
  if (!texto) return false;
  return /[\p{L}\p{N}]$/u.test(texto);
}
/** Blocodevereceberpontofinalautomatico. Usada pelo fluxo principal da aplicação. */
function blocoDeveReceberPontoFinalAutomatico(block) {
  const tipo = block?.dataset?.blockType || 'action';
  return ['neutral', 'action', 'dialogue', 'comment', 'music'].includes(tipo);
}
/** Garantirpontofinalnobloco. Usada pelo fluxo principal da aplicação. */
function garantirPontoFinalNoBloco(block) {
  if (!block || !blocoDeveReceberPontoFinalAutomatico(block) || !blocoTerminaComLetraOuNumero(block)) return;
  const ultimoNo = block.lastChild;
  if (ultimoNo && ultimoNo.nodeType === Node.TEXT_NODE) {
    ultimoNo.textContent = `${ultimoNo.textContent || ''}.`;
  } else {
    block.appendChild(document.createTextNode('.'));
  }
  invalidateStructureCaches({ pages: false });
  markBlockDirty(block);
  updateNeutralState(block);
  normalizeParentheticalBlock(block);
  updateDialogueTime(block);
}
/** Setblockplaintext. Usada pelo fluxo principal da aplicação. */
function setBlockPlainText(block, text) {
  if (!block) return;
  const value = String(text || '');
  const currentText = blockPlainText(block);
  const isCurrentlyEmpty = !normalizeSpaces(currentText) && block.childNodes.length === 1 && block.firstChild?.nodeName === 'BR';
  if ((value && currentText === value) || (!value && isCurrentlyEmpty)) return;
  if (value) block.textContent = value;
  else block.replaceChildren(document.createElement('br'));
  invalidateStructureCaches({ pages: false });
  markBlockDirty(block);
  updateNeutralState(block);
  normalizeParentheticalBlock(block);
  updateDialogueTime(block);
}
/** Findsplitoffsetforblock. Usada pelo fluxo principal da aplicação. */
function findSplitOffsetForBlock(block, container, preferredOffset = null) {
  if (!block || !container) return null;
  const originalText = blockPlainText(block);
  if (!originalText.trim()) return null;
  const maxIndex = originalText.length;
  const preferred = Math.max(1, Math.min(typeof preferredOffset === 'number' ? preferredOffset : maxIndex, maxIndex - 1));
  const candidates = [];
  const candidateSet = new Set();
  /** Pushcandidate. Usada pelo fluxo principal da aplicação. */
  const pushCandidate = (value) => {
    const safe = Math.max(1, Math.min(maxIndex - 1, value));
    if (!safe || candidateSet.has(safe)) return;
    candidateSet.add(safe);
    candidates.push(safe);
  };
  pushCandidate(preferred);
  for (let i = preferred; i >= Math.max(1, preferred - WORD_LIKE_SPLIT_SCAN); i -= 1) {
    if (SPLIT_BOUNDARY_REGEX.test(originalText[i - 1] || '')) pushCandidate(i);
  }
  for (let i = preferred + 1; i < Math.min(maxIndex, preferred + WORD_LIKE_SPLIT_SCAN); i += 1) {
    if (SPLIT_BOUNDARY_REGEX.test(originalText[i - 1] || '')) pushCandidate(i);
  }
  for (let i = preferred; i >= 1; i -= 1) pushCandidate(i);

  let chosen = null;
  for (const candidate of candidates) {
    setBlockPlainText(block, originalText.slice(0, candidate).replace(/\s+$/g, ''));
    if (!pageIsOverflowing(container)) {
      chosen = candidate;
      break;
    }
  }
  setBlockPlainText(block, originalText);
  return chosen;
}
/** Splitblockforoverflow. Usada pelo fluxo principal da aplicação. */
function splitBlockForOverflow(block, preferredOffset = null) {
  const container = block?.closest('.roteiro-page-content');
  if (!block || !container || !pageIsOverflowing(container)) return null;
  const text = blockPlainText(block);
  if (!text.trim() || text.length < 2) return null;
  const splitOffset = findSplitOffsetForBlock(block, container, preferredOffset);
  if (!splitOffset || splitOffset >= text.length) return null;

  const beforeText = text.slice(0, splitOffset).replace(/\s+$/g, '');
  const afterText = text.slice(splitOffset).replace(/^\s+/g, '');
  if (!beforeText || !afterText) return null;

  const tail = createBlock(block.dataset.blockType || 'action');
  delete tail.dataset.initialNeutral;
  setBlockPlainText(block, beforeText);
  setBlockPlainText(tail, afterText);
  block.after(tail);
  return { tail, splitOffset };
}
/** Ensurecaretflowsacrosspages. Usada pelo fluxo principal da aplicação. */
function ensureCaretFlowsAcrossPages(block, offsetHint = null) {
  if (!block) return false;
  const pageContent = block.closest('.roteiro-page-content');
  if (!pageContent || !pageIsOverflowing(pageContent)) return false;

  const split = splitBlockForOverflow(block, offsetHint);
  repaginateEditor({ preserveSelection: false });

  if (split?.tail && editor.contains(split.tail)) {
    const textLength = blockPlainText(split.tail).length;
    const desired = typeof offsetHint === 'number' ? Math.max(0, Math.min(textLength, offsetHint - split.splitOffset)) : textLength;
    setCaretOffsetWithin(split.tail, desired);
    handleBlockFocus(split.tail);
    saveSelection();
    return true;
  }

  const sameBlock = editor.contains(block) ? block : null;
  if (sameBlock) {
    const targetOffset = typeof offsetHint === 'number' ? Math.min(blockPlainText(sameBlock).length, offsetHint) : blockPlainText(sameBlock).length;
    setCaretOffsetWithin(sameBlock, targetOffset);
    handleBlockFocus(sameBlock);
    saveSelection();
    return true;
  }
  return false;
}

/** Iseditingtexttarget. Usada pelo fluxo principal da aplicação. */
function isEditingTextTarget(target) {
  if (!target) return false;
  if (target === editor || editor?.contains(target)) return true;
  return !!target.closest('input, textarea, select, [contenteditable="true"]');
}
/** Updatesidebarstickyoffset. Usada pelo fluxo principal da aplicação. */
function updateSidebarStickyOffset() {
  if (!barraRoteiroSticky || !roteiroSidebar) return;
  const top = parseFloat(getComputedStyle(barraRoteiroSticky).top || '0') || 0;
  const height = barraRoteiroSticky.getBoundingClientRect().height || barraRoteiroSticky.offsetHeight || 0;
  document.documentElement.style.setProperty('--roteiro-sidebar-top', `${Math.ceil(top + height + 2)}px`);
}
/** Focusscene. Usada pelo fluxo principal da aplicação. */
function focusScene(scene) {
  if (!scene) return;
  const page = getPageElementForBlock(scene);
  if (page) page.scrollIntoView({ behavior: 'smooth', block: 'center' });
  requestAnimationFrame(() => {
    try {
      scene.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
    } catch (_) {
      scene.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });
  placeCaretAtEnd(scene);
  highlightCurrentScene(scene);
  updateCurrentTypeIndicator(scene);
  saveSelection();
}
/** Focusscenebyindex. Usada pelo fluxo principal da aplicação. */
function focusSceneByIndex(index) {
  const scenes = getSceneBlocks();
  if (!scenes.length) return false;
  const safeIndex = Math.max(0, Math.min(index, scenes.length - 1));
  focusScene(scenes[safeIndex]);
  return true;
}
/** Focusadjacentscene. Usada pelo fluxo principal da aplicação. */
function focusAdjacentScene(direction = 1) {
  const scenes = getSceneBlocks();
  if (!scenes.length) return false;
  const current = findSceneForBlock(getCurrentBlock());
  const currentIndex = Math.max(0, scenes.indexOf(current));
  const targetIndex = Math.max(0, Math.min(currentIndex + direction, scenes.length - 1));
  if (targetIndex === currentIndex && scenes.length) {
    focusScene(scenes[currentIndex]);
    return true;
  }
  return focusSceneByIndex(targetIndex);
}
/** Triggertoolbarblock. Usada pelo fluxo principal da aplicação. */
function triggerToolbarBlock(type) {
  restoreSelection();
  applyBlockType(type);
}
/** Toggleonlyscriptmode. Usada pelo fluxo principal da aplicação. */
function toggleOnlyScriptMode() {
  if (!toggleVisualizacao) return;
  toggleVisualizacao.checked = !toggleVisualizacao.checked;
  applyVisualization();
}
/** Escapehtml. Usada pelo fluxo principal da aplicação. */
function escapeHtml(value) {
  return String(value || '').replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
}

function textoTraduzido(key, fallback) {
  const value = i18n(key);
  return value === key ? fallback : value;
}

function normalizeResourceSearch(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLocaleUpperCase('pt-BR')
    .replace(/\s+/g, ' ')
    .trim();
}

function scriptResourceTypeLabel(tipo) {
  if (tipo === 'anotacoes') return textoTraduzido('resources.note', 'Anotação');
  if (tipo === 'locais') return i18n('common.location_singular');
  return i18n('common.character_singular');
}

function scriptResourceFieldLabel(tipo, field) {
  if (tipo === 'anotacoes') return field === 'description' ? textoTraduzido('resources.note', 'Anotação') : textoTraduzido('resources.title_label', 'Título');
  return field === 'description' ? i18n('common.description') : i18n('common.name');
}

function autocompleteItemLabel(item) {
  return typeof item === 'object' && item ? String(item.label || item.nome || '') : String(item || '');
}

function autocompleteItemSignature(item) {
  if (typeof item === 'object' && item) return `${item.tipo || ''}:${autocompleteItemLabel(item)}`;
  return autocompleteItemLabel(item);
}

function dedupeResourceAutocompleteItems(items) {
  const seen = new Set();
  const result = [];
  (items || []).forEach((item) => {
    const label = autocompleteItemLabel(item);
    const key = `${item?.tipo || 'item'}:${normalizeResourceSearch(label)}`;
    if (!label || seen.has(key)) return;
    seen.add(key);
    result.push(item);
  });
  return result;
}

function createRangeFromOffsets(element, start, end = start) {
  if (!element) return null;
  const range = document.createRange();
  const locate = (target) => {
    let remaining = Math.max(0, target || 0);
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT, null);
    let node = null;
    while ((node = walker.nextNode())) {
      const len = node.textContent.length;
      if (remaining <= len) return { node, offset: remaining };
      remaining -= len;
    }
    if (element.lastChild) return { node: element.lastChild, offset: element.lastChild.textContent?.length || element.lastChild.childNodes?.length || 0 };
    return null;
  };
  const startPos = locate(start);
  const endPos = locate(end);
  if (!startPos || !endPos) return null;
  range.setStart(startPos.node, startPos.offset);
  range.setEnd(endPos.node, endPos.offset);
  return range;
}

/** Getstoredscripttheme. Usada pelo fluxo principal da aplicação. */
function getStoredScriptTheme() {
  try {
    const saved = window.localStorage.getItem(SCRIPT_THEME_STORAGE_KEY);
    return SCRIPT_THEMES.has(saved) ? saved : 'light';
  } catch (err) {
    return 'light';
  }
}
/** Applyscripttheme. Usada pelo fluxo principal da aplicação. */
function applyScriptTheme(theme, { persist = true } = {}) {
  const safeTheme = SCRIPT_THEMES.has(theme) ? theme : 'light';
  if (editor) editor.dataset.theme = safeTheme;
  const pageWrap = editor?.closest('.pagina-roteiro');
  if (pageWrap) pageWrap.dataset.theme = safeTheme;
  if (autocomplete) autocomplete.dataset.theme = safeTheme;
  if (selectTemaRoteiro && selectTemaRoteiro.value !== safeTheme) selectTemaRoteiro.value = safeTheme;
  if (persist) {
    try { window.localStorage.setItem(SCRIPT_THEME_STORAGE_KEY, safeTheme); } catch (err) {}
  }
}

/** Ensureinfohovertooltip. Usada pelo fluxo principal da aplicação. */
function ensureInfoHoverTooltip() {
  if (infoHoverTooltip) return infoHoverTooltip;
  infoHoverTooltip = document.createElement('div');
  infoHoverTooltip.className = 'info-hover-roteiro oculto';
  document.body.appendChild(infoHoverTooltip);
  return infoHoverTooltip;
}
/** Hideinfohovertooltip. Usada pelo fluxo principal da aplicação. */
function hideInfoHoverTooltip() {
  ensureInfoHoverTooltip().classList.add('oculto');
  ensureInfoHoverTooltip().innerHTML = '';
}
/** Positioninfohovertooltip. Usada pelo fluxo principal da aplicação. */
function positionInfoHoverTooltip(clientX, clientY) {
  const tip = ensureInfoHoverTooltip();
  const gap = 16;
  const maxLeft = Math.max(8, window.innerWidth - tip.offsetWidth - 8);
  const maxTop = Math.max(8, window.innerHeight - tip.offsetHeight - 8);
  let left = clientX + gap;
  let top = clientY + gap;
  if (left > maxLeft) left = Math.max(8, clientX - tip.offsetWidth - gap);
  if (top > maxTop) top = Math.max(8, clientY - tip.offsetHeight - gap);
  tip.style.left = `${left}px`;
  tip.style.top = `${top}px`;
}
/** Getcatalogitembyname. Usada pelo fluxo principal da aplicação. */
function getCatalogItemByName(tipo, nome) {
  const normalized = normalizeSpaces(nome).toLowerCase();
  if (!normalized) return null;
  return (catalogos[tipo] || []).find((item) => normalizeSpaces(item?.nome).toLowerCase() === normalized) || null;
}
/** Getcatalogcontextforblock. Usada pelo fluxo principal da aplicação. */
function getCatalogContextForBlock(block) {
  if (!block) return null;
  if (block.dataset.blockType === 'character') {
    const nome = blockText(block).replace(/[()]/g, '').trim();
    if (!nome) return null;
    const item = getCatalogItemByName('personagens', nome);
    return {
      catalogoTipo: 'personagens',
      tipo: i18n('common.character_singular'),
      nome: item?.nome || nome,
      descricao: normalizeSpaces(item?.descricao || '') || i18n('common.no_description'),
      item: item || { nome, descricao: '' },
    };
  }
  if (block.dataset.blockType === 'scene_heading') {
    const data = extractSceneHeadingData(getBlockRawText(block));
    if (!data?.local) return null;
    const item = getCatalogItemByName('locais', data.local || '');
    return {
      catalogoTipo: 'locais',
      tipo: i18n('common.location_singular'),
      nome: item?.nome || data.local,
      descricao: normalizeSpaces(item?.descricao || '') || i18n('common.no_description'),
      item: item || { nome: data.local, descricao: '' },
    };
  }
  return null;
}
/** Gethoverinfoforblock. Usada pelo fluxo principal da aplicação. */
function getCatalogContextForResourceLink(link) {
  if (!link) return null;
  const tipoRaw = link.dataset.recursoTipo || '';
  const catalogoTipo = tipoRaw === 'anotacoes' ? 'anotacoes' : (tipoRaw === 'locais' ? 'locais' : 'personagens');
  const nome = link.dataset.recursoNome || link.textContent || '';
  const item = getCatalogItemByName(catalogoTipo, nome);
  return {
    catalogoTipo,
    tipo: scriptResourceTypeLabel(catalogoTipo),
    nome: item?.nome || nome,
    descricao: normalizeSpaces(item?.descricao || '') || i18n('common.no_description'),
    item: item || { nome, descricao: '' },
    link,
  };
}
function getHoverInfoForBlock(block) {
  const context = getCatalogContextForBlock(block);
  if (!context) return null;
  return {
    catalogoTipo: context.catalogoTipo,
    tipo: context.tipo,
    nome: context.nome,
    descricao: context.descricao,
    item: context.item,
  };
}
/** Showinfohovertooltip. Usada pelo fluxo principal da aplicação. */
function showInfoHoverTooltip(info, clientX, clientY) {
  if (!info) return hideInfoHoverTooltip();
  const tip = ensureInfoHoverTooltip();
  const helpText = altLinkModeEnabled ? i18n('script.alt_pressed_click_edit') : i18n('script.hold_alt_to_edit');
  tip.innerHTML = `<strong>${escapeHtml(info.tipo)}</strong><span>${escapeHtml(info.nome || '')}</span><p>${escapeHtml(info.descricao || i18n('common.no_description'))}</p><em>${escapeHtml(helpText)}</em>`;
  tip.classList.remove('oculto');
  positionInfoHoverTooltip(clientX, clientY);
}
/** Runeditorhoverframe. Usada pelo fluxo principal da aplicação. */
function runEditorHoverFrame() {
  hoverFrame = 0;
  const event = lastHoverEvent;
  if (!event) return;
  const link = event.target instanceof Element ? event.target.closest('.editor-recurso-link') : null;
  if (link && editor?.contains(link)) {
    const linkInfo = getCatalogContextForResourceLink(link);
    if (!linkInfo) return hideInfoHoverTooltip();
    showInfoHoverTooltip(linkInfo, event.clientX, event.clientY);
    return;
  }
  const block = event.target instanceof Element ? event.target.closest('.roteiro-bloco') : null;
  if (!block || !editor?.contains(block)) return hideInfoHoverTooltip();
  const info = getHoverInfoForBlock(block);
  if (!info) return hideInfoHoverTooltip();
  showInfoHoverTooltip(info, event.clientX, event.clientY);
}
/** Handleeditorhover. Usada pelo fluxo principal da aplicação. */
function handleEditorHover(event) {
  lastHoverEvent = event;
  if (hoverFrame) return;
  hoverFrame = requestAnimationFrame(runEditorHoverFrame);
}
/** Syncaltlinkmodestate. Usada pelo fluxo principal da aplicação. */
function syncAltLinkModeState(forceValue = null) {
  altLinkModeEnabled = typeof forceValue === 'boolean' ? forceValue : altLinkModeEnabled;
  if (editor) editor.classList.toggle('alt-link-mode', !!altLinkModeEnabled);
}
/** Normalizespaces. Usada pelo fluxo principal da aplicação. */
function normalizeSpaces(value) { return String(value || '').replace(/\s+/g, ' ').trim(); }
function upperInputValue(input) {
  if (!input || input.dataset.uppercase !== 'true') return;
  const start = input.selectionStart;
  const end = input.selectionEnd;
  const upper = String(input.value || '').toUpperCase();
  if (input.value !== upper) {
    input.value = upper;
    if (typeof start === 'number' && typeof end === 'number') input.setSelectionRange(start, end);
  }
}
/** Applyuppercaseinputs. Usada pelo fluxo principal da aplicação. */
function applyUppercaseInputs(root = document) {
  root.querySelectorAll('input[data-uppercase="true"]').forEach((input) => {
    upperInputValue(input);
    if (input.dataset.uppercaseBound === 'true') return;
    input.dataset.uppercaseBound = 'true';
    input.addEventListener('input', () => upperInputValue(input));
    input.addEventListener('blur', () => upperInputValue(input));
  });
}
/** Formatcatalogname. Usada pelo fluxo principal da aplicação. */
function formatCatalogName(value, tipo = catalogoTipo?.value || '') {
  const clean = normalizeSpaces(value);
  return tipo === 'anotacoes' ? clean : clean.toUpperCase();
}
/** Validarcatalogoeditor. Usada pelo fluxo principal da aplicação. */
function validarCatalogoEditor() {
  const nome = formatCatalogName(catalogoNome?.value || '');
  const descricao = String(catalogoDescricao?.value || '').trim();
  if (!nome) return i18n('js.catalog_name_required');
  if (nome.length > 60) return i18n('js.catalog_name_max');
  if (descricao.length > 4000) return i18n('js.catalog_description_max');
  return '';
}
/** Getscenenumberprefix. Usada pelo fluxo principal da aplicação. */
function getSceneNumberPrefix(number) {
  const prefixo = String(cfg.prefixoCena ?? '0').trim();
  return `${prefixo}${number}. `;
}
/** Stripscenenumberprefix. Usada pelo fluxo principal da aplicação. */
function stripSceneNumberPrefix(text) {
  return String(text || '').replace(/^\s*\d+\.\s*/, '');
}
/** Getscenenumberprefixlength. Usada pelo fluxo principal da aplicação. */
function getSceneNumberPrefixLength(block) {
  const numero = Number(block?.dataset?.sceneNumber || cfg.numeracaoInicial || 1);
  return getSceneNumberPrefix(numero).length;
}
/** Placecaretafterscenenumber. Usada pelo fluxo principal da aplicação. */
function placeCaretAfterSceneNumber(block) {
  if (!block) return;
  setCaretOffsetWithin(block, getSceneNumberPrefixLength(block));
}
/** Getsceneheadingcontent. Usada pelo fluxo principal da aplicação. */
function getSceneHeadingContent(block) {
  return stripSceneNumberPrefix(getBlockRawText(block)).trim();
}
/** Applyscenenumbers. Usada pelo fluxo principal da aplicação. */
function applySceneNumbers() {
  const initial = Number(cfg.numeracaoInicial) || 1;
  getSceneBlocks().forEach((scene, idx) => {
    const numero = initial + idx;
    const content = stripSceneNumberPrefix(getBlockRawText(scene)).toUpperCase();
    const nextText = `${getSceneNumberPrefix(numero)}${content}`.trim();
    const currentText = normalizeSpaces(getBlockRawText(scene));
    if (currentText !== nextText) {
      scene.textContent = nextText;
      markBlockDirty(scene);
    }
    if (scene.dataset.sceneNumber !== String(numero)) {
      scene.dataset.sceneNumber = String(numero);
      markBlockDirty(scene);
    }
  });
}
/** Setstatus. Usada pelo fluxo principal da aplicação. */
function setStatus(text, kind = '') {
  if (!statusAutosave) return;
  statusAutosave.textContent = text;
  statusAutosave.className = 'status-chip';
  if (kind) statusAutosave.classList.add(kind);
}
/** Getblockrawtext. Usada pelo fluxo principal da aplicação. */
function getBlockRawText(block) { return String(block?.textContent || block?.innerText || '').replace(/ /g, ' '); }
function blockText(block) { return normalizeSpaces(getBlockRawText(block)); }
/** Guessblocktypefromtext. Usada pelo fluxo principal da aplicação. */
function guessBlockTypeFromText(text) {
  const raw = normalizeSpaces(text);
  if (!raw) return 'neutral';
  if (/^(?:\d+\.\s*)?(?:INT\.\/EXT\.|INT\.|EXT\.|CAP\s+\d+)/i.test(raw) || /^\d+\.$/.test(raw)) return 'scene_heading';
  return 'action';
}
/** Formatscriptpagenumber. Usada pelo fluxo principal da aplicação. */
function formatScriptPageNumber(pageNumber) {
  return pageNumber > 1 ? `${pageNumber}.` : '';
}
/** Renderpagechrome. Usada pelo fluxo principal da aplicação. */
function renderPageChrome(page, pageNumber) {
  if (!page) return;
  page.dataset.pageNumber = String(pageNumber);
  const headerText = normalizeSpaces(cfg.cabecalho || '');
  const footerText = normalizeSpaces(cfg.rodape || '');
  const headerLabel = page.querySelector('.roteiro-page-header-label');
  const headerNumber = page.querySelector('.roteiro-page-number');
  const footerLabel = page.querySelector('.roteiro-page-footer-label');
  if (headerLabel) headerLabel.textContent = headerText;
  if (headerNumber) headerNumber.textContent = formatScriptPageNumber(pageNumber);
  if (footerLabel) footerLabel.textContent = footerText;
}
/** Createpage. Usada pelo fluxo principal da aplicação. */
function createPage(pageNumber = 1) {
  const page = document.createElement('section');
  page.className = 'roteiro-page';
  page.dataset.pageNumber = String(pageNumber);

  const header = document.createElement('div');
  header.className = 'roteiro-page-header';
  header.setAttribute('contenteditable', 'false');

  const headerLabel = document.createElement('div');
  headerLabel.className = 'roteiro-page-header-label';

  const headerNumber = document.createElement('div');
  headerNumber.className = 'roteiro-page-number';

  header.append(headerLabel, headerNumber);

  const content = document.createElement('div');
  content.className = 'roteiro-page-content';

  const footer = document.createElement('div');
  footer.className = 'roteiro-page-footer';
  footer.setAttribute('contenteditable', 'false');

  const footerLabel = document.createElement('div');
  footerLabel.className = 'roteiro-page-footer-label';
  footer.append(footerLabel);

  page.append(header, content, footer);
  renderPageChrome(page, pageNumber);
  return page;
}
/** Getpageelements. Usada pelo fluxo principal da aplicação. */
function getPageElements() {
  if (!editor) return [];
  if (!cachedPageElements) cachedPageElements = [...editor.querySelectorAll('.roteiro-page')];
  return cachedPageElements;
}
/** Ensureblockmaps. Usada pelo fluxo principal da aplicação. */
function ensureBlockMaps() {
  if (cachedBlockIndexMap && cachedBlockPageIndexMap && cachedBlockToSceneMap) return;
  const blocks = getAllBlocks();
  cachedBlockIndexMap = new WeakMap();
  cachedBlockPageIndexMap = new WeakMap();
  cachedBlockToSceneMap = new WeakMap();
  let currentScene = null;
  blocks.forEach((block, idx) => {
    cachedBlockIndexMap.set(block, idx);
    if (block?.dataset?.blockType === 'scene_heading') currentScene = block;
    cachedBlockToSceneMap.set(block, currentScene);
    const page = block?.closest('.roteiro-page');
    if (page) {
      const pageIndex = getPageElements().indexOf(page);
      cachedBlockPageIndexMap.set(block, pageIndex);
    }
  });
}
/** Getpagecontents. Usada pelo fluxo principal da aplicação. */
function getPageContents() {
  if (!editor) return [];
  if (!cachedPageContents) cachedPageContents = [...editor.querySelectorAll('.roteiro-page-content')];
  return cachedPageContents;
}
/** Getallblocks. Usada pelo fluxo principal da aplicação. */
function getAllBlocks() {
  if (!editor) return [];
  if (!cachedAllBlocks) cachedAllBlocks = [...editor.querySelectorAll('.roteiro-bloco')];
  return cachedAllBlocks;
}

/** Getpageelementforblock. Usada pelo fluxo principal da aplicação. */
function getPageElementForBlock(block) {
  return block?.closest('.roteiro-page') || null;
}
/** Getblockpageindex. Usada pelo fluxo principal da aplicação. */
function getBlockPageIndex(block) {
  if (!block) return -1;
  ensureBlockMaps();
  return cachedBlockPageIndexMap?.get(block) ?? -1;
}
/** Getpreviousblock. Usada pelo fluxo principal da aplicação. */
function getPreviousBlock(block) {
  if (!block) return null;
  const blocks = getAllBlocks();
  ensureBlockMaps();
  const idx = cachedBlockIndexMap?.get(block) ?? blocks.indexOf(block);
  return idx > 0 ? blocks[idx - 1] : null;
}
/** Getnextblock. Usada pelo fluxo principal da aplicação. */
function getNextBlock(block) {
  if (!block) return null;
  const blocks = getAllBlocks();
  ensureBlockMaps();
  const idx = cachedBlockIndexMap?.get(block) ?? blocks.indexOf(block);
  return idx >= 0 && idx < blocks.length - 1 ? blocks[idx + 1] : null;
}
/** Isblockvisuallyempty. Usada pelo fluxo principal da aplicação. */
function isBlockVisuallyEmpty(block) {
  return !normalizeSpaces(getBlockRawText(block));
}
/** Collapseextraemptypagefromblock. Usada pelo fluxo principal da aplicação. */
function collapseExtraEmptyPageFromBlock(block, direction = 'backward') {
  if (!block || !isBlockVisuallyEmpty(block)) return false;
  const pageIndex = getBlockPageIndex(block);
  if (pageIndex < 1) return false;
  const previousBlock = getPreviousBlock(block);
  const nextBlock = getNextBlock(block);
  if (direction === 'forward' && nextBlock) {
    block.remove();
    repaginateEditor({ preserveSelection: false });
    setCaretOffsetWithin(nextBlock, 0);
    handleBlockFocus(nextBlock);
    saveSelection();
    updateSceneSummary();
    scheduleAutosave();
    return true;
  }
  if (previousBlock) {
    block.remove();
    repaginateEditor({ preserveSelection: false });
    placeCaretAtEnd(previousBlock);
    handleBlockFocus(previousBlock);
    saveSelection();
    updateSceneSummary();
    scheduleAutosave();
    return true;
  }
  return false;
}
/** Rundeferreduirefresh. Usada pelo fluxo principal da aplicação. */
function runDeferredUiRefresh() {
  deferredUiFrame = 0;
  if (needsDeferredSceneSummary) {
    needsDeferredSceneSummary = false;
    updateSceneSummary();
  }
  if (needsDeferredVisualization) {
    needsDeferredVisualization = false;
    applyVisualization();
  }
}
/** Scheduledeferreduirefresh. Usada pelo fluxo principal da aplicação. */
function scheduleDeferredUiRefresh(options = {}) {
  if (options.sceneSummary) needsDeferredSceneSummary = true;
  if (options.visualization) needsDeferredVisualization = true;
  if (deferredUiFrame) return;
  deferredUiFrame = requestAnimationFrame(runDeferredUiRefresh);
}
/** Clearsoftrepagination. Usada pelo fluxo principal da aplicação. */
function clearSoftRepagination() {
  if (!softRepaginationTimer) return;
  clearTimeout(softRepaginationTimer);
  softRepaginationTimer = 0;
}
/** Executerepagination. Usada pelo fluxo principal da aplicação. */
function executeRepagination({ preserveSelection = true, after } = {}) {
  clearSoftRepagination();
  normalizeEditor({ preserveSelection, deferSceneSummary: true, deferVisualization: true });
  const block = getCurrentBlock();
  handleBlockFocus(block);
  saveSelection();
  scheduleAutosave();
  if (typeof after === 'function') after();
}
/** Schedulerepagination. Usada pelo fluxo principal da aplicação. */
function scheduleRepagination({ preserveSelection = true, after } = {}) {
  repaginationQueuedPreserveSelection = repaginationQueuedPreserveSelection && preserveSelection;
  clearSoftRepagination();
  if (repaginationFrame) return;
  repaginationFrame = requestAnimationFrame(() => {
    repaginationFrame = 0;
    const keepSelection = repaginationQueuedPreserveSelection;
    repaginationQueuedPreserveSelection = true;
    executeRepagination({ preserveSelection: keepSelection, after });
  });
}
/** Schedulesoftrepagination. Usada pelo fluxo principal da aplicação. */
function scheduleSoftRepagination({ preserveSelection = true, after, delay = 220 } = {}) {
  repaginationQueuedPreserveSelection = repaginationQueuedPreserveSelection && preserveSelection;
  clearSoftRepagination();
  softRepaginationTimer = setTimeout(() => {
    softRepaginationTimer = 0;
    const keepSelection = repaginationQueuedPreserveSelection;
    repaginationQueuedPreserveSelection = true;
    if (repaginationFrame) return;
    executeRepagination({ preserveSelection: keepSelection, after });
  }, delay);
}
/** Schedulerepaginationafternativeedit. Usada pelo fluxo principal da aplicação. */
function scheduleRepaginationAfterNativeEdit() {
  scheduleRepagination({ preserveSelection: true });
}
/** Ensurepagestructure. Usada pelo fluxo principal da aplicação. */
function ensurePageStructure() {
  if (!editor) return;
  let pages = getPageContents();
  if (!pages.length) {
    const page = createPage(1);
    const currentNodes = [...editor.childNodes];
    editor.replaceChildren();
    editor.appendChild(page);
    const content = page.querySelector('.roteiro-page-content');
    currentNodes.forEach((node) => content.appendChild(node));
    pages = [content];
  }
  editor.setAttribute('contenteditable', 'true');
  editor.setAttribute('spellcheck', 'false');
  [...editor.querySelectorAll('.roteiro-page-header, .roteiro-page-footer')].forEach((node) => {
    node.setAttribute('contenteditable', 'false');
  });
  const firstContent = pages[0];
  [...editor.childNodes].forEach((node) => {
    if (!(node instanceof HTMLElement) || node.classList.contains('roteiro-page')) return;
    firstContent.appendChild(node);
  });
}
/** Sanitizecontainernodes. Usada pelo fluxo principal da aplicação. */
function sanitizeContainerNodes(container) {
  if (!container) return;
  [...container.childNodes].forEach((node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = String(node.textContent || '');
      if (!text.trim()) {
        node.remove();
        return;
      }
      const block = createBlock(guessBlockTypeFromText(text), escapeHtml(text));
      node.replaceWith(block);
      return;
    }
    if (!(node instanceof HTMLElement)) return;
    if (node.tagName === 'BR') {
      node.remove();
      return;
    }
    if (node.classList.contains('roteiro-page')) {
      const content = node.querySelector('.roteiro-page-content');
      if (content) sanitizeContainerNodes(content);
      return;
    }
    if (!node.classList.contains('roteiro-bloco')) {
      const html = node.innerHTML?.trim() || '';
      const text = node.innerText || node.textContent || '';
      const block = createBlock(guessBlockTypeFromText(text), html || escapeHtml(text) || '<br>');
      node.replaceWith(block);
      return;
    }
    node.setAttribute('contenteditable', 'true');
    node.setAttribute('spellcheck', 'false');
  });
}
/** Sanitizetoplevelnodes. Usada pelo fluxo principal da aplicação. */
function sanitizeTopLevelNodes() {
  if (!editor) return;
  ensurePageStructure();
  getPageContents().forEach((container) => sanitizeContainerNodes(container));
  invalidateStructureCaches();
}
/** Createblock. Usada pelo fluxo principal da aplicação. */
function createBlock(type = 'action', text = '') {
  const div = document.createElement('div');
  div.className = 'roteiro-bloco';
  div.dataset.blockType = type;
  div.dataset.placeholder = Object.prototype.hasOwnProperty.call(BLOCK_PLACEHOLDERS, type) ? BLOCK_PLACEHOLDERS[type] : i18n('common.type_here');
  div.setAttribute('contenteditable', 'true');
  div.setAttribute('spellcheck', 'false');
  if (type === 'neutral') div.dataset.initialNeutral = 'true';
  if (text) div.innerHTML = text;
  else div.appendChild(document.createElement('br'));
  invalidateStructureCaches({ pages: false });
  return div;
}
/** Ensureinitialblocks. Usada pelo fluxo principal da aplicação. */
function ensureInitialBlocks() {
  if (!getAllBlocks().length) {
    ensurePageStructure();
    const firstPage = getPageContents()[0];
    firstPage?.appendChild(createBlock('neutral', '<br>'));
  }
}
/** Getpageelementfromblock. Usada pelo fluxo principal da aplicação. */
function getPageElementFromBlock(block) {
  return block?.closest('.roteiro-page') || null;
}
/** Getpagecontentindex. Usada pelo fluxo principal da aplicação. */
function getPageContentIndex(content) {
  if (!content) return -1;
  return getPageContents().indexOf(content);
}
/** Collectblocksfrompageindex. Usada pelo fluxo principal da aplicação. */
function collectBlocksFromPageIndex(startIndex = 0) {
  const pages = getPageContents();
  if (!pages.length) return [];
  return pages.slice(Math.max(0, startIndex)).flatMap((page) => [...page.querySelectorAll('.roteiro-bloco')]);
}
/** Isneutralinitialblock. Usada pelo fluxo principal da aplicação. */
function isNeutralInitialBlock(block) {
  return !!(block && block.dataset.initialNeutral === 'true');
}
/** Updateneutralstate. Usada pelo fluxo principal da aplicação. */
function updateNeutralState(block) {
  if (!block) return;
  const hasText = !!normalizeSpaces(getBlockRawText(block));
  if (isNeutralInitialBlock(block)) {
    if (block.dataset.blockType !== 'neutral' || hasText) {
      delete block.dataset.initialNeutral;
    }
  }
  block.dataset.placeholder = Object.prototype.hasOwnProperty.call(BLOCK_PLACEHOLDERS, block.dataset.blockType) ? BLOCK_PLACEHOLDERS[block.dataset.blockType] : i18n('common.type_here');
}
/** Repaginateeditor. Usada pelo fluxo principal da aplicação. */
function repaginateEditor({ preserveSelection = true } = {}) {
  if (!editor) return;
  invalidateStructureCaches();
  ensurePageStructure();
  const currentBlock = preserveSelection ? getCurrentBlock() : null;
  const repaginationAnchorBlock = currentBlock || lastChangedBlock;
  const currentOffset = currentBlock ? caretOffsetWithin(currentBlock) : null;
  let selectionTargetBlock = currentBlock;
  let selectionTargetOffset = currentOffset;

  const allContents = getPageContents();
  let repaginateStartIndex = 0;
  if (repaginationAnchorBlock) {
    const currentPage = getPageElementFromBlock(repaginationAnchorBlock);
    const currentPageContent = currentPage?.querySelector('.roteiro-page-content') || null;
    const currentIndex = getPageContentIndex(currentPageContent);
    if (currentIndex > 0) repaginateStartIndex = currentIndex - 1;
  }

  const blocks = collectBlocksFromPageIndex(repaginateStartIndex);
  let pages = getPageElements().slice();
  let startPage = pages[repaginateStartIndex] || null;

  if (!startPage) {
    editor.replaceChildren();
    startPage = createPage(1);
    editor.appendChild(startPage);
    pages = [startPage];
    repaginateStartIndex = 0;
  }

  const startContent = startPage.querySelector('.roteiro-page-content');
  startContent.replaceChildren();
  pages.slice(repaginateStartIndex + 1).forEach((pageEl) => pageEl.remove());

  let page = startPage;
  let content = startContent;
  const newPages = [startPage];

  if (!blocks.length) {
    content.appendChild(createBlock('neutral', '<br>'));
  } else {
    for (const block of blocks) {
      block.setAttribute('contenteditable', 'true');
      block.setAttribute('spellcheck', 'false');
      content.appendChild(block);

      if (!pageIsOverflowing(content)) continue;

      const shouldPreferCaretSplit = preserveSelection && currentBlock === block && typeof currentOffset === 'number';
      const split = splitBlockForOverflow(block, shouldPreferCaretSplit ? currentOffset : null);

      let overflowNode = null;
      if (split?.tail) {
        overflowNode = split.tail;
        if (preserveSelection && currentBlock === block && typeof currentOffset === 'number') {
          if (currentOffset > split.splitOffset) {
            selectionTargetBlock = split.tail;
            selectionTargetOffset = Math.max(0, currentOffset - split.splitOffset);
          } else {
            selectionTargetBlock = block;
            selectionTargetOffset = Math.min(currentOffset, blockPlainText(block).length);
          }
        }
      } else if (content.children.length > 1) {
        overflowNode = block;
        block.remove();
        if (preserveSelection && currentBlock === block) {
          selectionTargetBlock = block;
          selectionTargetOffset = currentOffset;
        }
      }

      if (!overflowNode) continue;

      const nextPageNumber = repaginateStartIndex + newPages.length + 1;
      const nextPage = createPage(nextPageNumber);
      const nextContent = nextPage.querySelector('.roteiro-page-content');
      nextContent.appendChild(overflowNode);
      page.after(nextPage);
      newPages.push(nextPage);
      page = nextPage;
      content = nextContent;
    }
  }

  getPageElements().forEach((pageEl, idx) => {
    renderPageChrome(pageEl, idx + 1);
  });
  invalidateStructureCaches();
  lastChangedBlock = null;

  if (preserveSelection && selectionTargetBlock && editor.contains(selectionTargetBlock)) {
    if (typeof selectionTargetOffset === 'number') setCaretOffsetWithin(selectionTargetBlock, selectionTargetOffset);
    else placeCaretAtEnd(selectionTargetBlock);
  }
}
/** Normalizeeditor. Usada pelo fluxo principal da aplicação. */
function normalizeEditor({ preserveSelection = true, deferSceneSummary = false, deferVisualization = false } = {}) {
  if (!editor) return;
  sanitizeTopLevelNodes();
  ensureInitialBlocks();
  const blocks = getAllBlocks();
  if (blocks.length === 1) {
    const first = blocks[0];
    if (first instanceof HTMLElement) {
      const vazio = !normalizeSpaces(getBlockRawText(first));
      if (vazio && first.dataset.blockType === 'action' && !first.dataset.initialNeutral) {
        first.dataset.blockType = 'neutral';
        first.dataset.initialNeutral = 'true';
      }
    }
  }
  blocks.forEach((child) => {
    if (!(child instanceof HTMLElement)) return;
    if (!child.dataset.blockType) child.dataset.blockType = 'action';
    child.setAttribute('contenteditable', 'true');
    child.setAttribute('spellcheck', 'false');
    if (!child.hasChildNodes()) child.replaceChildren(document.createElement('br'));
    updateNeutralState(child);
    updateDialogueTime(child);
  });
  repaginateEditor({ preserveSelection });
  if (deferSceneSummary || deferVisualization) {
    scheduleDeferredUiRefresh({ sceneSummary: true, visualization: true });
  } else {
    updateSceneSummary();
    applyVisualization();
  }
  updateCurrentTypeIndicator();
}
/** Getcurrentblock. Usada pelo fluxo principal da aplicação. */
function getCurrentBlock() {
  const sel = window.getSelection();
  if (!sel || !sel.rangeCount) return null;
  let node = sel.anchorNode;
  if (!node) return null;
  if (node.nodeType === Node.TEXT_NODE) node = node.parentElement;
  return node?.closest('.roteiro-bloco') || null;
}
/** Placecaretatend. Usada pelo fluxo principal da aplicação. */
function placeCaretAtEnd(el) {
  if (!el) return;
  el.focus();
  const range = document.createRange();
  range.selectNodeContents(el);
  range.collapse(false);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
}
/** Capitalizeblocktext. Usada pelo fluxo principal da aplicação. */
function capitalizeBlockText(text) {
  const raw = String(text || '');
  if (!raw) return '';

  const lower = raw.toLocaleLowerCase('pt-BR');
  let capitalizeNext = true;
  let result = '';

  for (const char of lower) {
    if (capitalizeNext && /[\p{L}\p{N}]/u.test(char)) {
      result += char.toLocaleUpperCase('pt-BR');
      capitalizeNext = false;
      continue;
    }
    result += char;
    if (/[.!?]/.test(char)) capitalizeNext = true;
  }

  return result;
}
/** Capitalizefirstwordonleadingspace. Usada pelo fluxo principal da aplicação. */
function capitalizeFirstWordOnLeadingSpace(block) {
  if (!block || block.dataset.blockType === 'neutral') return false;

  const offsets = getSelectionOffsetsWithin(block);
  if (!offsets?.collapsed) return false;

  const textBeforeCursor = getBlockRawText(block).slice(0, offsets.start);
  if (!/^\s*[^\s]+\s$/u.test(textBeforeCursor)) return false;

  const raw = getBlockRawText(block);
  const match = raw.match(/^(\s*)(\p{Ll})([^\s]*)/u);
  if (!match) return false;

  const letterIndex = match[1].length;
  const currentLetter = raw.charAt(letterIndex);
  const uppercaseLetter = currentLetter.toLocaleUpperCase('pt-BR');
  if (!currentLetter || currentLetter === uppercaseLetter) return false;

  block.textContent = `${raw.slice(0, letterIndex)}${uppercaseLetter}${raw.slice(letterIndex + 1)}`;
  markBlockDirty(block);
  setCaretOffsetWithin(block, offsets.start);
  saveSelection();
  return true;
}
/** Normalizeuppercaseblock. Usada pelo fluxo principal da aplicação. */
function normalizeUppercaseBlock(block) {
  if (!block) return;
  if (UPPERCASE_BLOCK_TYPES.has(block.dataset.blockType)) {
    const raw = getBlockRawText(block);
    const upper = raw.toUpperCase();
    if (raw !== upper) {
      const offsets = getSelectionOffsetsWithin(block);
      block.textContent = upper;
      markBlockDirty(block);
      if (offsets) {
        const nextStart = Math.min(offsets.start, upper.length);
        const nextEnd = Math.min(offsets.end, upper.length);
        if (offsets.collapsed) setCaretOffsetWithin(block, nextStart);
        else setSelectionOffsetsWithin(block, nextStart, nextEnd);
      } else {
        placeCaretAtEnd(block);
      }
      saveSelection();
    }
  }
}
/** Normalizecapitalizedblock. Usada pelo fluxo principal da aplicação. */
function normalizeCapitalizedBlock(block) {
  if (!block || UPPERCASE_BLOCK_TYPES.has(block.dataset.blockType) || block.dataset.blockType === 'neutral') return;
  const raw = getBlockRawText(block);
  const capitalized = capitalizeBlockText(raw);
  if (raw !== capitalized) {
    const offsets = getSelectionOffsetsWithin(block);
    block.textContent = capitalized;
    markBlockDirty(block);
    if (offsets) {
      const nextStart = Math.min(offsets.start, capitalized.length);
      const nextEnd = Math.min(offsets.end, capitalized.length);
      if (offsets.collapsed) setCaretOffsetWithin(block, nextStart);
      else setSelectionOffsetsWithin(block, nextStart, nextEnd);
    } else {
      placeCaretAtEnd(block);
    }
    saveSelection();
  }
}
/** Caretoffsetwithin. Usada pelo fluxo principal da aplicação. */
function caretOffsetWithin(element) {
  const sel = window.getSelection();
  if (!sel || !sel.rangeCount || !element) return null;
  const range = sel.getRangeAt(0);
  if (!element.contains(range.startContainer)) return null;
  const preRange = range.cloneRange();
  preRange.selectNodeContents(element);
  preRange.setEnd(range.startContainer, range.startOffset);
  return preRange.toString().length;
}
/** Setcaretoffsetwithin. Usada pelo fluxo principal da aplicação. */
function setCaretOffsetWithin(element, offset) {
  if (!element) return;
  const selection = window.getSelection();
  const range = document.createRange();
  let remaining = Math.max(0, offset || 0);
  const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT, null);
  let node = null;
  while ((node = walker.nextNode())) {
    const len = node.textContent.length;
    if (remaining <= len) {
      range.setStart(node, remaining);
      range.collapse(true);
      selection.removeAllRanges();
      selection.addRange(range);
      return;
    }
    remaining -= len;
  }
  placeCaretAtEnd(element);
}

/** Saveselection. Usada pelo fluxo principal da aplicação. */
function saveSelection() {
  const sel = window.getSelection();
  if (!sel || !sel.rangeCount || !editor) return;
  const range = sel.getRangeAt(0);
  if (!editor.contains(range.commonAncestorContainer)) return;
  const block = getCurrentBlock();
  if (!block || !editor.contains(block)) return;

  const offsets = getSelectionOffsetsWithin(block);
  if (!offsets) return;

  const signature = [block, offsets.start, offsets.end, offsets.collapsed].join('::');
  if (signature === savedSelectionSignature) return;

  savedSelection = {
    block,
    start: offsets.start,
    end: offsets.end,
    collapsed: offsets.collapsed,
  };
  savedSelectionSignature = signature;
}
/** Restoreselection. Usada pelo fluxo principal da aplicação. */
function restoreSelection() {
  if (!savedSelection || !savedSelection.block || !savedSelection.block.isConnected) return false;
  const { block, start, end, collapsed } = savedSelection;
  if (collapsed) setCaretOffsetWithin(block, start);
  else setSelectionOffsetsWithin(block, start, end);
  savedSelectionSignature = '';
  return true;
}
/** Selectallscriptblocks. Usada pelo fluxo principal da aplicação. */
function selectAllScriptBlocks() {
  if (!editor) return false;
  const blocks = getAllBlocks();
  const selection = window.getSelection();
  if (!selection || !blocks.length) return false;

  const first = blocks[0];
  const last = blocks[blocks.length - 1];
  const range = document.createRange();
  range.setStart(first, 0);
  range.setEnd(last, last.childNodes.length);

  selection.removeAllRanges();
  selection.addRange(range);
  saveSelection();
  updateCurrentTypeIndicator(first);
  return true;
}
/** Getselectionoffsetswithin. Usada pelo fluxo principal da aplicação. */
function getSelectionOffsetsWithin(element) {
  const sel = window.getSelection();
  if (!sel || !sel.rangeCount || !element) return null;
  const range = sel.getRangeAt(0);
  if (!element.contains(range.startContainer) || !element.contains(range.endContainer)) return null;
  const preStart = range.cloneRange();
  preStart.selectNodeContents(element);
  preStart.setEnd(range.startContainer, range.startOffset);
  const preEnd = range.cloneRange();
  preEnd.selectNodeContents(element);
  preEnd.setEnd(range.endContainer, range.endOffset);
  return {
    start: preStart.toString().length,
    end: preEnd.toString().length,
    collapsed: range.collapsed,
  };
}
/** Setselectionoffsetswithin. Usada pelo fluxo principal da aplicação. */
function setSelectionOffsetsWithin(element, start, end = start) {
  if (!element) return;
  const selection = window.getSelection();
  const range = document.createRange();
  /** Locate. Usada pelo fluxo principal da aplicação. */
  const locate = (target) => {
    let remaining = Math.max(0, target || 0);
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT, null);
    let node = null;
    while ((node = walker.nextNode())) {
      const len = node.textContent.length;
      if (remaining <= len) return { node, offset: remaining };
      remaining -= len;
    }
    return null;
  };
  const startPos = locate(start);
  const endPos = locate(end);
  if (startPos && endPos) {
    range.setStart(startPos.node, startPos.offset);
    range.setEnd(endPos.node, endPos.offset);
    selection.removeAllRanges();
    selection.addRange(range);
    saveSelection();
    return;
  }
  setCaretOffsetWithin(element, end);
  saveSelection();
}
/** Wrapselectionwithparentheses. Usada pelo fluxo principal da aplicação. */
function wrapSelectionWithParentheses(block) {
  if (!block) return false;
  const offsets = getSelectionOffsetsWithin(block);
  const text = getBlockRawText(block);
  if (!offsets) {
    const trimmed = normalizeSpaces(text);
    if (trimmed) {
      block.textContent = `(${trimmed.replace(/^\(+/, '').replace(/\)+$/, '')})`;
      markBlockDirty(block);
      setCaretOffsetWithin(block, block.innerText.length - 1);
      saveSelection();
      return true;
    }
    block.textContent = '()';
    markBlockDirty(block);
    setCaretOffsetWithin(block, 1);
    saveSelection();
    return true;
  }

  let start = offsets.start;
  let end = offsets.end;
  let nextText = text;

  if (!offsets.collapsed && end > start) {
    nextText = `${text.slice(0, start)}(${text.slice(start, end)})${text.slice(end)}`;
    block.textContent = nextText;
    markBlockDirty(block);
    setSelectionOffsetsWithin(block, start + 1, end + 1);
    return true;
  }

  const trimmed = normalizeSpaces(text);
  if (trimmed) {
    const clean = text.replace(/^\(+/, '').replace(/\)+$/, '');
    block.textContent = `(${clean})`;
    markBlockDirty(block);
    const desired = Math.max(1, Math.min((offsets.start || 0) + 1, block.innerText.length - 1));
    setCaretOffsetWithin(block, desired);
    saveSelection();
    return true;
  }

  block.textContent = '()';
  markBlockDirty(block);
  setCaretOffsetWithin(block, 1);
  saveSelection();
  return true;
}
/** Normalizeparentheticalblock. Usada pelo fluxo principal da aplicação. */
function normalizeParentheticalBlock(block, options = {}) {
  if (!block || block.dataset.blockType !== 'parenthetical') return;
  const { preserveSpacing = false } = options;
  const currentText = getBlockRawText(block);
  if (!currentText) return;

  const offset = caretOffsetWithin(block);
  const innerRaw = currentText.replace(/^\(+/, '').replace(/\)+$/, '');
  const inner = preserveSpacing ? innerRaw : normalizeSpaces(innerRaw);
  const wrapped = inner ? `(${inner})` : '';

  if (wrapped && wrapped !== currentText) {
    block.textContent = wrapped;
    markBlockDirty(block);
    const defaultOffset = preserveSpacing ? Math.max(1, wrapped.length - 1) : wrapped.length - 1;
    const desired = typeof offset === 'number'
      ? Math.min(Math.max(1, offset), wrapped.length - 1)
      : defaultOffset;
    setCaretOffsetWithin(block, desired);
  }
}
/** Estimatedialogueseconds. Usada pelo fluxo principal da aplicação. */
function estimateDialogueSeconds(text, wpm = 170) {
  const normalized = normalizeSpaces(text);
  if (!normalized) return 0;
  const words = normalized.split(/\s+/).filter(Boolean).length;
  const baseTime = (words / wpm) * 60;
  const pauses = (normalized.match(/[.,;:!?]/g) || []).length;
  const pauseTime = pauses * 0.4;
  const total = baseTime + pauseTime;
  if (total > 0 && total < 1) return 0.5;
  return Math.max(0, Math.round(total * 2) / 2);
}
/** Formatdialoguetime. Usada pelo fluxo principal da aplicação. */
function formatDialogueTime(seconds) {
  const total = Math.max(0, Number(seconds) || 0);
  const formatted = Number.isInteger(total)
    ? String(total)
    : new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(total);
  return `${formatted} ${total === 1 ? i18n('script.seconds_singular') : i18n('script.seconds_plural')}`;
}
/** Updatedialoguetime. Usada pelo fluxo principal da aplicação. */
function updateDialogueTime(block) {
  if (!block) return;
  if (block.dataset.blockType !== 'dialogue') {
    delete block.dataset.dialogueTimeLabel;
    delete block.dataset.dialogueTimeSeconds;
    return;
  }
  const seconds = estimateDialogueSeconds(getBlockRawText(block));
  if (seconds > 0) {
    block.dataset.dialogueTimeSeconds = String(seconds);
    block.dataset.dialogueTimeLabel = formatDialogueTime(seconds);
  } else {
    delete block.dataset.dialogueTimeLabel;
    delete block.dataset.dialogueTimeSeconds;
  }
}
/** Refreshdialoguetimes. Usada pelo fluxo principal da aplicação. */
function refreshDialogueTimes() {
  getAllBlocks().forEach((block) => updateDialogueTime(block));
}
/** Updatecurrenttypeindicator. Usada pelo fluxo principal da aplicação. */
function updateCurrentTypeIndicator(block = getCurrentBlock()) {
  if (indicadorTipoBloco) indicadorTipoBloco.textContent = BLOCK_LABELS[block?.dataset?.blockType] || i18n('script.editor_block_action');
}
/** Applyblocktype. Usada pelo fluxo principal da aplicação. */
function applyBlockType(type) {
  restoreSelection();
  invalidateStructureCaches({ pages: false });
  const block = getCurrentBlock();
  if (!block) return;
  block.focus();
  const previousType = block.dataset.blockType || 'action';
  const previousText = getBlockRawText(block);
  const offsets = getSelectionOffsetsWithin(block);
  block.dataset.blockType = type;
  block.dataset.placeholder = BLOCK_PLACEHOLDERS[type] || i18n('common.type_here');

  if (previousType === 'scene_heading' && type !== 'scene_heading') {
    block.textContent = stripSceneNumberPrefix(previousText);
    markBlockDirty(block);
  }
  if (previousType === 'parenthetical' && type !== 'parenthetical') {
    block.textContent = normalizeSpaces(previousText).replace(/^\(+/, '').replace(/\)+$/, '');
    markBlockDirty(block);
  }

  if (type === 'neutral') {
    block.textContent = '';
    markBlockDirty(block);
    setCaretOffsetWithin(block, 0);
  }

  if (type === 'scene_heading') {
    const content = stripSceneNumberPrefix(getBlockRawText(block)).toUpperCase();
    const numero = Number(block.dataset.sceneNumber || cfg.numeracaoInicial || 1);
    block.textContent = `${getSceneNumberPrefix(numero)}${content}`.trimEnd();
    markBlockDirty(block);
    applySceneNumbers();
  } else if (type === 'parenthetical') {
    if (UPPERCASE_BLOCK_TYPES.has(previousType)) {
      const normalized = capitalizeBlockText(getBlockRawText(block));
      if (normalized !== getBlockRawText(block)) {
        block.textContent = normalized;
        markBlockDirty(block);
      }
    }
    wrapSelectionWithParentheses(block);
  } else if (UPPERCASE_BLOCK_TYPES.has(type)) {
    normalizeUppercaseBlock(block);
  } else if (UPPERCASE_BLOCK_TYPES.has(previousType)) {
    normalizeCapitalizedBlock(block);
  }

  updateNeutralState(block);
  updateDialogueTime(block);
  saveSelection();
  updateSceneSummary();
  applyVisualization();
  updateCurrentTypeIndicator(block);

  if (type === 'scene_heading') {
    placeCaretAfterSceneNumber(block);
  } else if (type === 'parenthetical') {
    const parentheticalText = getBlockRawText(block);
    const hasOnlyParentheses = parentheticalText === '()';
    if (hasOnlyParentheses) {
      setCaretOffsetWithin(block, 1);
    } else if (previousType !== 'parenthetical') {
      const endInsideParentheses = Math.max(1, parentheticalText.length - 1);
      setCaretOffsetWithin(block, endInsideParentheses);
    }
  } else if (previousType === 'scene_heading') {
    setCaretOffsetWithin(block, 0);
  } else {
    placeCaretAtEnd(block);
  }

  scheduleAutosave();
  maybeAutocomplete(block);
}
/** Getsceneblocks. Usada pelo fluxo principal da aplicação. */
function getSceneBlocks() {
  if (!editor) return [];
  if (!cachedSceneBlocks) cachedSceneBlocks = getAllBlocks().filter((block) => block?.dataset?.blockType === 'scene_heading');
  return cachedSceneBlocks;
}
/** Getnextcapnumber. Usada pelo fluxo principal da aplicação. */
function getNextCapNumber() {
  const nums = getSceneBlocks().map((scene) => {
    const match = blockText(scene).match(/^CAP\s+(\d+)\b/i);
    return match ? Number(match[1]) : 0;
  }).filter(Boolean);
  return nums.length ? Math.max(...nums) + 1 : 1;
}
/** Getsceneprefixsuggestions. Usada pelo fluxo principal da aplicação. */
function getScenePrefixSuggestions() { return [...PREFIXOS_CENA_FIXOS, `CAP ${getNextCapNumber()}`]; }
function truncateSummaryLabel(text, maxLength = 38) {
  const normalized = normalizeSpaces(text);
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`;
}

/** Updatescenesummaryvisibility. Usada pelo fluxo principal da aplicação. */
function updateSceneSummaryVisibility(totalScenes) {
  if (!sidebarCardSumarioRoteiro) return;
  sidebarCardSumarioRoteiro.classList.toggle('oculto', !(Number(totalScenes) > 0));
}

/** Buildscenesummarysignature. Usada pelo fluxo principal da aplicação. */
function buildSceneSummarySignature(scenes) {
  return scenes.map((scene, idx) => `${idx}:${getSceneHeadingContent(scene)}:${scene.dataset.sceneNumber || ''}`).join('|');
}
/** Updatescenesummary. Usada pelo fluxo principal da aplicação. */
function updateSceneSummary() {
  applySceneNumbers();
  if (!sumarioRoteiro) return;
  const scenes = getSceneBlocks();
  updateSceneSummaryVisibility(scenes.length);
  const initial = Number(cfg.numeracaoInicial) || 1;
  const signature = buildSceneSummarySignature(scenes);
  if (sceneSummarySignature === signature && sumarioRoteiro.childElementCount === scenes.length) {
    highlightCurrentScene(getCurrentBlock());
    return;
  }
  sceneSummarySignature = signature;
  const fragment = document.createDocumentFragment();
  scenes.forEach((scene, idx) => {
    scene.dataset.sceneNumber = String(initial + idx);
    scene.id = `scene-${idx + 1}`;
    const numeroCena = getSceneNumberPrefix(scene.dataset.sceneNumber).trim();
    const cabecalhoCena = getSceneHeadingContent(scene) || `CENA ${scene.dataset.sceneNumber}`;
    const fullLabel = `${numeroCena} ${cabecalhoCena}`.trim();
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'item-sumario';
    item.dataset.sceneId = scene.id;
    item.dataset.sceneIndex = String(idx);
    const span = document.createElement('span');
    span.className = 'texto-sumario texto-sumario-cabecalho';
    span.title = fullLabel;
    span.textContent = truncateSummaryLabel(fullLabel);
    item.appendChild(span);
    fragment.appendChild(item);
  });
  sumarioRoteiro.replaceChildren(fragment);
  highlightCurrentScene(getCurrentBlock());
}
/** Findsceneforblock. Usada pelo fluxo principal da aplicação. */
function findSceneForBlock(block) {
  const scenes = getSceneBlocks();
  if (!block) return scenes[0] || null;
  if (block.dataset?.blockType === 'scene_heading') return block;
  ensureBlockMaps();
  return cachedBlockToSceneMap?.get(block) || scenes[0] || null;
}
/** Highlightcurrentscene. Usada pelo fluxo principal da aplicação. */
function highlightCurrentScene(block) {
  const scenes = getSceneBlocks();
  updateSceneSummaryVisibility(scenes.length);
  const currentScene = findSceneForBlock(block);
  if (currentSceneCache === currentScene && sumarioRoteiro?.querySelector('.item-sumario.ativo')) return;
  currentSceneCache = currentScene;
  [...(sumarioRoteiro?.children || [])].forEach((el, idx) => el.classList.toggle('ativo', scenes[idx] === currentScene));
}
/** Serialize. Usada pelo fluxo principal da aplicação. */
function serialize() {
  if (!serializationDirty && serializedHtmlCache) return serializedHtmlCache;
  const parts = [];
  getAllBlocks().forEach((node) => {
    if (!(node instanceof HTMLElement) || !node.classList.contains('roteiro-bloco')) return;
    let html = serializedBlockCache.get(node);
    if (!html) {
      const clone = node.cloneNode(true);
      window.AutoCorretorSimples?.stripDecorationsFromClone?.(clone);
      html = clone.outerHTML;
      serializedBlockCache.set(node, html);
    }
    parts.push(html);
  });
  serializedHtmlCache = parts.join('') || '<div class="roteiro-bloco" data-block-type="neutral" data-initial-neutral="true"><br></div>';
  serializationDirty = false;
  return serializedHtmlCache;
}
async function doAutosave(force = false) {
  if (salvando) { salvarDepois = true; return; }
  const payload = JSON.stringify({ titulo: campoTituloCapitulo?.value?.trim() || i18n('script.no_title'), html: serialize() });
  if (!force && payload === payloadAnterior) return;
  salvando = true;
  setStatus(i18n('js.saving'), 'status-salvando');
  try {
    const resp = await fetch(`/api/projetos/${cfg.slug}/capitulos/${cfg.numero}/autosave`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: payload,
    });
    const data = await resp.json();
    if (!resp.ok || !data.ok) throw new Error(data.erro || i18n('editor.save_failed'));
    payloadAnterior = payload;
    if (autosaveRetryTimer) {
      clearTimeout(autosaveRetryTimer);
      autosaveRetryTimer = null;
    }
    setStatus(i18n('js.saved'), 'status-salvo');
  } catch (err) {
    setStatus(err.message || i18n('js.save_error'), 'status-erro');
    if (!autosaveRetryTimer) {
      autosaveRetryTimer = setTimeout(() => {
        autosaveRetryTimer = null;
        doAutosave(true);
      }, 1600);
    }
  } finally {
    salvando = false;
    if (salvarDepois) { salvarDepois = false; doAutosave(true); }
  }
}
/** Scheduleautosave. Usada pelo fluxo principal da aplicação. */
function scheduleAutosave() {
  clearTimeout(autosaveTimer);
  if (autosaveRetryTimer) {
    clearTimeout(autosaveRetryTimer);
    autosaveRetryTimer = null;
  }
  if (idleAutosaveHandle) { cancelIdle(idleAutosaveHandle); idleAutosaveHandle = 0; }
  setStatus(i18n('js.pending_changes'), 'status-salvando');
  autosaveTimer = setTimeout(() => {
    idleAutosaveHandle = requestIdle(() => {
      idleAutosaveHandle = 0;
      doAutosave(false);
    });
  }, 750);
}
/** Hideautocomplete. Usada pelo fluxo principal da aplicação. */
function hideAutocomplete() {
  if (!autocomplete) return;
  autocomplete.classList.add('oculto');
  autocomplete.replaceChildren();
  autocompleteState = { items: [], active: -1, block: null, mode: '', context: {} };
}
/** Getnames. Usada pelo fluxo principal da aplicação. */
function getNames(tipo) { return (catalogos[tipo] || []).map(item => normalizeSpaces(item.nome)).filter(Boolean); }
function filterUnique(values) {
  return [...new Map(values.filter(Boolean).map(v => [String(v).toUpperCase(), String(v).toUpperCase()])).values()];
}
function refreshCatalogosFromResponse(data, tipo) {
  if (!data) return;
  if (Array.isArray(data.personagens)) catalogos.personagens = data.personagens;
  if (Array.isArray(data.locais)) catalogos.locais = data.locais;
  if (Array.isArray(data.lugares)) catalogos.locais = data.lugares;
  if (Array.isArray(data.anotacoes)) catalogos.anotacoes = data.anotacoes;
  if (Array.isArray(data.itens) && tipo) catalogos[tipo] = data.itens;
}
async function persistCatalogItem(tipo, item) {
  const url = tipo === 'anotacoes'
    ? `/api/projetos/${cfg.slug}/recursos/catalogo/anotacoes`
    : `/api/projetos/${cfg.slug}/roteiros/${cfg.numero}/catalogo/${tipo}`;
  const resp = await fetch(url, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(item)
  });
  const data = await resp.json();
  if (!resp.ok || !data.ok) throw new Error(data.erro || i18n('js.save_item_error'));
  refreshCatalogosFromResponse(data, tipo);
  renderCatalogList();
}
/** Queuepersistcatalog. Usada pelo fluxo principal da aplicação. */
function queuePersistCatalog(tipo, nome, extra = {}) {
  const clean = formatCatalogName(nome).replace(/^[-–—]+|[-–—]+$/g, '').trim();
  if (!clean) return;
  const key = `${tipo}:${clean.toLowerCase()}`;
  clearTimeout(pendingPersistCatalog.get(key));
  const timer = setTimeout(async () => {
    pendingPersistCatalog.delete(key);
    try {
      await persistCatalogItem(tipo, { nome: clean, descricao: extra.descricao || '' });
    } catch (_) {}
  }, 220);
  pendingPersistCatalog.set(key, timer);
}
/** Ensurecatalogentry. Usada pelo fluxo principal da aplicação. */
function ensureCatalogEntry(tipo, nome, { persist = true } = {}) {
  const clean = formatCatalogName(nome).replace(/^[-–—]+|[-–—]+$/g, '').trim();
  if (!clean) return false;
  const normalized = clean.toLowerCase();
  const list = catalogos[tipo] || [];
  const existing = list.find(item => normalizeSpaces(item.nome).toLowerCase() === normalized);
  if (!existing) {
    list.push({ nome: clean, descricao: '' });
    catalogos[tipo] = list;
    renderCatalogList();
    if (persist) queuePersistCatalog(tipo, clean);
    return true;
  }
  return false;
}
/** Extractsceneheadingdata. Usada pelo fluxo principal da aplicação. */
function extractSceneHeadingData(text) {
  const upper = normalizeSpaces(stripSceneNumberPrefix(text)).toUpperCase();
  const match = upper.match(/^(INT\.\/EXT\.|INT\.|EXT\.|CAP\s+\d+)(?:\s+(.*))?$/u);
  if (!match) return null;
  const prefix = match[1];
  const remainder = match[2] || '';
  const dashIndex = remainder.indexOf(' - ');
  if (dashIndex >= 0) {
    return { prefix, local: normalizeSpaces(remainder.slice(0, dashIndex)), period: normalizeSpaces(remainder.slice(dashIndex + 3)) };
  }
  return { prefix, local: normalizeSpaces(remainder), period: '' };
}
/** Persistscenelocalifnew. Usada pelo fluxo principal da aplicação. */
function persistSceneLocalIfNew(text) {
  const data = extractSceneHeadingData(String(text || ''));
  if (!data?.local) return false;
  return ensureCatalogEntry('locais', data.local, { persist: true });
}
/** Getfilteredlocais. Usada pelo fluxo principal da aplicação. */
function getFilteredLocais(query = '') {
  const upperQuery = normalizeSpaces(query).toUpperCase();
  const locais = filterUnique(getNames('locais'));
  return locais.filter(item => !upperQuery || item.includes(upperQuery));
}
/** Getfilteredperiods. Usada pelo fluxo principal da aplicação. */
function getFilteredPeriods(query = '') {
  const upperQuery = normalizeSpaces(query).toUpperCase();
  return PERIODOS_CENA.filter(item => !upperQuery || item.includes(upperQuery));
}
/** Buildsceneheadingautocomplete. Usada pelo fluxo principal da aplicação. */
function buildSceneHeadingAutocomplete(rawText) {
  const text = String(rawText || '');
  const upper = normalizeSpaces(text).toUpperCase();
  const prefixes = getScenePrefixSuggestions();
  if (!upper) return { items: prefixes, mode: 'scene_prefix', context: {} };
  const parsed = extractSceneHeadingData(text);
  if (!parsed) return { items: prefixes.filter(item => item.startsWith(upper)), mode: 'scene_prefix', context: {} };

  const rawWithoutNumber = stripSceneNumberPrefix(text);
  const rest = normalizeSpaces(String(rawWithoutNumber).slice(parsed.prefix.length));
  const typedSpaceAtEnd = /\s$/.test(text);
  const hasDash = normalizeSpaces(text).includes(' - ');
  if (!rest) {
    if (typedSpaceAtEnd) return { items: getFilteredLocais(''), mode: 'scene_local', context: { prefix: parsed.prefix } };
    return { items: prefixes.filter(item => item.startsWith(parsed.prefix)), mode: 'scene_prefix', context: {} };
  }
  if (hasDash) {
    const periodMatches = getFilteredPeriods(parsed.period);
    if (!parsed.period) return { items: periodMatches, mode: 'scene_period', context: { prefix: parsed.prefix, local: parsed.local } };
    if (PERIODOS_CENA.includes(parsed.period)) return null;
    return { items: periodMatches, mode: 'scene_period', context: { prefix: parsed.prefix, local: parsed.local } };
  }
  if (typedSpaceAtEnd && parsed.local) {
    return { items: getFilteredPeriods(''), mode: 'scene_period', context: { prefix: parsed.prefix, local: parsed.local } };
  }
  return { items: getFilteredLocais(parsed.local), mode: 'scene_local', context: { prefix: parsed.prefix, local: parsed.local } };
}
function allScriptAnnotationItems() {
  return dedupeResourceAutocompleteItems((catalogos.anotacoes || []).map((item) => ({
    tipo: 'anotacoes',
    label: String(item?.nome || ''),
    descricao: String(item?.descricao || ''),
    id: String(item?.id || ''),
    origem: String(item?.origem || ''),
  })).filter((item) => item.label));
}
function buildAnnotationAutocomplete(block) {
  if (!block) return null;
  const type = block.dataset.blockType || '';
  if (['scene_heading', 'character', 'transition', 'shot'].includes(type)) return null;
  const offsets = getSelectionOffsetsWithin(block);
  if (!offsets?.collapsed) return null;
  const textBefore = blockPlainText(block).slice(0, offsets.end);
  const match = String(textBefore || '').match(/[\p{L}\p{N}_'’.-]{2,}$/u);
  if (!match) return null;
  const typed = match[0];
  const query = normalizeResourceSearch(typed);
  if (query.length < 2) return null;
  const items = allScriptAnnotationItems()
    .filter((item) => {
      const normalized = normalizeResourceSearch(item.label);
      return normalized.startsWith(query) && normalized !== query;
    })
    .slice(0, 8);
  if (!items.length) return null;
  return { items, mode: 'resource_note', context: { startOffset: Math.max(0, offsets.end - typed.length), endOffset: offsets.end, query } };
}
/** Maybeautocomplete. Usada pelo fluxo principal da aplicação. */
function maybeAutocomplete(block) {
  if (!block || !autocomplete) return hideAutocomplete();
  const type = block.dataset.blockType;
  const text = blockText(block);
  let result = null;

  if (type === 'scene_heading') {
    result = buildSceneHeadingAutocomplete(stripSceneNumberPrefix(block.innerText || text));
  } else if (type === 'character') {
    if (text) return hideAutocomplete();
    result = { items: filterUnique(getNames('personagens')), mode: 'character', context: {} };
  } else if (type === 'transition') {
    const query = text.toUpperCase();
    if (TRANSITIONS.includes(query)) result = null;
    else result = { items: TRANSITIONS.filter(item => !query || item.includes(query)), mode: 'transition', context: {} };
  }

  if (!result) result = buildAnnotationAutocomplete(block);
  const rawItems = result?.items || [];
  const items = result?.mode === 'resource_note' ? dedupeResourceAutocompleteItems(rawItems).slice(0, 8) : filterUnique(rawItems).slice(0, 8);
  if (!items.length) return hideAutocomplete();
  const previous = autocompleteState;
  const sameBlock = previous.block === block;
  const sameMode = previous.mode === (result.mode || '');
  const sameItems = previous.items.length === items.length && previous.items.every((item, idx) => autocompleteItemSignature(item) === autocompleteItemSignature(items[idx]));
  const nextActive = sameBlock && sameMode && sameItems
    ? Math.max(0, Math.min(previous.active, items.length - 1))
    : 0;
  autocompleteState = { items, active: nextActive, block, mode: result.mode || '', context: result.context || {} };
  renderAutocomplete();
}
/** Renderautocomplete. Usada pelo fluxo principal da aplicação. */
function renderAutocomplete() {
  if (!autocomplete || !autocompleteState.items.length || !autocompleteState.block) return hideAutocomplete();
  const rect = autocompleteState.block.getBoundingClientRect();
  const parentRect = autocomplete.parentElement.getBoundingClientRect();
  autocomplete.style.left = `${Math.max(0, rect.left - parentRect.left)}px`;
  autocomplete.style.top = `${rect.bottom - parentRect.top + 4}px`;
  const fragment = document.createDocumentFragment();
  autocompleteState.items.forEach((item, idx) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'autocomplete-item' + (idx === autocompleteState.active ? ' ativo' : '');
    btn.dataset.index = String(idx);
    btn.dataset.value = autocompleteItemLabel(item);
    if (typeof item === 'object' && item?.tipo) {
      const label = document.createElement('span');
      label.className = 'autocomplete-item-label';
      label.textContent = autocompleteItemLabel(item);
      const meta = document.createElement('small');
      meta.className = 'autocomplete-item-meta';
      meta.textContent = scriptResourceTypeLabel(item.tipo);
      btn.append(label, meta);
    } else {
      btn.textContent = autocompleteItemLabel(item);
    }
    fragment.appendChild(btn);
  });
  autocomplete.replaceChildren(fragment);
  autocomplete.classList.remove('oculto');
}
/** Chooseautocomplete. Usada pelo fluxo principal da aplicação. */
function chooseAutocomplete(value) {
  const item = typeof value === 'object' && value ? value : null;
  const valueText = autocompleteItemLabel(value);
  if (autocompleteState.mode === 'resource_note') {
    chooseScriptResourceAutocomplete(item || autocompleteState.items[autocompleteState.active]);
    return;
  }
  invalidateStructureCaches({ pages: false });
  const block = autocompleteState.block;
  if (!block) return;
  const mode = autocompleteState.mode;
  const ctx = autocompleteState.context || {};

  if (mode === 'scene_prefix') {
    block.textContent = `${getSceneNumberPrefix(Number(block.dataset.sceneNumber || cfg.numeracaoInicial || 1))}${valueText} `;
    markBlockDirty(block);
  } else if (mode === 'scene_local') {
    block.textContent = `${getSceneNumberPrefix(Number(block.dataset.sceneNumber || cfg.numeracaoInicial || 1))}${ctx.prefix || ''} ${valueText} `;
    markBlockDirty(block);
  } else if (mode === 'scene_period') {
    const prefix = normalizeSpaces(ctx.prefix || '');
    const local = normalizeSpaces(ctx.local || '');
    block.textContent = `${getSceneNumberPrefix(Number(block.dataset.sceneNumber || cfg.numeracaoInicial || 1))}${prefix}${local ? ` ${local}` : ''} - ${valueText}`.trim();
    markBlockDirty(block);
  } else {
    block.textContent = valueText;
    markBlockDirty(block);
  }

  hideAutocomplete();
  updateSceneSummary();
  updateCurrentTypeIndicator(block);
  placeCaretAtEnd(block);
  if (mode !== 'scene_period' && mode !== 'transition') maybeAutocomplete(block);
  scheduleAutosave();
}
function chooseScriptResourceAutocomplete(item) {
  if (!item || !autocompleteState.block) return false;
  const block = autocompleteState.block;
  const ctx = autocompleteState.context || {};
  const startOffset = Number(ctx.startOffset);
  const endOffset = Number(ctx.endOffset);
  const range = Number.isFinite(startOffset) && Number.isFinite(endOffset) ? createRangeFromOffsets(block, startOffset, endOffset) : null;
  if (!range) return false;
  const link = document.createElement('a');
  link.href = '#';
  link.className = 'editor-recurso-link';
  link.dataset.recursoTipo = 'anotacoes';
  link.dataset.recursoNome = autocompleteItemLabel(item);
  link.title = `${scriptResourceTypeLabel('anotacoes')}: ${autocompleteItemLabel(item)}`;
  link.textContent = autocompleteItemLabel(item);
  range.deleteContents();
  range.insertNode(link);
  const after = document.createRange();
  after.setStartAfter(link);
  after.collapse(true);
  const selection = window.getSelection();
  selection?.removeAllRanges();
  selection?.addRange(after);
  hideAutocomplete();
  markBlockDirty(block);
  saveSelection();
  updateCurrentTypeIndicator(block);
  scheduleSoftRepagination({ preserveSelection: true, delay: 120 });
  scheduleAutosave();
  return true;
}
/** Rendercataloglist. Usada pelo fluxo principal da aplicação. */
function renderCatalogList() {
  const tipo = catalogoTipo?.value;
  const items = catalogos[tipo] || [];
  if (!catalogoLista) return;
  catalogoLista.innerHTML = '';
  if (!items.length) {
    catalogoLista.innerHTML = `<div class="vazio"><p>${escapeHtml(i18n('script.no_registered_items'))}</p></div>`;
    return;
  }
  items.slice().sort((a, b) => String(a.nome || '').localeCompare(String(b.nome || ''))).forEach((item) => {
    const card = document.createElement('article');
    card.className = 'catalogo-item catalogo-item-simples catalogo-item-sem-thumb';
    card.innerHTML = `
      <div class="catalogo-conteudo"><h4 title="${escapeHtml(item.nome || i18n('script.no_name'))}">${escapeHtml(item.nome || i18n('script.no_name'))}</h4>${item.descricao ? `<p title="${escapeHtml(item.descricao)}">${escapeHtml(String(item.descricao).replace(/\s+/g, ' ').trim().slice(0, 180))}${String(item.descricao).replace(/\s+/g, ' ').trim().length > 180 ? '…' : ''}</p>` : ''}</div>
      <div class="catalogo-acoes horizontal">
        <button type="button" class="botao-secundario botao-apenas-icone" title="${i18n('js.edit_title')}">✎</button>
        <button type="button" class="botao-perigo botao-apenas-icone" title="${i18n('js.delete_title')}">✕</button>
      </div>`;
    const [btnEdit, btnDelete] = card.querySelectorAll('button');
    btnEdit?.addEventListener('click', () => openCatalogEditor(tipo, item));
    btnDelete?.addEventListener('click', () => deleteCatalogItem(tipo, item.nome, item.id || ''));
    catalogoLista.appendChild(card);
  });
}
async function deleteCatalogItem(tipo, nome, id = '') {
  if (!window.confirm(i18n('script.delete_item_confirm', { name: nome }))) return;
  const url = tipo === 'anotacoes'
    ? `/api/projetos/${cfg.slug}/recursos/catalogo/anotacoes/excluir`
    : `/api/projetos/${cfg.slug}/roteiros/${cfg.numero}/catalogo/${tipo}/excluir`;
  const resp = await fetch(url, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nome, id })
  });
  const data = await resp.json();
  if (!resp.ok || !data.ok) return;
  refreshCatalogosFromResponse(data, tipo);
  renderCatalogList();
}
/** Opencatalog. Usada pelo fluxo principal da aplicação. */
function openCatalog(tipo) {
  if (!catalogoTipo || !tituloModalCatalogo) return;
  catalogoTipo.value = tipo;
  tituloModalCatalogo.textContent = tipo === 'personagens' ? i18n('js.characters_label') : (tipo === 'anotacoes' ? textoTraduzido('resources.notes', 'Anotações') : i18n('js.locations_label'));
  renderCatalogList();
  closeModal(modalCatalogoEditor);
  openModal(modalCatalogo);
}
/** Opencatalogeditor. Usada pelo fluxo principal da aplicação. */
function openCatalogEditor(tipo, item = null, link = null) {
  if (!catalogoTipo) return;
  const safeTipo = tipo === 'anotacoes' ? 'anotacoes' : (tipo === 'locais' ? 'locais' : 'personagens');
  const isNote = safeTipo === 'anotacoes';
  catalogoTipo.value = safeTipo;
  catalogoLinkAtivo = link || null;
  catalogoItemAtivo = item || null;
  tituloModalCatalogoEditor.textContent = item ? i18n('common.edit_item') : i18n('common.new_item');
  const nomeLabel = catalogoNome?.closest('label');
  const descricaoLabel = catalogoDescricao?.closest('label');
  if (nomeLabel?.firstChild) nomeLabel.firstChild.textContent = scriptResourceFieldLabel(safeTipo, 'name');
  if (descricaoLabel?.firstChild) descricaoLabel.firstChild.textContent = scriptResourceFieldLabel(safeTipo, 'description');
  if (catalogoNome) {
    catalogoNome.dataset.uppercase = isNote ? 'false' : 'true';
    catalogoNome.placeholder = isNote ? textoTraduzido('resources.note_title_placeholder', 'Título da anotação') : '';
    catalogoNome.maxLength = isNote ? 80 : 60;
  }
  if (catalogoDescricao) catalogoDescricao.placeholder = isNote ? textoTraduzido('resources.note_placeholder', 'Escreva o texto da anotação...') : i18n('script.describe_item');
  catalogoNomeOriginal.value = item?.nome || '';
  catalogoNome.value = item?.nome || '';
  catalogoDescricao.value = item?.descricao || '';
  statusCatalogo.textContent = '';
  openModal(modalCatalogoEditor);
  applyUppercaseInputs(modalCatalogoEditor || document);
  setTimeout(() => catalogoNome?.focus(), 30);
}
/** Handleblockfocus. Usada pelo fluxo principal da aplicação. */
function handleBlockFocus(block) {
  highlightCurrentScene(block);
  updateCurrentTypeIndicator(block);
  maybeAutocomplete(block);
}

/** Formatdurationlabel. Usada pelo fluxo principal da aplicação. */
function formatDurationLabel(totalSeconds) {
  const raw = Math.max(0, Number(totalSeconds) || 0);
  const secs = Math.round(raw * 2) / 2;
  if (secs < 60) {
    const formatted = Number.isInteger(secs)
      ? String(secs)
      : new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(secs);
    return `${formatted} ${secs === 1 ? i18n('script.seconds_singular') : i18n('script.seconds_plural')}`;
  }
  const hours = Math.floor(secs / 3600);
  const minutes = Math.floor((secs % 3600) / 60);
  const seconds = secs % 60;
  if (hours > 0) {
    if (minutes > 0) return `${hours} ${hours === 1 ? i18n('script.hour_singular') : i18n('script.hour_plural')} ${i18n('script.and')} ${minutes} ${minutes === 1 ? i18n('script.minute_singular') : i18n('script.minute_plural')}`;
    return `${hours} ${hours === 1 ? i18n('script.hour_singular') : i18n('script.hour_plural')}`;
  }
  if (minutes > 0 && seconds > 0 && minutes <= 2) return `${minutes} ${minutes === 1 ? i18n('script.minute_singular') : i18n('script.minute_plural')} ${i18n('script.and')} ${seconds} ${seconds === 1 ? i18n('script.seconds_singular') : i18n('script.seconds_plural')}`;
  return `${minutes} ${minutes === 1 ? i18n('script.minute_singular') : i18n('script.minute_plural')}`;
}
/** Pluralize. Usada pelo fluxo principal da aplicação. */
function pluralize(count, singular, plural = null) {
  const n = Number(count) || 0;
  return `${n} ${n === 1 ? singular : (plural || `${singular}s`)}`;
}
/** Getcharacternamefordialogue. Usada pelo fluxo principal da aplicação. */
function getCharacterNameForDialogue(blocks, index) {
  for (let i = index - 1; i >= 0; i -= 1) {
    const current = blocks[i];
    const type = current?.dataset?.blockType;
    if (type === 'character') return normalizeSpaces((getBlockRawText(current) || '').replace(/[()]/g, '')).toUpperCase();
    if (type === 'dialogue' || type === 'action' || type === 'scene_heading' || type === 'transition' || type === 'shot') break;
  }
  return i18n('script.not_identified');
}
/** Buildscriptstatistics. Usada pelo fluxo principal da aplicação. */
function buildScriptStatistics() {
  normalizeEditor();
  const blocks = [...editor.querySelectorAll('.roteiro-bloco')];
  const scenes = getSceneBlocks();
  const sceneMap = new Map();
  const firstScene = scenes[0] || null;
  scenes.forEach((scene, idx) => sceneMap.set(scene, { block: scene, index: idx, label: getSceneHeadingContent(scene) || i18n('script.scene_label', { number: idx + 1 }) }));
  const stats = {
    totalDialogueSeconds: 0,
    dialogueLines: [],
    characterTimes: new Map(),
    characterLineCounts: new Map(),
    actionBlocks: 0,
    actionWords: 0,
    dialogueBlocks: 0,
    dialogueWords: 0,
    totalWords: 0,
    totalCharacters: 0,
    totalCharactersNoSpaces: 0,
    locationCounts: new Map(),
    characterAppearances: new Map(),
    narrativeParts: [
      { key: 'inicio', label: i18n('script.narrative_beginning'), scenes: 0, dialogueSeconds: 0, actionWords: 0, dialogueWords: 0, blocks: 0 },
      { key: 'meio', label: i18n('script.middle'), scenes: 0, dialogueSeconds: 0, actionWords: 0, dialogueWords: 0, blocks: 0 },
      { key: 'fim', label: i18n('script.end'), scenes: 0, dialogueSeconds: 0, actionWords: 0, dialogueWords: 0, blocks: 0 },
    ],
    sceneTotals: [],
  };
  const totalScenes = Math.max(1, scenes.length);
  const narrativeBound1 = Math.ceil(totalScenes / 3);
  const narrativeBound2 = Math.ceil((totalScenes * 2) / 3);

  /** Getnarrativepart. Usada pelo fluxo principal da aplicação. */
  function getNarrativePart(sceneIndex) {
    if (sceneIndex < narrativeBound1) return stats.narrativeParts[0];
    if (sceneIndex < narrativeBound2) return stats.narrativeParts[1];
    return stats.narrativeParts[2];
  }

  if (scenes.length) {
    scenes.forEach((scene, idx) => {
      const label = getSceneHeadingContent(scene) || i18n('script.scene_label', { number: idx + 1 });
      const local = extractSceneHeadingData(getBlockRawText(scene))?.local || label;
      stats.sceneTotals.push({
        label,
        local,
        dialogueSeconds: 0,
        actionWords: 0,
        dialogueWords: 0,
        totalWords: 0,
        totalCharacters: 0,
        totalCharactersNoSpaces: 0,
        blocks: 0,
      });
      stats.locationCounts.set(local, (stats.locationCounts.get(local) || 0) + 1);
      getNarrativePart(idx).scenes += 1;
    });
  }

  blocks.forEach((block, index) => {
    const type = block.dataset.blockType || 'action';
    const text = normalizeSpaces(getBlockRawText(block));
    if (!text) return;

    const includeInTextMetrics = type !== 'comment';
    const words = includeInTextMetrics ? text.split(/\s+/).filter(Boolean).length : 0;
    const chars = includeInTextMetrics ? text.length : 0;
    const charsNoSpaces = includeInTextMetrics ? text.replace(/\s/g, '').length : 0;

    if (includeInTextMetrics) {
      stats.totalWords += words;
      stats.totalCharacters += chars;
      stats.totalCharactersNoSpaces += charsNoSpaces;
    }

    const scene = findSceneForBlock(block) || firstScene;
    const sceneMeta = scene ? sceneMap.get(scene) : null;
    const sceneIndex = sceneMeta?.index ?? 0;
    const narrativePart = getNarrativePart(sceneIndex);
    const sceneStats = stats.sceneTotals[sceneIndex] || null;
    narrativePart.blocks += 1;
    if (sceneStats) {
      sceneStats.blocks += 1;
      if (includeInTextMetrics) {
        sceneStats.totalWords += words;
        sceneStats.totalCharacters += chars;
        sceneStats.totalCharactersNoSpaces += charsNoSpaces;
      }
    }

    if (type === 'action') {
      stats.actionBlocks += 1;
      stats.actionWords += words;
      narrativePart.actionWords += words;
      if (sceneStats) sceneStats.actionWords += words;
    }

    if (type === 'character') {
      const nome = text.replace(/[()]/g, '').trim().toUpperCase();
      if (nome) stats.characterAppearances.set(nome, (stats.characterAppearances.get(nome) || 0) + 1);
    }

    if (type === 'dialogue') {
      const seconds = estimateDialogueSeconds(text);
      const character = getCharacterNameForDialogue(blocks, index);
      stats.totalDialogueSeconds += seconds;
      stats.dialogueBlocks += 1;
      stats.dialogueWords += words;
      narrativePart.dialogueSeconds += seconds;
      narrativePart.dialogueWords += words;
      if (sceneStats) {
        sceneStats.dialogueSeconds += seconds;
        sceneStats.dialogueWords += words;
      }
      stats.dialogueLines.push({
        index: stats.dialogueLines.length + 1,
        personagem: character,
        texto: text,
        segundos: seconds,
        cena: sceneMeta?.label || i18n('script.no_scene'),
      });
      stats.characterTimes.set(character, (stats.characterTimes.get(character) || 0) + seconds);
      stats.characterLineCounts.set(character, (stats.characterLineCounts.get(character) || 0) + 1);
      stats.characterAppearances.set(character, (stats.characterAppearances.get(character) || 0) + 1);
    }
  });

  stats.uniqueCharacters = stats.characterAppearances.size;
  stats.uniqueLocations = stats.locationCounts.size;
  stats.averageWordsPerScene = stats.sceneTotals.length ? (stats.totalWords / stats.sceneTotals.length) : 0;
  stats.averageDialogueWordsPerLine = stats.dialogueBlocks ? (stats.dialogueWords / stats.dialogueBlocks) : 0;
  stats.averageDialogueSecondsPerLine = stats.dialogueBlocks ? (stats.totalDialogueSeconds / stats.dialogueBlocks) : 0;
  stats.dominantCharacter = [...stats.characterTimes.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || '';
  return stats;
}
/** Maptosortedarray. Usada pelo fluxo principal da aplicação. */
function mapToSortedArray(map, extra = null) {
  return [...map.entries()]
    .map(([nome, valor]) => ({ nome, valor, ...(extra ? extra(nome, valor) : {}) }))
    .sort((a, b) => {
      if (b.valor !== a.valor) return b.valor - a.valor;
      return String(a.nome).localeCompare(String(b.nome), 'pt-BR');
    });
}
/** Buildrhythmsummary. Usada pelo fluxo principal da aplicação. */
function buildRhythmSummary(stats) {
  const sceneDurations = stats.sceneTotals.map((scene) => scene.dialogueSeconds + Math.max(0, Math.round(scene.actionWords / 3)));
  if (!sceneDurations.length) {
    return {
      average: i18n('script.not_enough_scenes_for_rhythm'),
      distribution: [],
      highlight: i18n('script.stats_create_scenes_hint'),
    };
  }
  const averageSeconds = sceneDurations.reduce((acc, value) => acc + value, 0) / sceneDurations.length;
  const distribution = [
    { label: i18n('script.short_scenes'), count: sceneDurations.filter((value) => value < 45).length },
    { label: i18n('script.average_scenes'), count: sceneDurations.filter((value) => value >= 45 && value < 90).length },
    { label: i18n('script.long_scenes'), count: sceneDurations.filter((value) => value >= 90).length },
  ];
  const maxIdx = sceneDurations.indexOf(Math.max(...sceneDurations));
  const minIdx = sceneDurations.indexOf(Math.min(...sceneDurations));
  return {
    average: i18n('script.average_per_scene_approx', { value: formatDurationLabel(averageSeconds) }),
    distribution,
    highlight: i18n('script.rhythm_highlight', { densest: stats.sceneTotals[maxIdx]?.label || '—', densestDuration: formatDurationLabel(sceneDurations[maxIdx] || 0), fastest: stats.sceneTotals[minIdx]?.label || '—', fastestDuration: formatDurationLabel(sceneDurations[minIdx] || 0) }),
  };
}
/** Renderminibar. Usada pelo fluxo principal da aplicação. */
function renderMiniBar(value, total, formatter = null) {
  const safeTotal = Math.max(1, Number(total) || 0);
  const safeValue = Math.max(0, Number(value) || 0);
  const pct = Math.max(0, Math.min(100, (safeValue / safeTotal) * 100));
  const label = formatter ? formatter(safeValue, pct) : `${Math.round(pct)}%`;
  return `<div class="mini-bar"><div class="mini-bar-fill" style="width:${pct.toFixed(2)}%"></div></div><span>${label}</span>`;
}
/** Formatstatnumber. Usada pelo fluxo principal da aplicação. */
function formatStatNumber(value) {
  return new Intl.NumberFormat('pt-BR').format(Math.round(Number(value) || 0));
}
/** Formatstatdecimal. Usada pelo fluxo principal da aplicação. */
function formatStatDecimal(value, maxFraction = 1) {
  return new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: maxFraction }).format(Number(value) || 0);
}
/** Renderstatkpi. Usada pelo fluxo principal da aplicação. */
function renderStatKpi(label, value, sublabel = '') {
  return `<div class="estat-kpi"><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value || '0'))}</strong>${sublabel ? `<small>${escapeHtml(sublabel)}</small>` : ''}</div>`;
}
/** Renderstatisticsmodal. Usada pelo fluxo principal da aplicação. */
function renderStatisticsModal() {
  if (!estatisticasRoteiroConteudo) return;
  const stats = buildScriptStatistics();
  const tempoPorPersonagem = mapToSortedArray(stats.characterTimes, (nome) => ({ falas: stats.characterLineCounts.get(nome) || 0 }));
  const personagens = mapToSortedArray(stats.characterAppearances);
  const locais = mapToSortedArray(stats.locationCounts);
  const totalNarrativoTempo = Math.max(1, stats.narrativeParts.reduce((acc, item) => acc + item.dialogueSeconds + Math.round(item.actionWords / 3), 0));
  const ritmo = buildRhythmSummary(stats);
  const dialogueVsActionTotal = Math.max(1, stats.totalDialogueSeconds + Math.round(stats.actionWords / 3));
  const topFalas = stats.dialogueLines.slice().sort((a, b) => b.segundos - a.segundos).slice(0, 12);
  const topScene = stats.sceneTotals.slice().sort((a, b) => b.totalWords - a.totalWords)[0] || null;
  const dominantCharacterTime = stats.dominantCharacter ? (stats.characterTimes.get(stats.dominantCharacter) || 0) : 0;

  estatisticasRoteiroConteudo.innerHTML = `
    <section class="estat-card destaque destaque-dashboard">
      <div class="estat-hero-texto">
        <span class="estat-label">${i18n('script.stats_dashboard')}</span>
		<h3>${i18n('script.total_time')}</h3>
        <strong class="estat-valor">${formatDurationLabel(stats.totalDialogueSeconds)}</strong>
        <p class="estat-ajuda">${i18n('script.dialogue_time_sum')}</p>
      </div>
      <div class="estat-kpi-grid">
        ${renderStatKpi(i18n('script.words'), formatStatNumber(stats.totalWords), `${pluralize(stats.sceneTotals.length, i18n('script.scene_singular'), i18n('script.scene_plural'))}`)}
        ${renderStatKpi(i18n('script.characters'), formatStatNumber(stats.totalCharacters), i18n('script.with_spaces'))}
        ${renderStatKpi(i18n('script.without_space'), formatStatNumber(stats.totalCharactersNoSpaces), i18n('script.useful_characters'))}
        ${renderStatKpi(i18n('common.characters'), formatStatNumber(stats.uniqueCharacters), `${pluralize(stats.dialogueBlocks, i18n('script.line_singular'), i18n('script.line_plural'))}`)}
      </div>
    </section>

    <section class="estat-grid estat-grid-topo">
      <article class="estat-card">
        <h3>${i18n('script.text_metrics')}</h3>
        <div class="estat-resumo-bloco">
          <div class="estat-kpi-grid compacto">
            ${renderStatKpi(i18n('script.total_words'), formatStatNumber(stats.totalWords), `${formatStatDecimal(stats.averageWordsPerScene)} ${i18n('script.per_scene')}`)}
            ${renderStatKpi(i18n('script.characters'), formatStatNumber(stats.totalCharacters), i18n('script.with_spaces'))}
            ${renderStatKpi(i18n('script.without_spaces'), formatStatNumber(stats.totalCharactersNoSpaces), i18n('script.plain_text'))}
            ${renderStatKpi(i18n('script.average_per_line'), formatStatDecimal(stats.averageDialogueWordsPerLine), i18n('script.seconds_per_line', { value: formatStatDecimal(stats.averageDialogueSecondsPerLine) }))}
          </div>
          <p>${i18n('script.metrics_help_text')}</p>
        </div>
      </article>

      <article class="estat-card">
        <h3>${i18n('script.summary')}</h3>
        <div class="lista-metrica compacta sem-scroll">
          <div class="linha-metrica"><strong>${i18n('script.total_scenes')}</strong><span>${formatStatNumber(stats.sceneTotals.length)}</span></div>
          <div class="linha-metrica"><strong>${escapeHtml(i18n('script.unique_locations'))}</strong><span>${formatStatNumber(stats.uniqueLocations)}</span></div>
          <div class="linha-metrica"><strong>${i18n('script.dominant_character')}</strong><span>${escapeHtml(stats.dominantCharacter || '—')}</span></div>
          <div class="linha-metrica"><strong>${i18n('script.dominant_time')}</strong><span>${formatDurationLabel(dominantCharacterTime)}</span></div>
          <div class="linha-metrica"><strong>${i18n('script.longest_scene')}</strong><span>${topScene ? i18n('script.words_count', { count: formatStatNumber(topScene.totalWords) }) : '—'}</span></div>
        </div>
      </article>
    </section>

    <section class="estat-grid">
      <article class="estat-card estat-card-largo">
        <h3>${i18n('script.scene_metrics')}</h3>
        <div class="lista-metrica lista-cenas">
          ${stats.sceneTotals.length ? stats.sceneTotals.map((scene, idx) => `
            <div class="linha-metrica linha-metrica-cena">
              <div>
                <strong>${String(idx + 1).padStart(3, '0')}. ${escapeHtml(scene.label)}</strong>
                <p>${escapeHtml(scene.local)} • ${i18n('script.words_count', { count: formatStatNumber(scene.totalWords) })} • ${formatStatNumber(scene.totalCharacters)} ${i18n('script.characters_count').toLowerCase()}</p>
              </div>
              <span>${formatDurationLabel(scene.dialogueSeconds)}</span>
            </div>`).join('') : `<p class="texto-vazio">${escapeHtml(i18n('script.no_scene_found'))}</p>`}
        </div>
      </article>

      <article class="estat-card">
        <h3>${i18n('script.time_per_line')}</h3>
        <div class="lista-metrica compacta">
          ${topFalas.length ? topFalas.map(item => `
            <div class="linha-metrica">
              <div>
                <strong>${escapeHtml(item.personagem)}</strong>
                <p title="${escapeHtml(item.texto)}">${escapeHtml(item.texto.slice(0, 90))}${item.texto.length > 90 ? '…' : ''}</p>
              </div>
              <span>${formatDurationLabel(item.segundos)}</span>
            </div>`).join('') : `<p class="texto-vazio">${escapeHtml(i18n('script.no_lines_found'))}</p>`}
        </div>
      </article>

      <article class="estat-card">
        <h3>${escapeHtml(i18n('js.characters_label'))}</h3>
        <div class="estat-resumo-bloco">
          <div class="estat-kpi-grid compacto">
            ${renderStatKpi(i18n('script.total'), formatStatNumber(stats.uniqueCharacters), i18n('script.total_distinct'))}
            ${renderStatKpi(i18n('script.lines'), formatStatNumber(stats.dialogueBlocks), i18n('script.dialogue_blocks'))}
          </div>
          <div class="lista-metrica">
            ${tempoPorPersonagem.length ? tempoPorPersonagem.map(item => `
              <div class="linha-metrica">
                <div><strong>${escapeHtml(item.nome)}</strong><p>${pluralize(item.falas, i18n('script.line_singular'), i18n('script.line_plural'))}</p></div>
                <span>${formatDurationLabel(item.valor)}</span>
              </div>`).join('') : `<p class="texto-vazio">${escapeHtml(i18n('js.no_character_lines_yet'))}</p>`}
          </div>
        </div>
      </article>

      <article class="estat-card">
        <h3>${i18n('script.character_entries')}</h3>
        <div class="lista-metrica">
          ${personagens.length ? personagens.map(item => `
            <div class="linha-metrica">
              <strong>${escapeHtml(item.nome)}</strong>
              <span>${pluralize(item.valor, i18n('script.entry_singular'), i18n('script.entry_plural'))}</span>
            </div>`).join('') : `<p class="texto-vazio">${escapeHtml(i18n('js.no_character_identified'))}</p>`}
        </div>
      </article>

      <article class="estat-card">
        <h3>${escapeHtml(i18n('js.locations_label'))}</h3>
        <div class="estat-resumo-bloco">
          <div class="estat-kpi-grid compacto">
            ${renderStatKpi(i18n('script.total'), formatStatNumber(stats.uniqueLocations), i18n('script.unique_locations'))}
            ${renderStatKpi(i18n('script.total_usage'), formatStatNumber(stats.sceneTotals.length), i18n('script.mapped_scenes'))}
          </div>
          <div class="lista-metrica">
            ${locais.length ? locais.map(item => `
              <div class="linha-metrica">
                <strong>${escapeHtml(item.nome)}</strong>
                <span>${pluralize(item.valor, i18n('script.use_scenes'), i18n('script.use_scenes_plural'))}</span>
              </div>`).join('') : `<p class="texto-vazio">${escapeHtml(i18n('js.no_location_identified'))}</p>`}
          </div>
        </div>
      </article>

      <article class="estat-card">
        <h3>${i18n('script.dialogue_vs_action')}</h3>
        <div class="estat-comparativo">
          <div class="comparativo-item">
            <strong>${i18n('script.editor_block_dialogue')}</strong>
            ${renderMiniBar(stats.totalDialogueSeconds, dialogueVsActionTotal, (value, pct) => `${formatDurationLabel(value)} • ${Math.round(pct)}%`)}
          </div>
          <div class="comparativo-item">
            <strong>${i18n('script.editor_block_action')}</strong>
            ${renderMiniBar(Math.round(stats.actionWords / 3), dialogueVsActionTotal, (value, pct) => `${formatDurationLabel(value)} • ${Math.round(pct)}%`)}
          </div>
          <p class="estat-ajuda">${i18n('script.action_balance_help')}</p>
        </div>
      </article>

      <article class="estat-card">
        <h3>${i18n('script.rhythm')}</h3>
        <div class="estat-resumo-bloco">
          <p>${escapeHtml(ritmo.average)}</p>
          <p>${escapeHtml(ritmo.highlight)}</p>
          <div class="lista-metrica compacta sem-scroll">
            ${ritmo.distribution.map(item => `<div class="linha-metrica"><strong>${escapeHtml(item.label)}</strong><span>${pluralize(item.count, i18n('script.use_scenes'), i18n('script.use_scenes_plural'))}</span></div>`).join('')}
          </div>
        </div>
      </article>

      <article class="estat-card estat-card-largo">
        <h3>${i18n('script.narrative_distribution')}</h3>
        <div class="lista-metrica sem-scroll">
          ${stats.narrativeParts.map(part => `
            <div class="bloco-distribuicao">
              <div class="linha-metrica"><strong>${escapeHtml(part.label)}</strong><span>${pluralize(part.scenes, i18n('script.use_scenes'), i18n('script.use_scenes_plural'))}</span></div>
              <div class="comparativo-item">
                <strong>${i18n('script.narrative_presence')}</strong>
                ${renderMiniBar(part.dialogueSeconds + Math.round(part.actionWords / 3), totalNarrativoTempo, (value, pct) => `${formatDurationLabel(value)} • ${Math.round(pct)}%`)}
              </div>
              <p>${i18n('script.tracked_words', { duration: formatDurationLabel(part.dialogueSeconds), blocks: pluralize(part.blocks, i18n('script.block_singular'), i18n('script.block_plural')), words: formatStatNumber(part.dialogueWords + part.actionWords) })}</p>
            </div>`).join('')}
        </div>
      </article>
    </section>`;
}

document.querySelectorAll('[data-fechar-modal="true"]').forEach(el => el.addEventListener('click', (ev) => {
  ev.preventDefault();
  closeModal(el.closest('.modal'));
}));
document.querySelectorAll('[data-modal-card="true"]').forEach(el => el.addEventListener('click', (ev) => ev.stopPropagation()));
document.querySelectorAll('.btn-tipo-bloco').forEach((btn) => { btn.addEventListener('mousedown', (ev) => { ev.preventDefault(); restoreSelection(); }); btn.addEventListener('click', () => applyBlockType(btn.dataset.blockType)); });
document.getElementById('btnUndo')?.addEventListener('click', performNativeUndo);
document.getElementById('btnRedo')?.addEventListener('click', performNativeRedo);
document.getElementById('btnCatalogoPersonagens')?.addEventListener('click', () => openCatalog('personagens'));
document.getElementById('btnCatalogoLocais')?.addEventListener('click', () => openCatalog('locais'));
document.getElementById('btnEstatisticasRoteiro')?.addEventListener('click', () => { renderStatisticsModal(); openModal(modalEstatisticasRoteiro); });
btnToggleVisualizacao?.addEventListener('click', toggleOnlyScriptMode);
toggleVisualizacao?.addEventListener('change', applyVisualization);

/** Applyvisualization. Usada pelo fluxo principal da aplicação. */
function applyVisualization() {
  const onlyScript = !!toggleVisualizacao?.checked;
  if (visualizationStateCache !== onlyScript) {
    editor?.classList.toggle('apenas-roteiro', onlyScript);
    getAllBlocks().filter((block) => block?.dataset?.blockType === 'comment').forEach((block) => {
      block.classList.toggle('oculto-visualizacao', onlyScript);
    });
    visualizationStateCache = onlyScript;
  }
  if (btnToggleVisualizacao) {
    btnToggleVisualizacao.classList.toggle('ativo', onlyScript);
    btnToggleVisualizacao.title = onlyScript ? i18n('common.show_comments') : i18n('common.hide_comments');
  }
  if (iconeToggleVisualizacao) {
    iconeToggleVisualizacao.src = onlyScript ? '/static/img/ocultar.png' : '/static/img/mostrar.png';
    iconeToggleVisualizacao.alt = onlyScript ? i18n('common.show_comments') : i18n('common.hide_comments');
  }
}

selectTemaRoteiro?.addEventListener('change', () => applyScriptTheme(selectTemaRoteiro.value));
campoTituloCapitulo?.addEventListener('input', () => { upperInputValue(campoTituloCapitulo); scheduleAutosave(); });
editor?.addEventListener('compositionstart', () => { isEditorComposing = true; });
editor?.addEventListener('compositionend', () => {
  isEditorComposing = false;
  const block = getCurrentBlock();
  if (block) {
    limparMarcaDeRevisaoIA(block);
    markBlockDirty(block);
    normalizeUppercaseBlock(block);
    updateNeutralState(block);
    if (block.dataset.blockType === 'dialogue') updateDialogueTime(block);
    handleBlockFocus(block);
  }
  scheduleSoftRepagination({
    preserveSelection: true,
    after: () => ensureCaretFlowsAcrossPages(block, block ? caretOffsetWithin(block) : null),
    delay: 260,
  });
  if (block?.dataset?.blockType === 'scene_heading') scheduleDeferredUiRefresh({ sceneSummary: true });
  scheduleAutosave();
});
editor?.addEventListener('input', () => {
  if (isEditorComposing) return;
  invalidateStructureCaches({ pages: false });
  const block = getCurrentBlock();
  if (block) {
    limparMarcaDeRevisaoIA(block);
    markBlockDirty(block);
  }
  const caretOffset = block ? caretOffsetWithin(block) : null;
  capitalizeFirstWordOnLeadingSpace(block);
  normalizeUppercaseBlock(block);
  updateNeutralState(block);
  if (block?.dataset?.blockType === 'dialogue') updateDialogueTime(block);

  const pageContent = block?.closest('.roteiro-page-content') || null;
  const needsImmediateRepagination = !!(pageContent && pageIsOverflowing(pageContent));
  const repaginationOptions = {
    preserveSelection: true,
    after: () => ensureCaretFlowsAcrossPages(block, caretOffset),
  };
  if (needsImmediateRepagination) scheduleRepagination(repaginationOptions);
  else scheduleSoftRepagination(repaginationOptions);

  handleBlockFocus(block);
  if (block?.dataset?.blockType === 'scene_heading') scheduleDeferredUiRefresh({ sceneSummary: true });
  scheduleAutosave();
});
editor?.addEventListener('click', (event) => {
  saveSelection();
  const block = getCurrentBlock();
  handleBlockFocus(block);
  const clickedLink = event.target instanceof Element ? event.target.closest('.editor-recurso-link') : null;
  if (clickedLink && editor?.contains(clickedLink)) {
    event.preventDefault();
    event.stopPropagation();
    if (!event.altKey) return;
    const linkInfo = getCatalogContextForResourceLink(clickedLink);
    if (linkInfo) openCatalogEditor(linkInfo.catalogoTipo, linkInfo.item || { nome: linkInfo.nome, descricao: '' }, clickedLink);
    return;
  }
  if (!event.altKey) return;
  const clickedBlock = event.target instanceof Element ? event.target.closest('.roteiro-bloco') : null;
  if (!clickedBlock || !editor?.contains(clickedBlock)) return;
  const selection = window.getSelection();
  if (selection && !selection.isCollapsed) return;
  const info = getCatalogContextForBlock(clickedBlock);
  if (!info) return;
  event.preventDefault();
  event.stopPropagation();
  openCatalogEditor(info.catalogoTipo, info.item || { nome: info.nome, descricao: '' });
});
editor?.addEventListener('keyup', (ev) => {
  if (['ArrowUp', 'ArrowDown', 'Enter', 'Escape'].includes(ev.key)) return;
  saveSelection();
  handleBlockFocus(getCurrentBlock());
});
editor?.addEventListener('focusin', () => { saveSelection(); handleBlockFocus(getCurrentBlock()); });

editor?.addEventListener('mousemove', handleEditorHover);
editor?.addEventListener('mouseleave', hideInfoHoverTooltip);
editor?.addEventListener('scroll', hideInfoHoverTooltip);
window.addEventListener('scroll', hideInfoHoverTooltip, { passive: true });
window.addEventListener('resize', () => { hideInfoHoverTooltip(); updateSidebarStickyOffset(); scheduleRepagination({ preserveSelection: true }); });
document.addEventListener('selectionchange', () => {
  if (selectionChangeFrame) return;
  selectionChangeFrame = requestAnimationFrame(() => {
    selectionChangeFrame = 0;
    const block = getCurrentBlock();
    if (block && editor?.contains(block)) {
      saveSelection();
      highlightCurrentScene(block);
      updateCurrentTypeIndicator(block);
      scheduleEnsureScriptCaretVisible();
    }
  });
});
editor?.addEventListener('keydown', (ev) => {
  const block = getCurrentBlock();
  if (!block) return;

  if ((ev.key === 'Backspace' || ev.key === 'Delete') && !ev.ctrlKey && !ev.altKey && !ev.metaKey) {
    const offsets = getSelectionOffsetsWithin(block);
    const keyDirection = ev.key === 'Backspace' ? 'backward' : 'forward';
    const scenePrefixLength = getSceneNumberPrefixLength(block);
    const onlySceneNumber = block?.dataset?.blockType === 'scene_heading' && !normalizeSpaces(stripSceneNumberPrefix(getBlockRawText(block)));
    const deletingAutoSceneNumber = offsets?.collapsed && ev.key === 'Backspace' && onlySceneNumber && (offsets.start <= scenePrefixLength);
    if (deletingAutoSceneNumber) {
      ev.preventDefault();
      block.dataset.blockType = 'neutral';
      block.dataset.placeholder = BLOCK_PLACEHOLDERS.neutral || '';
      block.replaceChildren(document.createElement('br'));
      markBlockDirty(block);
      updateNeutralState(block);
      repaginateEditor({ preserveSelection: false });
      setCaretOffsetWithin(block, 0);
      handleBlockFocus(block);
      saveSelection();
      updateSceneSummary();
      scheduleAutosave();
      hideAutocomplete();
      scheduleEnsureScriptCaretVisible(true);
      return;
    }
    if (offsets?.collapsed && isBlockVisuallyEmpty(block)) {
      ev.preventDefault();
      if (collapseExtraEmptyPageFromBlock(block, keyDirection)) return;
      const fallback = keyDirection === 'backward' ? getPreviousBlock(block) : getNextBlock(block);
      if (fallback) {
        block.remove();
        repaginateEditor({ preserveSelection: false });
        if (keyDirection === 'backward') placeCaretAtEnd(fallback);
        else setCaretOffsetWithin(fallback, 0);
        handleBlockFocus(fallback);
        saveSelection();
        updateSceneSummary();
        scheduleAutosave();
        return;
      }
      block.replaceChildren(document.createElement('br'));
      markBlockDirty(block);
      saveSelection();
      return;
    }

    if (offsets?.collapsed) {
      const atStart = offsets.start === 0;
      const atEnd = offsets.end === blockPlainText(block).length;
      if ((ev.key === 'Backspace' && atStart) || (ev.key === 'Delete' && atEnd)) {
        scheduleRepaginationAfterNativeEdit();
      }
    } else {
      scheduleRepaginationAfterNativeEdit();
    }
  }

  if (autocompleteState.items.length) {
    if (ev.key === 'ArrowDown') {
      ev.preventDefault();
      autocompleteState.active = Math.min(autocompleteState.active + 1, autocompleteState.items.length - 1);
      renderAutocomplete();
      return;
    }
    if (ev.key === 'ArrowUp') {
      ev.preventDefault();
      autocompleteState.active = Math.max(autocompleteState.active - 1, 0);
      renderAutocomplete();
      return;
    }
    if ((ev.key === 'Enter' || ev.key === 'Tab') && autocompleteState.active >= 0) {
      ev.preventDefault();
      chooseAutocomplete(autocompleteState.items[autocompleteState.active]);
      return;
    }
    if (ev.key === 'Escape') {
      hideAutocomplete();
      return;
    }
  }

  if (ev.key === 'Enter' && !ev.shiftKey) {
    ev.preventDefault();
    garantirPontoFinalNoBloco(block);
    if (block.dataset.blockType === 'scene_heading') {
      persistSceneLocalIfNew(getBlockRawText(block));
      applySceneNumbers();
    }
    if (block.dataset.blockType === 'dialogue') updateDialogueTime(block);
    if (block.dataset.blockType === 'character') {
      const nomePersonagem = blockText(block).replace(/[()]/g, '').trim();
      if (nomePersonagem) ensureCatalogEntry('personagens', nomePersonagem, { persist: true });
    }
    const nextType = NEXT_BLOCK[block.dataset.blockType] || (block.dataset.blockType === 'neutral' ? 'action' : block.dataset.blockType) || 'action';
    const next = createBlock(nextType);
    block.after(next);
    repaginateEditor({ preserveSelection: false });
    const flowedToNextPage = ensureCaretFlowsAcrossPages(next, 0);
    updateSceneSummary();
    if (!flowedToNextPage) placeCaretAtEnd(next);
    handleBlockFocus(getCurrentBlock() || next);
    scheduleAutosave();
    hideAutocomplete();
    scheduleEnsureScriptCaretVisible(true);
  }
});
document.addEventListener('keydown', (ev) => {
  if (ev.key === 'Alt') syncAltLinkModeState(true);
  const key = (ev.key || '').toLowerCase();
  const target = ev.target;
  const editingText = isEditingTextTarget(target);

  if (ev.ctrlKey && !ev.shiftKey && key === 'z') { ev.preventDefault(); performNativeUndo(); return; }
  if (ev.ctrlKey && ev.shiftKey && key === 'z') { ev.preventDefault(); performNativeRedo(); return; }
  if (ev.ctrlKey && !ev.altKey && !ev.shiftKey && key === 'a' && editor?.contains(target)) {
    ev.preventDefault();
    selectAllScriptBlocks();
    return;
  }

  if (ev.ctrlKey && ev.altKey && !ev.shiftKey) {
    if (key === 'p') { ev.preventDefault(); document.getElementById('btnCatalogoPersonagens')?.click(); return; }
    if (key === 'l') { ev.preventDefault(); document.getElementById('btnCatalogoLocais')?.click(); return; }
    if (key === 'i') { ev.preventDefault(); document.getElementById('btnEstatisticasRoteiro')?.click(); return; }
    if (key === 'r') { ev.preventDefault(); iniciarRevisaoOrtografica(); return; }
  }

  if (ev.ctrlKey && !ev.altKey && !ev.shiftKey && editingText) {
    if (ev.key === 'ArrowUp') { ev.preventDefault(); focusAdjacentScene(-1); return; }
    if (ev.key === 'ArrowDown') { ev.preventDefault(); focusAdjacentScene(1); return; }
  }

  if (ev.key === 'Escape' && !ev.ctrlKey && !ev.altKey && !ev.metaKey && !ev.shiftKey) {
    const modalAberto = document.querySelector('.modal-overlay:not(.oculto)');
    if (modalAberto) {
      closeModal(modalAberto);
      hideAutocomplete();
      hideInfoHoverTooltip();
      return;
    }
    if (autocompleteState.items.length) {
      hideAutocomplete();
      return;
    }
    if (editingText || ev.target === campoTituloCapitulo) {
      ev.preventDefault();
      document.getElementById('botaoVoltarEditor')?.click();
      return;
    }
  }

  if (!ev.altKey || ev.ctrlKey || ev.metaKey) return;

  if (key === '0') { ev.preventDefault(); focusSceneByIndex(getSceneBlocks().length - 1); return; }
  if (key === '1') { ev.preventDefault(); focusSceneByIndex(0); return; }

  if (key === 'o') { ev.preventDefault(); toggleOnlyScriptMode(); return; }
  if (!editingText) return;

  const blockShortcuts = {
    c: 'scene_heading',
    a: 'action',
    p: 'character',
    d: 'dialogue',
    s: 'parenthetical',
    l: 'shot',
    t: 'transition',
    n: 'comment',
    m: 'music',
    e: 'neutral',
  };
  const blockType = blockShortcuts[key];
  if (blockType) {
    ev.preventDefault();
    triggerToolbarBlock(blockType);
  }
});
formCatalogoEditor?.addEventListener('submit', async (ev) => {
  ev.preventDefault();
  const tipo = catalogoTipo.value;
  const original = formatCatalogName(catalogoNomeOriginal.value);
  const nome = formatCatalogName(catalogoNome.value);
  const erro = validarCatalogoEditor();
  if (erro) {
    if (statusCatalogo) statusCatalogo.textContent = erro;
    return;
  }
  if (statusCatalogo) statusCatalogo.textContent = i18n('js.saving');
  try {
    const itemId = catalogoItemAtivo?.id || '';
    if (original && original.toLowerCase() !== nome.toLowerCase()) {
      await deleteCatalogItem(tipo, original, itemId);
    }
    await persistCatalogItem(tipo, {
      id: original.toLowerCase() === nome.toLowerCase() ? itemId : '',
      nome,
      descricao: catalogoDescricao.value.trim(),
    });
    if (catalogoLinkAtivo?.isConnected) {
      catalogoLinkAtivo.textContent = nome;
      catalogoLinkAtivo.dataset.recursoNome = nome;
      catalogoLinkAtivo.dataset.recursoTipo = tipo;
      catalogoLinkAtivo.title = `${scriptResourceTypeLabel(tipo)}: ${nome}`;
      const linkedBlock = catalogoLinkAtivo.closest('.roteiro-bloco');
      if (linkedBlock) markBlockDirty(linkedBlock);
      scheduleAutosave();
    }
    if (statusCatalogo) statusCatalogo.textContent = i18n('js.save_item_success');
    closeModal(modalCatalogoEditor);
    openModal(modalCatalogo);
  } catch (err) {
    if (statusCatalogo) statusCatalogo.textContent = err.message || i18n('js.save_error');
  }
});


sumarioRoteiro?.addEventListener('click', (event) => {
  const button = event.target instanceof Element ? event.target.closest('.item-sumario') : null;
  if (!button) return;

  const index = Number.parseInt(button.dataset.sceneIndex || '', 10);
  if (Number.isInteger(index) && focusSceneByIndex(index)) return;

  const sceneId = button.dataset.sceneId || '';
  if (!sceneId) return;
  const targetScene = editor?.querySelector(`#${CSS.escape(sceneId)}`);
  if (targetScene) focusScene(targetScene);
});

autocomplete?.addEventListener('mousedown', (ev) => {
  const button = ev.target instanceof Element ? ev.target.closest('.autocomplete-item') : null;
  if (!button) return;
  ev.preventDefault();
  const index = Number.parseInt(button.dataset.index || '', 10);
  const item = Number.isInteger(index) ? autocompleteState.items[index] : null;
  chooseAutocomplete(item || button.dataset.value || button.textContent || '');
});
applyUppercaseInputs();
applyScriptTheme(getStoredScriptTheme(), { persist: false });
normalizeEditor();
autoCorretorSimples = window.AutoCorretorSimples?.init?.({
  editor,
  onContentMutated: (block) => {
    if (block) markBlockDirty(block);
    scheduleAutosave();
  },
}) || null;
autoCorretorSimples?.rescanAll?.();
applySceneNumbers();
requestAnimationFrame(() => {
  repaginateEditor({ preserveSelection: false });
  updateSceneSummary();
  updateSidebarStickyOffset();
});
payloadAnterior = JSON.stringify({ titulo: campoTituloCapitulo?.value?.trim() || i18n('editor.no_title'), html: serialize() });

document.getElementById('btnNovoItemCatalogo')?.addEventListener('click', ()=> openCatalogEditor(catalogoTipo.value));

window.addEventListener('load', updateSidebarStickyOffset);

document.addEventListener('keyup', (ev) => {
  if (ev.key === 'Alt') syncAltLinkModeState(false);
});
editor?.addEventListener('input', () => scheduleEnsureScriptCaretVisible(true));
editor?.addEventListener('click', () => scheduleEnsureScriptCaretVisible(true));
editor?.addEventListener('focusin', () => scheduleEnsureScriptCaretVisible(true));
editor?.addEventListener('keyup', (ev) => { if (['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Enter','Backspace','Delete'].includes(ev.key)) scheduleEnsureScriptCaretVisible(true); });
window.addEventListener('blur', () => syncAltLinkModeState(false));
document.addEventListener('visibilitychange', () => { if (document.hidden) syncAltLinkModeState(false); });
syncAltLinkModeState(false);
window.addEventListener('beforeunload', () => doAutosave(true));


const btnAbrirRevisaoOrtografica = document.getElementById('btnAbrirRevisaoOrtografica');
const modalRevisaoOrtografica = document.getElementById('modalRevisaoOrtografica');
const revisaoTextoOriginal = document.getElementById('revisaoTextoOriginal');
const revisaoTextoCorrigido = document.getElementById('revisaoTextoCorrigido');
const revisaoSubtitulo = document.getElementById('revisaoSubtitulo');
const revisaoStatus = document.getElementById('revisaoStatus');
const btnIgnorarBlocoRevisao = document.getElementById('btnIgnorarBlocoRevisao');
const btnRevisarBlocoRevisao = document.getElementById('btnRevisarBlocoRevisao');
const btnAceitarBlocoRevisao = document.getElementById('btnAceitarBlocoRevisao');
const estadoRevisaoOrtografica = { blocos: [], indice: -1, carregando: false };

const LIMITE_PALAVRAS_REVISAO = 70;
/** Blocojarevisadopelaia. Usada pelo fluxo principal da aplicação. */
function blocoJaRevisadoPelaIA(block) {
  return Boolean(block?.dataset?.revisadoIa === 'true' || block?.classList?.contains('bloco-revisado-ia'));
}
/** Marcarblococomorevisadopelaia. Usada pelo fluxo principal da aplicação. */
function marcarBlocoComoRevisadoPelaIA(block) {
  if (!block) return;
  block.dataset.revisadoIa = 'true';
  block.classList.add('bloco-revisado-ia');
}
/** Limparmarcaderevisaoia. Usada pelo fluxo principal da aplicação. */
function limparMarcaDeRevisaoIA(block) {
  if (!block) return;
  delete block.dataset.revisadoIa;
  block.classList.remove('bloco-revisado-ia');
}
/** Contarpalavrasrevisao. Usada pelo fluxo principal da aplicação. */
function contarPalavrasRevisao(texto = '') { return (String(texto).trim().match(/\S+/g) || []).length; }
function textoLimpoDoBlocoRevisao(block) { return blockPlainText(block).trim(); }
/** Quebrargrupoporpalavras. Usada pelo fluxo principal da aplicação. */
function quebrarGrupoPorPalavras(blocos) {
  const grupos = [];
  let grupoAtual = [];
  let totalPalavras = 0;
  /** Finalizargrupo. Usada pelo fluxo principal da aplicação. */
  const finalizarGrupo = () => {
    if (!grupoAtual.length) return;
    grupos.push({
      blocos: [...grupoAtual],
      original: grupoAtual.map((block) => textoLimpoDoBlocoRevisao(block)).join('\n\n'),
      corrigido: '',
      revisado: false,
    });
    grupoAtual = [];
    totalPalavras = 0;
  };
  blocos.forEach((block) => {
    const texto = textoLimpoDoBlocoRevisao(block);
    const palavras = contarPalavrasRevisao(texto);
    if (grupoAtual.length && totalPalavras + palavras > LIMITE_PALAVRAS_REVISAO) finalizarGrupo();
    grupoAtual.push(block);
    totalPalavras += palavras;
    if (totalPalavras >= LIMITE_PALAVRAS_REVISAO) finalizarGrupo();
  });
  finalizarGrupo();
  return grupos;
}
/** Montarblocosderevisao. Usada pelo fluxo principal da aplicação. */
function montarBlocosDeRevisao() {
  const blocos = getAllBlocks().filter((block) => !blocoJaRevisadoPelaIA(block) && contarPalavrasRevisao(textoLimpoDoBlocoRevisao(block)) > 0);
  return quebrarGrupoPorPalavras(blocos);
}
async function solicitarCorrecaoOrtografica(texto) {
  const resposta = await fetch('/api/revisao/gemini', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ texto, idioma: window.EDITOR_CONFIG?.idioma || "pt-BR" }),
  });
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados?.erro || i18n('js.api_consult_error'));
  return String(dados?.texto_corrigido || texto);
}
/** Distribuirtextocorrigidoentreblocos. Usada pelo fluxo principal da aplicação. */
function distribuirTextoCorrigidoEntreBlocos(texto, quantidade) {
  const partes = String(texto || '').split(/\n\s*\n/).map((item) => item.trim());
  if (partes.length === quantidade) return partes;
  if (partes.length > quantidade) {
    const base = partes.slice(0, quantidade - 1);
    base.push(partes.slice(quantidade - 1).join('\n\n').trim());
    return base;
  }
  while (partes.length < quantidade) partes.push('');
  return partes;
}
/** Exibiretaparevisaoconcluida. Usada pelo fluxo principal da aplicação. */
function exibirEtapaRevisaoConcluida() {
  revisaoSubtitulo.textContent = i18n('editor.review_done');
  revisaoStatus.textContent = i18n('editor.review_all_processed');
  revisaoTextoOriginal.textContent = i18n('editor.review_no_pending_blocks');
  revisaoTextoCorrigido.textContent = i18n('editor.review_you_can_close');
  revisaoTextoOriginal.classList.add('vazio');
  revisaoTextoCorrigido.classList.add('vazio');
  btnIgnorarBlocoRevisao.disabled = true;
  btnRevisarBlocoRevisao.disabled = true;
  btnAceitarBlocoRevisao.disabled = true;
}
/** Atualizaracoesrevisao. Usada pelo fluxo principal da aplicação. */
function atualizarAcoesRevisao(etapa) {
  const revisado = Boolean(etapa?.revisado);
  btnIgnorarBlocoRevisao.disabled = estadoRevisaoOrtografica.carregando;
  btnRevisarBlocoRevisao.disabled = estadoRevisaoOrtografica.carregando;
  btnAceitarBlocoRevisao.disabled = estadoRevisaoOrtografica.carregando || !revisado;
}
/** Preencheretaparevisaoatual. Usada pelo fluxo principal da aplicação. */
function preencherEtapaRevisaoAtual() {
  const etapa = estadoRevisaoOrtografica.blocos[estadoRevisaoOrtografica.indice];
  if (!etapa) {
    exibirEtapaRevisaoConcluida();
    return;
  }
  revisaoTextoOriginal.classList.remove('vazio');
  revisaoTextoCorrigido.classList.remove('vazio');
  revisaoSubtitulo.textContent = i18n('editor.review_block_counter', { current: estadoRevisaoOrtografica.indice + 1, total: estadoRevisaoOrtografica.blocos.length });
  revisaoTextoOriginal.textContent = etapa.original;
  revisaoTextoCorrigido.textContent = etapa.revisado
    ? (etapa.corrigido || etapa.original)
    : i18n('editor.review_click_this_block');
  revisaoStatus.textContent = etapa.revisado
    ? (etapa.corrigido === etapa.original ? i18n('editor.review_no_corrections') : i18n('editor.review_suggestion_ready'))
    : i18n('editor.review_click_start');
  atualizarAcoesRevisao(etapa);
}
async function revisarBlocoAtualDaRevisao() {
  const etapa = estadoRevisaoOrtografica.blocos[estadoRevisaoOrtografica.indice];
  if (!etapa || estadoRevisaoOrtografica.carregando) return;
  estadoRevisaoOrtografica.carregando = true;
  revisaoTextoCorrigido.textContent = i18n('editor.review_consulting');
  revisaoStatus.textContent = i18n('editor.review_fetching_suggestion');
  atualizarAcoesRevisao(etapa);
  try {
    etapa.corrigido = await solicitarCorrecaoOrtografica(etapa.original);
    etapa.revisado = true;
    revisaoTextoCorrigido.textContent = etapa.corrigido;
    revisaoStatus.textContent = etapa.corrigido === etapa.original ? i18n('editor.review_no_corrections') : i18n('editor.review_suggestion_ready');
  } catch (erro) {
    etapa.corrigido = etapa.original;
    etapa.revisado = false;
    revisaoTextoCorrigido.textContent = i18n('editor.review_could_not_generate');
    revisaoStatus.textContent = erro?.message || i18n('editor.review_service_failure');
  } finally {
    estadoRevisaoOrtografica.carregando = false;
    atualizarAcoesRevisao(etapa);
  }
}
/** Avancarrevisaoortografica. Usada pelo fluxo principal da aplicação. */
function avancarRevisaoOrtografica() {
  estadoRevisaoOrtografica.indice += 1;
  preencherEtapaRevisaoAtual();
}
/** Iniciarrevisaoortografica. Usada pelo fluxo principal da aplicação. */
function iniciarRevisaoOrtografica() {
  estadoRevisaoOrtografica.blocos = montarBlocosDeRevisao();
  estadoRevisaoOrtografica.indice = 0;
  openModal(modalRevisaoOrtografica);
  if (!estadoRevisaoOrtografica.blocos.length) {
    revisaoSubtitulo.textContent = i18n('editor.review_nothing');
    revisaoStatus.textContent = i18n('editor.review_not_enough_text');
    revisaoTextoOriginal.textContent = i18n('editor.review_write_some_content');
    revisaoTextoCorrigido.textContent = i18n('editor.review_blocks_auto_split');
    revisaoTextoOriginal.classList.add('vazio');
    revisaoTextoCorrigido.classList.add('vazio');
    btnIgnorarBlocoRevisao.disabled = true;
    btnRevisarBlocoRevisao.disabled = true;
    btnAceitarBlocoRevisao.disabled = true;
    return;
  }
  preencherEtapaRevisaoAtual();
}
/** Aceitarsugestaorevisaoortografica. Usada pelo fluxo principal da aplicação. */
function aceitarSugestaoRevisaoOrtografica() {
  const etapa = estadoRevisaoOrtografica.blocos[estadoRevisaoOrtografica.indice];
  if (!etapa || estadoRevisaoOrtografica.carregando || !etapa.revisado) return;
  const partes = distribuirTextoCorrigidoEntreBlocos(etapa.corrigido, etapa.blocos.length);
  etapa.blocos.forEach((block, indice) => {
    setBlockPlainText(block, partes[indice] || '');
    marcarBlocoComoRevisadoPelaIA(block);
  });
  repaginateEditor({ preserveSelection: false });
  updateSceneSummary();
  scheduleAutosave();
  avancarRevisaoOrtografica();
}
btnAbrirRevisaoOrtografica?.addEventListener('click', iniciarRevisaoOrtografica);
btnIgnorarBlocoRevisao?.addEventListener('click', () => { if (!estadoRevisaoOrtografica.carregando) avancarRevisaoOrtografica(); });
btnRevisarBlocoRevisao?.addEventListener('click', revisarBlocoAtualDaRevisao);
btnAceitarBlocoRevisao?.addEventListener('click', aceitarSugestaoRevisaoOrtografica);
document.querySelectorAll('[data-fechar-revisao="true"]').forEach((el) => el.addEventListener('click', (ev) => { ev.preventDefault(); closeModal(el.closest('.modal')); }));
