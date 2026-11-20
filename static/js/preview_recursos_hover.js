/** Prévia flutuante compartilhada para imagens e descrições dos recursos do projeto. */
(function () {
  'use strict';

  let preview = null;
  let activeTarget = null;
  let activeItem = null;
  let positionFrame = 0;
  let hideTimer = 0;
  let activeInteractive = false;

  function cancelScheduledHide() {
    if (hideTimer) window.clearTimeout(hideTimer);
    hideTimer = 0;
  }

  function scheduleHide() {
    cancelScheduledHide();
    hideTimer = window.setTimeout(() => {
      hideTimer = 0;
      hide();
    }, 180);
  }

  function normalizeItem(value = {}, options = {}) {
    const item = value && typeof value === 'object' ? value : { description: value };
    return {
      name: String(options.name ?? item.nome ?? item.name ?? item.label ?? item.titulo ?? '').trim(),
      type: String(options.type ?? item.tipo ?? item.type ?? '').trim(),
      description: String(options.description ?? item.descricao ?? item.description ?? item.anotacao ?? item.notas ?? item.citacao ?? item.texto ?? item.text ?? '').trim(),
      image: String(options.image ?? item.imagem ?? item.image ?? '').trim(),
      hint: String(options.hint ?? item.hint ?? '').trim(),
    };
  }

  function ensurePreview() {
    if (preview) return preview;
    preview = document.createElement('aside');
    preview.className = 'gutenberg-resource-preview';
    preview.setAttribute('role', 'tooltip');
    preview.setAttribute('aria-hidden', 'true');
    preview.addEventListener('mouseenter', () => {
      if (activeInteractive) cancelScheduledHide();
    });
    preview.addEventListener('mouseleave', () => {
      if (activeInteractive) hide();
    });
    document.body.appendChild(preview);
    return preview;
  }

  function cleanDescription(value) {
    return String(value || '')
      .replace(/<\s*br\s*\/?>/gi, '\n')
      .replace(/<\s*\/\s*(p|div|li|h[1-6])\s*>/gi, '\n')
      .replace(/<[^>]*>/g, '')
      .replace(/&nbsp;/gi, ' ')
      .replace(/&amp;/gi, '&')
      .replace(/&lt;/gi, '<')
      .replace(/&gt;/gi, '>')
      .replace(/&quot;/gi, '"')
      .replace(/&#39;|&apos;/gi, "'")
      .replace(/[ \t]+\n/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  }

  function render(item) {
    const tip = ensurePreview();
    tip.replaceChildren();

    if (item.name || item.type) {
      const header = document.createElement('div');
      header.className = 'gutenberg-resource-preview-header';
      if (item.name) {
        const name = document.createElement('strong');
        name.className = 'gutenberg-resource-preview-name';
        name.textContent = item.name;
        header.appendChild(name);
      }
      if (item.type) {
        const type = document.createElement('span');
        type.className = 'gutenberg-resource-preview-type';
        type.textContent = item.type;
        header.appendChild(type);
      }
      tip.appendChild(header);
    }

    if (item.image) {
      const imageWrap = document.createElement('div');
      imageWrap.className = 'gutenberg-resource-preview-image-wrap';
      const image = document.createElement('img');
      image.className = 'gutenberg-resource-preview-image';
      image.alt = item.name ? `Imagem de referência de ${item.name}` : 'Imagem de referência';
      image.src = item.image;
      image.addEventListener('error', () => {
        imageWrap.remove();
        requestAnimationFrame(positionActivePreview);
      }, { once: true });
      image.addEventListener('load', () => requestAnimationFrame(positionActivePreview), { once: true });
      imageWrap.appendChild(image);
      tip.appendChild(imageWrap);
    }

    const description = cleanDescription(item.description);
    if (description) {
      const text = document.createElement('p');
      text.className = 'gutenberg-resource-preview-description';
      text.textContent = description;
      tip.appendChild(text);
    } else if (!item.image) {
      const empty = document.createElement('p');
      empty.className = 'gutenberg-resource-preview-description is-empty';
      empty.textContent = 'Sem descrição cadastrada.';
      tip.appendChild(empty);
    }

    if (item.hint) {
      const hint = document.createElement('span');
      hint.className = 'gutenberg-resource-preview-hint';
      hint.textContent = item.hint;
      tip.appendChild(hint);
    }
  }

  function setPosition(rect, point = null) {
    const tip = ensurePreview();
    const margin = 12;
    const gap = 12;
    const maxWidth = Math.min(320, Math.max(220, window.innerWidth - margin * 2));
    tip.style.width = `${maxWidth}px`;
    tip.style.maxWidth = `calc(100vw - ${margin * 2}px)`;

    const bounds = tip.getBoundingClientRect();
    const width = bounds.width || maxWidth;
    const height = bounds.height || 180;
    const anchor = rect || { left: point?.x || 0, right: point?.x || 0, top: point?.y || 0, bottom: point?.y || 0 };

    let left = anchor.right + gap;
    if (left + width > window.innerWidth - margin) left = anchor.left - width - gap;
    if (left < margin) left = Math.max(margin, Math.min(window.innerWidth - width - margin, anchor.left));

    let top = rect ? anchor.top : (point?.y || 0) + gap;
    if (top + height > window.innerHeight - margin) top = window.innerHeight - height - margin;
    if (top < margin) top = margin;

    tip.style.left = `${Math.round(left)}px`;
    tip.style.top = `${Math.round(top)}px`;
  }

  function positionActivePreview() {
    positionFrame = 0;
    if (!activeTarget || !preview || !preview.classList.contains('is-visible')) return;
    if (activeTarget instanceof Element) {
      const rect = activeTarget.getBoundingClientRect();
      if (!rect.width && !rect.height) return hide();
      setPosition(rect);
    } else if (activeTarget && typeof activeTarget === 'object') {
      setPosition(null, activeTarget);
    }
  }

  function schedulePosition() {
    if (positionFrame) return;
    positionFrame = requestAnimationFrame(positionActivePreview);
  }

  function activate(target, value, options = {}, interactive = false) {
    cancelScheduledHide();
    activeInteractive = interactive;
    const nextItem = normalizeItem(value, options);
    const unchanged = activeItem && activeItem.name === nextItem.name
      && activeItem.type === nextItem.type
      && activeItem.description === nextItem.description
      && activeItem.image === nextItem.image
      && activeItem.hint === nextItem.hint;
    activeTarget = target;
    if (!unchanged || !preview?.classList.contains('is-visible')) {
      activeItem = nextItem;
      render(activeItem);
    }
    const tip = ensurePreview();
    tip.classList.toggle('is-interactive', activeInteractive);
    tip.classList.add('is-visible');
    tip.setAttribute('aria-hidden', 'false');
    schedulePosition();
  }

  function show(target, value, options = {}) {
    activate(target, value, options, true);
  }

  function showAtPoint(value, x, y, options = {}) {
    activate({ x: Number(x) || 0, y: Number(y) || 0 }, value, options, false);
  }

  function hide() {
    cancelScheduledHide();
    activeInteractive = false;
    if (positionFrame) cancelAnimationFrame(positionFrame);
    positionFrame = 0;
    activeTarget = null;
    activeItem = null;
    if (!preview) return;
    preview.classList.remove('is-visible', 'is-interactive');
    preview.setAttribute('aria-hidden', 'true');
    preview.replaceChildren();
  }

  function bind(target, value, options = {}) {
    if (!(target instanceof Element)) return target;
    const item = normalizeItem(value, options);
    target.addEventListener('mouseenter', () => {
      cancelScheduledHide();
      show(target, item);
    });
    target.addEventListener('mousemove', schedulePosition);
    target.addEventListener('mouseleave', () => {
      if (activeInteractive && activeTarget === target) scheduleHide();
      else hide();
    });
    target.addEventListener('focusin', () => {
      cancelScheduledHide();
      show(target, item);
    });
    target.addEventListener('focusout', () => {
      if (activeInteractive && activeTarget === target) scheduleHide();
      else hide();
    });
    return target;
  }

  window.GutenbergResourcePreview = { bind, show, showAtPoint, hide, normalizeItem };
})();
