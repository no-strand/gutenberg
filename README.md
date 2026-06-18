<div align="center">

# Gutenberg ✍️📚

**Editor local para criação de livros e roteiros**

Python · Flask · HTML · CSS · JavaScript

[Português (Brasil)](#português-brasil) · [English (US)](#english-us)

</div>

---

# Português (Brasil)

## Apresentação

**Gutenberg** é um editor local para criação de livros e roteiros. O projeto combina **Python**, **Flask**, **HTML**, **CSS** e **JavaScript** para oferecer uma interface de escrita organizada, com foco em planejamento, produção, revisão, exportação e leitura.

Ele pode ser usado como aplicativo desktop no Windows ou como servidor local acessado pelo navegador em outros ambientes compatíveis.

---

## O que o Gutenberg oferece

- Criar e organizar **projetos de livro** com capítulos, capa, metadados e tags.
- Criar **projetos de roteiro** com múltiplos roteiros, cenas, diálogos, personagens e blocos especializados.
- Escrever em editores com **formatação rica**, salvamento automático, atalhos e modo de leitura.
- Organizar **recursos do projeto**, como informações, fluxo visual, personagens, lugares e anotações.
- Consultar personagens, lugares e notas diretamente durante a escrita pelo modal de recursos.
- Revisar textos com integração à **API Gemini**, quando uma chave válida estiver configurada.
- Importar e exportar conteúdos em formatos como `.gut`, `.gutr`, `.docx`, `.pdf`, `.txt`, `.epub` e `.xhtml`.
- Exportar livros e roteiros em formatos de leitura ou compartilhamento.
- Manter uma biblioteca local para leitura de arquivos **EPUB** e **PDF**.

> A documentação integrada do projeto explica o uso detalhado de cada recurso.

---

## Requisitos

| Requisito | Observação |
|---|---|
| **Python 3.11+** | Recomendado para executar o projeto. |
| `requirements.txt` | Contém as dependências Python necessárias. |
| Navegador moderno | Necessário para uso em modo servidor/browser. |
| **Windows 10+** | Necessário para o modo desktop com `pywebview`. |
| **API Gemini** | Necessária apenas para usar a revisão automática. |

Para instalar as dependências:

```bash
pip install -r requirements.txt
```

---

## Compatibilidade

O modo desktop com `pywebview` é voltado para **Windows 10 ou superior**.

Em sistemas que não usam o modo desktop, como **Linux** e **macOS**, o Gutenberg pode ser executado como servidor local e acessado pelo navegador. Quando o `pystray` não está disponível ou falha durante a inicialização, o aplicativo cai automaticamente para o modo servidor sem ícone de bandeja, equivalente ao uso direto de `server_only.py`.

| Modo | Comando |
|---|---|
| Servidor/browser | `python server_only.py` |
| Inicializador principal | `python app.py` |

Depois de iniciar em modo servidor, acesse no navegador:

```text
http://127.0.0.1:5000
```

---

## Estrutura do projeto

```text
Gutenberg/
├── app.py                       # Inicialização principal do aplicativo
├── server_only.py               # Execução em modo servidor/browser
├── requirements.txt             # Dependências Python
├── modules/                     # Backend: projetos, biblioteca, importação, exportação, i18n e persistência
├── templates/                   # Templates HTML usados pelo Flask
├── static/                      # CSS, JavaScript, imagens e assets da interface
├── locales/                     # Arquivos de tradução pt_BR e en_US
├── documentation/               # Documentação integrada do aplicativo
└── tests/                       # Testes automatizados
```

---

## Armazenamento local

O Gutenberg salva dados localmente no computador do usuário. Projetos, biblioteca, exportações e configurações usam pastas locais, que podem ser ajustadas nas configurações do aplicativo.

---

# English (US)

## Overview

**Gutenberg** is a local editor for creating books and screenplays. The project combines **Python**, **Flask**, **HTML**, **CSS**, and **JavaScript** to provide an organized writing interface focused on planning, production, revision, export, and reading.

It can be used as a desktop application on Windows or as a local server accessed through the browser in other compatible environments.

---

## What Gutenberg offers

- Create and organize **book projects** with chapters, cover, metadata, and tags.
- Create **screenplay projects** with multiple scripts, scenes, dialogue, characters, and specialized blocks.
- Write in editors with **rich formatting**, autosave, shortcuts, and reading mode.
- Organize **project resources**, such as information, visual flow, characters, places, and notes.
- Consult characters, places, and notes directly while writing through the resources modal.
- Revise texts with **Gemini API** integration when a valid key is configured.
- Import and export content in formats such as `.gut`, `.gutr`, `.docx`, `.pdf`, `.txt`, `.epub`, and `.xhtml`.
- Export books and screenplays in reading or sharing formats.
- Keep a local library for reading **EPUB** and **PDF** files.

> The integrated project documentation explains the detailed use of each feature.

---

## Requirements

| Requirement | Note |
|---|---|
| **Python 3.11+** | Recommended to run the project. |
| `requirements.txt` | Contains the required Python dependencies. |
| Modern browser | Required for server/browser mode. |
| **Windows 10+** | Required for desktop mode with `pywebview`. |
| **Gemini API** | Required only for automatic revision. |

To install the dependencies:

```bash
pip install -r requirements.txt
```

---

## Compatibility

Desktop mode with `pywebview` is intended for **Windows 10 or later**.

On systems that do not use desktop mode, such as **Linux** and **macOS**, Gutenberg can run as a local server and be accessed through the browser. When `pystray` is not available or fails during startup, the application automatically falls back to server mode without a tray icon, equivalent to running `server_only.py` directly.

| Mode | Command |
|---|---|
| Server/browser | `python server_only.py` |
| Main launcher | `python app.py` |

After starting in server mode, open in the browser:

```text
http://127.0.0.1:5000
```

---

## Project structure

```text
Gutenberg/
├── app.py                       # Main application startup
├── server_only.py               # Server/browser mode execution
├── requirements.txt             # Python dependencies
├── modules/                     # Backend: projects, library, import, export, i18n, and persistence
├── templates/                   # HTML templates used by Flask
├── static/                      # CSS, JavaScript, images, and interface assets
├── locales/                     # pt_BR and en_US translation files
├── documentation/               # Integrated application documentation
└── tests/                       # Automated tests
```

---

## Local storage

Gutenberg saves data locally on the user's computer. Projects, library, exports, and settings use local folders, which can be adjusted in the application settings.
