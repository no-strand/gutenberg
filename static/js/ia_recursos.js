/* Assistente de geração por IA para os recursos do projeto. Reutiliza a mesma rota/modelo do editor EPUB. */
(() => {
  const modal = document.getElementById('modalIARecursos');
  const abrir = document.getElementById('btnAbrirIARecursos');
  const promptEl = document.getElementById('iaRecursosPrompt');
  const preview = document.getElementById('iaRecursosPreview');
  const status = document.getElementById('iaRecursosStatus');
  const gerarBtn = document.getElementById('btnGerarIARecursos');
  const aplicarBtn = document.getElementById('btnAplicarIARecursos');
  if (!modal || !abrir || !promptEl || !preview || !status || !gerarBtn || !aplicarBtn) return;

  let htmlGerado = '';
  let textoGerado = '';

  const $ = (s, r=document) => r.querySelector(s);
  const $$ = (s, r=document) => [...r.querySelectorAll(s)];
  const tr = (key, fallback='') => (typeof window.t === 'function' ? (window.t(key) || fallback) : fallback);

  function alvoAtual() { return $('input[name="iaRecursoAlvo"]:checked')?.value || 'informacoes'; }
  function abrirModal() {
    modal.classList.remove('oculto'); modal.setAttribute('aria-hidden','false');
    promptEl.focus();
  }
  function fecharModal() {
    modal.classList.add('oculto'); modal.setAttribute('aria-hidden','true');
  }
  function contextoRecursos() {
    const data = window.PROJETO_RECURSOS_INITIAL || {};
    const alvo = alvoAtual();
    const resumo = {
      projeto: data.projeto || {},
      alvo,
      informacoes: data.informacoes_abas || data.informacoes || [],
      personagens: data.personagens || [],
      lugares: data.lugares || [],
      anotacoes: data.anotacoes || [],
    };
    return JSON.stringify(resumo, null, 2).slice(0, 12000);
  }
  function contextoEditor() {
    const editor = document.getElementById('editorInfoPagina');
    return editor ? (editor.innerHTML || '').slice(0, 16000) : '';
  }
  function instrucoes(alvo) {
    if (alvo === 'personagens') return 'Crie um personagem. Retorne SOMENTE HTML seguro com um h2 para o nome e um ou mais p para a descrição. O primeiro h2 deve ser apenas o nome, sem rótulos como "Nome:".';
    if (alvo === 'lugares') return 'Crie um lugar/cenário. Retorne SOMENTE HTML seguro com um h2 para o nome e um ou mais p para a descrição. O primeiro h2 deve ser apenas o nome, sem rótulos.';
    if (alvo === 'anotacoes') return 'Crie uma anotação. Retorne SOMENTE HTML seguro com um h2 para o título e um ou mais p para o texto. O primeiro h2 deve ser apenas o título.';
    return 'Crie conteúdo editorial para uma página de informações do projeto. Retorne SOMENTE HTML seguro, usando h1/h2/h3, p, blockquote, ul, ol, li, br, strong, em, u e hr quando necessário.';
  }
  function limparHtml(html) {
    const root = document.createElement('div'); root.innerHTML = html || '';
    root.querySelectorAll('script,style,iframe,object,embed,form').forEach(el => el.remove());
    root.querySelectorAll('*').forEach(el => [...el.attributes].forEach(a => {
      if (a.name.toLowerCase().startsWith('on') || ['href','src','style'].includes(a.name.toLowerCase())) el.removeAttribute(a.name);
    }));
    return root;
  }
  function textoSemFormatacao(root) { return (root.textContent || '').replace(/\s+/g,' ').trim(); }
  function primeiroTitulo(root) {
    return (root.querySelector('h1,h2,h3')?.textContent || '').replace(/^\s*(nome|título)\s*:\s*/i,'').trim().slice(0,80);
  }
  function descricaoCatalogo(root) {
    const partes = [...root.querySelectorAll('p,li,blockquote')].map(el => el.textContent.trim()).filter(Boolean);
    if (partes.length) return partes.join('\n').slice(0,4000);
    const texto = textoSemFormatacao(root); const nome = primeiroTitulo(root);
    return (nome && texto.startsWith(nome) ? texto.slice(nome.length).trim() : texto).slice(0,4000);
  }
  function atualizarAlvos() {
    $$('.ia-recurso-alvo').forEach(label => label.classList.toggle('ativo', !!$('input',label)?.checked));
    const alvo = alvoAtual();
    aplicarBtn.disabled = !htmlGerado;
    aplicarBtn.textContent = alvo === 'informacoes' ? tr('resources.ai_insert_info','Inserir nas informações') : tr('resources.ai_apply_catalog','Preencher formulário');
  }

  async function gerar() {
    const pedido = promptEl.value.trim();
    if (!pedido) { status.textContent = tr('editor.ai_prompt_required','Escreva um pedido.'); promptEl.focus(); return; }
    const alvo = alvoAtual();
    gerarBtn.disabled = true; aplicarBtn.disabled = true; preview.innerHTML = ''; htmlGerado = ''; textoGerado = '';
    status.textContent = tr('resources.ai_generating','Gerando…');
    const prompt = `${instrucoes(alvo)}\n\nPEDIDO DO USUÁRIO:\n${pedido}`;
    try {
      const r = await fetch('/api/ia/editor', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({
        modo:'epub', prompt, idioma: window.PROJETO_RECURSOS_INITIAL?.projeto?.idioma || 'pt-BR', contexto: contextoEditor(), recursos: contextoRecursos()
      })});
      const d = await r.json().catch(() => ({}));
      if (!r.ok || !d.html) throw new Error(d.erro || tr('resources.ai_error','Não foi possível gerar o recurso.'));
      const root = limparHtml(d.html);
      htmlGerado = root.innerHTML;
      textoGerado = textoSemFormatacao(root);
      preview.innerHTML = htmlGerado || '<p></p>';
      aplicarBtn.disabled = !htmlGerado;
      status.textContent = tr('resources.ai_ready','Conteúdo pronto para revisão.');
    } catch (err) {
      status.textContent = err.message || tr('resources.ai_error','Não foi possível gerar o recurso.');
    } finally { gerarBtn.disabled = false; }
  }

  function aplicar() {
    if (!htmlGerado) return;
    const alvo = alvoAtual();
    if (alvo === 'informacoes') {
      const editor = document.getElementById('editorInfoPagina');
      if (!editor) return;
      const atual = editor.innerHTML.trim();
      editor.innerHTML = atual && atual !== '<p></p>' ? `${atual}<p><br></p>${htmlGerado}` : htmlGerado;
      editor.dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:null}));
      fecharModal();
      return;
    }
    // Para catálogos, preencher o formulário existente e deixar o usuário revisar/salvar.
    const root = limparHtml(htmlGerado);
    const nome = primeiroTitulo(root) || textoGerado.split(/\n+/)[0].slice(0,80);
    const descricao = descricaoCatalogo(root);
    const tipo = alvo;
    const novoBtn = document.querySelector(`[data-novo-catalogo="${tipo}"]`);
    novoBtn?.click();
    setTimeout(() => {
      const tipoInput = document.getElementById('catalogoRecursosTipo');
      const nomeInput = document.getElementById('catalogoRecursosNome');
      const descInput = document.getElementById('catalogoRecursosDescricao');
      if (tipoInput) tipoInput.value = tipo;
      if (nomeInput) nomeInput.value = nome;
      if (descInput) descInput.value = descricao;
      const st = document.getElementById('statusCatalogoRecursos');
      if (st) st.textContent = tr('resources.ai_fill_done','Campos preenchidos. Revise e salve.');
      fecharModal();
    }, 0);
  }

  abrir.addEventListener('click', abrirModal);
  document.addEventListener('keydown', ev => {
    const key = String(ev.key || '').toLowerCase();
    if (ev.ctrlKey && ev.altKey && !ev.shiftKey && !ev.metaKey && key === 'g') {
      ev.preventDefault();
      if (!ev.repeat) abrir.click();
    }
  });
  gerarBtn.addEventListener('click', gerar);
  aplicarBtn.addEventListener('click', aplicar);
  $$('[data-fechar-ia-recursos="true"]', modal).forEach(el => el.addEventListener('click', ev => { ev.preventDefault(); fecharModal(); }));
  $$('input[name="iaRecursoAlvo"]').forEach(input => input.addEventListener('change', atualizarAlvos));
  document.addEventListener('keydown', ev => { if (ev.key === 'Escape' && !modal.classList.contains('oculto')) fecharModal(); });
  atualizarAlvos();
})();
