"""Exporta snapshots estruturados do projeto no formato binário .gut.

"""

from __future__ import annotations

import gzip
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

import msgpack
from bs4 import BeautifulSoup

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
        "tem_capa": bool(projeto.get("tem_capa")),
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
        capitulos_payload.append({
            "id": int(item["id"]),
            "titulo": capitulo.get("titulo") or "",
            "html": html,
            "texto": _texto_simples_html(html),
            "data_criacao": capitulo.get("data_criacao"),
            "data_atualizacao": capitulo.get("data_atualizacao"),
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
            }
        },
    }

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
                "balões_fluxo": len((recursos.get("fluxo") or {}).get("nodes") or []),
                "ligacoes_fluxo": len((recursos.get("fluxo") or {}).get("edges") or []),
                "personagens": len(recursos.get("personagens") or []),
                "lugares": len(recursos.get("lugares") or []),
                "anotacoes": len(recursos.get("anotacoes") or []),
            },
        },
    }
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
    payload = bruto[48:48 + tamanho]
    if len(payload) != tamanho:
        raise ValueError("Conteúdo do arquivo truncado.")
    if hashlib.sha256(payload).digest() != hash_esperado:
        raise ValueError("Integridade do arquivo inválida.")

    descompactado = gzip.decompress(payload)
    return msgpack.unpackb(descompactado, raw=False)


@registrar_etapa
def validar_payload_gut(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Confere se os dados recebidos atendem ao formato esperado antes de permitir a continuidade do fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        payload: Valor usado pela rotina para compor a operação de validar payload gut.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    if not isinstance(payload, dict):
        raise ValueError("Arquivo Gutenberg inválido.")
    if payload.get("container") != "gutenberg_gut":
        raise ValueError("Arquivo incompatível com o Gutenberg.")
    tipo = str(payload.get("tipo_arquivo") or "").strip().lower()
    if tipo not in {"livro", "roteiro"}:
        raise ValueError("Tipo de arquivo inválido.")
    projeto = payload.get("projeto") or {}
    conteudo = payload.get("conteudo") or {}
    if not isinstance(projeto, dict) or not isinstance(conteudo, dict):
        raise ValueError("Estrutura de metadados inválida.")
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
def validar_payload_gutr(payload: dict[str, Any]) -> dict[str, Any]:
    """Valida um pacote .gutr de recursos do Gutenberg."""
    if not isinstance(payload, dict):
        raise ValueError("Arquivo de recursos Gutenberg inválido.")
    if payload.get("container") != "gutenberg_gutr":
        raise ValueError("Arquivo incompatível com recursos do Gutenberg.")
    if str(payload.get("tipo_arquivo") or "").strip().lower() != "recursos":
        raise ValueError("Tipo de arquivo de recursos inválido.")
    conteudo = payload.get("conteudo") or {}
    recursos = conteudo.get("recursos") if isinstance(conteudo, dict) else None
    if not isinstance(recursos, dict):
        raise ValueError("Estrutura de recursos inválida.")
    return payload


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
    atualizados = mesclar_recursos_importados(pasta_projeto, recursos_payload)
    return {
        "ok": True,
        "tipo_arquivo": "recursos",
        "slug": slug,
        "recursos": atualizados,
        "importados": {
            "informacoes": len((normalizar_recursos(recursos_payload).get("informacoes") or [])),
            "balões_fluxo": len(((normalizar_recursos(recursos_payload).get("fluxo") or {}).get("nodes") or [])),
            "ligacoes_fluxo": len(((normalizar_recursos(recursos_payload).get("fluxo") or {}).get("edges") or [])),
            "personagens": len((normalizar_recursos(recursos_payload).get("personagens") or [])),
            "lugares": len((normalizar_recursos(recursos_payload).get("lugares") or [])),
            "anotacoes": len((normalizar_recursos(recursos_payload).get("anotacoes") or [])),
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
    if tipo == "roteiro":
        base.update({
            "contatos": str(projeto.get("contatos") or "").strip(),
            "informacoes_adicionais": str(projeto.get("informacoes_adicionais") or "").strip(),
            "tags": [],
        })
    else:
        base.update({
            "tags": [str(tag).strip() for tag in list(projeto.get("tags") or []) if str(tag).strip()],
            "contatos": "",
            "informacoes_adicionais": "",
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
    if tipo_arquivo == "roteiro":
        atualizacoes.update({
            "contatos": metadados.get("contatos") or "",
            "informacoes_adicionais": metadados.get("informacoes_adicionais") or "",
            "tags": [],
        })
    else:
        atualizacoes.update({
            "tags": list(metadados.get("tags") or []),
            "contatos": "",
            "informacoes_adicionais": "",
        })
    atualizar_metadados_projeto(slug, atualizacoes)

    pasta_projeto = obter_pasta_projeto(slug)
    if tipo_arquivo == "livro":
        capitulos_importados = []
        for item in list((payload.get("conteudo") or {}).get("capitulos") or []):
            titulo = str(item.get("titulo") or "Capítulo").strip() or "Capítulo"
            html = str(item.get("html") or "<p><br></p>")
            novo = criar_capitulo(pasta_projeto, titulo)
            novo = salvar_capitulo(pasta_projeto, int(novo["id"]), titulo, html)
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
    )
    html = str(roteiro_payload.get("html") or '<div class="roteiro-bloco"><br></div>')
    salvar_roteiro(pasta_projeto, int(novo_roteiro["id"]), titulo, html)
    atualizar_roteiro_info(pasta_projeto, int(novo_roteiro["id"]), {
        "personagens": list(roteiro_payload.get("personagens") or []),
        "locais": list(roteiro_payload.get("locais") or []),
        "catalogo_personagens": list(roteiro_payload.get("catalogo_personagens") or []),
        "catalogo_locais": list(roteiro_payload.get("catalogo_locais") or []),
    })
    return {
        "tipo_arquivo": tipo_arquivo,
        "slug": slug,
        "capitulos_importados": 0,
        "roteiro_importado": int(novo_roteiro["id"]),
        "editor_numero": int(novo_roteiro["id"]),
    }
