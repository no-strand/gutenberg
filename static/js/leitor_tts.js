/* TTS local Kokoro: fila antecipada, cache em memória e destaque sincronizado. */
(() => {
  const botao = document.getElementById('botaoTtsLeitor');
  if (!botao) return;

  const area = document.getElementById('areaLeitura');
  const frame = document.getElementById('epubFrame');
  const cfg = window.LEITOR_CONFIG || {};

  // Mantemos vários trechos prontos à frente do áudio atual. A síntese acontece
  // no servidor enquanto o navegador reproduz o trecho corrente.
  const TAMANHO_FILA = 3;

  let trechos = [];
  let indice = 0;
  let audio = null;
  let tocando = false;
  let preparando = false;
  // Fica ativo somente enquanto o PRIMEIRO áudio da sessão está sendo
  // sintetizado/carregado. Os trechos seguintes usam o ícone normal para
  // evitar que o botão fique piscando entre segmentos pré-carregados.
  let carregandoPrimeiroAudio = false;
  let tokenExecucao = 0;

  // Guarda o ponto que originou a sessão atual. Ao pausar e rolar para cima,
  // o Play pode iniciar uma nova sessão a partir do novo parágrafo visível,
  // sem forçar o usuário a continuar do ponto anterior.
  let indiceInicioSessao = 0;
  let scrollYAoPausar = null;

  // index -> Promise<string> (Object URL). O Promise permite que vários pedidos
  // de pré-carregamento do mesmo trecho compartilhem uma única requisição.
  const cacheAudio = new Map();
  const urlsCriadas = new Set();

  // Diagnóstico persistente: os eventos técnicos do player são enviados ao
  // Flask e gravados junto com o diagnóstico do Kokoro em tts_debug.txt.
  // Nunca enviamos o texto do livro, apenas metadados de reprodução.
  function enviarLogTts(event, details = {}) {
    try {
      fetch('/api/tts/log', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({event, details}),
        keepalive: true
      }).catch(() => {});
    } catch (_) {}
  }

  function estadoAudio(extra = {}, alvo = audio) {
    if (!alvo) return {...extra, audioExiste: false};
    const erro = alvo.error;
    return {
      ...extra,
      audioExiste: true,
      paused: alvo.paused,
      ended: alvo.ended,
      readyState: alvo.readyState,
      networkState: alvo.networkState,
      muted: alvo.muted,
      volume: alvo.volume,
      playbackRate: alvo.playbackRate,
      currentTime: Number.isFinite(alvo.currentTime) ? Number(alvo.currentTime.toFixed(3)) : null,
      duration: Number.isFinite(alvo.duration) ? Number(alvo.duration.toFixed(3)) : null,
      mediaErrorCode: erro?.code ?? null,
      mediaErrorMessage: erro?.message ?? null
    };
  }

  enviarLogTts('player_script_iniciado', {
    userAgent: navigator.userAgent,
    language: cfg.ttsLanguage || 'pt_BR',
    speed: Number(cfg.ttsSpeed || 1),
    temIframe: Boolean(frame)
  });

  let verificandoModelosTts = false;
  let ultimoErroTtsAlertado = "";
  let ultimoErroTtsAlertadoEm = 0;

  function traduzir(chave, fallback) {
    try {
      const valor = typeof window.t === 'function' ? window.t(chave) : '';
      return valor && valor !== chave ? valor : fallback;
    } catch (_) {
      return fallback;
    }
  }

  async function verificarModelosTtsAntesDeReproduzir() {
    if (verificandoModelosTts) return false;
    verificandoModelosTts = true;
    botao.disabled = true;

    try {
      const resposta = await fetch('/api/tts/modelos/status', { cache: 'no-store' });
      const dados = await resposta.json().catch(() => ({}));
      const instalado = Boolean(resposta.ok && dados?.ok && dados?.estado?.instalado);
      if (instalado) {
        enviarLogTts('modelos_tts_verificados', { instalado: true });
        return true;
      }

      enviarLogTts('modelos_tts_ausentes', {
        instalado: false,
        modeloOk: Boolean(dados?.estado?.modelo?.ok),
        voicesOk: Boolean(dados?.estado?.voices?.ok)
      });

      const mensagem = traduzir(
        'reader.tts_models_missing',
        'Os arquivos de modelo do TTS não estão instalados ou estão incompletos. Abra Configurações e use “Baixar modelos TTS” antes de usar a leitura em voz alta.\n\nDeseja abrir Configurações agora?'
      );
      if (window.confirm(mensagem)) {
        window.location.href = '/configuracoes';
      }
      return false;
    } catch (erro) {
      enviarLogTts('modelos_tts_status_erro', {
        nome: erro?.name || '',
        mensagem: erro?.message || String(erro)
      });
      window.alert(traduzir(
        'reader.tts_models_status_error',
        'Não foi possível verificar os arquivos do TTS. Abra Configurações e confirme se os modelos estão instalados.'
      ));
      return false;
    } finally {
      verificandoModelosTts = false;
      botao.disabled = false;
    }
  }

  // Os trechos vivem no documento do iframe quando o leitor está no modo EPUB.
  // Por isso nunca procuramos esses elementos com document.querySelector().
  function documentoDosTrechos() {
    return frame?.contentDocument || area?.ownerDocument || document;
  }

  // Assim que a síntese termina, o próprio trecho vira um link discreto.
  // Não alteramos o texto: apenas acrescentamos o comportamento de navegação.
  function marcarTrechoPronto(idx) {
    const doc = documentoDosTrechos();
    const el = doc?.querySelector?.(`[data-tts-idx="${idx}"]`);
    if (!el) return;

    el.classList.add('tts-pronto');
    el.setAttribute('role', 'link');
    el.setAttribute('tabindex', '0');
    el.setAttribute('aria-label', 'Reproduzir este trecho');

    if (el.dataset.ttsLinkBound === 'true') return;
    el.dataset.ttsLinkBound = 'true';

    const ativar = async (evento) => {
      evento.preventDefault();
      evento.stopPropagation();
      const idxAtual = Number(el.dataset.ttsIdx);
      if (!Number.isInteger(idxAtual)) return;
      if (!(await verificarModelosTtsAntesDeReproduzir())) return;

      // Um clique em um trecho pronto passa a ser o novo ponto de leitura.
      // Invalidamos apenas a reprodução corrente; os demais áudios prontos
      // continuam no cache para que a navegação seja imediata.
      const token = ++tokenExecucao;
      pararAudio();
      tocando = false;
      preparando = false;
      carregandoPrimeiroAudio = false;
      indice = idxAtual;
      indiceInicioSessao = idxAtual;
      scrollYAoPausar = null;
      atualizarBotao();

      solicitarAudio(idxAtual, token)
        .then(() => tocarIndice(idxAtual, token))
        .catch(erroTts);
    };

    el.addEventListener('click', ativar);
    el.addEventListener('keydown', (evento) => {
      if (evento.key === 'Enter' || evento.key === ' ') ativar(evento);
    });
  }


  const raizConteudo = () => {
    if (frame) return frame.contentDocument?.body || null;
    return area || null;
  };

  // -------------------------------------------------------------------------
  // Limpeza do texto antes da síntese
  // -------------------------------------------------------------------------
  // O texto exibido nunca é alterado. Esta limpeza existe apenas para o TTS,
  // evitando que vocalizações, gaguejos e sons escritos de forma exagerada
  // sejam pronunciados literalmente pelo modelo.
  const SUBSTITUICOES_TTS = new Map([
    ['hmm', 'hum'],
    ['hmmm', 'hum'],
    ['hmmmm', 'hum'],
    ['hm', 'hum'],
    ['mmm', 'hum'],
    ['mmmm', 'hum'],
    ['mm-hm', 'hum'],
    ['mmhm', 'hum'],
    ['uh-huh', 'uh huh'],
    ['uhh', 'uh'],
    ['uhhh', 'uh'],
    ['ahhh', 'ah'],
    ['ahhhh', 'ah'],
    ['oohhh', 'oh'],
    ['ohhh', 'oh'],
    ['shh', ''],
    ['shhh', ''],
    ['psst', ''],
    ['tsk', ''],
  ]);

  const VOGAIS = /[aeiouyáàâãéêíóôõúü]/i;
  const LETRAS = /[a-záàâãéêíóôõúüç]/i;
  // Apóstrofos usados em contrações/possessivos ingleses. Mantemos todas
  // as variantes comuns para que formas como man's, wasn't e don't sejam
  // tratadas como uma única palavra.
  const APOSTROFOS = /['’‘ʼ＇]/u;

  function normalizarPalavraExagerada(palavra) {
    let valor = String(palavra || '');
    if (!valor) return '';

    // Sons como "aaaaahhhhh" são reduzidos para "ah". Só reduzimos
    // sequências de 3+ caracteres iguais, preservando palavras normais.
    valor = valor.replace(/(.)\1{2,}/giu, '$1');

    // Garante que as vocalizações mais comuns continuem pronunciáveis.
    const chave = valor.toLocaleLowerCase('en-US');
    if (SUBSTITUICOES_TTS.has(chave)) return SUBSTITUICOES_TTS.get(chave);
    return valor;
  }

  function tokenEhSomSemVogais(token) {
    const str = String(token || '');
    if (APOSTROFOS.test(str) || /y/i.test(str)) return false;

    const somenteLetras = str.replace(/[^\p{L}]/gu, '');
    if (!somenteLetras || VOGAIS.test(somenteLetras)) return false;
    if (somenteLetras.length === 1) return /^[bcdfghjklmnpqrstvwxyzç]$/iu.test(somenteLetras);

    return /^[bcdfghjklmnpqrstvwxyzç]+$/iu.test(somenteLetras);
}
function limparTextoParaTts(texto) {
    let valor = String(texto || '').replace(/\s+/g, ' ').trim();
    if (!valor) return '';

    // "W-Well", "H-Hey", etc.: remove a consoante isolada usada como
    // gaguejo antes do hífen. Não mexemos em hífens internos de palavras.
    valor = valor.replace(/(^|[\s("'“‘])([bcdfghjklmnpqrstvwxyzç])-(?=[A-ZÁÀÂÃÉÊÍÓÔÕÚÜ])/giu, '$1');

    // Processa palavras individualmente para não juntar palavras vizinhas
    // quando uma vocalização for descartada.
    const tokens = valor.split(/(\s+)/u);
    const saida = [];

    for (const token of tokens) {
      if (!token || /^\s+$/u.test(token)) {
        if (saida.length && token) saida.push(token);
        continue;
      }

      // Tokens sem nenhuma letra não formam uma palavra pronunciável.
      // Isso elimina marcadores como ~~ e ◇◇◇, mas números isolados são
      // preservados porque são conteúdo válido (ex.: "capitulo 20").
      if (!LETRAS.test(token)) {
        if (/\p{N}/u.test(token)) saida.push(token);
        continue;
      }

      // Captura a unidade lexical inteira. Apóstrofos internos são parte da
      // palavra em inglês (wasn’t, wasn't, don't, I'm, they've, etc.) e não
      // podem ser tratados como separadores. Hífens internos também são
      // preservados para palavras legítimas como "well-being".
      //
      // Isso é importante porque o filtro de sons consonantais deve analisar
      // a palavra completa. Antes desta proteção, uma contração podia ser
      // dividida em "wasn" + "’t", fazendo a segunda parte parecer uma
      // sequência consonantal isolada.
      // Remove somente dígitos que estejam colados a letras. Números
      // separados por espaço continuam intactos (ex.: "capitulo 20").
      // Fazemos as duas direções para cobrir "claro20", "20claro" e
      // casos mistos como "a1b2" sem remover números isolados.
      const tokenSemDigitosColados = token
        .replace(/(\p{L})\p{N}+/gu, '$1')
        .replace(/\p{N}+(\p{L})/gu, '$1');

      if (!LETRAS.test(tokenSemDigitosColados)) {
        if (/\p{N}/u.test(tokenSemDigitosColados)) saida.push(tokenSemDigitosColados);
        continue;
      }

      const match = tokenSemDigitosColados.match(/^(.*?)([\p{L}]+(?:['’‘ʼ＇][\p{L}]+)*['’‘ʼ＇]?)([^\p{L}]*)$/u);
      if (!match) {
        saida.push(token);
        continue;
      }

      const prefixo = match[1];
      const palavraOriginal = match[2];
      const sufixo = match[3];
      const chave = palavraOriginal.toLocaleLowerCase('en-US');

      if (SUBSTITUICOES_TTS.has(chave)) {
        const substituta = SUBSTITUICOES_TTS.get(chave);
        if (substituta) saida.push(prefixo + substituta + sufixo);
        else if (sufixo) saida.push(sufixo);
        continue;
      }

      // Números isolados continuam sendo falados (ex.: "capitulo 20"),
      // mas dígitos colados a uma palavra não fazem parte do texto a ser
      // pronunciado: "claro20" vira "claro", "20claro" vira "claro"
      // e "a1b2" vira "ab".
      const palavraSemDigitos = palavraOriginal.replace(/\p{N}+/gu, '');
      const palavra = normalizarPalavraExagerada(palavraSemDigitos);
      if (!palavra) {
        if (sufixo) saida.push(sufixo);
        continue;
      }

      // Qualquer palavra que contenha apóstrofo é preservada como unidade
      // lexical. Isso evita que possessivos e contrações inglesas, como
      // "man's", "James's", "wasn't", "don't" e "they're", sejam
      // confundidos com uma sequência consonantal isolada. O filtro de sons
      // sem vogais continua valendo normalmente para palavras sem apóstrofo.
      const possuiApostrofo = APOSTROFOS.test(palavraOriginal);
      if (!possuiApostrofo && tokenEhSomSemVogais(palavra)) {
        if (sufixo) saida.push(sufixo);
        continue;
      }

      saida.push(prefixo + palavra + sufixo);
    }

    valor = saida.join('').replace(/\s+([,.;:!?…])/gu, '$1').replace(/\s{2,}/gu, ' ').trim();
    return valor;
  }

  function dividirTexto(texto, maxPalavras = 30) {
    const limpo = texto.replace(/\s+/g, ' ').trim();
    if (!limpo) return [];

    const palavras = limpo.split(' ');
    const partes = [];
    let atual = [];
    let ultimoLimite = 0;

    for (const palavra of palavras) {
      atual.push(palavra);
      const qtd = atual.length;
      const terminaPontuacao = /[.,;:!?…]+[\x22'’”»)]*$/u.test(palavra);
      if (qtd >= maxPalavras && terminaPontuacao) {
        partes.push(atual.join(' '));
        atual = [];
        ultimoLimite = partes.length;
      } else if (qtd > maxPalavras && terminaPontuacao) {
        partes.push(atual.join(' '));
        atual = [];
      }
    }

    // Se um trecho ultrapassou o limite, continuamos até encontrar a
    // próxima pontuação forte/fraca. Assim o áudio não termina no meio de
    // uma frase só porque atingiu o limite de palavras.
    if (atual.length) partes.push(atual.join(' '));

    // Caso exista um bloco excepcionalmente longo sem qualquer pontuação,
    // ainda precisamos respeitar o limite para não enviar um texto enorme
    // ao Kokoro.
    const finais = [];
    for (const parte of partes) {
      const ws = parte.split(' ');
      if (ws.length <= maxPalavras || /[.,;:!?…]+[\x22'’”»)]*$/u.test(ws[ws.length - 1])) {
        finais.push(parte);
        continue;
      }
      for (let i = 0; i < ws.length; i += maxPalavras) finais.push(ws.slice(i, i + maxPalavras).join(' '));
    }
    return finais;
  }

  // Pausa natural entre trechos. O valor depende da pontuação no final do
  // trecho, aproximando a cadência de uma leitura humana.
  function calcularPausaNatural(texto) {
    const final = String(texto || '').trim();
    if (!final) return 0.18;

    // Ignora aspas/parênteses depois da pontuação para reconhecer corretamente
    // finais como: "...fim." ou "...fim!".
    const match = final.match(/([.!?…]+|[,;:])(?:["'’”»)]*)$/u);
    if (!match) return 0.25;

    const pontuacao = match[1];
    if (/[.!?…]/u.test(pontuacao)) {
      if (/…/u.test(pontuacao)) return 1.02;
      return 0.75;
    }
    if (/[,]/u.test(pontuacao)) return 0.42;
    return 0.52;
  }

  function esperar(ms, token) {
    return new Promise((resolve) => {
      const inicio = performance.now();
      const verificar = () => {
        if (token !== tokenExecucao) {
          resolve(false);
          return;
        }
        if (performance.now() - inicio >= ms) {
          resolve(true);
          return;
        }
        window.setTimeout(verificar, Math.min(40, ms));
      };
      window.setTimeout(verificar, Math.min(40, ms));
    });
  }

  function instalarEstiloDestaque(doc) {
    if (!doc) return;
    let style = doc.getElementById('tts-highlight-style');
    if (!style) {
      style = doc.createElement('style');
      style.id = 'tts-highlight-style';
      (doc.head || doc.documentElement).appendChild(style);
    }
    style.textContent = `
      .tts-trecho {
        transition: background-color .12s ease, box-shadow .12s ease, color .12s ease, text-decoration-color .12s ease;
        border-radius: 2px;
        -webkit-box-decoration-break: clone;
        box-decoration-break: clone;
      }
      .tts-trecho.tts-pronto {
        cursor: pointer;
        text-decoration-line: underline;
        text-decoration-style: dotted;
        text-decoration-thickness: 1px;
        text-underline-offset: 2px;
        text-decoration-color: #1976d2;
      }
      .tts-trecho.tts-pronto:hover,
      .tts-trecho.tts-pronto:focus-visible {
        text-decoration-thickness: 2px;
        text-decoration-color: #1565c0;
        outline: none;
      }
      .tts-trecho.tts-atual {
        background: rgba(255, 193, 7, .42) !important;
        color: inherit !important;
        box-shadow: 0 0 0 3px rgba(255, 193, 7, .16);
        text-decoration: none !important;
      }
    `;
  }

  function prepararTrechos() {
    const raiz = raizConteudo();
    if (!raiz) return [];

    instalarEstiloDestaque(raiz.ownerDocument);

    raiz.querySelectorAll('.tts-trecho').forEach((el) => {
      el.replaceWith(raiz.ownerDocument.createTextNode(el.textContent || ''));
    });

    const walker = raiz.ownerDocument.createTreeWalker(
      raiz,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode(node) {
          if (!node.nodeValue?.trim()) return NodeFilter.FILTER_REJECT;
          const pai = node.parentElement;
          if (!pai || ['SCRIPT', 'STYLE', 'NOSCRIPT', 'SVG'].includes(pai.tagName)) {
            return NodeFilter.FILTER_REJECT;
          }
          return NodeFilter.FILTER_ACCEPT;
        }
      }
    );

    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);

    const lista = [];
    nodes.forEach((node) => {
      const partes = dividirTexto(node.nodeValue || '');
      if (!partes.length) return;

      const frag = node.ownerDocument.createDocumentFragment();
      partes.forEach((texto, i) => {
        const textoTts = limparTextoParaTts(texto);
        const span = node.ownerDocument.createElement('span');
        span.className = 'tts-trecho';
        span.textContent = texto + (i < partes.length - 1 ? ' ' : '');

        // O texto visual permanece intacto; somente a versão enviada ao TTS
        // recebe a limpeza.
        span.dataset.ttsText = textoTts;
        frag.appendChild(span);

        // O índice é atribuído somente aos trechos que realmente entram na fila.
        // Assim, o vínculo entre link e áudio permanece estável mesmo quando
        // existem nós de texto que o filtro do TTS descarta.
        if (textoTts) {
          span.dataset.ttsIdx = String(lista.length);
          lista.push(span);
        }
      });
      node.parentNode.replaceChild(frag, node);
    });

    enviarLogTts('trechos_preparados', {quantidade: lista.length});
    return lista;
  }

  // Converte a posição de um elemento do conteúdo para coordenadas da
  // janela principal. Os dois leitores usam um iframe alto, enquanto a
  // rolagem real acontece no documento pai.
  function retanguloNaTela(el) {
    if (!el?.getBoundingClientRect) return null;
    const rect = el.getBoundingClientRect();

    if (frame && el.ownerDocument === frame.contentDocument) {
      const rectFrame = frame.getBoundingClientRect();
      return {
        top: rectFrame.top + rect.top,
        bottom: rectFrame.top + rect.bottom,
        left: rectFrame.left + rect.left,
        right: rectFrame.left + rect.right,
        width: rect.width,
        height: rect.height,
      };
    }

    return {
      top: rect.top,
      bottom: rect.bottom,
      left: rect.left,
      right: rect.right,
      width: rect.width,
      height: rect.height,
    };
  }

  // A barra superior é sticky no desktop. Uma parte do texto que esteja
  // geometricamente dentro da viewport, porém atrás dessa barra, não conta
  // como conteúdo efetivamente mostrado ao leitor.
  function limiteSuperiorConteudoVisivel() {
    let limite = 0;
    const topo = document.querySelector('.topo-leitor');
    if (!topo) return limite;

    const estilo = window.getComputedStyle?.(topo);
    if (!['sticky', 'fixed'].includes(estilo?.position)) return limite;

    const rect = topo.getBoundingClientRect();
    if (rect.bottom > 0 && rect.top < window.innerHeight) {
      limite = Math.max(limite, Math.min(window.innerHeight, rect.bottom + 8));
    }
    return limite;
  }

  function elementoEstaVisivelNaTela(el, topoVisivel, baseVisivel) {
    const rect = retanguloNaTela(el);
    if (!rect || rect.height <= 0 || rect.width <= 0) return false;
    return rect.bottom > topoVisivel && rect.top < baseVisivel;
  }

  // Determina de onde uma NOVA sessão de TTS deve começar. A prioridade é o
  // primeiro parágrafo (ou bloco textual equivalente) atualmente mostrado na
  // tela. Mesmo que só a parte final do parágrafo esteja visível, retornamos o
  // primeiro trecho TTS dele para que a leitura comece no início do parágrafo.
  // Caso o EPUB não use tags semânticas de parágrafo, usamos o primeiro trecho
  // TTS efetivamente visível como fallback.
  function calcularIndiceInicialVisivel() {
    if (!trechos.length) return 0;

    const topoVisivel = limiteSuperiorConteudoVisivel();
    const baseVisivel = Math.max(topoVisivel, window.innerHeight || document.documentElement.clientHeight || 0);
    const blocosVistos = new Set();

    for (const trecho of trechos) {
      const bloco = trecho.closest?.('p, li, blockquote, dd, dt');
      if (!bloco || blocosVistos.has(bloco)) continue;
      blocosVistos.add(bloco);

      if (!elementoEstaVisivelNaTela(bloco, topoVisivel, baseVisivel)) continue;

      const primeiro = bloco.querySelector?.('[data-tts-idx]');
      const idx = Number(primeiro?.dataset?.ttsIdx);
      if (Number.isInteger(idx) && idx >= 0 && idx < trechos.length) {
        enviarLogTts('tts_inicio_pela_tela', {
          indice: idx,
          origem: 'primeiro_paragrafo_visivel',
          topoVisivel: Math.round(topoVisivel),
        });
        return idx;
      }
    }

    for (let i = 0; i < trechos.length; i++) {
      if (elementoEstaVisivelNaTela(trechos[i], topoVisivel, baseVisivel)) {
        enviarLogTts('tts_inicio_pela_tela', {
          indice: i,
          origem: 'primeiro_trecho_visivel',
          topoVisivel: Math.round(topoVisivel),
        });
        return i;
      }
    }

    // Se o conteúdo ainda estiver terminando de ajustar o layout, usa o
    // primeiro trecho como fallback seguro, preservando o comportamento antigo.
    enviarLogTts('tts_inicio_pela_tela', {indice: 0, origem: 'fallback_inicio'});
    return 0;
  }

  function posicaoVerticalLeitor() {
    const scroller = document.scrollingElement || document.documentElement;
    const valor = Number(window.scrollY ?? scroller?.scrollTop ?? 0);
    return Number.isFinite(valor) ? valor : 0;
  }

  function registrarPausaParaRetomada() {
    scrollYAoPausar = posicaoVerticalLeitor();
    enviarLogTts('tts_pausa_posicao_registrada', {
      indice,
      indiceInicioSessao,
      scrollY: Math.round(scrollYAoPausar),
    });
  }

  // Só troca o ponto de leitura se, depois da pausa, o usuário realmente
  // rolou a página para cima E o primeiro parágrafo visível está antes do
  // ponto que iniciou a sessão atual. Isso evita reinícios acidentais apenas
  // porque o trecho pausado está centralizado e há texto anterior na viewport.
  function calcularIndiceReinicioAposPausa() {
    if (scrollYAoPausar === null || !trechos.length) return null;

    const scrollAtual = posicaoVerticalLeitor();
    if (scrollAtual >= scrollYAoPausar - 4) return null;

    const indiceVisivel = calcularIndiceInicialVisivel();
    if (!Number.isInteger(indiceVisivel) || indiceVisivel >= indiceInicioSessao) {
      return null;
    }

    return indiceVisivel;
  }

  function limparDestaque() {
    trechos.forEach((el) => el.classList.remove('tts-atual'));
  }

  function atualizarBotao() {
    const ativo = tocando || preparando;

    if (carregandoPrimeiroAudio) {
      botao.dataset.estado = 'loading';
      botao.setAttribute('aria-pressed', 'true');
      botao.setAttribute('aria-busy', 'true');
      botao.title = 'Preparando primeiro áudio...';
      botao.setAttribute('aria-label', 'Preparando primeiro áudio. Clique para cancelar.');

      const icon = botao.querySelector('.icone-svg');
      if (icon) {
        icon.innerHTML = '<span class="tts-loading-spinner" aria-hidden="true"></span>';
      }
      return;
    }

    botao.dataset.estado = tocando ? 'playing' : 'paused';
    botao.setAttribute('aria-pressed', ativo ? 'true' : 'false');
    botao.removeAttribute('aria-busy');
    botao.title = tocando ? 'Pausar leitura em voz alta' : 'Ler em voz alta';
    botao.setAttribute('aria-label', botao.title);

    const icon = botao.querySelector('.icone-svg');
    if (icon) {
      icon.innerHTML = tocando
        ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 5v14M17 5v14"/></svg>'
        : '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 5 11 7-11 7z"/></svg>';
    }
  }

  function liberarCacheAudio() {
    // Os itens do cache são Promises; os Object URLs efetivamente criados
    // ficam em urlsCriadas. Revoga todos antes de limpar para não acumular
    // áudio órfão quando uma sessão é reiniciada.
    urlsCriadas.forEach((url) => {
      try { URL.revokeObjectURL(url); } catch (_) {}
    });
    cacheAudio.clear();
    urlsCriadas.clear();
  }

  function pararAudio() {
    if (!audio) return;
    enviarLogTts('audio_parar', estadoAudio({indice}));
    audio.onplay = null;
    audio.onended = null;
    audio.onerror = null;
    audio.pause();
    audio.removeAttribute('src');
    audio.load();
    audio = null;
  }

  async function gerarAudio(texto, token, idx) {
    const inicio = performance.now();
    enviarLogTts('fetch_inicio', {
      indice: idx,
      token,
      chars: String(texto || '').length,
      language: cfg.ttsLanguage || 'pt_BR',
      speed: Number(cfg.ttsSpeed || 1)
    });

    let resposta;
    try {
      resposta = await fetch('/api/tts/kokoro', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          text: texto,
          language: cfg.ttsLanguage || 'pt_BR',
          fallback_language: cfg.ttsFallbackLanguage || 'pt_BR',
          speed: Number(cfg.ttsSpeed || 1)
        })
      });
    } catch (erro) {
      enviarLogTts('fetch_excecao', {
        indice: idx,
        nome: erro?.name || '',
        mensagem: erro?.message || String(erro),
        duracaoMs: Math.round(performance.now() - inicio)
      });
      throw erro;
    }

    enviarLogTts('fetch_resposta', {
      indice: idx,
      status: resposta.status,
      ok: resposta.ok,
      contentType: resposta.headers.get('content-type'),
      contentLength: resposta.headers.get('content-length'),
      serverAudioBytes: resposta.headers.get('x-gutenberg-tts-bytes'),
      duracaoMs: Math.round(performance.now() - inicio)
    });

    if (token !== tokenExecucao) {
      enviarLogTts('fetch_descartado_token', {indice: idx, token, tokenAtual: tokenExecucao});
      throw new Error('TTS interrompido.');
    }

    if (!resposta.ok) {
      let mensagem = 'Não foi possível gerar o áudio.';
      let caminhoLog = '';
      try {
        const dadosErro = await resposta.json();
        mensagem = dadosErro?.erro || mensagem;
        caminhoLog = String(dadosErro?.log || '').trim();
      } catch (_) {}
      if (caminhoLog) {
        mensagem += `\n\nLog de diagnóstico: ${caminhoLog}`;
      }
      enviarLogTts('fetch_erro_http', {indice: idx, status: resposta.status, mensagem});
      throw new Error(mensagem);
    }

    let blob;
    try {
      blob = await resposta.blob();
    } catch (erro) {
      enviarLogTts('blob_excecao', {indice: idx, nome: erro?.name || '', mensagem: erro?.message || String(erro)});
      throw erro;
    }

    enviarLogTts('blob_pronto', {
      indice: idx,
      bytes: blob.size,
      type: blob.type,
      duracaoMs: Math.round(performance.now() - inicio)
    });

    if (!blob.size) {
      const erro = new Error('O servidor retornou um WAV vazio.');
      enviarLogTts('blob_vazio', {indice: idx, type: blob.type});
      throw erro;
    }

    if (token !== tokenExecucao) {
      enviarLogTts('blob_descartado_token', {indice: idx, token, tokenAtual: tokenExecucao});
      throw new Error('TTS interrompido.');
    }

    const url = URL.createObjectURL(blob);
    urlsCriadas.add(url);
    enviarLogTts('object_url_criada', {indice: idx, bytes: blob.size});
    return url;
  }

  function solicitarAudio(i, token) {
    if (i < 0 || i >= trechos.length) return Promise.resolve(null);
    if (cacheAudio.has(i)) return cacheAudio.get(i);

    const promise = gerarAudio(trechos[i].dataset.ttsText || trechos[i].textContent || '', token, i)
      .then((url) => {
        // Este é o ponto em que o áudio realmente está pronto no navegador.
        // A marcação é feita aqui (e não no fim da fila), permitindo ao usuário
        // clicar no trecho assim que a síntese individual terminar.
        if (token === tokenExecucao) marcarTrechoPronto(i);
        return url;
      })
      .catch((erro) => {
        cacheAudio.delete(i);
        throw erro;
      });

    cacheAudio.set(i, promise);
    return promise;
  }

  function preCarregarFrente(i, token) {
    // Dispara as próximas sínteses sem esperar uma pela outra. No servidor,
    // a inferência do modelo é serializada com segurança; enquanto isso o
    // navegador já está reproduzindo o áudio anterior.
    for (let n = 1; n <= TAMANHO_FILA; n++) {
      const alvo = i + n;
      if (alvo >= trechos.length) break;
      solicitarAudio(alvo, token).catch((erro) => {
        if (token === tokenExecucao) {
          console.debug('Pré-carregamento TTS:', erro);
          enviarLogTts('preload_erro', {indice: alvo, nome: erro?.name || '', mensagem: erro?.message || String(erro)});
        }
      });
    }
  }

  async function tocarIndice(i, token) {
    enviarLogTts('tocar_indice_inicio', {indice: i, token, tokenAtual: tokenExecucao, totalTrechos: trechos.length});
    if (token !== tokenExecucao) {
      enviarLogTts('tocar_indice_cancelado_token', {indice: i, token, tokenAtual: tokenExecucao});
      return;
    }

    if (i >= trechos.length) {
      pararAudio();
      tocando = false;
      preparando = false;
      carregandoPrimeiroAudio = false;
      indice = 0;
      indiceInicioSessao = 0;
      scrollYAoPausar = null;
      liberarCacheAudio();
      limparDestaque();
      atualizarBotao();
      return;
    }

    indice = i;
    limparDestaque();

    const trecho = trechos[indice];
    trecho.classList.add('tts-atual');
    trecho.scrollIntoView({behavior: 'smooth', block: 'center'});

    preparando = true;
    atualizarBotao();

    try {
      // O áudio atual já pode estar pronto graças ao pré-carregamento.
      const url = await solicitarAudio(indice, token);
      enviarLogTts('audio_url_disponivel', {indice, token, urlValida: Boolean(url)});

      if (token !== tokenExecucao || !url) {
        enviarLogTts('audio_url_descartada', {indice, token, tokenAtual: tokenExecucao, urlValida: Boolean(url)});
        return;
      }

      // Assim que o atual fica disponível, já começa a preparar os próximos.
      preCarregarFrente(indice, token);

      pararAudio();
      audio = new Audio();
      audio.preload = 'auto';
      audio.src = url;
      const audioAtual = audio;
      enviarLogTts('audio_elemento_criado', estadoAudio({indice, token}, audioAtual));

      audio.onloadedmetadata = () => enviarLogTts('audio_loadedmetadata', estadoAudio({indice}, audioAtual));
      audio.oncanplay = () => enviarLogTts('audio_canplay', estadoAudio({indice}, audioAtual));
      audio.onplaying = () => enviarLogTts('audio_playing', estadoAudio({indice}, audioAtual));
      audio.onwaiting = () => enviarLogTts('audio_waiting', estadoAudio({indice}, audioAtual));
      audio.onstalled = () => enviarLogTts('audio_stalled', estadoAudio({indice}, audioAtual));
      audio.onabort = () => enviarLogTts('audio_abort', estadoAudio({indice}, audioAtual));
      audio.onpause = () => enviarLogTts('audio_pause_event', estadoAudio({indice}, audioAtual));

      audio.onplay = () => {
        enviarLogTts('audio_onplay', estadoAudio({indice}, audioAtual));
        preparando = false;
        carregandoPrimeiroAudio = false;
        tocando = true;
        atualizarBotao();
      };

      audio.onended = async () => {
        enviarLogTts('audio_ended', estadoAudio({indice}, audioAtual));
        if (token !== tokenExecucao) return;

        // O URL usado pode sair do cache somente depois que a reprodução
        // terminou. O próximo já deve estar sendo sintetizado.
        cacheAudio.delete(indice);
        try { URL.revokeObjectURL(url); } catch (_) {}
        urlsCriadas.delete(url);

        // O próximo áudio já foi pré-carregado em paralelo. Esperamos apenas
        // a pausa natural da pontuação, evitando o efeito de leitura
        // "máquina por máquina" sem introduzir uma espera desnecessária.
        const pausaMs = Math.round(calcularPausaNatural(trecho.textContent || '') * 1000);
        enviarLogTts('pausa_entre_trechos', {indice, pausaMs});
        const podeContinuar = await esperar(pausaMs, token);
        if (!podeContinuar || token !== tokenExecucao) return;
        tocarIndice(indice + 1, token).catch(erroTts);
      };

      audio.onerror = () => {
        enviarLogTts('audio_error_event', estadoAudio({indice}, audioAtual));
        if (token !== tokenExecucao) return;
        cacheAudio.delete(indice);
        try { URL.revokeObjectURL(url); } catch (_) {}
        urlsCriadas.delete(url);
        tocando = false;
        preparando = false;
        carregandoPrimeiroAudio = false;
        atualizarBotao();
        const mediaErro = audioAtual?.error;
        erroTts(new Error(`Falha ao reproduzir o áudio${mediaErro?.code ? ` (MediaError ${mediaErro.code})` : ''}.`));
      };

      enviarLogTts('audio_play_chamada', estadoAudio({indice, token}, audioAtual));
      try {
        await audioAtual.play();
        enviarLogTts('audio_play_resolvido', estadoAudio({indice, token}, audioAtual));
      } catch (erroPlay) {
        enviarLogTts('audio_play_rejeitado', estadoAudio({
          indice,
          token,
          nome: erroPlay?.name || '',
          mensagem: erroPlay?.message || String(erroPlay)
        }, audioAtual));
        throw erroPlay;
      }
    } catch (erro) {
      enviarLogTts('tocar_indice_excecao', {
        indice: i,
        token,
        tokenAtual: tokenExecucao,
        nome: erro?.name || '',
        mensagem: erro?.message || String(erro)
      });
      if (token === tokenExecucao) {
        tocando = false;
        preparando = false;
        carregandoPrimeiroAudio = false;
        atualizarBotao();
        erroTts(erro);
      }
    }
  }

  function erroTts(erro) {
    enviarLogTts('erro_tts', {
      nome: erro?.name || '',
      mensagem: erro?.message || String(erro),
      indice,
      tokenAtual: tokenExecucao
    });
    console.error(erro);
    if (erro?.message && !/interrompido/i.test(erro.message)) {
      botao.title = erro.message;

      // No executável sem console, deixar o erro apenas em console.error fazia
      // o botão parecer não responder. Mostra o primeiro erro técnico ao usuário
      // e evita alertas duplicados causados pela fila de pré-carregamento.
      const agora = Date.now();
      const mensagem = String(erro.message);
      const repetidoRecente = mensagem === ultimoErroTtsAlertado && (agora - ultimoErroTtsAlertadoEm) < 5000;
      if (!repetidoRecente) {
        ultimoErroTtsAlertado = mensagem;
        ultimoErroTtsAlertadoEm = agora;
        const titulo = traduzir(
          'reader.tts_runtime_error',
          'Não foi possível iniciar a leitura em voz alta. O detalhe técnico está abaixo:'
        );
        window.alert(`${titulo}\n\n${mensagem}`);
      }
    }
  }

  function iniciar() {
    enviarLogTts('iniciar_solicitado', {indice, trechosExistentes: trechos.length});
    if (!trechos.length) {
      trechos = prepararTrechos();
      indice = calcularIndiceInicialVisivel();
      liberarCacheAudio();
    }

    if (!trechos.length) {
      enviarLogTts('iniciar_sem_trechos', {});
      return;
    }

    indiceInicioSessao = indice;
    scrollYAoPausar = null;

    const token = ++tokenExecucao;
    enviarLogTts('sessao_tts_iniciada', {token, indice, indiceInicioSessao, totalTrechos: trechos.length});
    tocando = false;
    preparando = true;
    carregandoPrimeiroAudio = true;
    atualizarBotao();

    // Começa imediatamente o primeiro e, em paralelo, solicita os próximos.
    solicitarAudio(indice, token).catch(erroTts);
    preCarregarFrente(indice, token);
    tocarIndice(indice, token).catch(erroTts);
  }

  function pausar() {
    enviarLogTts('pausar_solicitado', estadoAudio({indice, preparando, tocando, tokenAtual: tokenExecucao}));
    if (preparando && !audio) {
      tokenExecucao++;
      preparando = false;
      carregandoPrimeiroAudio = false;
      tocando = false;
      liberarCacheAudio();
      limparDestaque();
      registrarPausaParaRetomada();
      atualizarBotao();
      return;
    }

    if (audio && !audio.paused) {
      audio.pause();
      tocando = false;
      preparando = false;
      carregandoPrimeiroAudio = false;
      registrarPausaParaRetomada();
      atualizarBotao();
      return;
    }

    if (trechos.length && !preparando) {
      const token = ++tokenExecucao;
      prepararTrechoEContinuar(token);
    } else {
      iniciar();
    }
  }

  async function prepararTrechoEContinuar(token) {
    try {
      prepararTrechoEContinuar.preparando = true;
      prepararTrechoEContinuar.preparando = false;
      await tocarIndice(indice, token);
    } catch (erro) {
      erroTts(erro);
    }
  }

  botao.addEventListener('click', async (evento) => {
    evento.preventDefault();
    enviarLogTts('botao_tts_click', estadoAudio({indice, preparando, tocando, totalTrechos: trechos.length}));

    if (tocando || preparando) {
      pausar();
      return;
    }

    if (!(await verificarModelosTtsAntesDeReproduzir())) return;

    if (!trechos.length) {
      iniciar();
      return;
    }

    const indiceReinicio = calcularIndiceReinicioAposPausa();
    if (indiceReinicio !== null) {
      // Nova posição escolhida pelo usuário: invalida a reprodução/cache da
      // sessão pausada e começa pelo início do novo parágrafo visível.
      ++tokenExecucao;
      pararAudio();
      liberarCacheAudio();
      limparDestaque();

      indice = indiceReinicio;
      indiceInicioSessao = indiceReinicio;
      scrollYAoPausar = null;

      const token = tokenExecucao;
      tocando = false;
      preparando = true;
      carregandoPrimeiroAudio = true;
      atualizarBotao();

      enviarLogTts('tts_reinicio_acima_apos_pausa', {
        token,
        indice,
        indiceInicioSessao,
        totalTrechos: trechos.length,
      });

      solicitarAudio(indice, token).catch(erroTts);
      preCarregarFrente(indice, token);
      tocarIndice(indice, token).catch(erroTts);
      return;
    }

    scrollYAoPausar = null;
    const token = ++tokenExecucao;
    solicitarAudio(indice, token).catch(erroTts);
    preCarregarFrente(indice, token);
    tocarIndice(indice, token).catch(erroTts);
  });

  if (frame) {
    frame.addEventListener('load', () => {
      enviarLogTts('iframe_load_reset', {tokenAtual: tokenExecucao});
      pararAudio();
      tokenExecucao++;
      liberarCacheAudio();
      trechos = [];
      indice = 0;
      indiceInicioSessao = 0;
      scrollYAoPausar = null;
      tocando = false;
      preparando = false;
      carregandoPrimeiroAudio = false;
      instalarEstiloDestaque(frame.contentDocument);
      atualizarBotao();
    });
  }

  window.addEventListener('beforeunload', () => {
    enviarLogTts('pagina_beforeunload', {indice, tokenAtual: tokenExecucao});
    tokenExecucao++;
    pararAudio();
    liberarCacheAudio();
  });

  atualizarBotao();
})();
