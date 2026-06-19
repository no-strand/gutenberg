/**
 * Controla o leitor alternativo baseado em iframe para conteúdos estruturados, como EPUB.
 */

const areaLeitura = document.getElementById('areaLeitura');
const epubFrame = document.getElementById('epubFrame');
const controleTema = document.getElementById('controleTema');
const controleFonte = document.getElementById('controleFonte');
const controleTamanho = document.getElementById('controleTamanho');
const botaoAbrirSumario = document.getElementById('abrirSumario');
const modalSumario = document.getElementById('modalSumario');
const chave = `leitor_pref_${window.LEITOR_CONFIG?.slug || 'biblioteca'}`;
let timeoutPersistencia = null;
let timeoutSalvarPosicao = null;
let restaurouPosicao = false;
let resizeObserverIframe = null;
let mutationObserverIframe = null;
let ultimaPosicaoSalva = null;
let ultimoPercentualSalvo = null;
let enviandoPosicaoAgora = false;
let timeoutRestauracao = null;


const TEMAS_LEITOR = ['light','dark','serpia','dark-blue','terminal-calm','warm-brown','sunset-mode','frost','pastel-pink','code-like'];

/** Normalizartema. Usada pelo fluxo principal da aplicação. */
function normalizarTema(valor) {
  const mapa = {
    'tema-claro': 'light',
    'tema-escuro': 'dark',
    'tema-sepia': 'serpia',
    'claro': 'light',
    'escuro': 'dark',
    'sepia': 'serpia',
    'sépia': 'serpia',
  };
  const tema = mapa[valor] || valor;
  return TEMAS_LEITOR.includes(tema) ? tema : 'light';
}


/** Topoabsolutoarealeitura. Usada pelo fluxo principal da aplicação. */
function topoAbsolutoAreaLeitura() {
  if (!areaLeitura) return 0;
  const rect = areaLeitura.getBoundingClientRect();
  return rect.top + (window.scrollY || window.pageYOffset || 0);
}

/** Rolarviewportparaarealeitura. Usada pelo fluxo principal da aplicação. */
function rolarViewportParaAreaLeitura() {
  const topo = Math.max(0, Math.round(topoAbsolutoAreaLeitura() - 10));
  window.scrollTo({ top: topo, behavior: 'auto' });
}


/** Obterpreferencias. Usada pelo fluxo principal da aplicação. */
function obterPreferencias() {
  return {
    tema: controleTema?.value || 'light',
    fonte: controleFonte?.value || 'fonte-serif',
    tamanho: controleTamanho?.value || '20',
    conforto: false,
    ampliado: true,
  };
}

/** Salvarpreferenciaslocal. Usada pelo fluxo principal da aplicação. */
function salvarPreferenciasLocal() {
  localStorage.setItem(chave, JSON.stringify(obterPreferencias()));
}

/** Persistirpreferenciasnoservidor. Usada pelo fluxo principal da aplicação. */
function persistirPreferenciasNoServidor() {
  const preferencias = obterPreferencias();
  clearTimeout(timeoutPersistencia);
  timeoutPersistencia = setTimeout(() => {
    fetch('/api/configuracoes/leitor', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(preferencias),
    }).catch(() => {});
  }, 180);
}

/** Carregarpreferencias. Usada pelo fluxo principal da aplicação. */
function carregarPreferencias() {
  try {
    const dados = JSON.parse(localStorage.getItem(chave) || '{}');
    if (dados.tema && controleTema) controleTema.value = normalizarTema(dados.tema);
    else if (controleTema) controleTema.value = normalizarTema(controleTema.value);
    if (dados.fonte && controleFonte) controleFonte.value = dados.fonte;
    if (dados.tamanho && controleTamanho) controleTamanho.value = dados.tamanho;
  } catch (_) {}
}

/** Obterdocumentoiframe. Usada pelo fluxo principal da aplicação. */
function obterDocumentoIframe() {
  return epubFrame?.contentDocument || epubFrame?.contentWindow?.document || null;
}

/** Obterjanelaiframe. Usada pelo fluxo principal da aplicação. */
function obterJanelaIframe() {
  return epubFrame?.contentWindow || null;
}

/** Fonteparacss. Usada pelo fluxo principal da aplicação. */
function fonteParaCss(valor) {
  if (valor === 'fonte-sans') return "Inter, Arial, Helvetica, sans-serif";
  if (valor === 'fonte-mono') return "Consolas, 'Courier New', monospace";
  return "Georgia, 'Times New Roman', serif";
}

/** Temaatual. Usada pelo fluxo principal da aplicação. */
function temaAtual() {
  const tema = normalizarTema(controleTema?.value);
  const temas = {
    'light': { fundo: '#ffffff', texto: '#111827' },
    'dark': { fundo: '#111827', texto: '#e5e7eb' },
    'serpia': { fundo: '#f3e7d1', texto: '#4b3725' },
    'dark-blue': { fundo: '#0f1b2d', texto: '#dbeafe' },
    'terminal-calm': { fundo: '#08120c', texto: '#b6f7c0' },
    'warm-brown': { fundo: '#f5eee6', texto: '#4a3427' },
    'sunset-mode': { fundo: '#2a1634', texto: '#fde7f3' },
    'frost': { fundo: '#eef6fb', texto: '#16324f' },
    'pastel-pink': { fundo: '#fff1f6', texto: '#5b2145' },
    'code-like': { fundo: '#16181d', texto: '#e4e7eb' },
  };
  return temas[tema] || temas.light;
}

/** Larguraleitura. Usada pelo fluxo principal da aplicação. */
function larguraLeitura() {
  const larguraBase = Number(window.LEITOR_CONFIG?.overrides?.largura || 860);
  return Math.max(larguraBase + 260, window.innerWidth - 80);
}

/** Montarcssoverride. Usada pelo fluxo principal da aplicação. */
function montarCssOverride() {
  const cfg = window.LEITOR_CONFIG?.overrides || {};
  const tema = temaAtual();
  const tamanhoFonte = Number(controleTamanho?.value || 20);
  const fonte = fonteParaCss(controleFonte?.value);
  const largura = larguraLeitura();
  const padding = 'min(2vw, 18px)';
  const lineHeight = Number(cfg.espacoLinhas || 1.85);
  const espacoParagrafos = Number(cfg.espacoParagrafos || 1.15);
  const indent = Number(cfg.indent || 2);
  const indentMaior = Number(cfg.indentMaior || 3.2);
  const h1 = Number(cfg.h1 || tamanhoFonte + 8);
  const h2 = Number(cfg.h2 || tamanhoFonte + 2);
  const h3 = Number(cfg.h3 || tamanhoFonte);

  return `
    :root {
      color-scheme: light;
      --epubplus-font: ${tamanhoFonte}px;
      --epubplus-line: ${lineHeight};
      --epubplus-indent: ${indent}em;
      --epubplus-indent-maior: ${indentMaior}em;
      --epubplus-gap: ${espacoParagrafos}em;
      --epubplus-width: ${largura}px;
      --epubplus-h1: ${h1}px;
      --epubplus-h2: ${h2}px;
      --epubplus-h3: ${h3}px;
    }
    html, body {
      background: ${tema.fundo} !important;
      color: ${tema.texto} !important;
      margin: 0 auto !important;
      padding: ${padding} !important;
      max-width: var(--epubplus-width) !important;
      box-sizing: border-box !important;
      width: 100% !important;
      font-size: var(--epubplus-font) !important;
      line-height: var(--epubplus-line) !important;
      font-family: ${fonte} !important;
      letter-spacing: normal !important;
      word-break: break-word !important;
      overflow-wrap: anywhere !important;
    }
    body *, p, div, span, li, a, td, th, blockquote, section, article {
      font-family: ${fonte} !important;
      line-height: var(--epubplus-line) !important;
    }
    p, li, blockquote {
      font-size: var(--epubplus-font) !important;
      margin: 0 0 var(--epubplus-gap) !important;
      text-indent: var(--epubplus-indent) !important;
      text-align: justify !important;
      word-break: break-word !important;
      overflow-wrap: anywhere !important;
      hyphens: auto !important;
    }
    h1, h2, h3 {
      font-family: ${fonte} !important;
      line-height: 1.2 !important;
      margin: 0 0 0.7em !important;
    }
    h1 { font-size: var(--epubplus-h1) !important; text-align: center !important; }
    h2 { font-size: var(--epubplus-h2) !important; text-align: left !important; }
    h3 { font-size: var(--epubplus-h3) !important; text-align: left !important; }
    img, svg, video, canvas {
      max-width: 100% !important;
      height: auto !important;
    }
    [class*="recuo-a-direita"] { text-indent: var(--epubplus-indent-maior) !important; }
    [class*="recuo-a-esquerda"] { text-indent: 0 !important; }
  `;
}

/** Ajustaralturaiframe. Usada pelo fluxo principal da aplicação. */
function ajustarAlturaIframe() {
  if (!epubFrame) return 0;
  const doc = obterDocumentoIframe();
  if (!doc) return 0;
  const body = doc.body;
  const docEl = doc.documentElement;
  const altura = Math.max(body?.scrollHeight || 0, body?.offsetHeight || 0, docEl?.scrollHeight || 0, docEl?.offsetHeight || 0, docEl?.clientHeight || 0);
  if (altura > 0) {
    epubFrame.style.height = `${Math.ceil(altura)}px`;
    areaLeitura?.style.setProperty('--epub-frame-height', `${Math.ceil(altura)}px`);
  }
  return altura;
}

/** Observarmudancasnoiframe. Usada pelo fluxo principal da aplicação. */
function observarMudancasNoIframe() {
  const doc = obterDocumentoIframe();
  if (!doc) return;
  resizeObserverIframe?.disconnect?.();
  mutationObserverIframe?.disconnect?.();
  if (window.ResizeObserver) {
    resizeObserverIframe = new ResizeObserver(() => ajustarAlturaIframe());
    if (doc.body) resizeObserverIframe.observe(doc.body);
    if (doc.documentElement) resizeObserverIframe.observe(doc.documentElement);
  }
  if (window.MutationObserver) {
    mutationObserverIframe = new MutationObserver(() => ajustarAlturaIframe());
    mutationObserverIframe.observe(doc.documentElement || doc.body, { childList: true, subtree: true, attributes: true, characterData: false });
  }
  doc.querySelectorAll('img').forEach((img) => {
    if (!img.__epubPlusResizeHook) {
      img.__epubPlusResizeHook = true;
      img.addEventListener('load', ajustarAlturaIframe, { passive: true });
      img.addEventListener('error', ajustarAlturaIframe, { passive: true });
    }
  });
}

/** Aplicarpreferenciasnoiframe. Usada pelo fluxo principal da aplicação. */
function aplicarPreferenciasNoIframe() {
  if (!epubFrame) return;
  areaLeitura?.classList.remove(...TEMAS_LEITOR);
  areaLeitura?.classList.add(normalizarTema(controleTema.value));
  areaLeitura?.classList.remove('modo-confortavel');
  areaLeitura?.classList.add('modo-ampliado');
  rolarViewportParaAreaLeitura();
  salvarPreferenciasLocal();
  persistirPreferenciasNoServidor();

  const doc = obterDocumentoIframe();
  if (!doc) return;
  const body = doc.body;
  if (!body) return;

  let styleEl = doc.getElementById('epubplus-overrides');
  if (!styleEl) {
    styleEl = doc.createElement('style');
    styleEl.id = 'epubplus-overrides';
    doc.head.appendChild(styleEl);
  }
  styleEl.textContent = montarCssOverride();

  const tema = temaAtual();
  doc.documentElement.style.background = tema.fundo;
  body.style.background = tema.fundo;
  body.style.color = tema.texto;
  doc.documentElement.style.overflow = 'hidden';
  body.style.overflow = 'hidden';
  ajustarAlturaIframe();
  observarMudancasNoIframe();
}

/** Abrirsumario. Usada pelo fluxo principal da aplicação. */
function abrirSumario() {
  modalSumario?.classList.remove('oculto');
  modalSumario?.setAttribute('aria-hidden', 'false');
}

/** Fecharsumario. Usada pelo fluxo principal da aplicação. */
function fecharSumario() {
  modalSumario?.classList.add('oculto');
  modalSumario?.setAttribute('aria-hidden', 'true');
}

/** Irparacapitulo. Usada pelo fluxo principal da aplicação. */
function irParaCapitulo(numero) {
  if (!numero) return;
  window.location.href = `/biblioteca/${window.LEITOR_CONFIG.slug}/capitulos/${numero}/ler`;
}

/** Calcularpercentualiframe. Usada pelo fluxo principal da aplicação. */
function calcularPercentualIframe() {
  const viewport = window.innerHeight || document.documentElement.clientHeight || 1;
  const topoAtual = Math.max(0, (window.scrollY || window.pageYOffset || 0) - topoAbsolutoAreaLeitura());
  const total = Math.max(epubFrame?.offsetHeight || areaLeitura?.scrollHeight || 0, viewport);
  return Math.max(0, Math.min(100, ((topoAtual + viewport) / total) * 100));
}

/** Atualizarindicadorprogresso. Usada pelo fluxo principal da aplicação. */
function atualizarIndicadorProgresso(valor) {
  const el = document.getElementById('indicadorProgressoLivro');
  if (el) el.textContent = `${Math.round(Number(valor || 0))}%`;
}

/** Obterposicaoatualleitura. Usada pelo fluxo principal da aplicação. */
function obterPosicaoAtualLeitura() {
  return Math.max(0, Math.round((window.scrollY || window.pageYOffset || 0) - topoAbsolutoAreaLeitura()));
}

/** Enviarposicaoleitura. Usada pelo fluxo principal da aplicação. */
function enviarPosicaoLeitura(imediato = false) {
  const url = window.LEITOR_CONFIG?.salvarPosicaoUrl;
  if (!url || enviandoPosicaoAgora) return;
  const posicao = obterPosicaoAtualLeitura();
  const percentual = calcularPercentualIframe();
  atualizarIndicadorProgresso(percentual);
  if (!imediato && ultimaPosicaoSalva === posicao && ultimoPercentualSalvo === Math.round(percentual)) return;
  ultimaPosicaoSalva = posicao;
  ultimoPercentualSalvo = Math.round(percentual);
  const payload = JSON.stringify({ posicao, percentual });

  if (imediato && navigator.sendBeacon) {
    try {
      const ok = navigator.sendBeacon(url, new Blob([payload], { type: 'application/json' }));
      if (ok) return;
    } catch (_) {}
  }

  enviandoPosicaoAgora = true;
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: payload,
    keepalive: true,
  }).catch(() => {}).finally(() => {
    enviandoPosicaoAgora = false;
  });
}

/** Salvarposicaoleitura. Usada pelo fluxo principal da aplicação. */
function salvarPosicaoLeitura() {
  clearTimeout(timeoutSalvarPosicao);
  timeoutSalvarPosicao = setTimeout(() => enviarPosicaoLeitura(false), 220);
}

/** Conectareventosdoiframe. Usada pelo fluxo principal da aplicação. */
function conectarEventosDoIframe() {
  ajustarAlturaIframe();
  observarMudancasNoIframe();
}

/** Restaurarposicaoleitura. Usada pelo fluxo principal da aplicação. */
function restaurarPosicaoLeitura(tentativa = 0) {
  if (!epubFrame) return;
  const posicao = Number(window.LEITOR_CONFIG?.posicaoInicial ?? epubFrame?.dataset?.posicaoInicial ?? 0) || 0;
  clearTimeout(timeoutRestauracao);
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      const altura = ajustarAlturaIframe();
      rolarViewportParaAreaLeitura();
      const destino = Math.max(0, Math.round(topoAbsolutoAreaLeitura() + posicao));
      window.scrollTo({ top: destino, behavior: 'auto' });
      const atual = Math.max(0, Math.round(window.scrollY || window.pageYOffset || 0));
      const precisaTentarDeNovo = !restaurouPosicao && tentativa < 18 && (altura <= 0 || Math.abs(atual - destino) > 3);
      if (precisaTentarDeNovo) {
        timeoutRestauracao = setTimeout(() => restaurarPosicaoLeitura(tentativa + 1), 140);
        return;
      }
      restaurouPosicao = true;
      ultimaPosicaoSalva = posicao;
      atualizarIndicadorProgresso(calcularPercentualIframe());
    });
  });
}


[controleTema, controleFonte, controleTamanho].forEach((controle) => {
  controle?.addEventListener('input', aplicarPreferenciasNoIframe);
  controle?.addEventListener('change', aplicarPreferenciasNoIframe);
});

botaoAbrirSumario?.addEventListener('click', abrirSumario);
document.querySelectorAll('[data-fechar-sumario="true"]').forEach((el) => {
  el.addEventListener('click', (ev) => {
    ev.preventDefault();
    fecharSumario();
  });
});
document.querySelector('[data-sumario-card="true"]')?.addEventListener('click', (ev) => ev.stopPropagation());
epubFrame?.addEventListener('load', () => {
  restaurouPosicao = false;
  ajustarAlturaIframe();
  rolarViewportParaAreaLeitura();
  aplicarPreferenciasNoIframe();
  conectarEventosDoIframe();
  restaurarPosicaoLeitura();
  atualizarIndicadorProgresso(window.LEITOR_CONFIG?.progressoInicial || 0);
});

window.addEventListener('scroll', salvarPosicaoLeitura, { passive: true });
window.addEventListener('scroll', () => atualizarIndicadorProgresso(calcularPercentualIframe()), { passive: true });
window.addEventListener('resize', ajustarAlturaIframe, { passive: true });
window.addEventListener('beforeunload', () => enviarPosicaoLeitura(true));
window.addEventListener('pagehide', () => enviarPosicaoLeitura(true));

document.addEventListener('keydown', (evento) => {
  if (evento.target.matches('input, textarea, select')) return;
  if ((evento.key === 'ArrowLeft' || evento.key === '<') && window.LEITOR_CONFIG?.anterior) {
    evento.preventDefault();
    irParaCapitulo(window.LEITOR_CONFIG.anterior);
    return;
  }
  if ((evento.key === 'ArrowRight' || evento.key === '>') && window.LEITOR_CONFIG?.proximo) {
    evento.preventDefault();
    irParaCapitulo(window.LEITOR_CONFIG.proximo);
    return;
  }
  if (evento.key === 'ArrowUp') {
    evento.preventDefault();
    window.scrollBy({ top: -110, behavior: 'smooth' });
    return;
  }
  if (evento.key === 'ArrowDown') {
    evento.preventDefault();
    window.scrollBy({ top: 110, behavior: 'smooth' });
    return;
  }
  if (evento.key === 'Escape') {
    if (modalSumario && !modalSumario.classList.contains('oculto')) {
      evento.preventDefault();
      fecharSumario();
      return;
    }
    if (window.LEITOR_CONFIG?.voltarUrl) {
      evento.preventDefault();
      enviarPosicaoLeitura(true);
      window.location.href = window.LEITOR_CONFIG.voltarUrl;
    }
    return;
  }
  if ((evento.key.toLowerCase() === 's') && !evento.ctrlKey && !evento.altKey && !evento.metaKey) {
    abrirSumario();
  }
});

/** Sincronizarleitoraltcomlayout. Usada pelo fluxo principal da aplicação. */
function sincronizarLeitorAltComLayout() {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      rolarViewportParaAreaLeitura();
      aplicarPreferenciasNoIframe();
      conectarEventosDoIframe();
      restaurouPosicao = false;
      restaurarPosicaoLeitura();
      atualizarIndicadorProgresso(window.LEITOR_CONFIG?.progressoInicial || 0);
    });
  });
}

window.addEventListener('load', sincronizarLeitorAltComLayout);
window.addEventListener('app:skeleton-hidden', sincronizarLeitorAltComLayout);

carregarPreferencias();
sincronizarLeitorAltComLayout();
