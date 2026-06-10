"""Camada de persistência JSON com leitura/escrita segura e tolerante a bloqueios no Windows."""
from __future__ import annotations

import json
import os
import time
import threading
from pathlib import Path
from typing import Any
from .logging_config import obter_logger, registrar_etapa
logger = obter_logger(__name__)

_JSON_LOCK = threading.RLock()


@registrar_etapa
def ler_json(caminho: Path, padrao: Any = None) -> Any:
    """
    Lê conteúdo persistido e devolve dados estruturados para consumo pelo restante da aplicação.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        caminho: Caminho de arquivo ou pasta usado como origem ou destino da operação.
        padrao: Valor usado pela rotina para compor a operação de ler json.

    Retorno:
        Conteúdo estruturado lido a partir da origem informada.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    if not caminho.exists():
        return {} if padrao is None else padrao
    fallback = {} if padrao is None else padrao
    with _JSON_LOCK:
        for tentativa in range(4):
            try:
                with caminho.open("r", encoding="utf-8") as arquivo:
                    return json.load(arquivo)
            except FileNotFoundError:
                return fallback
            except PermissionError:
                if tentativa == 3:
                    return fallback
                time.sleep(0.08 * (tentativa + 1))
            except json.JSONDecodeError:
                return fallback
    return fallback


@registrar_etapa
def salvar_json(caminho: Path, dados: Any) -> None:
    """
    Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        caminho: Caminho de arquivo ou pasta usado como origem ou destino da operação.
        dados: Valor usado pela rotina para compor a operação de salvar json.

    Retorno:
        A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with _JSON_LOCK:
        ultimo_erro: Exception | None = None
        for tentativa in range(6):
            temporario = caminho.with_suffix(caminho.suffix + f".{os.getpid()}.{threading.get_ident()}.tmp")
            try:
                with temporario.open("w", encoding="utf-8") as arquivo:
                    json.dump(dados, arquivo, ensure_ascii=False, indent=2)
                    arquivo.flush()
                    os.fsync(arquivo.fileno())
                os.replace(temporario, caminho)
                return
            except PermissionError as erro:
                ultimo_erro = erro
                try:
                    if temporario.exists():
                        temporario.unlink()
                except OSError:
                    pass
                time.sleep(0.12 * (tentativa + 1))
            except OSError as erro:
                ultimo_erro = erro
                try:
                    if temporario.exists():
                        temporario.unlink()
                except OSError:
                    pass
                if tentativa == 5:
                    raise
                time.sleep(0.08 * (tentativa + 1))
        if ultimo_erro:
            raise ultimo_erro
