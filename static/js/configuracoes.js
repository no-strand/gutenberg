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
  const botaoAtualizar = document.getElementById('botaoIniciarAtualizacao');
  let ultimaVerificacao = null;

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

  function definirEstadoCarregando() {
    if (status) status.textContent = tr('updates.checking');
    info?.classList.add('oculto');
    notas?.classList.add('oculto');
    if (botaoAtualizar) {
      botaoAtualizar.disabled = true;
      botaoAtualizar.dataset.podeAtualizar = '0';
    }
  }

  function exibirResultado(dados) {
    ultimaVerificacao = dados || null;
    info?.classList.remove('oculto');
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

  async function verificarAtualizacao() {
    abrirModalAtualizacao();
    definirEstadoCarregando();
    try {
      const resposta = await fetch('/api/atualizacao/verificar?manual=1', { cache: 'no-store' });
      const dados = await resposta.json().catch(() => ({}));
      exibirResultado(dados);
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
      if (status) status.textContent = dados.mensagem || tr('updates.started');
      if (descricao) descricao.textContent = tr('updates.started');
    } catch (erro) {
      if (status) status.textContent = tr('updates.error');
      if (descricao) descricao.textContent = String(erro?.message || erro || '');
      if (botaoAtualizar) botaoAtualizar.disabled = !ultimaVerificacao?.pode_atualizar;
    }
  }

  botaoAbrir?.addEventListener('click', verificarAtualizacao);
  botaoAtualizar?.addEventListener('click', iniciarAtualizacao);
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
})();
