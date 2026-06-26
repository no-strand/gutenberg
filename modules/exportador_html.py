"""Exportação em EPUB/XHTML com foco em compatibilidade real para EPUB 2 e EPUB 3."""
from __future__ import annotations

import html
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from bs4 import BeautifulSoup, Tag

from .manipulador_capitulos import listar_capitulos, ler_capitulo
from .manipulador_projetos import caminho_capa_projeto, normalizar_idioma_projeto, obter_projeto
from .utilidades import PASTA_PROJETOS, agora_iso, inferir_extensao_data_url, nome_seguro, obter_configuracoes, obter_pasta_exportacao_projeto
from .logging_config import obter_logger, registrar_etapa
logger = obter_logger(__name__)

CONTAINER_XML = """<?xml version='1.0' encoding='utf-8'?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="Misc/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

DISPLAY_OPTIONS_XML = """<?xml version='1.0' encoding='UTF-8'?>
<display_options>
  <platform name="*">
    <option name="specified-fonts">true</option>
  </platform>
</display_options>
"""

IDIOMAS = {"pt-BR": "pt-BR", "en_US": "en-US"}
CLASSES_ESTILO = ["alinhar-a-esquerda", "alinhar-centro", "alinhar-a-direita", "justificar", "recuo-a-esquerda", "recuo-a-direita", "fonte-serif", "fonte-sans", "fonte-mono"]


@registrar_etapa
def _idioma_projeto(projeto: dict) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        projeto: Dicionário com os metadados e configurações do projeto atual.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return IDIOMAS.get(normalizar_idioma_projeto(projeto.get("idioma")), "pt-BR")


@registrar_etapa
def _css_global() -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    cfg = obter_configuracoes()
    return f"""html, body {{
  margin: 0;
  padding: 0;
}}
body.conteudo {{
  font-family: Georgia, 'Times New Roman', serif;
  font-size: {cfg['tamanho_fonte_px']}px;
  line-height: {cfg['espaco_linhas']};
  margin: 0;
  padding: 0 6%;
}}
h1 {{
  font-size: {cfg['h1_px']}px;
  text-align: center;
  margin: 1.4em 0 1em;
  line-height: 1.2;
}}
h2 {{
  font-size: {cfg['h2_px']}px;
  text-align: left;
  margin: 1.5em 0 .8em;
  line-height: 1.25;
}}
h3 {{
  font-size: {cfg['h3_px']}px;
  text-align: left;
  margin: 1.3em 0 .7em;
  line-height: 1.25;
}}
p, li, blockquote {{
  margin: 0 0 {cfg['espaco_paragrafos_em']}em;
  overflow-wrap: break-word;
  word-wrap: break-word;
}}
p {{
  text-align: justify;
}}

p.editor-separador-decorativo {{
  text-align: center;
  text-indent: 0 !important;
  letter-spacing: 0.06em;
}}
p.editor-separador-decorativo span,
p.editor-separador-decorativo strong,
p.editor-separador-decorativo em,
p.editor-separador-decorativo u {{
  text-align: inherit;
}}
blockquote {{
  margin-left: 1.5em;
  margin-right: 1.5em;
}}
hr.editor-divider {{
  border: 0;
  border-top: 2px solid rgba(15, 23, 42, .18);
  margin: 1.2em 0;
  width: 100%;
}}
ul, ol {{
  margin: 0 0 {cfg['espaco_paragrafos_em']}em 1.5em;
  padding: 0;
}}
img {{
  width: 100%;
  max-width: 100%;
  height: auto;
  vertical-align: middle;
  display: block;
  margin: 1em auto;
}}
span.alinhar-a-esquerda {{ display:block; text-align:left !important; }}
span.alinhar-centro {{ display:block; text-align:center !important; }}
span.alinhar-a-direita {{ display:block; text-align:right !important; }}
span.justificar {{ display:block; text-align:justify !important; }}
span.recuo-a-esquerda {{ display:block; text-indent:0 !important; }}
span.recuo-a-direita {{ display:block; text-indent:{cfg['identacao_paragrafo_maior_em']}em !important; }}
p.alinhar-a-esquerda, h1.alinhar-a-esquerda, h2.alinhar-a-esquerda, h3.alinhar-a-esquerda, li.alinhar-a-esquerda, blockquote.alinhar-a-esquerda {{ text-align:left !important; }}
p.alinhar-centro, h1.alinhar-centro, h2.alinhar-centro, h3.alinhar-centro, li.alinhar-centro, blockquote.alinhar-centro {{ text-align:center !important; }}
p.alinhar-a-direita, h1.alinhar-a-direita, h2.alinhar-a-direita, h3.alinhar-a-direita, li.alinhar-a-direita, blockquote.alinhar-a-direita {{ text-align:right !important; }}
p.justificar, h1.justificar, h2.justificar, h3.justificar, li.justificar, blockquote.justificar {{ text-align:justify !important; }}
p.recuo-a-esquerda, li.recuo-a-esquerda, blockquote.recuo-a-esquerda {{ text-indent:0 !important; }}
p.recuo-a-direita, li.recuo-a-direita, blockquote.recuo-a-direita {{ text-indent:{cfg['identacao_paragrafo_maior_em']}em !important; }}
span.fonte-serif {{ font-family: Georgia, 'Times New Roman', serif; }}
span.fonte-sans {{ font-family: Arial, Helvetica, sans-serif; }}
span.fonte-mono {{ font-family: Consolas, 'Courier New', monospace; }}
a.editor-recurso-link,
a.editor-recurso-link:visited,
a.editor-recurso-link:hover,
a.editor-recurso-link:active {{
  color: inherit !important;
  text-decoration: none !important;
  background: transparent !important;
}}
.cover-page {{
  margin: 0;
  padding: 0;
}}
.cover-page img {{
  display: block;
  width: 100%;
  height: auto;
  max-width: 100%;
  max-height: 100vh;
  margin: 0 auto;
}}
"""


@registrar_etapa
def _sanitizar_nome_capitulo(titulo: str, fallback: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        titulo: Título exibido ou salvo para representar o conteúdo tratado.
        fallback: Valor usado pela rotina para compor a operação de sanitizar nome capitulo.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return nome_seguro(titulo) or fallback


@registrar_etapa
def _media_type_por_extensao(extensao: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        extensao: Valor usado pela rotina para compor a operação de media type por extensao.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return {
        ".xhtml": "application/xhtml+xml",
        ".css": "text/css",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".ncx": "application/x-dtbncx+xml",
        ".html": "application/xhtml+xml",
    }.get(extensao.lower(), "application/octet-stream")


@registrar_etapa
def _uuid_publicacao(slug: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, f'escritor-projetos:{slug}') }"


@registrar_etapa
def _substituir_imagens_base64(conteudo: str, pasta_images: Path) -> tuple[str, list[dict]]:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        conteudo: Valor usado pela rotina para compor a operação de substituir imagens base64.
        pasta_images: Valor usado pela rotina para compor a operação de substituir imagens base64.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    contador = 1
    imagens: list[dict] = []

    @registrar_etapa
    def repl(match: re.Match) -> str:
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            match: Valor usado pela rotina para compor a operação de repl.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        nonlocal contador
        src = match.group(1)
        if not src.startswith("data:image/"):
            return match.group(0)
        ext, dados = inferir_extensao_data_url(src)
        nome = f"imagem_{contador}{ext}"
        pasta_images.mkdir(parents=True, exist_ok=True)
        caminho = pasta_images / nome
        while caminho.exists():
            contador += 1
            nome = f"imagem_{contador}{ext}"
            caminho = pasta_images / nome
        caminho.write_bytes(dados)
        imagens.append({
            "nome": nome,
            "href": nome,
            "href_opf": f"../Images/{nome}",
            "media_type": _media_type_por_extensao(ext),
        })
        contador += 1
        return match.group(0).replace(src, f"Images/{nome}")

    novo_conteudo = re.sub(r'src=["\']([^"\']+)["\']', repl, conteudo, flags=re.IGNORECASE)
    return novo_conteudo, imagens


@registrar_etapa
def _normalizar_conteudo_html(conteudo: str) -> str:
    """
    Padroniza valores de entrada para que diferentes partes do sistema trabalhem com o mesmo formato.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        conteudo: Valor usado pela rotina para compor a operação de normalizar conteudo html.

    Retorno:
        O valor recebido em uma forma padronizada e segura para uso interno.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    conteudo = conteudo or "<p><span class='justificar recuo-a-direita'></span></p>"
    conteudo = re.sub(r"\sstyle=['\"]([^'\"]*)['\"]", '', conteudo)

    soup = BeautifulSoup(conteudo, 'html.parser')

    for tag in soup.find_all(["script", "style", "iframe", "object", "embed"]):
        tag.decompose()
    for tag in soup.find_all(True):
        for atributo in list(tag.attrs):
            if atributo.lower().startswith("on"):
                del tag.attrs[atributo]

    # Links internos de recursos existem apenas para uso dentro dos editores.
    # Em HTML/EPUB exportado eles devem virar texto normal, sem href.
    for tag in list(soup.find_all("a")):
        classes = tag.get("class") or []
        if isinstance(classes, str):
            classes = classes.split()
        if "editor-recurso-link" in classes or tag.has_attr("data-recurso-tipo") or tag.has_attr("data-recurso-nome"):
            tag.unwrap()

    @registrar_etapa
    def estilos_para_classes(classes: list[str]) -> str:
        """
        Converte a estrutura recebida para uma representação adequada ao próximo estágio do processamento.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            classes: Valor usado pela rotina para compor a operação de estilos para classes.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        estilos: list[str] = []
        valores = set(classes)
        if 'alinhar-a-esquerda' in valores:
            estilos.append('text-align:left !important')
        elif 'alinhar-centro' in valores:
            estilos.append('text-align:center !important')
        elif 'alinhar-a-direita' in valores:
            estilos.append('text-align:right !important')
        elif 'justificar' in valores:
            estilos.append('text-align:justify !important')
        if 'recuo-a-esquerda' in valores:
            estilos.append('text-indent:0 !important')
        elif 'recuo-a-direita' in valores:
            estilos.append(f"text-indent:{obter_configuracoes()['identacao_paragrafo_maior_em']}em !important")
        if 'fonte-serif' in valores:
            estilos.append("font-family:Georgia, 'Times New Roman', serif")
        elif 'fonte-sans' in valores:
            estilos.append('font-family:Arial, Helvetica, sans-serif')
        elif 'fonte-mono' in valores:
            estilos.append("font-family:Consolas, 'Courier New', monospace")
        return '; '.join(estilos)

    for tag in soup.find_all(True):
        classes_originais = tag.get('class', []) or []
        classes = [c for c in classes_originais if c in CLASSES_ESTILO or c == 'editor-separador-decorativo']
        if tag.name == 'span':
            if not classes:
                classes = ['justificar', 'recuo-a-direita']
            tag['class'] = list(dict.fromkeys(classes))
            estilos = estilos_para_classes(classes)
            if estilos:
                tag['style'] = estilos
            continue

        if tag.name in {'p', 'h1', 'h2', 'h3', 'li', 'blockquote'}:
            if classes:
                tag['class'] = list(dict.fromkeys(classes))
                estilos = estilos_para_classes(classes)
                if 'editor-separador-decorativo' in classes:
                    estilos = '; '.join(filter(None, [estilos, 'text-align:center !important', 'text-indent:0 !important', 'letter-spacing:0.06em']))
                if estilos:
                    tag['style'] = estilos

    return str(soup)


@registrar_etapa
def _doctype_por_versao(versao: str, formato_html: bool = False) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        versao: Valor usado pela rotina para compor a operação de doctype por versao.
        formato_html: Valor usado pela rotina para compor a operação de doctype por versao.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    if formato_html or str(versao).startswith('3'):
        return '<!DOCTYPE html>'
    return '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">'


@registrar_etapa
def _xhtml_documento(titulo: str, corpo: str, idioma: str, versao: str = '3.0', usar_css: bool = True, formato_html: bool = False) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        titulo: Título exibido ou salvo para representar o conteúdo tratado.
        corpo: Valor usado pela rotina para compor a operação de xhtml documento.
        idioma: Código de idioma usado para selecionar textos, metadados ou regras de formatação.
        versao: Valor usado pela rotina para compor a operação de xhtml documento.
        usar_css: Valor usado pela rotina para compor a operação de xhtml documento.
        formato_html: Valor usado pela rotina para compor a operação de xhtml documento.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    link = '<link rel="stylesheet" type="text/css" href="../Style/stylesheet.css" />' if usar_css else ""
    classe = ' class="conteudo"' if usar_css else ""
    doctype = _doctype_por_versao(versao, formato_html=formato_html)
    meta = '<meta charset="utf-8" />' if not formato_html else '<meta charset="utf-8">'
    corpo = _normalizar_conteudo_html(corpo)
    return f"""<?xml version='1.0' encoding='utf-8'?>
{doctype}
<html xmlns="http://www.w3.org/1999/xhtml" lang="{html.escape(idioma)}" xml:lang="{html.escape(idioma)}">
<head>
  {meta}
  <title>{html.escape(titulo)}</title>
  {link}
</head>
<body{classe}>
  <h1>{html.escape(titulo)}</h1>
  {corpo}
</body>
</html>
"""


@registrar_etapa
def _xhtml_capa(titulo: str, tem_capa: bool, idioma: str, versao: str = '3.0') -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        titulo: Título exibido ou salvo para representar o conteúdo tratado.
        tem_capa: Valor usado pela rotina para compor a operação de xhtml capa.
        idioma: Código de idioma usado para selecionar textos, metadados ou regras de formatação.
        versao: Valor usado pela rotina para compor a operação de xhtml capa.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    img = '<img src="../Images/cover.jpg" alt="Capa do projeto" />' if tem_capa else f'<h1>{html.escape(titulo)}</h1>'
    return f"""<?xml version='1.0' encoding='utf-8'?>
{_doctype_por_versao(versao)}
<html xmlns="http://www.w3.org/1999/xhtml" lang="{html.escape(idioma)}" xml:lang="{html.escape(idioma)}">
<head>
  <meta charset="utf-8" />
  <title>Capa</title>
  <link rel="stylesheet" type="text/css" href="../Style/stylesheet.css" />
</head>
<body class="cover-page">
  {img}
</body>
</html>
"""


@registrar_etapa
def _criar_toc_ncx(projeto: dict, itens: list[tuple[str, str]], identificador: str) -> str:
    """
    Cria um novo registro, arquivo ou estrutura interna mantendo o padrão de armazenamento do projeto.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        projeto: Dicionário com os metadados e configurações do projeto atual.
        itens: Valor usado pela rotina para compor a operação de criar toc ncx.
        identificador: Valor usado pela rotina para compor a operação de criar toc ncx.

    Retorno:
        Os dados do novo item criado, incluindo identificadores gerados quando existirem.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    pontos = []
    for i, (titulo, arquivo) in enumerate(itens, start=1):
        pontos.append(f'<navPoint id="nav-{i}" playOrder="{i}"><navLabel><text>{html.escape(titulo)}</text></navLabel><content src="../Text/{arquivo}"/></navPoint>')
    return f"""<?xml version='1.0' encoding='utf-8'?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="{html.escape(identificador)}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{html.escape(projeto['titulo'])}</text></docTitle>
  <navMap>
    {''.join(pontos)}
  </navMap>
</ncx>
"""


@registrar_etapa
def _criar_nav_xhtml(projeto: dict, itens: list[tuple[str, str]], idioma: str) -> str:
    """
    Cria um novo registro, arquivo ou estrutura interna mantendo o padrão de armazenamento do projeto.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        projeto: Dicionário com os metadados e configurações do projeto atual.
        itens: Valor usado pela rotina para compor a operação de criar nav xhtml.
        idioma: Código de idioma usado para selecionar textos, metadados ou regras de formatação.

    Retorno:
        Os dados do novo item criado, incluindo identificadores gerados quando existirem.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    lis = ''.join([f'<li><a href="{html.escape(arquivo)}">{html.escape(titulo)}</a></li>' for titulo, arquivo in itens])
    return f"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{html.escape(idioma)}" xml:lang="{html.escape(idioma)}">
<head>
  <meta charset="utf-8" />
  <title>Sumário</title>
  <link rel="stylesheet" type="text/css" href="../Style/stylesheet.css" />
</head>
<body class="conteudo">
  <nav epub:type="toc" id="toc">
    <h1>Sumário</h1>
    <ol>{lis}</ol>
  </nav>
</body>
</html>
"""


@registrar_etapa
def _criar_content_opf_epub2(projeto: dict, itens: list[tuple[str, str]], imagens: list[dict], tem_capa: bool, identificador: str) -> str:
    """
    Cria um novo registro, arquivo ou estrutura interna mantendo o padrão de armazenamento do projeto.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        projeto: Dicionário com os metadados e configurações do projeto atual.
        itens: Valor usado pela rotina para compor a operação de criar content opf epub2.
        imagens: Valor usado pela rotina para compor a operação de criar content opf epub2.
        tem_capa: Valor usado pela rotina para compor a operação de criar content opf epub2.
        identificador: Valor usado pela rotina para compor a operação de criar content opf epub2.

    Retorno:
        Os dados do novo item criado, incluindo identificadores gerados quando existirem.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    idioma = _idioma_projeto(projeto)
    manifesto = [
        '<item id="css" href="../Style/stylesheet.css" media-type="text/css"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="cover-xhtml" href="../Text/cover.xhtml" media-type="application/xhtml+xml"/>',
    ]
    spine = ['<itemref idref="cover-xhtml"/>']
    guide = ['<reference type="cover" title="Capa" href="../Text/cover.xhtml"/>']
    if tem_capa:
        manifesto.append('<item id="cover-image" href="../Images/cover.jpg" media-type="image/jpeg"/>')
    for idx, imagem in enumerate(imagens, start=1):
        manifesto.append(f'<item id="img-{idx}" href="{html.escape(imagem["href_opf"])}" media-type="{imagem["media_type"]}"/>')
    for idx, (titulo, arquivo) in enumerate(itens, start=1):
        manifesto.append(f'<item id="chap-{idx}" href="../Text/{arquivo}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="chap-{idx}"/>')
        if idx == 1:
            guide.append(f'<reference type="text" title="Início" href="../Text/{arquivo}"/>')
    meta_cover = '<meta name="cover" content="cover-image"/>' if tem_capa else ''
    return f"""<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata>
    <dc:title>{html.escape(projeto['titulo'])}</dc:title>
    <dc:language>{html.escape(idioma)}</dc:language>
    <dc:identifier id="BookId" opf:scheme="UUID">{html.escape(identificador)}</dc:identifier>
    <dc:creator opf:role="aut">{html.escape(projeto.get('autor') or 'Não informado')}</dc:creator>
    <dc:description>{html.escape(projeto.get('descricao') or '')}</dc:description>
    <dc:subject>{html.escape(', '.join(projeto.get('tags', [])))}</dc:subject>
    <dc:date>{html.escape((projeto.get('data_criacao') or agora_iso())[:10])}</dc:date>
    <dc:format>application/epub+zip;version=2.0</dc:format>
    {meta_cover}
  </metadata>
  <manifest>{''.join(manifesto)}</manifest>
  <spine toc="ncx">{''.join(spine)}</spine>
  <guide>{''.join(guide)}</guide>
</package>
"""


@registrar_etapa
def _criar_content_opf_epub3(projeto: dict, itens: list[tuple[str, str]], imagens: list[dict], tem_capa: bool, identificador: str, versao: str) -> str:
    """
    Cria um novo registro, arquivo ou estrutura interna mantendo o padrão de armazenamento do projeto.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        projeto: Dicionário com os metadados e configurações do projeto atual.
        itens: Valor usado pela rotina para compor a operação de criar content opf epub3.
        imagens: Valor usado pela rotina para compor a operação de criar content opf epub3.
        tem_capa: Valor usado pela rotina para compor a operação de criar content opf epub3.
        identificador: Valor usado pela rotina para compor a operação de criar content opf epub3.
        versao: Valor usado pela rotina para compor a operação de criar content opf epub3.

    Retorno:
        Os dados do novo item criado, incluindo identificadores gerados quando existirem.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    idioma = _idioma_projeto(projeto)
    manifesto = [
        '<item id="css" href="../Style/stylesheet.css" media-type="text/css"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="cover-xhtml" href="../Text/cover.xhtml" media-type="application/xhtml+xml"/>',
        '<item id="nav" href="../Text/nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
    ]
    spine = ['<itemref idref="cover-xhtml"/>', '<itemref idref="nav" linear="no"/>']
    if tem_capa:
        manifesto.append('<item id="cover-image" href="../Images/cover.jpg" media-type="image/jpeg" properties="cover-image"/>')
    for idx, imagem in enumerate(imagens, start=1):
        manifesto.append(f'<item id="img-{idx}" href="{html.escape(imagem["href_opf"])}" media-type="{imagem["media_type"]}"/>')
    for idx, (titulo, arquivo) in enumerate(itens, start=1):
        manifesto.append(f'<item id="chap-{idx}" href="../Text/{arquivo}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="chap-{idx}"/>')
    data_modificada = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return f"""<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="{versao}" prefix="dcterms: http://purl.org/dc/terms/">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="BookId">{html.escape(identificador)}</dc:identifier>
    <dc:title id="title">{html.escape(projeto['titulo'])}</dc:title>
    <dc:language>{html.escape(idioma)}</dc:language>
    <dc:creator id="creator">{html.escape(projeto.get('autor') or 'Não informado')}</dc:creator>
    <dc:description>{html.escape(projeto.get('descricao') or '')}</dc:description>
    <dc:subject>{html.escape(', '.join(projeto.get('tags', [])))}</dc:subject>
    <dc:date>{html.escape((projeto.get('data_criacao') or agora_iso())[:10])}</dc:date>
    <dc:format>application/epub+zip;version={html.escape(versao)}</dc:format>
    <meta property="dcterms:modified">{html.escape(data_modificada)}</meta>
    <meta property="belongs-to-collection">Escritor de Projetos</meta>
  </metadata>
  <manifest>{''.join(manifesto)}</manifest>
  <spine>{''.join(spine)}</spine>
</package>
"""


@registrar_etapa
def _criar_content_opf(projeto: dict, itens: list[tuple[str, str]], imagens: list[dict], versao: str, tem_capa: bool, identificador: str) -> str:
    """
    Cria um novo registro, arquivo ou estrutura interna mantendo o padrão de armazenamento do projeto.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        projeto: Dicionário com os metadados e configurações do projeto atual.
        itens: Valor usado pela rotina para compor a operação de criar content opf.
        imagens: Valor usado pela rotina para compor a operação de criar content opf.
        versao: Valor usado pela rotina para compor a operação de criar content opf.
        tem_capa: Valor usado pela rotina para compor a operação de criar content opf.
        identificador: Valor usado pela rotina para compor a operação de criar content opf.

    Retorno:
        Os dados do novo item criado, incluindo identificadores gerados quando existirem.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    if str(versao).startswith('2'):
        return _criar_content_opf_epub2(projeto, itens, imagens, tem_capa, identificador)
    return _criar_content_opf_epub3(projeto, itens, imagens, tem_capa, identificador, str(versao))


@registrar_etapa
def exportar_projeto_xhtml(slug: str) -> Path:
    """
    Conduz a exportação dos dados do projeto para o formato esperado, preparando o conteúdo e delegando etapas auxiliares quando necessário.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.

    Retorno:
        O caminho do arquivo exportado ou uma estrutura com informações da exportação.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    projeto = obter_projeto(slug)
    idioma = _idioma_projeto(projeto)
    raiz_export = obter_pasta_exportacao_projeto(projeto['titulo']) / 'xhtml'
    if raiz_export.exists():
        shutil.rmtree(raiz_export)
    (raiz_export / 'Style').mkdir(parents=True, exist_ok=True)
    (raiz_export / 'Style' / 'stylesheet.css').write_text(_css_global(), encoding='utf-8')
    usados: set[str] = set()
    pasta_projeto = PASTA_PROJETOS / slug
    for capitulo_info in listar_capitulos(pasta_projeto):
        capitulo = ler_capitulo(pasta_projeto, capitulo_info['id'])
        titulo = capitulo.get('titulo') or f"Capítulo {capitulo_info['id']}"
        nome = _sanitizar_nome_capitulo(titulo, f"capitulo_{capitulo_info['id']}")
        if nome in usados:
            nome = f"{nome}_{capitulo_info['id']}"
        usados.add(nome)
        conteudo = '\n'.join(capitulo.get('paragrafos', []))
        html_doc = _xhtml_documento(titulo, conteudo, idioma, versao='3.0', usar_css=True, formato_html=True)
        html_doc = html_doc.replace('../Style/stylesheet.css', 'Style/stylesheet.css')
        (raiz_export / f"{nome}.html").write_text(html_doc, encoding='utf-8')
    return raiz_export


@registrar_etapa
def exportar_projeto_epub(slug: str, versao: str = '2.0') -> Path:
    """
    Conduz a exportação dos dados do projeto para o formato esperado, preparando o conteúdo e delegando etapas auxiliares quando necessário.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        versao: Valor usado pela rotina para compor a operação de exportar projeto epub.

    Retorno:
        O caminho do arquivo exportado ou uma estrutura com informações da exportação.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    projeto = obter_projeto(slug)
    idioma = _idioma_projeto(projeto)
    pasta_projeto = PASTA_PROJETOS / slug
    base_saida = obter_pasta_exportacao_projeto(projeto["titulo"])
    temporaria = base_saida / f"_{nome_seguro(projeto['titulo'])}_epub"
    if temporaria.exists():
        shutil.rmtree(temporaria)
    for pasta in [temporaria / 'META-INF', temporaria / 'Text', temporaria / 'Style', temporaria / 'Images', temporaria / 'Misc']:
        pasta.mkdir(parents=True, exist_ok=True)
    identificador = _uuid_publicacao(slug)
    (temporaria / 'mimetype').write_text('application/epub+zip', encoding='utf-8')
    (temporaria / 'META-INF' / 'container.xml').write_text(CONTAINER_XML, encoding='utf-8')
    (temporaria / 'META-INF' / 'com.apple.ibooks.display-options.xml').write_text(DISPLAY_OPTIONS_XML, encoding='utf-8')
    (temporaria / 'Style' / 'stylesheet.css').write_text(_css_global(), encoding='utf-8')
    imagens_manifesto: list[dict] = []
    tem_capa = caminho_capa_projeto(slug).exists()
    if tem_capa:
        shutil.copy2(caminho_capa_projeto(slug), temporaria / 'Images' / 'cover.jpg')
    (temporaria / 'Text' / 'cover.xhtml').write_text(_xhtml_capa(projeto['titulo'], tem_capa, idioma, versao=versao), encoding='utf-8')
    itens_navegacao: list[tuple[str, str]] = [('Capa', 'cover.xhtml')]
    itens_capitulos: list[tuple[str, str]] = []
    usados: set[str] = set()
    for capitulo_info in listar_capitulos(pasta_projeto):
        capitulo = ler_capitulo(pasta_projeto, capitulo_info['id'])
        titulo = capitulo.get('titulo') or f"Capítulo {capitulo_info['id']}"
        nome = _sanitizar_nome_capitulo(titulo, f"capitulo_{capitulo_info['id']}")
        if nome in usados:
            nome = f"{nome}_{capitulo_info['id']}"
        usados.add(nome)
        nome_arquivo = f"{nome}.xhtml"
        conteudo_original = '\n'.join(capitulo.get('paragrafos', []))
        conteudo, imagens = _substituir_imagens_base64(_normalizar_conteudo_html(conteudo_original), temporaria / 'Images')
        imagens_manifesto.extend(imagens)
        (temporaria / 'Text' / nome_arquivo).write_text(_xhtml_documento(titulo, conteudo, idioma, versao=versao, usar_css=True), encoding='utf-8')
        itens_navegacao.append((titulo, nome_arquivo))
        itens_capitulos.append((titulo, nome_arquivo))
    if not itens_capitulos:
        vazio = 'capitulo_inicial.xhtml'
        corpo = '<p><span class="justificar recuo-a-direita">Projeto sem capítulos no momento.</span></p>'
        (temporaria / 'Text' / vazio).write_text(_xhtml_documento('Início', corpo, idioma, versao=versao, usar_css=True), encoding='utf-8')
        itens_navegacao.append(('Início', vazio))
        itens_capitulos.append(('Início', vazio))
    if str(versao).startswith('3'):
        (temporaria / 'Text' / 'nav.xhtml').write_text(_criar_nav_xhtml(projeto, itens_navegacao, idioma), encoding='utf-8')
    (temporaria / 'Misc' / 'toc.ncx').write_text(_criar_toc_ncx(projeto, itens_navegacao, identificador), encoding='utf-8')
    (temporaria / 'Misc' / 'content.opf').write_text(_criar_content_opf(projeto, itens_capitulos, imagens_manifesto, versao, tem_capa, identificador), encoding='utf-8')
    epub_path = base_saida / f"{nome_seguro(projeto['titulo'])}.epub"
    with ZipFile(epub_path, 'w') as zf:
        zf.write(temporaria / 'mimetype', arcname='mimetype', compress_type=ZIP_STORED)
        for arquivo in sorted(temporaria.rglob('*')):
            if arquivo.is_file() and arquivo.name != 'mimetype':
                zf.write(arquivo, arcname=arquivo.relative_to(temporaria).as_posix(), compress_type=ZIP_DEFLATED)
    return epub_path
