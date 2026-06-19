/**
 * Lógica da página do projeto, incluindo exportação, validações e estatísticas.
 */

/** I18n. Usada pelo fluxo principal da aplicação. */
const i18n = (key, vars = {}) => (window.t ? window.t(key, vars) : key);

const modalCapitulo = document.getElementById('modalCapitulo');
const modalExportacao = document.getElementById('modalExportacao');
const modalEditarProjeto = document.getElementById('modalEditarProjeto');
const modalImportarCapitulosGut = document.getElementById('modalImportarCapitulosGut');
const modalEstatisticasProjeto = document.getElementById('modalEstatisticasProjeto');
const estatisticasProjetoConteudo = document.getElementById('estatisticasProjetoConteudo');
const formEditarProjeto = document.getElementById('formEditarProjeto');
const statusEditarProjeto = document.getElementById('statusEditarProjeto');
const formExportacao = document.getElementById('formExportacao');
const statusExportacao = document.getElementById('statusExportacao');

const selectFormatoExportacao = document.getElementById('selectFormatoExportacao');
const grupoVersaoEpub = document.getElementById('grupoVersaoEpub');

/** Atualizarcamposexportacao. Usada pelo fluxo principal da aplicação. */
function atualizarCamposExportacao(){
  if (!selectFormatoExportacao || !grupoVersaoEpub) return;
  grupoVersaoEpub.style.display = selectFormatoExportacao.value === 'epub' ? '' : 'none';
}
selectFormatoExportacao?.addEventListener('change', atualizarCamposExportacao);
atualizarCamposExportacao();

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
/** Validarcapitulo. Usada pelo fluxo principal da aplicação. */
function validarCapitulo(form){
  const titulo = sanitizeSpaces(form.querySelector('[name="titulo"]')?.value);
  if (!titulo) return i18n('js.chapter_title_required');
  if (titulo.length > 70) return i18n('js.chapter_title_max');
  return '';
}
/** Validarprojetolivro. Usada pelo fluxo principal da aplicação. */
function validarProjetoLivro(form){
  const titulo = sanitizeSpaces(form.querySelector('[name="titulo"]')?.value);
  const descricao = String(form.querySelector('[name="descricao"]')?.value || '').trim();
  const autor = sanitizeSpaces(form.querySelector('[name="autor"]')?.value);
  const tags = String(form.querySelector('[name="tags"]')?.value || '').trim();
  const contatos = sanitizeSpaces(form.querySelector('[name="contatos"]')?.value);
  if (!titulo) return i18n('js.project_required');
  if (titulo.length > 70) return i18n('js.project_title_max');
  if (descricao.length > 1000) return i18n('js.project_description_max');
  if (autor.length > 80) return i18n('js.project_author_max');
  if (tags.length > 180) return i18n('js.project_tags_max');
  if (contatos) {
    if (contatos.length > 70) return i18n('js.project_contact_max');
    if (!isValidEmail(contatos) && !isValidPhone(contatos)) return i18n('js.project_contact_invalid');
  }
  return '';
}
document.getElementById('abrirModalCapitulo')?.addEventListener('click', ()=> abrirModal(modalCapitulo));
document.getElementById('abrirModalExportacao')?.addEventListener('click', ()=> abrirModal(modalExportacao));
document.getElementById('abrirModalEditarProjeto')?.addEventListener('click', ()=> abrirModal(modalEditarProjeto));
document.getElementById('abrirModalImportarCapitulosGut')?.addEventListener('click', ()=> abrirModal(modalImportarCapitulosGut));
document.getElementById('abrirModalEstatisticasProjeto')?.addEventListener('click', async ()=> { abrirModal(modalEstatisticasProjeto); await carregarEstatisticasProjeto(); });
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


document.getElementById('formCapitulo')?.addEventListener('submit', async (e)=>{
  e.preventDefault();
  const status = document.getElementById('statusCapitulo');
  const erro = validarCapitulo(e.target);
  if (erro) {
    if (status) status.textContent = erro;
    return;
  }
  const r = await fetch(`/projetos/${window.PROJETO_SLUG}/capitulos/criar`, {method:'POST', body:new FormData(e.target)});
  const d = await r.json();
  if (d.ok) location.href = d.redirect;
  else if (status) status.textContent = d.erro || i18n('js.create_chapter_error');
});

document.querySelectorAll('.btn-excluir-capitulo').forEach(btn => btn.addEventListener('click', async ()=>{
  if (!confirm(i18n('js.delete_chapter_confirm'))) return;
  const r = await fetch(`/projetos/${window.PROJETO_SLUG}/capitulos/${btn.dataset.numero}/excluir`, {method:'POST'});
  const d = await r.json(); if (d.ok) location.reload();
}));

const inputCoverProjeto = document.getElementById('inputCoverProjeto');
inputCoverProjeto?.addEventListener('change', async ()=>{
  if (!inputCoverProjeto.files?.length) return;
  const fd = new FormData(); fd.append('cover', inputCoverProjeto.files[0]);
  const r = await fetch(`/projetos/${window.PROJETO_SLUG}/cover`, {method:'POST', body:fd});
  const d = await r.json();
  if (d.ok) location.reload(); else alert(d.erro || i18n('js.save_cover_error'));
});

formEditarProjeto?.addEventListener('submit', async (e)=>{
  e.preventDefault();
  const erro = validarProjetoLivro(formEditarProjeto);
  if (erro) {
    statusEditarProjeto.textContent = erro;
    return;
  }
  statusEditarProjeto.textContent = i18n('js.saving');
  const r = await fetch(`/projetos/${window.PROJETO_SLUG}/atualizar`, {method:'POST', body:new FormData(formEditarProjeto)});
  const d = await r.json();
  if (d.ok){ fecharModal(modalEditarProjeto); location.reload(); }
  else statusEditarProjeto.textContent = d.erro || i18n('js.save_error');
});


document.getElementById('botaoSalvarCapitulosGut')?.addEventListener('click', async ()=>{
  await salvarArquivoPorRota({
    url: `/projetos/${window.PROJETO_SLUG}/salvar-capitulos`,
    formato: 'gut',
    statusElement: document.getElementById('statusSalvarCapitulosGut'),
    sucessoMensagem: i18n('js.save_success'),
    erroMensagem: i18n('js.save_error'),
    usarOverlay: true,
    mensagemOverlay: i18n('js.saving_gut'),
    tituloOverlay: i18n('index.save_gut_title'),
  });
});

document.getElementById('confirmarImportarCapitulosGut')?.addEventListener('click', async ()=>{
  fecharModal(modalImportarCapitulosGut);
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


/** Formatarnumero. Usada pelo fluxo principal da aplicação. */
function formatarNumero(valor){
  return new Intl.NumberFormat(window.APP_CONFIG?.idiomaApp === 'en_US' ? 'en-US' : 'pt-BR').format(Number(valor || 0));
}

/** Escapehtml. Usada pelo fluxo principal da aplicação. */
function escapeHtml(valor){
  return String(valor ?? '').replace(/[&<>"']/g, (ch)=>({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[ch]));
}

/** Formatartempominutos. Usada pelo fluxo principal da aplicação. */
function formatarTempoMinutos(valor){
  const total = Math.max(0, Number(valor || 0));
  return i18n('js.minutes_short', { total: formatarNumero(total) });
}

/** Normalizartextotempo. Usada pelo fluxo principal da aplicação. */
function normalizarTextoTempo(valor){
  return String(valor ?? '0 min')
    .replace(/(\d)min\b/g, '$1 min')
    .replace(/h\s*(\d+)min\b/g, 'h $1 min')
    .replace(/(\d)seg\b/g, i18n('js.seconds_short_compact', { value: '$1' }));
}

/** Criarkpi. Usada pelo fluxo principal da aplicação. */
function criarKpi(label, valor, sublabel = ''){
  return `<div class="estat-kpi"><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(valor ?? '0'))}</strong>${sublabel ? `<small>${escapeHtml(sublabel)}</small>` : ''}</div>`;
}

/** Criarlinhametrica. Usada pelo fluxo principal da aplicação. */
function criarLinhaMetrica(label, valor, apoio = ''){
  return `<div class="linha-metrica"><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(valor ?? '0'))}</strong>${apoio ? `<p>${escapeHtml(apoio)}</p>` : ''}</div>`;
}

/** Criarbarracapitulo. Usada pelo fluxo principal da aplicação. */
function criarBarraCapitulo(item){
  const largura = Math.max(6, Math.min(100, Number(item.participacao || 0)));
  return `
    <div class="barra-capitulo-item">
      <div class="barra-capitulo-topo">
        <strong>${escapeHtml(item.titulo)}</strong>
        <span>${escapeHtml(i18n('script.chapter_word_percent', { words: formatarNumero(item.palavras), percent: String(item.participacao || 0) }))}</span>
      </div>
      <div class="barra-capitulo-trilha"><div class="barra-capitulo-valor" style="width:${largura}%"></div></div>
      <small>${escapeHtml(window.t('js.chapter_reading_time', { number: item.id, time: formatarTempoMinutos(item.tempo_leitura_min) }))}</small>
    </div>`;
}

/** Criartagvocabulario. Usada pelo fluxo principal da aplicação. */
function criarTagVocabulario(item){
  return `<span class="estat-chip">${escapeHtml(item[0])} · ${formatarNumero(item[1])}</span>`;
}

let estatisticasProjetoCache = null;
async function carregarEstatisticasProjeto(force = false){
  if (!estatisticasProjetoConteudo) return;
  if (estatisticasProjetoCache && !force) {
    renderizarEstatisticasProjeto(estatisticasProjetoCache);
    return;
  }
  estatisticasProjetoConteudo.innerHTML = `<section class="estat-card"><p class="estat-ajuda">${escapeHtml(i18n('js.loading_project_stats'))}</p></section>`;
  try {
    const resp = await fetch(`/api/projetos/${window.PROJETO_SLUG}/estatisticas`);
    const dados = await resp.json();
    if (!resp.ok || !dados.ok) throw new Error(dados.erro || i18n('js.project_stats_error'));
    estatisticasProjetoCache = dados.estatisticas;
    renderizarEstatisticasProjeto(dados.estatisticas);
  } catch (erro) {
    estatisticasProjetoConteudo.innerHTML = `<section class="estat-card"><p class="estat-ajuda">${escapeHtml(erro.message || i18n('js.project_stats_error'))}</p></section>`;
  }
}

/** Renderizarestatisticasprojeto. Usada pelo fluxo principal da aplicação. */
function renderizarEstatisticasProjeto(stats){
  if (!estatisticasProjetoConteudo || !stats) return;
  const resumo = stats.resumo || {};
  const maior = stats.maior_capitulo;
  const menor = stats.menor_capitulo;
  const ranking = (stats.ranking_capitulos || []).map(criarBarraCapitulo).join('') || `<p class="estat-ajuda">${escapeHtml(i18n('js.no_chapters_for_analysis'))}</p>`;;
  const vocabulario = (stats.top_vocabulario || []).map(criarTagVocabulario).join('') || `<p class="estat-ajuda">${escapeHtml(i18n('js.add_more_content_words'))}</p>`;;

  estatisticasProjetoConteudo.innerHTML = `
    <section class="estat-card destaque destaque-dashboard">
      <div class="estat-hero-texto">
        <span class="estat-label">${escapeHtml(i18n('js.book_panel'))}</span>
        <strong class="estat-valor">${i18n('script.words_count', { count: formatarNumero(resumo.palavras) })}</strong>
        <p class="estat-ajuda">${escapeHtml(i18n('js.project_overview_desc'))}</p>
      </div>
      <div class="estat-kpi-grid">
        ${criarKpi(i18n('js.chapters'), formatarNumero(resumo.total_capitulos), i18n('script.with_text', { count: formatarNumero(resumo.capitulos_com_texto) }))}
        ${criarKpi(i18n('js.estimated_reading'), escapeHtml(normalizarTextoTempo(resumo.tempo_leitura_legivel || '0 min')), i18n('script.pages_estimated', { count: formatarNumero(resumo.paginas_estimadas) }))}
        ${criarKpi(i18n('script.reams'), formatarNumero(resumo.laudas_estimadas), i18n('script.reams_base'))}
        ${criarKpi(i18n('js.unique_vocabulary'), formatarNumero(resumo.palavras_unicas), i18n('script.lexical_diversity', { value: escapeHtml(String(resumo.diversidade_lexica || 0)) }))}
      </div>
    </section>

    <section class="estat-grid estat-grid-topo">
      <article class="estat-card">
        <h3>${escapeHtml(i18n('js.editorial_overview'))}</h3>
        <div class="estat-kpi-grid compacto">
          ${criarKpi(i18n('js.paragraphs'), formatarNumero(resumo.paragrafos), i18n('script.sentences_count', { count: formatarNumero(resumo.sentencas) }))}
          ${criarKpi(i18n('script.average_per_chapter'), formatarNumero(resumo.media_palavras_capitulo), i18n('script.words_per_chapter'))}
          ${criarKpi(i18n('script.average_per_paragraph'), formatarNumero(resumo.media_palavras_paragrafo), i18n('script.prose_density'))}
          ${criarKpi(i18n('script.average_per_sentence'), formatarNumero(resumo.media_palavras_sentenca), i18n('script.reading_pace'))}
        </div>
      </article>
      <article class="estat-card">
        <h3>${escapeHtml(i18n('js.epub_structure'))}</h3>
        <div class="estat-resumo-bloco">
          ${criarLinhaMetrica(i18n('js.h1_titles'), formatarNumero(resumo.h1), i18n('js.main_openings'))}
          ${criarLinhaMetrica(i18n('js.h2_titles'), formatarNumero(resumo.h2), i18n('js.internal_sections'))}
          ${criarLinhaMetrica(i18n('js.h3_titles'), formatarNumero(resumo.h3), i18n('js.subsections'))}
          ${criarLinhaMetrica(i18n('js.empty_chapters'), formatarNumero(resumo.capitulos_vazios), i18n('js.ready_for_development'))}
        </div>
      </article>
    </section>

    <section class="estat-grid">
      <article class="estat-card estat-card-largo">
        <h3>${escapeHtml(i18n('js.chapter_distribution'))}</h3>
        <div class="estat-barras-capitulos">${ranking}</div>
      </article>

      <article class="estat-card">
        <h3>${escapeHtml(i18n('js.longest_chapter'))}</h3>
        ${maior ? `
          <div class="estat-resumo-bloco">
            ${criarLinhaMetrica(maior.titulo, i18n('script.word_count_and_density', { words: formatarNumero(maior.palavras) }), i18n('script.chapter_time_pages', { number: maior.id, time: formatarTempoMinutos(maior.tempo_leitura_min), pages: maior.paginas_estimadas }))}
            ${criarLinhaMetrica(i18n('js.paragraphs'), formatarNumero(maior.paragrafos), i18n('js.avg_density_words_per_paragraph', { density: formatarNumero(maior.densidade) }))}
          </div>` : `<p class="estat-ajuda">${escapeHtml(i18n('js.not_enough_text_yet'))}</p>`}
      </article>

      <article class="estat-card">
        <h3>${escapeHtml(i18n('js.shortest_chapter'))}</h3>
        ${menor ? `
          <div class="estat-resumo-bloco">
            ${criarLinhaMetrica(menor.titulo, i18n('script.word_count_and_density', { words: formatarNumero(menor.palavras) }), i18n('script.chapter_time_pages', { number: menor.id, time: formatarTempoMinutos(menor.tempo_leitura_min), pages: menor.paginas_estimadas }))}
            ${criarLinhaMetrica(i18n('js.paragraphs'), formatarNumero(menor.paragrafos), i18n('js.avg_density_words_per_paragraph', { density: formatarNumero(menor.densidade) }))}
          </div>` : `<p class="estat-ajuda">${escapeHtml(i18n('js.not_enough_text_yet'))}</p>`}
      </article>

      <article class="estat-card">
        <h3>${escapeHtml(i18n('js.content_features'))}</h3>
        <div class="estat-kpi-grid compacto">
          ${criarKpi(i18n('js.images'), formatarNumero(resumo.imagens), i18n('js.embedded_in_chapters'))}
          ${criarKpi(i18n('js.links'), formatarNumero(resumo.links), i18n('js.internal_external_refs'))}
          ${criarKpi(i18n('js.lists'), formatarNumero(resumo.listas), i18n('js.list_items', { total: formatarNumero(resumo.itens_lista) }))}
          ${criarKpi(i18n('js.quotes'), formatarNumero(resumo.citacoes), i18n('js.dialog_quote_blocks', { percent: escapeHtml(String(resumo.percentual_dialogos || 0)) }))}
        </div>
      </article>

      <article class="estat-card estat-card-largo">
        <h3>${escapeHtml(i18n('js.recurring_vocabulary'))}</h3>
        <div class="estat-chip-group">${vocabulario}</div>
        <p class="estat-ajuda">${escapeHtml(i18n('js.recurring_vocabulary_desc'))}</p>
      </article>
    </section>`;
}


document.getElementById('botaoExportarEstatisticasPdf')?.addEventListener('click', ()=>{
  const botao = document.getElementById('botaoExportarEstatisticasPdf');
  if (!botao) return;
  const span = botao.querySelector('span');
  const textoOriginal = span?.textContent;
  if (span) span.textContent = i18n('project.generating_pdf');
  window.setTimeout(()=>{ if (span) span.textContent = textoOriginal || i18n('project.export_pdf'); }, 3000);
});
