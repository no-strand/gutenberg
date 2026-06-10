/**
 * Controla formulários, catálogo e vínculos do fluxo de roteiros.
 * Créditos do projeto: Nostrand.
 */

/** I18n. Usada pelo fluxo principal da aplicação. */
const i18n = (key, vars = {}) => (window.t ? window.t(key, vars) : key);

const modalRoteiro = document.getElementById('modalRoteiro');
const modalExportacao = document.getElementById('modalExportacao');
const modalEditarProjeto = document.getElementById('modalEditarProjeto');
const modalSalvarRoteiroGut = document.getElementById('modalSalvarRoteiroGut');
const modalImportarRoteirosGut = document.getElementById('modalImportarRoteirosGut');
const modalInfoRoteiro = document.getElementById('modalInfoRoteiro');
const modalVinculosRoteiro = document.getElementById('modalVinculosRoteiro');
const formEditarProjeto = document.getElementById('formEditarProjeto');
const formRoteiro = document.getElementById('formRoteiro');
const formExportacao = document.getElementById('formExportacao');
const formInfoRoteiro = document.getElementById('formInfoRoteiro');

/** Atualizarcheckboxcopyrightportipo. Usada pelo fluxo principal da aplicação. */
function atualizarCheckboxCopyrightPorTipo(selectEl, checkboxEl){
  if (!selectEl || !checkboxEl) return;
  if (!checkboxEl.dataset.userTouched) {
    checkboxEl.checked = selectEl.value !== 'spec_script';
  }
}

const formVinculosRoteiro = document.getElementById('formVinculosRoteiro');
const formSalvarRoteiroGut = document.getElementById('formSalvarRoteiroGut');
const selectFormatoExportacao = document.getElementById('selectFormatoExportacao');
const grupoTipoDocumentoExportacao = document.getElementById('grupoTipoDocumentoExportacao');

/** Abrirmodal. Usada pelo fluxo principal da aplicação. */
function abrirModal(el){ el?.classList.remove('oculto'); requestAnimationFrame(() => window.validacaoCampos?.refreshModal?.(el)); }
function fecharModal(el){ el?.classList.add('oculto'); }
/** Escapehtml. Usada pelo fluxo principal da aplicação. */
function escapeHtml(valor){
  return String(valor || '').replace(/[&<>"]/g, ch => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;' }[ch]));
}
/** Upperinputvalue. Usada pelo fluxo principal da aplicação. */
function upperInputValue(input){
  if (!input) return;
  const start = input.selectionStart;
  const end = input.selectionEnd;
  const upper = String(input.value || '').toUpperCase();
  if (input.value !== upper) {
    input.value = upper;
    if (typeof start === 'number' && typeof end === 'number') input.setSelectionRange(start, end);
  }
}
/** Applyuppercaseinputs. Usada pelo fluxo principal da aplicação. */
function applyUppercaseInputs(root = document){
  root.querySelectorAll('input[data-uppercase="true"]').forEach((input) => {
    upperInputValue(input);
    if (input.dataset.uppercaseBound === 'true') return;
    input.dataset.uppercaseBound = 'true';
    input.addEventListener('input', () => upperInputValue(input));
    input.addEventListener('blur', () => upperInputValue(input));
  });
}

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
/** Validatenumericprefix. Usada pelo fluxo principal da aplicação. */
function validateNumericPrefix(value){
  const prefixo = String(value || '').trim();
  return /^0{1,4}$/.test(prefixo);
}
/** Validarformularioprojetoroteiro. Usada pelo fluxo principal da aplicação. */
function validarFormularioProjetoRoteiro(form){
  const titulo = sanitizeSpaces(form.querySelector('[name="titulo"]')?.value);
  const descricao = String(form.querySelector('[name="descricao"]')?.value || '').trim();
  const autor = sanitizeSpaces(form.querySelector('[name="autor"]')?.value);
  const contatos = sanitizeSpaces(form.querySelector('[name="contatos"]')?.value);
  const info = String(form.querySelector('[name="informacoes_adicionais"]')?.value || '').trim();
  if (!titulo) return i18n('js.project_required');
  if (titulo.length > 70) return i18n('js.project_title_max');
  if (descricao.length > 1000) return i18n('js.project_description_max');
  if (autor.length > 80) return i18n('js.project_author_max');
  if (contatos) {
    if (contatos.length > 70) return i18n('js.project_contact_max');
    if (!isValidEmail(contatos) && !isValidPhone(contatos)) return i18n('js.project_contact_invalid');
  }
  if (info.length > 50) return i18n('js.project_additional_info_max');
  return '';
}
/** Validarformularioroteiro. Usada pelo fluxo principal da aplicação. */
function validarFormularioRoteiro(form){
  const titulo = sanitizeSpaces(form.querySelector('[name="titulo"]')?.value).toUpperCase();
  const cabecalho = sanitizeSpaces(form.querySelector('[name="cabecalho"]')?.value);
  const rodape = sanitizeSpaces(form.querySelector('[name="rodape"]')?.value);
  const prefixo = String(form.querySelector('[name="prefixo_cena"]')?.value || '').trim();
  const inicial = Number(form.querySelector('[name="numeracao_inicial"]')?.value || 1);
  const logline = String(form.querySelector('[name="logline"]')?.value || '').trim();
  const sinopse = String(form.querySelector('[name="sinopse"]')?.value || '').trim();
  const genero = sanitizeSpaces(form.querySelector('[name="genero"]')?.value);
  if (!titulo) return i18n('js.script_name_required');
  if (titulo.length > 70) return window.t('js.script_title_max');
  if (cabecalho.length > 40) return i18n('js.script_header_max');
  if (rodape.length > 40) return i18n('js.script_footer_max');
  if (!validateNumericPrefix(prefixo)) return i18n('js.script_prefix_invalid');
  if (!Number.isInteger(inicial) || inicial < 1 || inicial > 9999) return i18n('js.script_initial_number_invalid');
  if (logline.length > 280) return i18n('js.script_logline_max');
  if (sinopse.length > 1000) return i18n('js.script_synopsis_max');
  if (genero.length > 60) return i18n('js.script_genre_max');
  return '';
}
/** Validarformulariocatalogo. Usada pelo fluxo principal da aplicação. */
function validarFormularioCatalogo(form){
  const nome = sanitizeSpaces(form.querySelector('input[type="text"]')?.value).toUpperCase();
  const descricao = String(form.querySelector('textarea')?.value || '').trim();
  if (!nome) return i18n('js.catalog_name_required');
  if (nome.length > 60) return i18n('js.catalog_name_max');
  if (descricao.length > 240) return i18n('js.catalog_description_max');
  return '';
}
/** Clamptext. Usada pelo fluxo principal da aplicação. */
function clampText(text, limit = 140){
  const clean = String(text || '').replace(/\s+/g, ' ').trim();
  if (!clean) return '';
  return clean.length > limit ? `${clean.slice(0, limit - 1).trimEnd()}…` : clean;
}
/** Getcatalogitemdetails. Usada pelo fluxo principal da aplicação. */
function getCatalogItemDetails(tipo, nome){
  const key = String(nome || '').trim().toLowerCase();
  return (catalogosProjeto[tipo] || []).find(item => String(item.nome || '').trim().toLowerCase() === key) || null;
}
/** Getcatalogaccent. Usada pelo fluxo principal da aplicação. */
function getCatalogAccent(tipo){
  return tipo === 'personagens' ? i18n('js.character_badge') : i18n('js.location_badge');
}
/** Getcatalogemoji. Usada pelo fluxo principal da aplicação. */
function getCatalogEmoji(tipo){
  return tipo === 'personagens' ? '' : '';
}
/** Getcatalogemptytext. Usada pelo fluxo principal da aplicação. */
function getCatalogEmptyText(tipo, contexto = 'vinculo'){
  if (contexto === 'catalogo') return tipo === 'personagens' ? i18n('js.no_script_characters_registered') : i18n('js.no_script_locations_registered');
  return tipo === 'personagens' ? i18n('js.no_script_characters_linked') : i18n('js.no_script_locations_linked');
}
/** Rendercatalogcardmarkup. Usada pelo fluxo principal da aplicação. */
function renderCatalogCardMarkup(tipo, item, { compact = false } = {}){
  const nome = String(item?.nome || '').trim() || i18n('script.no_name');
  const descricaoCompleta = String(item?.descricao || '').trim();
  const descricao = clampText(descricaoCompleta, compact ? 140 : 220);
  const badge = getCatalogAccent(tipo);
  const emoji = getCatalogEmoji(tipo);
  return `
    <div class="catalogo-card-topo">
      <span class="catalogo-card-badge">${emoji} ${escapeHtml(badge)}</span>
    </div>
    <div class="catalogo-card-corpo">
      <h4 title="${escapeHtml(nome)}">${escapeHtml(nome)}</h4>
      <p class="catalogo-card-descricao${descricao ? '' : ' vazio'}"${descricaoCompleta ? ` title="${escapeHtml(descricaoCompleta)}"` : ''}>${escapeHtml(descricao || window.t('common.no_description'))}</p>
    </div>`;
}
document.getElementById('abrirModalRoteiro')?.addEventListener('click', ()=> abrirModal(modalRoteiro));
document.getElementById('abrirModalExportacao')?.addEventListener('click', ()=> abrirModal(modalExportacao));
document.getElementById('abrirModalEditarProjeto')?.addEventListener('click', ()=> abrirModal(modalEditarProjeto));
document.getElementById('abrirModalSalvarRoteiroGut')?.addEventListener('click', ()=>{
  const status = document.getElementById('statusSalvarRoteiroGut');
  if (status) status.textContent = '';
  abrirModal(modalSalvarRoteiroGut);
});
document.getElementById('abrirModalImportarRoteirosGut')?.addEventListener('click', ()=> abrirModal(modalImportarRoteirosGut));
document.querySelectorAll('[data-fechar-modal="true"]').forEach(el => el.addEventListener('click', (ev)=>{ ev.preventDefault(); ev.stopPropagation(); fecharModal(el.closest('.modal')); }));
document.querySelectorAll('[data-modal-card="true"]').forEach(el => el.addEventListener('click', (ev)=> ev.stopPropagation()));


async function salvarBlobComJanelaDoNavegador(blob, nomeArquivo, formato){
  if (typeof window.showSaveFilePicker !== 'function' || !window.isSecureContext) return false;

  const tipos = {
    epub: [{ description: 'EPUB', accept: { 'application/epub+zip': ['.epub'] } }],
    pdf: [{ description: 'PDF', accept: { 'application/pdf': ['.pdf'] } }],
    docx: [{ description: 'DOCX', accept: { 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'] } }],
    gut: [{ description: 'Gutenberg Snapshot', accept: { 'application/octet-stream': ['.gut'] } }],
  };

  try {
    const handle = await window.showSaveFilePicker({
      id: 'gutenberg-arquivos',
      suggestedName: nomeArquivo,
      types: tipos[String(formato || '').toLowerCase()] || undefined,
    });
    const writable = await handle.createWritable();
    await writable.write(blob);
    await writable.close();
    return true;
  } catch (err) {
    if (err && (err.name === 'AbortError' || err.name === 'SecurityError')) return 'cancelado';
    console.warn('Falha ao salvar com showSaveFilePicker:', err);
    return false;
  }
}

async function baixarBlobComFallback(blob, nomeArquivo, formato){
  const resultadoPicker = await salvarBlobComJanelaDoNavegador(blob, nomeArquivo, formato);
  if (resultadoPicker === true) return { ok: true, modo: 'picker' };
  if (resultadoPicker === 'cancelado') return { ok: false, cancelado: true };

  const dl = document.createElement('a');
  dl.href = URL.createObjectURL(blob);
  dl.download = nomeArquivo;
  document.body.appendChild(dl);
  dl.click();
  dl.remove();
  URL.revokeObjectURL(dl.href);
  return { ok: true, modo: 'download' };
}


function definirProcessamentoGut(ativo, mensagem = '', titulo = ''){
  const overlay = document.getElementById('overlayProcessandoGut');
  const texto = document.getElementById('mensagemOverlayGut');
  const tituloEl = document.getElementById('tituloOverlayGut');
  if (tituloEl) tituloEl.textContent = titulo || i18n('index.pending_gut_title');
  if (texto) texto.textContent = mensagem || i18n('js.processing_file');
  if (!overlay) return;
  overlay.classList.toggle('oculto', !ativo);
  overlay.setAttribute('aria-hidden', ativo ? 'false' : 'true');
  document.body.classList.toggle('biblioteca-processando', !!ativo);
}

async function importarGutViaDesktop(){
  definirProcessamentoGut(true, i18n('js.import_preparing'));
  const seletor = await window.pywebview?.api?.openGutFileDialog?.();
  if (!seletor?.ok) {
    definirProcessamentoGut(false);
    if (seletor?.erro && !seletor?.cancelado) throw new Error(seletor.erro);
    return false;
  }
  definirProcessamentoGut(true, i18n('js.importing_gut'));
  try {
    const resposta = await fetch(`/projetos/${window.PROJETO_SLUG}/importar-gut-desktop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ caminho: seletor.caminho }),
    });
    const dados = await resposta.json().catch(() => ({}));
    if (!resposta.ok || !dados?.ok) throw new Error(dados?.erro || i18n('js.import_error'));
    location.href = dados.redirect;
    return true;
  } catch (err) {
    definirProcessamentoGut(false);
    throw err;
  }
}

async function importarGutViaUpload(arquivo){
  const fd = new FormData();
  fd.append('arquivo', arquivo);
  definirProcessamentoGut(true, i18n('js.importing_gut'));
  try {
    const resposta = await fetch(`/projetos/${window.PROJETO_SLUG}/importar-gut`, { method: 'POST', body: fd });
    const dados = await resposta.json().catch(() => ({}));
    if (!resposta.ok || !dados?.ok) throw new Error(dados?.erro || i18n('js.import_error'));
    location.href = dados.redirect;
    return true;
  } catch (err) {
    definirProcessamentoGut(false);
    throw err;
  }
}

async function iniciarImportacaoGut(){
  const input = document.getElementById('inputGutImportacao');
  try {
    if (window.pywebview?.api?.openGutFileDialog) {
      await importarGutViaDesktop();
      return;
    }
    if (!input) throw new Error(i18n('js.import_error'));
    definirProcessamentoGut(true, i18n('js.import_preparing'));
    input.value = '';
    const aoRetornarJanela = () => {
      setTimeout(() => {
        if (!(input.files && input.files.length)) definirProcessamentoGut(false);
      }, 200);
    };
    window.addEventListener('focus', aoRetornarJanela, { once: true });
    input.click();
  } catch (err) {
    definirProcessamentoGut(false);
    alert(err.message || i18n('js.import_error'));
  }
}


async function salvarArquivoPorRota({ url, formato = 'gut', statusElement, sucessoMensagem, erroMensagem, modalParaFechar = null, usarOverlay = false, mensagemOverlay = '', tituloOverlay = '' }){
  if (statusElement) statusElement.textContent = i18n('js.saving');
  if (usarOverlay) definirProcessamentoGut(true, mensagemOverlay || i18n('js.saving'), tituloOverlay || i18n('index.pending_gut_title'));
  const isDesktopSave = Boolean(window.pywebview?.api?.saveExportedFile);
  const destino = `${url}${url.includes('?') ? '&' : '?'}${isDesktopSave ? 'desktop_save=1' : ''}`;

  try {
    const resp = await fetch(destino);
    if (!resp.ok) {
      let mensagem = erroMensagem || i18n('js.save_error');
      try {
        const erro = await resp.json();
        mensagem = erro.erro || erro.mensagem || mensagem;
      } catch (_) {}
      throw new Error(mensagem);
    }

    if (isDesktopSave) {
      const dados = await resp.json();
      if (!dados?.ok || !dados?.arquivo) throw new Error(dados?.erro || erroMensagem || i18n('js.save_error'));
      const resultado = await window.pywebview.api.saveExportedFile(dados.arquivo, dados.nome, dados.pasta_inicial);
      if (!resultado?.ok) {
        if (resultado?.cancelado) {
          if (statusElement) statusElement.textContent = i18n('js.export_cancelled');
          if (usarOverlay) definirProcessamentoGut(false);
          return false;
        }
        throw new Error(resultado?.erro || erroMensagem || i18n('js.save_error'));
      }
      if (modalParaFechar) fecharModal(modalParaFechar);
      if (statusElement) statusElement.textContent = sucessoMensagem || i18n('js.save_success');
      if (usarOverlay) definirProcessamentoGut(false);
      return true;
    }

    const blob = await resp.blob();
    const dispo = resp.headers.get('Content-Disposition') || '';
    const m = dispo.match(/filename=([^;]+)/i);
    const nomeArquivo = m ? m[1].replace(/"/g,'') : `${window.PROJETO_SLUG}.${formato}`;
    const download = await baixarBlobComFallback(blob, nomeArquivo, formato);
    if (!download?.ok) {
      if (download?.cancelado) {
        if (statusElement) statusElement.textContent = i18n('js.export_cancelled');
        if (usarOverlay) definirProcessamentoGut(false);
        return false;
      }
      throw new Error(erroMensagem || i18n('js.save_error'));
    }

    if (modalParaFechar) fecharModal(modalParaFechar);
    if (statusElement) statusElement.textContent = sucessoMensagem || i18n('js.save_success');
    if (usarOverlay) definirProcessamentoGut(false);
    return true;
  } catch (err) {
    if (usarOverlay) definirProcessamentoGut(false);
    if (statusElement) statusElement.textContent = err.message || erroMensagem || i18n('js.save_error');
    return false;
  }
}




formRoteiro?.addEventListener('submit', async (e)=>{
  e.preventDefault();
  const status = document.getElementById('statusRoteiro');
  const erro = validarFormularioRoteiro(formRoteiro);
  if (erro) {
    if (status) status.textContent = erro;
    return;
  }
  if (status) status.textContent = i18n('js.creating_script');
  try {
    const r = await fetch(`/projetos/${window.PROJETO_SLUG}/roteiros/criar`, {method:'POST', body:new FormData(formRoteiro)});
    const d = await r.json();
    if (d.ok) { location.href = d.redirect; return; }
    if (status) status.textContent = d.erro || i18n('js.create_script_error');
  } catch (err) {
    if (status) status.textContent = err.message || i18n('js.create_script_error');
  }
});

document.querySelectorAll('.btn-excluir-roteiro').forEach(btn => btn.addEventListener('click', async ()=>{
  if (!confirm(window.t('js.confirm_delete_script'))) return;
  const r = await fetch(`/projetos/${window.PROJETO_SLUG}/roteiros/${btn.dataset.numero}/excluir`, {method:'POST'});
  const d = await r.json(); if (d.ok) location.reload();
}));

formEditarProjeto?.addEventListener('submit', async (e)=>{
  e.preventDefault();
  const status = document.getElementById('statusEditarProjeto');
  const erro = validarFormularioProjetoRoteiro(formEditarProjeto);
  if (erro) {
    status.textContent = erro;
    return;
  }
  status.textContent = i18n('js.saving');
  const r = await fetch(`/projetos/${window.PROJETO_SLUG}/atualizar`, {method:'POST', body:new FormData(formEditarProjeto)});
  const d = await r.json();
  if (d.ok){ fecharModal(modalEditarProjeto); location.reload(); }
  else status.textContent = d.erro || i18n('js.save_error');
});


formSalvarRoteiroGut?.addEventListener('submit', async (e)=>{
  e.preventDefault();
  fecharModal(modalSalvarRoteiroGut);
  const status = document.getElementById('statusSalvarRoteiroGut');
  if (status) status.textContent = '';
  const params = new URLSearchParams(new FormData(formSalvarRoteiroGut));
  const salvou = await salvarArquivoPorRota({
    url: `${formSalvarRoteiroGut.action}?${params.toString()}`,
    formato: 'gut',
    statusElement: null,
    sucessoMensagem: i18n('js.save_success'),
    erroMensagem: i18n('js.save_error'),
    modalParaFechar: null,
    usarOverlay: true,
    mensagemOverlay: i18n('js.saving_gut'),
    tituloOverlay: i18n('index.save_gut_title'),
  });
  if (!salvou && status) status.textContent = i18n('js.save_error');
});

document.getElementById('confirmarImportarRoteirosGut')?.addEventListener('click', async ()=>{
  fecharModal(modalImportarRoteirosGut);
  await iniciarImportacaoGut();
});
document.getElementById('inputGutImportacao')?.addEventListener('change', async (ev)=>{
  const arquivo = ev.target?.files?.[0];
  if (!arquivo) {
    definirProcessamentoGut(false);
    return;
  }
  try {
    await importarGutViaUpload(arquivo);
  } catch (err) {
    definirProcessamentoGut(false);
    alert(err.message || i18n('js.import_error'));
  }
});

formExportacao?.addEventListener('submit', async (e)=>{
  e.preventDefault();
  const status = document.getElementById('statusExportacao');
  status.textContent = i18n('js.exporting');
  const params = new URLSearchParams(new FormData(formExportacao));
  const formato = params.get('formato');
  const isDesktopSave = Boolean(window.pywebview?.api?.saveExportedFile) && formato !== 'xhtml';
  const url = `${formExportacao.action}?${params.toString()}${isDesktopSave ? '&desktop_save=1' : ''}`;
  try {
    const resp = await fetch(url);
    if (!resp.ok) {
      let mensagem = i18n('js.export_failed');
      try {
        const erro = await resp.json();
        mensagem = erro.erro || erro.mensagem || mensagem;
      } catch (_) {}
      throw new Error(mensagem);
    }

    if (isDesktopSave) {
      const dados = await resp.json();
      if (!dados?.ok || !dados?.arquivo) throw new Error(dados?.erro || i18n('js.export_failed'));

      const resultado = await window.pywebview.api.saveExportedFile(dados.arquivo, dados.nome, dados.pasta_inicial);
      if (!resultado?.ok) {
        if (resultado?.cancelado) {
          status.textContent = i18n('js.export_cancelled');
          return;
        }
        throw new Error(resultado?.erro || i18n('js.export_error'));
      }

      fecharModal(modalExportacao);
      status.textContent = i18n('js.export_success');
      return;
    }

    const blob = await resp.blob();
    const dispo = resp.headers.get('Content-Disposition') || '';
    const m = dispo.match(/filename=([^;]+)/i);
    const nomeArquivo = m ? m[1].replace(/"/g,'') : `${window.PROJETO_SLUG}.${formato}`;
    const download = await baixarBlobComFallback(blob, nomeArquivo, formato);
    if (!download?.ok) {
      if (download?.cancelado) {
        status.textContent = i18n('js.export_cancelled');
        return;
      }
      throw new Error(i18n('js.export_error'));
    }
    fecharModal(modalExportacao);
    status.textContent = i18n('js.export_success');
  } catch (err) {
    status.textContent = err.message || i18n('js.export_error');
  }
});

document.querySelectorAll('.btn-info-roteiro').forEach(btn => btn.addEventListener('click', ()=>{
  document.getElementById('infoRoteiroNumero').value = btn.dataset.numero;
  document.getElementById('infoRoteiroTitulo').value = btn.dataset.titulo || '';
  document.getElementById('infoRoteiroCabecalho').value = btn.dataset.cabecalho || '';
  document.getElementById('infoRoteiroRodape').value = btn.dataset.rodape || '';
  document.getElementById('infoRoteiroPrefixo').value = btn.dataset.prefixo || '0';
  document.getElementById('infoRoteiroInicial').value = btn.dataset.inicial || '1';
  document.getElementById('infoRoteiroLogline').value = btn.dataset.logline || '';
  document.getElementById('infoRoteiroSinopse').value = btn.dataset.sinopse || '';
  document.getElementById('infoRoteiroGenero').value = btn.dataset.genero || '';
  const campoTipoRoteiro = document.getElementById('infoRoteiroTipo');
  if (campoTipoRoteiro) campoTipoRoteiro.value = btn.dataset.tipo || 'spec_script';
  const campoCopyright = document.getElementById('infoRoteiroCopyright');
  if (campoCopyright) {
    campoCopyright.dataset.userTouched = '';
    campoCopyright.checked = String(btn.dataset.copyright || '').toLowerCase() === 'true';
  }
  abrirModal(modalInfoRoteiro);
  window.validacaoCampos?.refreshModal?.(modalInfoRoteiro);
}));

formInfoRoteiro?.addEventListener('submit', async (e)=>{
  e.preventDefault();
  const numero = document.getElementById('infoRoteiroNumero').value;
  const status = document.getElementById('statusInfoRoteiro');
  const erro = validarFormularioRoteiro(formInfoRoteiro);
  if (erro) {
    status.textContent = erro;
    return;
  }
  status.textContent = i18n('js.updating_info');
  const r = await fetch(`/projetos/${window.PROJETO_SLUG}/roteiros/${numero}/atualizar`, {method:'POST', body:new FormData(formInfoRoteiro)});
  const d = await r.json();
  if (d.ok) location.reload(); else status.textContent = d.erro || i18n('js.save_error');
});

const tituloModalVinculosRoteiro = document.getElementById('tituloModalVinculosRoteiro');
const vinculosListaRoteiro = document.getElementById('vinculosListaRoteiro');
const vinculosRoteiroNumero = document.getElementById('vinculosRoteiroNumero');
const vinculosRoteiroTipo = document.getElementById('vinculosRoteiroTipo');
const statusVinculosRoteiro = document.getElementById('statusVinculosRoteiro');
let selecoesVinculosRoteiro = new Set();
let numeroRoteiroCatalogoAtual = '';

/** Parsecatalogoserializado. Usada pelo fluxo principal da aplicação. */
function parseCatalogoSerializado(valor){
  if (Array.isArray(valor)) return valor;
  const texto = String(valor || '').trim();
  if (!texto) return [];
  try {
    const parsed = JSON.parse(texto);
    return Array.isArray(parsed) ? parsed : [];
  } catch (_) {
    return normalizarListaNomes(texto).map(nome => ({ nome, descricao: '' }));
  }
}

/** Normalizarlistanomes. Usada pelo fluxo principal da aplicação. */
function normalizarListaNomes(valor){
  return String(valor || '').split(/\r?\n/).map(item => item.trim()).filter(Boolean);
}
/** Sincronizardatasetbotaovinculo. Usada pelo fluxo principal da aplicação. */
function sincronizarDatasetBotaoVinculo(tipo, numero, itens){
  const seletor = tipo === 'personagens' ? '.btn-personagens-roteiro' : '.btn-locais-roteiro';
  const btn = [...document.querySelectorAll(seletor)].find(el => String(el.dataset.numero) === String(numero));
  if (!btn) return;
  btn.dataset[tipo] = JSON.stringify(itens || []);
}

/** Rendervinculosroteiro. Usada pelo fluxo principal da aplicação. */
function renderVinculosRoteiro(){
  const tipo = vinculosRoteiroTipo?.value || 'personagens';
  const nomesSelecionados = [...selecoesVinculosRoteiro].map(item => String(item || '').trim()).filter(Boolean);
  vinculosListaRoteiro.innerHTML = '';
  if (!nomesSelecionados.length) {
    vinculosListaRoteiro.innerHTML = `<div class="vazio"><p>${getCatalogEmptyText(tipo)}</p></div>`;
    return;
  }
  nomesSelecionados.sort((a, b) => a.localeCompare(b, 'pt-BR')).forEach((nomeOriginal) => {
    const detalhes = getCatalogItemDetails(tipo, nomeOriginal) || { nome: nomeOriginal, descricao: '' };
    const article = document.createElement('article');
    article.className = 'catalogo-item catalogo-card catalogo-card-visualizacao';
    article.innerHTML = renderCatalogCardMarkup(tipo, detalhes, { compact: true });
    vinculosListaRoteiro.appendChild(article);
  });
}
async function abrirVinculosRoteiro(tipo, numero, selecionados){
  numeroRoteiroCatalogoAtual = String(numero || '');
  await carregarCatalogosProjeto(numeroRoteiroCatalogoAtual);
  vinculosRoteiroTipo.value = tipo;
  vinculosRoteiroNumero.value = numeroRoteiroCatalogoAtual;
  const itens = parseCatalogoSerializado(selecionados);
  selecoesVinculosRoteiro = new Set(itens.map(item => String(item?.nome || '').trim()).filter(Boolean));
  if (itens.length) {
    const key = tipo === 'personagens' ? 'personagens' : 'locais';
    catalogosProjeto[key] = itens;
  }
  tituloModalVinculosRoteiro.textContent = tipo === 'personagens' ? i18n('js.script_characters_title') : i18n('js.script_locations_title');
  statusVinculosRoteiro.textContent = '';
  renderVinculosRoteiro();
  abrirModal(modalVinculosRoteiro);
}

document.querySelectorAll('.btn-personagens-roteiro').forEach(btn => btn.addEventListener('click', ()=> abrirVinculosRoteiro('personagens', btn.dataset.numero, btn.dataset.personagens || '')));
document.querySelectorAll('.btn-locais-roteiro').forEach(btn => btn.addEventListener('click', ()=> abrirVinculosRoteiro('locais', btn.dataset.numero, btn.dataset.locais || '')));



document.getElementById('btnGerenciarCatalogoRoteiro')?.addEventListener('click', ()=> {
  const tipo = vinculosRoteiroTipo.value || 'personagens';
  fecharModal(modalVinculosRoteiro);
  abrirCatalogoProjeto(tipo, vinculosRoteiroNumero.value || numeroRoteiroCatalogoAtual);
});


const modalCatalogoProjeto = document.getElementById('modalCatalogoProjeto');
const modalCatalogoProjetoEditor = document.getElementById('modalCatalogoProjetoEditor');
const tituloModalCatalogoProjeto = document.getElementById('tituloModalCatalogoProjeto');
const tituloModalCatalogoProjetoEditor = document.getElementById('tituloModalCatalogoProjetoEditor');
const catalogoListaProjeto = document.getElementById('catalogoListaProjeto');
const formCatalogoProjeto = document.getElementById('formCatalogoProjeto');
const catalogoTipoProjeto = document.getElementById('catalogoTipoProjeto');
const catalogoNomeProjeto = document.getElementById('catalogoNomeProjeto');
const catalogoNomeOriginalProjeto = document.getElementById('catalogoNomeOriginalProjeto');
const catalogoDescricaoProjeto = document.getElementById('catalogoDescricaoProjeto');
const statusCatalogoProjeto = document.getElementById('statusCatalogoProjeto');
let catalogosProjeto = {personagens: [], locais: []};

async function carregarCatalogosProjeto(numero){
  if (!numero) return;
  const resp = await fetch(`/api/projetos/${window.PROJETO_SLUG}/roteiros/${numero}/catalogo`);
  const data = await resp.json();
  if (data.ok) catalogosProjeto = {personagens: data.personagens || [], locais: data.locais || []};
}
/** Rendercatalogoprojeto. Usada pelo fluxo principal da aplicação. */
function renderCatalogoProjeto(){
  const tipo = catalogoTipoProjeto.value;
  const items = (catalogosProjeto[tipo] || []).slice().sort((a, b) => String(a.nome || '').localeCompare(String(b.nome || '')));
  catalogoListaProjeto.innerHTML = '';
  if (!items.length) {
    catalogoListaProjeto.innerHTML = `<div class="vazio"><p>${getCatalogEmptyText(tipo, 'catalogo')}</p></div>`;
    return;
  }
  items.forEach(item => {
    const article = document.createElement('article');
    article.className = 'catalogo-item catalogo-card catalogo-card-gerenciavel';
    article.innerHTML = `
      ${renderCatalogCardMarkup(tipo, item)}
      <div class="catalogo-card-acoes">
        <button type="button" class="botao-secundario botao-apenas-icone" title="${i18n('js.edit_title')}">✎</button>
        <button type="button" class="botao-perigo botao-apenas-icone" title="${i18n('js.delete_title')}">✕</button>
      </div>`;
    const [btnEdit, btnDelete] = article.querySelectorAll('button');
    btnEdit?.addEventListener('click', ()=> abrirEditorCatalogoProjeto(tipo, item));
    btnDelete?.addEventListener('click', ()=> excluirItemCatalogoProjeto(tipo, item.nome));
    catalogoListaProjeto.appendChild(article);
  });
}
async function excluirItemCatalogoProjeto(tipo, nome){
  if (!confirm(i18n('script.delete_item_confirm', { name: nome }))) return;
  const numero = numeroRoteiroCatalogoAtual || vinculosRoteiroNumero.value;
  const resp = await fetch(`/api/projetos/${window.PROJETO_SLUG}/roteiros/${numero}/catalogo/${tipo}/excluir`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({nome})});
  const data = await resp.json();
  if (data.ok) {
    catalogosProjeto[tipo] = data.itens || [];
    sincronizarDatasetBotaoVinculo(tipo, numero, catalogosProjeto[tipo]);
    renderCatalogoProjeto();
    renderVinculosRoteiro();
  }
}
/** Limpareditorcatalogoprojeto. Usada pelo fluxo principal da aplicação. */
function limparEditorCatalogoProjeto(){
  catalogoNomeOriginalProjeto.value = '';
  catalogoNomeProjeto.value = '';
  catalogoDescricaoProjeto.value = '';
  statusCatalogoProjeto.textContent = '';
}
/** Abrireditorcatalogoprojeto. Usada pelo fluxo principal da aplicação. */
function abrirEditorCatalogoProjeto(tipo, item = null){
  catalogoTipoProjeto.value = tipo;
  tituloModalCatalogoProjetoEditor.textContent = item ? i18n('common.edit_item') : i18n('common.new_item');
  catalogoNomeOriginalProjeto.value = item?.nome || '';
  catalogoNomeProjeto.value = item?.nome || '';
  catalogoDescricaoProjeto.value = item?.descricao || '';
  statusCatalogoProjeto.textContent = '';
  applyUppercaseInputs(modalCatalogoProjetoEditor || document);
  fecharModal(modalCatalogoProjeto);
  abrirModal(modalCatalogoProjetoEditor);
  window.validacaoCampos?.refreshModal?.(modalCatalogoProjetoEditor);
}
async function abrirCatalogoProjeto(tipo, numero){
  numeroRoteiroCatalogoAtual = String(numero || numeroRoteiroCatalogoAtual || '');
  await carregarCatalogosProjeto(numeroRoteiroCatalogoAtual);
  catalogoTipoProjeto.value = tipo;
  tituloModalCatalogoProjeto.textContent = tipo === 'personagens' ? i18n('js.script_characters_title') : i18n('js.script_locations_title');
  limparEditorCatalogoProjeto();
  renderCatalogoProjeto();
  fecharModal(modalCatalogoProjetoEditor);
  abrirModal(modalCatalogoProjeto);
  window.validacaoCampos?.refreshModal?.(modalCatalogoProjeto);
}
formCatalogoProjeto?.addEventListener('submit', async (e)=> {
  e.preventDefault();
  const erro = validarFormularioCatalogo(formCatalogoProjeto);
  if (erro) {
    statusCatalogoProjeto.textContent = erro;
    return;
  }
  statusCatalogoProjeto.textContent = i18n('js.saving');
  const tipo = catalogoTipoProjeto.value;
  const nomeOriginal = catalogoNomeOriginalProjeto.value.trim().toUpperCase();
  const nome = catalogoNomeProjeto.value.trim().toUpperCase();
  try {
    if (nomeOriginal && nomeOriginal.toLowerCase() !== nome.toLowerCase()) {
      const numero = numeroRoteiroCatalogoAtual || vinculosRoteiroNumero.value;
      const respExcluir = await fetch(`/api/projetos/${window.PROJETO_SLUG}/roteiros/${numero}/catalogo/${tipo}/excluir`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({nome: nomeOriginal})});
      const dataExcluir = await respExcluir.json();
      if (dataExcluir.ok) catalogosProjeto[tipo] = dataExcluir.itens || [];
    }
    const numero = numeroRoteiroCatalogoAtual || vinculosRoteiroNumero.value;
    const resp = await fetch(`/api/projetos/${window.PROJETO_SLUG}/roteiros/${numero}/catalogo/${tipo}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({nome, descricao: catalogoDescricaoProjeto.value.trim()})});
    const data = await resp.json();
    if (data.ok) {
      catalogosProjeto[tipo] = data.itens || [];
      sincronizarDatasetBotaoVinculo(tipo, numero, catalogosProjeto[tipo]);
      renderVinculosRoteiro();
      statusCatalogoProjeto.textContent = i18n('script.saved');
      fecharModal(modalCatalogoProjetoEditor);
      abrirModal(modalCatalogoProjeto);
      renderCatalogoProjeto();
    } else {
      statusCatalogoProjeto.textContent = data.erro || i18n('script.save_error');
    }
  } catch (err) {
    statusCatalogoProjeto.textContent = err.message || i18n('script.save_error');
  }
});

document.getElementById('btnNovoItemCatalogoProjeto')?.addEventListener('click', ()=> abrirEditorCatalogoProjeto(catalogoTipoProjeto.value));

applyUppercaseInputs();
