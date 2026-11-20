"""Operações locais e seguras de leitura PDF, preservando a paginação original.

PyMuPDF já é dependência do Gutenberg (conversão PDF->EPUB). Nenhum serviço
externo ou PDF.js remoto é necessário para visualizar documentos.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import fitz

MAX_PDF_BYTES = 250 * 1024 * 1024
MAX_PDF_PAGES = 3000
MAX_RENDER_PIXELS = 12_000_000


def _abrir_pdf(caminho: Path) -> fitz.Document:
    arquivo = Path(caminho)
    if not arquivo.is_file() or arquivo.stat().st_size > MAX_PDF_BYTES:
        raise ValueError('PDF inexistente ou maior que o limite de 250 MB.')
    with arquivo.open('rb') as origem:
        if b'%PDF-' not in origem.read(1024):
            raise ValueError('O arquivo não contém um cabeçalho PDF válido.')
    try:
        documento = fitz.open(str(arquivo), filetype='pdf')
    except Exception as exc:
        raise ValueError('Não foi possível abrir o PDF. O arquivo pode estar danificado.') from exc
    if documento.needs_pass:
        documento.close()
        raise ValueError('PDF protegido por senha: remova a proteção antes de importar.')
    if documento.page_count < 1 or documento.page_count > MAX_PDF_PAGES:
        documento.close()
        raise ValueError('O PDF deve conter entre 1 e 3000 páginas.')
    return documento


def inspecionar_pdf(caminho: Path) -> dict:
    """Lê apenas metadados e marcadores, sem converter texto nem páginas."""
    with _abrir_pdf(caminho) as documento:
        meta = documento.metadata or {}
        sumario = []
        try:
            marcadores = documento.get_toc(simple=True)
        except Exception:
            marcadores = []
        for nivel, titulo, pagina in marcadores[:1000]:
            if 1 <= int(pagina) <= documento.page_count:
                sumario.append({
                    'nivel': max(1, min(6, int(nivel))),
                    'titulo': str(titulo or '').strip()[:160] or f'Página {pagina}',
                    'pagina': int(pagina),
                })
        return {
            'titulo': str(meta.get('title') or '').strip()[:200],
            'autor': str(meta.get('author') or '').strip()[:200],
            'paginas': documento.page_count,
            'sumario': sumario,
        }


def miniatura_pdf(caminho: Path) -> bytes:
    """Cria capa local a partir da primeira página, sem alterar o PDF."""
    with _abrir_pdf(caminho) as documento:
        pagina = documento.load_page(0)
        escala = min(1.35, 410 / max(1.0, pagina.rect.width),
                     620 / max(1.0, pagina.rect.height),
                     (500_000 / max(1.0, pagina.rect.width * pagina.rect.height)) ** 0.5)
        return pagina.get_pixmap(matrix=fitz.Matrix(escala, escala), alpha=False).tobytes('png')


def renderizar_pagina_pdf(caminho: Path, pagina: int, escala: float = 1.25) -> bytes:
    """Devolve PNG da página em escala limitada para evitar alocações enormes."""
    with _abrir_pdf(caminho) as documento:
        if not 1 <= pagina <= documento.page_count:
            raise FileNotFoundError('Página do PDF não encontrada.')
        atual = documento.load_page(pagina - 1)
        escala = min(2.5, max(0.5, float(escala)))
        area = max(1.0, atual.rect.width * atual.rect.height)
        escala = min(escala, (MAX_RENDER_PIXELS / area) ** .5)
        try:
            return atual.get_pixmap(matrix=fitz.Matrix(escala, escala), alpha=False).tobytes('png')
        except Exception as exc:
            raise ValueError('Não foi possível renderizar esta página do PDF.') from exc


def texto_pagina_pdf(caminho: Path, pagina: int) -> str:
    with _abrir_pdf(caminho) as documento:
        if not 1 <= pagina <= documento.page_count:
            raise FileNotFoundError('Página do PDF não encontrada.')
        return documento.load_page(pagina - 1).get_text('text')[:200_000]


def pesquisar_pdf(caminho: Path, consulta: str, limite: int = 40) -> list[dict]:
    """Pesquisa texto extraível, com limite de resultados para interface responsiva."""
    termo = str(consulta or '').strip()[:100]
    if len(termo) < 2:
        return []
    resultados = []
    with _abrir_pdf(caminho) as documento:
        for indice in range(documento.page_count):
            texto = documento.load_page(indice).get_text('text')
            inicio = texto.casefold().find(termo.casefold())
            if inicio < 0:
                continue
            trecho = ' '.join(texto[max(0, inicio - 70):inicio + len(termo) + 100].split())
            resultados.append({'pagina': indice + 1, 'trecho': trecho[:220]})
            if len(resultados) >= limite:
                break
    return resultados
