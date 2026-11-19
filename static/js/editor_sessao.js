/**
 * Parte 5 — evita dois escritores locais do mesmo documento.
 * O Web Locks API coordena abas da MESMA origem/perfil. Não substitui
 * controle de revisões no servidor para dispositivos/perfis diferentes.
 */
(function () {
  'use strict';

  function criar({ tipo, slug, numero, editor, titulo, status, antesDeLiberar }) {
    if (!editor || !tipo || !slug || !numero ||
        typeof navigator.locks?.request !== 'function') return null;

    const chave = `gutenberg:editor:v1:${tipo}:${encodeURIComponent(String(slug))}:${numero}`;
    const pt = (document.documentElement.lang || 'pt').toLowerCase().startsWith('pt');
    const textos = pt ? {
      aviso: 'Este texto já está aberto para edição em outra aba. Para evitar sobrescrever alterações, esta aba está em modo de leitura.',
      recarregar: 'Recarregar para editar',
      aguardar: 'Verificando outra aba…',
      bloqueado: 'Somente leitura — aberto em outra aba',
    } : {
      aviso: 'This document is already being edited in another tab. To avoid overwriting changes, this tab is read-only.',
      recarregar: 'Reload to edit',
      aguardar: 'Checking other tabs…',
      bloqueado: 'Read only — open in another tab',
    };
    const conteudoOriginal = editor.getAttribute('contenteditable');
    const tituloOriginalmenteDesabilitado = Boolean(titulo?.disabled);
    let estado = 'verificando';
    let soltarLock = null;
    let encerrado = false;
    const callbacks = [];

    function aplicarBloqueio(bloqueado) {
      editor.setAttribute('contenteditable', bloqueado ? 'false' : (conteudoOriginal ?? 'true'));
      if (titulo) titulo.disabled = bloqueado || tituloOriginalmenteDesabilitado;
      document.body?.classList.toggle('editor-sessao-bloqueada', bloqueado);
    }

    function avisarConflito() {
      if (!document.body || document.querySelector('.editor-sessao-aviso')) return;
      const aviso = document.createElement('aside');
      aviso.className = 'editor-sessao-aviso';
      aviso.setAttribute('role', 'alert');
      const mensagem = document.createElement('p');
      mensagem.textContent = textos.aviso;
      const botao = document.createElement('button');
      botao.type = 'button';
      botao.textContent = textos.recarregar;
      // Sempre recarregar o conteúdo do servidor antes de tentar tomar o lock.
      // Reabilitar esta aba sem reload poderia sobrescrever uma versão mais nova.
      botao.addEventListener('click', () => window.location.reload());
      aviso.append(mensagem, botao);
      document.body.appendChild(aviso);
    }

    aplicarBloqueio(true);
    void navigator.locks.request(chave, { mode: 'exclusive', ifAvailable: true }, (lock) => {
      if (encerrado || !lock) {
        if (!encerrado) {
          estado = 'bloqueado';
          aplicarBloqueio(true);
          if (status) status.textContent = textos.bloqueado;
          avisarConflito();
        }
        return;
      }
      estado = 'ativo';
      aplicarBloqueio(false);
      callbacks.splice(0).forEach(fn => {
        try { fn(); } catch (e) { console.error('Falha na inicialização da sessão de edição', e); }
      });
      // O lock fica retido enquanto a aba permanecer aberta, inclusive oculta.
      // Ao fechá-la, o navegador também libera o lock automaticamente.
      return new Promise(resolve => { soltarLock = resolve; });
    }).catch((erro) => {
      if (encerrado) return;
      estado = 'bloqueado';
      aplicarBloqueio(true);
      if (status) status.textContent = textos.bloqueado;
      console.warn('Não foi possível reservar a sessão de edição:', erro);
      avisarConflito();
    });

    function aoAdquirir(callback) {
      if (typeof callback !== 'function') return;
      if (estado === 'ativo') callback();
      else if (estado === 'verificando') callbacks.push(callback);
    }

    window.addEventListener('pagehide', () => {
      // A cópia pendente PRECISA ser gravada antes de bloquear os callbacks
      // e liberar o lock; os ouvintes de recuperação são registrados depois.
      if (estado === 'ativo') {
        try { antesDeLiberar?.(); } catch (e) { console.warn('Falha na cópia ao fechar:', e); }
      }
      encerrado = true;
      estado = 'encerrado';
      aplicarBloqueio(true);
      if (soltarLock) { soltarLock(); soltarLock = null; }
    });
    // O histórico bfcache conserva objetos JS; a página precisa recuperar
    // a versão atual do servidor E obter um novo lock antes de voltar a editar.
    window.addEventListener('pageshow', (event) => {
      if (event.persisted) window.location.reload();
    });
    return { podeSalvar: () => estado === 'ativo', aoAdquirir, estado: () => estado };
  }

  window.GutenbergSessaoEditor = { criar };
}());
