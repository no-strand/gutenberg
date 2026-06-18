# Gutenberg ✍️📚

**Gutenberg** é um editor local para criação de livros e roteiros. O projeto combina **Python**, **Flask**, **HTML**, **CSS** e **JavaScript** para oferecer uma interface de escrita organizada, com foco em planejamento, produção, revisão, exportação e leitura.

Ele pode ser usado como aplicativo desktop no Windows ou como servidor local acessado pelo navegador em outros ambientes compatíveis.

---

## O que o Gutenberg oferece

Com o Gutenberg, é possível:

- Criar e organizar **projetos de livro** com capítulos, capa, metadados e tags.
- Criar **projetos de roteiro** com múltiplos roteiros, cenas, diálogos, personagens e blocos especializados.
- Escrever em editores com **formatação rica**, salvamento automático, atalhos e modo de leitura.
- Organizar **recursos do projeto**, como informações, fluxo visual, personagens, lugares e anotações.
- Consultar personagens, lugares e notas diretamente durante a escrita pelo modal de recursos.
- Revisar textos com integração à **API Gemini**, quando uma chave válida estiver configurada.
- Importar e exportar conteúdos em formatos como `.gut`, `.gutr`, `.docx`, `.pdf`, `.txt`, `.epub` e `.xhtml`.
- Exportar livros e roteiros em formatos de leitura ou compartilhamento.
- Manter uma biblioteca local para leitura de arquivos **EPUB** e **PDF**.
- Alternar a interface entre **Português (Brasil)** e **English (US)**.

A documentação integrada do projeto explica o uso detalhado de cada recurso.

---

## Requisitos

- **Python 3.11+** recomendado.
- Dependências listadas em `requirements.txt`.
- Navegador moderno para uso em modo servidor/browser.
- **Windows 10+** para o modo desktop com `pywebview`.
- Chave da **API Gemini** apenas se o usuário quiser usar a revisão automática.

Para instalar as dependências:

```bash
pip install -r requirements.txt
```

---

## Compatibilidade

O modo desktop com `pywebview` é voltado para **Windows 10 ou superior**.

Em sistemas que não usam o modo desktop, como **Linux** e **macOS**, o Gutenberg pode ser executado como servidor local e acessado pelo navegador. Quando o `pystray` não está disponível ou falha durante a inicialização, o aplicativo cai automaticamente para o modo servidor sem ícone de bandeja, equivalente ao uso direto de `server_only.py`.

Execução em modo servidor:

```bash
python server_only.py
```

Depois, acesse no navegador:

```text
http://127.0.0.1:5000
```

Execução pelo inicializador principal:

```bash
python app.py
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
