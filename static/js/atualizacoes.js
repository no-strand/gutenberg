(function configurarAtualizacoesGlobais(){
  const tr = (key, vars = {}) => (window.t ? window.t(key, vars) : key);
  const CHAVE_ULTIMA_VERIFICACAO = 'gutenberg-atualizacao-semanal-ultima-verificacao';
  const CHAVE_POPUP = 'gutenberg-atualizacao-popup-dados';
  const CHAVE_DISPENSADA = 'gutenberg-atualizacao-popup-dispensada';
  const CHAVE_OCULTA = 'gutenberg-atualizacao-popup-oculta';
  const UMA_SEMANA_MS = 7 * 24 * 60 * 60 * 1000;
  let pollTimer = null;
  let popupAtual = null;
  let ultimoPayloadPopup = null;

  function lerJSON(chave, fallback = null){
    try { return JSON.parse(localStorage.getItem(chave) || 'null') ?? fallback; } catch (_) { return fallback; }
  }

  function salvarJSON(chave, valor){
    try { localStorage.setItem(chave, JSON.stringify(valor)); } catch (_) {}
  }

  function remover(chave){
    try { localStorage.removeItem(chave); } catch (_) {}
  }

  function deveVerificar(){
    if (window.location.pathname !== '/') return false;
    try {
      const ultimo = Number(localStorage.getItem(CHAVE_ULTIMA_VERIFICACAO) || 0);
      return !ultimo || (Date.now() - ultimo) >= UMA_SEMANA_MS;
    } catch (_) {
      return true;
    }
  }

  function marcarVerificado(){
    try { localStorage.setItem(CHAVE_ULTIMA_VERIFICACAO, String(Date.now())); } catch (_) {}
  }

  function versaoDispensada(versao){
    const dados = lerJSON(CHAVE_DISPENSADA, {});
    return Boolean(versao && dados?.versao === versao);
  }

  function dispensarVersao(versao){
    if (versao) salvarJSON(CHAVE_DISPENSADA, {versao, quando: Date.now()});
  }

  function ocultarVersao(versao){
    if (versao) salvarJSON(CHAVE_OCULTA, {versao, quando: Date.now()});
  }

  function versaoOculta(versao){
    const dados = lerJSON(CHAVE_OCULTA, {});
    return Boolean(versao && dados?.versao === versao);
  }

  function limparOcultoSeOutraVersao(versao){
    const dados = lerJSON(CHAVE_OCULTA, {});
    if (dados?.versao && dados.versao !== versao) remover(CHAVE_OCULTA);
  }

  function limparPopupVisual(){
    document.querySelectorAll('.atualizacao-popup').forEach((item) => item.remove());
    popupAtual = null;
  }

  function persistirPopupPayload(dados){
    if (!dados || dados.silencioso || dados.atualizacao_indisponivel) return;
    const estado = dados.estado || null;
    if (dados.ha_atualizacao || estado?.ativo || estado?.etapa === 'erro' || estado?.etapa === 'cancelado' || estado?.concluido) {
      ultimoPayloadPopup = dados;
      salvarJSON(CHAVE_POPUP, dados);
    }
  }

  function textoProgresso(estado){
    if (!estado) return '';
    const baixado = estado.bytes_baixados_formatado || '';
    const total = estado.bytes_total_formatado || '';
    if (baixado && total) return `${baixado} / ${total}`;
    if (total) return `${estado.progresso || 0}% • ${total}`;
    return `${estado.progresso || 0}%`;
  }

  function criarBarraProgresso(estado){
    const wrap = document.createElement('div');
    wrap.className = 'atualizacao-progresso-wrap';
    const barra = document.createElement('div');
    barra.className = 'atualizacao-progresso-barra';
    const interno = document.createElement('span');
    interno.style.width = `${Math.max(0, Math.min(100, Number(estado?.progresso || 0)))}%`;
    barra.appendChild(interno);
    const detalhe = document.createElement('small');
    detalhe.className = 'atualizacao-progresso-texto';
    detalhe.textContent = textoProgresso(estado);
    wrap.appendChild(barra);
    wrap.appendChild(detalhe);
    return wrap;
  }

  async function cancelarAtualizacao(texto, botao){
    if (botao) botao.disabled = true;
    if (texto) texto.textContent = tr('updates.canceling');
    try {
      await fetch('/api/atualizacao/cancelar', {method:'POST', cache:'no-store'});
    } catch (_) {}
    await atualizarStatusAgora();
  }

  function renderizarPopup(dados, {persistir = true} = {}){
    if (!dados || dados.silencioso || dados.atualizacao_indisponivel) return;
    const estado = dados.estado || null;
    const versao = dados.versao_remota || estado?.versao || dados.versao || '';
    const ativo = Boolean(estado?.ativo);
    limparOcultoSeOutraVersao(versao);
    if ((ativo || dados.ha_atualizacao || estado?.concluido || estado?.etapa === 'erro' || estado?.etapa === 'cancelado') && versaoOculta(versao)) return;
    if (!ativo && dados.ha_atualizacao && versaoDispensada(versao)) return;
    if (persistir) {
      persistirPopupPayload(dados);
    } else {
      ultimoPayloadPopup = dados;
    }

    limparPopupVisual();
    const popup = document.createElement('aside');
    popup.className = 'atualizacao-popup';
    popup.setAttribute('role', 'status');

    const titulo = document.createElement('strong');
    const texto = document.createElement('p');
    const acoes = document.createElement('div');
    acoes.className = 'atualizacao-popup-acoes';

    const botaoFechar = document.createElement('button');
    botaoFechar.type = 'button';
    botaoFechar.className = 'botao-secundario atualizacao-popup-fechar';
    botaoFechar.textContent = dados?.ha_atualizacao ? tr('updates.dismiss') : tr('common.close');
    botaoFechar.addEventListener('click', () => {
      ocultarVersao(versao);
      if (!ativo) dispensarVersao(versao);
      remover(CHAVE_POPUP);
      limparPopupVisual();
    });

    if (estado?.ativo) {
      titulo.textContent = tr('updates.toast_available_title');
      texto.textContent = estado.mensagem || tr('updates.downloading');
      popup.classList.add('disponivel');
      acoes.appendChild(botaoFechar);
      const botaoCancelar = document.createElement('button');
      botaoCancelar.type = 'button';
      botaoCancelar.className = 'botao-secundario atualizacao-popup-cancelar';
      botaoCancelar.textContent = tr('updates.cancel');
      botaoCancelar.disabled = Boolean(estado.cancelando);
      botaoCancelar.addEventListener('click', () => cancelarAtualizacao(texto, botaoCancelar));
      acoes.appendChild(botaoCancelar);
      popup.appendChild(titulo);
      popup.appendChild(texto);
      popup.appendChild(criarBarraProgresso(estado));
      popup.appendChild(acoes);
      document.body.appendChild(popup);
      popupAtual = popup;
      requestAnimationFrame(() => popup.classList.add('visivel'));
      iniciarPollingStatus();
      return;
    }

    if (estado?.etapa === 'cancelado') {
      titulo.textContent = tr('updates.toast_error_title');
      texto.textContent = estado.mensagem || tr('updates.cancelled');
      popup.classList.add('erro');
      acoes.appendChild(botaoFechar);
    } else if (estado?.etapa === 'erro') {
      titulo.textContent = tr('updates.toast_error_title');
      texto.textContent = estado.erro || estado.mensagem || tr('updates.error');
      popup.classList.add('erro');
      acoes.appendChild(botaoFechar);
    } else if (estado?.concluido) {
      titulo.textContent = tr('updates.toast_updated_title');
      texto.textContent = estado.mensagem || tr('updates.started');
      popup.classList.add('atualizado');
      acoes.appendChild(botaoFechar);
    } else if (!dados?.ok) {
      titulo.textContent = tr('updates.toast_error_title');
      texto.textContent = dados?.erro || tr('updates.toast_error_text');
      popup.classList.add('erro');
      acoes.appendChild(botaoFechar);
    } else if (dados.ha_atualizacao) {
      titulo.textContent = tr('updates.toast_available_title');
      texto.textContent = dados.pode_atualizar ? tr('updates.toast_available_text', {version: dados.versao_remota || ''}) : (dados.aviso || tr('updates.no_installer'));
      popup.classList.add('disponivel');
      const botaoAtualizar = document.createElement('button');
      botaoAtualizar.type = 'button';
      botaoAtualizar.className = 'botao-primario atualizacao-popup-atualizar';
      botaoAtualizar.textContent = tr('updates.update_now');
      botaoAtualizar.disabled = !dados.pode_atualizar;
      botaoAtualizar.addEventListener('click', async () => {
        botaoAtualizar.disabled = true;
        texto.textContent = tr('updates.starting');
        try {
          const resposta = await fetch('/api/atualizacao/iniciar', {method:'POST', cache:'no-store'});
          const retorno = await resposta.json().catch(() => ({}));
          if (!resposta.ok || !retorno.ok) {
            texto.textContent = retorno.erro || tr('updates.error');
            botaoAtualizar.disabled = !dados.pode_atualizar;
            return;
          }
          const proximo = {...dados, ...retorno, estado: retorno.estado || retorno?.estado_atualizacao || {ativo:true, mensagem: retorno.mensagem || tr('updates.downloading')}};
          renderizarPopup(proximo);
          iniciarPollingStatus();
        } catch (_) {
          texto.textContent = tr('updates.error');
          botaoAtualizar.disabled = !dados.pode_atualizar;
        }
      });
      acoes.appendChild(botaoFechar);
      acoes.appendChild(botaoAtualizar);
    } else {
      titulo.textContent = tr('updates.toast_updated_title');
      texto.textContent = tr('updates.toast_updated_text');
      popup.classList.add('atualizado');
      acoes.appendChild(botaoFechar);
      setTimeout(() => { if (popup.isConnected) popup.remove(); }, 8500);
    }

    popup.appendChild(titulo);
    popup.appendChild(texto);
    popup.appendChild(acoes);
    document.body.appendChild(popup);
    popupAtual = popup;
    requestAnimationFrame(() => popup.classList.add('visivel'));
  }

  async function atualizarStatusAgora(){
    try {
      const resposta = await fetch('/api/atualizacao/status', {cache:'no-store'});
      const dados = await resposta.json().catch(() => ({}));
      const estado = dados.estado;
      const ultima = dados.ultima_verificacao || {};
      if (!estado || (!estado.ativo && !estado.concluido && !estado.cancelado && estado.etapa !== 'erro')) {
        if (ultima?.ha_atualizacao) {
          const versaoUltima = ultima.versao_remota || ultima.versao || '';
          if (!versaoOculta(versaoUltima) && !versaoDispensada(versaoUltima)) {
            renderizarPopup(ultima);
          }
        }
        if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
        return estado;
      }
      if (estado.versao && versaoOculta(estado.versao)) return estado;
      const anterior = lerJSON(CHAVE_POPUP, {}) || ultima || {};
      const payload = {...anterior, ok: true, ha_atualizacao: true, estado, versao: estado.versao || anterior.versao || anterior.versao_remota};
      renderizarPopup(payload);
      if (!estado.ativo && pollTimer) { clearInterval(pollTimer); pollTimer = null; }
      return estado;
    } catch (_) {
      return null;
    }
  }

  function iniciarPollingStatus(){
    if (pollTimer) return;
    pollTimer = setInterval(atualizarStatusAgora, 900);
  }

  async function verificarAutomaticamente(){
    if (!deveVerificar()) return;
    marcarVerificado();
    try {
      const resposta = await fetch('/api/atualizacao/verificar?automatico=semanal', {cache:'no-store'});
      const dados = await resposta.json().catch(() => ({}));
      if (dados?.ha_atualizacao && dados?.versao_remota && !versaoDispensada(dados.versao_remota)) {
        renderizarPopup(dados);
      } else if (!dados?.ha_atualizacao && dados?.ok) {
        renderizarPopup(dados, {persistir:false});
      }
    } catch (_) {}
  }

  function restaurarPopup(){
    const dados = lerJSON(CHAVE_POPUP, null);
    const versao = dados?.versao_remota || dados?.estado?.versao || dados?.versao || '';
    if (dados && !versaoOculta(versao)) renderizarPopup(dados, {persistir:false});
  }

  window.GutenbergAtualizacoes = {
    atualizarStatusAgora,
    iniciarPollingStatus,
    renderizarPopup,
    limparPopupVisual,
  };

  window.addEventListener('pagehide', () => {
    if (popupAtual && ultimoPayloadPopup) persistirPopupPayload(ultimoPayloadPopup);
  });

  document.addEventListener('DOMContentLoaded', () => {
    restaurarPopup();
    setTimeout(atualizarStatusAgora, 350);
    verificarAutomaticamente();
  });
})();
