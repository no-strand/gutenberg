/**
 * Atualiza a visualização instantânea das preferências alteradas na tela de configurações.
 */

const mapaSufixos = {
  cfgIndent: 'em',
  cfgIndentMaior: 'em',
  cfgEspacoParagrafos: 'em',
  cfgEspacoLinhas: '',
  cfgTamanhoFonte: 'px',
  cfgH1: 'px',
  cfgH2: 'px',
  cfgH3: 'px',
  cfgLargura: 'px',
};

const ids = Object.keys(mapaSufixos);

/** Atualizarpreview. Usada pelo fluxo principal da aplicação. */
function atualizarPreview(){
  const root = document.documentElement;
  const valores = {
    cfgIndent: document.getElementById('cfgIndent')?.value || 2,
    cfgIndentMaior: document.getElementById('cfgIndentMaior')?.value || 3.2,
    cfgEspacoParagrafos: document.getElementById('cfgEspacoParagrafos')?.value || 1.15,
    cfgEspacoLinhas: document.getElementById('cfgEspacoLinhas')?.value || 1.85,
    cfgTamanhoFonte: document.getElementById('cfgTamanhoFonte')?.value || 20,
    cfgH1: document.getElementById('cfgH1')?.value || 28,
    cfgH2: document.getElementById('cfgH2')?.value || 22,
    cfgH3: document.getElementById('cfgH3')?.value || 18,
    cfgLargura: document.getElementById('cfgLargura')?.value || 860,
  };
  root.style.setProperty('--cfg-indent', `${valores.cfgIndent}em`);
  root.style.setProperty('--cfg-indent-maior', `${valores.cfgIndentMaior}em`);
  root.style.setProperty('--cfg-espaco-paragrafo', `${valores.cfgEspacoParagrafos}em`);
  root.style.setProperty('--cfg-line-height', `${valores.cfgEspacoLinhas}`);
  root.style.setProperty('--cfg-font-size', `${valores.cfgTamanhoFonte}px`);
  root.style.setProperty('--cfg-h1', `${valores.cfgH1}px`);
  root.style.setProperty('--cfg-h2', `${valores.cfgH2}px`);
  root.style.setProperty('--cfg-h3', `${valores.cfgH3}px`);
  root.style.setProperty('--cfg-largura-leitura', `${valores.cfgLargura}px`);

  ids.forEach((id) => {
    const span = document.querySelector(`[data-valor="${id}"]`);
    const input = document.getElementById(id);
    if (span && input) span.textContent = `${input.value}${mapaSufixos[id]}`;
  });
}


ids.forEach((id) => document.getElementById(id)?.addEventListener('input', atualizarPreview));
document.addEventListener('DOMContentLoaded', atualizarPreview);

(function configurarAtualizacoes() {
  const botaoAbrir = document.getElementById('botaoVerificarAtualizacao');
  const modal = document.getElementById('modalAtualizacao');
  const status = document.getElementById('atualizacaoStatus');
  const info = document.getElementById('atualizacaoInfo');
  const versaoAtual = document.getElementById('atualizacaoVersaoAtual');
  const versaoRemota = document.getElementById('atualizacaoVersaoRemota');
  const descricao = document.getElementById('atualizacaoDescricao');
  const notas = document.getElementById('atualizacaoNotas');
  const progressoBox = document.getElementById('atualizacaoProgressoBox');
  const progressoBarra = document.getElementById('atualizacaoProgressoBarra');
  const progressoTexto = document.getElementById('atualizacaoProgressoTexto');
  const botaoAtualizar = document.getElementById('botaoIniciarAtualizacao');
  const botaoCancelar = document.getElementById('botaoCancelarAtualizacao');
  let ultimaVerificacao = null;
  let statusTimer = null;

  const tr = (key, vars = {}) => (window.t ? window.t(key, vars) : key);

  function abrirModalAtualizacao() {
    if (!modal) return;
    modal.classList.remove('oculto');
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    setTimeout(() => botaoAtualizar?.focus?.(), 40);
  }

  function fecharModalAtualizacao() {
    if (!modal) return;
    modal.classList.add('oculto');
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  function textoProgresso(estado) {
    const baixado = estado?.bytes_baixados_formatado || '';
    const total = estado?.bytes_total_formatado || '';
    if (baixado && total) return `${baixado} / ${total}`;
    if (total) return `${estado?.progresso || 0}% • ${total}`;
    return `${estado?.progresso || 0}%`;
  }

  function exibirProgresso(estado) {
    const ativo = Boolean(estado && (estado.ativo || estado.concluido || estado.etapa === 'erro' || estado.etapa === 'cancelado'));
    progressoBox?.classList.toggle('oculto', !ativo);
    if (!ativo) {
      if (progressoBarra) progressoBarra.style.width = '0%';
      if (progressoTexto) progressoTexto.textContent = '';
      botaoCancelar?.classList.add('oculto');
      return;
    }
    const progresso = Math.max(0, Math.min(100, Number(estado.progresso || 0)));
    if (progressoBarra) progressoBarra.style.width = `${progresso}%`;
    if (progressoTexto) progressoTexto.textContent = textoProgresso(estado);
    botaoCancelar?.classList.toggle('oculto', !estado.ativo);
    if (botaoCancelar) botaoCancelar.disabled = Boolean(estado.cancelando);
  }

  function definirEstadoCarregando() {
    if (status) status.textContent = tr('updates.checking');
    info?.classList.add('oculto');
    notas?.classList.add('oculto');
    exibirProgresso(null);
    if (botaoAtualizar) {
      botaoAtualizar.disabled = true;
      botaoAtualizar.dataset.podeAtualizar = '0';
    }
  }

  function exibirResultado(dados) {
    ultimaVerificacao = dados || null;
    info?.classList.remove('oculto');
    exibirProgresso(null);
    if (versaoAtual) versaoAtual.textContent = dados?.versao_atual || '-';
    if (versaoRemota) versaoRemota.textContent = dados?.versao_remota || '-';

    if (!dados?.ok) {
      if (status) status.textContent = dados?.erro || tr('updates.error');
      if (descricao) descricao.textContent = dados?.detalhe || '';
      if (botaoAtualizar) botaoAtualizar.disabled = true;
      return;
    }

    if (dados.ha_atualizacao) {
      if (status) status.textContent = tr('updates.update_available');
      const partes = [];
      if (dados.plataforma?.rotulo) partes.push(tr('updates.compatible_system', { system: `${dados.plataforma.rotulo} ${dados.plataforma.arquitetura || ''}`.trim() }));
      if (dados.instalador?.nome) partes.push(tr('updates.package_name', { name: dados.instalador.nome }));
      if (dados.instalador?.tamanho_formatado) partes.push(tr('updates.download_size', { size: dados.instalador.tamanho_formatado }));
      if (dados.aviso) partes.push(dados.aviso);
      if (descricao) descricao.textContent = partes.join(' • ') || tr('updates.update_available');
      if (notas) {
        notas.textContent = dados.notas || '';
        notas.classList.toggle('oculto', !dados.notas);
      }
      if (botaoAtualizar) {
        botaoAtualizar.disabled = !dados.pode_atualizar;
        botaoAtualizar.dataset.podeAtualizar = dados.pode_atualizar ? '1' : '0';
      }
      if (!dados.pode_atualizar && status) status.textContent = dados.aviso || tr('updates.no_installer');
      return;
    }

    if (status) status.textContent = tr('updates.updated');
    if (descricao) descricao.textContent = dados?.plataforma?.rotulo
      ? tr('updates.compatible_system', { system: `${dados.plataforma.rotulo} ${dados.plataforma.arquitetura || ''}`.trim() })
      : '';
    notas?.classList.add('oculto');
    if (botaoAtualizar) botaoAtualizar.disabled = true;
  }

  function aplicarEstadoAtualizacao(estado) {
    if (!estado || (!estado.ativo && !estado.concluido && !estado.cancelado && estado.etapa !== 'erro')) return;
    info?.classList.remove('oculto');
    if (versaoRemota && estado.versao) versaoRemota.textContent = estado.versao;
    if (descricao) descricao.textContent = estado.instalador || '';
    exibirProgresso(estado);
    if (botaoAtualizar) botaoAtualizar.disabled = true;

    if (estado.ativo) {
      if (status) status.textContent = estado.mensagem || tr('updates.downloading');
      iniciarPollingStatus();
      return;
    }
    if (estado.etapa === 'cancelado') {
      if (status) status.textContent = estado.mensagem || tr('updates.cancelled');
      if (botaoAtualizar) botaoAtualizar.disabled = !ultimaVerificacao?.pode_atualizar;
      pararPollingStatus();
      return;
    }
    if (estado.etapa === 'erro') {
      if (status) status.textContent = estado.erro || estado.mensagem || tr('updates.error');
      if (botaoAtualizar) botaoAtualizar.disabled = !ultimaVerificacao?.pode_atualizar;
      pararPollingStatus();
      return;
    }
    if (estado.concluido) {
      if (status) status.textContent = estado.mensagem || tr('updates.started');
      pararPollingStatus();
    }
  }

  async function atualizarStatusAgora() {
    try {
      const resposta = await fetch('/api/atualizacao/status', { cache: 'no-store' });
      const dados = await resposta.json().catch(() => ({}));
      aplicarEstadoAtualizacao(dados.estado);
      if (window.GutenbergAtualizacoes?.atualizarStatusAgora) window.GutenbergAtualizacoes.atualizarStatusAgora();
      return dados.estado;
    } catch (_) {
      return null;
    }
  }

  function iniciarPollingStatus() {
    if (statusTimer) return;
    statusTimer = setInterval(atualizarStatusAgora, 900);
  }

  function pararPollingStatus() {
    if (!statusTimer) return;
    clearInterval(statusTimer);
    statusTimer = null;
  }

  async function verificarAtualizacao() {
    abrirModalAtualizacao();
    definirEstadoCarregando();
    try {
      const resposta = await fetch('/api/atualizacao/verificar?manual=1', { cache: 'no-store' });
      const dados = await resposta.json().catch(() => ({}));
      exibirResultado(dados);
      await atualizarStatusAgora();
    } catch (erro) {
      exibirResultado({ ok: false, erro: tr('updates.error'), detalhe: String(erro?.message || erro || '') });
    }
  }

  async function iniciarAtualizacao() {
    if (!ultimaVerificacao?.pode_atualizar) return;
    if (botaoAtualizar) botaoAtualizar.disabled = true;
    if (status) status.textContent = tr('updates.starting');
    try {
      const resposta = await fetch('/api/atualizacao/iniciar', { method: 'POST', cache: 'no-store' });
      const dados = await resposta.json().catch(() => ({}));
      if (!resposta.ok || !dados.ok) {
        if (status) status.textContent = dados.erro || tr('updates.error');
        if (botaoAtualizar) botaoAtualizar.disabled = !ultimaVerificacao?.pode_atualizar;
        return;
      }
      aplicarEstadoAtualizacao(dados.estado || { ativo: true, mensagem: dados.mensagem || tr('updates.downloading') });
      iniciarPollingStatus();
      if (window.GutenbergAtualizacoes?.renderizarPopup) {
        window.GutenbergAtualizacoes.renderizarPopup({ ...ultimaVerificacao, ...dados, estado: dados.estado });
      }
    } catch (erro) {
      if (status) status.textContent = tr('updates.error');
      if (descricao) descricao.textContent = String(erro?.message || erro || '');
      if (botaoAtualizar) botaoAtualizar.disabled = !ultimaVerificacao?.pode_atualizar;
    }
  }

  async function cancelarAtualizacaoModal() {
    botaoCancelar.disabled = true;
    if (status) status.textContent = tr('updates.canceling');
    try {
      await fetch('/api/atualizacao/cancelar', { method: 'POST', cache: 'no-store' });
    } catch (_) {}
    await atualizarStatusAgora();
  }

  botaoAbrir?.addEventListener('click', verificarAtualizacao);
  botaoAtualizar?.addEventListener('click', iniciarAtualizacao);
  botaoCancelar?.addEventListener('click', cancelarAtualizacaoModal);
  modal?.querySelectorAll('[data-close-update-modal]').forEach((elemento) => {
    elemento.addEventListener('click', fecharModalAtualizacao);
  });
  modal?.querySelector('[data-modal-card="true"]')?.addEventListener('click', (event) => event.stopPropagation());
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modal && !modal.classList.contains('oculto')) {
      event.preventDefault();
      fecharModalAtualizacao();
    }
  });
  atualizarStatusAgora();
})();
