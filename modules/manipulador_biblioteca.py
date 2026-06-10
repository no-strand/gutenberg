"""Regras de negócio da biblioteca EPUB."""
from __future__ import annotations

import mimetypes
import posixpath
import shutil
import zipfile
from collections import OrderedDict

try:
    from rapidfuzz import fuzz
except Exception:  # pragma: no cover
    from difflib import SequenceMatcher

    class _FuzzFallback:
        """
        Representa  FuzzFallback dentro do fluxo da aplicação.
    
        Esta classe concentra estado e comportamentos relacionados para evitar que a
        lógica fique espalhada por vários pontos do código. A intenção é oferecer uma
        interface simples para quem consome o módulo, escondendo os detalhes internos
        de organização, validação e integração com os demais componentes.
        """
        @staticmethod
        @registrar_etapa
        def ratio(a: str, b: str) -> float:
            """
            Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
        
            A função isola esta responsabilidade para deixar o fluxo principal mais fácil
            de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
            normalizações ou verificações necessárias e entrega um resultado previsível
            para a próxima camada do sistema.
        
            Parâmetros:
                a: Valor usado pela rotina para compor a operação de ratio.
                b: Valor usado pela rotina para compor a operação de ratio.
        
            Retorno:
                O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
        
            Observações:
                Mantém a lógica centralizada e evita que detalhes de implementação vazem
                para quem apenas precisa acionar este comportamento.
            """
            return SequenceMatcher(None, a, b).ratio() * 100

        @staticmethod
        @registrar_etapa
        def token_sort_ratio(a: str, b: str) -> float:
            """
            Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
        
            A função isola esta responsabilidade para deixar o fluxo principal mais fácil
            de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
            normalizações ou verificações necessárias e entrega um resultado previsível
            para a próxima camada do sistema.
        
            Parâmetros:
                a: Valor usado pela rotina para compor a operação de token sort ratio.
                b: Valor usado pela rotina para compor a operação de token sort ratio.
        
            Retorno:
                O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
        
            Observações:
                Mantém a lógica centralizada e evita que detalhes de implementação vazem
                para quem apenas precisa acionar este comportamento.
            """
            sa = ' '.join(sorted((a or '').split()))
            sb = ' '.join(sorted((b or '').split()))
            return SequenceMatcher(None, sa, sb).ratio() * 100

    fuzz = _FuzzFallback()
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .persistencia_json import ler_json, salvar_json
from .conversor_pdf_epub import converter_pdf_para_epub3
from .i18n import t
from .utilidades import agora_iso, garantir_pasta_biblioteca, nome_seguro, obter_pasta_biblioteca, obter_progresso, salvar_progresso
from .logging_config import obter_logger, registrar_etapa
logger = obter_logger(__name__)

NAMESPACES = {
    "ocf": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ncx": "http://www.daisy.org/z3986/2005/ncx/",
    "xhtml": "http://www.w3.org/1999/xhtml",
    "epub": "http://www.idpf.org/2007/ops",
}

MEDIA_TYPES_DOCUMENTO = {
    "application/xhtml+xml",
    "text/html",
    "application/xml",
    "text/xml",
}


@registrar_etapa
def _normalizar_relpath(caminho: str) -> str:
    """
    Padroniza valores de entrada para que diferentes partes do sistema trabalhem com o mesmo formato.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        caminho: Caminho de arquivo ou pasta usado como origem ou destino da operação.

    Retorno:
        O valor recebido em uma forma padronizada e segura para uso interno.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    caminho = caminho.replace('\\', '/').strip('/')
    return posixpath.normpath(caminho).lstrip('./')


@registrar_etapa
def _slug_unico(base: Path, titulo: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        base: Valor usado pela rotina para compor a operação de slug unico.
        titulo: Título exibido ou salvo para representar o conteúdo tratado.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    slug_base = nome_seguro(titulo) or 'livro'
    slug = slug_base
    contador = 2
    while (base / slug).exists():
        slug = f"{slug_base}_{contador}"
        contador += 1
    return slug


@registrar_etapa
def _resolver_relativo(base: str, href: str) -> str:
    """
    Resolve caminhos, referências ou conflitos de nomes de forma previsível para o restante do sistema.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        base: Valor usado pela rotina para compor a operação de resolver relativo.
        href: Valor usado pela rotina para compor a operação de resolver relativo.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return _normalizar_relpath(posixpath.join(posixpath.dirname(base), href))


@registrar_etapa
def _abrir_xml(caminho: Path) -> ET.Element:
    """
    Abre um recurso solicitado pelo usuário ou pela aplicação usando o mecanismo apropriado para o contexto.

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
    return ET.fromstring(caminho.read_bytes())


@registrar_etapa
def _normalizar_alvo_href(caminho_base: str, href: str) -> tuple[str, str | None]:
    """
    Padroniza valores de entrada para que diferentes partes do sistema trabalhem com o mesmo formato.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        caminho_base: Valor usado pela rotina para compor a operação de normalizar alvo href.
        href: Valor usado pela rotina para compor a operação de normalizar alvo href.

    Retorno:
        O valor recebido em uma forma padronizada e segura para uso interno.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    href = (href or '').strip()
    if not href:
        return '', None
    alvo, _, fragmento = href.partition('#')
    alvo = _resolver_relativo(caminho_base, alvo) if alvo else _normalizar_relpath(caminho_base)
    return alvo, (fragmento.strip() or None)


@registrar_etapa
def _texto_limpo(elemento: ET.Element | None) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        elemento: Valor usado pela rotina para compor a operação de texto limpo.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    if elemento is None:
        return ''
    return ' '.join(''.join(elemento.itertext()).split())


@registrar_etapa
def _adicionar_toc_item(destino: list[dict[str, Any]], vistos: set[tuple[str, str | None]], caminho_base: str, href: str, titulo: str, nivel: int) -> None:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        destino: Valor usado pela rotina para compor a operação de adicionar toc item.
        vistos: Valor usado pela rotina para compor a operação de adicionar toc item.
        caminho_base: Valor usado pela rotina para compor a operação de adicionar toc item.
        href: Valor usado pela rotina para compor a operação de adicionar toc item.
        titulo: Título exibido ou salvo para representar o conteúdo tratado.
        nivel: Valor usado pela rotina para compor a operação de adicionar toc item.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    alvo, fragmento = _normalizar_alvo_href(caminho_base, href)
    titulo = ' '.join((titulo or '').split())
    if not alvo or not titulo:
        return
    chave = (alvo, fragmento)
    if chave in vistos:
        return
    vistos.add(chave)
    destino.append({
        'asset_path': alvo,
        'fragmento': fragmento,
        'titulo': titulo,
        'nivel': max(0, int(nivel)),
    })


@registrar_etapa
def _encontrar_rootfile(pasta_extraida: Path) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pasta_extraida: Valor usado pela rotina para compor a operação de encontrar rootfile.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    container_xml = pasta_extraida / 'META-INF' / 'container.xml'
    raiz = _abrir_xml(container_xml)
    rootfile = raiz.find('.//ocf:rootfile', NAMESPACES)
    if rootfile is None:
        raise FileNotFoundError('rootfile do EPUB não encontrado.')
    caminho = rootfile.attrib.get('full-path', '').strip()
    if not caminho:
        raise FileNotFoundError('Caminho do pacote OPF inválido.')
    return _normalizar_relpath(caminho)


@registrar_etapa
def _extrair_toc_nav(pasta_extraida: Path, caminho_nav: str) -> list[dict[str, Any]]:
    """
    Extrai informações de uma origem específica e devolve uma representação mais simples para as próximas etapas do fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pasta_extraida: Valor usado pela rotina para compor a operação de extrair toc nav.
        caminho_nav: Valor usado pela rotina para compor a operação de extrair toc nav.

    Retorno:
        Dados extraídos em uma estrutura simplificada, adequada para as próximas etapas.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    itens: list[dict[str, Any]] = []
    vistos: set[tuple[str, str | None]] = set()
    try:
        raiz = _abrir_xml(pasta_extraida / caminho_nav)
    except Exception:
        return itens

    nav_toc = None
    for nav in raiz.findall('.//xhtml:nav', NAMESPACES):
        tipo = (nav.attrib.get('{http://www.idpf.org/2007/ops}type') or nav.attrib.get('type') or '').lower()
        if 'toc' in tipo:
            nav_toc = nav
            break
    if nav_toc is None:
        nav_toc = raiz.find('.//xhtml:nav', NAMESPACES)
    if nav_toc is None:
        return itens

    @registrar_etapa
    def visitar_lista(lista: ET.Element, nivel: int) -> None:
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            lista: Valor usado pela rotina para compor a operação de visitar lista.
            nivel: Valor usado pela rotina para compor a operação de visitar lista.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        for li in lista.findall('./xhtml:li', NAMESPACES):
            link = li.find('./xhtml:a', NAMESPACES)
            if link is not None:
                _adicionar_toc_item(itens, vistos, caminho_nav, link.attrib.get('href', ''), _texto_limpo(link), nivel)
            else:
                span = li.find('./xhtml:span', NAMESPACES)
                subtitulo = _texto_limpo(span)
                sublista = li.find('./xhtml:ol', NAMESPACES) or li.find('./xhtml:ul', NAMESPACES)
                if subtitulo and sublista is not None:
                    primeiro_link = sublista.find('.//xhtml:a', NAMESPACES)
                    if primeiro_link is not None:
                        _adicionar_toc_item(itens, vistos, caminho_nav, primeiro_link.attrib.get('href', ''), subtitulo, nivel)
            for tag in ('./xhtml:ol', './xhtml:ul'):
                sublista = li.find(tag, NAMESPACES)
                if sublista is not None:
                    visitar_lista(sublista, nivel + 1)

    for tag in ('./xhtml:ol', './xhtml:ul'):
        lista_raiz = nav_toc.find(tag, NAMESPACES)
        if lista_raiz is not None:
            visitar_lista(lista_raiz, 0)
            break
    return itens


@registrar_etapa
def _extrair_toc_ncx(pasta_extraida: Path, caminho_ncx: str) -> list[dict[str, Any]]:
    """
    Extrai informações de uma origem específica e devolve uma representação mais simples para as próximas etapas do fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pasta_extraida: Valor usado pela rotina para compor a operação de extrair toc ncx.
        caminho_ncx: Valor usado pela rotina para compor a operação de extrair toc ncx.

    Retorno:
        Dados extraídos em uma estrutura simplificada, adequada para as próximas etapas.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    itens: list[dict[str, Any]] = []
    vistos: set[tuple[str, str | None]] = set()
    try:
        raiz = _abrir_xml(pasta_extraida / caminho_ncx)
    except Exception:
        return itens

    @registrar_etapa
    def visitar_pontos(pontos: list[ET.Element], nivel: int) -> None:
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            pontos: Valor usado pela rotina para compor a operação de visitar pontos.
            nivel: Valor usado pela rotina para compor a operação de visitar pontos.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        for ponto in pontos:
            src = ponto.find('./ncx:content', NAMESPACES)
            label = ponto.find('./ncx:navLabel/ncx:text', NAMESPACES)
            href = (src.attrib.get('src') if src is not None else '') or ''
            titulo = (label.text if label is not None else '') or ''
            _adicionar_toc_item(itens, vistos, caminho_ncx, href, titulo, nivel)
            filhos = ponto.findall('./ncx:navPoint', NAMESPACES)
            if filhos:
                visitar_pontos(filhos, nivel + 1)

    visitar_pontos(raiz.findall('.//ncx:navMap/ncx:navPoint', NAMESPACES), 0)
    return itens


@registrar_etapa
def _extrair_titulo_do_documento(pasta_extraida: Path, asset_path: str) -> str:
    """
    Extrai informações de uma origem específica e devolve uma representação mais simples para as próximas etapas do fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pasta_extraida: Valor usado pela rotina para compor a operação de extrair titulo do documento.
        asset_path: Valor usado pela rotina para compor a operação de extrair titulo do documento.

    Retorno:
        Dados extraídos em uma estrutura simplificada, adequada para as próximas etapas.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    try:
        raiz = _abrir_xml(pasta_extraida / asset_path)
    except Exception:
        return ''
    for seletor in ('./xhtml:head/xhtml:title', './/xhtml:h1', './/xhtml:h2'):
        el = raiz.find(seletor, NAMESPACES)
        texto = _texto_limpo(el)
        if texto:
            return texto
    return ''


@registrar_etapa
def _detectar_capa(opf_path: str, manifest: dict[str, dict[str, str]], metadata_el: ET.Element | None, guide_el: ET.Element | None) -> str | None:
    """
    Analisa pistas no conteúdo para decidir automaticamente qual recurso, metadado ou comportamento deve ser usado.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        opf_path: Valor usado pela rotina para compor a operação de detectar capa.
        manifest: Valor usado pela rotina para compor a operação de detectar capa.
        metadata_el: Valor usado pela rotina para compor a operação de detectar capa.
        guide_el: Valor usado pela rotina para compor a operação de detectar capa.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    if metadata_el is not None:
        for meta in metadata_el.findall('opf:meta', NAMESPACES):
            if (meta.attrib.get('name') or '').lower() == 'cover':
                cover_id = meta.attrib.get('content') or ''
                if cover_id and cover_id in manifest:
                    return _resolver_relativo(opf_path, manifest[cover_id]['href'])
    for item_id, item in manifest.items():
        props = item.get('properties', '')
        media = item.get('media-type', '')
        if 'cover-image' in props or item_id.lower() == 'cover' or media.startswith('image/') and 'cover' in item.get('href', '').lower():
            return _resolver_relativo(opf_path, item['href'])
    if guide_el is not None:
        for ref in guide_el.findall('opf:reference', NAMESPACES):
            if (ref.attrib.get('type') or '').lower() == 'cover':
                href = ref.attrib.get('href') or ''
                if href:
                    return _resolver_relativo(opf_path, href)
    return None


@registrar_etapa
def _parsear_epub_extraido(pasta_extraida: Path) -> dict[str, Any]:
    """
    Interpreta uma estrutura textual ou documental e converte seus elementos em dados manipuláveis.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pasta_extraida: Valor usado pela rotina para compor a operação de parsear epub extraido.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    opf_rel = _encontrar_rootfile(pasta_extraida)
    opf_path = pasta_extraida / opf_rel
    raiz = _abrir_xml(opf_path)
    metadata_el = raiz.find('opf:metadata', NAMESPACES)
    manifest_el = raiz.find('opf:manifest', NAMESPACES)
    spine_el = raiz.find('opf:spine', NAMESPACES)
    guide_el = raiz.find('opf:guide', NAMESPACES)

    titulo = 'Livro sem título'
    autor = ''
    idioma = 'pt-BR'
    if metadata_el is not None:
        titulo_el = metadata_el.find('dc:title', NAMESPACES)
        autor_el = metadata_el.find('dc:creator', NAMESPACES)
        idioma_el = metadata_el.find('dc:language', NAMESPACES)
        if titulo_el is not None and titulo_el.text:
            titulo = ' '.join(titulo_el.text.split())
        if autor_el is not None and autor_el.text:
            autor = ' '.join(autor_el.text.split())
        if idioma_el is not None and idioma_el.text:
            idioma = ' '.join(idioma_el.text.split())

    manifest: dict[str, dict[str, str]] = {}
    if manifest_el is not None:
        for item in manifest_el.findall('opf:item', NAMESPACES):
            item_id = item.attrib.get('id', '').strip()
            href = item.attrib.get('href', '').strip()
            if not item_id or not href:
                continue
            manifest[item_id] = {
                'href': href,
                'media-type': item.attrib.get('media-type', '').strip(),
                'properties': item.attrib.get('properties', '').strip(),
            }

    toc_itens: list[dict[str, Any]] = []
    nav_item = next((item for item in manifest.values() if 'nav' in item.get('properties', '').split()), None)
    if nav_item:
        toc_itens.extend(_extrair_toc_nav(pasta_extraida, _resolver_relativo(opf_rel, nav_item['href'])))

    toc_id = spine_el.attrib.get('toc') if spine_el is not None else None
    if toc_id and toc_id in manifest:
        toc_itens.extend(_extrair_toc_ncx(pasta_extraida, _resolver_relativo(opf_rel, manifest[toc_id]['href'])))
    else:
        ncx_item = next((item for item in manifest.values() if item.get('media-type') == 'application/x-dtbncx+xml'), None)
        if ncx_item:
            toc_itens.extend(_extrair_toc_ncx(pasta_extraida, _resolver_relativo(opf_rel, ncx_item['href'])))

    titulos_por_arquivo: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for item in toc_itens:
        asset_path = item['asset_path']
        if asset_path not in titulos_por_arquivo:
            titulos_por_arquivo[asset_path] = item

    capitulos = []
    vistos_capitulos: set[str] = set()
    if spine_el is not None:
        for itemref in spine_el.findall('opf:itemref', NAMESPACES):
            idref = itemref.attrib.get('idref', '').strip()
            if not idref or idref not in manifest:
                continue
            item = manifest[idref]
            media_type = item.get('media-type', '')
            if media_type not in MEDIA_TYPES_DOCUMENTO:
                continue
            asset_path = _resolver_relativo(opf_rel, item['href'])
            if asset_path in vistos_capitulos:
                continue
            vistos_capitulos.add(asset_path)
            toc_info = titulos_por_arquivo.get(asset_path, {})
            titulo_documento = _extrair_titulo_do_documento(pasta_extraida, asset_path)
            titulo_cap = toc_info.get('titulo') or titulo_documento or Path(item['href']).stem.replace('_', ' ').replace('-', ' ').title() or f'Capítulo {len(capitulos) + 1}'
            capitulos.append({
                'id': len(capitulos) + 1,
                'titulo': titulo_cap,
                'href': item['href'],
                'asset_path': asset_path,
                'media_type': media_type,
                'nivel': int(toc_info.get('nivel', 0)),
                'fragmento_inicial': toc_info.get('fragmento'),
            })

    if not capitulos:
        for item in manifest.values():
            media_type = item.get('media-type', '')
            if media_type not in MEDIA_TYPES_DOCUMENTO:
                continue
            asset_path = _resolver_relativo(opf_rel, item['href'])
            if asset_path in vistos_capitulos:
                continue
            vistos_capitulos.add(asset_path)
            toc_info = titulos_por_arquivo.get(asset_path, {})
            titulo_documento = _extrair_titulo_do_documento(pasta_extraida, asset_path)
            capitulos.append({
                'id': len(capitulos) + 1,
                'titulo': toc_info.get('titulo') or titulo_documento or Path(item['href']).stem.replace('_', ' ').replace('-', ' ').title() or f'Capítulo {len(capitulos) + 1}',
                'href': item['href'],
                'asset_path': asset_path,
                'media_type': media_type,
                'nivel': int(toc_info.get('nivel', 0)),
                'fragmento_inicial': toc_info.get('fragmento'),
            })

    return {
        'titulo': titulo,
        'autor': autor,
        'idioma': idioma,
        'opf_path': opf_rel,
        'cover_path': _detectar_capa(opf_rel, manifest, metadata_el, guide_el),
        'capitulos': capitulos,
        'toc': toc_itens,
    }


@registrar_etapa
def _caminho_meta(slug: str) -> Path:
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
    return obter_pasta_biblioteca() / slug / 'livro.json'


@registrar_etapa
def _pasta_livro(slug: str) -> Path:
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
    pasta = obter_pasta_biblioteca() / slug
    if not pasta.exists():
        raise FileNotFoundError('Livro não encontrado.')
    return pasta



@registrar_etapa
def adicionar_livro_pdf(caminho_origem: Path) -> dict[str, Any]:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        caminho_origem: Valor usado pela rotina para compor a operação de adicionar livro pdf.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    epub_gerado = caminho_origem.with_suffix('.epub')
    try:
        converter_pdf_para_epub3(caminho_origem, epub_gerado)
        livro = adicionar_livro_epub(epub_gerado)
        livro['arquivo_original_pdf'] = caminho_origem.name
        atualizar_metadados_livro(livro['slug'], {'arquivo_original_pdf': caminho_origem.name})
        return livro
    finally:
        try:
            epub_gerado.unlink(missing_ok=True)
        except Exception:
            pass


@registrar_etapa
def adicionar_livro_epub(caminho_origem: Path) -> dict[str, Any]:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        caminho_origem: Valor usado pela rotina para compor a operação de adicionar livro epub.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    garantir_pasta_biblioteca()
    base = obter_pasta_biblioteca()
    slug = _slug_unico(base, caminho_origem.stem)
    pasta = base / slug
    extraido = pasta / 'extraido'
    arquivo_destino = pasta / caminho_origem.name
    pasta.mkdir(parents=True, exist_ok=True)
    shutil.copy2(caminho_origem, arquivo_destino)
    with zipfile.ZipFile(arquivo_destino, 'r') as epub_zip:
        epub_zip.extractall(extraido)
    dados = _parsear_epub_extraido(extraido)
    livro = {
        'slug': slug,
        'arquivo_original': caminho_origem.name,
        'arquivo_epub': arquivo_destino.name,
        'titulo': dados['titulo'] or caminho_origem.stem,
        'autor': dados['autor'],
        'idioma': dados['idioma'],
        'data_adicao': agora_iso(),
        'cover_path': dados['cover_path'],
        'opf_path': dados['opf_path'],
        'capitulos': dados['capitulos'],
        'toc': dados.get('toc', []),
        'ultimo_lido': None,
        'posicoes_leitura': {},
    }
    salvar_json(pasta / 'livro.json', livro)
    return livro




@registrar_etapa
def _registro_livro_padrao() -> dict[str, Any]:
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
    return {
        'ultimo_lido': None,
        'ultima_leitura_em': '',
        'capitulo_atual': None,
        'percentual': 0.0,
        'concluido': False,
        'marcado_lido': False,
        'iniciado': False,
        'capitulos': {},
    }


@registrar_etapa
def _posicoes_registro_livro(registro: dict[str, Any]) -> dict[str, int]:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        registro: Valor usado pela rotina para compor a operação de posicoes registro livro.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    posicoes: dict[str, int] = {}
    for chave, valor in (registro.get('capitulos') or {}).items():
        if not isinstance(valor, dict):
            continue
        try:
            posicoes[str(chave)] = max(0, int(valor.get('posicao') or 0))
        except Exception:
            continue
    return posicoes


@registrar_etapa
def _obter_registro_livro(slug: str) -> dict[str, Any]:
    """
    Localiza e devolve um dado ou recurso específico, aplicando as validações necessárias antes do retorno.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.

    Retorno:
        O recurso solicitado ou uma estrutura com os dados encontrados.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    progresso = obter_progresso()
    livros = progresso.setdefault('livros', {})
    registro = livros.get(slug)
    if not isinstance(registro, dict):
        registro = _registro_livro_padrao()
        livros[slug] = registro
        salvar_progresso(progresso)
    base = _registro_livro_padrao()
    base.update(registro)
    if not isinstance(base.get('capitulos'), dict):
        base['capitulos'] = {}
    return base


@registrar_etapa
def _salvar_registro_livro(slug: str, registro: dict[str, Any]) -> dict[str, Any]:
    """
    Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        registro: Valor usado pela rotina para compor a operação de salvar registro livro.

    Retorno:
        A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    progresso = obter_progresso()
    livros = progresso.setdefault('livros', {})
    base = _registro_livro_padrao()
    base.update(registro or {})
    if not isinstance(base.get('capitulos'), dict):
        base['capitulos'] = {}
    livros[slug] = base
    salvar_progresso(progresso)
    return base


@registrar_etapa
def _percentual_global_livro(livro: dict[str, Any], registro: dict[str, Any]) -> float:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        livro: Valor usado pela rotina para compor a operação de percentual global livro.
        registro: Valor usado pela rotina para compor a operação de percentual global livro.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    capitulos = livro.get('capitulos') or []
    total = len(capitulos)
    if total <= 0:
        return float(registro.get('percentual') or 0.0)
    atual = int(registro.get('capitulo_atual') or registro.get('ultimo_lido') or 1)
    atual = max(1, min(total, atual))
    cap_percent = 0.0
    cap_data = (registro.get('capitulos') or {}).get(str(atual), {})
    try:
        cap_percent = float(cap_data.get('percentual') or 0.0)
    except Exception:
        cap_percent = 0.0
    percentual = ((atual - 1) / total) * 100.0 + (cap_percent / total)
    return max(0.0, min(100.0, percentual))


@registrar_etapa
def _enriquecer_livro_com_progresso(livro: dict[str, Any]) -> dict[str, Any]:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        livro: Valor usado pela rotina para compor a operação de enriquecer livro com progresso.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    registro = _obter_registro_livro(livro['slug'])
    percentual = float(registro.get('percentual') or _percentual_global_livro(livro, registro) or 0.0)
    concluiu = bool(registro.get('concluido') or registro.get('marcado_lido') or percentual >= 95.0)
    livro['progresso_percentual'] = round(percentual, 1)
    livro['ultimo_lido'] = registro.get('ultimo_lido') or livro.get('ultimo_lido')
    livro['ultima_leitura_em'] = registro.get('ultima_leitura_em') or ''
    livro['capitulo_atual'] = registro.get('capitulo_atual') or livro.get('ultimo_lido')
    posicoes = dict(livro.get('posicoes_leitura') or {})
    posicoes.update(_posicoes_registro_livro(registro))
    livro['posicoes_leitura'] = posicoes
    livro['foi_iniciado'] = bool(registro.get('iniciado') or percentual > 0 or livro.get('ultimo_lido'))
    livro['foi_lido'] = concluiu
    livro['marcado_lido'] = bool(registro.get('marcado_lido') or concluiu)
    livro['estado_leitura'] = 'lido' if concluiu else ('lendo' if livro['foi_iniciado'] else 'nao_iniciado')
    return livro


@registrar_etapa
def chave_colecao_titulo(titulo: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        titulo: Título exibido ou salvo para representar o conteúdo tratado.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    texto = ' '.join((titulo or '').split())
    texto = texto.replace('–', '-').replace('—', '-')
    import re
    texto = re.sub(r'\s*[\-:–—]?\s*(volume|vol\.?|ln|light\s+novel|book|tomo|parte|chapter|cap[ií]tulo)\s*\d+\b.*$', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\s*\((volume|vol\.?|ln|book|tomo|parte)\s*\d+\)\s*$', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\b(novel|series)\b$', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'[^\w\s]', ' ', texto, flags=re.UNICODE)
    texto = re.sub(r'\s+', ' ', texto).strip(' -:')
    return texto or titulo


@registrar_etapa
def _titulos_parecidos(base: str, outro: str) -> bool:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        base: Valor usado pela rotina para compor a operação de titulos parecidos.
        outro: Valor usado pela rotina para compor a operação de titulos parecidos.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    base = ' '.join((base or '').split()).lower()
    outro = ' '.join((outro or '').split()).lower()
    if not base or not outro:
        return False
    if base == outro:
        return True
    ratio = float(fuzz.ratio(base, outro))
    token_ratio = float(fuzz.token_sort_ratio(base, outro))
    menor, maior = sorted((base, outro), key=len)
    contem = len(menor) >= 12 and (menor in maior)
    return ratio >= 88.0 or token_ratio >= 92.0 or contem


@registrar_etapa
def _resolver_mapa_colecoes(livros: list[dict[str, Any]]) -> tuple[dict[str, dict[str, str]], list[dict[str, Any]]]:
    """
    Resolve caminhos, referências ou conflitos de nomes de forma previsível para o restante do sistema.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        livros: Valor usado pela rotina para compor a operação de resolver mapa colecoes.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    grupos: list[dict[str, Any]] = []
    for livro in livros:
        titulo_base = chave_colecao_titulo(livro.get('titulo', ''))
        alvo = None
        for grupo in grupos:
            if _titulos_parecidos(grupo['base'], titulo_base):
                alvo = grupo
                break
        if alvo is None:
            alvo = {'base': titulo_base, 'nome': titulo_base, 'livros': []}
            grupos.append(alvo)
        elif len(titulo_base) < len(alvo['nome']):
            alvo['nome'] = titulo_base
        alvo['livros'].append(livro)

    mapa: dict[str, dict[str, str]] = {}
    colecoes: list[dict[str, Any]] = []
    for grupo in grupos:
        nome = grupo['nome']
        slug = nome_seguro(nome)
        total = len(grupo['livros'])
        for livro in grupo['livros']:
            chave = livro.get('slug') or livro.get('arquivo_original') or livro.get('titulo')
            mapa[chave] = {
                'slug': slug,
                'nome': nome,
                'total': total,
                'tem_colecao': total >= 2,
            }
        if total >= 2:
            colecoes.append({'nome': nome, 'slug': slug, 'total': total})

    colecoes.sort(key=lambda item: item['nome'].lower())
    return mapa, colecoes


@registrar_etapa
def listar_colecoes_livros() -> list[dict[str, Any]]:
    """
    Reúne e devolve uma lista organizada de itens disponíveis para a interface ou para outra camada do sistema.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Retorno:
        Uma lista com os registros encontrados, normalmente já ordenada e pronta para a interface.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    livros = listar_livros()
    _, colecoes = _resolver_mapa_colecoes(livros)
    return colecoes

@registrar_etapa
def listar_livros() -> list[dict[str, Any]]:
    """
    Reúne e devolve uma lista organizada de itens disponíveis para a interface ou para outra camada do sistema.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Retorno:
        Uma lista com os registros encontrados, normalmente já ordenada e pronta para a interface.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    garantir_pasta_biblioteca()
    livros = []
    for pasta in obter_pasta_biblioteca().iterdir():
        if not pasta.is_dir():
            continue
        livro = ler_json(pasta / 'livro.json', {})
        if not livro:
            continue
        livro['slug'] = pasta.name
        livro['total_capitulos'] = len(livro.get('capitulos', []))
        livro['tem_capa'] = bool(livro.get('cover_path')) and (pasta / 'extraido' / livro.get('cover_path', '')).exists()
        livros.append(_enriquecer_livro_com_progresso(livro))
    mapa_colecoes, _ = _resolver_mapa_colecoes(livros)
    for livro in livros:
        colecao = mapa_colecoes.get(livro.get('slug'), {})
        livro['chave_colecao'] = colecao.get('slug', '')
        livro['nome_colecao'] = colecao.get('nome', chave_colecao_titulo(livro.get('titulo', '')))
        livro['tem_colecao'] = bool(colecao.get('tem_colecao'))
    livros.sort(key=lambda item: ((item.get('ultima_leitura_em') or ''), item.get('data_adicao', '')), reverse=True)
    return livros


@registrar_etapa
def obter_livro(slug: str) -> dict[str, Any]:
    """
    Localiza e devolve um dado ou recurso específico, aplicando as validações necessárias antes do retorno.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.

    Retorno:
        O recurso solicitado ou uma estrutura com os dados encontrados.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    livro = ler_json(_caminho_meta(slug), {})
    if not livro:
        raise FileNotFoundError('Livro não encontrado.')
    livro['slug'] = slug
    livro['total_capitulos'] = len(livro.get('capitulos', []))
    livro['tem_capa'] = bool(livro.get('cover_path')) and (_pasta_livro(slug) / 'extraido' / livro.get('cover_path', '')).exists()
    livro.setdefault('ultimo_lido', None)
    livro.setdefault('posicoes_leitura', {})
    livro = _enriquecer_livro_com_progresso(livro)
    mapa_colecoes, _ = _resolver_mapa_colecoes(listar_livros())
    colecao = mapa_colecoes.get(slug, {})
    livro['chave_colecao'] = colecao.get('slug', nome_seguro(chave_colecao_titulo(livro.get('titulo', ''))))
    livro['nome_colecao'] = colecao.get('nome', chave_colecao_titulo(livro.get('titulo', '')))
    livro['tem_colecao'] = bool(colecao.get('tem_colecao'))
    return livro


@registrar_etapa
def atualizar_metadados_livro(slug: str, atualizacoes: dict[str, Any]) -> dict[str, Any]:
    """
    Aplica alterações controladas sobre dados já existentes sem recriar estruturas desnecessariamente.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        atualizacoes: Valor usado pela rotina para compor a operação de atualizar metadados livro.

    Retorno:
        A estrutura atualizada depois da aplicação das mudanças.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    caminho = _caminho_meta(slug)
    dados = ler_json(caminho, {})
    if not dados:
        raise FileNotFoundError('Livro não encontrado.')
    dados.update(atualizacoes)
    salvar_json(caminho, dados)
    return dados


@registrar_etapa
def registrar_ultimo_lido_livro(slug: str, numero_capitulo: int) -> None:
    """
    Registra uma informação de estado ou progresso para que ela possa ser consultada posteriormente.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        numero_capitulo: Valor usado pela rotina para compor a operação de registrar ultimo lido livro.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    registro = _obter_registro_livro(slug)
    registro['ultimo_lido'] = max(1, int(numero_capitulo or 1))
    registro['capitulo_atual'] = registro['ultimo_lido']
    registro['ultima_leitura_em'] = agora_iso()
    registro['iniciado'] = True
    _salvar_registro_livro(slug, registro)


@registrar_etapa
def registrar_posicao_leitura_livro(slug: str, numero_capitulo: int, posicao: int) -> None:
    """
    Registra uma informação de estado ou progresso para que ela possa ser consultada posteriormente.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        numero_capitulo: Valor usado pela rotina para compor a operação de registrar posicao leitura livro.
        posicao: Valor usado pela rotina para compor a operação de registrar posicao leitura livro.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    registro = _obter_registro_livro(slug)
    capitulos = dict(registro.get('capitulos') or {})
    cap_reg = dict(capitulos.get(str(numero_capitulo)) or {})
    cap_reg['posicao'] = max(0, int(posicao))
    capitulos[str(numero_capitulo)] = cap_reg
    registro['capitulos'] = capitulos
    registro['ultimo_lido'] = max(1, int(numero_capitulo or 1))
    registro['capitulo_atual'] = registro['ultimo_lido']
    registro['ultima_leitura_em'] = agora_iso()
    registro['iniciado'] = True
    _salvar_registro_livro(slug, registro)




@registrar_etapa
def atualizar_progresso_livro(slug: str, numero_capitulo: int, percentual_capitulo: float | int, posicao: int | None = None) -> dict[str, Any]:
    """
    Aplica alterações controladas sobre dados já existentes sem recriar estruturas desnecessariamente.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        numero_capitulo: Valor usado pela rotina para compor a operação de atualizar progresso livro.
        percentual_capitulo: Valor usado pela rotina para compor a operação de atualizar progresso livro.
        posicao: Valor usado pela rotina para compor a operação de atualizar progresso livro.

    Retorno:
        A estrutura atualizada depois da aplicação das mudanças.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    livro = obter_livro(slug)
    total = max(1, len(livro.get('capitulos') or []))
    numero_capitulo = max(1, min(total, int(numero_capitulo or 1)))
    percentual_capitulo = max(0.0, min(100.0, float(percentual_capitulo or 0.0)))
    registro = _obter_registro_livro(slug)
    capitulos = dict(registro.get('capitulos') or {})
    cap_reg = dict(capitulos.get(str(numero_capitulo)) or {})
    cap_reg['percentual'] = round(percentual_capitulo, 2)
    if posicao is not None:
        cap_reg['posicao'] = max(0, int(posicao))
    capitulos[str(numero_capitulo)] = cap_reg
    registro['capitulos'] = capitulos
    registro['ultimo_lido'] = numero_capitulo
    registro['capitulo_atual'] = numero_capitulo
    registro['ultima_leitura_em'] = agora_iso()
    registro['iniciado'] = True
    percentual_global = ((numero_capitulo - 1) / total) * 100.0 + (percentual_capitulo / total)
    registro['percentual'] = round(max(0.0, min(100.0, percentual_global)), 2)
    ultimo_capitulo = total
    registro['concluido'] = bool(registro.get('marcado_lido')) or (numero_capitulo >= ultimo_capitulo and percentual_capitulo >= 95.0) or registro['percentual'] >= 95.0
    salvo = _salvar_registro_livro(slug, registro)
    return _enriquecer_livro_com_progresso({**livro, **{'slug': slug}})


@registrar_etapa
def marcar_livro_como_lido(slug: str, lido: bool) -> dict[str, Any]:
    """
    Altera um estado booleano ou de progresso associado ao item informado.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        lido: Valor usado pela rotina para compor a operação de marcar livro como lido.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    livro = obter_livro(slug)
    registro = _obter_registro_livro(slug)
    registro['marcado_lido'] = bool(lido)
    registro['concluido'] = bool(lido) or bool(registro.get('concluido'))
    if lido:
        registro['iniciado'] = True
        registro['percentual'] = max(float(registro.get('percentual') or 0.0), 100.0)
        registro['ultima_leitura_em'] = registro.get('ultima_leitura_em') or agora_iso()
    salvo = _salvar_registro_livro(slug, registro)
    return _enriquecer_livro_com_progresso({**livro, **{'slug': slug}})

@registrar_etapa
def excluir_livro(slug: str) -> None:
    """
    Remove o item indicado e executa os cuidados necessários para manter o restante do projeto consistente.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.

    Retorno:
        None. A função sinaliza falhas por exceção quando a remoção não pode ser concluída.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    pasta_livro = _pasta_livro(slug)
    slug_progress = slug

    livro_json = pasta_livro / 'livro.json'
    if livro_json.exists():
        try:
            dados_livro = ler_json(livro_json, {}) or {}
            slug_livro = str(dados_livro.get('slug') or '').strip()
            if slug_livro:
                slug_progress = slug_livro
        except Exception:
            pass

    progresso = obter_progresso()
    livros = progresso.setdefault('livros', {})
    if slug_progress in livros:
        livros.pop(slug_progress, None)
        salvar_progresso(progresso)

    shutil.rmtree(pasta_livro, ignore_errors=True)


@registrar_etapa
def obter_capitulo_livro(slug: str, numero: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    """
    Localiza e devolve um dado ou recurso específico, aplicando as validações necessárias antes do retorno.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        numero: Número usado para localizar o capítulo, item ou posição correspondente.

    Retorno:
        O recurso solicitado ou uma estrutura com os dados encontrados.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    livro = obter_livro(slug)
    capitulos = livro.get('capitulos', [])
    indice = numero - 1
    if indice < 0 or indice >= len(capitulos):
        raise FileNotFoundError(t('backend.chapter_not_found'))
    atual = capitulos[indice]
    anterior = capitulos[indice - 1] if indice > 0 else None
    proximo = capitulos[indice + 1] if indice < len(capitulos) - 1 else None
    return livro, atual, anterior, proximo


@registrar_etapa
def obter_arquivo_extraido(slug: str, relpath: str) -> Path:
    """
    Localiza e devolve um dado ou recurso específico, aplicando as validações necessárias antes do retorno.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        relpath: Valor usado pela rotina para compor a operação de obter arquivo extraido.

    Retorno:
        O recurso solicitado ou uma estrutura com os dados encontrados.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    base = (_pasta_livro(slug) / 'extraido').resolve()
    caminho = (base / _normalizar_relpath(relpath)).resolve()
    if not str(caminho).startswith(str(base)) or not caminho.exists() or not caminho.is_file():
        raise FileNotFoundError('Arquivo do livro não encontrado.')
    return caminho


@registrar_etapa
def obter_caminho_capa(slug: str) -> Path:
    """
    Localiza e devolve um dado ou recurso específico, aplicando as validações necessárias antes do retorno.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.

    Retorno:
        O recurso solicitado ou uma estrutura com os dados encontrados.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    livro = obter_livro(slug)
    cover = livro.get('cover_path')
    if not cover:
        raise FileNotFoundError('Capa não encontrada.')
    return obter_arquivo_extraido(slug, cover)


@registrar_etapa
def mime_por_arquivo(caminho: Path) -> str:
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
    mime, _ = mimetypes.guess_type(str(caminho))
    return mime or 'application/octet-stream'
