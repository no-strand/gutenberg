"""Exporta snapshots estruturados do projeto no formato binário .gut.

"""

from __future__ import annotations

import base64
import binascii
import gzip
import hashlib
import json
import math
import re
import struct
from io import BytesIO
from urllib.parse import unquote_to_bytes, urlsplit
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import msgpack
from bs4 import BeautifulSoup

from .revisao_editorial import (
    ler as ler_revisao_editorial, importar_estado as importar_revisao_editorial,
    MAX_ITENS as MAX_REVISAO_ITENS, MAX_VERSOES as MAX_REVISAO_VERSOES,
    MAX_HTML as MAX_REVISAO_HTML,
)
from .manipulador_capitulos import criar_capitulo, ler_capitulo, salvar_capitulo
from .manipulador_projetos import atualizar_metadados_projeto, obter_pasta_projeto, obter_projeto
from .manipulador_roteiros import criar_roteiro, ler_roteiro, salvar_roteiro, atualizar_roteiro_info
from .manipulador_recursos_projeto import ler_recursos_projeto, mesclar_recursos_importados, normalizar_recursos
from .utilidades import APP_VERSAO, agora_iso, nome_seguro, obter_pasta_exportacao_projeto
from .logging_config import obter_logger, registrar_etapa
logger = obter_logger(__name__)

MAGIC = b"GUT1"
FORMATO_VERSAO = 1
ALGORITMO_COMPRESSAO = 1  # gzip
ARQUIVO_VERSAO = 1


@registrar_etapa
def _texto_simples_html(html: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        html: Conteúdo HTML já editado ou normalizado pela aplicação.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


@registrar_etapa
def _metadados_base_projeto(projeto: dict[str, Any]) -> dict[str, Any]:
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
    return {
        "slug": projeto.get("slug"),
        "titulo": projeto.get("titulo"),
        "descricao": projeto.get("descricao") or "",
        "autor": projeto.get("autor") or "",
        "tags": list(projeto.get("tags") or []),
        "idioma": projeto.get("idioma") or "pt-BR",
        "tipo": projeto.get("tipo") or "livro",
        "contatos": projeto.get("contatos") or "",
        "informacoes_adicionais": projeto.get("informacoes_adicionais") or "",
        "data_criacao": projeto.get("data_criacao"),
        "data_atualizacao": projeto.get("data_atualizacao"),
    }


@registrar_etapa
def _empacotar_payload(payload: dict[str, Any], destino: Path) -> Path:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        payload: Valor usado pela rotina para compor a operação de empacotar payload.
        destino: Valor usado pela rotina para compor a operação de empacotar payload.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    bruto = msgpack.packb(payload, use_bin_type=True)
    comprimido = gzip.compress(bruto, compresslevel=9, mtime=0)
    sha256 = hashlib.sha256(comprimido).digest()
    cabecalho = MAGIC + struct.pack("<BBHQ", FORMATO_VERSAO, ALGORITMO_COMPRESSAO, 0, len(comprimido)) + sha256
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(cabecalho + comprimido)
    return destino


@registrar_etapa
def _nome_base_destino(projeto: dict[str, Any]) -> str:
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
    return nome_seguro(str(projeto.get("titulo") or projeto.get("slug") or "projeto"))


@registrar_etapa
def exportar_gut_capitulos(slug: str) -> Path:
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
    if projeto.get("tipo") != "livro":
        raise ValueError("Projeto incompatível para salvar capítulos.")

    pasta_projeto = obter_pasta_projeto(slug)
    capitulos_payload = []
    for item in projeto.get("capitulos") or []:
        capitulo = ler_capitulo(pasta_projeto, int(item["id"]))
        html = str(capitulo.get("html_editor") or (capitulo.get("paragrafos") or [""])[0] or "")
        revisao_editorial = ler_revisao_editorial(pasta_projeto, "livro", int(item["id"]), incluir_html=True)
        _validar_revisao_editorial(revisao_editorial, f"capítulo {item['id']}")
        capitulos_payload.append({
            "id": int(item["id"]),
            "titulo": capitulo.get("titulo") or "",
            "html": html,
            "texto": _texto_simples_html(html),
            "data_criacao": capitulo.get("data_criacao"),
            "data_atualizacao": capitulo.get("data_atualizacao"),
            "revisao_editorial": revisao_editorial,
        })

    payload = {
        "container": "gutenberg_gut",
        "schema_version": ARQUIVO_VERSAO,
        "exportado_em": agora_iso(),
        "app_versao": APP_VERSAO,
        "tipo_arquivo": "livro",
        "projeto": _metadados_base_projeto(projeto),
        "conteudo": {
            "quantidade_capitulos": len(capitulos_payload),
            "capitulos": capitulos_payload,
        },
    }

    validar_payload_gut(payload)
    pasta_destino = obter_pasta_exportacao_projeto(str(projeto.get("titulo") or slug))
    destino = pasta_destino / f"{_nome_base_destino(projeto)}_capitulos.gut"
    return _empacotar_payload(payload, destino)


@registrar_etapa
def exportar_gut_roteiro(slug: str, numero_roteiro: int | None) -> Path:
    """
    Conduz a exportação dos dados do projeto para o formato esperado, preparando o conteúdo e delegando etapas auxiliares quando necessário.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        numero_roteiro: Valor usado pela rotina para compor a operação de exportar gut roteiro.

    Retorno:
        O caminho do arquivo exportado ou uma estrutura com informações da exportação.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    projeto = obter_projeto(slug)
    if projeto.get("tipo") != "roteiro":
        raise ValueError("Projeto incompatível para salvar roteiro.")
    if numero_roteiro is None:
        raise FileNotFoundError("Roteiro não informado para exportação .gut.")

    pasta_projeto = obter_pasta_projeto(slug)
    roteiro = ler_roteiro(pasta_projeto, int(numero_roteiro))
    html = str(roteiro.get("html_editor") or (roteiro.get("paragrafos") or [""])[0] or "")
    titulo_roteiro = str(roteiro.get("titulo") or f"roteiro_{numero_roteiro}")
    revisao_editorial = ler_revisao_editorial(pasta_projeto, "roteiro", int(numero_roteiro), incluir_html=True)
    _validar_revisao_editorial(revisao_editorial, f"roteiro {numero_roteiro}")

    payload = {
        "container": "gutenberg_gut",
        "schema_version": ARQUIVO_VERSAO,
        "exportado_em": agora_iso(),
        "app_versao": APP_VERSAO,
        "tipo_arquivo": "roteiro",
        "projeto": _metadados_base_projeto(projeto),
        "conteudo": {
            "roteiro": {
                "id": int(numero_roteiro),
                "titulo": titulo_roteiro,
                "tipo_roteiro": roteiro.get("tipo_roteiro") or "spec_script",
                "cabecalho": roteiro.get("cabecalho") or "",
                "rodape": roteiro.get("rodape") or "",
                "prefixo_cena": roteiro.get("prefixo_cena") or "0",
                "numeracao_inicial": int(roteiro.get("numeracao_inicial") or 1),
                "logline": roteiro.get("logline") or "",
                "sinopse": roteiro.get("sinopse") or "",
                "genero": roteiro.get("genero") or "",
                "copyright": bool(roteiro.get("copyright")),
                "personagens": list(roteiro.get("personagens") or []),
                "locais": list(roteiro.get("locais") or []),
                "catalogo_personagens": list(roteiro.get("catalogo_personagens") or []),
                "catalogo_locais": list(roteiro.get("catalogo_locais") or []),
                "html": html,
                "texto": _texto_simples_html(html),
                "data_criacao": roteiro.get("data_criacao"),
                "data_atualizacao": roteiro.get("data_atualizacao"),
                "revisao_editorial": revisao_editorial,
            }
        },
    }

    validar_payload_gut(payload)
    pasta_destino = obter_pasta_exportacao_projeto(str(projeto.get("titulo") or slug))
    destino = pasta_destino / f"{_nome_base_destino(projeto)}_{nome_seguro(titulo_roteiro)}.gut"
    return _empacotar_payload(payload, destino)


@registrar_etapa
def exportar_gutr_recursos(slug: str) -> Path:
    """Exporta todos os recursos atuais do projeto para um pacote .gutr."""
    projeto = obter_projeto(slug)
    pasta_projeto = obter_pasta_projeto(slug)
    recursos = normalizar_recursos(ler_recursos_projeto(pasta_projeto))
    payload = {
        "container": "gutenberg_gutr",
        "schema_version": ARQUIVO_VERSAO,
        "exportado_em": agora_iso(),
        "app_versao": APP_VERSAO,
        "tipo_arquivo": "recursos",
        "projeto": _metadados_base_projeto(projeto),
        "conteudo": {
            "recursos": recursos,
            "quantidades": {
                "informacoes": len(recursos.get("informacoes") or []),
                "fluxogramas": len(recursos.get("fluxos") or []),
                "balões_fluxo": sum(len((fluxo or {}).get("nodes") or []) for fluxo in (recursos.get("fluxos") or [])),
                "ligacoes_fluxo": sum(len((fluxo or {}).get("edges") or []) for fluxo in (recursos.get("fluxos") or [])),
                "personagens": len(recursos.get("personagens") or []),
                "lugares": len(recursos.get("lugares") or []),
                "anotacoes": len(recursos.get("anotacoes") or []),
                "cenas": len((recursos.get("planejamento") or {}).get("cenas") or []),
                "fontes": len((recursos.get("planejamento") or {}).get("fontes") or []),
            },
        },
    }
    validar_payload_gutr(payload)
    pasta_destino = obter_pasta_exportacao_projeto(str(projeto.get("titulo") or slug))
    destino = pasta_destino / f"{_nome_base_destino(projeto)}_recursos.gutr"
    return _empacotar_payload(payload, destino)


@registrar_etapa
def ler_cabecalho_gut(caminho: str | Path) -> dict[str, Any]:
    """
    Lê conteúdo persistido e devolve dados estruturados para consumo pelo restante da aplicação.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        caminho: Caminho de arquivo ou pasta usado como origem ou destino da operação.

    Retorno:
        Conteúdo estruturado lido a partir da origem informada.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    bruto = Path(caminho).read_bytes()
    minimo = 4 + 1 + 1 + 2 + 8 + 32
    if len(bruto) < minimo:
        raise ValueError("Arquivo Gutenberg inválido ou corrompido.")

    if bruto[:4] != MAGIC:
        raise ValueError("Assinatura do arquivo inválida.")

    versao, compressao, _reservado, tamanho = struct.unpack("<BBHQ", bruto[4:16])
    if versao != FORMATO_VERSAO:
        raise ValueError("Versão de arquivo incompatível.")
    if compressao != ALGORITMO_COMPRESSAO:
        raise ValueError("Algoritmo de compressão não suportado.")

    hash_esperado = bruto[16:48]
    if len(bruto) != 48 + tamanho:
        raise ValueError("Tamanho do arquivo inválido: conteúdo truncado ou dados extras.")
    payload = bruto[48:]
    if hashlib.sha256(payload).digest() != hash_esperado:
        raise ValueError("Integridade do arquivo inválida.")

    try:
        descompactado = gzip.decompress(payload)
        dados = msgpack.unpackb(descompactado, raw=False, strict_map_key=False)
    except Exception as exc:
        raise ValueError("Conteúdo compactado inválido ou corrompido.") from exc
    if not isinstance(dados, dict):
        raise ValueError("O conteúdo do arquivo não contém um objeto válido.")
    return dados


def _validar_metadados_projeto(projeto: dict[str, Any]) -> None:
    """Impede que metadados incompatíveis sejam convertidos ou descartados na importação."""
    for campo in ("slug", "titulo", "descricao", "autor", "idioma", "tipo", "contatos", "informacoes_adicionais"):
        valor = projeto.get(campo)
        if valor is not None and not isinstance(valor, str):
            raise ValueError(f"O metadado de projeto '{campo}' é inválido.")
    tags = projeto.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise ValueError("A lista de tags do projeto é inválida.")
    for campo in ("data_criacao", "data_atualizacao"):
        if projeto.get(campo) is not None and not isinstance(projeto.get(campo), str):
            raise ValueError(f"O metadado de projeto '{campo}' é inválido.")
    tipo = projeto.get("tipo")
    if tipo is not None and tipo not in {"livro", "roteiro"}:
        raise ValueError("O tipo de projeto nos metadados é inválido.")


def _validar_revisao_editorial(revisao: Any, nome: str) -> None:
    """Valida integralmente o estado editorial para que o importador não pule registros."""
    if revisao is None:
        return
    if not isinstance(revisao, dict):
        raise ValueError(f"A revisão editorial de {nome} é inválida.")
    itens = revisao.get("itens", [])
    versoes = revisao.get("versoes", [])
    if not isinstance(itens, list) or not isinstance(versoes, list):
        raise ValueError(f"As listas da revisão editorial de {nome} são inválidas.")
    if len(itens) > MAX_REVISAO_ITENS or len(versoes) > MAX_REVISAO_VERSOES:
        raise ValueError(f"A revisão editorial de {nome} excede os limites permitidos.")

    estados = {"pendente", "aceito", "rejeitado", "resolvido"}
    for indice, item in enumerate(itens, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"O comentário {indice} da revisão editorial de {nome} é inválido.")
        if item.get("tipo") not in {"comentario", "sugestao"} or item.get("estado") not in estados:
            raise ValueError(f"O tipo ou estado do comentário {indice} de {nome} é inválido.")
        trecho = item.get("trecho")
        if not isinstance(trecho, str) or not trecho.strip() or len(trecho) > 2000:
            raise ValueError(f"O trecho do comentário {indice} de {nome} é inválido.")
        limites = (("nota", 4000), ("substituicao", 2000), ("prefixo", 120), ("sufixo", 120))
        for campo, limite in limites:
            valor = item.get(campo, "")
            if not isinstance(valor, str) or len(valor) > limite:
                raise ValueError(f"O campo {campo} do comentário {indice} de {nome} é inválido.")
        if item["tipo"] == "comentario" and not item.get("nota", "").strip():
            raise ValueError(f"O comentário {indice} de {nome} não contém uma anotação.")
        if item["tipo"] == "sugestao" and not item.get("substituicao", "").strip():
            raise ValueError(f"A sugestão {indice} de {nome} não contém texto substituto.")
        inicio = item.get("inicio", 0)
        if type(inicio) is not int or not 0 <= inicio <= 15_000_000:
            raise ValueError(f"A posição do comentário {indice} de {nome} é inválida.")
        for campo in ("criado_em", "atualizado_em"):
            valor = item.get(campo, "")
            if not isinstance(valor, str) or len(valor) > 60:
                raise ValueError(f"O campo {campo} do comentário {indice} de {nome} é inválido.")

    for indice, versao in enumerate(versoes, start=1):
        if not isinstance(versao, dict):
            raise ValueError(f"A versão {indice} da revisão editorial de {nome} é inválida.")
        html = versao.get("html")
        if not isinstance(html, str) or len(html.encode("utf-8")) > MAX_REVISAO_HTML:
            raise ValueError(f"O HTML da versão {indice} de {nome} é inválido ou excede o limite.")
        for campo, limite in (("titulo", 200), ("rotulo", 120), ("criado_em", 60)):
            valor = versao.get(campo, "")
            if not isinstance(valor, str) or len(valor) > limite:
                raise ValueError(f"O campo {campo} da versão {indice} de {nome} é inválido.")
        hash_versao = versao.get("hash")
        if hash_versao is not None:
            hash_calculado = hashlib.sha256(html.encode("utf-8")).hexdigest()
            if not isinstance(hash_versao, str) or not re.fullmatch(r"[0-9a-f]{64}", hash_versao) or hash_versao != hash_calculado:
                raise ValueError(f"O hash da versão {indice} de {nome} não corresponde ao conteúdo HTML.")


def _validar_imagem_referencia_data_url(valor: str, nome: str) -> None:
    """Valida referências raster/SVG sem aceitar bytes truncados silenciosamente."""
    from .manipulador_recursos_projeto import (
        MAX_IMAGEM_DATA_URL, MAX_IMAGEM_DATA_URL_ENTRADA,
    )

    if len(valor) > MAX_IMAGEM_DATA_URL_ENTRADA:
        raise ValueError(f"A imagem de referência de {nome} excede o limite de tamanho.")
    if not valor.startswith("data:image/"):
        raise ValueError(f"A imagem de referência de {nome} não usa uma URL de imagem válida.")

    cabecalho, separador, conteudo = valor.partition(",")
    if not separador:
        # O limite exato é compatível com arquivos cortados pela versão antiga;
        # a normalização os marca para reenvio em vez de exibi-los como válidos.
        if len(valor) == MAX_IMAGEM_DATA_URL:
            return
        raise ValueError(f"A imagem de referência de {nome} está malformada.")

    mime = cabecalho[5:].split(";", 1)[0].strip().lower()
    eh_base64 = ";base64" in cabecalho.lower()
    if not eh_base64 and mime != "image/svg+xml":
        raise ValueError(f"A imagem de referência de {nome} usa codificação não suportada.")

    try:
        dados = base64.b64decode(conteudo, validate=True) if eh_base64 else unquote_to_bytes(conteudo)
    except (binascii.Error, ValueError) as exc:
        if len(valor) == MAX_IMAGEM_DATA_URL:
            return
        raise ValueError(f"A imagem de referência de {nome} contém dados inválidos.") from exc

    if not dados:
        if len(valor) == MAX_IMAGEM_DATA_URL:
            return
        raise ValueError(f"A imagem de referência de {nome} está vazia.")

    if mime == "image/svg+xml":
        try:
            raiz = ET.fromstring(dados)
        except ET.ParseError as exc:
            if len(valor) == MAX_IMAGEM_DATA_URL:
                return
            raise ValueError(f"O SVG da imagem de referência de {nome} está incompleto.") from exc
        if raiz.tag.split("}")[-1].lower() != "svg":
            raise ValueError(f"O arquivo de referência de {nome} não contém um SVG válido.")
        return

    try:
        from PIL import Image
        arquivo = BytesIO(dados)
        imagem = Image.open(arquivo)
        largura, altura = imagem.size
        if largura <= 0 or altura <= 0 or largura * altura > 50_000_000:
            raise ValueError(f"A imagem de referência de {nome} possui dimensões inválidas.")
        imagem.verify()
        arquivo.seek(0)
        imagem = Image.open(arquivo)
        imagem.load()
    except ValueError:
        raise
    except Exception as exc:
        if len(valor) == MAX_IMAGEM_DATA_URL:
            return
        raise ValueError(f"A imagem de referência de {nome} está incompleta ou corrompida.") from exc


@registrar_etapa
def validar_payload_gut(payload: dict[str, Any]) -> dict[str, Any]:
    """Valida todo o conteúdo de um .gut antes de alterar o projeto de destino."""
    if not isinstance(payload, dict):
        raise ValueError("Arquivo Gutenberg inválido.")
    if payload.get("container") != "gutenberg_gut":
        raise ValueError("Arquivo incompatível com o Gutenberg.")
    versao_schema = payload.get("schema_version", ARQUIVO_VERSAO)
    if type(versao_schema) is not int or versao_schema != ARQUIVO_VERSAO:
        raise ValueError(f"Versão de estrutura .gut não suportada: {versao_schema!r}.")

    tipo = str(payload.get("tipo_arquivo") or "").strip().lower()
    if tipo not in {"livro", "roteiro"}:
        raise ValueError("Tipo de arquivo inválido.")
    projeto = payload.get("projeto") or {}
    conteudo = payload.get("conteudo") or {}
    if not isinstance(projeto, dict) or not isinstance(conteudo, dict):
        raise ValueError("Estrutura de metadados ou conteúdo inválida.")
    _validar_metadados_projeto(projeto)

    if tipo == "livro":
        capitulos = conteudo.get("capitulos")
        if not isinstance(capitulos, list):
            raise ValueError("A lista de capítulos do arquivo .gut é inválida.")
        quantidade = conteudo.get("quantidade_capitulos")
        if quantidade is not None and (type(quantidade) is not int or quantidade != len(capitulos)):
            raise ValueError("A quantidade de capítulos não corresponde ao conteúdo do arquivo .gut.")
        for indice, item in enumerate(capitulos, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"O capítulo {indice} possui uma estrutura inválida.")
            if not isinstance(item.get("titulo", ""), str) or not isinstance(item.get("html", ""), str):
                raise ValueError(f"O título ou conteúdo HTML do capítulo {indice} é inválido.")
            for chave in ("data_criacao", "data_atualizacao"):
                if item.get(chave) is not None and not isinstance(item.get(chave), str):
                    raise ValueError(f"O campo {chave} do capítulo {indice} é inválido.")
            _validar_revisao_editorial(item.get("revisao_editorial"), f"capítulo {indice}")
    else:
        roteiro = conteudo.get("roteiro")
        if not isinstance(roteiro, dict):
            raise ValueError("O conteúdo do roteiro no arquivo .gut é inválido.")
        campos_texto = ("titulo", "html", "cabecalho", "rodape", "prefixo_cena", "logline", "sinopse", "genero")
        for chave in campos_texto:
            if roteiro.get(chave) is not None and not isinstance(roteiro.get(chave), str):
                raise ValueError(f"O campo {chave} do roteiro é inválido.")
        for chave in ("personagens", "locais"):
            valor = roteiro.get(chave, [])
            if not isinstance(valor, list) or any(not isinstance(nome, str) for nome in valor):
                raise ValueError(f"A lista {chave} do roteiro é inválida.")
        for chave in ("catalogo_personagens", "catalogo_locais"):
            itens = roteiro.get(chave, [])
            if not isinstance(itens, list):
                raise ValueError(f"A lista {chave} do roteiro é inválida.")
            for indice, item in enumerate(itens, start=1):
                if isinstance(item, dict):
                    nome = item.get("nome", "")
                    descricao = item.get("descricao", "")
                elif isinstance(item, str):
                    nome, descricao = item, ""
                else:
                    raise ValueError(f"O item {indice} de {chave} é inválido.")
                if not isinstance(nome, str) or not nome.strip() or not isinstance(descricao, str):
                    raise ValueError(f"O nome ou descrição do item {indice} de {chave} é inválido.")
        try:
            numero_inicial_bruto = roteiro.get("numeracao_inicial", 1)
            if isinstance(numero_inicial_bruto, bool):
                raise ValueError
            numero_inicial = int(numero_inicial_bruto or 1)
            if str(numero_inicial_bruto).strip() not in {str(numero_inicial), f"{numero_inicial}.0"}:
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise ValueError("A numeração inicial do roteiro é inválida.") from exc
        if numero_inicial < 1:
            raise ValueError("A numeração inicial do roteiro deve ser maior que zero.")
        if roteiro.get("tipo_roteiro") is not None and roteiro.get("tipo_roteiro") not in {
            "spec_script", "shooting_script", "revised_draft", "production_draft", "continuity_script"
        }:
            raise ValueError("O tipo de roteiro não é suportado.")
        if roteiro.get("copyright") is not None and not isinstance(roteiro.get("copyright"), bool):
            raise ValueError("A configuração de copyright do roteiro é inválida.")
        for chave in ("data_criacao", "data_atualizacao"):
            if roteiro.get(chave) is not None and not isinstance(roteiro.get(chave), str):
                raise ValueError(f"O campo {chave} do roteiro é inválido.")
        _validar_revisao_editorial(roteiro.get("revisao_editorial"), "roteiro")
    return payload


@registrar_etapa
def validar_payload_gutr(payload: dict[str, Any]) -> dict[str, Any]:
    """Valida recursos, limites e vínculos de um .gutr antes da mesclagem."""
    if not isinstance(payload, dict):
        raise ValueError("Arquivo de recursos Gutenberg inválido.")
    if payload.get("container") != "gutenberg_gutr":
        raise ValueError("Arquivo incompatível com recursos do Gutenberg.")
    versao_schema = payload.get("schema_version", ARQUIVO_VERSAO)
    if type(versao_schema) is not int or versao_schema != ARQUIVO_VERSAO:
        raise ValueError(f"Versão de estrutura .gutr não suportada: {versao_schema!r}.")
    if str(payload.get("tipo_arquivo") or "").strip().lower() != "recursos":
        raise ValueError("Tipo de arquivo de recursos inválido.")
    conteudo = payload.get("conteudo") or {}
    recursos = conteudo.get("recursos") if isinstance(conteudo, dict) else None
    if not isinstance(recursos, dict):
        raise ValueError("Estrutura de recursos inválida.")
    projeto = payload.get("projeto") or {}
    if not isinstance(projeto, dict):
        raise ValueError("Os metadados do projeto no .gutr são inválidos.")
    _validar_metadados_projeto(projeto)

    def _lista(obj: dict[str, Any], chave: str, limite: int, aliases: tuple[str, ...] = ()) -> list[Any]:
        valor = obj.get(chave)
        if valor is None:
            for alias in aliases:
                if obj.get(alias) is not None:
                    valor = obj.get(alias)
                    break
        if valor is None:
            return []
        if not isinstance(valor, list):
            raise ValueError(f"A lista de recursos {chave} é inválida.")
        if len(valor) > limite:
            raise ValueError(f"O arquivo .gutr excede o limite de {limite} itens em {chave}.")
        return valor

    def _texto(item: dict[str, Any], campo: str, limite: int, nome: str, *, obrigatorio: bool = False) -> str:
        valor = item.get(campo, "")
        if not isinstance(valor, str) or "\x00" in valor or len(valor) > limite or (obrigatorio and not valor.strip()):
            raise ValueError(f"O campo {campo} de {nome} é inválido.")
        return valor

    def _id(item: dict[str, Any], campo: str, nome: str, *, obrigatorio: bool = False) -> str:
        valor = item.get(campo)
        if valor is None and not obrigatorio:
            return ""
        if not isinstance(valor, str) or not valor or len(valor) > 80 or "\x00" in valor:
            raise ValueError(f"O identificador {campo} de {nome} é inválido.")
        return valor

    def _datas(item: dict[str, Any], nome: str) -> None:
        for campo in ("data_criacao", "data_atualizacao"):
            valor = item.get(campo)
            if valor is not None and (not isinstance(valor, str) or "\x00" in valor or len(valor) > 40):
                raise ValueError(f"O campo {campo} de {nome} é inválido.")

    ids_info: set[str] = set()
    abas_info = _lista(recursos, "informacoes_abas", 7, ("abas_informacoes",))
    if not abas_info and isinstance(recursos.get("informacoes"), list):
        paginas_legadas = _lista(recursos, "informacoes", 300)
        for indice, pagina in enumerate(paginas_legadas, start=1):
            if not isinstance(pagina, dict):
                raise ValueError(f"A página de Informações {indice} é inválida.")
            pid = _id(pagina, "id", f"página de Informações {indice}")
            _texto(pagina, "titulo", 90, f"página de Informações {indice}")
            _texto(pagina, "html", 1_200_000, f"página de Informações {indice}")
            if pid and pid in ids_info:
                raise ValueError(f"O arquivo .gutr contém ID de página de Informações duplicado: {pid}.")
            if pid:
                ids_info.add(pid)
            _datas(pagina, f"página de Informações {indice}")
    else:
        ids_abas_info: set[str] = set()
        for indice, aba in enumerate(abas_info, start=1):
            if not isinstance(aba, dict):
                raise ValueError(f"A aba de Informações {indice} é inválida.")
            aid = _id(aba, "id", f"aba de Informações {indice}")
            if aid and aid in ids_abas_info:
                raise ValueError("O arquivo .gutr contém IDs de abas de Informações duplicados.")
            if aid:
                ids_abas_info.add(aid)
            _texto(aba, "titulo", 60, f"aba de Informações {indice}")
            _datas(aba, f"aba de Informações {indice}")
            paginas = _lista(aba, "paginas", 300, ("pages", "informacoes"))
            for pagina_indice, pagina in enumerate(paginas, start=1):
                if not isinstance(pagina, dict):
                    raise ValueError(f"A página {pagina_indice} da aba de Informações {indice} é inválida.")
                pid = _id(pagina, "id", f"página {pagina_indice} de Informações")
                if pid and pid in ids_info:
                    raise ValueError(f"O arquivo .gutr contém ID de página de Informações duplicado: {pid}.")
                if pid:
                    ids_info.add(pid)
                _texto(pagina, "titulo", 90, f"página {pagina_indice} de Informações")
                _texto(pagina, "html", 1_200_000, f"página {pagina_indice} de Informações")
                _datas(pagina, f"página {pagina_indice} de Informações")

    ids_nos: set[str] = set()
    fluxos = _lista(recursos, "fluxos", 7)
    if not fluxos and recursos.get("fluxo") is not None:
        if not isinstance(recursos.get("fluxo"), dict):
            raise ValueError("O fluxograma principal do arquivo .gutr é inválido.")
        fluxos = [recursos["fluxo"]]
    ids_fluxos: set[str] = set()
    for indice, fluxo in enumerate(fluxos, start=1):
        if not isinstance(fluxo, dict):
            raise ValueError(f"O fluxograma {indice} é inválido.")
        fid = _id(fluxo, "id", f"fluxograma {indice}")
        if fid and fid in ids_fluxos:
            raise ValueError("O arquivo .gutr contém IDs de fluxograma duplicados.")
        if fid:
            ids_fluxos.add(fid)
        _texto(fluxo, "titulo", 60, f"fluxograma {indice}")
        _datas(fluxo, f"fluxograma {indice}")
        bruto = fluxo.get("fluxo") if isinstance(fluxo.get("fluxo"), dict) else fluxo
        nos = _lista(bruto, "nodes", 240)
        ligacoes = _lista(bruto, "edges", 500)
        ids_local: set[str] = set()
        for no_indice, no in enumerate(nos, start=1):
            if not isinstance(no, dict):
                raise ValueError(f"O bloco {no_indice} do fluxograma {indice} é inválido.")
            nid = _id(no, "id", f"bloco {no_indice} do fluxograma {indice}", obrigatorio=True)
            if nid in ids_nos:
                raise ValueError(f"O arquivo .gutr contém ID de bloco duplicado: {nid}.")
            ids_nos.add(nid)
            ids_local.add(nid)
            _texto(no, "titulo", 120, f"bloco {no_indice} do fluxograma {indice}")
            _texto(no, "texto", 4000, f"bloco {no_indice} do fluxograma {indice}")
            for campo, minimo, maximo in (("x", -5000, 5000), ("y", -5000, 5000), ("width", 170, 760), ("height", 96, 620)):
                valor = no.get(campo, {"x": 120, "y": 120, "width": 240, "height": 150}[campo])
                if isinstance(valor, bool):
                    raise ValueError(f"A geometria do bloco {no_indice} de {indice} é inválida.")
                try:
                    numero = float(valor)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"A geometria do bloco {no_indice} de {indice} é inválida.") from exc
                if not math.isfinite(numero) or not minimo <= numero <= maximo:
                    raise ValueError(f"A geometria do bloco {no_indice} de {indice} excede os limites permitidos.")
        ids_ligacoes: set[str] = set()
        for ligacao_indice, ligacao in enumerate(ligacoes, start=1):
            if not isinstance(ligacao, dict):
                raise ValueError(f"A ligação {ligacao_indice} do fluxograma {indice} é inválida.")
            origem = _texto(ligacao, "from", 80, f"ligação {ligacao_indice}", obrigatorio=True)
            destino = _texto(ligacao, "to", 80, f"ligação {ligacao_indice}", obrigatorio=True)
            if origem not in ids_local or destino not in ids_local or origem == destino:
                raise ValueError(f"A ligação {ligacao_indice} do fluxograma {indice} aponta para blocos inexistentes.")
            eid = _id(ligacao, "id", f"ligação {ligacao_indice}")
            if eid and eid in ids_ligacoes:
                raise ValueError(f"O fluxograma {indice} contém IDs de ligação duplicados.")
            if eid:
                ids_ligacoes.add(eid)
            for campo in ("fromSide", "toSide"):
                lado = ligacao.get(campo)
                if lado is not None and lado not in {"top", "right", "bottom", "left"}:
                    raise ValueError(f"O campo {campo} da ligação {ligacao_indice} é inválido.")

    # Catálogos: abas, itens, imagens e pertencimento de cada item.
    ids_catalogos: dict[str, set[str]] = {}
    for chave, chave_paginas, aliases_paginas, aliases_itens, permite_imagem in (
        ("personagens", "personagens_paginas", ("paginas_personagens",), (), True),
        ("lugares", "lugares_paginas", ("paginas_lugares",), ("locais",), True),
        ("anotacoes", "anotacoes_paginas", ("paginas_anotacoes",), ("notas", "notes"), False),
    ):
        paginas = _lista(recursos, chave_paginas, 7, aliases_paginas)
        ids_paginas: set[str] = set()
        ids_paginas_existentes: set[str] = set()
        for indice, pagina in enumerate(paginas, start=1):
            if not isinstance(pagina, dict):
                raise ValueError(f"A aba {indice} do catálogo {chave} é inválida.")
            pid = _id(pagina, "id", f"aba {indice} de {chave}")
            if pid and pid in ids_paginas:
                raise ValueError(f"O catálogo {chave} contém IDs de abas duplicados.")
            if pid:
                ids_paginas.add(pid)
                ids_paginas_existentes.add(pid)
            _texto(pagina, "titulo", 60, f"aba {indice} de {chave}")
            _datas(pagina, f"aba {indice} de {chave}")
        itens = _lista(recursos, chave, 400, aliases_itens)
        ids_itens: set[str] = set()
        nomes_por_pagina: set[tuple[str, str]] = set()
        for indice, item in enumerate(itens, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"O item {indice} do catálogo {chave} é inválido.")
            iid = _id(item, "id", f"item {indice} de {chave}")
            if iid and iid in ids_itens:
                raise ValueError(f"O catálogo {chave} contém IDs de itens duplicados.")
            if iid:
                ids_itens.add(iid)
            campo_nome = "nome" if item.get("nome") is not None else "titulo" if item.get("titulo") is not None else "name" if item.get("name") is not None else "title"
            nome = _texto(item, campo_nome, 80, f"item {indice} de {chave}", obrigatorio=True)
            campo_desc = "descricao" if item.get("descricao") is not None else "anotacao" if item.get("anotacao") is not None else "texto" if item.get("texto") is not None else "description" if item.get("description") is not None else "text"
            _texto(item, campo_desc, 4000, f"item {indice} de {chave}")
            pagina_id = item.get("pagina_id") or item.get("page_id") or item.get("pagina") or ""
            if pagina_id and (not isinstance(pagina_id, str) or len(pagina_id) > 80 or pagina_id not in ids_paginas_existentes):
                raise ValueError(f"O item {indice} do catálogo {chave} aponta para uma aba inexistente.")
            pagina_key = str(pagina_id or (next(iter(ids_paginas_existentes), "")))
            chave_nome = (pagina_key, nome.strip().casefold())
            if chave_nome in nomes_por_pagina:
                raise ValueError(f"O catálogo {chave} contém nomes duplicados na mesma aba.")
            nomes_por_pagina.add(chave_nome)
            imagem = item.get("imagem") or item.get("image") or ""
            if imagem is not None and not isinstance(imagem, str):
                raise ValueError(f"A imagem do item {indice} do catálogo {chave} é inválida.")
            if imagem:
                if not permite_imagem:
                    raise ValueError(f"O item {indice} de {chave} contém imagem, mas esse catálogo não aceita imagens.")
                _validar_imagem_referencia_data_url(imagem, f"item {indice} de {chave}")
            precisa_reenvio = item.get("imagem_necessita_reenvio", False)
            if not isinstance(precisa_reenvio, bool):
                raise ValueError(f"O indicador de reenvio de imagem do item {indice} de {chave} é inválido.")
            _datas(item, f"item {indice} de {chave}")
        ids_catalogos[chave] = ids_itens

    ocultos = recursos.get("ocultos")
    if ocultos is not None:
        if not isinstance(ocultos, dict):
            raise ValueError("A estrutura de itens ocultos do .gutr é inválida.")
        for chave in ("personagens", "lugares", "anotacoes"):
            nomes = ocultos.get(chave, [])
            if not isinstance(nomes, list) or len(nomes) > 400 or any(not isinstance(nome, str) or not nome.strip() or len(nome) > 80 for nome in nomes):
                raise ValueError(f"A lista de itens ocultos de {chave} é inválida.")
            if len({nome.strip().casefold() for nome in nomes}) != len(nomes):
                raise ValueError(f"A lista de itens ocultos de {chave} contém nomes duplicados.")

    planejamento = recursos.get("planejamento")
    if planejamento is not None:
        if not isinstance(planejamento, dict):
            raise ValueError("A estrutura de cenas e fontes do .gutr é inválida.")
        fontes = _lista(planejamento, "fontes", 300)
        cenas = _lista(planejamento, "cenas", 300)
        padrao_id = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
        ids_fontes: set[str] = set()
        ids_cenas: set[str] = set()
        for indice, fonte in enumerate(fontes, start=1):
            if not isinstance(fonte, dict):
                raise ValueError(f"A fonte {indice} do planejamento é inválida.")
            fid = fonte.get("id")
            if fid is not None and (not isinstance(fid, str) or not padrao_id.fullmatch(fid)):
                raise ValueError(f"O identificador da fonte {indice} é inválido.")
            if fid and fid in ids_fontes:
                raise ValueError("O planejamento contém IDs de fontes duplicados.")
            if fid:
                ids_fontes.add(fid)
            _texto(fonte, "titulo", 160, f"fonte {indice}", obrigatorio=True)
            if fonte.get("tipo", "outro") not in {"pagina_web", "livro", "artigo", "entrevista", "arquivo", "outro"}:
                raise ValueError(f"O tipo da fonte {indice} é inválido.")
            for campo, limite in (("autor", 160), ("citacao", 2000), ("notas", 6000), ("url", 2000)):
                _texto(fonte, campo, limite, f"fonte {indice}")
            url = fonte.get("url", "")
            if url:
                try:
                    parsed = urlsplit(url)
                    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or any(ch.isspace() for ch in parsed.netloc):
                        raise ValueError
                    if parsed.port is not None and not 1 <= parsed.port <= 65535:
                        raise ValueError
                except ValueError as exc:
                    raise ValueError(f"A URL da fonte {indice} é inválida.") from exc
            verificada = fonte.get("verificada", False)
            if not isinstance(verificada, bool) and verificada not in (0, 1):
                raise ValueError(f"O indicador de verificação da fonte {indice} é inválido.")
            _datas(fonte, f"fonte {indice}")
        for indice, cena in enumerate(cenas, start=1):
            if not isinstance(cena, dict):
                raise ValueError(f"A cena {indice} do planejamento é inválida.")
            cid = cena.get("id")
            if cid is not None and (not isinstance(cid, str) or not padrao_id.fullmatch(cid)):
                raise ValueError(f"O identificador da cena {indice} é inválido.")
            if cid and cid in ids_cenas:
                raise ValueError("O planejamento contém IDs de cenas duplicados.")
            if cid:
                ids_cenas.add(cid)
            _texto(cena, "titulo", 120, f"cena {indice}", obrigatorio=True)
            _texto(cena, "resumo", 6000, f"cena {indice}")
            for campo in ("objetivo", "conflito", "desfecho"):
                _texto(cena, campo, 2000, f"cena {indice}")
            if cena.get("status", "planejada") not in {"planejada", "em_andamento", "revisao", "concluida"}:
                raise ValueError(f"O status da cena {indice} é inválido.")
            for campo in ("personagens", "lugares", "anotacoes", "referencias", "paginas_info", "nos_fluxo"):
                refs = cena.get(campo, [])
                if not isinstance(refs, list) or len(refs) > 100:
                    raise ValueError(f"A lista {campo} da cena {indice} é inválida.")
                if any(not isinstance(ref, str) or not padrao_id.fullmatch(ref) for ref in refs):
                    raise ValueError(f"A lista {campo} da cena {indice} contém um identificador inválido.")
                if len(set(refs)) != len(refs):
                    raise ValueError(f"A lista {campo} da cena {indice} contém referências duplicadas.")
            if any(ref not in ids_fontes for ref in cena.get("referencias", [])):
                raise ValueError(f"A cena {indice} contém referências a fontes ausentes no arquivo .gutr.")
            if any(ref not in ids_info for ref in cena.get("paginas_info", [])):
                raise ValueError(f"A cena {indice} contém vínculos a páginas de Informações ausentes no arquivo .gutr.")
            if any(ref not in ids_nos for ref in cena.get("nos_fluxo", [])):
                raise ValueError(f"A cena {indice} contém vínculos a blocos de fluxograma ausentes no arquivo .gutr.")
            _datas(cena, f"cena {indice}")
    return payload

@registrar_etapa
def ler_payload_gut(caminho: str | Path) -> dict[str, Any]:
    """
    Lê conteúdo persistido e devolve dados estruturados para consumo pelo restante da aplicação.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        caminho: Caminho de arquivo ou pasta usado como origem ou destino da operação.

    Retorno:
        Conteúdo estruturado lido a partir da origem informada.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return validar_payload_gut(ler_cabecalho_gut(caminho))


@registrar_etapa
def ler_payload_gutr(caminho: str | Path) -> dict[str, Any]:
    """Lê e valida um arquivo .gutr."""
    return validar_payload_gutr(ler_cabecalho_gut(caminho))


@registrar_etapa
def importar_gutr_em_projeto(slug: str, caminho_gutr: str | Path) -> dict[str, Any]:
    """Importa um pacote .gutr e adiciona seus recursos ao projeto atual."""
    payload = ler_payload_gutr(caminho_gutr)
    recursos_payload = ((payload.get("conteudo") or {}).get("recursos") or {})
    pasta_projeto = obter_pasta_projeto(slug)
    normalizados = normalizar_recursos(recursos_payload)
    atualizados = mesclar_recursos_importados(pasta_projeto, normalizados)
    fluxos = normalizados.get("fluxos") or []
    planejamento = normalizados.get("planejamento") or {}
    return {
        "ok": True,
        "tipo_arquivo": "recursos",
        "slug": slug,
        "recursos": atualizados,
        "importados": {
            "informacoes": len(normalizados.get("informacoes") or []),
            "fluxogramas": len(fluxos),
            "balões_fluxo": sum(len((fluxo or {}).get("nodes") or []) for fluxo in fluxos),
            "ligacoes_fluxo": sum(len((fluxo or {}).get("edges") or []) for fluxo in fluxos),
            "personagens": len(normalizados.get("personagens") or []),
            "lugares": len(normalizados.get("lugares") or []),
            "anotacoes": len(normalizados.get("anotacoes") or []),
            "cenas": len(planejamento.get("cenas") or []),
            "fontes": len(planejamento.get("fontes") or []),
        },
    }


@registrar_etapa
def metadados_importaveis_projeto(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        payload: Valor usado pela rotina para compor a operação de metadados importaveis projeto.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    payload = validar_payload_gut(payload)
    projeto = payload.get("projeto") or {}
    tipo = str(payload.get("tipo_arquivo") or "livro")
    base = {
        "titulo": str(projeto.get("titulo") or "").strip(),
        "descricao": str(projeto.get("descricao") or "").strip(),
        "autor": str(projeto.get("autor") or "").strip(),
        "idioma": str(projeto.get("idioma") or "pt-BR").strip() or "pt-BR",
        "tipo": tipo,
    }
    # O .gut carrega os metadados editáveis comuns do projeto. O tipo limita
    # quais campos a interface usa, mas não deve causar perda de dados na cópia.
    base.update({
        "tags": [str(tag).strip() for tag in list(projeto.get("tags") or []) if str(tag).strip()],
        "contatos": str(projeto.get("contatos") or "").strip(),
        "informacoes_adicionais": str(projeto.get("informacoes_adicionais") or "").strip(),
    })
    return base


@registrar_etapa
def importar_gut_em_projeto(slug: str, caminho_gut: str | Path) -> dict[str, Any]:
    """
    Coordena a importação de conteúdo externo para dentro do projeto, normalizando os dados para o modelo usado pela aplicação.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        caminho_gut: Valor usado pela rotina para compor a operação de importar gut em projeto.

    Retorno:
        Um resumo do conteúdo importado e dos registros criados no projeto.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    payload = ler_payload_gut(caminho_gut)
    projeto_destino = obter_projeto(slug)
    tipo_arquivo = str(payload.get("tipo_arquivo") or "")
    if projeto_destino.get("tipo") != tipo_arquivo:
        raise ValueError("Tipo de arquivo incompatível com este projeto.")

    metadados = metadados_importaveis_projeto(payload)
    atualizacoes = {
        "titulo": metadados.get("titulo") or projeto_destino.get("titulo") or "",
        "descricao": metadados.get("descricao") or "",
        "autor": metadados.get("autor") or "",
        "idioma": metadados.get("idioma") or projeto_destino.get("idioma") or "pt-BR",
    }
    atualizacoes.update({
        "tags": list(metadados.get("tags") or []),
        "contatos": metadados.get("contatos") or "",
        "informacoes_adicionais": metadados.get("informacoes_adicionais") or "",
    })
    atualizar_metadados_projeto(slug, atualizacoes)

    pasta_projeto = obter_pasta_projeto(slug)
    if tipo_arquivo == "livro":
        capitulos_importados = []
        for item in list((payload.get("conteudo") or {}).get("capitulos") or []):
            titulo = str(item.get("titulo") or "Capítulo").strip() or "Capítulo"
            html = str(item.get("html") or "<p><br></p>")
            novo = criar_capitulo(pasta_projeto, titulo)
            novo = salvar_capitulo(
                pasta_projeto,
                int(novo["id"]),
                titulo,
                html,
                data_criacao=str(item.get("data_criacao") or novo.get("data_criacao") or ""),
                data_atualizacao=str(item.get("data_atualizacao") or novo.get("data_atualizacao") or ""),
            )
            if item.get("revisao_editorial") is not None:
                importar_revisao_editorial(pasta_projeto, "livro", int(novo["id"]), item["revisao_editorial"])
            capitulos_importados.append(novo)
        primeiro = int(capitulos_importados[0]["id"]) if capitulos_importados else None
        return {
            "tipo_arquivo": tipo_arquivo,
            "slug": slug,
            "capitulos_importados": len(capitulos_importados),
            "roteiro_importado": None,
            "editor_numero": primeiro,
        }

    roteiro_payload = (payload.get("conteudo") or {}).get("roteiro") or {}
    titulo = str(roteiro_payload.get("titulo") or "ROTEIRO").strip() or "ROTEIRO"
    novo_roteiro = criar_roteiro(
        pasta_projeto,
        titulo,
        cabecalho=str(roteiro_payload.get("cabecalho") or ""),
        rodape=str(roteiro_payload.get("rodape") or ""),
        prefixo_cena=str(roteiro_payload.get("prefixo_cena") or "0"),
        numeracao_inicial=int(roteiro_payload.get("numeracao_inicial") or 1),
        logline=str(roteiro_payload.get("logline") or ""),
        sinopse=str(roteiro_payload.get("sinopse") or ""),
        genero=str(roteiro_payload.get("genero") or ""),
        tipo_roteiro=str(roteiro_payload.get("tipo_roteiro") or "spec_script"),
        copyright=bool(roteiro_payload.get("copyright")),
        data_criacao=str(roteiro_payload.get("data_criacao") or "") or None,
        data_atualizacao=str(roteiro_payload.get("data_atualizacao") or "") or None,
    )
    html = str(roteiro_payload.get("html") or '<div class="roteiro-bloco"><br></div>')
    salvar_roteiro(pasta_projeto, int(novo_roteiro["id"]), titulo, html)
    if roteiro_payload.get("revisao_editorial") is not None:
        importar_revisao_editorial(pasta_projeto, "roteiro", int(novo_roteiro["id"]), roteiro_payload["revisao_editorial"])
    atualizar_roteiro_info(pasta_projeto, int(novo_roteiro["id"]), {
        "personagens": list(roteiro_payload.get("personagens") or []),
        "locais": list(roteiro_payload.get("locais") or []),
        "catalogo_personagens": list(roteiro_payload.get("catalogo_personagens") or []),
        "catalogo_locais": list(roteiro_payload.get("catalogo_locais") or []),
    }, data_atualizacao=str(roteiro_payload.get("data_atualizacao") or "") or None)
    return {
        "tipo_arquivo": tipo_arquivo,
        "slug": slug,
        "capitulos_importados": 0,
        "roteiro_importado": int(novo_roteiro["id"]),
        "editor_numero": int(novo_roteiro["id"]),
    }
