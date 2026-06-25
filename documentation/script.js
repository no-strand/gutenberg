/**
 * Controla a documentação HTML, alternando idioma, navegação interna e busca local de conteúdo.
 */

const translations = {
  "pt-BR": {
    "meta": {
      "title": "Documentação do Gutenberg",
      "brandSubtitle": "Documentação oficial do projeto",
      "searchPlaceholder": "Buscar na documentação...",
      "heroEyebrow": "Documentação",
      "heroTitle": "Gutenberg",
      "heroDescription": "Aprenda a usar o <strong>Gutenberg</strong> para criar livros, escrever roteiros, planejar projetos, revisar textos, exportar documentos e ler EPUBs ou PDFs na biblioteca integrada.",
      "footerText": "Documentação do projeto Gutenberg.",
      "menuLabel": "Abrir menu"
    },
    "nav": [
      [
        "visao-geral",
        "Visão geral"
      ],
      [
        "primeiros-passos",
        "Primeiros passos"
      ],
      [
        "modo-browser",
        "Modo browser e compatibilidade"
      ],
      [
        "tela-inicial",
        "Tela inicial"
      ],
      [
        "criar-projetos",
        "Criar projetos"
      ],
      [
        "livros",
        "Projetos de livro"
      ],
      [
        "editor-livro",
        "Editor de livro"
      ],
      [
        "leitor-capitulos",
        "Leitor de capítulos"
      ],
      [
        "roteiros",
        "Projetos de roteiro"
      ],
      [
        "editor-roteiro",
        "Editor de roteiro"
      ],
      [
        "catalogos",
        "Catálogos"
      ],
      [
        "recursos-projeto",
        "Recursos do projeto"
      ],
      [
        "revisao",
        "Revisão com Gemini"
      ],
      [
        "estatisticas",
        "Estatísticas"
      ],
      [
        "importacao",
        "Importação"
      ],
      [
        "gut-gutr",
        "Arquivos .gut e .gutr"
      ],
      [
        "exportacao",
        "Exportação"
      ],
      [
        "biblioteca",
        "Biblioteca"
      ],
      [
        "leitor-biblioteca",
        "Leitor EPUB/PDF"
      ],
      [
        "configuracoes",
        "Configurações"
      ],
      [
        "atualizacoes",
        "Atualizações"
      ],
      [
        "atalhos",
        "Atalhos"
      ],
      [
        "armazenamento",
        "Armazenamento e backup"
      ]
    ],
    "sections": {
      "visao-geral": "<section class=\"callout info\" id=\"visao-geral\"><h2>Visão geral</h2><p>O <strong>Gutenberg</strong> é um aplicativo local para escrever livros, criar roteiros, organizar materiais de apoio, revisar textos, exportar documentos e manter uma biblioteca de leitura. Ele funciona como uma interface web local e também pode ser aberto como aplicativo desktop.</p><p>A proposta é reunir o fluxo completo de escrita em um só lugar: você cria um projeto, escreve em capítulos ou em blocos de roteiro, consulta recursos do projeto, acompanha estatísticas, revisa com Gemini, exporta o resultado e ainda lê EPUBs ou PDFs importados para a biblioteca.</p><div class=\"card-grid two\"><article class=\"card\"><h3>Para escritores de livros</h3><p>Projetos de livro usam capítulos, capa, tags, editor rico, modo leitura e exportação para EPUB, XHTML, DOCX e PDF.</p></article><article class=\"card\"><h3>Para roteiristas</h3><p>Projetos de roteiro usam blocos próprios de roteiro, catálogo de personagens e locais, estatísticas de cena, tempo de fala e exportação em DOCX ou PDF.</p></article></div></section>",
      "primeiros-passos": "<section id=\"primeiros-passos\"><h2>Primeiros passos</h2><ol class=\"steps\"><li>Abra o Gutenberg pelo executável, por <code>python app.py</code> ou diretamente em modo browser com <code>python server_only.py</code>.</li><li>Na tela inicial, escolha entre criar um <strong>Livro</strong>, criar um <strong>Roteiro</strong>, abrir um projeto existente, entrar na <strong>Biblioteca</strong> ou ajustar as <strong>Configurações</strong>.</li><li>Antes de começar um projeto longo, configure a pasta de exportação, a pasta da biblioteca, o idioma da interface e, se for usar revisão automática, a chave da API Gemini.</li><li>Crie o projeto, escreva, use os recursos de planejamento e exporte quando estiver pronto.</li></ol><div class=\"callout tip\"><strong>Dica:</strong> o Gutenberg salva os dados localmente. Faça backups periódicos da pasta dos projetos e use arquivos <code>.gut</code> e <code>.gutr</code> para transportar conteúdo entre instalações.</div></section>",
      "modo-browser": "<section id=\"modo-browser\"><h2>Modo browser e compatibilidade</h2><p>O <strong>modo browser</strong> executa o Gutenberg como um servidor local e permite acessar a interface pelo navegador em <code>http://127.0.0.1:5000</code>. Ele é útil quando você prefere usar o navegador, quando o ambiente não suporta a janela desktop ou quando está em outro sistema operacional.</p><p>O modo desktop com <strong>pywebview</strong> exige <strong>Windows 10 ou superior</strong>. Se o computador estiver abaixo do Windows 10, se o <code>pywebview</code> não estiver disponível ou se o sistema operacional não for Windows, o Gutenberg tenta iniciar automaticamente em modo browser.</p><p>Se o <code>pystray</code> falhar, não estiver disponível ou o ambiente gráfico não permitir ícone de bandeja, o aplicativo cai automaticamente para o <strong>modo servidor</strong> sem tray, equivalente ao fluxo de <code>python server_only.py</code>. Nesse caso, acesse a interface pelo navegador em <code>http://127.0.0.1:5000</code> e encerre pelo terminal com Ctrl+C.</p><p>Também é possível iniciar diretamente esse modo com <code>python server_only.py</code> ou ativar <strong>Modo browser</strong> nas Configurações, quando disponível.</p></section>",
      "tela-inicial": "<section id=\"tela-inicial\"><h2>Tela inicial</h2><p>A tela inicial é o painel onde ficam seus projetos de livro e roteiro. Ela apresenta título, descrição, autor, idioma, tags ou contato, data de criação e data de atualização.</p><div class=\"table-wrap\"><table><thead><tr><th>Controle</th><th>Como usar</th></tr></thead><tbody><tr><td>Grade / Explorer</td><td>Alterne a visualização dos projetos entre cartões e lista compacta.</td></tr><tr><td>Configurações</td><td>Abra preferências de leitura, exportação, biblioteca, idioma, modo browser, efeito visual e Gemini.</td></tr><tr><td>Biblioteca</td><td>Entre na área de leitura de EPUBs e PDFs importados.</td></tr><tr><td>Novo projeto</td><td>Abra o formulário para criar livro ou roteiro.</td></tr><tr><td>Abrir</td><td>Entre no painel do projeto selecionado.</td></tr><tr><td>Excluir</td><td>Remove o projeto selecionado. Use com cuidado, pois é uma ação destrutiva.</td></tr></tbody></table></div><p>Quando o aplicativo detecta um arquivo <code>.gut</code> pendente no modo desktop, a tela inicial mostra uma janela para importar esse conteúdo para um projeto existente compatível ou criar um novo projeto a partir dele.</p></section>",
      "criar-projetos": "<section id=\"criar-projetos\"><h2>Criar projetos</h2><p>Clique em <strong>Novo projeto</strong> e escolha o tipo. O tipo define quais telas, editores, importações e exportações estarão disponíveis.</p><div class=\"card-grid two\"><article class=\"card\"><h3>Livro</h3><p>Use para romances, novelas, contos, ensaios e obras organizadas por capítulos. O formulário permite título, descrição, autor, idioma, tags e capa opcional.</p></article><article class=\"card\"><h3>Roteiro</h3><p>Use para scripts com cenas, ações, personagens e diálogos. O formulário permite título, descrição, autor, idioma, contato e informações adicionais.</p></article></div><h3>Campos importantes</h3><div class=\"table-wrap\"><table><thead><tr><th>Campo</th><th>Função</th></tr></thead><tbody><tr><td>Título</td><td>Nome do projeto. É obrigatório e usado para identificar a pasta e o cartão.</td></tr><tr><td>Idioma</td><td>Ajuda a revisão e a rotulagem do projeto.</td></tr><tr><td>Descrição</td><td>Resumo visível na tela inicial e no painel do projeto.</td></tr><tr><td>Autor</td><td>Usado na identificação do projeto e nas exportações.</td></tr><tr><td>Tags</td><td>Disponível para livros; serve para gênero, série, tema ou organização pessoal.</td></tr><tr><td>Contato</td><td>Disponível para roteiros; útil para informações de contato do autor ou produção.</td></tr><tr><td>Capa</td><td>Disponível para livros; aparece no painel e pode ser usada na exportação.</td></tr></tbody></table></div></section>",
      "livros": "<section id=\"livros\"><h2>Projetos de livro</h2><p>Ao abrir um projeto de livro, você vê a capa, os metadados e a lista de capítulos. A página centraliza as ações principais de escrita e publicação.</p><div class=\"card-grid two\"><article class=\"card\"><h3>Capa e metadados</h3><p>Clique na capa para trocar a imagem. Use <strong>Editar projeto</strong> para alterar título, descrição, autor, tags, contato e idioma.</p></article><article class=\"card\"><h3>Capítulos</h3><p>Crie capítulos com <strong>Novo capítulo</strong>. Cada item da lista permite editar, ler ou excluir.</p></article><article class=\"card\"><h3>Continuar</h3><p>Abre o último capítulo lido. Se ainda não houver histórico, abre o primeiro capítulo.</p></article><article class=\"card\"><h3>Importar e salvar capítulos</h3><p>Importe <code>.gut</code>, <code>.docx</code>, <code>.pdf</code> ou <code>.txt</code> como capítulos e gere um pacote <code>.gut</code> com os capítulos existentes.</p></article><article class=\"card\"><h3>Recursos</h3><p>Abre o esboço de planejamento do projeto, fluxograma, personagens, lugares e anotações.</p></article><article class=\"card\"><h3>Exportar</h3><p>Gere EPUB 2.0, EPUB 3.0, XHTML, DOCX ou PDF.</p></article></div></section>",
      "editor-livro": "<section id=\"editor-livro\"><h2>Editor de livro</h2><p>O editor de livro é uma folha de escrita com barra de ferramentas fixa, título editável e salvamento automático. O status no topo indica quando o conteúdo está pronto, sendo salvo ou já foi salvo.</p><h3>Ferramentas de formatação</h3><div class=\"table-wrap\"><table><thead><tr><th>Grupo</th><th>Recursos</th></tr></thead><tbody><tr><td>Parágrafo</td><td>Alinhar à esquerda, centralizar, alinhar à direita, justificar, remover/aumentar recuo.</td></tr><tr><td>Texto</td><td>Desfazer, refazer, negrito, itálico, sublinhado e troca de fonte serifada, sem serifa ou monoespaçada.</td></tr><tr><td>Estrutura</td><td>Parágrafo, H1, H2, H3, lista não ordenada e linha horizontal.</td></tr><tr><td>Elementos decorativos</td><td>Separadores como <code>◆◆◆</code> e delimitadores como <code>『』</code> para trechos selecionados.</td></tr><tr><td>Mídia e limpeza</td><td>Inserir imagem e limpar formatação do conteúdo selecionado ou atual.</td></tr><tr><td>Revisão</td><td>Abre a revisão ortográfica com Gemini.</td></tr></tbody></table></div><h3>Recursos dentro do texto</h3><p>O botão <strong>Recursos</strong> abre um modal com personagens, lugares e anotações sem sair do editor. Ao digitar pelo menos duas letras do nome de um recurso, o editor pode sugerir itens do catálogo; escolha uma sugestão para inserir a referência no texto e consultar detalhes pelo modal de Recursos.</p><h3>Modo leitura</h3><p>Use <strong>Modo leitura</strong> para conferir o capítulo como leitor. O modo mantém preferências de tema, fonte e tamanho de fonte.</p></section>",
      "leitor-capitulos": "<section id=\"leitor-capitulos\"><h2>Leitor de capítulos</h2><p>O leitor de capítulos mostra o texto em uma área ampla, com navegação por capítulo, sumário, progresso e preferências visuais.</p><div class=\"table-wrap\"><table><thead><tr><th>Controle</th><th>Função</th></tr></thead><tbody><tr><td>Voltar</td><td>Retorna ao painel do projeto.</td></tr><tr><td>Sumário</td><td>Abre a lista de capítulos e destaca o capítulo atual.</td></tr><tr><td>Editar</td><td>Volta ao editor do capítulo aberto.</td></tr><tr><td>Progresso</td><td>Mostra a porcentagem de leitura do capítulo.</td></tr><tr><td>Modo</td><td>Altera o tema visual: claro, escuro, sépia, azul escuro, terminal calmo, marrom quente, pôr do sol, gelo, rosa pastel ou estilo código.</td></tr><tr><td>Fonte</td><td>Troca entre serifada, sem serifa e monoespaçada.</td></tr><tr><td>Tamanho</td><td>Ajusta a fonte do texto do leitor.</td></tr><tr><td>&lt; e &gt;</td><td>Navega para capítulo anterior ou próximo quando existir.</td></tr></tbody></table></div><p>O leitor registra a posição de leitura para que o botão <strong>Continuar</strong> leve você de volta ao ponto mais recente.</p></section>",
      "roteiros": "<section id=\"roteiros\"><h2>Projetos de roteiro</h2><p>Um projeto de roteiro reúne um ou mais roteiros. Cada roteiro tem metadados próprios, como cabeçalho, rodapé, prefixo de cena, numeração inicial, logline, sinopse, gênero, tipo de roteiro e opção de copyright.</p><div class=\"card-grid two\"><article class=\"card\"><h3>Novo roteiro</h3><p>Cria um script dentro do projeto. O título é convertido para caixa alta, seguindo a linguagem de roteiro.</p></article><article class=\"card\"><h3>Cartões de roteiro</h3><p>Cada cartão permite editar o texto, gerenciar personagens, gerenciar locais, editar informações ou excluir.</p></article><article class=\"card\"><h3>Importar roteiros</h3><p>Adiciona conteúdo de <code>.gut</code>, <code>.docx</code>, <code>.pdf</code> ou <code>.txt</code> como roteiro compatível.</p></article><article class=\"card\"><h3>Salvar roteiro</h3><p>Gera um pacote <code>.gut</code> de um roteiro escolhido para backup ou transferência.</p></article><article class=\"card\"><h3>Recursos</h3><p>Abre a área de planejamento compartilhada do projeto.</p></article><article class=\"card\"><h3>Exportar</h3><p>Exporta um roteiro em PDF ou DOCX como roteiro, outline, estatística ou documento completo.</p></article></div></section>",
      "editor-roteiro": "<section id=\"editor-roteiro\"><h2>Editor de roteiro</h2><p>O editor de roteiro usa blocos especializados. Cada bloco representa uma função narrativa e recebe formatação própria na página.</p><div class=\"table-wrap\"><table><thead><tr><th>Bloco</th><th>Uso</th></tr></thead><tbody><tr><td>Cena</td><td>Cabeçalho de cena. O editor aplica numeração automática conforme o prefixo configurado.</td></tr><tr><td>Ação</td><td>Descrição visual, movimento, ambientação e ações de personagens.</td></tr><tr><td>Personagem</td><td>Nome de personagem antes de diálogo.</td></tr><tr><td>Diálogo</td><td>Fala do personagem. O editor estima tempo de fala.</td></tr><tr><td>Rubrica</td><td>Indicação curta entre personagem e diálogo.</td></tr><tr><td>Plano</td><td>Indicações de câmera, shot ou orientação visual.</td></tr><tr><td>Transição</td><td>Cortes e transições.</td></tr><tr><td>Comentário</td><td>Notas internas que podem ser ocultadas na visualização.</td></tr><tr><td>Música</td><td>Indicação musical.</td></tr><tr><td>Neutro</td><td>Texto auxiliar sem formato específico.</td></tr></tbody></table></div><h3>Como escrever</h3><ol class=\"steps compact\"><li>Escolha o tipo de bloco na barra ou use o atalho.</li><li>Digite o conteúdo do bloco.</li><li>Pressione <strong>Enter</strong> para criar o próximo bloco sugerido automaticamente.</li><li>Use o botão de comentários para ocultar ou mostrar notas internas.</li><li>Troque o tema do editor pelo seletor de modo da barra.</li></ol><p>O editor também oferece desfazer/refazer, seleção geral com Ctrl+A, autocomplete de cenas, personagens, transições e anotações, estatísticas, revisão e acesso ao painel de recursos.</p></section>",
      "catalogos": "<section id=\"catalogos\"><h2>Catálogos</h2><p>Catálogos são listas de personagens, locais e anotações que ajudam a manter consistência durante a escrita. Eles aparecem no painel de recursos do projeto e também podem ser consultados nos editores.</p><div class=\"card-grid two\"><article class=\"card\"><h3>Personagens</h3><p>Registre nomes, descrições e imagens de referência para personagens importantes. No roteiro, os nomes cadastrados podem aparecer como sugestões no bloco de personagem.</p></article><article class=\"card\"><h3>Locais</h3><p>Organize lugares relevantes do projeto, como cenários, cidades, ambientes internos e pontos recorrentes da história.</p></article><article class=\"card\"><h3>Anotações</h3><p>Guarde ideias, objetos, pistas, regras de mundo, linhas de pesquisa, lembretes e observações que precisam ficar disponíveis durante a escrita.</p></article></div></section>",
      "recursos-projeto": "<section id=\"recursos-projeto\"><h2>Recursos do projeto</h2><p>O painel <strong>Recursos</strong> funciona como um esboço de planejamento do projeto. Ele reúne materiais que não precisam entrar diretamente no capítulo ou no roteiro, mas ajudam a planejar e consultar o universo da obra.</p><div class=\"table-wrap\"><table><thead><tr><th>Aba</th><th>O que faz</th></tr></thead><tbody><tr><td>Informações</td><td>Crie páginas livres com editor rico, títulos, listas, negrito, itálico, sublinhado e imagens. Use para sinopse, linha do tempo, regras de mundo, pesquisa e notas de produção.</td></tr><tr><td>Fluxo</td><td>Monte um fluxograma com balões arrastáveis e ligações. Use para arcos, cenas, linhas temporais, relações ou etapas de trabalho.</td></tr><tr><td>Personagens</td><td>Cadastre personagem com nome, descrição e imagem de referência.</td></tr><tr><td>Lugares</td><td>Cadastre locais com nome, descrição e imagem de referência.</td></tr><tr><td>Anotações</td><td>Cadastre notas de texto para ideias, regras, objetos, pistas, temas ou lembretes.</td></tr></tbody></table></div><h3>Abas de páginas</h3><p>Cada opção de recursos tem abas internas de páginas. Use <strong>+</strong> para criar até 7 abas por opção, edite o nome na própria aba ativa e use <strong>×</strong> para remover a aba e o conteúdo guardado nela. Em <strong>Informações</strong>, cada aba superior cria uma área independente do recurso e mantém sua própria lista lateral de páginas.</p><h3>Fluxograma</h3><p>Use <strong>Adicionar balão</strong> para criar um nó. Conecte pontos de balões para formar relações. Use <strong>Cancelar conexão</strong> para interromper a criação de ligação. Quando precisar remover ligações específicas, use a interação indicada no próprio painel.</p><p>Para manusear fluxos grandes, mantenha <strong>Espaço</strong> pressionado dentro da área do fluxograma e arraste com o mouse. Esse gesto move a área rolável horizontal e verticalmente, sem alterar a posição dos balões.</p><h3>Salvar e importar recursos</h3><p><strong>Salvar recursos</strong> gera um arquivo <code>.gutr</code> com informações, fluxos, personagens, lugares, anotações e as abas internas. <strong>Importar recursos</strong> adiciona o conteúdo de um <code>.gutr</code> ao projeto aberto sem substituir capítulos ou roteiros.</p><h3>Uso dentro dos editores</h3><p>No editor de livro e no editor de roteiro, o botão <strong>Recursos</strong> abre um modal de consulta. Use <strong>Abrir painel</strong> quando quiser editar a versão completa.</p></section>",
      "revisao": "<section id=\"revisao\"><h2>Revisão com Gemini</h2><p>A revisão envia blocos de texto para o Gemini e mostra o texto atual ao lado de uma sugestão corrigida. O objetivo é apoiar correções de ortografia, pontuação, concordância e pequenos ajustes gramaticais preservando a estrutura do editor.</p><h3>Como conseguir uma chave gratuita</h3><p>A chave da API do Gemini pode ser criada no <strong>Google AI Studio</strong>. Acesse <a href=\"https://aistudio.google.com/app/apikey\" target=\"_blank\" rel=\"noopener\">https://aistudio.google.com/app/apikey</a>, entre com uma conta Google e crie uma chave de API para usar no Gutenberg.</p><ol class=\"steps compact\"><li>Abra o link oficial do Google AI Studio.</li><li>Faça login com sua conta Google.</li><li>Clique em <strong>Criar chave de API</strong> ou <strong>Get API key</strong>.</li><li>Copie a chave gerada.</li><li>Volte ao Gutenberg, abra <strong>Configurações</strong> e cole a chave no campo da Gemini.</li></ol><div class=\"callout tip\"><strong>Chave gratuita:</strong> a Gemini API oferece uma camada gratuita para começar, com acesso ao Google AI Studio e limites de uso. Se o usuário precisar de mais volume ou recursos pagos, pode configurar cobrança depois, mas a revisão do Gutenberg pode ser testada com a chave gratuita enquanto houver cota disponível.</div><div class=\"callout warn\"><strong>Segurança:</strong> não publique a chave em repositórios, imagens, prints ou mensagens. Ela deve ficar apenas nas configurações locais do Gutenberg.</div><h3>Como ativar no Gutenberg</h3><ol class=\"steps compact\"><li>Abra <strong>Configurações</strong>.</li><li>Preencha a <strong>chave da API do Google Gemini</strong>.</li><li>Salve as configurações.</li><li>Abra um capítulo ou roteiro e clique em <strong>Revisar</strong>.</li></ol><h3>Como revisar</h3><div class=\"table-wrap\"><table><thead><tr><th>Ação</th><th>Resultado</th></tr></thead><tbody><tr><td>Ignorar</td><td>Mantém o bloco como está e passa para o próximo.</td></tr><tr><td>Revisar</td><td>Solicita uma nova sugestão para o bloco atual.</td></tr><tr><td>Aceitar revisão</td><td>Substitui o bloco atual pela sugestão corrigida.</td></tr></tbody></table></div><div class=\"callout warn\"><strong>Atenção:</strong> revise as sugestões antes de aceitar. A ferramenta ajuda na correção, mas a decisão final de estilo e sentido continua sendo sua.</div></section>",
      "estatisticas": "<section id=\"estatisticas\"><h2>Estatísticas</h2><p>As estatísticas ajudam a acompanhar volume, ritmo e estrutura do projeto.</p><div class=\"card-grid two\"><article class=\"card\"><h3>Livro</h3><p>No painel do livro, clique em <strong>Estatísticas</strong>. O Gutenberg mostra total de palavras, capítulos, tempo estimado de leitura, páginas e laudas estimadas, vocabulário único, médias por capítulo, parágrafo e frase, títulos H1/H2/H3, capítulos vazios, imagens, links, listas, citações, distribuição por capítulo, maior e menor capítulo e vocabulário recorrente. Também é possível exportar as estatísticas em PDF.</p></article><article class=\"card\"><h3>Roteiro</h3><p>No editor de roteiro, abra o botão de estatísticas. O painel mostra palavras, caracteres, cenas, locais, personagens, tempo total de diálogo, tempo por personagem, falas mais longas, entradas de personagem, uso de locais, equilíbrio entre diálogo e ação, ritmo de cenas e distribuição narrativa.</p></article></div><p>Use esses dados como referência editorial: eles ajudam a encontrar capítulos curtos demais, cenas densas, excesso de diálogo, personagens dominantes ou pontos do texto que precisam de revisão estrutural.</p></section>",
      "importacao": "<section id=\"importacao\"><h2>Importação</h2><p>O Gutenberg permite trazer conteúdo externo para dentro de projetos existentes.</p><div class=\"table-wrap\"><table><thead><tr><th>Arquivo</th><th>Em livro</th><th>Em roteiro</th></tr></thead><tbody><tr><td><code>.gut</code></td><td>Importa capítulos salvos de outro projeto de livro.</td><td>Importa roteiro salvo de outro projeto de roteiro.</td></tr><tr><td><code>.docx</code></td><td>Converte o documento em capítulo ou capítulos.</td><td>Converte o documento em roteiro estruturado.</td></tr><tr><td><code>.pdf</code></td><td>Extrai texto e tenta organizar como capítulo.</td><td>Extrai texto e tenta organizar como roteiro.</td></tr><tr><td><code>.txt</code></td><td>Importa texto simples como conteúdo de livro.</td><td>Importa texto simples como roteiro.</td></tr><tr><td><code>.gutr</code></td><td colspan=\"2\">Importa apenas recursos do projeto: informações, fluxo, personagens, lugares e anotações.</td></tr></tbody></table></div><div class=\"callout info\"><strong>Observação:</strong> DOCX e TXT tendem a importar com mais previsibilidade. PDFs podem variar conforme a estrutura do arquivo original.</div></section>",
      "gut-gutr": "<section id=\"gut-gutr\"><h2>Arquivos .gut e .gutr</h2><p>O Gutenberg usa dois formatos próprios para backup e transferência.</p><div class=\"card-grid two\"><article class=\"card\"><h3><code>.gut</code></h3><p>Salva conteúdo principal: capítulos de um livro ou um roteiro selecionado. Use para transportar texto entre projetos compatíveis ou manter snapshots do trabalho.</p></article><article class=\"card\"><h3><code>.gutr</code></h3><p>Salva recursos do projeto: páginas de informação, fluxograma, personagens, lugares e anotações. Use para reutilizar um esboço de projeto ou transferir planejamento.</p></article></div><h3>Importação pendente no desktop</h3><p>No modo desktop, um arquivo <code>.gut</code> aberto pelo sistema pode aparecer como importação pendente. A tela inicial permite escolher um projeto compatível ou criar um novo projeto para receber o conteúdo.</p></section>",
      "exportacao": "<section id=\"exportacao\"><h2>Exportação</h2><p>A exportação usa a pasta configurada em <strong>Configurações</strong>. Depois de exportar, o aplicativo entrega o arquivo gerado ou informa a pasta criada.</p><div class=\"table-wrap\"><table><thead><tr><th>Tipo de projeto</th><th>Formatos</th><th>Uso recomendado</th></tr></thead><tbody><tr><td>Livro</td><td>EPUB 2.0, EPUB 3.0</td><td>Distribuição para leitores digitais e validação de fluxo de ebook.</td></tr><tr><td>Livro</td><td>XHTML</td><td>Saída simples em páginas HTML para inspeção ou uso intermediário.</td></tr><tr><td>Livro</td><td>DOCX</td><td>Revisão em processador de texto.</td></tr><tr><td>Livro</td><td>PDF</td><td>Leitura, compartilhamento e prova visual.</td></tr><tr><td>Roteiro</td><td>DOCX, PDF</td><td>Exportação de roteiro, outline, estatística ou documento completo.</td></tr></tbody></table></div><p>Para melhores resultados, revise o conteúdo antes da exportação, confira títulos, imagens, capítulos vazios e metadados do projeto.</p></section>",
      "biblioteca": "<section id=\"biblioteca\"><h2>Biblioteca</h2><p>A Biblioteca é uma área separada dos projetos de escrita. Ela serve para importar e ler arquivos <strong>EPUB</strong> e <strong>PDF</strong> com acompanhamento de progresso.</p><div class=\"table-wrap\"><table><thead><tr><th>Controle</th><th>Função</th></tr></thead><tbody><tr><td>Adicionar livro</td><td>Importa um ou mais arquivos EPUB/PDF.</td></tr><tr><td>Busca</td><td>Filtra livros por título, autor, idioma ou arquivo original.</td></tr><tr><td>Lendo / Todos / Lidos</td><td>Filtra a biblioteca por estado de leitura.</td></tr><tr><td>Coleções</td><td>Mostra agrupamentos automáticos por coleção/chave detectada.</td></tr><tr><td>✓</td><td>Marca ou desmarca um livro como lido.</td></tr><tr><td>Lixeira</td><td>Remove o livro da biblioteca local.</td></tr></tbody></table></div><p>Cada capa mostra a porcentagem de progresso. Ao abrir um livro, o Gutenberg tenta voltar ao último capítulo ou posição lida.</p></section>",
      "leitor-biblioteca": "<section id=\"leitor-biblioteca\"><h2>Leitor EPUB/PDF</h2><p>O leitor da biblioteca usa uma visualização adaptada para livros importados. PDFs são convertidos para leitura interna, e EPUBs são exibidos por capítulos.</p><div class=\"card-grid two\"><article class=\"card\"><h3>Sumário</h3><p>Abre a árvore de capítulos do livro. Em EPUBs com níveis, o recuo indica hierarquia.</p></article><article class=\"card\"><h3>Progresso</h3><p>Salva posição e porcentagem de leitura no livro.</p></article><article class=\"card\"><h3>Preferências visuais</h3><p>Use modo, fonte e tamanho para ajustar a leitura. As preferências são globais para os leitores.</p></article><article class=\"card\"><h3>Navegação</h3><p>Use os botões de capítulo anterior/próximo ou atalhos de teclado.</p></article></div><p>O leitor EPUB/PDF mantém a mesma família de temas do leitor de capítulos: claro, escuro, sépia e outros modos de conforto visual.</p></section>",
      "configuracoes": "<section id=\"configuracoes\"><h2>Configurações</h2><p>A tela de configurações controla aparência de leitura, pastas, revisão, idioma e comportamento do aplicativo.</p><div class=\"table-wrap\"><table><thead><tr><th>Configuração</th><th>O que altera</th></tr></thead><tbody><tr><td>Recuo padrão e recuo aumentado</td><td>Define indentação normal e indentação maior usadas em leitura e exportação.</td></tr><tr><td>Espaço entre parágrafos e linhas</td><td>Ajusta conforto de leitura e prévia visual.</td></tr><tr><td>Tamanho base da fonte</td><td>Define a escala principal do texto.</td></tr><tr><td>H1, H2, H3</td><td>Controla o tamanho dos títulos.</td></tr><tr><td>Largura de leitura</td><td>Define largura máxima da área de texto.</td></tr><tr><td>Idioma do aplicativo</td><td>Alterna a interface entre Português (Brasil) e English (US).</td></tr><tr><td>Documentação</td><td>Abre esta documentação.</td></tr><tr><td>Verificar atualizações</td><td>Consulta o GitHub Releases do repositório <code>no-strand/gutenberg</code>, compara a versão instalada com a última release e, quando houver pacote compatível para o sistema operacional, permite iniciar a atualização.</td></tr><tr><td>Pasta de exportação</td><td>Local onde os arquivos exportados serão salvos.</td></tr><tr><td>Pasta da biblioteca</td><td>Local onde EPUBs/PDFs importados serão organizados.</td></tr><tr><td>Chave Gemini</td><td>Habilita a revisão com Gemini.</td></tr><tr><td>Modo browser</td><td>Usa o aplicativo em navegador/tray, quando disponível; se o pystray falhar, usa modo servidor sem tray.</td></tr><tr><td>Efeito do editor</td><td>Ativa ou desativa o efeito visual de partículas nas páginas de edição.</td></tr></tbody></table></div><p>A prévia no fim da tela mostra como as opções de leitura afetam títulos, parágrafos, recuos e espaçamentos.</p></section>",
      "atualizacoes": "<section id=\"atualizacoes\"><h2>Atualizações</h2><p>O Gutenberg pode verificar se existe uma versão mais recente do aplicativo disponível para instalação.</p><p>Em <strong>Configurações</strong>, use o botão <strong>Verificar atualizações</strong> para conferir manualmente. Uma janela será aberta informando se o programa já está atualizado ou se existe uma nova versão disponível.</p><p>Além disso, ao abrir a tela inicial, o Gutenberg pode fazer uma verificação automática no máximo uma vez por semana. Quando a consulta é concluída, um pequeno aviso aparece no canto da tela com o resultado. Se houver atualização, o aviso mostra o botão <strong>Atualizar agora</strong> para iniciar o processo.</p><p>Se o aplicativo não conseguir verificar naquele momento, por exemplo por falta de conexão, ele simplesmente ignora a tentativa e continua abrindo normalmente, sem interromper o uso.</p></section>",
      "atalhos": "<section id=\"atalhos\"><h2>Atalhos</h2><h3>Editor de livro</h3><div class=\"table-wrap\"><table><thead><tr><th>Ação</th><th>Atalho</th></tr></thead><tbody><tr><td>Desfazer / refazer</td><td>Ctrl+Z / Ctrl+Y ou Ctrl+Shift+Z</td></tr><tr><td>Alinhar esquerda, centro, direita, justificar</td><td>Alt+E, Alt+C, Alt+D, Alt+J</td></tr><tr><td>Negrito, itálico, sublinhado</td><td>Alt+B, Alt+I, Alt+U</td></tr><tr><td>Parágrafo, H1, H2, H3, lista</td><td>Alt+P, Alt+1, Alt+2, Alt+3, Alt+L</td></tr><tr><td>Linha horizontal</td><td>Alt+R</td></tr><tr><td>Delimitador decorativo</td><td>Alt+Q</td></tr><tr><td>Separador decorativo</td><td>Ctrl+Alt+Q</td></tr><tr><td>Recuo esquerda/direita</td><td>Ctrl+Alt+E / Ctrl+Alt+D</td></tr><tr><td>Fonte sem serifa, serifada, monoespaçada</td><td>Ctrl+Alt+X, Ctrl+Alt+S, Ctrl+Alt+M</td></tr><tr><td>Inserir imagem</td><td>Ctrl+Alt+I</td></tr><tr><td>Limpar edição</td><td>Ctrl+Alt+L</td></tr><tr><td>Revisar</td><td>Ctrl+Alt+R</td></tr></tbody></table></div><h3>Editor de roteiro</h3><div class=\"table-wrap\"><table><thead><tr><th>Ação</th><th>Atalho</th></tr></thead><tbody><tr><td>Desfazer / refazer</td><td>Ctrl+Z / Ctrl+Shift+Z</td></tr><tr><td>Selecionar blocos do roteiro</td><td>Ctrl+A no editor</td></tr><tr><td>Ir para primeira/última cena</td><td>Alt+1 / Alt+0</td></tr><tr><td>Ocultar ou mostrar comentários</td><td>Alt+O</td></tr><tr><td>Cena, ação, personagem, diálogo</td><td>Alt+C, Alt+A, Alt+P, Alt+D</td></tr><tr><td>Rubrica, plano, transição</td><td>Alt+S, Alt+L, Alt+T</td></tr><tr><td>Comentário, música, neutro</td><td>Alt+N, Alt+M, Alt+E</td></tr><tr><td>Catálogo de personagens/locais</td><td>Ctrl+Alt+P / Ctrl+Alt+L</td></tr><tr><td>Estatísticas</td><td>Ctrl+Alt+I</td></tr><tr><td>Revisão</td><td>Ctrl+Alt+R</td></tr></tbody></table></div><h3>Leitores</h3><p>Use <strong>←</strong> ou <strong>&lt;</strong> para o capítulo anterior, <strong>→</strong> ou <strong>&gt;</strong> para o próximo, <strong>↑</strong> e <strong>↓</strong> para rolar, <strong>S</strong> para abrir o sumário e <strong>Esc</strong> para fechar o sumário ou voltar.</p></section>",
      "armazenamento": "<section id=\"armazenamento\"><h2>Armazenamento e backup</h2><p>O Gutenberg guarda dados localmente. Os caminhos podem variar conforme o sistema e as configurações, mas o projeto trabalha com três grupos principais.</p><ul class=\"clean-list\"><li><strong>Projetos:</strong> livros e roteiros criados pelo usuário.</li><li><strong>Exportações:</strong> arquivos gerados em EPUB, XHTML, DOCX, PDF, <code>.gut</code> ou <code>.gutr</code>.</li><li><strong>Biblioteca:</strong> EPUBs/PDFs importados, capas, arquivos extraídos e progresso.</li></ul><h3>Como fazer backup</h3><ol class=\"steps compact\"><li>Copie a pasta local onde seus projetos são salvos.</li><li>Exporte <code>.gut</code> dos capítulos ou roteiros importantes.</li><li>Exporte <code>.gutr</code> dos recursos de projeto importantes.</li><li>Guarde os arquivos exportados fora da pasta principal, como em um drive externo ou serviço de nuvem.</li></ol><div class=\"callout warn\"><strong>Importante:</strong> excluir um projeto ou livro remove dados locais. Tenha backup antes de limpar sua biblioteca ou projetos antigos.</div></section>",
    }
  },
  "en-US": {
    "meta": {
      "title": "Gutenberg Documentation",
      "brandSubtitle": "Official project documentation",
      "searchPlaceholder": "Search the documentation...",
      "heroEyebrow": "Documentation",
      "heroTitle": "Gutenberg",
      "heroDescription": "Learn how to use <strong>Gutenberg</strong> to create books, write screenplays, plan projects, revise text, export documents, and read EPUBs or PDFs in the built-in library.",
      "footerText": "Gutenberg project documentation.",
      "menuLabel": "Open menu"
    },
    "nav": [
      [
        "visao-geral",
        "Overview"
      ],
      [
        "primeiros-passos",
        "First steps"
      ],
      [
        "modo-browser",
        "Browser mode and compatibility"
      ],
      [
        "tela-inicial",
        "Home screen"
      ],
      [
        "criar-projetos",
        "Create projects"
      ],
      [
        "livros",
        "Book projects"
      ],
      [
        "editor-livro",
        "Book editor"
      ],
      [
        "leitor-capitulos",
        "Chapter reader"
      ],
      [
        "roteiros",
        "Screenplay projects"
      ],
      [
        "editor-roteiro",
        "Screenplay editor"
      ],
      [
        "catalogos",
        "Catalogs"
      ],
      [
        "recursos-projeto",
        "Project resources"
      ],
      [
        "revisao",
        "Gemini revision"
      ],
      [
        "estatisticas",
        "Statistics"
      ],
      [
        "importacao",
        "Import"
      ],
      [
        "gut-gutr",
        ".gut and .gutr files"
      ],
      [
        "exportacao",
        "Export"
      ],
      [
        "biblioteca",
        "Library"
      ],
      [
        "leitor-biblioteca",
        "EPUB/PDF reader"
      ],
      [
        "configuracoes",
        "Settings"
      ],
      [
        "atualizacoes",
        "Updates"
      ],
      [
        "atalhos",
        "Shortcuts"
      ],
      [
        "armazenamento",
        "Storage and backup"
      ]
    ],
    "sections": {
      "visao-geral": "<section class=\"callout info\" id=\"visao-geral\"><h2>Overview</h2><p><strong>Gutenberg</strong> is a local application for writing books, creating screenplays, organizing reference material, revising text, exporting documents, and maintaining a reading library. It runs as a local web interface and can also be opened as a desktop app.</p><p>Its goal is to keep the writing workflow in one place: create a project, write in chapters or screenplay blocks, consult project resources, track statistics, revise with Gemini, export the result, and read EPUBs or PDFs in the built-in library.</p><div class=\"card-grid two\"><article class=\"card\"><h3>For book writers</h3><p>Book projects use chapters, cover images, tags, a rich editor, reading mode, and export to EPUB, XHTML, DOCX, and PDF.</p></article><article class=\"card\"><h3>For screenwriters</h3><p>Screenplay projects use specialized blocks, character and location catalogs, scene statistics, dialogue timing, and export to DOCX or PDF.</p></article></div></section>",
      "primeiros-passos": "<section id=\"primeiros-passos\"><h2>First steps</h2><ol class=\"steps\"><li>Open Gutenberg through the executable, with <code>python app.py</code>, or directly in browser mode with <code>python server_only.py</code>.</li><li>On the home screen, create a <strong>Book</strong>, create a <strong>Screenplay</strong>, open an existing project, enter the <strong>Library</strong>, or adjust <strong>Settings</strong>.</li><li>Before starting a long project, configure the export folder, library folder, interface language, and, if you plan to use automatic revision, the Gemini API key.</li><li>Create the project, write, use planning resources, and export when ready.</li></ol><div class=\"callout tip\"><strong>Tip:</strong> Gutenberg stores data locally. Back up your project folder regularly and use <code>.gut</code> and <code>.gutr</code> files to move content between installations.</div></section>",
      "modo-browser": "<section id=\"modo-browser\"><h2>Browser mode and compatibility</h2><p><strong>Browser mode</strong> runs Gutenberg as a local server and lets you access the interface in your browser at <code>http://127.0.0.1:5000</code>. It is useful when you prefer the browser, when the environment does not support the desktop window, or when you are on another operating system.</p><p>The <strong>pywebview</strong> desktop mode requires <strong>Windows 10 or later</strong>. If the computer is below Windows 10, if <code>pywebview</code> is unavailable, or if the operating system is not Windows, Gutenberg tries to start automatically in browser mode.</p><p>If <code>pystray</code> fails, is unavailable, or the graphical environment does not allow a tray icon, the app automatically falls back to <strong>server mode</strong> without tray, equivalent to the <code>python server_only.py</code> flow. In that case, open the interface in your browser at <code>http://127.0.0.1:5000</code> and stop it from the terminal with Ctrl+C.</p><p>You can also start this mode directly with <code>python server_only.py</code> or enable <strong>Browser mode</strong> in Settings when available.</p></section>",
      "tela-inicial": "<section id=\"tela-inicial\"><h2>Home screen</h2><p>The home screen is the dashboard for your book and screenplay projects. It shows title, description, author, language, tags or contact, creation date, and update date.</p><div class=\"table-wrap\"><table><thead><tr><th>Control</th><th>How to use it</th></tr></thead><tbody><tr><td>Grid / Explorer</td><td>Switch the project view between cards and a compact list.</td></tr><tr><td>Settings</td><td>Open reading, export, library, language, browser mode, visual effect, and Gemini preferences.</td></tr><tr><td>Library</td><td>Enter the EPUB/PDF reading area.</td></tr><tr><td>New project</td><td>Open the form to create a book or screenplay.</td></tr><tr><td>Open</td><td>Enter the selected project dashboard.</td></tr><tr><td>Delete</td><td>Removes the selected project. Use carefully, because it is destructive.</td></tr></tbody></table></div><p>When the desktop app detects a pending <code>.gut</code> file, the home screen displays a dialog to import it into a compatible existing project or create a new project from it.</p></section>",
      "criar-projetos": "<section id=\"criar-projetos\"><h2>Create projects</h2><p>Click <strong>New project</strong> and choose a type. The type determines which screens, editors, imports, and exports are available.</p><div class=\"card-grid two\"><article class=\"card\"><h3>Book</h3><p>Use it for novels, novellas, short stories, essays, and works organized by chapter. The form supports title, description, author, language, tags, and optional cover.</p></article><article class=\"card\"><h3>Screenplay</h3><p>Use it for scripts with scenes, action, characters, and dialogue. The form supports title, description, author, language, contact, and additional information.</p></article></div><h3>Important fields</h3><div class=\"table-wrap\"><table><thead><tr><th>Field</th><th>Purpose</th></tr></thead><tbody><tr><td>Title</td><td>Project name. Required and used to identify the folder and card.</td></tr><tr><td>Language</td><td>Helps revision and project labeling.</td></tr><tr><td>Description</td><td>Summary visible on the home screen and project dashboard.</td></tr><tr><td>Author</td><td>Used in project identification and exports.</td></tr><tr><td>Tags</td><td>Available for books; useful for genre, series, themes, or personal organization.</td></tr><tr><td>Contact</td><td>Available for screenplays; useful for author or production contact information.</td></tr><tr><td>Cover</td><td>Available for books; appears on the dashboard and can be used in export.</td></tr></tbody></table></div></section>",
      "livros": "<section id=\"livros\"><h2>Book projects</h2><p>When you open a book project, you see the cover, metadata, and chapter list. This page centralizes the main writing and publishing actions.</p><div class=\"card-grid two\"><article class=\"card\"><h3>Cover and metadata</h3><p>Click the cover to change the image. Use <strong>Edit project</strong> to change title, description, author, tags, contact, and language.</p></article><article class=\"card\"><h3>Chapters</h3><p>Create chapters with <strong>New chapter</strong>. Each row lets you edit, read, or delete.</p></article><article class=\"card\"><h3>Continue</h3><p>Opens the last chapter you read. If there is no history yet, it opens the first chapter.</p></article><article class=\"card\"><h3>Import and save chapters</h3><p>Import <code>.gut</code>, <code>.docx</code>, <code>.pdf</code>, or <code>.txt</code> as chapters and generate a <code>.gut</code> package from existing chapters.</p></article><article class=\"card\"><h3>Resources</h3><p>Opens the project planning outline, flowchart, characters, places, and notes.</p></article><article class=\"card\"><h3>Export</h3><p>Generate EPUB 2.0, EPUB 3.0, XHTML, DOCX, or PDF.</p></article></div></section>",
      "editor-livro": "<section id=\"editor-livro\"><h2>Book editor</h2><p>The book editor is a writing page with a fixed toolbar, editable title, and autosave. The top status indicates whether the content is ready, being saved, or already saved.</p><h3>Formatting tools</h3><div class=\"table-wrap\"><table><thead><tr><th>Group</th><th>Features</th></tr></thead><tbody><tr><td>Paragraph</td><td>Align left, center, align right, justify, remove/increase indent.</td></tr><tr><td>Text</td><td>Undo, redo, bold, italic, underline, and switch between serif, sans, or monospaced fonts.</td></tr><tr><td>Structure</td><td>Paragraph, H1, H2, H3, unordered list, and horizontal rule.</td></tr><tr><td>Decorative elements</td><td>Separators such as <code>◆◆◆</code> and wrappers such as <code>『』</code> for selected text.</td></tr><tr><td>Media and cleanup</td><td>Insert image and clear formatting from the current or selected content.</td></tr><tr><td>Revision</td><td>Opens Gemini-based spelling revision.</td></tr></tbody></table></div><h3>Resources inside the text</h3><p>The <strong>Resources</strong> button opens a modal with characters, places, and notes without leaving the editor. After typing at least two letters of a resource name, the editor can suggest links; choose a suggestion to create a consultable link in the text.</p><h3>Reading mode</h3><p>Use <strong>Reading mode</strong> to check the chapter as a reader. It keeps theme, font, and font-size preferences.</p></section>",
      "leitor-capitulos": "<section id=\"leitor-capitulos\"><h2>Chapter reader</h2><p>The chapter reader displays the text in a wide reading area with chapter navigation, table of contents, progress, and visual preferences.</p><div class=\"table-wrap\"><table><thead><tr><th>Control</th><th>Purpose</th></tr></thead><tbody><tr><td>Back</td><td>Returns to the project dashboard.</td></tr><tr><td>Summary</td><td>Opens the chapter list and highlights the current chapter.</td></tr><tr><td>Edit</td><td>Returns to the editor for the open chapter.</td></tr><tr><td>Progress</td><td>Shows the reading percentage for the chapter.</td></tr><tr><td>Mode</td><td>Changes the visual theme: light, dark, sepia, dark blue, calm terminal, warm brown, sunset, frost, pastel pink, or code-like.</td></tr><tr><td>Font</td><td>Switches between serif, sans, and monospaced fonts.</td></tr><tr><td>Size</td><td>Adjusts the reader text size.</td></tr><tr><td>&lt; and &gt;</td><td>Navigates to the previous or next chapter when available.</td></tr></tbody></table></div><p>The reader stores the reading position so <strong>Continue</strong> can take you back to your latest point.</p></section>",
      "roteiros": "<section id=\"roteiros\"><h2>Screenplay projects</h2><p>A screenplay project can contain one or more scripts. Each script has its own metadata: header, footer, scene prefix, initial scene number, logline, synopsis, genre, script type, and copyright option.</p><div class=\"card-grid two\"><article class=\"card\"><h3>New script</h3><p>Creates a script inside the project. The title is converted to uppercase, following screenplay conventions.</p></article><article class=\"card\"><h3>Script cards</h3><p>Each card lets you edit the text, manage characters, manage locations, edit information, or delete.</p></article><article class=\"card\"><h3>Import scripts</h3><p>Adds content from <code>.gut</code>, <code>.docx</code>, <code>.pdf</code>, or <code>.txt</code> as a compatible script.</p></article><article class=\"card\"><h3>Save script</h3><p>Generates a <code>.gut</code> package from a selected script for backup or transfer.</p></article><article class=\"card\"><h3>Resources</h3><p>Opens the shared planning area for the project.</p></article><article class=\"card\"><h3>Export</h3><p>Exports a script as PDF or DOCX as script, outline, statistics, or complete document.</p></article></div></section>",
      "editor-roteiro": "<section id=\"editor-roteiro\"><h2>Screenplay editor</h2><p>The screenplay editor uses specialized blocks. Each block represents a narrative function and receives its own page formatting.</p><div class=\"table-wrap\"><table><thead><tr><th>Block</th><th>Use</th></tr></thead><tbody><tr><td>Scene</td><td>Scene heading. The editor applies automatic numbering according to the configured prefix.</td></tr><tr><td>Action</td><td>Visual description, movement, environment, and character actions.</td></tr><tr><td>Character</td><td>Character name before dialogue.</td></tr><tr><td>Dialogue</td><td>Character speech. The editor estimates speaking time.</td></tr><tr><td>Parenthetical</td><td>Short direction between character and dialogue.</td></tr><tr><td>Shot</td><td>Camera, shot, or visual direction.</td></tr><tr><td>Transition</td><td>Cuts and transitions.</td></tr><tr><td>Comment</td><td>Internal notes that can be hidden from view.</td></tr><tr><td>Music</td><td>Music cue.</td></tr><tr><td>Neutral</td><td>Auxiliary text without a specific format.</td></tr></tbody></table></div><h3>How to write</h3><ol class=\"steps compact\"><li>Choose the block type in the toolbar or use a shortcut.</li><li>Type the block content.</li><li>Press <strong>Enter</strong> to create the automatically suggested next block.</li><li>Use the comments button to hide or show internal notes.</li><li>Change the editor theme with the mode selector in the toolbar.</li></ol><p>The editor also includes undo/redo, Ctrl+A block selection, autocomplete for scenes, characters, transitions and notes, statistics, revision, and access to project resources.</p></section>",
      "catalogos": "<section id=\"catalogos\"><h2>Catalogs</h2><p>Catalogs are lists of characters, locations, and notes that help keep writing consistent. They appear in the project resources panel and can also be consulted inside the editors.</p><div class=\"card-grid two\"><article class=\"card\"><h3>Characters</h3><p>Register names, descriptions, and reference images for important characters. In screenplays, saved names can appear as suggestions in character blocks.</p></article><article class=\"card\"><h3>Locations</h3><p>Organize relevant project places, such as settings, cities, interior spaces, and recurring story locations.</p></article><article class=\"card\"><h3>Notes</h3><p>Store ideas, objects, clues, world rules, research lines, reminders, and observations that should stay available while writing.</p></article></div></section>",
      "recursos-projeto": "<section id=\"recursos-projeto\"><h2>Project resources</h2><p>The <strong>Resources</strong> panel works as a project planning outline. It stores material that does not need to go directly into a chapter or script, but helps you plan and consult the world of the work.</p><div class=\"table-wrap\"><table><thead><tr><th>Tab</th><th>What it does</th></tr></thead><tbody><tr><td>Information</td><td>Create free pages with a rich editor, headings, lists, bold, italic, underline, and images. Use it for synopsis, timeline, world rules, research, and production notes.</td></tr><tr><td>Flow</td><td>Build a flowchart with draggable balloons and connections. Use it for arcs, scenes, timelines, relationships, or workflow steps.</td></tr><tr><td>Characters</td><td>Register a character with name, description, and reference image.</td></tr><tr><td>Places</td><td>Register locations with name, description, and reference image.</td></tr><tr><td>Notes</td><td>Register text notes for ideas, rules, objects, clues, themes, or reminders.</td></tr></tbody></table></div><h3>Page tabs</h3><p>Each resource option has internal page tabs. Use <strong>+</strong> to create up to 7 tabs per option, edit the name in the active tab, and use <strong>×</strong> to remove the tab and the content stored in it. In <strong>Information</strong>, each upper tab creates an independent area for the resource and keeps its own side page list.</p><h3>Flowchart</h3><p>Use <strong>Add balloon</strong> to create a node. Connect balloon points to form relationships. Use <strong>Cancel connection</strong> to stop creating a link. When you need to remove specific links, use the interaction shown in the panel.</p><p>For large flows, hold <strong>Space</strong> inside the flowchart area and drag with the mouse. This gesture pans the horizontal and vertical scroll area without moving the balloons themselves.</p><h3>Save and import resources</h3><p><strong>Save resources</strong> generates a <code>.gutr</code> file containing information, flows, characters, places, notes, and the internal tabs. <strong>Import resources</strong> adds the contents of a <code>.gutr</code> to the open project without replacing chapters or scripts.</p><h3>Use inside editors</h3><p>In the book editor and screenplay editor, the <strong>Resources</strong> button opens a consultation modal. Use <strong>Open panel</strong> when you need to edit the full version.</p></section>",
      "revisao": "<section id=\"revisao\"><h2>Gemini revision</h2><p>Revision sends text blocks to Gemini and shows the current text beside a corrected suggestion. It is meant to help with spelling, punctuation, agreement, and small grammatical adjustments while preserving the editor structure.</p><h3>How to get a free key</h3><p>The Gemini API key can be created in <strong>Google AI Studio</strong>. Open <a href=\"https://aistudio.google.com/app/apikey\" target=\"_blank\" rel=\"noopener\">https://aistudio.google.com/app/apikey</a>, sign in with a Google account, and create an API key to use in Gutenberg.</p><ol class=\"steps compact\"><li>Open the official Google AI Studio link.</li><li>Sign in with your Google account.</li><li>Click <strong>Create API key</strong> or <strong>Get API key</strong>.</li><li>Copy the generated key.</li><li>Return to Gutenberg, open <strong>Settings</strong>, and paste the key into the Gemini field.</li></ol><div class=\"callout tip\"><strong>Free key:</strong> the Gemini API offers a free tier to get started, with Google AI Studio access and usage limits. If the user needs higher volume or paid features, billing can be configured later, but Gutenberg revision can be tested with the free key while quota is available.</div><div class=\"callout warn\"><strong>Security:</strong> do not publish the key in repositories, images, screenshots, or messages. It should stay only in Gutenberg's local settings.</div><h3>How to enable in Gutenberg</h3><ol class=\"steps compact\"><li>Open <strong>Settings</strong>.</li><li>Fill in the <strong>Google Gemini API key</strong>.</li><li>Save settings.</li><li>Open a chapter or script and click <strong>Review</strong>.</li></ol><h3>How to revise</h3><div class=\"table-wrap\"><table><thead><tr><th>Action</th><th>Result</th></tr></thead><tbody><tr><td>Ignore</td><td>Keeps the block as it is and moves to the next one.</td></tr><tr><td>Review</td><td>Requests a new suggestion for the current block.</td></tr><tr><td>Accept review</td><td>Replaces the current block with the corrected suggestion.</td></tr></tbody></table></div><div class=\"callout warn\"><strong>Attention:</strong> read suggestions before accepting them. The tool helps with correction, but the final decision about style and meaning remains yours.</div></section>",
      "estatisticas": "<section id=\"estatisticas\"><h2>Statistics</h2><p>Statistics help you track volume, rhythm, and structure.</p><div class=\"card-grid two\"><article class=\"card\"><h3>Book</h3><p>On the book dashboard, click <strong>Statistics</strong>. Gutenberg shows total words, chapters, estimated reading time, estimated pages and manuscript pages, unique vocabulary, averages per chapter, paragraph and sentence, H1/H2/H3 headings, empty chapters, images, links, lists, quotes, chapter distribution, longest and shortest chapter, and recurring vocabulary. You can also export statistics as PDF.</p></article><article class=\"card\"><h3>Screenplay</h3><p>In the screenplay editor, open the statistics button. The panel shows words, characters, scenes, locations, characters, total dialogue time, time per character, longest lines, character entries, location usage, dialogue/action balance, scene rhythm, and narrative distribution.</p></article></div><p>Use these numbers as editorial guidance: they help identify chapters that are too short, dense scenes, excessive dialogue, dominant characters, or text areas that need structural revision.</p></section>",
      "importacao": "<section id=\"importacao\"><h2>Import</h2><p>Gutenberg can bring external content into existing projects.</p><div class=\"table-wrap\"><table><thead><tr><th>File</th><th>In books</th><th>In screenplays</th></tr></thead><tbody><tr><td><code>.gut</code></td><td>Imports saved chapters from another book project.</td><td>Imports a saved script from another screenplay project.</td></tr><tr><td><code>.docx</code></td><td>Converts the document into a chapter or chapters.</td><td>Converts the document into a structured script.</td></tr><tr><td><code>.pdf</code></td><td>Extracts text and tries to organize it as a chapter.</td><td>Extracts text and tries to organize it as a script.</td></tr><tr><td><code>.txt</code></td><td>Imports plain text as book content.</td><td>Imports plain text as screenplay content.</td></tr><tr><td><code>.gutr</code></td><td colspan=\"2\">Imports project resources only: information, flow, characters, places, and notes.</td></tr></tbody></table></div><div class=\"callout info\"><strong>Note:</strong> DOCX and TXT usually import more predictably. PDFs can vary depending on the structure of the original file.</div></section>",
      "gut-gutr": "<section id=\"gut-gutr\"><h2>.gut and .gutr files</h2><p>Gutenberg uses two custom formats for backup and transfer.</p><div class=\"card-grid two\"><article class=\"card\"><h3><code>.gut</code></h3><p>Saves main content: book chapters or a selected script. Use it to move text between compatible projects or keep snapshots of your work.</p></article><article class=\"card\"><h3><code>.gutr</code></h3><p>Saves project resources: information pages, flowchart, characters, places, and notes. Use it to reuse a project outline or transfer planning material.</p></article></div><h3>Pending import on desktop</h3><p>In desktop mode, a <code>.gut</code> file opened by the operating system can appear as a pending import. The home screen lets you choose a compatible project or create a new project for the content.</p></section>",
      "exportacao": "<section id=\"exportacao\"><h2>Export</h2><p>Export uses the folder configured in <strong>Settings</strong>. After exporting, the app delivers the generated file or reports the created folder.</p><div class=\"table-wrap\"><table><thead><tr><th>Project type</th><th>Formats</th><th>Recommended use</th></tr></thead><tbody><tr><td>Book</td><td>EPUB 2.0, EPUB 3.0</td><td>Distribution for e-readers and ebook flow validation.</td></tr><tr><td>Book</td><td>XHTML</td><td>Simple HTML-page output for inspection or intermediate use.</td></tr><tr><td>Book</td><td>DOCX</td><td>Revision in a word processor.</td></tr><tr><td>Book</td><td>PDF</td><td>Reading, sharing, and visual proofing.</td></tr><tr><td>Screenplay</td><td>DOCX, PDF</td><td>Export as script, outline, statistics, or complete document.</td></tr></tbody></table></div><p>For best results, review content before export and check headings, images, empty chapters, and project metadata.</p></section>",
      "biblioteca": "<section id=\"biblioteca\"><h2>Library</h2><p>The Library is separate from writing projects. It is used to import and read <strong>EPUB</strong> and <strong>PDF</strong> files with progress tracking.</p><div class=\"table-wrap\"><table><thead><tr><th>Control</th><th>Purpose</th></tr></thead><tbody><tr><td>Add book</td><td>Imports one or more EPUB/PDF files.</td></tr><tr><td>Search</td><td>Filters books by title, author, language, or original file.</td></tr><tr><td>Reading / All / Read</td><td>Filters the library by reading state.</td></tr><tr><td>Collections</td><td>Shows automatic groups by detected collection/key.</td></tr><tr><td>✓</td><td>Marks or unmarks a book as read.</td></tr><tr><td>Trash</td><td>Removes the book from the local library.</td></tr></tbody></table></div><p>Each cover displays the progress percentage. When you open a book, Gutenberg tries to return to the last chapter or position you read.</p></section>",
      "leitor-biblioteca": "<section id=\"leitor-biblioteca\"><h2>EPUB/PDF reader</h2><p>The library reader uses a view adapted for imported books. PDFs are converted for internal reading, and EPUBs are displayed by chapter.</p><div class=\"card-grid two\"><article class=\"card\"><h3>Summary</h3><p>Opens the book chapter tree. In EPUBs with levels, indentation indicates hierarchy.</p></article><article class=\"card\"><h3>Progress</h3><p>Saves reading position and percentage for the book.</p></article><article class=\"card\"><h3>Visual preferences</h3><p>Use mode, font, and size to adjust reading. Preferences are global for the readers.</p></article><article class=\"card\"><h3>Navigation</h3><p>Use previous/next chapter buttons or keyboard shortcuts.</p></article></div><p>The EPUB/PDF reader uses the same theme family as the chapter reader: light, dark, sepia, and other comfort modes.</p></section>",
      "configuracoes": "<section id=\"configuracoes\"><h2>Settings</h2><p>The settings screen controls reading appearance, folders, revision, language, and application behavior.</p><div class=\"table-wrap\"><table><thead><tr><th>Setting</th><th>What it changes</th></tr></thead><tbody><tr><td>Default indent and increased indent</td><td>Defines normal and larger indentation used in reading and export.</td></tr><tr><td>Paragraph and line spacing</td><td>Adjusts reading comfort and visual preview.</td></tr><tr><td>Base font size</td><td>Defines the main text scale.</td></tr><tr><td>H1, H2, H3</td><td>Controls heading sizes.</td></tr><tr><td>Reading width</td><td>Defines the maximum text area width.</td></tr><tr><td>App language</td><td>Switches the interface between Português (Brasil) and English (US).</td></tr><tr><td>Documentation</td><td>Opens this documentation.</td></tr><tr><td>Check for updates</td><td>Checks GitHub Releases for <code>no-strand/gutenberg</code>, compares the installed version with the latest release, and, when a compatible package for the operating system is attached, lets you start the update.</td></tr><tr><td>Export folder</td><td>Location where exported files are saved.</td></tr><tr><td>Library folder</td><td>Location where imported EPUB/PDF files are organized.</td></tr><tr><td>Gemini key</td><td>Enables Gemini revision.</td></tr><tr><td>Browser mode</td><td>Runs Gutenberg as a local server accessible from the browser; it is the automatic fallback when desktop/pywebview cannot be used and when pystray fails.</td></tr><tr><td>Editor effect</td><td>Enables or disables the particle visual effect on editing pages.</td></tr></tbody></table></div><p>The preview at the end of the screen shows how reading options affect headings, paragraphs, indents, and spacing.</p></section>",
      "atualizacoes": "<section id=\"atualizacoes\"><h2>Updates</h2><p>Gutenberg can check whether a newer version of the app is available to install.</p><p>In <strong>Settings</strong>, use <strong>Check for updates</strong> to check manually. A window will show whether the program is already up to date or whether a new version is available.</p><p>Gutenberg can also check automatically from the home screen, at most once per week. When the check is completed, a small notice appears in the corner of the screen with the result. If an update is available, the notice includes an <strong>Update now</strong> button to start the process.</p><p>If the app cannot check at that moment, for example because there is no connection, it simply skips the attempt and keeps opening normally without interrupting your work.</p></section>",
      "atalhos": "<section id=\"atalhos\"><h2>Shortcuts</h2><h3>Book editor</h3><div class=\"table-wrap\"><table><thead><tr><th>Action</th><th>Shortcut</th></tr></thead><tbody><tr><td>Undo / redo</td><td>Ctrl+Z / Ctrl+Y or Ctrl+Shift+Z</td></tr><tr><td>Align left, center, right, justify</td><td>Alt+E, Alt+C, Alt+D, Alt+J</td></tr><tr><td>Bold, italic, underline</td><td>Alt+B, Alt+I, Alt+U</td></tr><tr><td>Paragraph, H1, H2, H3, list</td><td>Alt+P, Alt+1, Alt+2, Alt+3, Alt+L</td></tr><tr><td>Horizontal rule</td><td>Alt+R</td></tr><tr><td>Decorative wrapper</td><td>Alt+Q</td></tr><tr><td>Decorative separator</td><td>Ctrl+Alt+Q</td></tr><tr><td>Indent left/right</td><td>Ctrl+Alt+E / Ctrl+Alt+D</td></tr><tr><td>Sans, serif, monospaced font</td><td>Ctrl+Alt+X, Ctrl+Alt+S, Ctrl+Alt+M</td></tr><tr><td>Insert image</td><td>Ctrl+Alt+I</td></tr><tr><td>Clear editing</td><td>Ctrl+Alt+L</td></tr><tr><td>Review</td><td>Ctrl+Alt+R</td></tr></tbody></table></div><h3>Screenplay editor</h3><div class=\"table-wrap\"><table><thead><tr><th>Action</th><th>Shortcut</th></tr></thead><tbody><tr><td>Undo / redo</td><td>Ctrl+Z / Ctrl+Shift+Z</td></tr><tr><td>Select script blocks</td><td>Ctrl+A inside the editor</td></tr><tr><td>Go to first/last scene</td><td>Alt+1 / Alt+0</td></tr><tr><td>Hide or show comments</td><td>Alt+O</td></tr><tr><td>Scene, action, character, dialogue</td><td>Alt+C, Alt+A, Alt+P, Alt+D</td></tr><tr><td>Parenthetical, shot, transition</td><td>Alt+S, Alt+L, Alt+T</td></tr><tr><td>Comment, music, neutral</td><td>Alt+N, Alt+M, Alt+E</td></tr><tr><td>Character/location catalog</td><td>Ctrl+Alt+P / Ctrl+Alt+L</td></tr><tr><td>Statistics</td><td>Ctrl+Alt+I</td></tr><tr><td>Revision</td><td>Ctrl+Alt+R</td></tr></tbody></table></div><h3>Readers</h3><p>Use <strong>←</strong> or <strong>&lt;</strong> for the previous chapter, <strong>→</strong> or <strong>&gt;</strong> for the next one, <strong>↑</strong> and <strong>↓</strong> to scroll, <strong>S</strong> to open the summary, and <strong>Esc</strong> to close the summary or go back.</p></section>",
      "armazenamento": "<section id=\"armazenamento\"><h2>Storage and backup</h2><p>Gutenberg stores data locally. Paths can vary by system and settings, but the project works with three main groups.</p><ul class=\"clean-list\"><li><strong>Projects:</strong> books and screenplays created by the user.</li><li><strong>Exports:</strong> files generated as EPUB, XHTML, DOCX, PDF, <code>.gut</code>, or <code>.gutr</code>.</li><li><strong>Library:</strong> imported EPUB/PDF files, covers, extracted files, and progress.</li></ul><h3>How to back up</h3><ol class=\"steps compact\"><li>Copy the local folder where your projects are stored.</li><li>Export <code>.gut</code> files for important chapters or scripts.</li><li>Export <code>.gutr</code> files for important project resources.</li><li>Keep exported files outside the main folder, such as on an external drive or cloud service.</li></ol><div class=\"callout warn\"><strong>Important:</strong> deleting a project or book removes local data. Keep a backup before cleaning your library or old projects.</div></section>"
    }
  }
};

const menuToggle = document.getElementById("menuToggle");
const sidebar = document.getElementById("sidebar");
const searchInput = document.getElementById("searchInput");
const menuNav = document.getElementById("menuNav");
const sectionsContainer = document.getElementById("sectionsContainer");
const langPt = document.getElementById("langPt");
const langEn = document.getElementById("langEn");
const hero = document.querySelector(".hero");
const footer = document.querySelector(".footer");
const LOCALE_KEY = "gutenberg-doc-locale";
const LOCALE_INIT_KEY = "gutenberg-doc-locale-initialized-v2";

/** Getinitiallocale. Usada pelo fluxo principal da aplicação. */
function getInitialLocale() {
  const savedLocale = localStorage.getItem(LOCALE_KEY);
  const wasInitialized = localStorage.getItem(LOCALE_INIT_KEY);

  if (!wasInitialized) {
    localStorage.setItem(LOCALE_KEY, "en-US");
    localStorage.setItem(LOCALE_INIT_KEY, "1");
    return "en-US";
  }

  return savedLocale === "pt-BR" || savedLocale === "en-US" ? savedLocale : "en-US";
}

let currentLocale = getInitialLocale();
let observer = null;

/** Setlocale. Usada pelo fluxo principal da aplicação. */
function setLocale(locale) {
  if (locale === currentLocale) return;
  currentLocale = locale;
  localStorage.setItem("gutenberg-doc-locale", locale);
  document.body.classList.add("locale-switching");
  window.setTimeout(() => {
    ensureContentShells();
renderLocale();
    window.requestAnimationFrame(() => {
      window.setTimeout(() => document.body.classList.remove("locale-switching"), 60);
    });
  }, 180);
}

/** Ensurecontentshells. Usada pelo fluxo principal da aplicação. */
function ensureContentShells() {
  [hero, sectionsContainer, footer].forEach((element) => {
    if (element) element.classList.add("content-shell");
  });
}

/** Renderlocale. Usada pelo fluxo principal da aplicação. */
function renderLocale() {
  const t = translations[currentLocale];
  document.documentElement.lang = currentLocale;
  document.title = t.meta.title;
  document.getElementById("brandSubtitle").textContent = t.meta.brandSubtitle;
  searchInput.placeholder = t.meta.searchPlaceholder;
  document.getElementById("heroEyebrow").textContent = t.meta.heroEyebrow;
  document.getElementById("heroTitle").textContent = t.meta.heroTitle;
  document.getElementById("heroDescription").innerHTML = t.meta.heroDescription;
  document.getElementById("footerText").textContent = t.meta.footerText;
  menuToggle.setAttribute("aria-label", t.meta.menuLabel);
  langPt.classList.toggle("active", currentLocale === "pt-BR");
  langEn.classList.toggle("active", currentLocale === "en-US");
  document.querySelector(".lang-switch").classList.toggle("is-en", currentLocale === "en-US");
  menuNav.innerHTML = t.nav.map(([id, label]) => `<a href="#${id}">${label}</a>`).join("");
  sectionsContainer.innerHTML = t.nav.map(([id]) => t.sections[id]).join("");
  bindNavigation();
  setupObserver();
  applySearch();
}

/** Bindnavigation. Usada pelo fluxo principal da aplicação. */
function bindNavigation() {
  const navLinks = [...document.querySelectorAll("#menuNav a")];
  navLinks.forEach(link => {
    link.addEventListener("click", () => {
      if (window.innerWidth <= 1024) sidebar.classList.remove("open");
    });
  });
}

/** Setupobserver. Usada pelo fluxo principal da aplicação. */
function setupObserver() {
  const sections = [...document.querySelectorAll("main section")];
  const navLinks = [...document.querySelectorAll("#menuNav a")];
  if (observer) observer.disconnect();
  observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const id = entry.target.id;
      navLinks.forEach(link => {
        link.classList.toggle("active", link.getAttribute("href") === `#${id}`);
      });
    });
  }, { rootMargin: "-25% 0px -60% 0px", threshold: 0.1 });
  sections.forEach(section => observer.observe(section));
}

/** Clearsearchstate. Usada pelo fluxo principal da aplicação. */
function clearSearchState() {
  const sections = [...document.querySelectorAll("main section")];
  sections.forEach(section => {
    section.classList.remove("hidden-by-search");
    section.classList.remove("highlight");
  });
}

/** Applysearch. Usada pelo fluxo principal da aplicação. */
function applySearch() {
  const term = searchInput.value.trim().toLowerCase();
  const sections = [...document.querySelectorAll("main section")];
  clearSearchState();
  if (!term) return;
  sections.forEach(section => {
    const text = section.innerText.toLowerCase();
    const match = text.includes(term);
    section.classList.toggle("hidden-by-search", !match);
    section.classList.toggle("highlight", match);
  });
}

menuToggle.addEventListener("click", () => sidebar.classList.toggle("open"));
searchInput.addEventListener("input", applySearch);
langPt.addEventListener("click", () => setLocale("pt-BR"));
langEn.addEventListener("click", () => setLocale("en-US"));

document.addEventListener("click", (event) => {
  if (window.innerWidth > 1024) return;
  if (!sidebar.classList.contains("open")) return;
  const clickedInsideSidebar = sidebar.contains(event.target);
  const clickedToggle = menuToggle.contains(event.target);
  if (!clickedInsideSidebar && !clickedToggle) sidebar.classList.remove("open");
});

ensureContentShells();
renderLocale();
