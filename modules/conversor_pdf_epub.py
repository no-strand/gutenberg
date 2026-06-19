"""
Conversão de PDF para EPUB com preservação de estrutura, estilos básicos, capa e navegação entre capítulos.

"""

from __future__ import annotations

import html
import io
import posixpath
import re
import statistics
import unicodedata
import uuid
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

import fitz
from PIL import Image
from .logging_config import obter_logger, registrar_etapa
logger = obter_logger(__name__)


EPUB_MIMETYPE = 'application/epub+zip'


@dataclass
class SpanInfo:
    """
    Representa SpanInfo dentro do fluxo da aplicação.

    Esta classe concentra estado e comportamentos relacionados para evitar que a
    lógica fique espalhada por vários pontos do código. A intenção é oferecer uma
    interface simples para quem consome o módulo, escondendo os detalhes internos
    de organização, validação e integração com os demais componentes.
    """
    text: str
    size: float
    flags: int
    font: str
    bbox: tuple[float, float, float, float]
    underlined: bool = False


@dataclass
class BlockInfo:
    """
    Representa BlockInfo dentro do fluxo da aplicação.

    Esta classe concentra estado e comportamentos relacionados para evitar que a
    lógica fique espalhada por vários pontos do código. A intenção é oferecer uma
    interface simples para quem consome o módulo, escondendo os detalhes internos
    de organização, validação e integração com os demais componentes.
    """
    kind: str
    html: str
    text: str
    level: int = 0
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


HORIZONTAL_LINE_TOLERANCE = 3.0
MIN_UNDERLINE_WIDTH = 6.0
MAX_WORDS_IN_HEADING = 18




COMMON_PT_WORDS = {
    'a', 'à', 'ao', 'aos', 'aquela', 'aquelas', 'aquele', 'aqueles', 'aquilo', 'as', 'até',
    'com', 'como', 'contra', 'da', 'das', 'de', 'dela', 'dele', 'deles', 'demais', 'depois',
    'do', 'dos', 'e', 'ela', 'elas', 'ele', 'eles', 'em', 'entre', 'era', 'eram', 'essa', 'esse',
    'esta', 'está', 'estao', 'estão', 'eu', 'foi', 'fora', 'há', 'isso', 'isto', 'já', 'la', 'lá',
    'lhe', 'lhes', 'mais', 'mas', 'me', 'mesmo', 'meu', 'minha', 'muito', 'na', 'não', 'nas', 'nem',
    'no', 'noite', 'nos', 'nós', 'num', 'numa', 'o', 'os', 'ou', 'para', 'pela', 'pelas', 'pelo', 'pelos',
    'por', 'porque', 'quando', 'que', 'quem', 'se', 'sem', 'seu', 'sua', 'suas', 'tambem', 'também',
    'tarde', 'te', 'tem', 'tinha', 'todas', 'todos', 'tu', 'um', 'uma', 'umas', 'uns', 'vida', 'vez', 'viu',
    'você', 'vocês', 'já', 'ser', 'só', 'sobre', 'sob', 'dos', 'das', 'lhe', 'ouvia', 'ouvia-se', 'ouviam', 'tambores'
}


@registrar_etapa
def _normalize_word(texto: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        texto: Texto bruto ou parcialmente tratado que será analisado pela função.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    base = unicodedata.normalize('NFKD', texto or '')
    sem_acentos = ''.join(ch for ch in base if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]+', '', sem_acentos.lower())


@registrar_etapa
def _collect_pdf_lexicon(doc: fitz.Document) -> set[str]:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        doc: Documento em processamento, normalmente vindo de uma biblioteca de exportação ou leitura.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    lexicon = {_normalize_word(palavra) for palavra in COMMON_PT_WORDS}
    for page_index in range(len(doc)):
        page = doc.load_page(page_index)
        data = page.get_text('dict', flags=fitz.TEXTFLAGS_DICT)
        for block in data.get('blocks', []):
            if block.get('type', 0) != 0:
                continue
            for line in block.get('lines', []):
                for span in line.get('spans', []):
                    texto = span.get('text') or ''
                    for palavra in re.findall(r"[A-Za-zÀ-ÿ]+(?:['’-][A-Za-zÀ-ÿ]+)?", texto):
                        normalizada = _normalize_word(palavra)
                        if len(normalizada) >= 2:
                            lexicon.add(normalizada)
    return {item for item in lexicon if item}


@registrar_etapa
def _split_glued_word(token: str, lexicon: set[str]) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        token: Valor usado pela rotina para compor a operação de split glued word.
        lexicon: Valor usado pela rotina para compor a operação de split glued word.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    token_limpo = token.strip()
    normalizado = _normalize_word(token_limpo)
    if not token_limpo or len(normalizado) < 7 or normalizado in lexicon:
        return token
    if not re.fullmatch(r"[A-Za-zÀ-ÿ]+", token_limpo):
        return token
    melhores: list[tuple[int, str]] = []
    for idx in range(2, len(token_limpo) - 1):
        esquerda = token_limpo[:idx]
        direita = token_limpo[idx:]
        ne = _normalize_word(esquerda)
        nd = _normalize_word(direita)
        if len(ne) < 2 or len(nd) < 2:
            continue
        if ne in lexicon and nd in lexicon:
            score = abs(len(ne) - len(nd))
            if ne in {'a', 'e', 'o'} or nd in {'a', 'e', 'o'}:
                score += 1
            melhores.append((score, f'{esquerda} {direita}'))
    if not melhores:
        return token
    melhores.sort(key=lambda item: item[0])
    return melhores[0][1]


@registrar_etapa
def _correct_glued_words(texto: str, lexicon: set[str]) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        texto: Texto bruto ou parcialmente tratado que será analisado pela função.
        lexicon: Valor usado pela rotina para compor a operação de correct glued words.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    if not texto:
        return texto
    return re.sub(r"[A-Za-zÀ-ÿ]{7,}", lambda m: _split_glued_word(m.group(0), lexicon), texto)


@registrar_etapa
def _is_standalone_numeric_line(texto: str) -> bool:
    """
    Avalia uma condição específica do conteúdo recebido e devolve uma resposta simples para orientar o fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        texto: Texto bruto ou parcialmente tratado que será analisado pela função.

    Retorno:
        True ou False, conforme a condição analisada seja atendida.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    texto_limpo = (texto or '').strip()
    return bool(texto_limpo) and bool(re.fullmatch(r'(?:\d{1,4}|[IVXLCDMivxlcdm]{1,12})', texto_limpo))


CSS_EPUB = """body {
  font-family: serif;
  line-height: 1.6;
  margin: 0 auto;
  max-width: 48rem;
  padding: 1.2rem 1rem 2rem;
  color: #111;
}
img {
  max-width: 100%;
  height: auto;
  display: block;
  margin: 0 auto;
}
.cover-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.cover-page img {
  width: 100%;
}
p {
  margin: 0 0 1em;
  text-align: justify;
}
h1, h2, h3 {
  line-height: 1.25;
  margin: 1.4em 0 0.6em;
}
h1 { font-size: 1.8em; }
h2 { font-size: 1.45em; }
h3 { font-size: 1.2em; }
.page-break {
  break-before: page;
}
.image-block {
  text-align: center;
  margin: 0 auto 1rem;
}
.image-block img,
.pdf-page-image {
  margin: 0 auto;
  border-radius: 0.4rem;
}
.dropcap {
  float: left;
  font-size: 4.4em;
  line-height: 0.82;
  font-weight: 700;
  margin: 0.02em 0.12em 0 0;
}
"""


@registrar_etapa
def _slugify(texto: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        texto: Texto bruto ou parcialmente tratado que será analisado pela função.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    texto = (texto or '').strip().lower()
    texto = re.sub(r'[^a-z0-9]+', '-', texto)
    return texto.strip('-') or 'book'


@registrar_etapa
def _compact_spaces(texto: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        texto: Texto bruto ou parcialmente tratado que será analisado pela função.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return ' '.join((texto or '').split())


@registrar_etapa
def _escape_text(texto: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        texto: Texto bruto ou parcialmente tratado que será analisado pela função.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return html.escape(texto or '', quote=False)


@registrar_etapa
def _is_bold(span: SpanInfo) -> bool:
    """
    Avalia uma condição específica do conteúdo recebido e devolve uma resposta simples para orientar o fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        span: Valor usado pela rotina para compor a operação de is bold.

    Retorno:
        True ou False, conforme a condição analisada seja atendida.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    font = (span.font or '').lower()
    return 'bold' in font or bool(span.flags & (1 << 4))


@registrar_etapa
def _is_italic(span: SpanInfo) -> bool:
    """
    Avalia uma condição específica do conteúdo recebido e devolve uma resposta simples para orientar o fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        span: Valor usado pela rotina para compor a operação de is italic.

    Retorno:
        True ou False, conforme a condição analisada seja atendida.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    font = (span.font or '').lower()
    return 'italic' in font or 'oblique' in font or bool(span.flags & (1 << 1))


@registrar_etapa
def _extract_horizontal_lines(page: fitz.Page) -> list[tuple[float, float, float, float]]:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        page: Página do documento analisada individualmente.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    linhas: list[tuple[float, float, float, float]] = []
    try:
        drawings = page.get_drawings()
    except Exception:
        return linhas
    for drawing in drawings:
        for item in drawing.get('items', []):
            if not item:
                continue
            kind = item[0]
            if kind == 'l':
                p1 = item[1]
                p2 = item[2]
                if abs(p1.y - p2.y) <= HORIZONTAL_LINE_TOLERANCE:
                    x0, x1 = sorted((float(p1.x), float(p2.x)))
                    y = float((p1.y + p2.y) / 2)
                    if (x1 - x0) >= MIN_UNDERLINE_WIDTH:
                        linhas.append((x0, y, x1, y))
            elif kind == 're':
                rect = item[1]
                if rect.height <= HORIZONTAL_LINE_TOLERANCE + 1 and rect.width >= MIN_UNDERLINE_WIDTH:
                    y = float(rect.y0 + (rect.height / 2))
                    linhas.append((float(rect.x0), y, float(rect.x1), y))
    return linhas


@registrar_etapa
def _span_is_underlined(span_bbox: tuple[float, float, float, float], linhas: list[tuple[float, float, float, float]]) -> bool:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        span_bbox: Valor usado pela rotina para compor a operação de span is underlined.
        linhas: Linhas já extraídas de um documento e enriquecidas com metadados básicos.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    x0, y0, x1, y1 = span_bbox
    baseline = y1 + 1.5
    for lx0, ly, lx1, _ in linhas:
        if abs(ly - baseline) <= 3.0 and lx0 <= x0 + 2 and lx1 >= x1 - 2:
            return True
    return False


@registrar_etapa
def _span_to_html(span: SpanInfo) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        span: Valor usado pela rotina para compor a operação de span to html.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    texto = _escape_text(span.text)
    if not texto:
        return ''
    if span.underlined:
        texto = f'<u>{texto}</u>'
    if _is_italic(span):
        texto = f'<em>{texto}</em>'
    if _is_bold(span):
        texto = f'<strong>{texto}</strong>'
    return texto


@registrar_etapa
def _join_spans(spans: list[SpanInfo]) -> tuple[str, str]:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        spans: Valor usado pela rotina para compor a operação de join spans.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    html_parts: list[str] = []
    text_parts: list[str] = []
    prev_x1: float | None = None
    for span in spans:
        texto_bruto = span.text or ''
        if not texto_bruto.strip():
            prev_x1 = span.bbox[2]
            continue
        inserir_espaco = bool(html_parts)
        if prev_x1 is not None:
            gap = span.bbox[0] - prev_x1
            if gap <= 1.5:
                inserir_espaco = False
        if inserir_espaco and not html_parts[-1].endswith((' ', '(', '“', '‘', '/', '-')) and not texto_bruto.startswith(('.', ',', ';', ':', '?', '!', ')', '”', '’')):
            html_parts.append(' ')
            text_parts.append(' ')
        html_parts.append(_span_to_html(span))
        text_parts.append(texto_bruto.strip())
        prev_x1 = span.bbox[2]
    html_text = ''.join(html_parts).strip()
    plain_text = _compact_spaces(''.join(text_parts))
    return html_text, plain_text


@registrar_etapa
def _block_bbox(block: dict[str, Any]) -> tuple[float, float, float, float]:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        block: Valor usado pela rotina para compor a operação de block bbox.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    bbox = block.get('bbox') or (0, 0, 0, 0)
    return tuple(float(v) for v in bbox)


@registrar_etapa
def _is_probable_page_number(texto: str, bbox: tuple[float, float, float, float], page_rect: fitz.Rect, max_size: float, body_font_size: float) -> bool:
    """
    Avalia uma condição específica do conteúdo recebido e devolve uma resposta simples para orientar o fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        texto: Texto bruto ou parcialmente tratado que será analisado pela função.
        bbox: Valor usado pela rotina para compor a operação de is probable page number.
        page_rect: Valor usado pela rotina para compor a operação de is probable page number.
        max_size: Valor usado pela rotina para compor a operação de is probable page number.
        body_font_size: Valor usado pela rotina para compor a operação de is probable page number.

    Retorno:
        True ou False, conforme a condição analisada seja atendida.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    texto_limpo = (texto or '').strip()
    if not texto_limpo:
        return False
    curto = len(texto_limpo) <= 8
    numero_simples = texto_limpo.isdigit() or bool(re.fullmatch(r'[ivxlcdmIVXLCDM]+', texto_limpo))
    if not (curto and numero_simples):
        return False
    y0, y1 = bbox[1], bbox[3]
    perto_topo = y1 <= page_rect.height * 0.09
    perto_base = y0 >= page_rect.height * 0.90
    return (perto_topo or perto_base) and max_size <= max(body_font_size, 10.5)


@registrar_etapa
def _merge_dropcaps(blocks: list[BlockInfo], body_font_size: float) -> list[BlockInfo]:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        blocks: Valor usado pela rotina para compor a operação de merge dropcaps.
        body_font_size: Valor usado pela rotina para compor a operação de merge dropcaps.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    if not blocks:
        return blocks
    resultado: list[BlockInfo] = []
    i = 0
    while i < len(blocks):
        atual = blocks[i]
        prox = blocks[i + 1] if i + 1 < len(blocks) else None
        pode_ser_dropcap = (
            atual.kind == 'p'
            and len((atual.text or '').strip()) == 1
            and (atual.text or '').strip().isalpha()
            and prox is not None
            and prox.kind == 'p'
        )
        if pode_ser_dropcap:
            letra = (atual.text or '').strip()
            altura_dropcap = atual.bbox[3] - atual.bbox[1]
            alinhado = atual.bbox[0] <= prox.bbox[0] and atual.bbox[1] <= prox.bbox[1] + 24
            destaque = altura_dropcap >= max(42.0, body_font_size * 3.2)
            if alinhado and destaque:
                html_combinado = f'<p><span class="dropcap">{_escape_text(letra)}</span>{prox.html[3:]}' if prox.html.startswith('<p>') else f'<p><span class="dropcap">{_escape_text(letra)}</span>{prox.html}</p>'
                texto_combinado = f'{letra}{prox.text or ""}'.strip()
                resultado.append(BlockInfo(kind='p', html=html_combinado, text=texto_combinado, level=0, bbox=(atual.bbox[0], atual.bbox[1], prox.bbox[2], max(atual.bbox[3], prox.bbox[3]))))
                i += 2
                continue
        resultado.append(atual)
        i += 1
    return resultado


@registrar_etapa
def _extract_page_blocks(page: fitz.Page, body_font_size: float, lexicon: set[str] | None = None) -> tuple[list[BlockInfo], list[bytes]]:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        page: Página do documento analisada individualmente.
        body_font_size: Valor usado pela rotina para compor a operação de extract page blocks.
        lexicon: Valor usado pela rotina para compor a operação de extract page blocks.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    data = page.get_text('dict', flags=fitz.TEXTFLAGS_DICT)
    underlines = _extract_horizontal_lines(page)
    blocks: list[tuple[float, BlockInfo]] = []
    images: list[bytes] = []
    for block in data.get('blocks', []):
        btype = block.get('type', 0)
        bbox = _block_bbox(block)
        if btype == 1:
            try:
                xref = int(block.get('xref') or 0)
            except Exception:
                xref = 0
            if xref:
                try:
                    base = page.parent.extract_image(xref)
                    if base and base.get('image'):
                        images.append(base['image'])
                except Exception:
                    pass
            continue
        if btype != 0:
            continue
        spans: list[SpanInfo] = []
        for line in block.get('lines', []):
            for span in line.get('spans', []):
                text = _correct_glued_words(span.get('text') or '', lexicon or set())
                if not text.strip():
                    continue
                span_bbox = tuple(float(v) for v in (span.get('bbox') or (0, 0, 0, 0)))
                spans.append(SpanInfo(
                    text=text,
                    size=float(span.get('size') or body_font_size or 12.0),
                    flags=int(span.get('flags') or 0),
                    font=str(span.get('font') or ''),
                    bbox=span_bbox,
                    underlined=_span_is_underlined(span_bbox, underlines),
                ))
        if not spans:
            continue
        html_text, plain_text = _join_spans(spans)
        if not plain_text:
            continue
        avg_size = statistics.mean(s.size for s in spans)
        max_size = max(s.size for s in spans)
        min_size = min(s.size for s in spans)
        words = len(plain_text.split())
        is_short = words <= MAX_WORDS_IN_HEADING
        mostly_bold = sum(1 for s in spans if _is_bold(s)) >= max(1, len(spans) * 0.6)
        all_capsish = plain_text == plain_text.upper() and any(ch.isalpha() for ch in plain_text)
        level = 0
        single_letter_dropcap = len(plain_text.strip()) == 1 and plain_text.strip().isalpha() and max_size >= max(42.0, body_font_size * 3.2)
        if single_letter_dropcap:
            level = 0
        elif max_size >= body_font_size + 5.5 and is_short:
            level = 1
        elif max_size >= body_font_size + 3.5 and is_short:
            level = 2
        elif max_size >= body_font_size + 1.8 and (is_short or mostly_bold or all_capsish):
            level = 3
        elif avg_size > body_font_size + 1.3 and min_size >= body_font_size and is_short and mostly_bold:
            level = 3
        if _is_probable_page_number(plain_text, bbox, page.rect, max_size, body_font_size):
            continue
        if _is_standalone_numeric_line(plain_text):
            continue
        tag = f'h{level}' if level else 'p'
        blocks.append((bbox[1], BlockInfo(kind=tag, html=f'<{tag}>{html_text}</{tag}>', text=plain_text, level=level, bbox=bbox)))
    blocks.sort(key=lambda item: item[0])
    ordenados = [item[1] for item in blocks]
    return _merge_dropcaps(ordenados, body_font_size), images


@registrar_etapa
def _body_font_size(doc: fitz.Document) -> float:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        doc: Documento em processamento, normalmente vindo de uma biblioteca de exportação ou leitura.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    sizes: list[float] = []
    for page_index in range(min(len(doc), 20)):
        page = doc.load_page(page_index)
        data = page.get_text('dict', flags=fitz.TEXTFLAGS_DICT)
        for block in data.get('blocks', []):
            if block.get('type', 0) != 0:
                continue
            for line in block.get('lines', []):
                for span in line.get('spans', []):
                    text = (span.get('text') or '').strip()
                    if not text or len(text) < 3:
                        continue
                    sizes.append(round(float(span.get('size') or 0), 1))
    if not sizes:
        return 12.0
    counts = Counter(sizes)
    return float(counts.most_common(1)[0][0])


@registrar_etapa
def _extract_metadata(doc: fitz.Document, pdf_path: Path) -> tuple[str, str, str]:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        doc: Documento em processamento, normalmente vindo de uma biblioteca de exportação ou leitura.
        pdf_path: Valor usado pela rotina para compor a operação de extract metadata.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    meta = doc.metadata or {}
    title = _compact_spaces(meta.get('title') or '')
    if not title or title.lower() in {'untitled', 'title', 'untitled document'}:
        title = pdf_path.stem.replace('_', ' ').replace('-', ' ').strip()
    author = _compact_spaces(meta.get('author') or '')
    if author.lower() in {'anonymous', 'unknown'}:
        author = ''
    lang = _compact_spaces(meta.get('language') or '') or 'pt-BR'
    return title, author, lang


@registrar_etapa
def _save_cover_from_first_page(doc: fitz.Document, images_dir: Path) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        doc: Documento em processamento, normalmente vindo de uma biblioteca de exportação ou leitura.
        images_dir: Valor usado pela rotina para compor a operação de save cover from first page.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    images_dir.mkdir(parents=True, exist_ok=True)
    page = doc.load_page(0)
    pix = page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), alpha=False)
    image = Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB')
    output = images_dir / 'cover.jpg'
    image.save(output, format='JPEG', quality=90, optimize=True)
    return f'images/{output.name}'


@registrar_etapa
def _page_image_bytes(page: fitz.Page) -> bytes:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        page: Página do documento analisada individualmente.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    pix = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4), alpha=False)
    return pix.tobytes('jpeg', jpg_quality=82)


@registrar_etapa
def _build_cover_page(title: str, cover_href: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        title: Valor usado pela rotina para compor a operação de build cover page.
        cover_href: Valor usado pela rotina para compor a operação de build cover page.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en">
  <head>
    <title>{xml_escape(title)}</title>
    <link rel="stylesheet" type="text/css" href="styles/book.css"/>
  </head>
  <body>
    <section class="cover-page">
      <img src="{xml_escape(cover_href)}" alt="{xml_escape(title)}"/>
    </section>
  </body>
</html>
'''


@registrar_etapa
def _build_nav(title: str, chapter_items: list[dict[str, str]]) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        title: Valor usado pela rotina para compor a operação de build nav.
        chapter_items: Valor usado pela rotina para compor a operação de build nav.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    nav_items = '\n'.join(f'      <li><a href="{xml_escape(item["href"])}">{xml_escape(item["title"])}</a></li>' for item in chapter_items)
    return f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="en">
  <head>
    <title>{xml_escape(title)}</title>
    <link rel="stylesheet" type="text/css" href="styles/book.css"/>
  </head>
  <body>
    <nav epub:type="toc" id="toc">
      <h1>{xml_escape(title)}</h1>
      <ol>
{nav_items}
      </ol>
    </nav>
  </body>
</html>
'''


@registrar_etapa
def _build_container_xml() -> str:
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
    return '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
'''


@registrar_etapa
def _build_content_opf(identifier: str, title: str, author: str, language: str, chapter_items: list[dict[str, str]], image_items: list[dict[str, str]], cover_href: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        identifier: Valor usado pela rotina para compor a operação de build content opf.
        title: Valor usado pela rotina para compor a operação de build content opf.
        author: Valor usado pela rotina para compor a operação de build content opf.
        language: Valor usado pela rotina para compor a operação de build content opf.
        chapter_items: Valor usado pela rotina para compor a operação de build content opf.
        image_items: Valor usado pela rotina para compor a operação de build content opf.
        cover_href: Valor usado pela rotina para compor a operação de build content opf.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    manifest_parts = [
        '    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '    <item id="css" href="styles/book.css" media-type="text/css"/>',
        f'    <item id="cover-image" href="{xml_escape(cover_href)}" media-type="image/jpeg" properties="cover-image"/>',
        '    <item id="cover-page" href="cover.xhtml" media-type="application/xhtml+xml"/>',
    ]
    spine_parts = []
    for index, item in enumerate(chapter_items, start=1):
        manifest_parts.append(f'    <item id="chap{index}" href="{xml_escape(item["href"])}" media-type="application/xhtml+xml"/>')
        spine_parts.append(f'    <itemref idref="chap{index}"/>')
    for idx, img in enumerate(image_items, start=1):
        manifest_parts.append(f'    <item id="img{idx}" href="{xml_escape(img["href"])}" media-type="{xml_escape(img["media_type"])}"/>')
    modified = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    author_meta = f'    <dc:creator>{xml_escape(author)}</dc:creator>\n' if author else ''
    return f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" prefix="rendition: http://www.idpf.org/vocab/rendition/#">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">urn:uuid:{xml_escape(identifier)}</dc:identifier>
    <dc:title>{xml_escape(title)}</dc:title>
{author_meta}    <dc:language>{xml_escape(language or 'pt-BR')}</dc:language>
    <meta property="dcterms:modified">{modified}</meta>
  </metadata>
  <manifest>
{chr(10).join(manifest_parts)}
  </manifest>
  <spine>
{chr(10).join(spine_parts)}
  </spine>
</package>
'''


@registrar_etapa
def _chapter_title_from_blocks(page_number: int, blocks: list[BlockInfo]) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        page_number: Valor usado pela rotina para compor a operação de chapter title from blocks.
        blocks: Valor usado pela rotina para compor a operação de chapter title from blocks.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    for block in blocks:
        if block.kind in {'h1', 'h2', 'h3'} and block.text:
            return block.text[:120]
    return f'Página {page_number}'


@registrar_etapa
def _chapter_xhtml(title: str, body_html: str, lang: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        title: Valor usado pela rotina para compor a operação de chapter xhtml.
        body_html: Valor usado pela rotina para compor a operação de chapter xhtml.
        lang: Valor usado pela rotina para compor a operação de chapter xhtml.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return f'''<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{xml_escape(lang or 'pt-BR')}">
  <head>
    <title>{xml_escape(title)}</title>
    <link rel="stylesheet" type="text/css" href="../styles/book.css"/>
  </head>
  <body>
{body_html}
  </body>
</html>
'''


@registrar_etapa
def converter_pdf_para_epub3(pdf_path: Path, epub_destino: Path) -> dict[str, Any]:
    """
    Transforma conteúdo de um formato para outro preservando o máximo possível da estrutura original.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pdf_path: Valor usado pela rotina para compor a operação de converter pdf para epub3.
        epub_destino: Valor usado pela rotina para compor a operação de converter pdf para epub3.

    Retorno:
        Informações sobre o arquivo convertido e os elementos gerados no processo.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    pdf_path = Path(pdf_path)
    epub_destino = Path(epub_destino)
    epub_destino.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    base_dir: Path | None = None
    try:
        title, author, language = _extract_metadata(doc, pdf_path)
        identifier = str(uuid.uuid4())
        base_dir = epub_destino.parent / f'.tmp_pdf_epub_{uuid.uuid4().hex}'
        oebps = base_dir / 'OEBPS'
        text_dir = oebps / 'text'
        images_dir = oebps / 'images'
        styles_dir = oebps / 'styles'
        meta_inf = base_dir / 'META-INF'
        text_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)
        styles_dir.mkdir(parents=True, exist_ok=True)
        meta_inf.mkdir(parents=True, exist_ok=True)

        cover_href = _save_cover_from_first_page(doc, images_dir)
        (styles_dir / 'book.css').write_text(CSS_EPUB, encoding='utf-8')
        (meta_inf / 'container.xml').write_text(_build_container_xml(), encoding='utf-8')

        body_size = _body_font_size(doc)
        lexicon = _collect_pdf_lexicon(doc)
        chapter_items: list[dict[str, str]] = []
        image_items: list[dict[str, str]] = [{'href': cover_href, 'media_type': 'image/jpeg'}]
        current_parts: list[str] = []
        current_title = title
        current_page_start = 1
        chapter_index = 1
        page_images_written = 0
        top_heading_seen = False

        @registrar_etapa
        def flush_current(force: bool = False):
            """
            Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
        
            A função isola esta responsabilidade para deixar o fluxo principal mais fácil
            de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
            normalizações ou verificações necessárias e entrega um resultado previsível
            para a próxima camada do sistema.
        
            Parâmetros:
                force: Valor usado pela rotina para compor a operação de flush current.
        
            Retorno:
                O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
        
            Observações:
                Mantém a lógica centralizada e evita que detalhes de implementação vazem
                para quem apenas precisa acionar este comportamento.
            """
            nonlocal current_parts, current_title, current_page_start, chapter_index
            content = ''.join(current_parts).strip()
            if not content and not force:
                return
            href = f'text/chapter_{chapter_index:04d}.xhtml'
            xhtml = _chapter_xhtml(current_title or f'Capítulo {chapter_index}', content or '<p></p>', language)
            (oebps / href).write_text(xhtml, encoding='utf-8')
            chapter_items.append({'href': href, 'title': current_title or f'Capítulo {chapter_index}'})
            chapter_index += 1
            current_parts = []

        for page_number in range(doc.page_count):
            page = doc.load_page(page_number)
            blocks, page_images = _extract_page_blocks(page, body_size, lexicon)
            if page_images:
                for img_bytes in page_images:
                    page_images_written += 1
                    img_name = f'page_asset_{page_number+1:04d}_{page_images_written:03d}.jpg'
                    img_path = images_dir / img_name
                    try:
                        Image.open(io.BytesIO(img_bytes)).convert('RGB').save(img_path, format='JPEG', quality=88, optimize=True)
                        image_items.append({'href': f'images/{img_name}', 'media_type': 'image/jpeg'})
                        current_parts.append(f'<figure class="image-block"><img class="pdf-page-image" src="../images/{xml_escape(img_name)}" alt="Imagem da página {page_number+1}"/></figure>')
                    except Exception:
                        continue
            meaningful_blocks = [b for b in blocks if b.text.strip()]
            if not meaningful_blocks:
                fallback_name = f'page_render_{page_number+1:04d}.jpg'
                (images_dir / fallback_name).write_bytes(_page_image_bytes(page))
                image_items.append({'href': f'images/{fallback_name}', 'media_type': 'image/jpeg'})
                page_title = f'Página {page_number+1}'
                flush_current(force=False)
                current_title = page_title
                current_parts = [f'<section class="page-break"><figure class="image-block"><img class="pdf-page-image" src="../images/{xml_escape(fallback_name)}" alt="{xml_escape(page_title)}"/></figure></section>']
                flush_current(force=True)
                current_title = title
                current_page_start = page_number + 2
                continue

            page_title = _chapter_title_from_blocks(page_number + 1, meaningful_blocks)
            top_heading = next((b for b in meaningful_blocks if b.kind == 'h1'), None)
            should_split = False
            if top_heading and top_heading_seen:
                should_split = True
            elif page_number > 0 and ((page_number + 1 - current_page_start) >= 12):
                should_split = True
            elif page_number > 0 and current_parts and page_title != current_title and any(b.kind == 'h1' for b in meaningful_blocks):
                should_split = True
            if should_split:
                flush_current(force=False)
                current_page_start = page_number + 1
                current_title = page_title
            elif not current_parts:
                current_title = page_title or title
                current_page_start = page_number + 1
            if top_heading:
                top_heading_seen = True
            current_parts.append(f'<section class="page-break" id="page-{page_number+1}">')
            for block in meaningful_blocks:
                current_parts.append(block.html)
            current_parts.append('</section>')

        flush_current(force=False)
        if not chapter_items:
            href = 'text/chapter_0001.xhtml'
            (oebps / href).write_text(_chapter_xhtml(title, '<p></p>', language), encoding='utf-8')
            chapter_items.append({'href': href, 'title': title})

        (oebps / 'cover.xhtml').write_text(_build_cover_page(title, cover_href), encoding='utf-8')
        (oebps / 'nav.xhtml').write_text(_build_nav(title, chapter_items), encoding='utf-8')
        (oebps / 'content.opf').write_text(_build_content_opf(identifier, title, author, language, chapter_items, image_items, cover_href), encoding='utf-8')

        with zipfile.ZipFile(epub_destino, 'w') as epub_zip:
            epub_zip.writestr('mimetype', EPUB_MIMETYPE, compress_type=zipfile.ZIP_STORED)
            for file_path in sorted(base_dir.rglob('*')):
                if file_path.is_file():
                    epub_zip.write(file_path, file_path.relative_to(base_dir).as_posix(), compress_type=zipfile.ZIP_DEFLATED)

        return {
            'titulo': title,
            'autor': author,
            'idioma': language,
            'paginas': doc.page_count,
            'arquivo_epub': str(epub_destino),
        }
    finally:
        doc.close()
        # limpeza defensiva
        try:
            import shutil
            if base_dir is not None:
                shutil.rmtree(base_dir, ignore_errors=True)
        except Exception:
            pass
