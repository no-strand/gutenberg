"""Exportação dos recursos de projeto em PDF."""
from __future__ import annotations

import base64
import html
import io
from datetime import datetime
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .i18n import t
from .logging_config import obter_logger, registrar_etapa
from .manipulador_projetos import obter_pasta_projeto, obter_projeto
from .manipulador_recursos_projeto import ler_recursos_projeto
from .utilidades import nome_seguro, obter_pasta_exportacao_projeto

logger = obter_logger(__name__)


@registrar_etapa
def _texto(valor: Any, limite: int = 2000) -> str:
    return str(valor or "").replace("\x00", "").strip()[:limite]


@registrar_etapa
def _esc(valor: Any) -> str:
    return html.escape(_texto(valor, 12000)).replace("\n", "<br/>")


@registrar_etapa
def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "GutenbergRecursosTitulo",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "subtitulo": ParagraphStyle(
            "GutenbergRecursosSubtitulo",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#5b6472"),
            spaceAfter=18,
        ),
        "secao": ParagraphStyle(
            "GutenbergRecursosSecao",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            spaceBefore=12,
            spaceAfter=8,
            textColor=colors.HexColor("#202734"),
        ),
        "aba": ParagraphStyle(
            "GutenbergRecursosAba",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            spaceBefore=8,
            spaceAfter=5,
            textColor=colors.HexColor("#374151"),
        ),
        "item": ParagraphStyle(
            "GutenbergRecursosItem",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            spaceBefore=5,
            spaceAfter=3,
            textColor=colors.HexColor("#111827"),
        ),
        "normal": ParagraphStyle(
            "GutenbergRecursosNormal",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            spaceAfter=5,
        ),
        "vazio": ParagraphStyle(
            "GutenbergRecursosVazio",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#6b7280"),
            spaceAfter=6,
        ),
        "pequeno": ParagraphStyle(
            "GutenbergRecursosPequeno",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#4b5563"),
        ),
    }


@registrar_etapa
def _html_para_flowables(fragmento: str, styles: dict[str, ParagraphStyle]) -> list[Any]:
    soup = BeautifulSoup(fragmento or "", "html.parser")
    elementos: list[Any] = []
    blocos = soup.find_all(["h1", "h2", "h3", "p", "li", "blockquote"], recursive=True)
    if not blocos:
        texto = soup.get_text(" ", strip=True)
        if texto:
            return [Paragraph(_esc(texto), styles["normal"])]
        return [Paragraph(t("resources.no_content", default="Sem conteúdo."), styles["vazio"])]
    for bloco in blocos:
        texto = bloco.get_text(" ", strip=True)
        if not texto:
            continue
        if bloco.name in {"h1", "h2", "h3"}:
            estilo = styles["aba"] if bloco.name == "h1" else styles["item"]
            elementos.append(Paragraph(_esc(texto), estilo))
        elif bloco.name == "li":
            elementos.append(Paragraph(f"• {_esc(texto)}", styles["normal"]))
        else:
            elementos.append(Paragraph(_esc(texto), styles["normal"]))
    return elementos or [Paragraph(t("resources.no_content", default="Sem conteúdo."), styles["vazio"])]


@registrar_etapa
def _imagem_data_url(data_url: str, largura_max: float = 3.2 * cm, altura_max: float = 4.0 * cm) -> RLImage | None:
    texto = str(data_url or "").strip()
    if not texto.startswith("data:image/") or "," not in texto:
        return None
    try:
        bruto = base64.b64decode(texto.split(",", 1)[1], validate=False)
        imagem_pil = Image.open(io.BytesIO(bruto))
        imagem_pil.thumbnail((900, 900))
        saida = io.BytesIO()
        if imagem_pil.mode not in {"RGB", "L"}:
            imagem_pil = imagem_pil.convert("RGB")
        imagem_pil.save(saida, format="JPEG", quality=86)
        saida.seek(0)
        largura, altura = imagem_pil.size
        escala = min(largura_max / max(1, largura), altura_max / max(1, altura), 1)
        return RLImage(saida, width=largura * escala, height=altura * escala)
    except Exception:
        logger.debug("Imagem de recurso ignorada na exportação PDF", exc_info=True)
        return None


@registrar_etapa
def _adicionar_titulo_secao(story: list[Any], styles: dict[str, ParagraphStyle], titulo: str) -> None:
    story.append(Spacer(1, 4))
    story.append(Paragraph(_esc(titulo), styles["secao"]))


@registrar_etapa
def _exportar_informacoes(story: list[Any], recursos: dict[str, Any], styles: dict[str, ParagraphStyle]) -> None:
    _adicionar_titulo_secao(story, styles, t("resources.info", default="Informações"))
    abas = recursos.get("informacoes_abas") if isinstance(recursos.get("informacoes_abas"), list) else []
    if not abas:
        story.append(Paragraph(t("resources.no_info", default="Nenhuma informação cadastrada."), styles["vazio"]))
        return
    for aba in abas:
        story.append(Paragraph(_esc(aba.get("titulo") or t("resources.untitled", default="Sem título")), styles["aba"]))
        paginas = aba.get("paginas") if isinstance(aba.get("paginas"), list) else []
        for pagina in paginas:
            story.append(Paragraph(_esc(pagina.get("titulo") or t("resources.untitled", default="Sem título")), styles["item"]))
            story.extend(_html_para_flowables(str(pagina.get("html") or ""), styles))


@registrar_etapa
def _exportar_fluxos(story: list[Any], recursos: dict[str, Any], styles: dict[str, ParagraphStyle]) -> None:
    _adicionar_titulo_secao(story, styles, t("resources.flow", default="Fluxo"))
    fluxos = recursos.get("fluxos") if isinstance(recursos.get("fluxos"), list) else []
    if not fluxos:
        story.append(Paragraph(t("resources.no_flow_nodes", default="Nenhum balão no fluxo ainda."), styles["vazio"]))
        return
    for fluxo in fluxos:
        story.append(Paragraph(_esc(fluxo.get("titulo") or t("resources.flow", default="Fluxo")), styles["aba"]))
        nodes = fluxo.get("nodes") if isinstance(fluxo.get("nodes"), list) else []
        edges = fluxo.get("edges") if isinstance(fluxo.get("edges"), list) else []
        if not nodes:
            story.append(Paragraph(t("resources.no_flow_nodes", default="Nenhum balão no fluxo ainda."), styles["vazio"]))
            continue
        por_id = {str(node.get("id") or ""): node for node in nodes}
        for node in nodes:
            titulo = node.get("titulo") or t("resources.balloon", default="Balão")
            story.append(Paragraph(_esc(titulo), styles["item"]))
            texto = _texto(node.get("texto"), 4000)
            story.append(Paragraph(_esc(texto) if texto else t("resources.no_content", default="Sem conteúdo."), styles["normal" if texto else "vazio"]))
        if edges:
            conexoes = []
            for edge in edges:
                origem = por_id.get(str(edge.get("from") or ""), {})
                destino = por_id.get(str(edge.get("to") or ""), {})
                conexoes.append(f"• {_texto(origem.get('titulo') or edge.get('from'), 120)} → {_texto(destino.get('titulo') or edge.get('to'), 120)}")
            story.append(Paragraph(_esc("\n".join(conexoes)), styles["pequeno"]))


@registrar_etapa
def _agrupar_por_pagina(recursos: dict[str, Any], tipo: str) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    paginas = recursos.get(f"{tipo}_paginas") if isinstance(recursos.get(f"{tipo}_paginas"), list) else []
    itens = recursos.get(tipo) if isinstance(recursos.get(tipo), list) else []
    if not paginas:
        paginas = [{"id": "", "titulo": t("resources.default_page_title", default="Página inicial")}]
    agrupado = []
    for pagina in paginas:
        pid = str(pagina.get("id") or "")
        agrupado.append((pagina, [item for item in itens if str(item.get("pagina_id") or "") == pid]))
    extras = [item for item in itens if not any(str(item.get("pagina_id") or "") == str(p.get("id") or "") for p in paginas)]
    if extras:
        agrupado.append(({"id": "extras", "titulo": t("resources.untitled", default="Sem título")}, extras))
    return agrupado


@registrar_etapa
def _exportar_catalogo(story: list[Any], recursos: dict[str, Any], styles: dict[str, ParagraphStyle], tipo: str, titulo_secao: str) -> None:
    _adicionar_titulo_secao(story, styles, titulo_secao)
    grupos = _agrupar_por_pagina(recursos, tipo)
    tem_itens = any(itens for _, itens in grupos)
    if not tem_itens:
        story.append(Paragraph(t("resources.no_items", default="Nenhum item cadastrado ainda."), styles["vazio"]))
        return
    for pagina, itens in grupos:
        if not itens:
            continue
        story.append(Paragraph(_esc(pagina.get("titulo") or t("resources.untitled", default="Sem título")), styles["aba"]))
        for item in itens:
            titulo = Paragraph(_esc(item.get("nome") or t("resources.no_item_name", default="Sem nome")), styles["item"])
            descricao = Paragraph(_esc(item.get("descricao") or t("resources.no_description", default="Sem descrição.")), styles["normal"])
            imagem = _imagem_data_url(str(item.get("imagem") or "")) if tipo != "anotacoes" else None
            if imagem:
                tabela = Table([[imagem, [titulo, descricao]]], colWidths=[3.5 * cm, 12.2 * cm])
                tabela.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#d1d5db")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]))
                story.append(tabela)
                story.append(Spacer(1, 6))
            else:
                story.append(titulo)
                story.append(descricao)


@registrar_etapa
def exportar_recursos_pdf(slug: str) -> Path:
    """Exporta recursos do projeto em um PDF organizado por tipo."""
    projeto = obter_projeto(slug)
    if not projeto:
        raise FileNotFoundError(t("backend.project_not_found", default="Projeto não encontrado."))
    pasta_projeto = obter_pasta_projeto(slug)
    recursos = ler_recursos_projeto(pasta_projeto)
    pasta_saida = obter_pasta_exportacao_projeto(slug)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    nome = f"{nome_seguro(projeto.get('titulo') or slug)}_recursos.pdf"
    caminho = pasta_saida / nome

    styles = _styles()
    doc = SimpleDocTemplate(
        str(caminho),
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.7 * cm,
        bottomMargin=1.7 * cm,
        title=f"{t('resources.project_resources', default='Recursos do projeto')} - {projeto.get('titulo') or slug}",
        author="Gutenberg",
    )
    story: list[Any] = []
    story.append(Paragraph(_esc(f"{t('resources.project_resources', default='Recursos do projeto')} - {projeto.get('titulo') or slug}"), styles["titulo"]))
    story.append(Paragraph(_esc(datetime.now().strftime("%d/%m/%Y %H:%M")), styles["subtitulo"]))

    _exportar_informacoes(story, recursos, styles)
    story.append(PageBreak())
    _exportar_fluxos(story, recursos, styles)
    story.append(PageBreak())
    _exportar_catalogo(story, recursos, styles, "personagens", t("resources.characters", default="Personagens"))
    _exportar_catalogo(story, recursos, styles, "lugares", t("resources.places", default="Lugares"))
    _exportar_catalogo(story, recursos, styles, "anotacoes", t("resources.notes", default="Anotações"))

    doc.build(story)
    return caminho
