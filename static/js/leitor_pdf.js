/** Leitor de PDF preservando páginas originais; renderização local via PyMuPDF. */
(() => {
  'use strict';
  const config = window.GUTENBERG_PDF_READER;
  if (!config) return;
  const $ = (id) => document.getElementById(id);
  const stage = $('pdfStage');
  const image = $('pdfPageImage');
  const loadStatus = $('pdfLoading');
  const error = $('pdfError');
  const pageField = $('pdfPageInput');
  const previous = $('pdfPrev');
  const next = $('pdfNext');
  const zoomOutput = $('pdfZoomValue');
  const sidebars = ['pdfOutline', 'pdfSearchPanel', 'pdfTextPanel'];
  let page = Math.min(config.count, Math.max(1, Number(config.page) || 1));
  let zoom = 1;
  let requestSequence = 0;
  let fitToWidth = true;
  let searchSequence = 0;

  function updateNavigation() {
    pageField.value = String(page);
    previous.disabled = page <= 1;
    next.disabled = page >= config.count;
    zoomOutput.textContent = `${Math.round(zoom * 100)}%`;
    const percent = Math.min(100, Math.round(page / config.count * 100));
    $('pdfProgressFill').style.width = `${percent}%`;
    $('pdfProgress').setAttribute('aria-valuenow', String(percent));
    $('pdfProgressText').textContent = `${percent}%`;
    document.querySelectorAll('.pdf-outline-item').forEach((item) => item.classList.toggle('ativo', Number(item.dataset.page) === page));
    document.title = `${config.strings.page} ${page}/${config.count} · Gutenberg`;
  }

  function render() {
    const seq = ++requestSequence;
    loadStatus.hidden = false;
    error.hidden = true;
    image.hidden = true;
    pageField.value = String(page);
    const viewport = Math.max(300, stage.clientWidth - 60);
    // PDF base de aproximadamente 600–850 pt; ajuste pela largura sem esticar a imagem.
    const scale = Math.min(2.5, Math.max(0.65, zoom * (fitToWidth ? Math.min(1.75, viewport / 720) : 1.4)));
    const src = config.imageUrl.replace('__PAGE__', String(page)) + `?escala=${scale.toFixed(2)}`;
    const nextImage = new Image();
    nextImage.onload = () => {
      if (seq !== requestSequence) return;
      image.src = src;
      image.style.width = fitToWidth ? `${Math.min(viewport * zoom, nextImage.naturalWidth)}px` : `${nextImage.naturalWidth}px`;
      image.alt = `${config.strings.page} ${page}`;
      image.hidden = false;
      loadStatus.hidden = true;
      stage.scrollTo({ top: 0, left: 0 });
      fetch(config.progressUrl, {
        method: 'POST', credentials: 'same-origin', keepalive: true,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ page: page }),
      }).catch(() => {});
    };
    nextImage.onerror = () => {
      if (seq !== requestSequence) return;
      loadStatus.hidden = true;
      error.textContent = config.strings.error;
      error.hidden = false;
    };
    nextImage.src = src;
  }

  function gotoPage(nextPage, pushHistory = true) {
    const target = Math.max(1, Math.min(config.count, Math.trunc(Number(nextPage) || 1)));
    if (target === page && image.src && !image.hidden) { updateNavigation(); return; }
    page = target;
    updateNavigation();
    render();
    if (pushHistory) history.replaceState(null, '', `${location.pathname}?pagina=${page}`);
    if (!$('pdfTextPanel').hidden) loadPageText();
  }

  function changeZoom(factor) {
    zoom = Math.min(2.4, Math.max(0.6, Math.round((zoom * factor) * 10) / 10));
    updateNavigation();
    render();
  }

  function toggleSidebar(id) {
    const sidebar = $(id);
    const shouldOpen = sidebar.hidden;
    sidebars.forEach((sidebarId) => { $(sidebarId).hidden = true; });
    sidebar.hidden = !shouldOpen;
    [['pdfOutlineToggle', 'pdfOutline'], ['pdfSearchToggle', 'pdfSearchPanel'], ['pdfTextToggle', 'pdfTextPanel']].forEach(([btn, side]) => {
      $(btn)?.setAttribute('aria-expanded', String(!$(side).hidden));
    });
    if (shouldOpen && id === 'pdfTextPanel') loadPageText();
    if (shouldOpen && id === 'pdfSearchPanel') $('pdfSearchInput').focus();
    render();
  }

  async function loadPageText() {
    const current = page;
    const element = $('pdfExtractedText');
    element.textContent = config.strings.loading;
    try {
      const response = await fetch(config.textUrl.replace('__PAGE__', String(current)));
      if (!response.ok) throw new Error();
      const data = await response.json();
      if (current === page && !$('pdfTextPanel').hidden) element.textContent = data.texto || config.strings.noText;
    } catch (_) {
      if (current === page) element.textContent = config.strings.error;
    }
  }

  previous.addEventListener('click', () => gotoPage(page - 1));
  next.addEventListener('click', () => gotoPage(page + 1));
  pageField.addEventListener('change', () => gotoPage(pageField.value));
  pageField.addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); gotoPage(pageField.value); pageField.blur(); } });
  $('pdfZoomIn').addEventListener('click', () => changeZoom(1.2));
  $('pdfZoomOut').addEventListener('click', () => changeZoom(1 / 1.2));
  $('pdfFit').addEventListener('click', () => { zoom = 1; fitToWidth = !fitToWidth; $('pdfFit').classList.toggle('ativo', fitToWidth); updateNavigation(); render(); });
  [['pdfOutlineToggle','pdfOutline'], ['pdfSearchToggle','pdfSearchPanel'], ['pdfTextToggle','pdfTextPanel']].forEach(([button, sidebar]) => {
    $(button)?.addEventListener('click', () => toggleSidebar(sidebar));
  });
  document.querySelectorAll('[data-pdf-close]').forEach((button) => button.addEventListener('click', () => toggleSidebar(button.dataset.pdfClose)));
  document.querySelectorAll('.pdf-outline-item').forEach((button) => button.addEventListener('click', () => gotoPage(button.dataset.page)));
  $('pdfSearchForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const term = $('pdfSearchInput').value.trim();
    if (term.length < 2) return;
    const seq = ++searchSequence;
    const container = $('pdfSearchResults');
    container.textContent = config.strings.loading;
    try {
      const response = await fetch(`${config.searchUrl}?q=${encodeURIComponent(term)}`);
      if (!response.ok) throw new Error();
      const data = await response.json();
      if (seq !== searchSequence) return;
      container.replaceChildren();
      if (!data.resultados.length) { container.textContent = config.strings.none; return; }
      data.resultados.forEach((hit) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'pdf-search-hit';
        const heading = document.createElement('strong');
        heading.textContent = `${config.strings.page} ${hit.pagina}`;
        const snippet = document.createElement('span');
        snippet.textContent = hit.trecho;
        button.append(heading, snippet);
        button.addEventListener('click', () => gotoPage(hit.pagina));
        container.append(button);
      });
    } catch (_) { if (seq === searchSequence) container.textContent = config.strings.error; }
  });
  $('pdfCopyText').addEventListener('click', async () => {
    const value = $('pdfExtractedText').textContent || '';
    if (!value || value === config.strings.noText) return;
    try { await navigator.clipboard.writeText(value); $('pdfCopyText').textContent = config.strings.copied; }
    catch (_) { $('pdfExtractedText').focus(); $('pdfExtractedText').setAttribute('aria-label', config.strings.error); }
  });
  document.addEventListener('keydown', (event) => {
    if (['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName) || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === 'ArrowLeft' || event.key === 'PageUp') { event.preventDefault(); gotoPage(page - 1); }
    if (event.key === 'ArrowRight' || event.key === 'PageDown') { event.preventDefault(); gotoPage(page + 1); }
    if (event.key === 'Escape') sidebars.forEach((id) => { if (!$(id).hidden) toggleSidebar(id); });
  });
  let resizeTimer;
  window.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(render, 200); });
  updateNavigation();
  render();
})();
