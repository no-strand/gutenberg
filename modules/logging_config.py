"""
Configuração centralizada de logging do Gutenberg.

"""

from __future__ import annotations

import ctypes
import functools
import logging
import logging.handlers
import os
import sys
import time
import traceback
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

NOME_APP = "gutenberg"
PASTA_LOGS_ENV = "GUTENBERG_LOG_DIR"
ARQUIVO_LOG_ERROS = "errors.log"
FORMATO_LOG = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
FORMATO_DATA = "%Y-%m-%d %H:%M:%S"
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 7
_CONFIGURADO = False
def _known_folder_documentos_windows() -> Path | None:
    """Obtém a pasta Documentos oficial do Windows, incluindo redirecionamento para OneDrive."""
    if os.name != "nt":
        return None
    try:
        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        folder_id = GUID(
            0xFDD39AD0,
            0x238F,
            0x46AF,
            (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7),
        )
        caminho_ptr = ctypes.c_wchar_p()
        resultado = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(folder_id),
            0,
            None,
            ctypes.byref(caminho_ptr),
        )
        if resultado == 0 and caminho_ptr.value:
            caminho = Path(caminho_ptr.value)
            ctypes.windll.ole32.CoTaskMemFree(caminho_ptr)
            return caminho
    except Exception:
        return None
    return None


def _pasta_documentos_usuario() -> Path:
    """Retorna a pasta Documentos real do usuário com fallback multiplataforma."""
    pasta_customizada = os.environ.get(PASTA_LOGS_ENV)
    if pasta_customizada:
        return Path(pasta_customizada).expanduser()

    pasta_windows = _known_folder_documentos_windows()
    if pasta_windows:
        return pasta_windows

    home = Path.home()
    candidatos = [home / "Documents", home / "Documentos"]
    for candidato in candidatos:
        if candidato.exists():
            return candidato
    return home / "Documents"



def obter_pasta_logs() -> Path:
    """Retorna a pasta de logs do Gutenberg e garante sua existência."""
    pasta = _pasta_documentos_usuario() / NOME_APP
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _criar_handler_arquivo(caminho: Path, nivel: int) -> logging.Handler:
    handler = logging.handlers.RotatingFileHandler(
        caminho,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(nivel)
    handler.setFormatter(logging.Formatter(FORMATO_LOG, datefmt=FORMATO_DATA))
    return handler


def configurar_logging(nivel: int = logging.DEBUG) -> Path:
    """
    Configura o logging de forma idempotente.

    - console recebe WARNING ou superior para não poluir a execução normal e os testes.
    - errors.log recebe somente ERROR e CRITICAL, com stack traces quando houver exceção.

    Observação: por decisão de produto, nenhum log DEBUG/INFO/WARNING é gravado em arquivo.
    """
    global _CONFIGURADO
    pasta_logs = obter_pasta_logs()
    if _CONFIGURADO:
        return pasta_logs

    root = logging.getLogger()
    root.setLevel(nivel)

    # Remove handlers equivalentes adicionados por configurações anteriores do app.
    for handler in list(root.handlers):
        if getattr(handler, "_gutenberg_handler", False):
            root.removeHandler(handler)
            handler.close()

    erros = _criar_handler_arquivo(pasta_logs / ARQUIVO_LOG_ERROS, logging.ERROR)
    erros._gutenberg_handler = True  # type: ignore[attr-defined]

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.WARNING)
    console.setFormatter(logging.Formatter("%(levelname)s | %(name)s | %(message)s"))
    console._gutenberg_handler = True  # type: ignore[attr-defined]

    root.addHandler(erros)
    root.addHandler(console)

    _CONFIGURADO = True
    logging.getLogger(__name__).debug(
        "Logging inicializado | pasta=%s | arquivo_erros=%s | arquivo_minimo=ERROR",
        pasta_logs,
        pasta_logs / ARQUIVO_LOG_ERROS,
    )
    return pasta_logs


def obter_logger(nome: str) -> logging.Logger:
    """Obtém um logger padronizado para o módulo informado."""
    if not _CONFIGURADO:
        configurar_logging()
    return logging.getLogger(nome)


def registrar_etapa(funcao: F) -> F:
    """
    Decora funções para registrar início, fim, duração e falhas.

    O log evita gravar argumentos por padrão para reduzir risco de expor textos,
    caminhos privados ou conteúdo de manuscritos nos arquivos de log.
    """
    logger = obter_logger(funcao.__module__)

    @functools.wraps(funcao)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        nome = f"{funcao.__module__}.{funcao.__qualname__}"
        inicio = time.perf_counter()
        logger.debug("Etapa iniciada | funcao=%s", nome)
        try:
            resultado = funcao(*args, **kwargs)
            duracao_ms = (time.perf_counter() - inicio) * 1000
            logger.debug("Etapa concluida | funcao=%s | duracao_ms=%.2f", nome, duracao_ms)
            return resultado
        except ValueError as exc:
            duracao_ms = (time.perf_counter() - inicio) * 1000
            logger.warning(
                "Etapa recusada por validação | funcao=%s | duracao_ms=%.2f | motivo=%s",
                nome,
                duracao_ms,
                exc,
            )
            raise
        except Exception:
            duracao_ms = (time.perf_counter() - inicio) * 1000
            logger.exception("Etapa falhou | funcao=%s | duracao_ms=%.2f", nome, duracao_ms)
            raise

    return wrapper  # type: ignore[return-value]


@contextmanager
def log_etapa(logger: logging.Logger, descricao: str, nivel: int = logging.DEBUG, **contexto: Any) -> Iterator[None]:
    """Context manager para registrar blocos operacionais específicos."""
    inicio = time.perf_counter()
    contexto_txt = " ".join(f"{chave}={valor}" for chave, valor in contexto.items())
    logger.log(nivel, "Etapa iniciada | %s%s", descricao, f" | {contexto_txt}" if contexto_txt else "")
    try:
        yield
    except Exception:
        logger.exception("Etapa falhou | %s%s", descricao, f" | {contexto_txt}" if contexto_txt else "")
        raise
    finally:
        duracao_ms = (time.perf_counter() - inicio) * 1000
        logger.log(nivel, "Etapa finalizada | %s | duracao_ms=%.2f", descricao, duracao_ms)


def registrar_excecao_global(tipo: type[BaseException], valor: BaseException, tb: Any) -> None:
    """Registra exceções não tratadas antes de delegar ao hook padrão do Python."""
    logger = obter_logger("gutenberg.excecoes")
    if issubclass(tipo, KeyboardInterrupt):
        logger.info("Aplicação interrompida pelo usuário.")
        sys.__excepthook__(tipo, valor, tb)
        return
    logger.critical("Exceção não tratada", exc_info=(tipo, valor, tb))
    sys.__excepthook__(tipo, valor, tb)


def instalar_hook_excecoes() -> None:
    """Instala hook global para exceções não capturadas."""
    sys.excepthook = registrar_excecao_global


configurar_logging()
