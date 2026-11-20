/** Etapa 3: conferência de publicação compartilhada pelos projetos e roteiros. */
(function () {
  'use strict';
  const traduzir = (key, vars) => window.t ? window.t(key, vars || {}) : key;

  function montar(formulario, modal) {
    if (!formulario || !modal) return;
    const painel = formulario.querySelector('.validacao-publicacao');
    if (!painel) return;
    const url = painel.dataset.urlValidacao;
    const resumo = painel.querySelector('#publicacaoResumo');
    const lista = painel.querySelector('#publicacaoLista');
    const confirmacao = painel.querySelector('#publicacaoAvisosConfirmacao');
    const aceite = painel.querySelector('#publicacaoAceitarAvisos');
    const atualizar = painel.querySelector('#publicacaoAtualizar');
    const botaoExportar = formulario.querySelector('button[type="submit"]');
    const status = formulario.querySelector('#statusExportacao');
    let ultimaAssinatura = null;
    let ultimaResposta = null;
    let sequencia = 0;
    let debounce = null;
    let emAndamento = false;
    let verificacaoPendente = false;

    function assinatura(dados) {
      return JSON.stringify((dados?.itens || []).map(item =>
        [item.nivel, item.codigo, item.contexto, item.detalhe]
      ));
    }
    function atualizarBotao() {
      const bloqueado = emAndamento || verificacaoPendente || !ultimaResposta || !ultimaResposta.aprovado
        || (ultimaResposta.avisos > 0 && !aceite.checked);
      if (botaoExportar) botaoExportar.disabled = Boolean(bloqueado);
    }
    function mostrar(dados) {
      const novaAssinatura = assinatura(dados);
      if (ultimaAssinatura !== novaAssinatura) aceite.checked = false;
      ultimaAssinatura = novaAssinatura;
      ultimaResposta = dados;
      resumo.textContent = dados.itens.length
        ? traduzir('publish.results', {errors: dados.erros, warnings: dados.avisos, documents: dados.documentos})
        : traduzir('publish.ready');
      resumo.classList.toggle('publicacao-bloqueado', !dados.aprovado);
      lista.replaceChildren();
      dados.itens.forEach(item => {
        const li = document.createElement('li');
        li.className = 'publicacao-item ' + (item.nivel === 'erro' ? 'erro' : 'aviso');
        const titulo = document.createElement('strong');
        titulo.textContent = (item.nivel === 'erro' ? '● ' : '◆ ') + item.titulo;
        const detalhe = document.createElement('p');
        detalhe.textContent = item.detalhe;
        li.append(titulo, detalhe);
        if (item.contexto) {
          const contexto = document.createElement('small');
          contexto.textContent = item.contexto;
          li.append(contexto);
        }
        lista.append(li);
      });
      confirmacao.hidden = dados.avisos === 0 || !dados.aprovado;
      if (!dados.aprovado) {
        status.textContent = traduzir('publish.blocking');
      } else if (status.textContent === traduzir('publish.blocking')) {
        status.textContent = '';
      }
      atualizarBotao();
    }

    async function verificar({forcar = false} = {}) {
      const numero = ++sequencia;
      emAndamento = true;
      verificacaoPendente = true;
      atualizarBotao();
      resumo.textContent = traduzir('publish.loading');
      try {
        const params = new URLSearchParams(new FormData(formulario));
        const resposta = await fetch(url + '?' + params.toString(), {cache: 'no-store'});
        if (!resposta.ok) throw new Error(traduzir('publish.error'));
        const dados = await resposta.json();
        if (!dados || !Array.isArray(dados.itens) || dados.ok !== true || !/^[0-9a-f]{64}$/.test(dados.assinatura || '')) throw new Error(traduzir('publish.error'));
        if (numero !== sequencia) return null; // descarta resposta de um formato anterior
        emAndamento = false;
        verificacaoPendente = false;
        mostrar(dados);
        return dados;
      } catch (erro) {
        if (numero !== sequencia) return null;
        ultimaResposta = null;
        ultimaAssinatura = null;
        emAndamento = false;
        verificacaoPendente = false;
        lista.replaceChildren();
        confirmacao.hidden = true;
        aceite.checked = false;
        resumo.textContent = erro.message || traduzir('publish.error');
        atualizarBotao();
        return null;
      }
    }

    function invalidar() {
      ultimaResposta = null;
      verificacaoPendente = true;
      aceite.checked = false;
      atualizarBotao();
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        if (!modal.classList.contains('oculto')) verificar();
      }, 140);
    }

    formulario.addEventListener('change', (event) => {
      if (event.target === aceite) return;
      invalidar();
    });
    document.getElementById('abrirModalExportacao')?.addEventListener('click', () => {
      ultimaResposta = null;
      ultimaAssinatura = null;
      aceite.checked = false;
      verificar();
    });
    aceite.addEventListener('change', atualizarBotao);
    atualizar.addEventListener('click', () => verificar({forcar: true}));
    atualizarBotao();

    async function antesDeExportar(params) {
      // Revalida imediatamente para capturar edições feitas em outra janela.
      const resposta = await verificar({forcar: true});
      if (!resposta || !resposta.aprovado) {
        status.textContent = resposta ? traduzir('publish.blocking') : traduzir('publish.error');
        return false;
      }
      if (resposta.avisos > 0 && !aceite.checked) {
        status.textContent = traduzir('publish.ack_required');
        return false;
      }
      params.set('validar', '1');
      if (resposta.avisos > 0) {
        params.set('confirmar_avisos', '1');
        params.set('assinatura_validacao', resposta.assinatura);
      }
      return true;
    }
    return {antesDeExportar, verificar};
  }

  let instancia = null;
  window.validacaoPublicacao = {
    montar(formulario, modal) {
      instancia = montar(formulario, modal);
      return instancia;
    },
    antesDeExportar(params) {
      return instancia ? instancia.antesDeExportar(params) : Promise.resolve(false);
    }
  };
})();
