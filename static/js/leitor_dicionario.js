/* Dicionário contextual dos leitores: Alt + hover destaca; Alt + clique consulta. */
(() => {
  const frame = document.getElementById('epubFrame');
  if (!frame) return;

  const cfg = window.LEITOR_CONFIG || {};
  const HIGHLIGHT_NAME = 'gutenberg-dictionary-hover';
  let requisicaoAtual = null;
  let palavraAtual = '';
  let destaqueAtual = null;
  const cacheLocal = new Map();
  const CACHE_LOCAL_MAX = 120;

  function tr(chave, fallback) {
    try {
      const valor = typeof window.t === 'function' ? window.t(chave) : '';
      return valor && valor !== chave ? valor : fallback;
    } catch (_) {
      return fallback;
    }
  }

  function normalizarIdioma(valor, fallback = 'pt_BR') {
    const idioma = String(valor || fallback).toLowerCase().replace('-', '_');
    return idioma === 'en_us' || idioma === 'en_gb' || idioma === 'en' ? 'en_US' : 'pt_BR';
  }

  function idiomaAtual() {
    return normalizarIdioma(cfg.ttsLanguage || 'pt_BR');
  }

  function direcaoTraducao() {
    const origem = normalizarIdioma(cfg.translationFrom || 'en_US', 'en_US');
    let destino = normalizarIdioma(cfg.translationTo || 'pt_BR', 'pt_BR');
    if (origem === destino) destino = origem === 'en_US' ? 'pt_BR' : 'en_US';
    return {origem, destino};
  }

  function nomeIdioma(codigo) {
    return codigo === 'en_US'
      ? tr('language.en_US', 'English')
      : tr('language.pt_BR', 'Português (Brasil)');
  }

  function direcaoAplicavel(idioma) {
    const direcao = direcaoTraducao();
    return idioma === direcao.origem ? direcao : null;
  }

  function chaveCacheLocal(palavra, idioma) {
    const direcao = direcaoTraducao();
    return `${idioma}|${direcao.origem}|${direcao.destino}|${String(palavra || '').toLocaleLowerCase()}`;
  }

  function obterCacheLocal(palavra, idioma) {
    const chave = chaveCacheLocal(palavra, idioma);
    const valor = cacheLocal.get(chave);
    if (!valor) return null;
    // Reinsere para manter os itens mais usados no fim do Map (LRU simples).
    cacheLocal.delete(chave);
    cacheLocal.set(chave, valor);
    return valor;
  }

  function salvarCacheLocal(palavra, idioma, dados) {
    if (!dados?.ok) return;
    const chave = chaveCacheLocal(palavra, idioma);
    cacheLocal.delete(chave);
    cacheLocal.set(chave, dados);
    while (cacheLocal.size > CACHE_LOCAL_MAX) {
      const primeira = cacheLocal.keys().next().value;
      cacheLocal.delete(primeira);
    }
  }

  function criarModal() {
    let modal = document.getElementById('modalDicionarioLeitor');
    if (modal) return modal;

    modal = document.createElement('div');
    modal.id = 'modalDicionarioLeitor';
    modal.className = 'reader-dictionary-modal oculto';
    modal.setAttribute('aria-hidden', 'true');
    modal.innerHTML = `
      <div class="reader-dictionary-overlay" data-dict-close="true"></div>
      <section class="reader-dictionary-card" role="dialog" aria-modal="true" aria-labelledby="readerDictionaryWord">
        <div class="reader-dictionary-header">
          <div class="reader-dictionary-heading">
            <span class="reader-dictionary-kicker"></span>
            <div class="reader-dictionary-title-line">
              <h2 id="readerDictionaryWord"></h2>
              <span class="reader-dictionary-phonetic" id="readerDictionaryPhonetic"></span>
            </div>
          </div>
          <button type="button" class="reader-dictionary-close" data-dict-close="true" aria-label="${tr('reader.dictionary_close', 'Fechar')}">×</button>
        </div>
        <div class="reader-dictionary-body" id="readerDictionaryBody" aria-live="polite"></div>
        <div class="reader-dictionary-footer" id="readerDictionaryFooter"></div>
      </section>`;

    const overlay = modal.querySelector('.reader-dictionary-overlay');
    const botaoFechar = modal.querySelector('.reader-dictionary-close');

    // O clique fora e o botão X usam exatamente o mesmo ciclo de fechamento.
    // Isso evita deixar o modal visualmente oculto, mas com estado interno ativo.
    overlay?.addEventListener('pointerdown', (evento) => {
      evento.preventDefault();
      evento.stopPropagation();
      fecharModal();
    });
    botaoFechar?.addEventListener('click', (evento) => {
      evento.preventDefault();
      evento.stopPropagation();
      fecharModal();
    });
    modal.querySelector('.reader-dictionary-card')?.addEventListener('pointerdown', (evento) => evento.stopPropagation());
    modal.querySelector('.reader-dictionary-card')?.addEventListener('click', (evento) => evento.stopPropagation());
    document.body.appendChild(modal);
    return modal;
  }

  function mostrarModal(palavra = '') {
    const modal = criarModal();
    modal.classList.remove('oculto');
    modal.setAttribute('aria-hidden', 'false');
    modal.querySelector('.reader-dictionary-kicker').textContent = tr('reader.dictionary_title', 'Dicionário');
    if (palavra) modal.querySelector('#readerDictionaryWord').textContent = palavra;
    return modal;
  }

  function devolverFocoAoLeitor() {
    window.setTimeout(() => {
      try {
        frame.focus?.();
        frame.contentWindow?.focus?.();
      } catch (_) {}
    }, 0);
  }

  function fecharModal() {
    if (requisicaoAtual) {
      requisicaoAtual.abort();
      requisicaoAtual = null;
    }
    const modal = document.getElementById('modalDicionarioLeitor');
    if (modal) {
      try {
        if (modal.contains(document.activeElement)) document.activeElement?.blur?.();
      } catch (_) {}
      modal.classList.add('oculto');
      modal.setAttribute('aria-hidden', 'true');
    }
    palavraAtual = '';
    limparDestaque();
    devolverFocoAoLeitor();
  }

  function abrirModalCarregando(palavra) {
    const modal = mostrarModal(palavra);
    modal.querySelector('#readerDictionaryWord').textContent = palavra;
    modal.querySelector('#readerDictionaryPhonetic').textContent = '';
    modal.querySelector('#readerDictionaryFooter').textContent = '';

    const body = modal.querySelector('#readerDictionaryBody');
    body.replaceChildren();
    const loading = document.createElement('div');
    loading.className = 'reader-dictionary-loading';
    const spinner = document.createElement('span');
    spinner.className = 'reader-dictionary-spinner';
    spinner.setAttribute('aria-hidden', 'true');
    const texto = document.createElement('span');
    texto.textContent = tr('reader.dictionary_loading', 'Buscando significado…');
    loading.append(spinner, texto);
    body.appendChild(loading);
  }

  function adicionarBlocoTexto(container, rotulo, texto, classe = '') {
    if (!texto) return;
    const bloco = document.createElement('div');
    bloco.className = `reader-dictionary-info${classe ? ` ${classe}` : ''}`;
    const label = document.createElement('span');
    label.className = 'reader-dictionary-label';
    label.textContent = rotulo;
    const valor = document.createElement('strong');
    valor.className = 'reader-dictionary-value';
    valor.textContent = texto;
    bloco.append(label, valor);
    container.appendChild(bloco);
  }

  function renderizarResultado(dados) {
    const palavraExibida = String(dados?.palavra || palavraAtual || '').trim();
    const modal = mostrarModal(palavraExibida);
    const body = modal.querySelector('#readerDictionaryBody');
    const footer = modal.querySelector('#readerDictionaryFooter');
    const fonetica = modal.querySelector('#readerDictionaryPhonetic');
    body.replaceChildren();
    footer.replaceChildren();
    fonetica.textContent = dados.fonetica || '';

    const palavraOriginal = String(dados.palavra || palavraAtual || '').trim();
    const verbete = String(dados.verbete || '').trim();
    if (verbete && palavraOriginal && verbete.toLocaleLowerCase() !== palavraOriginal.toLocaleLowerCase()) {
      adicionarBlocoTexto(
        body,
        tr('reader.dictionary_headword', 'Verbete encontrado'),
        verbete,
        'reader-dictionary-headword',
      );
    }

    if (dados.traducao) {
      const origem = normalizarIdioma(dados.idioma_traducao_de || dados.idioma || 'en_US', 'en_US');
      const destino = normalizarIdioma(dados.idioma_traducao_para || (origem === 'en_US' ? 'pt_BR' : 'en_US'));
      const rotulo = `${tr('reader.dictionary_translation', 'Tradução')} (${nomeIdioma(origem)} → ${nomeIdioma(destino)})`;
      adicionarBlocoTexto(body, rotulo, dados.traducao, 'reader-dictionary-translation');
    }

    const definicoes = Array.isArray(dados.definicoes) ? dados.definicoes : [];
    if (definicoes.length) {
      const titulo = document.createElement('h3');
      titulo.className = 'reader-dictionary-section-title';
      titulo.textContent = tr('reader.dictionary_meanings', 'Significados');
      body.appendChild(titulo);

      const lista = document.createElement('ol');
      lista.className = 'reader-dictionary-definitions';
      definicoes.forEach((item) => {
        const li = document.createElement('li');
        const topo = document.createElement('div');
        topo.className = 'reader-dictionary-definition-main';
        if (item.classe) {
          const classe = document.createElement('span');
          classe.className = 'reader-dictionary-pos';
          classe.textContent = item.classe;
          topo.appendChild(classe);
        }
        const texto = document.createElement('span');
        texto.className = 'reader-dictionary-definition-text';
        texto.textContent = item.texto || '';
        topo.appendChild(texto);
        li.appendChild(topo);
        if (item.exemplo) {
          const exemplo = document.createElement('p');
          exemplo.className = 'reader-dictionary-example';
          exemplo.textContent = `${tr('reader.dictionary_example', 'Exemplo')}: ${item.exemplo}`;
          li.appendChild(exemplo);
        }
        lista.appendChild(li);
      });
      body.appendChild(lista);
    } else if (dados.traducao) {
      const aviso = document.createElement('p');
      aviso.className = 'reader-dictionary-muted';
      aviso.textContent = tr('reader.dictionary_definition_unavailable', 'A tradução foi encontrada, mas não há uma definição disponível para esta palavra.');
      body.appendChild(aviso);
    }

    const fontes = [];
    if (dados.fonte_dicionario) fontes.push(`${tr('reader.dictionary_source', 'Dicionário')}: ${dados.fonte_dicionario}`);
    if (dados.fonte_traducao && dados.traducao) fontes.push(`${tr('reader.dictionary_translation_source', 'Tradução')}: ${dados.fonte_traducao}`);
    footer.textContent = fontes.join(' • ');
  }

  function renderizarErro(mensagem) {
    const modal = mostrarModal(palavraAtual);
    const body = modal.querySelector('#readerDictionaryBody');
    const footer = modal.querySelector('#readerDictionaryFooter');
    body.replaceChildren();
    footer.replaceChildren();
    const erro = document.createElement('div');
    erro.className = 'reader-dictionary-error';
    erro.textContent = mensagem || tr('reader.dictionary_error', 'Não foi possível consultar esta palavra.');
    body.appendChild(erro);
  }

  function textoHtmlLimpo(valor) {
    if (!valor) return '';
    const template = document.createElement('template');
    template.innerHTML = String(valor);
    return String(template.content.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function mesclarDefinicoesDireto(destino, novas, limite = 6) {
    const vistos = new Set(destino.map((item) => String(item?.texto || '').trim().toLocaleLowerCase()).filter(Boolean));
    for (const item of Array.isArray(novas) ? novas : []) {
      const texto = String(item?.texto || '').replace(/\s+/g, ' ').trim();
      const chave = texto.toLocaleLowerCase();
      if (!texto || vistos.has(chave) || destino.length >= limite) continue;
      const classe = String(item?.classe || '').replace(/\s+/g, ' ').trim();
      const exemplo = String(item?.exemplo || '').replace(/\s+/g, ' ').trim();
      destino.push({texto, ...(classe ? {classe} : {}), ...(exemplo ? {exemplo} : {})});
      vistos.add(chave);
    }
    return destino;
  }

  function parseDatamuseDireto(dados) {
    if (!Array.isArray(dados)) return {definicoes: [], verbete: ''};
    const mapaClasses = {n: 'noun', v: 'verb', adj: 'adjective', adv: 'adverb'};
    for (const entrada of dados.slice(0, 8)) {
      const defsBrutas = Array.isArray(entrada?.defs) ? entrada.defs : [];
      if (!defsBrutas.length) continue;
      const tags = Array.isArray(entrada?.tags) ? entrada.tags : [];
      const classePadrao = tags.map((tag) => mapaClasses[String(tag || '').toLowerCase()] || '').find(Boolean) || '';
      const definicoes = [];
      const vistos = new Set();
      for (const bruto of defsBrutas) {
        const brutoTexto = String(bruto || '');
        let texto = brutoTexto;
        let classe = classePadrao;
        if (brutoTexto.includes('\t')) {
          const partes = brutoTexto.split('\t');
          const prefixo = partes.shift().trim().toLowerCase();
          texto = partes.join('\t');
          classe = mapaClasses[prefixo] || classe;
        }
        texto = texto.replace(/\s+/g, ' ').trim();
        const chave = texto.toLocaleLowerCase('en');
        if (!texto || vistos.has(chave) || definicoes.length >= 6) continue;
        vistos.add(chave);
        definicoes.push({texto, ...(classe ? {classe} : {})});
      }
      if (definicoes.length) {
        const verbete = String(entrada?.defHeadword || entrada?.word || '').trim();
        return {definicoes, verbete};
      }
    }
    return {definicoes: [], verbete: ''};
  }

  function parseWiktionaryDireto(dados) {
    const entradas = Array.isArray(dados?.en) ? dados.en : [];
    const saida = [];
    const vistos = new Set();
    for (const entrada of entradas) {
      const classe = String(entrada?.partOfSpeech || '').trim();
      const defs = Array.isArray(entrada?.definitions) ? entrada.definitions : [];
      for (const item of defs) {
        const texto = textoHtmlLimpo(item?.definition);
        if (!texto || vistos.has(texto.toLocaleLowerCase()) || saida.length >= 6) continue;
        vistos.add(texto.toLocaleLowerCase());
        const exemplos = Array.isArray(item?.examples) ? item.examples : [];
        const exemplo = exemplos.map(textoHtmlLimpo).find(Boolean) || '';
        saida.push({texto, ...(classe ? {classe} : {}), ...(exemplo ? {exemplo} : {})});
      }
      if (saida.length >= 6) break;
    }
    return saida;
  }

  function parseFreeDictionaryDireto(dados) {
    if (!Array.isArray(dados)) return {definicoes: [], fonetica: ''};
    const definicoes = [];
    const vistos = new Set();
    let fonetica = '';
    for (const entrada of dados.slice(0, 4)) {
      if (!fonetica) {
        fonetica = String(entrada?.phonetic || '').trim();
        if (!fonetica) {
          fonetica = (Array.isArray(entrada?.phonetics) ? entrada.phonetics : [])
            .map((item) => String(item?.text || '').trim()).find(Boolean) || '';
        }
      }
      for (const significado of (Array.isArray(entrada?.meanings) ? entrada.meanings : [])) {
        const classe = String(significado?.partOfSpeech || '').trim();
        for (const item of (Array.isArray(significado?.definitions) ? significado.definitions : [])) {
          const texto = String(item?.definition || '').replace(/\s+/g, ' ').trim();
          const chave = texto.toLocaleLowerCase();
          if (!texto || vistos.has(chave) || definicoes.length >= 6) continue;
          vistos.add(chave);
          const exemplo = String(item?.example || '').replace(/\s+/g, ' ').trim();
          definicoes.push({texto, ...(classe ? {classe} : {}), ...(exemplo ? {exemplo} : {})});
        }
      }
    }
    return {definicoes, fonetica};
  }

  function parseDicionarioAbertoDireto(dados) {
    if (!Array.isArray(dados)) return [];
    const saida = [];
    const vistos = new Set();
    for (const entrada of dados.slice(0, 6)) {
      const xml = String(entrada?.xml || '').trim();
      if (!xml) continue;
      const docXml = new DOMParser().parseFromString(xml, 'application/xml');
      if (docXml.querySelector('parsererror')) continue;
      const classePadrao = String(docXml.querySelector('gramGrp')?.textContent || '').replace(/\s+/g, ' ').trim();
      for (const sentido of docXml.querySelectorAll('sense')) {
        const classe = String(sentido.querySelector('gramGrp')?.textContent || classePadrao).replace(/\s+/g, ' ').trim();
        const defs = Array.from(sentido.querySelectorAll('def'));
        const candidatos = defs.length ? defs : [sentido];
        for (const def of candidatos) {
          const texto = String(def.textContent || '').replace(/\s+/g, ' ').trim();
          const chave = texto.toLocaleLowerCase();
          if (!texto || vistos.has(chave) || saida.length >= 6) continue;
          vistos.add(chave);
          saida.push({texto, ...(classe ? {classe} : {})});
        }
        if (saida.length >= 6) break;
      }
      if (saida.length >= 6) break;
    }
    return saida;
  }

  function classeWikcionarioPortugues(texto) {
    const limpo = String(texto || '')
      .replace(/\[editar\]\s*$/i, '')
      .replace(/\s+\d+\s*$/, '')
      .replace(/\s+/g, ' ').trim();
    const base = limpo.toLocaleLowerCase('pt-BR');
    const exatas = new Set([
      'adjetivo', 'advérbio', 'artigo', 'conjunção', 'interjeição', 'numeral',
      'preposição', 'pronome', 'substantivo', 'verbo', 'locução', 'expressão',
      'expressão verbal', 'expressão idiomática', 'forma verbal', 'forma de verbo',
      'forma de substantivo', 'forma de adjetivo', 'forma de pronome', 'sigla',
      'abreviatura', 'contração', 'prefixo', 'sufixo', 'particípio', 'gerúndio',
    ]);
    if (exatas.has(base)) return limpo;
    if (base.startsWith('substantivo')) return 'Substantivo';
    if (base.startsWith('adjetivo')) return 'Adjetivo';
    if (base.startsWith('verbo')) return 'Verbo';
    if (base.startsWith('advérbio')) return 'Advérbio';
    if (base.startsWith('pronome')) return 'Pronome';
    if (base.startsWith('forma ') || base.startsWith('expressão') || base.startsWith('locução')) return limpo;
    return '';
  }

  function parseWikcionarioPortuguesDireto(dados) {
    const htmlBruto = typeof dados?.parse?.text === 'string'
      ? dados.parse.text
      : String(dados?.parse?.text?.['*'] || '');
    if (!htmlBruto) return [];
    const doc = new DOMParser().parseFromString(htmlBruto, 'text/html');
    const elementos = Array.from(doc.querySelectorAll('h2, h3, h4, ol'));
    let dentroPortugues = false;
    let classeAtual = '';
    const saida = [];
    const vistos = new Set();

    for (const elemento of elementos) {
      const tag = elemento.tagName.toLowerCase();
      if (tag === 'h2') {
        const titulo = String(elemento.textContent || '').replace(/\s+/g, ' ').trim().toLocaleLowerCase('pt-BR');
        const ident = String(elemento.id || '').trim().toLocaleLowerCase('pt-BR');
        if (!dentroPortugues) {
          dentroPortugues = titulo.startsWith('português') || ident === 'português';
          classeAtual = '';
          continue;
        }
        break;
      }
      if (!dentroPortugues) continue;
      if (tag === 'h3' || tag === 'h4') {
        classeAtual = classeWikcionarioPortugues(elemento.textContent);
        continue;
      }
      if (tag !== 'ol' || !classeAtual) continue;

      const itens = Array.from(elemento.children).filter((filho) => filho.tagName?.toLowerCase() === 'li');
      for (const li of itens) {
        const exemplo = Array.from(li.querySelectorAll('ul li, dl dd, blockquote'))
          .map((item) => String(item.textContent || '').replace(/\s+/g, ' ').trim()).find(Boolean) || '';
        const clone = li.cloneNode(true);
        clone.querySelectorAll('ul, ol, dl, table, blockquote').forEach((item) => item.remove());
        const texto = String(clone.textContent || '').replace(/\s+/g, ' ').replace(/^\s*\d+[.)]?\s*/, '').trim();
        const chave = texto.toLocaleLowerCase('pt-BR');
        if (!texto || vistos.has(chave) || saida.length >= 6) continue;
        vistos.add(chave);
        saida.push({texto, classe: classeAtual, ...(exemplo ? {exemplo} : {})});
      }
      if (saida.length >= 6) break;
    }
    return saida;
  }

  async function traduzirDireto(palavra, origem, destino, signal) {
    if (!origem || !destino || origem === destino) return '';
    const codigos = {en_US: 'en', pt_BR: 'pt'};
    try {
      const params = new URLSearchParams({
        q: palavra,
        langpair: `${codigos[origem]}|${codigos[destino]}`,
      });
      const resposta = await fetch(`https://api.mymemory.translated.net/get?${params}`, {signal, cache: 'no-store'});
      if (!resposta.ok) return '';
      const dados = await resposta.json();
      const texto = String(dados?.responseData?.translatedText || '').trim();
      if (texto && !texto.toUpperCase().includes('MYMEMORY WARNING')) return texto;
      const alternativa = (Array.isArray(dados?.matches) ? dados.matches : [])
        .map((item) => String(item?.translation || '').trim())
        .find((item) => item && !item.toUpperCase().includes('MYMEMORY WARNING'));
      return alternativa || '';
    } catch (_) {
      return '';
    }
  }

  async function consultarDiretoNoNavegador(palavra, idioma, signal) {
    /*
      Fallback para instalações em que o requests/Python não alcança os provedores,
      mas o Chromium/QWebEngine possui acesso normal à internet. A busca aproximada
      continua sendo feita pelos próprios provedores, não pelo Gutenberg.
    */
    const direcao = direcaoAplicavel(idioma);
    const promessaTraducao = direcao
      ? traduzirDireto(palavra, direcao.origem, direcao.destino, signal)
      : Promise.resolve('');

    if (idioma === 'en_US') {
      try {
        const termo = palavra.toLocaleLowerCase('en');
        const paramsDatamuse = new URLSearchParams({sp: termo, md: 'dp', max: '8'});
        const [respDatamuse, traducao] = await Promise.all([
          fetch(`https://api.datamuse.com/words?${paramsDatamuse}`, {signal, cache: 'no-store', headers: {'Accept': 'application/json'}}).catch(() => null),
          promessaTraducao,
        ]);

        const definicoes = [];
        const fontes = [];
        let fonetica = '';
        let verbete = '';
        if (respDatamuse?.ok) {
          const datamuse = parseDatamuseDireto(await respDatamuse.json());
          if (datamuse.definicoes.length) {
            mesclarDefinicoesDireto(definicoes, datamuse.definicoes);
            fontes.push('Datamuse (Wiktionary/WordNet)');
            verbete = datamuse.verbete || termo;
          }
        }

        const termoSecundario = String(verbete || termo).toLocaleLowerCase('en');
        if (definicoes.length < 6) {
          const urlWiktionary = `https://en.wiktionary.org/api/rest_v1/page/definition/${encodeURIComponent(termoSecundario)}`;
          const urlFree = `https://api.dictionaryapi.dev/api/v2/entries/en/${encodeURIComponent(termoSecundario)}`;
          const [respWiki, respFree] = await Promise.all([
            fetch(urlWiktionary, {signal, cache: 'no-store', headers: {'Accept': 'application/json'}}).catch(() => null),
            fetch(urlFree, {signal, cache: 'no-store', headers: {'Accept': 'application/json'}}).catch(() => null),
          ]);
          if (respWiki?.ok) {
            const defs = parseWiktionaryDireto(await respWiki.json());
            const antes = definicoes.length;
            mesclarDefinicoesDireto(definicoes, defs);
            if (definicoes.length > antes) fontes.push('Wiktionary');
            if (defs.length && !verbete) verbete = termoSecundario;
          }
          if (respFree?.ok && definicoes.length < 6) {
            const free = parseFreeDictionaryDireto(await respFree.json());
            const antes = definicoes.length;
            mesclarDefinicoesDireto(definicoes, free.definicoes);
            if (definicoes.length > antes) fontes.push('Free Dictionary API');
            fonetica = free.fonetica || '';
            if (free.definicoes.length && !verbete) verbete = termoSecundario;
          }
        }

        if (!definicoes.length && !traducao) return null;
        return {
          ok: true,
          palavra,
          verbete: verbete || palavra,
          idioma: 'en_US',
          definicoes,
          traducao,
          idioma_traducao_de: direcao?.origem || direcaoTraducao().origem,
          idioma_traducao_para: direcao?.destino || direcaoTraducao().destino,
          fonetica,
          fonte_dicionario: Array.from(new Set(fontes)).join(' + '),
          fonte_traducao: traducao ? 'MyMemory' : '',
          fallback_navegador: true,
        };
      } catch (_) {
        return null;
      }
    }

    try {
      const termo = palavra.toLocaleLowerCase('pt-BR');
      const paramsWikiExato = new URLSearchParams({
        action: 'parse', page: termo, prop: 'text|sections', redirects: '1',
        format: 'json', formatversion: '2', origin: '*',
      });
      const urlWikiExato = `https://pt.wiktionary.org/w/api.php?${paramsWikiExato}`;
      const urlAbertoExato = `https://api.dicionario-aberto.net/word/${encodeURIComponent(termo)}`;
      const [respWiki, respAberto, traducao] = await Promise.all([
        fetch(urlWikiExato, {signal, cache: 'no-store', headers: {'Accept': 'application/json'}}).catch(() => null),
        fetch(urlAbertoExato, {signal, cache: 'no-store', headers: {'Accept': 'application/json'}}).catch(() => null),
        promessaTraducao,
      ]);

      const definicoes = [];
      const fontes = [];
      let verbete = '';
      if (respWiki?.ok) {
        const defs = parseWikcionarioPortuguesDireto(await respWiki.json());
        if (defs.length) {
          mesclarDefinicoesDireto(definicoes, defs);
          fontes.push('Wikcionário');
          verbete = termo;
        }
      }
      if (respAberto?.ok) {
        const defs = parseDicionarioAbertoDireto(await respAberto.json());
        const antes = definicoes.length;
        mesclarDefinicoesDireto(definicoes, defs);
        if (definicoes.length > antes) fontes.push('Dicionário Aberto');
        if (defs.length && !verbete) verbete = termo;
      }

      // Busca aproximada nativa do Wikcionário/MediaWiki.
      if (!definicoes.length) {
        const paramsBusca = new URLSearchParams({
          action: 'query', list: 'search', srsearch: termo, srlimit: '5', srnamespace: '0',
          format: 'json', formatversion: '2', origin: '*',
        });
        const respBusca = await fetch(`https://pt.wiktionary.org/w/api.php?${paramsBusca}`, {
          signal, cache: 'no-store', headers: {'Accept': 'application/json'},
        }).catch(() => null);
        if (respBusca?.ok) {
          const dadosBusca = await respBusca.json();
          const candidatos = [];
          const vistos = new Set([termo.toLocaleLowerCase('pt-BR')]);
          const sugestao = String(dadosBusca?.query?.searchinfo?.suggestion || '').trim();
          if (sugestao && !vistos.has(sugestao.toLocaleLowerCase('pt-BR'))) {
            candidatos.push(sugestao); vistos.add(sugestao.toLocaleLowerCase('pt-BR'));
          }
          for (const item of (Array.isArray(dadosBusca?.query?.search) ? dadosBusca.query.search : [])) {
            const titulo = String(item?.title || '').trim();
            const chave = titulo.toLocaleLowerCase('pt-BR');
            if (titulo && !vistos.has(chave)) { candidatos.push(titulo); vistos.add(chave); }
            if (candidatos.length >= 5) break;
          }
          for (const candidato of candidatos.slice(0, 4)) {
            const paramsPagina = new URLSearchParams({
              action: 'parse', page: candidato, prop: 'text|sections', redirects: '1',
              format: 'json', formatversion: '2', origin: '*',
            });
            const resp = await fetch(`https://pt.wiktionary.org/w/api.php?${paramsPagina}`, {
              signal, cache: 'no-store', headers: {'Accept': 'application/json'},
            }).catch(() => null);
            if (!resp?.ok) continue;
            const defs = parseWikcionarioPortuguesDireto(await resp.json());
            if (defs.length) {
              mesclarDefinicoesDireto(definicoes, defs);
              fontes.push('Wikcionário (busca aproximada)');
              verbete = candidato;
              break;
            }
          }
        }
      }

      // Endpoint /near do próprio Dicionário Aberto, sem cálculo de distância local.
      if (!definicoes.length) {
        const respNear = await fetch(`https://api.dicionario-aberto.net/near/${encodeURIComponent(termo)}`, {
          signal, cache: 'no-store', headers: {'Accept': 'application/json'},
        }).catch(() => null);
        if (respNear?.ok) {
          const candidatos = await respNear.json();
          for (const candidatoBruto of (Array.isArray(candidatos) ? candidatos.slice(0, 5) : [])) {
            const candidato = String(candidatoBruto || '').trim();
            if (!candidato) continue;
            const resp = await fetch(`https://api.dicionario-aberto.net/word/${encodeURIComponent(candidato)}`, {
              signal, cache: 'no-store', headers: {'Accept': 'application/json'},
            }).catch(() => null);
            if (!resp?.ok) continue;
            const defs = parseDicionarioAbertoDireto(await resp.json());
            if (defs.length) {
              mesclarDefinicoesDireto(definicoes, defs);
              fontes.push('Dicionário Aberto (palavra próxima)');
              verbete = candidato;
              break;
            }
          }
        }
      }

      if (!definicoes.length && !traducao) return null;
      return {
        ok: true,
        palavra,
        verbete: verbete || palavra,
        idioma: 'pt_BR',
        definicoes,
        traducao,
        idioma_traducao_de: direcao?.origem || direcaoTraducao().origem,
        idioma_traducao_para: direcao?.destino || direcaoTraducao().destino,
        fonetica: '',
        fonte_dicionario: Array.from(new Set(fontes)).join(' + '),
        fonte_traducao: traducao ? 'MyMemory' : '',
        fallback_navegador: true,
      };
    } catch (_) {
      return null;
    }
  }

  async function consultarPalavra(palavra) {
    palavraAtual = palavra;
    const idioma = idiomaAtual();
    const emCacheLocal = obterCacheLocal(palavra, idioma);
    if (emCacheLocal) {
      if (requisicaoAtual) {
        requisicaoAtual.abort();
        requisicaoAtual = null;
      }
      // Resultados em cache também precisam reabrir explicitamente o modal.
      // renderizarResultado() chama mostrarModal(), garantindo que Alt+click
      // continue funcionando após fechar clicando fora da janela.
      renderizarResultado(emCacheLocal);
      return;
    }

    abrirModalCarregando(palavra);
    if (requisicaoAtual) requisicaoAtual.abort();
    const controller = new AbortController();
    requisicaoAtual = controller;

    try {
      const params = new URLSearchParams({palavra, idioma});
      let resposta = null;
      let dados = {};
      try {
        resposta = await fetch(`/api/dicionario/consultar?${params.toString()}`, {
          method: 'GET',
          cache: 'no-store',
          signal: controller.signal,
          headers: {'Accept': 'application/json'},
        });
        dados = await resposta.json().catch(() => ({}));
      } catch (erroBackend) {
        if (erroBackend?.name === 'AbortError') throw erroBackend;
      }

      if (controller.signal.aborted || palavraAtual !== palavra) return;

      if (resposta?.ok && dados?.ok) {
        // Se o backend conseguiu apenas a tradução, ainda tentamos obter a
        // definição pelo mecanismo de rede do WebView antes de exibir o resultado.
        if (!Array.isArray(dados.definicoes) || !dados.definicoes.length) {
          const fallback = await consultarDiretoNoNavegador(palavra, idioma, controller.signal);
          if (controller.signal.aborted || palavraAtual !== palavra) return;
          if (fallback?.ok && Array.isArray(fallback.definicoes) && fallback.definicoes.length) {
            fallback.traducao = dados.traducao || fallback.traducao || '';
            fallback.fonte_traducao = dados.fonte_traducao || fallback.fonte_traducao || '';
            salvarCacheLocal(palavra, idioma, fallback);
            renderizarResultado(fallback);
            return;
          }
        }
        salvarCacheLocal(palavra, idioma, dados);
        renderizarResultado(dados);
        return;
      }

      // 404, 502/5xx ou falha de rede no backend: tenta pelo mecanismo de rede do WebView.
      if (!resposta || resposta.status === 404 || resposta.status >= 500) {
        const fallback = await consultarDiretoNoNavegador(palavra, idioma, controller.signal);
        if (controller.signal.aborted || palavraAtual !== palavra) return;
        if (fallback?.ok) {
          salvarCacheLocal(palavra, idioma, fallback);
          renderizarResultado(fallback);
          return;
        }
      }

      renderizarErro(dados?.erro || tr('reader.dictionary_not_found', 'Nenhum significado foi encontrado para esta palavra.'));
    } catch (erro) {
      if (erro?.name === 'AbortError') return;
      const fallback = await consultarDiretoNoNavegador(palavra, idioma, controller.signal);
      if (controller.signal.aborted || palavraAtual !== palavra) return;
      if (fallback?.ok) {
        salvarCacheLocal(palavra, idioma, fallback);
        renderizarResultado(fallback);
      } else renderizarErro(tr('reader.dictionary_network_error', 'Não foi possível acessar o dicionário online. Verifique sua conexão com a internet.'));
    } finally {
      if (requisicaoAtual === controller) requisicaoAtual = null;
    }
  }

  const REGEX_PALAVRA = /[\p{L}\p{M}]+(?:['’\-][\p{L}\p{M}]+)*/gu;

  function matchPalavraNoOffset(texto, offset) {
    if (!texto) return null;
    const posicao = Math.max(0, Math.min(Number(offset) || 0, texto.length));
    REGEX_PALAVRA.lastIndex = 0;
    let match;
    while ((match = REGEX_PALAVRA.exec(texto))) {
      const inicio = match.index;
      const fim = inicio + match[0].length;
      if ((posicao >= inicio && posicao <= fim) || (posicao > 0 && posicao - 1 >= inicio && posicao - 1 < fim)) {
        return {palavra: match[0], inicio, fim};
      }
    }
    return null;
  }

  function caretNoPonto(doc, x, y) {
    if (typeof doc.caretPositionFromPoint === 'function') {
      const pos = doc.caretPositionFromPoint(x, y);
      if (pos) return {node: pos.offsetNode, offset: pos.offset};
    }
    if (typeof doc.caretRangeFromPoint === 'function') {
      const range = doc.caretRangeFromPoint(x, y);
      if (range) return {node: range.startContainer, offset: range.startOffset};
    }
    return null;
  }

  function pontoDentroRect(rect, x, y) {
    const margem = 1;
    return x >= rect.left - margem && x <= rect.right + margem && y >= rect.top - margem && y <= rect.bottom + margem;
  }

  function infoPorRanges(doc, alvo, x, y) {
    if (!alvo) return null;
    const walker = doc.createTreeWalker(alvo, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const texto = node.nodeValue || '';
      REGEX_PALAVRA.lastIndex = 0;
      let match;
      while ((match = REGEX_PALAVRA.exec(texto))) {
        const range = doc.createRange();
        range.setStart(node, match.index);
        range.setEnd(node, match.index + match[0].length);
        const rects = Array.from(range.getClientRects());
        if (rects.some((rect) => pontoDentroRect(rect, x, y))) {
          return {palavra: match[0], range, node, inicio: match.index, fim: match.index + match[0].length};
        }
      }
    }
    return null;
  }

  function infoPalavraNoPonto(evento) {
    const doc = evento.currentTarget;
    const caret = caretNoPonto(doc, evento.clientX, evento.clientY);
    if (caret?.node?.nodeType === Node.TEXT_NODE) {
      const match = matchPalavraNoOffset(caret.node.nodeValue || '', caret.offset);
      if (match) {
        const range = doc.createRange();
        range.setStart(caret.node, match.inicio);
        range.setEnd(caret.node, match.fim);
        const rects = Array.from(range.getClientRects());
        if (rects.some((rect) => pontoDentroRect(rect, evento.clientX, evento.clientY))) {
          return {palavra: match.palavra, range, node: caret.node, inicio: match.inicio, fim: match.fim};
        }
      }
    }

    const alvo = evento.target?.nodeType === Node.ELEMENT_NODE ? evento.target : evento.target?.parentElement;
    return infoPorRanges(doc, alvo, evento.clientX, evento.clientY);
  }

  function garantirEstiloDestaque(doc) {
    if (doc.getElementById('gutenbergDictionaryHoverStyle')) return;
    const style = doc.createElement('style');
    style.id = 'gutenbergDictionaryHoverStyle';
    style.textContent = `
      ::highlight(${HIGHLIGHT_NAME}) {
        background: rgba(125, 211, 252, .72);
        color: #0f172a;
      }
      .gutenberg-dictionary-hover-overlay {
        position: absolute;
        inset: 0 auto auto 0;
        pointer-events: none;
        z-index: 2147483646;
      }
      .gutenberg-dictionary-hover-overlay > i {
        position: absolute;
        display: block;
        pointer-events: none;
        border-radius: 4px;
        background: rgba(125, 211, 252, .58);
        box-shadow: 0 0 0 1px rgba(56, 189, 248, .16) inset;
      }`;
    (doc.head || doc.documentElement).appendChild(style);
  }

  function limparDestaque(doc = destaqueAtual?.doc) {
    if (!doc) {
      destaqueAtual = null;
      return;
    }
    try {
      doc.defaultView?.CSS?.highlights?.delete(HIGHLIGHT_NAME);
    } catch (_) {}
    doc.getElementById('gutenbergDictionaryHoverOverlay')?.remove();
    if (destaqueAtual?.doc === doc) destaqueAtual = null;
  }

  function destacarRange(doc, info) {
    if (!info?.range) {
      limparDestaque(doc);
      return;
    }
    if (
      destaqueAtual?.doc === doc &&
      destaqueAtual?.node === info.node &&
      destaqueAtual?.inicio === info.inicio &&
      destaqueAtual?.fim === info.fim
    ) return;

    limparDestaque(doc);
    garantirEstiloDestaque(doc);

    const win = doc.defaultView;
    const registry = win?.CSS?.highlights;
    const HighlightCtor = win?.Highlight;
    let aplicado = false;
    if (registry && typeof HighlightCtor === 'function') {
      try {
        registry.set(HIGHLIGHT_NAME, new HighlightCtor(info.range.cloneRange()));
        aplicado = true;
      } catch (_) {}
    }

    // Fallback para versões antigas do QtWebEngine/Chromium sem CSS Custom Highlight API.
    if (!aplicado) {
      const overlay = doc.createElement('span');
      overlay.id = 'gutenbergDictionaryHoverOverlay';
      overlay.className = 'gutenberg-dictionary-hover-overlay';
      overlay.setAttribute('aria-hidden', 'true');
      const scrollX = win?.scrollX || 0;
      const scrollY = win?.scrollY || 0;
      for (const rect of Array.from(info.range.getClientRects())) {
        if (!rect.width || !rect.height) continue;
        const marca = doc.createElement('i');
        marca.style.left = `${rect.left + scrollX}px`;
        marca.style.top = `${rect.top + scrollY}px`;
        marca.style.width = `${rect.width}px`;
        marca.style.height = `${rect.height}px`;
        overlay.appendChild(marca);
      }
      (doc.body || doc.documentElement).appendChild(overlay);
    }

    destaqueAtual = {doc, node: info.node, inicio: info.inicio, fim: info.fim};
  }

  function aoMoverNoConteudo(evento) {
    const doc = evento.currentTarget;
    if (!evento.altKey) {
      limparDestaque(doc);
      return;
    }
    destacarRange(doc, infoPalavraNoPonto(evento));
  }

  function aoClicarNoConteudo(evento) {
    if (!evento.altKey || evento.button !== 0) return;
    const info = infoPalavraNoPonto(evento);
    if (!info?.palavra) return;

    evento.preventDefault();
    evento.stopPropagation();
    limparDestaque(evento.currentTarget);
    try {
      evento.currentTarget.defaultView?.getSelection?.()?.removeAllRanges();
    } catch (_) {}
    consultarPalavra(info.palavra);
  }

  function conectarAoIframe() {
    const doc = frame.contentDocument;
    if (!doc?.documentElement || doc.documentElement.dataset.dictionaryAltClickBound === 'true') return;
    doc.documentElement.dataset.dictionaryAltClickBound = 'true';
    garantirEstiloDestaque(doc);
    doc.addEventListener('mousemove', aoMoverNoConteudo, true);
    doc.addEventListener('click', aoClicarNoConteudo, true);
    doc.addEventListener('keyup', (evento) => {
      if (evento.key === 'Alt') limparDestaque(doc);
    }, true);
    doc.addEventListener('mouseleave', () => limparDestaque(doc), true);
    doc.defaultView?.addEventListener('blur', () => limparDestaque(doc));
  }

  frame.addEventListener('load', () => {
    limparDestaque();
    conectarAoIframe();
  });
  if (frame.contentDocument?.readyState === 'complete' || frame.contentDocument?.readyState === 'interactive') {
    conectarAoIframe();
  }

  document.addEventListener('keyup', (evento) => {
    if (evento.key === 'Alt') limparDestaque();
  });
  window.addEventListener('blur', () => limparDestaque());
  document.addEventListener('keydown', (evento) => {
    if (evento.key === 'Escape' && !document.getElementById('modalDicionarioLeitor')?.classList.contains('oculto')) {
      fecharModal();
    }
  });
})();
