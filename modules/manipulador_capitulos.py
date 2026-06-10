"""Regras de negócio para capítulos."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .i18n import t
from .persistencia_editor_db import BancoEditorLocal

_DB_CACHE: dict[Path, BancoEditorLocal] = {}
from .utilidades import agora_iso
from .logging_config import obter_logger, registrar_etapa
logger = obter_logger(__name__)

ARQUIVO_PROJETO = "projeto.json"


@registrar_etapa
def _db(pasta_projeto: Path) -> BancoEditorLocal:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pasta_projeto: Pasta raiz do projeto em que os dados relacionados serão lidos ou gravados.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    pasta = Path(pasta_projeto)
    db = _DB_CACHE.get(pasta)
    if db is None:
        db = BancoEditorLocal(pasta)
        _DB_CACHE[pasta] = db
    return db


@registrar_etapa
def listar_capitulos(pasta_projeto: Path) -> list[dict[str, Any]]:
    """
    Reúne e devolve uma lista organizada de itens disponíveis para a interface ou para outra camada do sistema.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pasta_projeto: Pasta raiz do projeto em que os dados relacionados serão lidos ou gravados.

    Retorno:
        Uma lista com os registros encontrados, normalmente já ordenada e pronta para a interface.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return _db(pasta_projeto).listar_capitulos()


@registrar_etapa
def obter_caminho_capitulo(pasta_projeto: Path, numero: int) -> Path:
    """
    Localiza e devolve um dado ou recurso específico, aplicando as validações necessárias antes do retorno.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pasta_projeto: Pasta raiz do projeto em que os dados relacionados serão lidos ou gravados.
        numero: Número usado para localizar o capítulo, item ou posição correspondente.

    Retorno:
        O recurso solicitado ou uma estrutura com os dados encontrados.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return pasta_projeto / f"capitulo_{numero}.json"


@registrar_etapa
def proximo_numero_capitulo(pasta_projeto: Path) -> int:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pasta_projeto: Pasta raiz do projeto em que os dados relacionados serão lidos ou gravados.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return _db(pasta_projeto).proximo_numero_capitulo()


@registrar_etapa
def criar_capitulo(pasta_projeto: Path, titulo: str) -> dict[str, Any]:
    """
    Cria um novo registro, arquivo ou estrutura interna mantendo o padrão de armazenamento do projeto.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pasta_projeto: Pasta raiz do projeto em que os dados relacionados serão lidos ou gravados.
        titulo: Título exibido ou salvo para representar o conteúdo tratado.

    Retorno:
        Os dados do novo item criado, incluindo identificadores gerados quando existirem.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    numero = proximo_numero_capitulo(pasta_projeto)
    agora = agora_iso()
    return _db(pasta_projeto).criar_capitulo(
        numero=numero,
        titulo=titulo,
        html="<p><br></p>",
        data_criacao=agora,
        data_atualizacao=agora,
    )


@registrar_etapa
def ler_capitulo(pasta_projeto: Path, numero: int) -> dict[str, Any]:
    """
    Lê conteúdo persistido e devolve dados estruturados para consumo pelo restante da aplicação.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pasta_projeto: Pasta raiz do projeto em que os dados relacionados serão lidos ou gravados.
        numero: Número usado para localizar o capítulo, item ou posição correspondente.

    Retorno:
        Conteúdo estruturado lido a partir da origem informada.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    dados = _db(pasta_projeto).ler_capitulo(numero)
    if not dados:
        raise FileNotFoundError(t("backend.chapter_not_found"))
    return dados


@registrar_etapa
def salvar_capitulo(pasta_projeto: Path, numero: int, titulo: str, html: str) -> dict[str, Any]:
    """
    Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pasta_projeto: Pasta raiz do projeto em que os dados relacionados serão lidos ou gravados.
        numero: Número usado para localizar o capítulo, item ou posição correspondente.
        titulo: Título exibido ou salvo para representar o conteúdo tratado.
        html: Conteúdo HTML já editado ou normalizado pela aplicação.

    Retorno:
        A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    dados_atuais = _db(pasta_projeto).ler_capitulo(numero)
    if not dados_atuais:
        raise FileNotFoundError(t("backend.chapter_not_found"))

    dados = _db(pasta_projeto).salvar_capitulo(
        numero=numero,
        titulo=titulo,
        html=html,
        data_criacao=dados_atuais.get("data_criacao") or agora_iso(),
        data_atualizacao=agora_iso(),
    )
    if not dados:
        raise FileNotFoundError(t("backend.chapter_not_found"))
    return dados


@registrar_etapa
def excluir_capitulo(pasta_projeto: Path, numero: int) -> None:
    """
    Remove o item indicado e executa os cuidados necessários para manter o restante do projeto consistente.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pasta_projeto: Pasta raiz do projeto em que os dados relacionados serão lidos ou gravados.
        numero: Número usado para localizar o capítulo, item ou posição correspondente.

    Retorno:
        None. A função sinaliza falhas por exceção quando a remoção não pode ser concluída.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    _db(pasta_projeto).excluir_capitulo(numero)
