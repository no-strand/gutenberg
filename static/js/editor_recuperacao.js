/**
 * Cópia local de segurança dos editores EPUB/roteiro.
 * Não substitui o autosave no servidor e NUNCA restaura sem autorização.
 * O HTML da cópia não é introduzido no DOM até o usuário escolher Recuperar.
 */
(function () {
  'use strict';
  const PREFIXO = 'gutenberg:rascunho-local:v1:';
  const LIMITE_BYTES_APROX = 3 * 1024 * 1024;
  const ATRASO_COPIA_MS = 280;

  function criar({ tipo, slug, numero, lerPayload, restaurar, aoRetomar, podeGravar }) {
    if (!tipo || !slug || !numero || typeof lerPayload !== 'function' || typeof restaurar !== 'function') return null;
    const chave = `${PREFIXO}${tipo}:${encodeURIComponent(String(slug))}:${numero}`;
    let ultimoConfirmado = '';
    let timerCopia = 0;
    let copiaPendente = null;
    let aviso = null;
    let editadoDepoisDoAviso = false;
    let erroDeArmazenamento = false;
    const pt = (document.documentElement.lang || 'pt').toLowerCase().startsWith('pt');
    const frases = pt ? {
      aviso: 'Há uma cópia local deste texto que pode conter alterações não salvas.',
      recuperar: 'Recuperar cópia', descartar: 'Descartar cópia',
      conflito: 'Você já alterou o editor nesta sessão. Recuperar substituirá o texto atual. Continuar?',
      erro: 'Não foi possível guardar uma cópia local. Verifique o espaço do navegador e a conexão.',
    } : {
      aviso: 'A local draft may contain changes that were not saved.',
      recuperar: 'Restore draft', descartar: 'Discard draft',
      conflito: 'You have edited this document in this session. Restoring will replace those edits. Continue?',
      erro: 'Unable to store a local draft. Check browser storage and your connection.',
    };

    function lerCopia() {
      try {
        const valor = window.localStorage.getItem(chave);
        if (!valor) return null;
        const copia = JSON.parse(valor);
        if (copia?.versao !== 1 || typeof copia.payload !== 'string') return null;
        const dados = JSON.parse(copia.payload);
        if (typeof dados?.html !== 'string' || typeof dados?.titulo !== 'string') return null;
        return copia;
      } catch (_) { return null; }
    }

    function removerCopiaSeIgual(payload) {
      try {
        // Uma resposta atrasada não pode apagar o rascunho de uma edição mais nova.
        if (lerCopia()?.payload === payload) window.localStorage.removeItem(chave);
      } catch (_) { /* cópia pode permanecer para recuperação manual */ }
    }

    function informarErro() {
      if (erroDeArmazenamento || !document.body) return;
      erroDeArmazenamento = true;
      const mensagem = document.createElement('p');
      mensagem.className = 'editor-recuperacao-erro';
      mensagem.setAttribute('role', 'alert');
      mensagem.textContent = frases.erro;
      document.body.appendChild(mensagem);
    }

    function gravarCopia() {
      timerCopia = 0;
      if (podeGravar && !podeGravar()) return;
      if (copiaPendente) return; // Não sobrescrever cópia antiga enquanto o usuário decide.
      let payload;
      try { payload = lerPayload(); } catch (_) { return; }
      if (!payload) return;
      if (payload === ultimoConfirmado) {
        // Desfazer todas as edições locais não deve deixar uma cópia antiga
        // reaparecer como se ainda houvesse mudanças pendentes.
        try { if (!copiaPendente) window.localStorage.removeItem(chave); } catch (_) {}
        return;
      }
      const registro = JSON.stringify({ versao: 1, atualizadoEm: Date.now(), payload });
      if (registro.length > LIMITE_BYTES_APROX) { informarErro(); return; }
      try { window.localStorage.setItem(chave, registro); }
      catch (_) { informarErro(); }
    }

    function agendarCopia() {
      if (copiaPendente) editadoDepoisDoAviso = true;
      clearTimeout(timerCopia);
      timerCopia = window.setTimeout(gravarCopia, ATRASO_COPIA_MS);
    }

    function copiarAgora() {
      clearTimeout(timerCopia);
      gravarCopia();
    }

    function esconderAviso() {
      aviso?.remove();
      aviso = null;
      copiaPendente = null;
    }

    function mostrarAviso() {
      if (podeGravar && !podeGravar()) return;
      if (!copiaPendente || aviso || !document.body) return;
      const el = document.createElement('div');
      el.className = 'editor-recuperacao-aviso';
      el.setAttribute('role', 'status');
      const mensagem = document.createElement('p');
      mensagem.textContent = frases.aviso;
      const botoes = document.createElement('div');
      botoes.className = 'editor-recuperacao-acoes';
      const recuperar = document.createElement('button');
      recuperar.type = 'button';
      recuperar.textContent = frases.recuperar;
      recuperar.className = 'editor-recuperacao-restaurar';
      recuperar.addEventListener('click', () => {
        if ((podeGravar && !podeGravar()) || !copiaPendente) return;
        if (editadoDepoisDoAviso && !window.confirm(frases.conflito)) return;
        let dados;
        try { dados = JSON.parse(copiaPendente.payload); } catch (_) { return; }
        // A cópia permanece intacta caso a restauração falhe.
        try { restaurar(dados); } catch (e) { console.error('Falha ao restaurar rascunho local', e); return; }
        esconderAviso();
        agendarCopia();
        copiarAgora();
      });
      const descartar = document.createElement('button');
      descartar.type = 'button';
      descartar.textContent = frases.descartar;
      descartar.className = 'editor-recuperacao-descartar';
      descartar.addEventListener('click', () => {
        if (podeGravar && !podeGravar()) return;
        removerCopiaSeIgual(copiaPendente?.payload);
        esconderAviso();
        if (editadoDepoisDoAviso) { agendarCopia(); copiarAgora(); }
      });
      botoes.append(recuperar, descartar);
      el.append(mensagem, botoes);
      document.body.appendChild(el);
      aviso = el;
    }

    function iniciar(payloadServidor) {
      ultimoConfirmado = payloadServidor || '';
      const copia = lerCopia();
      if (copia && copia.payload !== ultimoConfirmado) {
        copiaPendente = copia;
        mostrarAviso();
      } else if (copia) {
        removerCopiaSeIgual(copia.payload);
      }
    }

    function confirmarSalvamento(payload) {
      ultimoConfirmado = payload;
      if (!copiaPendente) removerCopiaSeIgual(payload);
    }

    document.addEventListener('visibilitychange', () => {
      if (document.hidden) { copiarAgora(); aoRetomar?.(); }
    });
    window.addEventListener('pagehide', copiarAgora);
    window.addEventListener('beforeunload', copiarAgora);
    window.addEventListener('online', () => aoRetomar?.());
    return { iniciar, agendarCopia, copiarAgora, confirmarSalvamento, lerCopia };
  }

  window.GutenbergRascunhoLocal = { criar };
}());
