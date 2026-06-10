# Gutenberg ✍️📚

**Gutenberg** é um aplicativo local para criação literária, escrita de roteiros, revisão, exportação e leitura de biblioteca digital. Ele combina **Python + Flask + HTML/CSS/JavaScript** com modo desktop via **pywebview**, mantendo os dados do usuário organizados localmente.

> Foco da aplicação: escrever, revisar, importar, exportar e ler projetos de **livro**, **roteiro**, **EPUB** e **PDF** em um fluxo simples e integrado.

---

## ✨ Recursos principais

| Área | Funcionalidades |
|---|---|
| **Projetos** | Criação e gerenciamento de projetos do tipo **Livro** e **Roteiro**. |
| **Editor de livro** | Capítulos com formatação rica, imagens, títulos, listas, alinhamentos, recuos e salvamento automático. |
| **Editor de roteiro** | Blocos próprios para cena, ação, personagem, diálogo, parenthetical, transição, comentário, música e outros elementos de roteiro. |
| **Catálogo** | Personagens e locais detectáveis/organizáveis em projetos de roteiro. |
| **Revisão** | Revisão ortográfica e gramatical com integração configurável por chave de API Gemini. |
| **Importação** | Entrada de **.gut**, **.docx**, **.pdf** e **.txt** como capítulos de livro ou roteiros, conforme o tipo do projeto. |
| **Exportação de livros** | **EPUB 2.0**, **EPUB 3.0**, **XHTML**, **DOCX** e **PDF**. |
| **Exportação de roteiros** | **DOCX** e **PDF** com estrutura de roteiro. |
| **Snapshots .gut** | Pacotes binários para salvar, transferir, restaurar ou abrir/importar projetos compatíveis. |
| **Biblioteca** | Leitura de **EPUB** e **PDF**, progresso, sumário, coleções e configurações de leitura. |
| **Internacionalização** | Interface em **Português (Brasil)** e **English (US)**. |
| **Desktop/browser** | Modo desktop com pywebview e modo browser com tray icon no Windows. |
| **Documentação integrada** | Documentação HTML disponível em `documentation/index.html` e pela tela de Configurações. |

---

## 🧭 Fluxos de uso

### Livro

1. Crie um projeto do tipo **Livro**.
2. Cadastre título, autor, idioma, descrição, tags e capa opcional.
3. Crie capítulos e escreva no editor com salvamento automático.
4. Revise o texto quando necessário.
5. Exporte em EPUB, XHTML, DOCX, PDF ou salve um snapshot `.gut`.

### Roteiro

1. Crie um projeto do tipo **Roteiro**.
2. Informe contato, autor, metadados e tipo de roteiro.
3. Escreva usando blocos de cena, ação, personagem e diálogo.
4. Use catálogos de personagens/locais e estatísticas.
5. Exporte em DOCX/PDF ou salve um snapshot `.gut`.

### Importação

- Projetos de livro importam `.docx`, `.pdf` e `.txt` como novos capítulos.
- Projetos de roteiro importam `.docx`, `.pdf` e `.txt` como novo roteiro estruturado.
- Arquivos `.gut` restauram conteúdo em projetos compatíveis.
- No desktop, arquivos `.gut` podem ser registrados como importação pendente e depois importados para um projeto existente ou para um projeto novo.

---

## 🗂️ Estrutura do projeto

```text
Gutenberg/
├── app.py                       # Inicialização desktop com pywebview
├── server_only.py               # Execução somente Flask/browser
├── modules/                     # Backend: projetos, importação, exportação, biblioteca, i18n
├── templates/                   # Templates HTML Flask
├── static/                      # CSS, JS e imagens da interface
├── locales/                     # Traduções pt_BR e en_US
├── documentation/               # Documentação HTML integrada
├── tests/                       # Testes automatizados unittest
├── installer.ico                # Ícone do instalador
├── requirements.txt             # Dependências
└── README.md
```

---

## ⚙️ Requisitos

- **Python 3.11+** recomendado.
- **Windows 10/11** para o fluxo completo desktop, tray e instalador.
- **Inno Setup 6** para gerar o instalador.
- Dependências listadas em `requirements.txt`.

Instale tudo com:

```bash
pip install -r requirements.txt
```

---

## ▶️ Execução em desenvolvimento

### Modo browser/servidor

```bash
python server_only.py
```

Depois acesse:

```text
http://127.0.0.1:5000
```

### Modo desktop

```bash
python app.py
```

---

## 🧪 Testes

O projeto usa `unittest` e mantém testes em `tests/`.

```bash
python tests/run_tests.py
```

Ou, usando o executor padrão:

```bash
python -m unittest discover -s tests -v
```

A suíte cobre backend, rotas Flask, importação DOCX/PDF/TXT, criação/importação `.gut`, exportação XHTML/EPUB, validações, catálogo, créditos e fluxos de importação pendente.

Mais detalhes em [`TESTES.md`](TESTES.md).

---

## 📦 Build do executável

O build desktop usa **PyInstaller** com `Gutenberg.spec`:

```bash
pyinstaller Gutenberg.spec
```

Saída esperada:

```text
dist/Gutenberg/
```

O pacote inclui templates, arquivos estáticos, traduções, documentação HTML e metadados de versão.

---

## Instalador Windows

Depois do build com PyInstaller, compile `Gutenberg.iss` no **Inno Setup**.

Saída esperada:

```text
dist_installer/
```

O instalador usa `installer.ico`, inclui todos os arquivos do build e oferece suporte a sistemas x64 compatíveis.

---

## 🎨 Ícones e assets principais

| Uso | Arquivo |
|---|---|
| Favicon HTML | `static/img/favicon.ico` |
| Executável | `static/img/icon.ico` |
| Tray icon | `static/img/favicon.ico` |
| Instalador | `installer.ico` |
| Arquivos `.gut` | `static/img/gut_file.ico` |

---

## 💾 Armazenamento local

Por padrão, o aplicativo organiza dados em pastas locais:

- configurações em `AppData/Roaming/Gutenberg`;
- projetos em uma pasta Gutenberg dentro de **Documentos**;
- exportações na pasta configurada pelo usuário;
- biblioteca EPUB/PDF na pasta configurada pelo usuário.

Esses caminhos podem variar conforme as opções salvas em Configurações.

---

## Logging

O logging centralizado fica em `modules/logging_config.py`.

- `DEBUG`: etapas detalhadas de execução.
- `INFO`: inicialização, eventos e requisições relevantes.
- `WARNING`: validações, respostas 4xx e condições recuperáveis.
- `ERROR`/`CRITICAL`: falhas com stack trace.

O arquivo de erro é criado automaticamente em:

```text
Documentos/gutenberg/errors.log
```

Ele registra apenas `ERROR` e `CRITICAL`, com rotação de 5 MB e 7 backups. Para testes/suporte, é possível sobrescrever a pasta com `GUTENBERG_LOG_DIR`.

---

## 📖 Documentação

A documentação visual do aplicativo está em:

```text
documentation/index.html
```

Ela também é acessível pela tela **Configurações**. No desktop, abre no navegador padrão; no modo browser, é servida pela própria aplicação.

---
