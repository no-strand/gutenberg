/**
 * Lógica da página da biblioteca: filtros, busca, coleções e estados visuais.
 */

/** I18n. Usada pelo fluxo principal da aplicação. */
const i18n = (key, vars = {}) => (window.t ? window.t(key, vars) : key);


const inputEpubs = document.getElementById('inputEpubs');
const abrirSeletorEpub = document.getElementById('abrirSeletorEpub');
const statusBiblioteca = document.getElementById('statusBiblioteca');
const cards = [...document.querySelectorAll('.card-livro')];
const campoBusca = document.getElementById('campoBuscaBiblioteca');
const botoesFiltro = [...document.querySelectorAll('.toggle-filtro')];
const estadoSemResultados = document.getElementById('estadoSemResultados');
const modalColecoes = document.getElementById('modalColecoes');
const abrirColecoes = document.getElementById('abrirColecoes');
const botoesColecao = [...document.querySelectorAll('[data-colecao-filtro]')];
const overlayProcessandoBiblioteca = document.getElementById('overlayProcessandoBiblioteca');
const mensagemOverlayBiblioteca = document.getElementById('mensagemOverlayBiblioteca');

let filtroAtual = 'todos';
let colecaoAtual = '';


/** Atualiza o texto de status quando esse elemento existir na página. */
function atualizarStatusBiblioteca(mensagem) {
  if (statusBiblioteca) statusBiblioteca.textContent = mensagem;
}


/** Definirprocessamentobiblioteca. Usada pelo fluxo principal da aplicação. */
function definirProcessamentoBiblioteca(ativo, mensagem = i18n('js.import_preparing')) {
  document.body.classList.toggle('biblioteca-processando', !!ativo);
  overlayProcessandoBiblioteca?.classList.toggle('oculto', !ativo);
  overlayProcessandoBiblioteca?.setAttribute('aria-hidden', ativo ? 'false' : 'true');
  if (mensagemOverlayBiblioteca) mensagemOverlayBiblioteca.textContent = mensagem;
}


/** Abrirmodalcolecoes. Usada pelo fluxo principal da aplicação. */
function abrirModalColecoes() {
  modalColecoes?.classList.remove('oculto');
  modalColecoes?.setAttribute('aria-hidden', 'false');
}

/** Fecharmodalcolecoes. Usada pelo fluxo principal da aplicação. */
function fecharModalColecoes() {
  modalColecoes?.classList.add('oculto');
  modalColecoes?.setAttribute('aria-hidden', 'true');
}

/** Correspondefiltro. Usada pelo fluxo principal da aplicação. */
function correspondeFiltro(card) {
  const estado = card.dataset.estado || 'nao_iniciado';
  if (filtroAtual === 'todos') return true;
  if (filtroAtual === 'lidos') return estado === 'lido';
  return estado === 'lendo';
}

/** Correspondebusca. Usada pelo fluxo principal da aplicação. */
function correspondeBusca(card) {
  const termo = (campoBusca?.value || '').trim().toLowerCase();
  if (!termo) return true;
  return (card.dataset.busca || '').includes(termo);
}

/** Correspondecolecao. Usada pelo fluxo principal da aplicação. */
function correspondeColecao(card) {
  if (!colecaoAtual) return true;
  return (card.dataset.colecao || '') === colecaoAtual;
}

/** Atualizarestadovazio. Usada pelo fluxo principal da aplicação. */
function atualizarEstadoVazio(visiveis) {
  if (!estadoSemResultados) return;
  estadoSemResultados.classList.toggle('oculto', visiveis > 0);
}

/** Aplicarfiltros. Usada pelo fluxo principal da aplicação. */
function aplicarFiltros() {
  let visiveis = 0;
  cards.forEach((card) => {
    const mostrar = correspondeFiltro(card) && correspondeBusca(card) && correspondeColecao(card);
    card.classList.toggle('oculto', !mostrar);
    if (mostrar) visiveis += 1;
  });
  atualizarEstadoVazio(visiveis);
}

abrirSeletorEpub?.addEventListener('click', () => inputEpubs?.click());
abrirColecoes?.addEventListener('click', abrirModalColecoes);
document.querySelectorAll('[data-fechar-colecoes="true"]').forEach((el) => {
  el.addEventListener('click', (ev) => {
    ev.preventDefault();
    fecharModalColecoes();
  });
});
document.addEventListener('keydown', (ev) => {
  if (ev.key === 'Escape' && modalColecoes && !modalColecoes.classList.contains('oculto')) fecharModalColecoes();
});

botoesFiltro.forEach((botao) => {
  botao.addEventListener('click', () => {
    filtroAtual = botao.dataset.filtro || 'todos';
    botoesFiltro.forEach((item) => item.classList.toggle('ativo', item === botao));
    aplicarFiltros();
  });
});

botoesColecao.forEach((botao) => {
  botao.addEventListener('click', () => {
    colecaoAtual = botao.dataset.colecaoFiltro || '';
    botoesColecao.forEach((item) => item.classList.toggle('ativo', item === botao));
    fecharModalColecoes();
    aplicarFiltros();
  });
});

campoBusca?.addEventListener('input', aplicarFiltros);

const modalModoPdf = document.getElementById('modalModoPdf');
const confirmarModoPdf = document.getElementById('confirmarModoPdf');
let arquivosPendentesPdf = [];
let importandoBiblioteca = false;

function fecharEscolhaPdf() {
  modalModoPdf?.classList.add('oculto');
  modalModoPdf?.setAttribute('aria-hidden', 'true');
  arquivosPendentesPdf = [];
  if (inputEpubs) inputEpubs.value = '';
  abrirSeletorEpub?.focus();
}

function abrirEscolhaPdf(arquivos) {
  arquivosPendentesPdf = arquivos;
  modalModoPdf?.classList.remove('oculto');
  modalModoPdf?.setAttribute('aria-hidden', 'false');
  modalModoPdf?.querySelector('input[value="nativo"]')?.focus();
}

async function importarArquivosBiblioteca(arquivos, modoPdf = 'epub') {
  if (!arquivos.length || importandoBiblioteca) return;
  importandoBiblioteca = true;
  const possuiPdf = arquivos.some((arquivo) => (arquivo.name || '').toLowerCase().endsWith('.pdf'));
  const mensagemProgresso = arquivos.length > 1 ? i18n('js.adding_books', {count: arquivos.length}) : i18n('js.adding_book');
  atualizarStatusBiblioteca(mensagemProgresso);
  definirProcessamentoBiblioteca(true, possuiPdf && modoPdf === 'epub' ? i18n('js.import_pdf_wait') : (arquivos.length > 1 ? i18n('js.import_many_wait', {count: arquivos.length}) : i18n('js.import_one_wait')));
  const body = new FormData();
  body.append('modo_pdf', modoPdf);
  arquivos.forEach((arquivo) => body.append('epubs', arquivo));
  try {
    const resposta = await fetch('/biblioteca/adicionar', { method: 'POST', body });
    const dados = await resposta.json();
    if (!resposta.ok || !dados.ok) {
      atualizarStatusBiblioteca(dados.erro || i18n('js.add_books_error'));
      return;
    }
    const totalAdicionados = Array.isArray(dados.adicionados) ? dados.adicionados.length : 0;
    atualizarStatusBiblioteca(i18n('js.books_added_success', { total: totalAdicionados }));
    definirProcessamentoBiblioteca(true, i18n('js.import_success_reloading'));
    window.location.reload();
  } catch (_) {
    atualizarStatusBiblioteca(i18n('js.upload_book_error'));
  } finally {
    importandoBiblioteca = false;
    definirProcessamentoBiblioteca(false);
    if (inputEpubs) inputEpubs.value = '';
  }
}

inputEpubs?.addEventListener('change', () => {
  if (importandoBiblioteca) return;
  const arquivos = [...(inputEpubs.files || [])];
  if (!arquivos.length) return;
  if (arquivos.some((arquivo) => (arquivo.name || '').toLowerCase().endsWith('.pdf'))) {
    abrirEscolhaPdf(arquivos);
    return;
  }
  importarArquivosBiblioteca(arquivos);
});

confirmarModoPdf?.addEventListener('click', () => {
  const arquivos = [...arquivosPendentesPdf];
  const modo = modalModoPdf?.querySelector('input[name="modoPdf"]:checked')?.value || 'nativo';
  fecharEscolhaPdf();
  importarArquivosBiblioteca(arquivos, modo);
});

document.querySelectorAll('[data-cancelar-pdf="true"]').forEach((elemento) => {
  elemento.addEventListener('click', fecharEscolhaPdf);
});
document.addEventListener('keydown', (evento) => {
  if (evento.key === 'Escape' && modalModoPdf && !modalModoPdf.classList.contains('oculto')) {
    evento.preventDefault();
    fecharEscolhaPdf();
  }
});

document.querySelectorAll('.btn-excluir-livro').forEach((botao) => {
  botao.addEventListener('click', async (evento) => {
    evento.preventDefault();
    evento.stopPropagation();
    if (!confirm(window.t('js.confirm_delete_library_book'))) return;
    const resposta = await fetch(`/biblioteca/${botao.dataset.slug}/excluir`, { method: 'POST' });
    const dados = await resposta.json();
    if (dados.ok) window.location.reload();
  });
});

document.querySelectorAll('.botao-status-lido').forEach((botao) => {
  botao.addEventListener('click', async (evento) => {
    evento.preventDefault();
    evento.stopPropagation();
    const slug = botao.dataset.slug;
    const proximo = !(botao.dataset.lido === 'true');
    const resposta = await fetch(`/api/biblioteca/${slug}/marcar-lido`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lido: proximo }),
    });
    const dados = await resposta.json();
    if (!dados.ok) return;
    botao.dataset.lido = String(proximo);
    botao.classList.toggle('ativo', proximo);
    const card = botao.closest('.card-livro');
    const chip = card?.querySelector('.chip-progresso');
    if (chip && typeof dados.progresso_percentual !== 'undefined') chip.textContent = `${Math.round(Number(dados.progresso_percentual || 0))}%`;
    if (card) {
      card.dataset.foiLido = String(!!dados.foi_lido);
      card.dataset.estado = dados.foi_lido ? 'lido' : ((Number(dados.progresso_percentual || 0) > 0) ? 'lendo' : 'nao_iniciado');
      aplicarFiltros();
    }
  });
});

aplicarFiltros();
