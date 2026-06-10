/**
 * Gerencia o leitor padrão de capítulos com preferências, progresso e navegação.
 * Créditos do projeto: Nostrand.
 */

const areaLeitura = document.getElementById('areaLeitura');
const controleTema = document.getElementById('controleTema');
const controleFonte = document.getElementById('controleFonte');
const controleTamanho = document.getElementById('controleTamanho');
const botaoAbrirSumario = document.getElementById('abrirSumario');
const modalSumario = document.getElementById('modalSumario');
const chave = `leitor_pref_${window.LEITOR_CONFIG?.slug || 'global'}`;

let timeoutPersistencia = null;
let timeoutSalvarPosicao = null;
let restaurouPosicao = false;
let ultimaPosicaoSalva = null;
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
  const topo = Math.max(0, Math.round(topoAbsolutoAreaLeitura() - 8));
  window.scrollTo({ top: topo, behavior: 'auto' });
}

/** Normalizarconteudoleitura. Usada pelo fluxo principal da aplicação. */
function normalizarConteudoLeitura() {
  if (!areaLeitura) return;
  if (!areaLeitura.innerHTML.trim()) {
    areaLeitura.innerHTML = '<p><br></p>';
    return;
  }
  const possuiBloco = areaLeitura.querySelector('p,h1,h2,h3,ul,ol,blockquote');
  if (!possuiBloco) {
    areaLeitura.innerHTML = `<p>${areaLeitura.innerHTML}</p>`;
  }
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
function salvarPreferenciasLocal(){
  localStorage.setItem(chave, JSON.stringify(obterPreferencias()));
}

/** Persistirpreferenciasnoservidor. Usada pelo fluxo principal da aplicação. */
function persistirPreferenciasNoServidor() {
  const preferencias = obterPreferencias();
  clearTimeout(timeoutPersistencia);
  timeoutPersistencia = setTimeout(() => {
    fetch('/api/configuracoes/leitor', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(preferencias),
    }).catch(() => {});
  }, 180);
}

/** Carregarpreferencias. Usada pelo fluxo principal da aplicação. */
function carregarPreferencias(){
  try {
    const dados = JSON.parse(localStorage.getItem(chave) || '{}');
    if (dados.tema && controleTema) controleTema.value = normalizarTema(dados.tema);
    else if (controleTema) controleTema.value = normalizarTema(controleTema.value);
    if (dados.fonte && controleFonte) controleFonte.value = dados.fonte;
    if (dados.tamanho && controleTamanho) controleTamanho.value = dados.tamanho;
  } catch (_) {}
}

/** Aplicarpreferencias. Usada pelo fluxo principal da aplicação. */
function aplicarPreferencias(){
  if (!areaLeitura) return;
  areaLeitura.classList.remove(...TEMAS_LEITOR);
  areaLeitura.classList.add(normalizarTema(controleTema.value));
  areaLeitura.classList.remove('fonte-serif','fonte-sans','fonte-mono');
  areaLeitura.classList.add(controleFonte.value);
  areaLeitura.style.fontSize = `${controleTamanho.value}px`;
  areaLeitura.classList.remove('modo-confortavel');
  areaLeitura.classList.add('modo-ampliado');
  salvarPreferenciasLocal();
  persistirPreferenciasNoServidor();
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

/** Calcularpercentualleitura. Usada pelo fluxo principal da aplicação. */
function calcularPercentualLeitura() {
  const topoAtual = Math.max(0, (window.scrollY || window.pageYOffset || 0) - topoAbsolutoAreaLeitura());
  const viewport = window.innerHeight || document.documentElement.clientHeight || 1;
  const total = Math.max(areaLeitura?.scrollHeight || 0, viewport);
  return Math.max(0, Math.min(100, ((topoAtual + viewport) / total) * 100));
}

/** Atualizarindicadorprogresso. Usada pelo fluxo principal da aplicação. */
function atualizarIndicadorProgresso() {
  const el = document.getElementById('indicadorProgressoTexto');
  if (el) el.textContent = `${Math.round(calcularPercentualLeitura())}%`;
}

/** Obterposicaoatualleitura. Usada pelo fluxo principal da aplicação. */
function obterPosicaoAtualLeitura() {
  return Math.max(0, Math.round((window.scrollY || window.pageYOffset || 0) - topoAbsolutoAreaLeitura()));
}

/** Enviarposicaoleitura. Usada pelo fluxo principal da aplicação. */
function enviarPosicaoLeitura(imediato = false) {
  const url = window.LEITOR_CONFIG?.salvarPosicaoUrl;
  atualizarIndicadorProgresso();
  if (!url || enviandoPosicaoAgora) return;
  const posicao = obterPosicaoAtualLeitura();
  if (!imediato && ultimaPosicaoSalva === posicao) return;
  ultimaPosicaoSalva = posicao;
  const payload = JSON.stringify({ posicao });

  if (imediato && navigator.sendBeacon) {
    try {
      const ok = navigator.sendBeacon(url, new Blob([payload], { type: 'application/json' }));
      if (ok) return;
    } catch (_) {}
  }

  enviandoPosicaoAgora = true;
  fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
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

/** Restaurarposicaoleitura. Usada pelo fluxo principal da aplicação. */
function restaurarPosicaoLeitura(tentativa = 0) {
  const posicao = Number(window.LEITOR_CONFIG?.posicaoInicial ?? areaLeitura?.dataset?.posicaoInicial ?? 0) || 0;
  clearTimeout(timeoutRestauracao);
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      rolarViewportParaAreaLeitura();
      const destino = Math.max(0, Math.round(topoAbsolutoAreaLeitura() + posicao));
      window.scrollTo({ top: destino, behavior: 'auto' });
      const atual = Math.max(0, Math.round(window.scrollY || window.pageYOffset || 0));
      const precisaTentarDeNovo = !restaurouPosicao && tentativa < 12 && Math.abs(atual - destino) > 3;
      if (precisaTentarDeNovo) {
        timeoutRestauracao = setTimeout(() => restaurarPosicaoLeitura(tentativa + 1), 120);
        return;
      }
      restaurouPosicao = true;
      ultimaPosicaoSalva = posicao;
      atualizarIndicadorProgresso();
    });
  });
}

[controleTema, controleFonte, controleTamanho].forEach((c) => {
  c?.addEventListener('input', aplicarPreferencias);
  c?.addEventListener('change', aplicarPreferencias);
});

botaoAbrirSumario?.addEventListener('click', abrirSumario);
document.querySelectorAll('[data-fechar-sumario="true"]').forEach((el) => {
  el.addEventListener('click', (ev) => {
    ev.preventDefault();
    fecharSumario();
  });
});
document.querySelector('[data-sumario-card="true"]')?.addEventListener('click', (ev) => ev.stopPropagation());

/** Irparacapitulo. Usada pelo fluxo principal da aplicação. */
function irParaCapitulo(numero) {
  if (!numero) return;
  window.location.href = `/projetos/${window.LEITOR_CONFIG.slug}/capitulos/${numero}/ler`;
}

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

/** Sincronizarleitorcomlayout. Usada pelo fluxo principal da aplicação. */
function sincronizarLeitorComLayout() {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      rolarViewportParaAreaLeitura();
      restaurouPosicao = false;
      restaurarPosicaoLeitura();
      atualizarIndicadorProgresso();
    });
  });
}

window.addEventListener('scroll', salvarPosicaoLeitura, { passive: true });
window.addEventListener('scroll', atualizarIndicadorProgresso, { passive: true });
window.addEventListener('beforeunload', () => enviarPosicaoLeitura(true));
window.addEventListener('pagehide', () => enviarPosicaoLeitura(true));
window.addEventListener('load', sincronizarLeitorComLayout);
window.addEventListener('app:skeleton-hidden', sincronizarLeitorComLayout);

normalizarConteudoLeitura();
carregarPreferencias();
aplicarPreferencias();
sincronizarLeitorComLayout();
