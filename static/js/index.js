/**
 * Comanda a tela inicial e o formulário de criação de projetos.
 */

/** I18n. Usada pelo fluxo principal da aplicação. */
const i18n = (key, vars = {}) => (window.t ? window.t(key, vars) : key);

const modalProjeto = document.getElementById('modalProjeto');
const abrirModalProjeto = document.getElementById('abrirModalProjeto');
const formProjeto = document.getElementById('formProjeto');
const statusProjeto = document.getElementById('statusProjeto');
const campoTipoProjeto = document.getElementById('campoTipoProjeto');
const grupoTagsProjeto = document.getElementById('grupoTagsProjeto');
const grupoCapaProjeto = document.getElementById('grupoCapaProjeto');
const grupoContatosProjeto = document.getElementById('grupoContatosProjeto');
const grupoInformacoesProjeto = document.getElementById('grupoInformacoesProjeto');

/** Abrirmodal. Usada pelo fluxo principal da aplicação. */
function abrirModal(el){ el?.classList.remove('oculto'); requestAnimationFrame(() => window.validacaoCampos?.refreshModal?.(el)); }
function fecharModal(el){ el?.classList.add('oculto'); }

/** Sanitizespaces. Usada pelo fluxo principal da aplicação. */
function sanitizeSpaces(value){
  return String(value || '').replace(/\s+/g, ' ').trim();
}
/** Isvalidemail. Usada pelo fluxo principal da aplicação. */
function isValidEmail(value){
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}
/** Isvalidphone. Usada pelo fluxo principal da aplicação. */
function isValidPhone(value){
  const compact = String(value || '').replace(/[^\d+]/g, '');
  const digits = compact.replace(/\D/g, '');
  return digits.length >= 10 && digits.length <= 13 && /^\+?[\d]+$/.test(compact);
}
/** Validarformularioprojeto. Usada pelo fluxo principal da aplicação. */
function validarFormularioProjeto(form){
  const tipo = form.querySelector('[name="tipo"]')?.value || 'livro';
  const titulo = sanitizeSpaces(form.querySelector('[name="titulo"]')?.value);
  const descricao = String(form.querySelector('[name="descricao"]')?.value || '').trim();
  const autor = sanitizeSpaces(form.querySelector('[name="autor"]')?.value);
  const tags = String(form.querySelector('[name="tags"]')?.value || '').trim();
  const contatos = sanitizeSpaces(form.querySelector('[name="contatos"]')?.value);
  const info = String(form.querySelector('[name="informacoes_adicionais"]')?.value || '').trim();
  if (!titulo) return i18n('js.project_required');
  if (titulo.length > 70) return i18n('js.project_title_max');
  if (descricao.length > 1000) return i18n('js.project_description_max');
  if (autor.length > 80) return i18n('js.project_author_max');
  if (tipo === 'livro' && tags.length > 180) return i18n('js.project_tags_max');
  if (contatos) {
    if (contatos.length > 70) return i18n('js.project_contact_max');
    if (!isValidEmail(contatos) && !isValidPhone(contatos)) return i18n('js.project_contact_invalid');
  }
  if (tipo === 'roteiro' && info.length > 50) return i18n('js.project_additional_info_max');
  return '';
}
/** Atualizarcampostipoprojeto. Usada pelo fluxo principal da aplicação. */
function atualizarCamposTipoProjeto(){
  const isRoteiro = campoTipoProjeto?.value === 'roteiro';
  grupoTagsProjeto?.classList.toggle('oculto', isRoteiro);
  grupoCapaProjeto?.classList.toggle('oculto', isRoteiro);
  grupoContatosProjeto?.classList.remove('oculto');
  grupoInformacoesProjeto?.classList.toggle('oculto', !isRoteiro);
}
abrirModalProjeto?.addEventListener('click', ()=> { if (campoTipoProjeto) campoTipoProjeto.disabled = false; abrirModal(modalProjeto); atualizarCamposTipoProjeto(); });
campoTipoProjeto?.addEventListener('change', atualizarCamposTipoProjeto);
document.querySelectorAll('[data-fechar-modal="true"]').forEach(el => el.addEventListener('click', (ev)=> { ev.preventDefault(); ev.stopPropagation(); fecharModal(el.closest('.modal')); }));
document.querySelectorAll('[data-modal-card="true"]').forEach(el => el.addEventListener('click', (ev)=> ev.stopPropagation()));
document.addEventListener('keydown', (ev)=> { if (ev.key === 'Escape') document.querySelectorAll('.modal:not(.oculto)').forEach(fecharModal); });

document.querySelectorAll('.btn-excluir-projeto').forEach(btn => btn.addEventListener('click', async ()=> {
  if (!confirm(i18n('js.confirm_delete_project'))) return;
  const r = await fetch(`/projetos/${btn.dataset.slug}/excluir`, {method:'POST'});
  if ((await r.json()).ok) location.reload();
}));

formProjeto?.addEventListener('submit', async (e)=>{
  e.preventDefault();
  const erro = validarFormularioProjeto(formProjeto);
  if (erro) {
    statusProjeto.textContent = erro;
    return;
  }
  statusProjeto.textContent=i18n('js.creating');
  const body = new FormData(formProjeto);
  const url = gutPendenteAtual()?.ativo ? '/api/gut/pendente/criar-e-importar' : '/projetos/criar';
  const r = await fetch(url, {method:'POST', body});
  const d = await r.json();
  if (d.ok) location.href = d.redirect; else statusProjeto.textContent = d.erro || i18n('js.create_error');
});



atualizarCamposTipoProjeto();

const gradeProjetos = document.getElementById('gradeProjetos');
const botoesVisualizacao = [...document.querySelectorAll('[data-modo-visualizacao]')];
const chaveVisualizacao = 'epubmais-index-visualizacao';

/** Aplicarmodovisualizacao. Usada pelo fluxo principal da aplicação. */
function aplicarModoVisualizacao(modo) {
  if (!gradeProjetos) return;
  const modoFinal = modo === 'explorer' ? 'explorer' : 'grid';
  gradeProjetos.dataset.visualizacao = modoFinal;
  botoesVisualizacao.forEach((botao) => {
    const ativo = botao.dataset.modoVisualizacao === modoFinal;
    botao.classList.toggle('ativo', ativo);
    botao.setAttribute('aria-pressed', ativo ? 'true' : 'false');
  });
  try { localStorage.setItem(chaveVisualizacao, modoFinal); } catch (_) {}
}

botoesVisualizacao.forEach((botao) => {
  botao.addEventListener('click', () => aplicarModoVisualizacao(botao.dataset.modoVisualizacao));
});

try {
  aplicarModoVisualizacao(localStorage.getItem(chaveVisualizacao) || 'explorer');
} catch (_) {
  aplicarModoVisualizacao('explorer');
}


const gutPendenteAtual = () => window.GUT_PENDENTE || null;
const modalGutPendente = document.getElementById('modalGutPendente');
const statusGutPendente = document.getElementById('statusGutPendente');

const chaveGutDescartado = 'gutenberg-gut-pendente-descartado';

function tokenGut(contexto){
  if (!contexto?.ativo) return '';
  return String(contexto.token || contexto.caminho || '');
}

function obterGutDescartado(){
  try { return sessionStorage.getItem(chaveGutDescartado) || ''; } catch (_) { return ''; }
}

function marcarGutDescartado(contexto){
  const token = tokenGut(contexto);
  if (!token) return;
  try { sessionStorage.setItem(chaveGutDescartado, token); } catch (_) {}
}

function limparGutDescartado(contexto = null){
  const tokenAtual = tokenGut(contexto || gutPendenteAtual());
  try {
    if (!tokenAtual || sessionStorage.getItem(chaveGutDescartado) === tokenAtual) {
      sessionStorage.removeItem(chaveGutDescartado);
    }
  } catch (_) {}
}

function gutPendenteFoiDescartado(contexto){
  const token = tokenGut(contexto);
  return !!token && obterGutDescartado() === token;
}

function preencherFormularioProjetoComGutPendente(){
  const gutPendente = gutPendenteAtual();
  if (!gutPendente?.ativo || gutPendente?.erro) return;
  const pendenteRecursos = gutPendente.tipo_arquivo === 'recursos';
  if (campoTipoProjeto) {
    campoTipoProjeto.value = pendenteRecursos
      ? (gutPendente.metadados?.tipo || 'livro')
      : (gutPendente.tipo_projeto || 'livro');
    campoTipoProjeto.disabled = !pendenteRecursos;
  }
  atualizarCamposTipoProjeto();
  formProjeto?.querySelector('[name="titulo"]')?.setAttribute('value', gutPendente.metadados?.titulo || '');
  const titulo = formProjeto?.querySelector('[name="titulo"]');
  if (titulo && !titulo.value) titulo.value = gutPendente.metadados?.titulo || '';
  const descricao = formProjeto?.querySelector('[name="descricao"]');
  if (descricao && !descricao.value) descricao.value = gutPendente.metadados?.descricao || '';
  const autor = formProjeto?.querySelector('[name="autor"]');
  if (autor && !autor.value) autor.value = gutPendente.metadados?.autor || '';
  const idioma = formProjeto?.querySelector('[name="idioma"]');
  if (idioma && gutPendente.metadados?.idioma) idioma.value = gutPendente.metadados.idioma;
  const tags = formProjeto?.querySelector('[name="tags"]');
  if (tags && !tags.value) tags.value = (gutPendente.metadados?.tags || []).join(', ');
  const contatos = formProjeto?.querySelector('[name="contatos"]');
  if (contatos && !contatos.value) contatos.value = gutPendente.metadados?.contatos || '';
  const info = formProjeto?.querySelector('[name="informacoes_adicionais"]');
  if (info && !info.value) info.value = gutPendente.metadados?.informacoes_adicionais || '';
}

async function importarGutPendenteParaProjetoExistente(){
  const gutPendente = gutPendenteAtual();
  if (!gutPendente?.ativo) return;
  const slug = document.getElementById('selectProjetoGutPendente')?.value;
  if (!slug) return;
  if (statusGutPendente) statusGutPendente.textContent = i18n('js.importing_gut');
  const r = await fetch('/api/gut/pendente/importar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slug }),
  });
  const d = await r.json().catch(() => ({}));
  if (d.ok) { location.href = d.redirect; return; }
  if (statusGutPendente) statusGutPendente.textContent = d.erro || i18n('js.import_error');
}

document.getElementById('botaoImportarGutPendente')?.addEventListener('click', ()=> {
  limparGutDescartado();
  importarGutPendenteParaProjetoExistente();
});
document.getElementById('botaoCriarProjetoGutPendente')?.addEventListener('click', ()=> {
  limparGutDescartado();
  if (statusGutPendente) statusGutPendente.textContent = '';
  fecharModal(modalGutPendente);
  abrirModal(modalProjeto);
  preencherFormularioProjetoComGutPendente();
});

function aplicarGutPendenteAtual(contexto) {
  if (!contexto?.ativo || contexto?.erro) return;
  window.GUT_PENDENTE = contexto;
  if (statusGutPendente) statusGutPendente.textContent = '';
  if (gutPendenteFoiDescartado(contexto)) {
    fecharModal(modalGutPendente);
    return;
  }
  abrirModal(modalGutPendente);
  preencherFormularioProjetoComGutPendente();
}

window.addEventListener('gutenberg:gut-pendente-atualizado', (event) => {
  const contexto = event?.detail || window.GUT_PENDENTE || null;
  aplicarGutPendenteAtual(contexto);
});

if (gutPendenteAtual()?.ativo && !gutPendenteAtual()?.erro) {
  aplicarGutPendenteAtual(gutPendenteAtual());
}



modalGutPendente?.querySelectorAll('[data-fechar-modal="true"]').forEach((elemento) => {
  elemento.addEventListener('click', () => {
    marcarGutDescartado(gutPendenteAtual());
    fecharModal(modalGutPendente);
  });
});


