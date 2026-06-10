"""
Gerencia roteiros e suas informações auxiliares, como tipo, conteúdo HTML e preferências padrão.

Créditos do projeto: Nostrand.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .i18n import t
from .persistencia_editor_db import BancoEditorLocal

_DB_CACHE: dict[Path, BancoEditorLocal] = {}
from .utilidades import agora_iso
from .logging_config import obter_logger, registrar_etapa
logger = obter_logger(__name__)

PREFIXO_ARQUIVO = "roteiro_"

TIPOS_ROTEIRO = {
    "spec_script": {"label_key": "script.spec_script", "cena_numerada": False, "header_footer": False},
    "shooting_script": {"label_key": "script.shooting_script", "cena_numerada": True, "header_footer": True},
    "revised_draft": {"label_key": "script.revised_draft", "cena_numerada": True, "header_footer": True},
    "production_draft": {"label_key": "script.production_draft", "cena_numerada": True, "header_footer": True},
    "continuity_script": {"label_key": "script.continuity_script", "cena_numerada": True, "header_footer": True},
}
TIPO_ROTEIRO_PADRAO = "spec_script"


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
def normalizar_tipo_roteiro(valor: Any) -> str:
    """
    Padroniza valores de entrada para que diferentes partes do sistema trabalhem com o mesmo formato.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        valor: Valor usado pela rotina para compor a operação de normalizar tipo roteiro.

    Retorno:
        O valor recebido em uma forma padronizada e segura para uso interno.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    tipo = str(valor or "").strip().lower()
    return tipo if tipo in TIPOS_ROTEIRO else TIPO_ROTEIRO_PADRAO


@registrar_etapa
def obter_label_tipo_roteiro(valor: Any) -> str:
    """
    Localiza e devolve um dado ou recurso específico, aplicando as validações necessárias antes do retorno.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        valor: Valor usado pela rotina para compor a operação de obter label tipo roteiro.

    Retorno:
        O recurso solicitado ou uma estrutura com os dados encontrados.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    tipo = normalizar_tipo_roteiro(valor)
    return t(TIPOS_ROTEIRO[tipo]["label_key"])


@registrar_etapa
def _html_roteiro_padrao() -> str:
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
    return '<div class="roteiro-bloco" data-block-type="neutral" data-initial-neutral="true"><br></div>'


@registrar_etapa
def _normalizar_html_roteiro(paragrafos: Any) -> str:
    """
    Padroniza valores de entrada para que diferentes partes do sistema trabalhem com o mesmo formato.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        paragrafos: Valor usado pela rotina para compor a operação de normalizar html roteiro.

    Retorno:
        O valor recebido em uma forma padronizada e segura para uso interno.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    if isinstance(paragrafos, str):
        html = paragrafos.strip()
        return html or _html_roteiro_padrao()
    if isinstance(paragrafos, list):
        partes = []
        for item in paragrafos:
            if item is None:
                continue
            trecho = str(item).strip()
            if trecho:
                partes.append(trecho)
        html = "".join(partes).strip()
        return html or _html_roteiro_padrao()
    return _html_roteiro_padrao()


@registrar_etapa
def listar_roteiros(pasta_projeto: Path) -> list[dict[str, Any]]:
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
    roteiros = []
    for item in _db(pasta_projeto).listar_roteiros():
        numero = int(item["id"])
        roteiros.append({
            **item,
            "arquivo": f"{PREFIXO_ARQUIVO}{numero}.json",
            "titulo": item.get("titulo", t("script.script_default_with_number", number=numero)),
            "tipo_roteiro": normalizar_tipo_roteiro(item.get("tipo_roteiro")),
            "tipo_roteiro_label": obter_label_tipo_roteiro(item.get("tipo_roteiro")),
            "copyright": bool(item.get("copyright", _usar_copyright_por_padrao(item.get("tipo_roteiro")))),
        })
    return roteiros


@registrar_etapa
def obter_caminho_roteiro(pasta_projeto: Path, numero: int) -> Path:
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
    return pasta_projeto / f"{PREFIXO_ARQUIVO}{numero}.json"


@registrar_etapa
def proximo_numero_roteiro(pasta_projeto: Path) -> int:
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
    return _db(pasta_projeto).proximo_numero_roteiro()


@registrar_etapa
def _usar_copyright_por_padrao(tipo_roteiro: Any) -> bool:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        tipo_roteiro: Valor usado pela rotina para compor a operação de usar copyright por padrao.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return normalizar_tipo_roteiro(tipo_roteiro) != "spec_script"


@registrar_etapa
def criar_roteiro(pasta_projeto: Path, titulo: str, cabecalho: str = "", rodape: str = "", prefixo_cena: str = "0", numeracao_inicial: int = 1, logline: str = "", sinopse: str = "", genero: str = "", tipo_roteiro: str = TIPO_ROTEIRO_PADRAO, copyright: Any | None = None) -> dict[str, Any]:
    """
    Cria um novo registro, arquivo ou estrutura interna mantendo o padrão de armazenamento do projeto.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pasta_projeto: Pasta raiz do projeto em que os dados relacionados serão lidos ou gravados.
        titulo: Título exibido ou salvo para representar o conteúdo tratado.
        cabecalho: Valor usado pela rotina para compor a operação de criar roteiro.
        rodape: Valor usado pela rotina para compor a operação de criar roteiro.
        prefixo_cena: Valor usado pela rotina para compor a operação de criar roteiro.
        numeracao_inicial: Valor usado pela rotina para compor a operação de criar roteiro.
        logline: Valor usado pela rotina para compor a operação de criar roteiro.
        sinopse: Valor usado pela rotina para compor a operação de criar roteiro.
        genero: Valor usado pela rotina para compor a operação de criar roteiro.
        tipo_roteiro: Valor usado pela rotina para compor a operação de criar roteiro.
        copyright: Valor usado pela rotina para compor a operação de criar roteiro.

    Retorno:
        Os dados do novo item criado, incluindo identificadores gerados quando existirem.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    numero = proximo_numero_roteiro(pasta_projeto)
    tipo_normalizado = normalizar_tipo_roteiro(tipo_roteiro)
    agora = agora_iso()
    dados = {
        "titulo": (titulo or "").strip().upper() or t("script.script_default_with_number", number=numero),
        "paragrafos": [_html_roteiro_padrao()],
        "html_editor": _html_roteiro_padrao(),
        "cabecalho": cabecalho.strip(),
        "rodape": rodape.strip(),
        "prefixo_cena": str(prefixo_cena or "0").strip() or "0",
        "numeracao_inicial": max(1, int(numeracao_inicial or 1)),
        "logline": logline.strip(),
        "sinopse": sinopse.strip(),
        "genero": genero.strip(),
        "tipo_roteiro": tipo_normalizado,
        "copyright": _usar_copyright_por_padrao(tipo_normalizado) if copyright is None else bool(copyright),
        "personagens": [],
        "locais": [],
        "catalogo_personagens": [],
        "catalogo_locais": [],
        "data_criacao": agora,
        "data_atualizacao": agora,
    }
    return _db(pasta_projeto).criar_roteiro(numero, dados)


@registrar_etapa
def ler_roteiro(pasta_projeto: Path, numero: int) -> dict[str, Any]:
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
    dados = _db(pasta_projeto).ler_roteiro(numero)
    if not dados:
        raise FileNotFoundError(t("backend.script_not_found"))
    dados.setdefault("titulo", t("script.script_default_with_number", number=numero))
    dados["paragrafos"] = [_normalizar_html_roteiro(dados.get("paragrafos"))]
    dados["html_editor"] = dados["paragrafos"][0]
    dados["html"] = dados["html_editor"]
    dados.setdefault("cabecalho", "")
    dados.setdefault("rodape", "")
    dados.setdefault("prefixo_cena", "0")
    dados.setdefault("numeracao_inicial", 1)
    dados.setdefault("logline", "")
    dados.setdefault("sinopse", "")
    dados.setdefault("genero", "")
    dados.setdefault("tipo_roteiro", TIPO_ROTEIRO_PADRAO)
    dados["tipo_roteiro"] = normalizar_tipo_roteiro(dados.get("tipo_roteiro"))
    dados["tipo_roteiro_label"] = obter_label_tipo_roteiro(dados.get("tipo_roteiro"))
    dados["copyright"] = bool(dados.get("copyright", _usar_copyright_por_padrao(dados.get("tipo_roteiro"))))
    dados.setdefault("personagens", [])
    dados.setdefault("locais", [])
    dados.setdefault("catalogo_personagens", [])
    dados.setdefault("catalogo_locais", [])
    return dados


@registrar_etapa
def salvar_roteiro(pasta_projeto: Path, numero: int, titulo: str, html: str) -> dict[str, Any]:
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
    dados_atuais = _db(pasta_projeto).ler_roteiro(numero)
    if not dados_atuais:
        raise FileNotFoundError(t("backend.script_not_found"))
    dados = {
        **dados_atuais,
        "titulo": (titulo or "").strip().upper() or str(dados_atuais.get("titulo") or t("script.untitled")),
        "paragrafos": [_normalizar_html_roteiro(html)],
        "html_editor": _normalizar_html_roteiro(html),
        "data_atualizacao": agora_iso(),
    }
    salvo = _db(pasta_projeto).salvar_roteiro(numero, dados)
    if not salvo:
        raise FileNotFoundError(t("backend.script_not_found"))
    return salvo


@registrar_etapa
def atualizar_roteiro_info(pasta_projeto: Path, numero: int, atualizacoes: dict[str, Any]) -> dict[str, Any]:
    """
    Aplica alterações controladas sobre dados já existentes sem recriar estruturas desnecessariamente.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pasta_projeto: Pasta raiz do projeto em que os dados relacionados serão lidos ou gravados.
        numero: Número usado para localizar o capítulo, item ou posição correspondente.
        atualizacoes: Valor usado pela rotina para compor a operação de atualizar roteiro info.

    Retorno:
        A estrutura atualizada depois da aplicação das mudanças.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    dados = _db(pasta_projeto).ler_roteiro(numero)
    if not dados:
        raise FileNotFoundError(t("backend.script_not_found"))
    for chave, valor in (atualizacoes or {}).items():
        if chave in {"personagens", "locais"}:
            if isinstance(valor, str):
                valor = [item.strip() for item in valor.splitlines() if item.strip()]
            elif isinstance(valor, list):
                valor = [str(item).strip() for item in valor if str(item).strip()]
        elif chave == "numeracao_inicial":
            valor = max(1, int(valor or 1))
        elif chave == "prefixo_cena":
            valor = str(valor or "0").strip() or "0"
        elif chave == "tipo_roteiro":
            valor = normalizar_tipo_roteiro(valor)
            if "copyright" not in (atualizacoes or {}):
                dados["copyright"] = _usar_copyright_por_padrao(valor)
        elif chave == "copyright":
            valor = bool(valor)
        elif isinstance(valor, str):
            valor = valor.strip()
        dados[chave] = valor
    dados["data_atualizacao"] = agora_iso()
    salvo = _db(pasta_projeto).salvar_roteiro(numero, dados)
    if not salvo:
        raise FileNotFoundError(t("backend.script_not_found"))
    return salvo


@registrar_etapa
def excluir_roteiro(pasta_projeto: Path, numero: int) -> None:
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
    _db(pasta_projeto).excluir_roteiro(numero)
