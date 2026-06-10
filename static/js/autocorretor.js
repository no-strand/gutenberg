/**
 * Motor de autocorreção do editor, com análise de texto, sugestões e interação visual com o usuário.
 * Créditos do projeto: Nostrand.
 */

/** Aci18n. Usada pelo fluxo principal da aplicação. */
const acI18n = (key, vars = {}) => (window.t ? window.t(key, vars) : key);
const acI18nData = (key, fallback = null) => ((window.APP_CONFIG && window.APP_CONFIG.i18n && Object.prototype.hasOwnProperty.call(window.APP_CONFIG.i18n, key)) ? window.APP_CONFIG.i18n[key] : fallback);

(function () {
  const MENU_ID = 'autocorretorSugestoes';
  const DEBOUNCE_MS = 240;
  const IDLE_RESCAN_MS = 2000;
  const HIGHLIGHT_CLASS = 'autocorretor-destaque';
  const IGNORE_ATTR = 'data-autocorretor-ignore';

  const AUTOCORRECT_LOCALE = String(window.EDITOR_CONFIG?.idioma || window.APP_CONFIG?.idiomaApp || 'pt-BR').toLowerCase().startsWith('en') ? 'en_US' : 'pt_BR';
  const TERM_PAIRS = acI18nData('autocorrect.term_pairs', []);

  const TERM_RULES = [];
  const termSeen = new Set();
  TERM_PAIRS.forEach(([wrong, suggestion]) => {
    const key = `${wrong}=>${suggestion}`.toLowerCase();
    if (!wrong || !suggestion || termSeen.has(key)) return;
    termSeen.add(key);
    TERM_RULES.push({
      type: 'term',
      wrong,
      suggestion,
      regex: new RegExp(`(^|[^\\p{L}\\p{N}_])(${escapeRegExp(wrong)})(?=$|[^\\p{L}\\p{N}_])`, 'giu'),
      reason: acI18n('autocorrect.reason_possible_wrong_form', { wrong })
    });
  });

  const COMMON_CONTEXT_RULES = [
    {
      type: 'regex',
      reason: acI18n('autocorrect.reason_duplicate_word'),
      suggestionFromMatch: (m) => m[2],
      regex: /(^|[^\p{L}\p{N}_])([\p{L}À-ÿ]{2,})(\s+)\2(?=$|[^\p{L}\p{N}_])/giu,
      fullMatch: true,
      replacementFromMatch: (m) => `${m[1] || ''}${m[2]}`,
    },
    {
      type: 'regex',
      reason: acI18n('autocorrect.reason_sentence_lowercase'),
      suggestionFromMatch: (m) => preserveCase(m[2], capitalize(m[2])),
      regex: /(^|[.!?]\s+)([a-zà-ÿ])/g,
      targetGroup: 2,
      validate: (_, __, match) => /^[a-zà-ÿ]$/.test(match[2] || ''),
    },
    {
      type: 'regex',
      reason: acI18n('autocorrect.reason_repeated_quotes'),
      suggestionFromMatch: () => '"',
      regex: /("{2,})/g,
      targetGroup: 1,
    }
  ];

  const PT_CONTEXT_RULES = [
    {
      type: 'regex',
      reason: acI18n('autocorrect.reason_mais_mas'),
      suggestion: 'mas',
      regex: /(^|[^\p{L}\p{N}_])(mais)(?=\s+(eu|tu|ele|ela|nós|nos|vocês|voces|eles|elas|isso|isto|aquilo|não|nao|que|porém|porem|também|tambem|ainda|se|me|te|lhe|nos)\b)/giu,
      targetGroup: 2,
    },
    {
      type: 'regex',
      reason: acI18n('autocorrect.reason_mim_before_infinitive'),
      suggestionFromMatch: (m) => preserveCase(m[2], 'eu'),
      regex: /(^|[^\p{L}\p{N}_])(mim)(?=\s+(fazer|dizer|ir|trazer|escrever|ler|estudar|resolver|comprar|pagar|viajar|seguir|trabalhar|conseguir|ver|usar|explicar|falar|cuidar)\b)/giu,
      targetGroup: 2,
    },
    {
      type: 'regex',
      reason: acI18n('autocorrect.reason_mal_mau'),
      suggestion: 'mau',
      regex: /(^|[^\p{L}\p{N}_])(mal)(?=\s+(humor|cheiro|caráter|pressentimento|costume|agouro|desempenho|resultado)\b)/giu,
      targetGroup: 2,
    },
    {
      type: 'regex',
      reason: acI18n('autocorrect.reason_mau_mal'),
      suggestion: 'mal',
      regex: /(^|[^\p{L}\p{N}_])(mau)(?=\s+(feito|feita|feitos|feitas|estar|estava|estou|ficou|passou|saiu)\b)/giu,
      targetGroup: 2,
    },
    {
      type: 'regex',
      reason: acI18n('autocorrect.reason_missing_ha'),
      suggestion: 'há',
      regex: /(^|[^\p{L}\p{N}_])(a)(?=\s+(anos?|meses?|dias?|semanas?|horas?|minutos?)\b)/giu,
      targetGroup: 2,
      validate: (text, start) => {
        const before = text.slice(Math.max(0, start - 12), start).toLowerCase();
        return !/\bda?$|\buma?$|\bem\s*$/.test(before);
      }
    },
    {
      type: 'regex',
      reason: acI18n('autocorrect.reason_missing_pode_accent'),
      suggestion: 'pôde',
      regex: /(^|[^\p{L}\p{N}_])(pode)(?=\s+(ontem|antes|naquele|naquela|naquele dia|na véspera|finalmente)\b)/giu,
      targetGroup: 2,
    },
    {
      type: 'regex',
      reason: acI18n('autocorrect.reason_por_que_question'),
      suggestion: 'por que',
      regex: /(^|[^\p{L}\p{N}_])(porque)(?=[^\n?.!]{0,40}\?)/giu,
      targetGroup: 2,
    },
    {
      type: 'regex',
      reason: acI18n('autocorrect.reason_missing_senao'),
      suggestion: 'senão',
      regex: /(^|[^\p{L}\p{N}_])(se não)(?=\s+(for|fosse|chover|der|couber|puder|quiser|acontecer|vier)\b)/giu,
      targetGroup: 2,
    },
    {
      type: 'regex',
      reason: acI18n('autocorrect.reason_missing_se_nao'),
      suggestion: 'se não',
      regex: /(^|[^\p{L}\p{N}_])(senão)(?=\s+(me engano|for isso|quando|se)\b)/giu,
      targetGroup: 2,
    },
    {
      type: 'regex',
      reason: acI18n('autocorrect.reason_a_gente_singular'),
      suggestionFromMatch: (m) => preserveCase(m[2], 'vai'),
      regex: /(^|[^\p{L}\p{N}_])(vamos|fomos|iremos|queremos|podemos|estamos)(?=[^\n]{0,24}\ba gente\b)/giu,
      targetGroup: 2,
      reverseContext: true,
    },
    {
      type: 'regex',
      reason: acI18n('autocorrect.reason_nos_plural'),
      suggestionFromMatch: (m) => ({ 'vai': 'vamos', 'foi': 'fomos', 'quer': 'queremos', 'pode': 'podemos', 'está': 'estamos', 'ta': 'estamos' }[(m[2] || '').toLowerCase()] || m[2]),
      regex: /(^|[^\p{L}\p{N}_])(vai|foi|quer|pode|está|ta)(?=[^\n]{0,18}\bnós\b)/giu,
      targetGroup: 2,
      reverseContext: true,
    }
  ];

  const EN_CONTEXT_RULES = [
    {
      type: 'regex',
      reason: acI18n('autocorrect.reason_your_youre'),
      suggestion: "you're",
      regex: /(^|[^\p{L}\p{N}_])(your)(?=\s+(going|doing|trying|looking|being|making|working|using|writing|reading|talking|running|walking)\b)/giu,
      targetGroup: 2,
    },
    {
      type: 'regex',
      reason: acI18n('autocorrect.reason_their_there'),
      suggestion: 'there',
      regex: /(^|[^\p{L}\p{N}_])(their)(?=\s+(is|are|was|were|has|have|will be|seems|appears)\b)/giu,
      targetGroup: 2,
    },
    {
      type: 'regex',
      reason: acI18n('autocorrect.reason_then_than'),
      suggestion: 'than',
      regex: /(^|[^\p{L}\p{N}_])(then)(?=\s+(me|him|her|us|them)\b)/giu,
      targetGroup: 2,
    },
    {
      type: 'regex',
      reason: acI18n('autocorrect.reason_loose_lose'),
      suggestion: 'lose',
      regex: /(^|[^\p{L}\p{N}_])(loose)(?=\s+(it|my|your|our|their|the|this|that|everything|control|focus|money|time|weight)\b)/giu,
      targetGroup: 2,
    }
  ];

  const CONTEXT_RULES = [
    ...(AUTOCORRECT_LOCALE === 'en_US' ? EN_CONTEXT_RULES : PT_CONTEXT_RULES),
    ...COMMON_CONTEXT_RULES
  ];

  /** Escaperegexp. Usada pelo fluxo principal da aplicação. */
  function escapeRegExp(text) {
    return String(text || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  /** Capitalize. Usada pelo fluxo principal da aplicação. */
  function capitalize(text) {
    const value = String(text || '');
    return value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
  }

  /** Preservecase. Usada pelo fluxo principal da aplicação. */
  function preserveCase(original, suggestion) {
    const source = String(original || '');
    const target = String(suggestion || '');
    if (!source) return target;
    if (source === source.toUpperCase()) return target.toUpperCase();
    if (source[0] === source[0].toUpperCase()) return target.charAt(0).toUpperCase() + target.slice(1);
    return target;
  }

  /** Normalizeforignore. Usada pelo fluxo principal da aplicação. */
  function normalizeForIgnore(text) {
    return String(text || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/\s+/g, ' ')
      .trim()
      .toLowerCase();
  }

  /** Closestblockfromnode. Usada pelo fluxo principal da aplicação. */
  function closestBlockFromNode(root, node) {
    let current = node?.nodeType === Node.TEXT_NODE ? node.parentElement : node;
    while (current && current !== root) {
      if (current instanceof HTMLElement && !current.classList.contains(HIGHLIGHT_CLASS) && current.closest(`#${MENU_ID}`) == null) {
        const isRoteiro = current.classList.contains('roteiro-bloco');
        const isTextBlock = /^(P|H1|H2|H3|LI|BLOCKQUOTE|DIV)$/i.test(current.tagName || '');
        if (isRoteiro || isTextBlock) return current;
      }
      current = current.parentElement;
    }
    return root;
  }

  /** Savecaretoffset. Usada pelo fluxo principal da aplicação. */
  function saveCaretOffset(container) {
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount || !container.contains(sel.anchorNode)) return null;
    const range = sel.getRangeAt(0).cloneRange();
    const pre = range.cloneRange();
    pre.selectNodeContents(container);
    pre.setEnd(range.endContainer, range.endOffset);
    return pre.toString().length;
  }

  /** Restorecaretoffset. Usada pelo fluxo principal da aplicação. */
  function restoreCaretOffset(container, offset) {
    if (offset == null) return;
    const selection = window.getSelection();
    if (!selection) return;
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
    let remaining = offset;
    while (walker.nextNode()) {
      const text = walker.currentNode;
      const length = text.textContent.length;
      if (remaining <= length) {
        const range = document.createRange();
        range.setStart(text, Math.max(0, remaining));
        range.collapse(true);
        selection.removeAllRanges();
        selection.addRange(range);
        return;
      }
      remaining -= length;
    }
    const range = document.createRange();
    range.selectNodeContents(container);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
  }


  /** Createselectionmarker. Usada pelo fluxo principal da aplicação. */
  function createSelectionMarker(doc, id) {
    const marker = doc.createElement('span');
    marker.setAttribute('data-autocorretor-marker', id);
    marker.setAttribute('aria-hidden', 'true');
    marker.style.display = 'inline-block';
    marker.style.width = '0';
    marker.style.height = '0';
    marker.style.overflow = 'hidden';
    marker.style.lineHeight = '0';
    marker.textContent = '​';
    return marker;
  }

  /** Saveselectionbookmark. Usada pelo fluxo principal da aplicação. */
  function saveSelectionBookmark(container) {
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount || !container.contains(sel.anchorNode)) return null;
    const originalRange = sel.getRangeAt(0).cloneRange();
    const collapsed = originalRange.collapsed;
    const doc = container.ownerDocument || document;
    const token = `ac-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    const startId = `${token}-start`;
    const endId = `${token}-end`;

    if (!collapsed) {
      const endRange = originalRange.cloneRange();
      endRange.collapse(false);
      endRange.insertNode(createSelectionMarker(doc, endId));
    }

    const startRange = originalRange.cloneRange();
    startRange.collapse(true);
    startRange.insertNode(createSelectionMarker(doc, startId));

    return { startId, endId: collapsed ? null : endId, collapsed };
  }

  /** Restoreselectionbookmark. Usada pelo fluxo principal da aplicação. */
  function restoreSelectionBookmark(container, bookmark) {
    if (!bookmark) return false;
    const selection = window.getSelection();
    if (!selection) return false;
    const startMarker = container.querySelector(`[data-autocorretor-marker="${bookmark.startId}"]`);
    const endMarker = bookmark.endId ? container.querySelector(`[data-autocorretor-marker="${bookmark.endId}"]`) : null;
    if (!startMarker) return false;

    const range = document.createRange();
    if (bookmark.collapsed || !endMarker) {
      range.setStartBefore(startMarker);
      range.collapse(true);
    } else {
      range.setStartBefore(startMarker);
      range.setEndBefore(endMarker);
    }

    selection.removeAllRanges();
    selection.addRange(range);

    if (document.activeElement !== container && typeof container.focus === 'function') {
      try { container.focus(); } catch (_) {}
    }

    startMarker.remove();
    if (endMarker) endMarker.remove();
    return true;
  }

  /** Autofixtext. Usada pelo fluxo principal da aplicação. */
  function autoFixText(text) {
    return String(text || '')
      .replace(/﻿/g, '')
      .replace(/[  ]/g, ' ')
      .replace(/[‌‍]/g, '');
  }

  /** Unwrapelement. Usada pelo fluxo principal da aplicação. */
  function unwrapElement(el) {
    if (!el?.parentNode) return;
    while (el.firstChild) el.parentNode.insertBefore(el.firstChild, el);
    el.remove();
  }

  /** Stripallhighlights. Usada pelo fluxo principal da aplicação. */
  function stripAllHighlights(root) {
    if (!root) return;
    root.querySelectorAll(`.${HIGHLIGHT_CLASS}`).forEach(unwrapElement);
  }

  /** Stripdecorationsfromclone. Usada pelo fluxo principal da aplicação. */
  function stripDecorationsFromClone(root) {
    if (!root) return root;
    root.querySelectorAll(`.${HIGHLIGHT_CLASS}`).forEach((el) => {
      const text = el.getAttribute('data-original-text') || el.textContent || '';
      el.replaceWith(root.ownerDocument.createTextNode(text));
    });
    root.querySelectorAll(`#${MENU_ID}`).forEach((el) => el.remove());
    return root;
  }

  /** Makehighlight. Usada pelo fluxo principal da aplicação. */
  function makeHighlight(doc, original, suggestion, reason, ignoreKey) {
    const span = doc.createElement('span');
    span.className = HIGHLIGHT_CLASS;
    span.textContent = original;
    span.dataset.suggestion = suggestion;
    span.dataset.reason = reason;
    span.dataset.originalText = original;
    span.dataset.ignoreKey = ignoreKey;
    span.setAttribute('tabindex', '0');
    span.setAttribute('role', 'button');
    return span;
  }

  /** Collectissues. Usada pelo fluxo principal da aplicação. */
  function collectIssues(text, ignoredSet) {
    const issues = [];
    const occupied = [];
    /** Addissue. Usada pelo fluxo principal da aplicação. */
    const addIssue = (start, end, original, suggestion, reason) => {
      if (start == null || end == null || end <= start) return;
      if (normalizeForIgnore(original) === normalizeForIgnore(suggestion)) return;
      const ignoreKey = normalizeForIgnore(`${original}=>${suggestion}`);
      if (ignoredSet?.has(ignoreKey)) return;
      if (occupied.some(([a, b]) => start < b && end > a)) return;
      occupied.push([start, end]);
      issues.push({ start, end, original, suggestion, reason, ignoreKey });
    };

    CONTEXT_RULES.forEach((rule) => {
      rule.regex.lastIndex = 0;
      let match;
      while ((match = rule.regex.exec(text))) {
        if (rule.fullMatch) {
          const original = match[0];
          const suggestion = preserveCase(original, rule.replacementFromMatch?.(match) || rule.suggestionFromMatch?.(match) || rule.suggestion || original);
          if (!rule.validate || rule.validate(text, match.index, match)) {
            addIssue(match.index, match.index + original.length, original, suggestion, rule.reason);
          }
          continue;
        }
        const target = match[rule.targetGroup || 0] || match[0];
        const localIndex = match[0].toLowerCase().indexOf(String(target).toLowerCase());
        const start = match.index + Math.max(0, localIndex);
        const end = start + target.length;
        if (rule.validate && !rule.validate(text, start, match)) continue;
        const suggestion = preserveCase(target, rule.suggestionFromMatch?.(match) || rule.suggestion || target);
        addIssue(start, end, target, suggestion, rule.reason);
      }
    });

    TERM_RULES.forEach((rule) => {
      rule.regex.lastIndex = 0;
      let match;
      while ((match = rule.regex.exec(text))) {
        const target = match[2];
        const localIndex = match[0].toLowerCase().indexOf(String(target).toLowerCase());
        const start = match.index + Math.max(0, localIndex);
        const end = start + target.length;
        const suggestion = preserveCase(target, rule.suggestion);
        addIssue(start, end, target, suggestion, rule.reason);
      }
    });

    return issues.sort((a, b) => a.start - b.start);
  }

  /** Processtextnode. Usada pelo fluxo principal da aplicação. */
  function processTextNode(textNode, ignoredSet) {
    const parent = textNode.parentElement;
    if (!parent || parent.closest(`.${HIGHLIGHT_CLASS}`)) return false;
    const originalText = textNode.textContent || '';
    const fixedText = autoFixText(originalText);
    if (fixedText !== originalText) textNode.textContent = fixedText;
    const text = textNode.textContent || '';
    const issues = collectIssues(text, ignoredSet);
    if (!issues.length) return fixedText !== originalText;

    const frag = document.createDocumentFragment();
    let cursor = 0;
    issues.forEach((issue) => {
      if (issue.start > cursor) frag.appendChild(document.createTextNode(text.slice(cursor, issue.start)));
      frag.appendChild(makeHighlight(document, issue.original, issue.suggestion, issue.reason, issue.ignoreKey));
      cursor = issue.end;
    });
    if (cursor < text.length) frag.appendChild(document.createTextNode(text.slice(cursor)));
    textNode.replaceWith(frag);
    return true;
  }

  /** Createmenu. Usada pelo fluxo principal da aplicação. */
  function createMenu() {
    let menu = document.getElementById(MENU_ID);
    if (menu) return menu;
    menu = document.createElement('div');
    menu.id = MENU_ID;
    menu.className = 'autocorretor-menu oculto';
    document.body.appendChild(menu);
    return menu;
  }

  /** Positionmenu. Usada pelo fluxo principal da aplicação. */
  function positionMenu(menu, anchor) {
    const rect = anchor.getBoundingClientRect();
    menu.style.left = `${Math.min(window.innerWidth - 280, Math.max(12, rect.left))}px`;
    menu.style.top = `${Math.min(window.innerHeight - 120, rect.bottom + 10)}px`;
  }

  /** Init. Usada pelo fluxo principal da aplicação. */
  function init(options = {}) {
    const editor = options.editor;
    if (!editor) return null;
    const menu = createMenu();
    const ignoredByBlock = new WeakMap();
    let scanTimer = null;
    let openedHighlight = null;
    let suppressOutsideCloseUntil = 0;
    let isComposing = false;

    /** Hidemenu. Usada pelo fluxo principal da aplicação. */
    function hideMenu() {
      menu.classList.add('oculto');
      menu.innerHTML = '';
      openedHighlight = null;
    }

    /** Markinteractionwindow. Usada pelo fluxo principal da aplicação. */
    function markInteractionWindow(ms = 180) {
      suppressOutsideCloseUntil = Date.now() + ms;
    }

    /** Shouldsuppressoutsideclose. Usada pelo fluxo principal da aplicação. */
    function shouldSuppressOutsideClose() {
      return Date.now() <= suppressOutsideCloseUntil;
    }

    /** Hidemenusoon. Usada pelo fluxo principal da aplicação. */
    function hideMenuSoon(delay = 0) {
      window.setTimeout(() => {
        if (shouldSuppressOutsideClose()) return;
        if (!menu.matches(':hover') && !menu.contains(document.activeElement)) hideMenu();
      }, delay);
    }

    /** Getignoredset. Usada pelo fluxo principal da aplicação. */
    function getIgnoredSet(block) {
      let set = ignoredByBlock.get(block);
      if (!set) {
        set = new Set();
        ignoredByBlock.set(block, set);
      }
      return set;
    }

    /** Cleanblock. Usada pelo fluxo principal da aplicação. */
    function cleanBlock(block) {
      if (!block) return;
      stripAllHighlights(block);
      if (block instanceof HTMLElement) block.querySelectorAll(`[${IGNORE_ATTR}]`).forEach((el) => el.removeAttribute(IGNORE_ATTR));
    }

    /** Blockcontainsactiveselection. Usada pelo fluxo principal da aplicação. */
    function blockContainsActiveSelection(block) {
      if (!block || !editor) return false;
      const sel = window.getSelection();
      if (!sel || !sel.rangeCount) return false;
      const range = sel.getRangeAt(0);
      if (!block.contains(range.commonAncestorContainer)) return false;
      const active = document.activeElement;
      return active === editor || !!active?.closest?.('[contenteditable="true"]');
    }

    /** Rescanblock. Usada pelo fluxo principal da aplicação. */
    function rescanBlock(block, preserveCaret = true, optionsOverride = {}) {
      if (!block || !block.isConnected) return;
      const skipWhileTyping = optionsOverride.skipWhileTyping !== false;
      if (skipWhileTyping && blockContainsActiveSelection(block)) return;
      const bookmark = preserveCaret ? saveSelectionBookmark(block) : null;
      const caretOffset = preserveCaret && !bookmark ? saveCaretOffset(block) : null;
      cleanBlock(block);
      const ignoredSet = getIgnoredSet(block);
      const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT, {
        acceptNode(node) {
          if (!node.textContent || !node.textContent.trim()) return NodeFilter.FILTER_REJECT;
          if (node.parentElement?.closest(`.${HIGHLIGHT_CLASS}`)) return NodeFilter.FILTER_REJECT;
          return NodeFilter.FILTER_ACCEPT;
        }
      });
      const textNodes = [];
      while (walker.nextNode()) textNodes.push(walker.currentNode);
      let changed = false;
      textNodes.forEach((textNode) => { changed = processTextNode(textNode, ignoredSet) || changed; });
      if (changed && typeof options.onContentMutated === 'function') options.onContentMutated(block);
      if (preserveCaret) {
        const restored = bookmark ? restoreSelectionBookmark(block, bookmark) : false;
        if (!restored) restoreCaretOffset(block, caretOffset);
        if (document.activeElement !== editor && blockContainsActiveSelection(block)) {
          try { editor.focus(); } catch (_) {}
        }
      }
    }

    /** Schedulerescanfromnode. Usada pelo fluxo principal da aplicação. */
    function scheduleRescanFromNode(node, optionsOverride = {}) {
      const block = closestBlockFromNode(editor, node || document.activeElement || editor);
      if (!block) return;
      clearTimeout(scanTimer);
      if (isComposing) return;
      const delay = Number.isFinite(optionsOverride.delay) ? optionsOverride.delay : DEBOUNCE_MS;
      const override = { ...optionsOverride };
      delete override.delay;
      scanTimer = setTimeout(() => rescanBlock(block, true, override), delay);
    }

    /** Applysuggestion. Usada pelo fluxo principal da aplicação. */
    function applySuggestion(highlight) {
      const block = closestBlockFromNode(editor, highlight);
      if (!block) return;
      const text = document.createTextNode(highlight.dataset.suggestion || highlight.textContent || '');
      highlight.replaceWith(text);
      hideMenu();
      rescanBlock(block, false);
      if (typeof options.onContentMutated === 'function') options.onContentMutated(block);
    }

    /** Ignoresuggestion. Usada pelo fluxo principal da aplicação. */
    function ignoreSuggestion(highlight) {
      const block = closestBlockFromNode(editor, highlight);
      if (!block) return;
      getIgnoredSet(block).add(highlight.dataset.ignoreKey || normalizeForIgnore(`${highlight.textContent}=>${highlight.dataset.suggestion}`));
      const text = document.createTextNode(highlight.dataset.originalText || highlight.textContent || '');
      highlight.replaceWith(text);
      hideMenu();
      rescanBlock(block, false);
    }

    /** Openmenufor. Usada pelo fluxo principal da aplicação. */
    function openMenuFor(highlight) {
      if (!highlight?.isConnected) return;
      markInteractionWindow();
      openedHighlight = highlight;
      menu.innerHTML = `
        <div class="autocorretor-menu-titulo">${escapeHtml(acI18n('autocorrect.suggestion'))}</div>
        <div class="autocorretor-menu-texto">${highlight.dataset.reason || acI18n('autocorrect.possible_correction')}</div>
        <div class="autocorretor-menu-sugestao">${escapeHtml(highlight.dataset.suggestion || '')}</div>
        <div class="autocorretor-menu-acoes">
          <button type="button" class="botao-primario" data-autocorretor-action="apply"><strong>${escapeHtml(acI18n('autocorrect.apply'))}</strong></button>
          <button type="button" class="botao-secundario" data-autocorretor-action="ignore"><strong>${escapeHtml(acI18n('autocorrect.ignore'))}</strong></button>
        </div>`;
      positionMenu(menu, highlight);
      menu.classList.remove('oculto');
    }

    /** Runmenuactionfromevent. Usada pelo fluxo principal da aplicação. */
    function runMenuActionFromEvent(ev) {
      const button = ev.target instanceof HTMLElement ? ev.target.closest('[data-autocorretor-action]') : null;
      if (!button || !openedHighlight) return false;
      ev.preventDefault();
      ev.stopPropagation();
      markInteractionWindow(250);
      const action = button.dataset.autocorretorAction;
      if (action === 'apply') applySuggestion(openedHighlight);
      if (action === 'ignore') ignoreSuggestion(openedHighlight);
      return true;
    }

    editor.addEventListener('compositionstart', () => {
      isComposing = true;
      clearTimeout(scanTimer);
    });

    editor.addEventListener('compositionend', (ev) => {
      isComposing = false;
      scheduleRescanFromNode(ev.target, { skipWhileTyping: false });
    });

    editor.addEventListener('input', (ev) => {
      if (isComposing) return;
      scheduleRescanFromNode(ev.target, { skipWhileTyping: false, delay: IDLE_RESCAN_MS });
    });
    editor.addEventListener('paste', () => setTimeout(() => scheduleRescanFromNode(document.activeElement || editor, { skipWhileTyping: false }), 10));
    editor.addEventListener('focusin', (ev) => {
      const block = closestBlockFromNode(editor, ev.target);
      if (block) cleanBlock(block);
    });
    editor.addEventListener('focusout', (ev) => {
      const related = ev.relatedTarget;
      if (related instanceof HTMLElement && related.closest(`#${MENU_ID}`)) return;
      if (isComposing) return;
      const block = closestBlockFromNode(editor, ev.target);
      if (block) setTimeout(() => rescanBlock(block, false, { skipWhileTyping: false }), 30);
    });
    editor.addEventListener('blur', (ev) => {
      const related = ev.relatedTarget;
      if (related instanceof HTMLElement && related.closest(`#${MENU_ID}`)) return;
      hideMenuSoon(120);
    }, true);

    editor.addEventListener('pointerdown', (ev) => {
      const highlight = ev.target instanceof HTMLElement ? ev.target.closest(`.${HIGHLIGHT_CLASS}`) : null;
      if (!highlight) return;
      ev.preventDefault();
      ev.stopPropagation();
      openMenuFor(highlight);
    });

    editor.addEventListener('click', (ev) => {
      const highlight = ev.target instanceof HTMLElement ? ev.target.closest(`.${HIGHLIGHT_CLASS}`) : null;
      if (!highlight) return;
      ev.preventDefault();
      ev.stopPropagation();
      openMenuFor(highlight);
    });

    editor.addEventListener('keydown', (ev) => {
      const highlight = ev.target instanceof HTMLElement ? ev.target.closest(`.${HIGHLIGHT_CLASS}`) : null;
      if (highlight && (ev.key === 'Enter' || ev.key === ' ')) {
        ev.preventDefault();
        openMenuFor(highlight);
      }
      if (ev.key === 'Escape') hideMenu();
    });

    menu.addEventListener('pointerdown', (ev) => {
      markInteractionWindow(250);
      runMenuActionFromEvent(ev);
    });

    menu.addEventListener('mousedown', (ev) => {
      markInteractionWindow(250);
      if (ev.target instanceof HTMLElement && ev.target.closest('[data-autocorretor-action]')) {
        ev.preventDefault();
      }
    });

    menu.addEventListener('click', (ev) => {
      markInteractionWindow(250);
      runMenuActionFromEvent(ev);
    });

    document.addEventListener('pointerdown', (ev) => {
      const target = ev.target;
      if (!(target instanceof HTMLElement)) return;
      if (target.closest(`#${MENU_ID}`) || target.closest(`.${HIGHLIGHT_CLASS}`)) {
        markInteractionWindow();
        return;
      }
      if (!shouldSuppressOutsideClose()) hideMenu();
    }, true);

    document.addEventListener('click', (ev) => {
      const target = ev.target;
      if (!(target instanceof HTMLElement)) return;
      if (target.closest(`#${MENU_ID}`) || target.closest(`.${HIGHLIGHT_CLASS}`)) return;
      hideMenuSoon();
    });

    window.addEventListener('resize', () => {
      if (openedHighlight && !menu.classList.contains('oculto')) positionMenu(menu, openedHighlight);
    });

    return {
      rescanBlock,
      rescanAll() {
        const blocks = editor.querySelectorAll('.roteiro-bloco, p, h1, h2, h3, li, blockquote');
        if (blocks.length) blocks.forEach((block) => rescanBlock(block, false, { skipWhileTyping: true }));
        else rescanBlock(editor, false, { skipWhileTyping: true });
      },
      stripDecorationsFromClone,
      hideMenu,
      getRuleCount() {
        return { termRules: TERM_RULES.length, contextRules: CONTEXT_RULES.length };
      }
    };
  }

  /** Escapehtml. Usada pelo fluxo principal da aplicação. */
  function escapeHtml(text) {
    return String(text || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  window.AutoCorretorSimples = { init, stripDecorationsFromClone };
})();
