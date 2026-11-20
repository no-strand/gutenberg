"""Pré-publicação: conferência não destrutiva de conteúdo, metadados e arquivos.

Não escreve no projeto. Erros impedem a exportação; avisos podem ser aceitos
explicitamente na interface. Verificação de artefatos é executada APÓS exportar.
"""
from __future__ import annotations

import base64
import binascii
import io
import json
import re
from hashlib import sha256
from collections import Counter
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree

from bs4 import BeautifulSoup
from PIL import Image, UnidentifiedImageError

from .i18n import t
from .manipulador_capitulos import ler_capitulo
from .manipulador_projetos import obter_pasta_projeto, obter_projeto
from .manipulador_roteiros import ler_roteiro
from .revisao_editorial import ler as ler_revisao_editorial

FORMATOS_LIVRO = frozenset({'epub', 'xhtml', 'docx', 'pdf'})
FORMATOS_ROTEIRO = frozenset({'docx', 'pdf'})
TIPOS_DOCUMENTO = frozenset({'roteiro', 'outline', 'estatistica', 'completo'})
MAX_IMAGEM_DECODIFICADA = 15 * 1024 * 1024
MAX_DOCUMENTOS_ANALISADOS = 5000


def _mensagem(codigo: str, **kwargs) -> str:
    return t(f'publish.{codigo}', default=codigo, **kwargs)


def _item(nivel: str, codigo: str, *, contexto: str = '', **kwargs) -> dict:
    return {
        'nivel': nivel,
        'codigo': codigo,
        'titulo': _mensagem('issue_' + codigo),
        'detalhe': _mensagem('detail_' + codigo, **kwargs),
        'contexto': contexto,
    }


def _extrair_conteudo(documento: dict) -> str:
    paragrafos = documento.get('paragrafos') or []
    if isinstance(paragrafos, str):
        return paragrafos
    return '\n'.join(str(parte) for parte in paragrafos)


def _checar_imagens(soup: BeautifulSoup, *, contexto: str, formato: str, itens: list[dict]):
    """Não acessa endereços remotos nem lê caminhos fornecidos pelo HTML."""
    contagem = Counter()
    for imagem in soup.find_all('img'):
        src = (imagem.get('src') or '').strip()
        if not src:
            contagem['img_sem_origem'] += 1
        elif src.startswith('data:image/'):
            # Os exportadores EPUB usam dados embutidos em vez de caminho local.
            try:
                cabecalho, payload = src.split(',', 1)
                if not re.fullmatch(r'data:image/(?:jpeg|jpg|png|webp|gif);base64', cabecalho, re.I):
                    raise ValueError('MIME')
                if len(payload) > MAX_IMAGEM_DECODIFICADA * 4 // 3 + 8:
                    raise ValueError('tamanho')
                dados = base64.b64decode(payload, validate=True)
                if not dados or len(dados) > MAX_IMAGEM_DECODIFICADA:
                    raise ValueError('tamanho')
                with Image.open(io.BytesIO(dados)) as img:
                    img.verify()
            except (ValueError, binascii.Error, OSError, UnidentifiedImageError):
                contagem['img_corrompida'] += 1
        elif formato in ('epub', 'xhtml'):
            # Arquivos externos não são incorporados pelos exportadores atuais.
            contagem['img_externa'] += 1
    for codigo, quantidade in contagem.items():
        nivel = 'erro' if codigo == 'img_corrompida' else 'aviso'
        itens.append(_item(nivel, codigo, contexto=contexto, quantidade=quantidade))


def validar_publicacao(slug: str, *, formato: str = 'epub', versao: str = '2.0',
                       roteiro: int | str | None = None, tipo_documento: str = 'roteiro') -> dict:
    """Produz diagnóstico JSON serializável para os mesmos parâmetros de exportação.

    Falhas de leitura de um capítulo/roteiro são reportadas como erros em vez de
    interromper o checklist. Não altera/limpa dados nem corrige conteúdo.
    """
    projeto = obter_projeto(slug)
    pasta = obter_pasta_projeto(slug)
    eh_roteiro = projeto.get('tipo') == 'roteiro'
    formato = str(formato or '').strip().lower()
    versao = str(versao or '').strip()
    tipo_documento = str(tipo_documento or '').strip()
    itens: list[dict] = []
    formatos = FORMATOS_ROTEIRO if eh_roteiro else FORMATOS_LIVRO
    if formato not in formatos:
        itens.append(_item('erro', 'formato_invalido'))
    if not eh_roteiro and formato == 'epub' and versao not in ('2.0', '3.0'):
        itens.append(_item('erro', 'versao_invalida'))
    if eh_roteiro and tipo_documento not in TIPOS_DOCUMENTO:
        itens.append(_item('erro', 'tipo_documento_invalido'))

    if not str(projeto.get('titulo') or '').strip():
        itens.append(_item('erro', 'titulo_ausente'))
    if not str(projeto.get('autor') or '').strip():
        itens.append(_item('aviso', 'autor_ausente'))
    if not eh_roteiro and formato == 'epub' and not str(projeto.get('descricao') or '').strip():
        itens.append(_item('aviso', 'sinopse_ausente'))
    if not str(projeto.get('idioma') or '').strip():
        itens.append(_item('aviso', 'idioma_ausente'))

    if not eh_roteiro and formato in ('epub', 'docx', 'pdf'):
        capa = pasta / 'cover.jpg'
        if not capa.exists() and formato == 'epub':
            itens.append(_item('aviso', 'capa_ausente'))
        elif capa.exists():
            try:
                with Image.open(capa) as img:
                    img.verify()
            except (UnidentifiedImageError, OSError, ValueError):
                itens.append(_item('erro', 'capa_corrompida'))

    if eh_roteiro:
        try:
            numero = int(roteiro)
            if numero < 1:
                raise ValueError
        except (ValueError, TypeError):
            itens.append(_item('erro', 'roteiro_nao_selecionado'))
            numero = None
        documentos = [('roteiro', numero, None)] if numero is not None else []
    else:
        documentos = [('livro', item['id'], item) for item in projeto.get('capitulos', [])[:MAX_DOCUMENTOS_ANALISADOS]]
        if not documentos:
            itens.append(_item('erro' if formato == 'xhtml' else 'aviso',
                               'sem_capitulos_xhtml' if formato == 'xhtml' else 'sem_capitulos'))
        if len(projeto.get('capitulos', [])) > MAX_DOCUMENTOS_ANALISADOS:
            itens.append(_item('erro', 'limite_documentos'))

    nomes = Counter()
    analisados = 0
    for tipo, numero, info in documentos:
        try:
            documento = ler_roteiro(pasta, numero) if tipo == 'roteiro' else ler_capitulo(pasta, numero)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            itens.append(_item('erro', 'documento_inacessivel', contexto=f'{tipo} #{numero}'))
            continue
        analisados += 1
        titulo = str(documento.get('titulo') or (info or {}).get('titulo') or '').strip()
        contexto = titulo or f'{tipo} #{numero}'
        if not titulo:
            itens.append(_item('aviso', 'capitulo_sem_titulo', contexto=contexto))
        if tipo == 'livro' and titulo:
            nomes[titulo.casefold()] += 1
        html = _extrair_conteudo(documento)
        soup = BeautifulSoup(html, 'html.parser')
        for ignorar in soup(['script', 'style', 'noscript']):
            ignorar.decompose()
        texto = soup.get_text(' ', strip=True)
        if not texto and not soup.find('img'):
            itens.append(_item('aviso', 'documento_vazio', contexto=contexto))
        _checar_imagens(soup, contexto=contexto, formato=formato, itens=itens)
        try:
            editorial = ler_revisao_editorial(pasta, tipo, numero)
            pendentes = sum(1 for item in editorial.get('itens', []) if item.get('estado') == 'pendente')
            if pendentes:
                itens.append(_item('aviso', 'revisoes_pendentes', contexto=contexto, quantidade=pendentes))
        except (OSError, ValueError, TypeError):
            itens.append(_item('aviso', 'revisao_indisponivel', contexto=contexto))

    if any(quantidade > 1 for quantidade in nomes.values()):
        itens.append(_item('aviso', 'titulos_repetidos'))

    erros = sum(item['nivel'] == 'erro' for item in itens)
    avisos = len(itens) - erros
    # Identifica o diagnóstico específico aceito pelo autor. A exportação
    # revalida os dados no servidor e rejeita confirmações desatualizadas.
    assinatura = sha256(json.dumps({
        'formato': formato, 'versao': versao, 'tipo_documento': tipo_documento,
        'roteiro': roteiro, 'itens': itens,
    }, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')).hexdigest()
    return {
        'assinatura': assinatura,
        'ok': True,
        'aprovado': erros == 0,
        'erros': erros,
        'avisos': avisos,
        'documentos': analisados,
        'formato': formato,
        'itens': itens,
    }


def conferir_arquivo_exportado(caminho: Path, formato: str) -> None:
    """Verifica assinatura e componentes essenciais do resultado, sem alterar arquivos.

    Lança ValueError com mensagem clara caso a exportação tenha gerado arquivo
    incompleto/corrompido; não equivale a validador formal EPUBCheck.
    """
    arquivo = Path(caminho)
    if formato == 'xhtml':
        if not arquivo.is_dir() or not list(arquivo.glob('*.xhtml')):
            raise ValueError(_mensagem('artifact_invalid'))
        return
    if not arquivo.is_file() or arquivo.stat().st_size < 5:
        raise ValueError(_mensagem('artifact_invalid'))
    if formato == 'pdf':
        with arquivo.open('rb') as f:
            if f.read(5) != b'%PDF-':
                raise ValueError(_mensagem('artifact_invalid'))
        return
    if formato not in {'epub', 'docx'}:
        raise ValueError(_mensagem('artifact_invalid'))
    try:
        with ZipFile(arquivo) as zf:
            if zf.testzip() is not None:
                raise ValueError(_mensagem('artifact_invalid'))
            nomes = set(zf.namelist())
            if formato == 'docx':
                requeridos = {'[Content_Types].xml', 'word/document.xml'}
                if not requeridos.issubset(nomes):
                    raise ValueError(_mensagem('artifact_invalid'))
            else:
                requeridos = {'mimetype', 'META-INF/container.xml', 'Misc/content.opf'}
                if not requeridos.issubset(nomes) or zf.read('mimetype') != b'application/epub+zip':
                    raise ValueError(_mensagem('artifact_invalid'))
                if zf.infolist()[0].filename != 'mimetype' or zf.infolist()[0].compress_type != 0:
                    raise ValueError(_mensagem('artifact_invalid'))
                opf = ElementTree.fromstring(zf.read('Misc/content.opf'))
                ns = {'opf': 'http://www.idpf.org/2007/opf'}
                manifesto = opf.find('opf:manifest', ns)
                if manifesto is None:
                    raise ValueError(_mensagem('artifact_invalid'))
                for elemento in manifesto.findall('opf:item', ns):
                    href = elemento.attrib.get('href', '')
                    # Resolução do item relativo ao OPF, situado em Misc/.
                    from posixpath import normpath
                    destino = normpath('Misc/' + href)
                    if not href or destino.startswith('../') or destino not in nomes:
                        raise ValueError(_mensagem('artifact_invalid'))
    except (BadZipFile, OSError, ElementTree.ParseError, KeyError) as exc:
        raise ValueError(_mensagem('artifact_invalid')) from exc
