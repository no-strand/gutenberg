"""
Camada de internacionalização. Centraliza carregamento de traduções e utilitários de idioma da aplicação.

Créditos do projeto: Nostrand.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .utilidades import RAIZ_RECURSOS, obter_configuracoes
from .logging_config import obter_logger, registrar_etapa
logger = obter_logger(__name__)

LOCALES_DIR = RAIZ_RECURSOS / 'locales'
DEFAULT_LOCALE = 'pt_BR'
SUPPORTED_LOCALES = {'pt_BR', 'en_US'}


@registrar_etapa
def normalizar_idioma_app(idioma: str | None) -> str:
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
    return 'pt_BR'


@lru_cache(maxsize=8)
@registrar_etapa
def carregar_locale(idioma: str) -> dict[str, Any]:
    """
    Carrega dados externos ou persistidos e os prepara para uso imediato pela aplicação.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        idioma: Código de idioma usado para selecionar textos, metadados ou regras de formatação.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    codigo = normalizar_idioma_app(idioma)
    caminho = LOCALES_DIR / f'{codigo}.json'
    try:
        with caminho.open('r', encoding='utf-8') as arquivo:
            dados = json.load(arquivo)
            return dados if isinstance(dados, dict) else {}
    except Exception:
        if codigo != DEFAULT_LOCALE:
            return carregar_locale(DEFAULT_LOCALE)
        return {}


@registrar_etapa
def limpar_cache_i18n() -> None:
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
    carregar_locale.cache_clear()



@registrar_etapa
def obter_idioma_app() -> str:
    """
    Localiza e devolve um dado ou recurso específico, aplicando as validações necessárias antes do retorno.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Retorno:
        O recurso solicitado ou uma estrutura com os dados encontrados.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return normalizar_idioma_app(obter_configuracoes().get('idioma_app'))



@registrar_etapa
def t(key: str, idioma: str | None = None, default: str | None = None, **kwargs: Any) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        key: Valor usado pela rotina para compor a operação de t.
        idioma: Código de idioma usado para selecionar textos, metadados ou regras de formatação.
        default: Valor usado pela rotina para compor a operação de t.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    codigo = normalizar_idioma_app(idioma or obter_idioma_app())
    locale = carregar_locale(codigo)
    fallback = carregar_locale(DEFAULT_LOCALE) if codigo != DEFAULT_LOCALE else locale
    valor = locale.get(key, fallback.get(key, default if default is not None else key))
    if not isinstance(valor, str):
        valor = str(valor)
    if kwargs:
        try:
            return valor.format(**kwargs)
        except Exception:
            return valor
    return valor



@registrar_etapa
def idioma_projeto_rotulo(idioma_projeto: str | None) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        idioma_projeto: Valor usado pela rotina para compor a operação de idioma projeto rotulo.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    valor = str(idioma_projeto or '').strip()
    if valor in {'en', 'en-US', 'en_US'}:
        return t('language.en_US')
    return t('language.pt_BR')
