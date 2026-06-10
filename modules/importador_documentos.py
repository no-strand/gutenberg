"""Importação de capítulos e roteiros a partir de DOCX, PDF e TXT."""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

import fitz
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from .manipulador_capitulos import criar_capitulo, salvar_capitulo
from .manipulador_projetos import atualizar_metadados_projeto, obter_pasta_projeto, obter_projeto
from .manipulador_roteiros import criar_roteiro, salvar_roteiro, atualizar_roteiro_info
from .logging_config import obter_logger, registrar_etapa
logger = obter_logger(__name__)

EXTENSOES_DOCUMENTO_IMPORTAVEL = {".docx", ".pdf", ".txt"}


@registrar_etapa
def extensao_documento_importavel(caminho: str | Path) -> bool:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        caminho: Caminho de arquivo ou pasta usado como origem ou destino da operação.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return Path(caminho).suffix.lower() in EXTENSOES_DOCUMENTO_IMPORTAVEL


@registrar_etapa
def _limpar_linha(texto: Any) -> str:
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
    texto = str(texto or "").replace("\u00a0", " ")
    return re.sub(r"[ \t]+", " ", texto).strip()


@registrar_etapa
def _linha_vazia(linha: dict[str, Any]) -> bool:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        linha: Valor usado pela rotina para compor a operação de linha vazia.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return not _limpar_linha(linha.get("text"))


@registrar_etapa
def _eh_titulo_capitulo(linha: dict[str, Any], anterior_vazia: bool = True, proxima_vazia: bool = True) -> bool:
    """
    Avalia uma condição específica do conteúdo recebido e devolve uma resposta simples para orientar o fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        linha: Valor usado pela rotina para compor a operação de eh titulo capitulo.
        anterior_vazia: Valor usado pela rotina para compor a operação de eh titulo capitulo.
        proxima_vazia: Valor usado pela rotina para compor a operação de eh titulo capitulo.

    Retorno:
        True ou False, conforme a condição analisada seja atendida.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    texto = _limpar_linha(linha.get("text"))
    if not texto:
        return False
    if linha.get("is_heading"):
        return True
    palavras = texto.split()
    if len(palavras) > 16 or len(texto) > 120:
        return False
    if re.search(r"[.!?;:]$", texto) and not re.match(r"^(cap[ií]tulo|chapter|parte|part|pr[oó]logo|ep[ií]logo)\b", texto, flags=re.I):
        return False
    align = linha.get("align") or "left"
    bold = bool(linha.get("bold"))
    tamanho = float(linha.get("font_size") or 0.0)
    tamanho_base = float(linha.get("base_font_size") or 0.0)
    parece_rotulo = bool(re.match(r"^(cap[ií]tulo|chapter|parte|part|livro|book|pr[oó]logo|prologue|ep[ií]logo|epilogue)\b", texto, flags=re.I))
    destaque_tamanho = tamanho_base and tamanho >= tamanho_base + 1.5
    curto_isolado = anterior_vazia and proxima_vazia and len(palavras) <= 10
    caixa_alta = _eh_maiusculo_relevante(texto) and len(palavras) <= 12
    title_case = sum(1 for w in palavras if w[:1].isupper()) >= max(1, len(palavras) // 2)
    return bool(parece_rotulo or (curto_isolado and (bold or align == "center" or caixa_alta or title_case or destaque_tamanho)) or (destaque_tamanho and len(palavras) <= 14))


@registrar_etapa
def _texto_para_html_capitulo(texto: str) -> str:
    """
    Converte a estrutura recebida para uma representação adequada ao próximo estágio do processamento.

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
    linhas = [{"text": linha.rstrip(), "align": "left", "bold": False} for linha in texto.splitlines()]
    return _linhas_para_html_capitulo(linhas)


@registrar_etapa
def _linhas_para_html_capitulo(linhas: list[dict[str, Any]]) -> str:
    """
    Converte a estrutura recebida para uma representação adequada ao próximo estágio do processamento.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        linhas: Linhas já extraídas de um documento e enriquecidas com metadados básicos.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    tamanhos = [float(l.get("font_size") or 0.0) for l in linhas if _limpar_linha(l.get("text")) and float(l.get("font_size") or 0.0) > 0]
    if tamanhos:
        base = sorted(tamanhos)[len(tamanhos) // 2]
        for l in linhas:
            l.setdefault("base_font_size", base)

    partes: list[str] = []
    paragrafo_atual: list[str] = []

    @registrar_etapa
    def fechar_paragrafo() -> None:
        """
        Encerra um fluxo ou recurso de maneira controlada.
    
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
        nonlocal paragrafo_atual
        conteudo = " ".join(paragrafo_atual).strip()
        if conteudo:
            partes.append(f"<p>{html.escape(conteudo)}</p>")
        paragrafo_atual = []

    total = len(linhas)
    for idx, linha in enumerate(linhas):
        texto = _limpar_linha(linha.get("text"))
        anterior_vazia = idx == 0 or _linha_vazia(linhas[idx - 1])
        proxima_vazia = idx == total - 1 or _linha_vazia(linhas[idx + 1])
        if not texto:
            fechar_paragrafo()
            continue
        if _eh_titulo_capitulo(linha, anterior_vazia, proxima_vazia):
            fechar_paragrafo()
            partes.append(f"<h1>{html.escape(texto)}</h1>")
        else:
            paragrafo_atual.append(texto)
            if linha.get("paragraph_end"):
                fechar_paragrafo()
    fechar_paragrafo()
    return "".join(partes) or "<p><br></p>"

@registrar_etapa
def _extrair_txt(caminho: Path) -> list[dict[str, Any]]:
    """
    Extrai informações de uma origem específica e devolve uma representação mais simples para as próximas etapas do fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        caminho: Caminho de arquivo ou pasta usado como origem ou destino da operação.

    Retorno:
        Dados extraídos em uma estrutura simplificada, adequada para as próximas etapas.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    bruto = caminho.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            texto = bruto.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        texto = bruto.decode("utf-8", errors="ignore")
    return [{"text": linha.rstrip(), "align": "left", "x0": 0.0, "x1": 0.0, "page_width": 612.0, "bold": False} for linha in texto.splitlines()]


@registrar_etapa
def _extrair_docx(caminho: Path) -> list[dict[str, Any]]:
    """
    Extrai informações de uma origem específica e devolve uma representação mais simples para as próximas etapas do fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        caminho: Caminho de arquivo ou pasta usado como origem ou destino da operação.

    Retorno:
        Dados extraídos em uma estrutura simplificada, adequada para as próximas etapas.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    doc = Document(str(caminho))
    linhas: list[dict[str, Any]] = []
    for p in doc.paragraphs:
        texto = p.text.rstrip()
        align = "left"
        if p.alignment == WD_ALIGN_PARAGRAPH.CENTER:
            align = "center"
        elif p.alignment == WD_ALIGN_PARAGRAPH.RIGHT:
            align = "right"
        bold_runs = [r for r in p.runs if (r.text or "").strip()]
        bold = bool(bold_runs) and sum(1 for r in bold_runs if r.bold) >= max(1, len(bold_runs) // 2)
        sizes = [float(r.font.size.pt) for r in bold_runs if r.font.size]
        font_size = max(sizes) if sizes else 0.0
        style_name = str(getattr(getattr(p, "style", None), "name", "") or "")
        is_heading = bool(re.search(r"heading|t[ií]tulo|title", style_name, flags=re.I))
        left_indent = float(p.paragraph_format.left_indent.pt) if p.paragraph_format.left_indent else 0.0
        first_indent = float(p.paragraph_format.first_line_indent.pt) if p.paragraph_format.first_line_indent else 0.0
        linhas.append({"text": texto, "align": align, "x0": left_indent + max(0.0, first_indent), "x1": 0.0, "page_width": 612.0, "bold": bold, "font_size": font_size, "style": style_name, "is_heading": is_heading, "paragraph_end": True})
    return linhas

@registrar_etapa
def _extrair_pdf(caminho: Path) -> list[dict[str, Any]]:
    """
    Extrai informações de uma origem específica e devolve uma representação mais simples para as próximas etapas do fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        caminho: Caminho de arquivo ou pasta usado como origem ou destino da operação.

    Retorno:
        Dados extraídos em uma estrutura simplificada, adequada para as próximas etapas.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    linhas: list[dict[str, Any]] = []
    with fitz.open(str(caminho)) as doc:
        for page in doc:
            width = float(page.rect.width or 612.0)
            data = page.get_text("dict")
            for block_idx, block in enumerate(data.get("blocks", [])):
                if block.get("type") != 0:
                    continue
                block_lines = block.get("lines", [])
                for line_idx, line in enumerate(block_lines):
                    spans = line.get("spans", [])
                    texto = "".join(span.get("text", "") for span in spans).rstrip()
                    if not texto and spans:
                        linhas.append({"text": "", "align": "left", "x0": 0.0, "x1": 0.0, "page_width": width, "bold": False, "block_id": block_idx, "paragraph_end": line_idx == len(block_lines) - 1})
                        continue
                    bbox = line.get("bbox") or [0, 0, 0, 0]
                    x0, x1 = float(bbox[0]), float(bbox[2])
                    centro = (x0 + x1) / 2.0
                    if abs(centro - width / 2.0) <= width * 0.10:
                        align = "center"
                    elif x0 > width * 0.55:
                        align = "right"
                    else:
                        align = "left"
                    bold = any("bold" in str(span.get("font", "")).lower() for span in spans)
                    font_size = max([float(span.get("size") or 0.0) for span in spans] or [0.0])
                    linhas.append({"text": texto, "align": align, "x0": x0, "x1": x1, "page_width": width, "bold": bold, "font_size": font_size, "block_id": block_idx, "paragraph_end": line_idx == len(block_lines) - 1})
    return linhas


@registrar_etapa
def extrair_linhas_documento(caminho: str | Path) -> list[dict[str, Any]]:
    """
    Extrai informações de uma origem específica e devolve uma representação mais simples para as próximas etapas do fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        caminho: Caminho de arquivo ou pasta usado como origem ou destino da operação.

    Retorno:
        Dados extraídos em uma estrutura simplificada, adequada para as próximas etapas.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    caminho = Path(caminho)
    ext = caminho.suffix.lower()
    if ext == ".txt":
        return _extrair_txt(caminho)
    if ext == ".docx":
        return _extrair_docx(caminho)
    if ext == ".pdf":
        return _extrair_pdf(caminho)
    raise ValueError("Formato não suportado para importação.")


@registrar_etapa
def extrair_texto_documento(caminho: str | Path) -> str:
    """
    Extrai informações de uma origem específica e devolve uma representação mais simples para as próximas etapas do fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        caminho: Caminho de arquivo ou pasta usado como origem ou destino da operação.

    Retorno:
        Dados extraídos em uma estrutura simplificada, adequada para as próximas etapas.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    linhas = extrair_linhas_documento(caminho)
    return "\n".join(str(l.get("text") or "").rstrip() for l in linhas).strip()


@registrar_etapa
def importar_documento_como_capitulo(slug: str, caminho: str | Path) -> dict[str, Any]:
    """
    Coordena a importação de conteúdo externo para dentro do projeto, normalizando os dados para o modelo usado pela aplicação.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        caminho: Caminho de arquivo ou pasta usado como origem ou destino da operação.

    Retorno:
        Um resumo do conteúdo importado e dos registros criados no projeto.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    caminho = Path(caminho)
    projeto = obter_projeto(slug)
    if projeto.get("tipo") != "livro":
        raise ValueError("Este documento só pode ser importado como capítulo em projetos de livro.")
    linhas = extrair_linhas_documento(caminho)
    pasta = obter_pasta_projeto(slug)
    titulo_capitulo = caminho.stem[:70] or "Capítulo importado"
    cap = criar_capitulo(pasta, titulo_capitulo)
    cap = salvar_capitulo(pasta, int(cap["id"]), titulo_capitulo, _linhas_para_html_capitulo(linhas))
    atualizar_metadados_projeto(slug, {})
    return {"ok": True, "redirect": f"/projetos/{slug}/capitulos/{cap['id']}/editar", "capitulos_importados": 1, "roteiro_importado": None}


@registrar_etapa
def _eh_maiusculo_relevante(texto: str) -> bool:
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
    letras = re.findall(r"[A-Za-zÀ-ÿ]", texto)
    if len(letras) < 2:
        return False
    maiusculas = re.findall(r"[A-ZÀ-Ý]", texto)
    return len(maiusculas) / max(1, len(letras)) >= 0.82


@registrar_etapa
def _classificar_linha_roteiro(linha: dict[str, Any], anterior: str = "") -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        linha: Valor usado pela rotina para compor a operação de classificar linha roteiro.
        anterior: Valor usado pela rotina para compor a operação de classificar linha roteiro.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    texto = _limpar_linha(linha.get("text"))
    if not texto:
        return "blank"
    upper = texto.upper()
    align = linha.get("align") or "left"
    x0 = float(linha.get("x0") or 0.0)
    width = float(linha.get("page_width") or 612.0)

    if re.match(r"^(?:\d+\s+)?(?:INT|EXT|INT\./EXT|INT/EXT|I/E|EST|INT\.?/EXT\.?)\.?", upper):
        return "scene_heading"
    if upper.endswith("TO:") or upper in {"FADE IN:", "FADE OUT:", "CUT TO:", "DISSOLVE TO:"}:
        return "transition"
    if texto.startswith("(") and texto.endswith(")") and len(texto) <= 90:
        return "parenthetical"
    if (align == "center" or x0 > width * 0.30) and _eh_maiusculo_relevante(texto) and len(texto) <= 45 and not re.search(r"[.!?]$", texto):
        return "character"
    if anterior == "character" or anterior == "parenthetical":
        return "dialogue"
    if anterior == "dialogue" and (align == "center" or x0 > width * 0.18):
        return "dialogue"
    if _eh_maiusculo_relevante(texto) and len(texto) <= 55 and re.search(r"SHOT|ANGLE|CLOSE|PAN|TRAVELLING|PLANO|CÂMERA|CAMERA", upper):
        return "shot"
    if align == "left":
        return "action"
    return "neutral"


@registrar_etapa
def _bloco_roteiro_html(tipo: str, texto: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        tipo: Valor usado pela rotina para compor a operação de bloco roteiro html.
        texto: Texto bruto ou parcialmente tratado que será analisado pela função.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    if tipo == "blank":
        return ""
    tipo = tipo if tipo in {"scene_heading", "action", "character", "dialogue", "parenthetical", "shot", "transition", "music", "comment", "neutral"} else "neutral"
    extra = ' data-initial-neutral="true"' if tipo == "neutral" else ""
    conteudo = html.escape(_limpar_linha(texto)) or "<br>"
    return f'<div class="roteiro-bloco" data-block-type="{tipo}"{extra}>{conteudo}</div>'


@registrar_etapa
def _metadados_de_capa(linhas: list[dict[str, Any]], nome_arquivo: str) -> dict[str, str]:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        linhas: Linhas já extraídas de um documento e enriquecidas com metadados básicos.
        nome_arquivo: Valor usado pela rotina para compor a operação de metadados de capa.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    inicio = [_limpar_linha(l.get("text")) for l in linhas[:80] if _limpar_linha(l.get("text"))]
    texto_inicio = "\n".join(inicio)
    meta = {"titulo": "", "autor": "", "logline": "", "sinopse": "", "contatos": "", "genero": ""}
    for i, linha in enumerate(inicio[:30]):
        low = linha.lower()
        if not meta["autor"] and re.match(r"^(por|by)\s+", low):
            meta["autor"] = re.sub(r"^(por|by)\s+", "", linha, flags=re.I).strip()
        if not meta["contatos"] and ("@" in linha or re.search(r"\+?\d[\d\s().-]{7,}", linha)):
            meta["contatos"] = linha
        if not meta["titulo"] and i < 12 and len(linha) <= 80 and _eh_maiusculo_relevante(linha) and not re.match(r"^(por|by)\b", low):
            meta["titulo"] = linha
    rotulos = {
        "logline": r"(?:logline|linha\s+dram[aá]tica)",
        "sinopse": r"(?:sinopse|synopsis)",
        "genero": r"(?:g[eê]nero|genre)",
        "autor": r"(?:autor|author|escrito\s+por|written\s+by)",
        "contatos": r"(?:contato|contact|e-mail|email|telefone|phone)",
    }
    for chave, rotulo in rotulos.items():
        m = re.search(rf"^{rotulo}\s*[:\-]\s*(.+)$", texto_inicio, flags=re.I | re.M)
        if m:
            meta[chave] = m.group(1).strip()
    if not meta["titulo"]:
        meta["titulo"] = nome_arquivo
    return meta


@registrar_etapa
def _normalizar_nome_catalogo(texto: str) -> str:
    """
    Padroniza valores de entrada para que diferentes partes do sistema trabalhem com o mesmo formato.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        texto: Texto bruto ou parcialmente tratado que será analisado pela função.

    Retorno:
        O valor recebido em uma forma padronizada e segura para uso interno.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    texto = _limpar_linha(texto)
    texto = re.sub(r"\s*\([^)]*\)\s*$", "", texto).strip()
    texto = re.sub(r"\s+", " ", texto)
    return texto[:80]


@registrar_etapa
def _extrair_local_de_cabecalho(texto: str) -> str:
    """
    Extrai informações de uma origem específica e devolve uma representação mais simples para as próximas etapas do fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        texto: Texto bruto ou parcialmente tratado que será analisado pela função.

    Retorno:
        Dados extraídos em uma estrutura simplificada, adequada para as próximas etapas.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    texto = _limpar_linha(texto)
    texto = re.sub(r"^(?:\d+\s+)?(?:INT|EXT|INT\./EXT|INT/EXT|I/E|EST|INT\.?/EXT\.?)\.?\s+", "", texto, flags=re.I).strip()
    texto = re.split(r"\s+-\s+|\s+[–—]\s+", texto, maxsplit=1)[0].strip()
    texto = re.sub(r"\s+", " ", texto)
    return texto[:100]


@registrar_etapa
def _catalogo_item(nome: str) -> dict[str, str]:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        nome: Valor usado pela rotina para compor a operação de catalogo item.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return {"nome": nome, "descricao": ""}


@registrar_etapa
def _adicionar_unico(destino: list[str], valor: str) -> None:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        destino: Valor usado pela rotina para compor a operação de adicionar unico.
        valor: Valor usado pela rotina para compor a operação de adicionar unico.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    valor = _normalizar_nome_catalogo(valor)
    if not valor:
        return
    existentes = {item.casefold() for item in destino}
    if valor.casefold() not in existentes:
        destino.append(valor)


@registrar_etapa
def importar_documento_como_roteiro(slug: str, caminho: str | Path) -> dict[str, Any]:
    """
    Coordena a importação de conteúdo externo para dentro do projeto, normalizando os dados para o modelo usado pela aplicação.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        caminho: Caminho de arquivo ou pasta usado como origem ou destino da operação.

    Retorno:
        Um resumo do conteúdo importado e dos registros criados no projeto.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    caminho = Path(caminho)
    projeto = obter_projeto(slug)
    if projeto.get("tipo") != "roteiro":
        raise ValueError("Este documento só pode ser importado como roteiro em projetos de roteiro.")
    linhas = extrair_linhas_documento(caminho)
    meta = _metadados_de_capa(linhas, caminho.stem.upper())

    partes: list[str] = []
    personagens_detectados: list[str] = []
    locais_detectados: list[str] = []
    anterior = ""
    started = False
    for linha in linhas:
        texto = _limpar_linha(linha.get("text"))
        tipo = _classificar_linha_roteiro(linha, anterior)
        if not started:
            if tipo == "scene_heading":
                started = True
            else:
                continue
        if tipo == "blank":
            continue
        if tipo == "scene_heading":
            _adicionar_unico(locais_detectados, _extrair_local_de_cabecalho(texto))
        elif tipo == "character":
            _adicionar_unico(personagens_detectados, texto)
        partes.append(_bloco_roteiro_html(tipo, texto))
        anterior = tipo if tipo != "blank" else anterior
    if not partes:
        # Sem evidência segura de formatação de roteiro: importa todo o texto como neutro, como solicitado.
        partes = [_bloco_roteiro_html("neutral", _limpar_linha(l.get("text"))) for l in linhas if _limpar_linha(l.get("text"))]

    pasta = obter_pasta_projeto(slug)
    titulo = (meta.get("titulo") or caminho.stem).upper()[:70]
    roteiro = criar_roteiro(
        pasta,
        titulo,
        logline=meta.get("logline", ""),
        sinopse=meta.get("sinopse", ""),
        genero=meta.get("genero", ""),
    )
    numero = int(roteiro["id"])
    salvar_roteiro(pasta, numero, titulo, "".join(partes) or '<div class="roteiro-bloco" data-block-type="neutral" data-initial-neutral="true"><br></div>')
    info_roteiro = {
        "logline": meta.get("logline", ""),
        "sinopse": meta.get("sinopse", ""),
        "genero": meta.get("genero", ""),
    }
    if personagens_detectados:
        info_roteiro["personagens"] = personagens_detectados
        info_roteiro["catalogo_personagens"] = [_catalogo_item(nome) for nome in personagens_detectados]
    if locais_detectados:
        info_roteiro["locais"] = locais_detectados
        info_roteiro["catalogo_locais"] = [_catalogo_item(nome) for nome in locais_detectados]
    atualizar_roteiro_info(pasta, numero, info_roteiro)
    atualizacoes_projeto = {}
    if meta.get("autor") and not projeto.get("autor"):
        atualizacoes_projeto["autor"] = meta["autor"]
    if meta.get("contatos") and not projeto.get("contatos"):
        atualizacoes_projeto["contatos"] = meta["contatos"]
    if meta.get("sinopse") and not projeto.get("descricao"):
        atualizacoes_projeto["descricao"] = meta["sinopse"][:1000]
    atualizar_metadados_projeto(slug, atualizacoes_projeto)
    return {"ok": True, "redirect": f"/projetos/{slug}/roteiros/{numero}/editar", "capitulos_importados": 0, "roteiro_importado": numero}
