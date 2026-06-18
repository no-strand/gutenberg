# Gutenberg ✍️📚

**Gutenberg** é um aplicativo local para escrita literária, criação de roteiros, organização de materiais de apoio, revisão, exportação e leitura de EPUB/PDF. Ele usa **Python + Flask + HTML/CSS/JavaScript** e pode ser executado como aplicativo desktop com **pywebview** ou como servidor local no navegador. O modo desktop com **pywebview** exige **Windows 10+**; em versões anteriores do Windows ou em outros sistemas operacionais, o Gutenberg tenta executar em **modo browser** e, se o **pystray** não puder ser usado, cai automaticamente para o **modo servidor** sem ícone de bandeja.

**Gutenberg** is a local app for literary writing, screenplay creation, planning material, revision, export, and EPUB/PDF reading. It uses **Python + Flask + HTML/CSS/JavaScript** and can run as a **pywebview** desktop app or as a local browser server. The **pywebview** desktop mode requires **Windows 10+**; on older Windows versions or other operating systems, Gutenberg tries to run in **browser mode** and, if **pystray** cannot be used, automatically falls back to **server mode** without a tray icon.

---

## Sumário dos idiomas / Language index

- [Português (Brasil)](#português-brasil)
- [English (US)](#english-us)

---

# Português (Brasil)

## Sumário

- [O que é o Gutenberg](#o-que-é-o-gutenberg)
- [Sumário de funcionalidades](#sumário-de-funcionalidades)
- [Fluxos principais](#fluxos-principais)
- [Importação, exportação e arquivos próprios](#importação-exportação-e-arquivos-próprios)
- [Execução em desenvolvimento](#execução-em-desenvolvimento)
- [Testes](#testes)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Armazenamento local](#armazenamento-local)
- [Documentação integrada](#documentação-integrada)
- [Assets principais](#assets-principais)

## O que é o Gutenberg

O Gutenberg reúne, em uma interface local, o fluxo de criação de **livros**, **roteiros**, **recursos de planejamento**, **revisão com Gemini**, **exportação de documentos** e **biblioteca de leitura**. Os dados são salvos no computador do usuário, e as pastas de projetos, exportações e biblioteca podem ser configuradas na tela **Configurações**.

O aplicativo tem interface em **Português (Brasil)** e **English (US)**, documentação visual integrada e modos de execução para desktop ou navegador local. O desktop via **pywebview** depende de **Windows 10 ou superior**; fora desse requisito, a execução padrão tenta o **modo browser** e usa o **modo servidor** como fallback quando o **pystray** falha ou não está disponível.

## Sumário de funcionalidades

- [Projetos](#projetos)
- [Editor de livro](#editor-de-livro)
- [Leitor de capítulos](#leitor-de-capítulos)
- [Projetos e editor de roteiro](#projetos-e-editor-de-roteiro)
- [Catálogos](#catálogos)
- [Recursos do projeto](#recursos-do-projeto)
- [Revisão com Gemini](#revisão-com-gemini)
- [Estatísticas](#estatísticas)
- [Biblioteca EPUB/PDF](#biblioteca-epubpdf)
- [Configurações e idiomas](#configurações-e-idiomas)

### Projetos

| Funcionalidade | Descrição |
|---|---|
| **Livro** | Criação de projetos organizados por capítulos, com título, descrição, autor, idioma, tags e capa opcional. |
| **Roteiro** | Criação de projetos com um ou mais roteiros, metadados de produção, contato, tipo de roteiro, logline, sinopse e gênero. |
| **Tela inicial** | Lista projetos em grade ou modo explorer, abre projetos, cria novos itens, remove projetos e mostra informações de atualização. |
| **Metadados** | Permite editar título, descrição, autor, idioma, tags, contato e informações específicas de cada tipo de projeto. |
| **Capa de livro** | Projetos de livro podem receber e trocar imagem de capa. |

### Editor de livro

| Funcionalidade | Descrição |
|---|---|
| **Capítulos** | Criação, edição, leitura, importação e exclusão de capítulos. |
| **Salvamento automático** | O editor salva alterações durante a escrita e mostra o estado de salvamento na barra superior. |
| **Formatação rica** | Alinhamento, recuo, negrito, itálico, sublinhado, fonte serifada/sem serifa/monoespaçada, títulos H1/H2/H3, listas e linha horizontal. |
| **Elementos decorativos** | Inserção de separadores e delimitadores para trechos selecionados. |
| **Imagens** | Inserção de imagens no conteúdo do capítulo. |
| **Recursos no editor** | Abre um modal para consultar personagens, lugares e anotações do projeto sem sair do texto. |
| **Revisão** | Envia trechos para revisão ortográfica e gramatical quando a chave Gemini está configurada. |

### Leitor de capítulos

| Funcionalidade | Descrição |
|---|---|
| **Modo leitura** | Mostra capítulos em uma página de leitura com foco no conforto visual. |
| **Sumário** | Abre a lista de capítulos do projeto. |
| **Progresso** | Registra o último capítulo aberto e a posição de leitura. |
| **Preferências visuais** | Ajuste de modo, fonte e tamanho de fonte diretamente no leitor. |
| **Navegação** | Botões e atalhos para capítulo anterior, próximo capítulo, rolagem e retorno. |

### Projetos e editor de roteiro

| Funcionalidade | Descrição |
|---|---|
| **Múltiplos roteiros** | Um projeto de roteiro pode conter vários roteiros independentes. |
| **Blocos especializados** | Cena, ação, personagem, diálogo, rubrica, plano, transição, comentário, música e neutro. |
| **Numeração de cenas** | Cabeçalhos de cena usam prefixo e numeração inicial definidos nas informações do roteiro. |
| **Sugestão de próximo bloco** | O editor cria o próximo bloco com base no fluxo comum de escrita de roteiro. |
| **Comentários** | Blocos de comentário podem ser ocultados ou exibidos. |
| **Atalhos** | Atalhos para tipos de bloco, navegação entre cenas, estatísticas, revisão e catálogos. |
| **Exportação de roteiro** | Exporta PDF ou DOCX nos modos roteiro, outline, estatística ou documento completo. |

### Catálogos

| Funcionalidade | Descrição |
|---|---|
| **Personagens** | Cadastro de nomes, descrições e imagens de referência. No roteiro, os nomes podem ser sugeridos em blocos de personagem. |
| **Lugares** | Cadastro de locais, cenários e ambientes importantes do projeto. |
| **Anotações** | Registro de ideias, objetos, pistas, regras de mundo, lembretes e observações. |
| **Consulta nos editores** | Personagens, lugares e anotações podem ser consultados pelo modal de Recursos durante a escrita. |

### Recursos do projeto

O **Painel Recursos do projeto** concentra o esboço, o fluxo e os catálogos usados como apoio durante a escrita.

| Aba | O que faz |
|---|---|
| **Informações** | Páginas livres com editor rico para sinopse, esboço, pesquisa, regras de mundo, imagens e notas de produção. |
| **Fluxo** | Fluxograma com balões arrastáveis e conexões para organizar arcos, cenas, relações, linhas temporais ou etapas de trabalho. |
| **Personagens** | Cadastro central de personagens com descrição e imagem de referência. |
| **Lugares** | Cadastro central de locais com descrição e imagem de referência. |
| **Anotações** | Cadastro de notas textuais reutilizáveis durante a escrita. |
| **Salvar recursos** | Gera um arquivo `.gutr` com informações, fluxo, personagens, lugares e anotações. |
| **Importar recursos** | Adiciona o conteúdo de um `.gutr` ao projeto atual sem substituir capítulos ou roteiros. |

### Revisão com Gemini

A revisão automática usa a chave da API Gemini configurada em **Configurações**. Ela pode ser acionada no editor de livro e no editor de roteiro para revisar o trecho atual, mantendo o usuário no controle da aceitação ou descarte das sugestões.

### Estatísticas

| Área | Estatísticas disponíveis |
|---|---|
| **Livro** | Cálculos para capítulos e projeto EPUB, com exportação de estatísticas em PDF. |
| **Roteiro** | Contagem de cenas, blocos, personagens, diálogos, tempo estimado de fala e informações úteis para análise do roteiro. |

### Biblioteca EPUB/PDF

| Funcionalidade | Descrição |
|---|---|
| **Adicionar livro** | Importa arquivos EPUB ou PDF para a biblioteca local. |
| **Leitura integrada** | EPUBs são lidos por capítulos; PDFs são convertidos para visualização interna. |
| **Progresso** | Registra último item lido, posição e porcentagem. |
| **Filtros** | Busca por título, autor, idioma ou arquivo original; filtros por leitura, todos e lidos. |
| **Coleções** | Agrupamento automático por informações detectadas nos livros. |
| **Marcar como lido** | Permite alternar o estado de leitura de cada item. |
| **Preferências visuais** | Leitor com modo, fonte, tamanho de fonte, sumário e navegação. |

### Configurações e idiomas

| Configuração | Descrição |
|---|---|
| **Aparência de leitura** | Recuo, espaçamento entre parágrafos, espaçamento de linhas, tamanho base, tamanhos de H1/H2/H3 e largura de leitura. |
| **Pastas** | Define pasta de exportação e pasta da biblioteca. |
| **Gemini** | Salva a chave usada para revisão automática. |
| **Idioma da interface** | Alterna entre Português (Brasil) e English (US). |
| **Modo browser/servidor** | Executa o Gutenberg como servidor local acessível pelo navegador; é o fallback automático quando o desktop/pywebview não pode ser usado e também quando o pystray falha. |
| **Efeito do editor** | Ativa ou desativa o efeito visual de partículas nas páginas de edição. |
| **Documentação e créditos** | Abre a documentação integrada e a tela de créditos. |

## Fluxos principais

### Criar um livro

1. Na tela inicial, clique em **Novo projeto**.
2. Escolha **Livro**.
3. Preencha título, descrição, autor, idioma, tags e capa opcional.
4. Abra o projeto e crie capítulos com **Novo capítulo**.
5. Escreva no editor, revise quando necessário e confira no **Modo leitura**.
6. Exporte o projeto em EPUB, XHTML, DOCX ou PDF, ou salve capítulos em `.gut`.

### Criar um roteiro

1. Na tela inicial, clique em **Novo projeto**.
2. Escolha **Roteiro**.
3. Preencha título, descrição, autor, idioma, contato e informações adicionais.
4. Abra o projeto e crie um roteiro.
5. Configure título, cabeçalho, rodapé, prefixo de cena, numeração inicial, logline, sinopse, gênero e tipo de roteiro.
6. Escreva usando blocos de roteiro e consulte estatísticas quando precisar.
7. Exporte em PDF ou DOCX como roteiro, outline, estatística ou documento completo, ou salve o roteiro em `.gut`.

### Usar Recursos do projeto

1. Abra um projeto e clique em **Recursos**.
2. Use **Informações** para páginas de esboço, sinopse, pesquisa e notas.
3. Use **Fluxo** para criar balões, organizar conexões e mapear relações.
4. Cadastre personagens, lugares e anotações nas abas correspondentes.
5. Use **Salvar recursos** para gerar `.gutr` ou **Importar recursos** para adicionar recursos de outro arquivo.
6. Dentro dos editores, use o botão **Recursos** ou o atalho **Ctrl + Alt + U** para consultar o modal sem sair do texto.

### Usar a Biblioteca

1. Abra **Biblioteca** pela tela inicial.
2. Clique em **Adicionar livro** e selecione arquivos EPUB ou PDF.
3. Abra o livro importado para ler.
4. Use modo, fonte, tamanho, sumário e navegação conforme sua preferência.
5. O progresso é salvo automaticamente.

## Importação, exportação e arquivos próprios

| Formato | Uso |
|---|---|
| `.gut` | Salva conteúdo principal: capítulos de livro ou roteiro selecionado. Pode ser importado em projetos compatíveis. |
| `.gutr` | Salva recursos do projeto: informações, fluxo, personagens, lugares e anotações. |
| `.docx` | Pode ser importado como capítulo ou roteiro e também usado como exportação. |
| `.pdf` | Pode ser importado como capítulo ou roteiro, exportado pelo projeto e adicionado à biblioteca. |
| `.txt` | Pode ser importado como capítulo ou roteiro. |
| `.epub` | Exportação de livros nas versões EPUB 2.0 e EPUB 3.0; também pode ser importado para a biblioteca. |
| `.xhtml` | Exportação simples de livros em XHTML. |

No modo desktop, arquivos `.gut` podem aparecer como importação pendente na tela inicial. O usuário pode escolher um projeto compatível ou criar um novo projeto para receber o conteúdo.

## Execução em desenvolvimento

### Requisitos

- Python 3.11+ recomendado.
- Windows 10+ obrigatório para o modo desktop com pywebview, tray e instalador; em versões anteriores ou em outros sistemas operacionais, o Gutenberg tenta o modo browser. Se o pystray falhar ou não estiver disponível, o aplicativo inicia automaticamente em modo servidor sem tray, equivalente a `python server_only.py`.
- Inno Setup 6 para gerar o instalador Windows.
- Dependências listadas em `requirements.txt`.

Instale as dependências:

```bash
pip install -r requirements.txt
```

### Modo browser/servidor

O modo browser executa o Gutenberg como servidor local e permite acessar a interface pelo navegador em `http://127.0.0.1:5000`. Ele é usado automaticamente quando o modo desktop com pywebview não pode ser iniciado, incluindo Windows abaixo da versão 10, ausência do pywebview ou sistemas operacionais diferentes do Windows. Se o pystray falhar durante essa inicialização, o Gutenberg abandona o tray e mantém a execução em modo servidor sem ícone de bandeja, no mesmo fluxo do `server_only.py`.

```bash
python server_only.py
```

Depois acesse:

```text
http://127.0.0.1:5000
```

### Modo desktop

O modo desktop usa pywebview e requer Windows 10 ou superior. Se esse requisito não for atendido, `python app.py` tenta iniciar o Gutenberg em modo browser; se o pystray não puder ser usado, o fallback automático é o modo servidor sem tray.

```bash
python app.py
```

## Testes

O projeto usa `unittest`.

```bash
python tests/run_tests.py
```

Também é possível executar:

```bash
python -m unittest discover -s tests -v
```

A suíte cobre unidades de backend, rotas Flask, biblioteca EPUB/PDF, progresso de leitura, coleções, importação DOCX/PDF/TXT, exportações, arquivos `.gut`, arquivos `.gutr`, recursos do projeto e fluxos de importação pendente.

## Estrutura do projeto

```text
Gutenberg/
├── app.py                       # Inicialização desktop com pywebview
├── server_only.py               # Execução Flask/browser
├── modules/                     # Backend: projetos, biblioteca, importação, exportação, i18n e persistência
├── templates/                   # Templates HTML Flask
├── static/                      # CSS, JavaScript, ícones e imagens da interface
├── locales/                     # Traduções pt_BR e en_US
├── documentation/               # Documentação HTML integrada
├── tests/                       # Testes automatizados unittest
├── installer.ico                # Ícone do instalador
├── Gutenberg.spec               # Configuração PyInstaller
├── Gutenberg.iss                # Script do Inno Setup
├── version.txt                  # Metadados de versão
├── requirements.txt             # Dependências Python
└── README.md
```

## Armazenamento local

Por padrão, o aplicativo usa pastas locais para configurações, projetos, exportações e biblioteca. Os caminhos podem variar conforme o sistema e as opções salvas na tela **Configurações**.

- Configurações: pasta de dados do usuário do sistema.
- Projetos: pasta Gutenberg dentro de Documentos, salvo alteração de configuração.
- Exportações: pasta configurada pelo usuário.
- Biblioteca: pasta configurada pelo usuário, com arquivos importados, capas, dados extraídos e progresso.
- Logs de erro: `Documentos/gutenberg/errors.log`, com rotação automática.

## Documentação integrada

A documentação visual fica em:

```text
documentation/index.html
```

Ela também pode ser aberta pela tela **Configurações**. No desktop, abre no navegador padrão; no modo browser, é servida pela própria aplicação.

## Assets principais

| Uso | Arquivo |
|---|---|
| Favicon HTML | `static/img/favicon.ico` |
| Ícone do executável | `static/img/icon.ico` |
| Ícone da bandeja | `static/img/favicon.ico` |
| Ícone do instalador | `installer.ico` |
| Ícone de arquivos `.gut` e `.gutr` | `static/img/gut_file.ico` |

---

# English (US)

## Table of contents

- [What Gutenberg is](#what-gutenberg-is)
- [Feature summary](#feature-summary)
- [Main workflows](#main-workflows)
- [Import, export, and custom files](#import-export-and-custom-files)
- [Development run](#development-run)
- [Tests](#tests)
- [Project structure](#project-structure)
- [Local storage](#local-storage)
- [Integrated documentation](#integrated-documentation)
- [Main assets](#main-assets)

## What Gutenberg is

Gutenberg brings together **book writing**, **screenplay writing**, **project planning resources**, **Gemini revision**, **document export**, and an **EPUB/PDF reading library** in a local interface. User data is stored on the computer, and the project, export, and library folders can be adjusted on the **Settings** screen.

The app supports **Português (Brasil)** and **English (US)**, includes integrated visual documentation, and can run as a desktop app or as a local browser app. Desktop execution through **pywebview** depends on **Windows 10 or later**; outside that requirement, the default execution tries **browser mode** and uses **server mode** as a fallback when **pystray** fails or is unavailable.

## Feature summary

- [Projects](#projects)
- [Book editor](#book-editor)
- [Chapter reader](#chapter-reader)
- [Screenplay projects and editor](#screenplay-projects-and-editor)
- [Catalogs](#catalogs)
- [Project resources](#project-resources)
- [Gemini revision](#gemini-revision)
- [Statistics](#statistics)
- [EPUB/PDF library](#epubpdf-library)
- [Settings and languages](#settings-and-languages)

### Projects

| Feature | Description |
|---|---|
| **Book** | Creates chapter-based projects with title, description, author, language, tags, and optional cover. |
| **Screenplay** | Creates projects with one or more scripts, production metadata, contact, script type, logline, synopsis, and genre. |
| **Home screen** | Shows projects as cards or in explorer mode, opens projects, creates new items, deletes projects, and displays update information. |
| **Metadata** | Edits title, description, author, language, tags, contact, and type-specific project fields. |
| **Book cover** | Book projects can receive and change a cover image. |

### Book editor

| Feature | Description |
|---|---|
| **Chapters** | Create, edit, read, import, and delete chapters. |
| **Autosave** | Saves changes while writing and shows the save state in the top bar. |
| **Rich formatting** | Alignment, indentation, bold, italic, underline, serif/sans/monospaced font, H1/H2/H3 headings, lists, and horizontal rule. |
| **Decorative elements** | Inserts separators and wrappers around selected passages. |
| **Images** | Inserts images into chapter content. |
| **Resources in the editor** | Opens a modal to consult project characters, places, and notes without leaving the text. |
| **Revision** | Sends passages for spelling and grammar revision when the Gemini key is configured. |

### Chapter reader

| Feature | Description |
|---|---|
| **Reading mode** | Displays chapters in a focused reading page. |
| **Summary** | Opens the project chapter list. |
| **Progress** | Stores the last opened chapter and reading position. |
| **Visual preferences** | Adjust mode, font, and font size directly in the reader. |
| **Navigation** | Buttons and shortcuts for previous chapter, next chapter, scrolling, and return. |

### Screenplay projects and editor

| Feature | Description |
|---|---|
| **Multiple scripts** | A screenplay project can contain multiple independent scripts. |
| **Specialized blocks** | Scene, action, character, dialogue, parenthetical, shot, transition, comment, music, and neutral. |
| **Scene numbering** | Scene headings use the prefix and initial number defined in the script information. |
| **Next block suggestion** | The editor creates the next block according to the usual screenplay writing flow. |
| **Comments** | Comment blocks can be hidden or shown. |
| **Shortcuts** | Shortcuts for block types, scene navigation, statistics, revision, and catalogs. |
| **Screenplay export** | Exports PDF or DOCX as script, outline, statistics, or complete document. |

### Catalogs

| Feature | Description |
|---|---|
| **Characters** | Register names, descriptions, and reference images. In screenplays, names can be suggested in character blocks. |
| **Places** | Register important project locations, settings, and environments. |
| **Notes** | Store ideas, objects, clues, world rules, reminders, and observations. |
| **Editor access** | Characters, places, and notes can be consulted through the Resources modal while writing. |

### Project resources

| Tab | Purpose |
|---|---|
| **Information** | Free pages with a rich editor for synopsis, outline, research, world rules, images, and production notes. |
| **Flow** | Flowchart with draggable balloons and connections to organize arcs, scenes, relationships, timelines, or workflow steps. |
| **Characters** | Central character catalog with description and reference image. |
| **Places** | Central location catalog with description and reference image. |
| **Notes** | Text notes that can be reused while writing. |
| **Save resources** | Generates a `.gutr` file with information, flow, characters, places, and notes. |
| **Import resources** | Adds the contents of a `.gutr` file to the current project without replacing chapters or scripts. |

### Gemini revision

Automatic revision uses the Gemini API key configured in **Settings**. It can be triggered in the book editor and screenplay editor to revise the current passage while keeping the user in control of accepting or discarding suggestions.

### Statistics

| Area | Available statistics |
|---|---|
| **Book** | Chapter and EPUB project calculations, with PDF export for statistics. |
| **Screenplay** | Scene count, block count, characters, dialogue, estimated speech time, and useful script analysis information. |

### EPUB/PDF library

| Feature | Description |
|---|---|
| **Add book** | Imports EPUB or PDF files into the local library. |
| **Integrated reading** | EPUBs are read by chapter; PDFs are converted for internal viewing. |
| **Progress** | Stores the last item read, position, and percentage. |
| **Filters** | Search by title, author, language, or original file; filters for reading, all, and read. |
| **Collections** | Automatic grouping based on detected book information. |
| **Mark as read** | Toggles the reading state of each item. |
| **Visual preferences** | Reader with mode, font, font size, summary, and navigation. |

### Settings and languages

| Setting | Description |
|---|---|
| **Reading appearance** | Indentation, paragraph spacing, line spacing, base size, H1/H2/H3 sizes, and reading width. |
| **Folders** | Defines export folder and library folder. |
| **Gemini** | Stores the key used for automatic revision. |
| **Interface language** | Switches between Português (Brasil) and English (US). |
| **Browser/server mode** | Runs Gutenberg as a local server accessible from the browser; it is the automatic fallback when desktop/pywebview cannot be used and also when pystray fails. |
| **Editor effect** | Enables or disables the particle visual effect on editing pages. |
| **Documentation and credits** | Opens the integrated documentation and credits page. |

## Main workflows

### Create a book

1. On the home screen, click **New project**.
2. Choose **Book**.
3. Fill in title, description, author, language, tags, and optional cover.
4. Open the project and create chapters with **New chapter**.
5. Write in the editor, revise when needed, and check the result in **Reading mode**.
6. Export the project as EPUB, XHTML, DOCX, or PDF, or save chapters as `.gut`.

### Create a screenplay

1. On the home screen, click **New project**.
2. Choose **Screenplay**.
3. Fill in title, description, author, language, contact, and additional information.
4. Open the project and create a script.
5. Configure title, header, footer, scene prefix, initial numbering, logline, synopsis, genre, and script type.
6. Write using screenplay blocks and open statistics when needed.
7. Export as PDF or DOCX in script, outline, statistics, or complete-document mode, or save the script as `.gut`.

### Use Project resources

1. Open a project and click **Resources**.
2. Use **Information** for outline pages, synopsis, research, and notes.
3. Use **Flow** to create balloons, organize connections, and map relationships.
4. Register characters, places, and notes in their own tabs.
5. Use **Save resources** to generate `.gutr` or **Import resources** to add resources from another file.
6. Inside the editors, use **Resources** or **Ctrl + Alt + U** to consult the modal without leaving the text.

### Use the Library

1. Open **Library** from the home screen.
2. Click **Add book** and select EPUB or PDF files.
3. Open the imported book to read.
4. Use mode, font, size, summary, and navigation according to your preference.
5. Progress is saved automatically.

## Import, export, and custom files

| Format | Use |
|---|---|
| `.gut` | Saves main content: book chapters or a selected script. It can be imported into compatible projects. |
| `.gutr` | Saves project resources: information, flow, characters, places, and notes. |
| `.docx` | Can be imported as a chapter or screenplay and also used as an export format. |
| `.pdf` | Can be imported as a chapter or screenplay, exported from projects, and added to the library. |
| `.txt` | Can be imported as a chapter or screenplay. |
| `.epub` | Book export in EPUB 2.0 and EPUB 3.0; can also be imported into the library. |
| `.xhtml` | Simple XHTML book export. |

In desktop mode, `.gut` files can appear as a pending import on the home screen. The user can choose a compatible project or create a new project to receive the content.

## Development run

### Requirements

- Python 3.11+ recommended.
- Windows 10+ is required for the pywebview desktop mode, tray, and installer flow; on older versions or other operating systems, Gutenberg tries browser mode. If pystray fails or is unavailable, the app automatically starts in server mode without tray, equivalent to `python server_only.py`.
- Inno Setup 6 to generate the Windows installer.
- Dependencies listed in `requirements.txt`.

Install dependencies:

```bash
pip install -r requirements.txt
```

### Browser/server mode

Browser mode runs Gutenberg as a local server and lets you access the interface through the browser at `http://127.0.0.1:5000`. It is used automatically when the pywebview desktop mode cannot start, including Windows versions below 10, missing pywebview, or operating systems other than Windows. If pystray fails during this startup, Gutenberg drops the tray and keeps running in server mode without a tray icon, following the same flow as `server_only.py`.

```bash
python server_only.py
```

Then open:

```text
http://127.0.0.1:5000
```

### Desktop mode

Desktop mode uses pywebview and requires Windows 10 or later. If this requirement is not met, `python app.py` tries to start Gutenberg in browser mode; if pystray cannot be used, the automatic fallback is server mode without tray.

```bash
python app.py
```

## Tests

The project uses `unittest`.

```bash
python tests/run_tests.py
```

You can also run:

```bash
python -m unittest discover -s tests -v
```

The suite covers backend units, Flask routes, EPUB/PDF library, reading progress, collections, DOCX/PDF/TXT import, exports, `.gut` files, `.gutr` files, project resources, and pending import workflows.

## Project structure

```text
Gutenberg/
├── app.py                       # Desktop startup with pywebview
├── server_only.py               # Flask/browser execution
├── modules/                     # Backend: projects, library, import, export, i18n, persistence
├── templates/                   # Flask HTML templates
├── static/                      # CSS, JavaScript, icons, and interface images
├── locales/                     # pt_BR and en_US translations
├── documentation/               # Integrated HTML documentation
├── tests/                       # unittest automated tests
├── installer.ico                # Installer icon
├── Gutenberg.spec               # PyInstaller configuration
├── Gutenberg.iss                # Inno Setup script
├── version.txt                  # Version metadata
├── requirements.txt             # Python dependencies
└── README.md
```

## Local storage

By default, the app uses local folders for settings, projects, exports, and the library. Paths may vary depending on the system and the options saved in **Settings**.

- Settings: user data folder for the operating system.
- Projects: Gutenberg folder inside Documents, unless changed by configuration.
- Exports: folder configured by the user.
- Library: folder configured by the user, with imported files, covers, extracted data, and progress.
- Error logs: `Documents/gutenberg/errors.log`, with automatic rotation.

## Integrated documentation

The visual documentation is located at:

```text
documentation/index.html
```

It can also be opened from **Settings**. On desktop, it opens in the default browser; in browser mode, it is served by the application itself.

## Main assets

| Use | File |
|---|---|
| HTML favicon | `static/img/favicon.ico` |
| Executable icon | `static/img/icon.ico` |
| Tray icon | `static/img/favicon.ico` |
| Installer icon | `installer.ico` |
| `.gut` and `.gutr` file icon | `static/img/gut_file.ico` |
