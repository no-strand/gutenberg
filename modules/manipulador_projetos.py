"""Regras de negócio para projetos literários."""
from __future__ import annotations

import os
import shutil
import stat
import time
from pathlib import Path
from typing import Any

from PIL import Image

from .persistencia_json import ler_json, salvar_json
from .utilidades import PASTA_PROJETOS, agora_iso, garantir_pasta_projetos, nome_seguro, obter_pasta_exportacao_projeto
from .manipulador_capitulos import listar_capitulos
from .i18n import t
from .manipulador_roteiros import listar_roteiros
from .persistencia_editor_db import limpar_estado_banco_editor
from .logging_config import obter_logger, registrar_etapa
logger = obter_logger(__name__)


@registrar_etapa
def normalizar_idioma_projeto(idioma: str | None) -> str:
    """
    Padroniza valores de entrada para que diferentes partes do sistema trabalhem com o mesmo formato.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        idioma: Código de idioma usado para selecionar textos, metadados ou regras de formatação.

    Retorno:
        O valor recebido em uma forma padronizada e segura para uso interno.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    valor = str(idioma or '').strip()
    if valor in {'en', 'en-US', 'en_US'}:
        return 'en_US'
    return 'pt-BR'


@registrar_etapa
def _limpar_campos_catalogo_projeto(dados: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        dados: Valor usado pela rotina para compor a operação de limpar campos catalogo projeto.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    alterado = False
    for chave in ("catalogo_personagens", "catalogo_locais"):
        if chave in dados:
            dados.pop(chave, None)
            alterado = True
    return dados, alterado



@registrar_etapa
def _onerror_apagar_readonly(func, path, exc_info):
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        func: Valor usado pela rotina para compor a operação de onerror apagar readonly.
        path: Valor usado pela rotina para compor a operação de onerror apagar readonly.
        exc_info: Valor usado pela rotina para compor a operação de onerror apagar readonly.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        raise


@registrar_etapa
def _apagar_pasta_com_retry(pasta: Path, tentativas: int = 6) -> None:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pasta: Valor usado pela rotina para compor a operação de apagar pasta com retry.
        tentativas: Valor usado pela rotina para compor a operação de apagar pasta com retry.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    if not pasta.exists():
        return
    ultimo_erro: Exception | None = None
    for tentativa in range(tentativas):
        try:
            shutil.rmtree(pasta, onerror=_onerror_apagar_readonly)
            if not pasta.exists():
                return
        except FileNotFoundError:
            return
        except Exception as erro:
            ultimo_erro = erro
        time.sleep(0.08 * (tentativa + 1))
    if pasta.exists():
        if ultimo_erro:
            raise ultimo_erro
        raise OSError(f"Nao foi possivel excluir a pasta do projeto: {pasta}")


@registrar_etapa
def criar_projeto(titulo: str, descricao: str = "", autor: str = "", tags: list[str] | None = None, idioma: str = "pt-BR", tipo: str = "livro", contatos: str = "", informacoes_adicionais: str = "") -> dict[str, Any]:
    """
    Cria um novo registro, arquivo ou estrutura interna mantendo o padrão de armazenamento do projeto.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        titulo: Título exibido ou salvo para representar o conteúdo tratado.
        descricao: Valor usado pela rotina para compor a operação de criar projeto.
        autor: Valor usado pela rotina para compor a operação de criar projeto.
        tags: Valor usado pela rotina para compor a operação de criar projeto.
        idioma: Código de idioma usado para selecionar textos, metadados ou regras de formatação.
        tipo: Valor usado pela rotina para compor a operação de criar projeto.
        contatos: Valor usado pela rotina para compor a operação de criar projeto.
        informacoes_adicionais: Valor usado pela rotina para compor a operação de criar projeto.

    Retorno:
        Os dados do novo item criado, incluindo identificadores gerados quando existirem.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    garantir_pasta_projetos()
    safe = nome_seguro(titulo)
    pasta = PASTA_PROJETOS / safe
    if pasta.exists():
        raise FileExistsError(t("backend.project_exists"))

    tipo_normalizado = tipo if tipo in {"livro", "roteiro"} else "livro"
    dados = {
        "titulo": titulo.strip(),
        "descricao": descricao.strip(),
        "autor": autor.strip(),
        "tags": [tag.strip() for tag in (tags or []) if tag.strip()] if tipo_normalizado == "livro" else [],
        "data_criacao": agora_iso(),
        "data_atualizacao": agora_iso(),
        "slug": safe,
        "ultimo_lido": None,
        "posicoes_leitura": {},
        "tem_capa": False,
        "idioma": normalizar_idioma_projeto(idioma),
        "tipo": tipo_normalizado,
        "contatos": contatos.strip(),
        "informacoes_adicionais": informacoes_adicionais.strip() if tipo_normalizado == "roteiro" else "",
    }
    pasta.mkdir(parents=True, exist_ok=True)
    salvar_json(pasta / "projeto.json", dados)
    return dados


@registrar_etapa
def caminho_capa_projeto(slug: str) -> Path:
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
    return obter_pasta_projeto(slug) / "cover.jpg"


@registrar_etapa
def salvar_capa_projeto(slug: str, caminho_origem: Path) -> Path:
    """
    Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        caminho_origem: Valor usado pela rotina para compor a operação de salvar capa projeto.

    Retorno:
        A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    destino = caminho_capa_projeto(slug)
    with Image.open(caminho_origem) as imagem:
        rgb = imagem.convert("RGB")
        rgb.save(destino, format="JPEG", quality=92)
    atualizar_metadados_projeto(slug, {"tem_capa": True})
    return destino


@registrar_etapa
def listar_projetos() -> list[dict[str, Any]]:
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
    garantir_pasta_projetos()
    projetos = []
    for pasta in sorted(PASTA_PROJETOS.iterdir(), key=lambda p: p.name.lower()):
        if not pasta.is_dir():
            continue
        projeto = ler_json(pasta / "projeto.json", {})
        if not projeto:
            continue
        projeto, alterado = _limpar_campos_catalogo_projeto(projeto)
        if alterado:
            salvar_json(pasta / "projeto.json", projeto)
        projeto["slug"] = pasta.name
        projeto["idioma"] = normalizar_idioma_projeto(projeto.get("idioma"))
        projeto.setdefault("tipo", "livro")
        projeto.setdefault("contatos", "")
        projeto.setdefault("informacoes_adicionais", "")
        projeto.setdefault("posicoes_leitura", {})
        projeto["total_capitulos"] = len(listar_capitulos(pasta))
        projeto["total_roteiros"] = len(listar_roteiros(pasta))
        projeto["tem_capa"] = projeto.get("tipo") == "livro" and (pasta / "cover.jpg").exists()
        projetos.append(projeto)
    projetos.sort(key=lambda item: item.get("data_atualizacao", ""), reverse=True)
    return projetos


@registrar_etapa
def obter_projeto(slug: str) -> dict[str, Any]:
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
    pasta = PASTA_PROJETOS / slug
    projeto = ler_json(pasta / "projeto.json", {})
    if not projeto:
        raise FileNotFoundError(t("backend.project_not_found"))
    projeto, alterado = _limpar_campos_catalogo_projeto(projeto)
    if alterado:
        salvar_json(pasta / "projeto.json", projeto)
    projeto["slug"] = slug
    projeto["idioma"] = normalizar_idioma_projeto(projeto.get("idioma"))
    projeto.setdefault("tipo", "livro")
    projeto.setdefault("contatos", "")
    projeto.setdefault("informacoes_adicionais", "")
    projeto.setdefault("posicoes_leitura", {})
    projeto["capitulos"] = listar_capitulos(pasta)
    projeto["roteiros"] = listar_roteiros(pasta)
    projeto["tem_capa"] = projeto.get("tipo") == "livro" and (pasta / "cover.jpg").exists()
    projeto["url_capa"] = f"/projetos/{slug}/cover.jpg" if projeto["tem_capa"] else None
    return projeto


@registrar_etapa
def obter_pasta_projeto(slug: str) -> Path:
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
    pasta = PASTA_PROJETOS / slug
    if not pasta.exists():
        raise FileNotFoundError(t("backend.project_not_found"))
    return pasta


@registrar_etapa
def atualizar_metadados_projeto(slug: str, atualizacoes: dict[str, Any]) -> dict[str, Any]:
    """
    Aplica alterações controladas sobre dados já existentes sem recriar estruturas desnecessariamente.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        atualizacoes: Valor usado pela rotina para compor a operação de atualizar metadados projeto.

    Retorno:
        A estrutura atualizada depois da aplicação das mudanças.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    pasta = obter_pasta_projeto(slug)
    caminho = pasta / "projeto.json"
    dados = ler_json(caminho, {})
    if not dados:
        raise FileNotFoundError(t("backend.project_not_found"))
    dados.update(atualizacoes)
    dados["idioma"] = normalizar_idioma_projeto(dados.get("idioma"))
    dados, _ = _limpar_campos_catalogo_projeto(dados)
    dados["data_atualizacao"] = agora_iso()
    salvar_json(caminho, dados)
    return dados


@registrar_etapa
def atualizar_data_projeto(slug: str) -> None:
    """
    Aplica alterações controladas sobre dados já existentes sem recriar estruturas desnecessariamente.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.

    Retorno:
        A estrutura atualizada depois da aplicação das mudanças.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    atualizar_metadados_projeto(slug, {})


@registrar_etapa
def registrar_ultimo_lido(slug: str, numero_capitulo: int) -> None:
    """
    Registra uma informação de estado ou progresso para que ela possa ser consultada posteriormente.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        numero_capitulo: Valor usado pela rotina para compor a operação de registrar ultimo lido.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    atualizar_metadados_projeto(slug, {"ultimo_lido": numero_capitulo})



@registrar_etapa
def registrar_posicao_leitura(slug: str, numero_capitulo: int, posicao: int) -> None:
    """
    Registra uma informação de estado ou progresso para que ela possa ser consultada posteriormente.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        numero_capitulo: Valor usado pela rotina para compor a operação de registrar posicao leitura.
        posicao: Valor usado pela rotina para compor a operação de registrar posicao leitura.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    projeto = obter_projeto(slug)
    posicoes = dict(projeto.get("posicoes_leitura") or {})
    posicoes[str(numero_capitulo)] = max(0, int(posicao))
    atualizar_metadados_projeto(slug, {"ultimo_lido": numero_capitulo, "posicoes_leitura": posicoes})

@registrar_etapa
def excluir_projeto(slug: str) -> None:
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
    projeto = obter_projeto(slug)
    pasta = obter_pasta_projeto(slug)

    limpar_estado_banco_editor(pasta)
    _apagar_pasta_com_retry(pasta)

    titulo = str(projeto.get("titulo") or "").strip()
    if titulo:
        pasta_exportacao = obter_pasta_exportacao_projeto(titulo)
        limpar_estado_banco_editor(pasta_exportacao)
        _apagar_pasta_com_retry(pasta_exportacao)
