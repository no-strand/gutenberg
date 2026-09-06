"""Gerenciamento e download dos modelos externos do Kokoro TTS.

Os arquivos pesados de modelo/vozes ficam fora do bundle do PyInstaller em uma
pasta persistente do usuário. O download acontece em uma thread do servidor e a
interface consulta o estado por HTTP para exibir progresso e permitir cancelamento.
"""
from __future__ import annotations

from pathlib import Path
from threading import Event, Lock, Thread
from urllib.request import Request, urlopen
from zipfile import ZipFile
import os
import time

from .logging_config import obter_logger_tts
from .utilidades import PASTA_MODELOS_TTS

logger = obter_logger_tts("gutenberg.tts.modelos")

MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin"
MODEL_NAME = "kokoro-v1.0.onnx"
VOICES_NAME = "voices-v1.0.bin"
MODEL_PATH = PASTA_MODELOS_TTS / MODEL_NAME
VOICES_PATH = PASTA_MODELOS_TTS / VOICES_NAME
MIN_MODEL_BYTES = 250_000_000
MIN_VOICES = 54
PTBR_VOICES = {"pf_dora", "pm_alex", "pm_santa"}
TTS_MENU_VOICES = PTBR_VOICES | {"af_heart", "af_bella", "af_nicole", "am_michael", "bf_emma", "bm_george"}

_estado_lock = Lock()
_cancelar = Event()
_thread: Thread | None = None
_estado: dict = {
    "ativo": False,
    "concluido": False,
    "cancelado": False,
    "etapa": "ocioso",
    "mensagem": "",
    "erro": "",
    "arquivo_atual": "",
    "arquivo_indice": 0,
    "arquivo_total_itens": 2,
    "bytes_recebidos": 0,
    "bytes_total": 0,
    "percentual": 0.0,
    "iniciado_em": None,
    "finalizado_em": None,
}


class DownloadCancelado(RuntimeError):
    pass


def _human_bytes(valor: int | None) -> str:
    n = float(valor or 0)
    for unidade in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidade == "GB":
            return f"{n:.1f} {unidade}" if unidade != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} GB"


def _validar_modelo(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "arquivo ausente"
    try:
        tamanho = path.stat().st_size
    except OSError as exc:
        return False, str(exc)
    if tamanho < MIN_MODEL_BYTES:
        return False, f"arquivo pequeno demais ({tamanho:,} bytes); esperado FP32"
    return True, f"{tamanho:,} bytes"


def _validar_vozes(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, "arquivo ausente"
    try:
        with ZipFile(path, "r") as pacote:
            nomes = {Path(nome).stem for nome in pacote.namelist() if nome.endswith(".npy")}
    except Exception as exc:
        return False, f"não foi possível abrir o pacote de vozes: {exc}"
    faltantes = sorted(TTS_MENU_VOICES - nomes)
    if len(nomes) < MIN_VOICES:
        return False, f"pacote antigo: {len(nomes)} vozes (esperado >= {MIN_VOICES})"
    if faltantes:
        return False, f"faltam vozes configuráveis: {', '.join(faltantes)}"
    return True, f"{len(nomes)} vozes; catálogo configurável OK"


def status_modelos_tts() -> dict:
    """Retorna o estado do conjunto instalado e do download em andamento."""
    model_ok, model_info = _validar_modelo(MODEL_PATH)
    voices_ok, voices_info = _validar_vozes(VOICES_PATH)
    try:
        model_bytes = MODEL_PATH.stat().st_size if MODEL_PATH.is_file() else 0
    except OSError:
        model_bytes = 0
    try:
        voices_bytes = VOICES_PATH.stat().st_size if VOICES_PATH.is_file() else 0
    except OSError:
        voices_bytes = 0

    with _estado_lock:
        estado = dict(_estado)

    estado.update(
        {
            "instalado": bool(model_ok and voices_ok),
            "pasta": str(PASTA_MODELOS_TTS),
            "modelo": {
                "nome": MODEL_NAME,
                "ok": model_ok,
                "detalhe": model_info,
                "bytes": model_bytes,
                "tamanho": _human_bytes(model_bytes),
            },
            "voices": {
                "nome": VOICES_NAME,
                "ok": voices_ok,
                "detalhe": voices_info,
                "bytes": voices_bytes,
                "tamanho": _human_bytes(voices_bytes),
            },
        }
    )
    return estado


def _set_estado(**valores) -> None:
    with _estado_lock:
        _estado.update(valores)


def _baixar_arquivo(url: str, destino_tmp: Path, *, indice: int, nome: str) -> None:
    if destino_tmp.exists():
        destino_tmp.unlink()

    req = Request(url, headers={"User-Agent": "Gutenberg-TTS-Model-Downloader/1.1"})
    _set_estado(
        etapa="baixando",
        mensagem=f"Baixando {nome}...",
        arquivo_atual=nome,
        arquivo_indice=indice,
        bytes_recebidos=0,
        bytes_total=0,
        percentual=0.0,
    )
    logger.info("Download TTS iniciado | arquivo=%s | url=%s | destino=%s", nome, url, destino_tmp)

    try:
        with urlopen(req, timeout=90) as resposta, destino_tmp.open("wb") as saida:
            total = int(resposta.headers.get("Content-Length") or 0)
            recebido = 0
            _set_estado(bytes_total=total)
            while True:
                if _cancelar.is_set():
                    raise DownloadCancelado("Download cancelado pelo usuário.")
                bloco = resposta.read(1024 * 1024)
                if not bloco:
                    break
                saida.write(bloco)
                recebido += len(bloco)
                percentual = (recebido * 100.0 / total) if total else 0.0
                _set_estado(bytes_recebidos=recebido, bytes_total=total, percentual=round(percentual, 2))
        logger.info("Download TTS concluido | arquivo=%s | bytes=%d", nome, destino_tmp.stat().st_size)
    except Exception:
        try:
            destino_tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def _worker_download() -> None:
    model_tmp = MODEL_PATH.with_suffix(MODEL_PATH.suffix + ".part")
    voices_tmp = VOICES_PATH.with_suffix(VOICES_PATH.suffix + ".part")
    try:
        PASTA_MODELOS_TTS.mkdir(parents=True, exist_ok=True)
        _baixar_arquivo(MODEL_URL, model_tmp, indice=1, nome=MODEL_NAME)
        _baixar_arquivo(VOICES_URL, voices_tmp, indice=2, nome=VOICES_NAME)

        _set_estado(etapa="validando", mensagem="Validando modelo e vozes...", percentual=100.0)
        model_ok, model_info = _validar_modelo(model_tmp)
        voices_ok, voices_info = _validar_vozes(voices_tmp)
        if not model_ok or not voices_ok:
            raise RuntimeError(
                "Os arquivos baixados não passaram na validação. "
                f"Modelo: {model_info}; voices: {voices_info}."
            )
        if _cancelar.is_set():
            raise DownloadCancelado("Download cancelado pelo usuário.")

        # Só substitui o conjunto instalado depois que ambos foram baixados e validados.
        os.replace(model_tmp, MODEL_PATH)
        os.replace(voices_tmp, VOICES_PATH)
        _set_estado(
            ativo=False,
            concluido=True,
            cancelado=False,
            etapa="concluido",
            mensagem="Modelos TTS instalados e prontos para uso.",
            erro="",
            arquivo_atual="",
            arquivo_indice=2,
            percentual=100.0,
            finalizado_em=time.time(),
        )
        logger.info("Conjunto TTS instalado | pasta=%s", PASTA_MODELOS_TTS)
    except DownloadCancelado as exc:
        for tmp in (model_tmp, voices_tmp):
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
        _set_estado(
            ativo=False,
            concluido=False,
            cancelado=True,
            etapa="cancelado",
            mensagem=str(exc),
            erro="",
            finalizado_em=time.time(),
        )
        logger.info("Download TTS cancelado")
    except Exception as exc:
        for tmp in (model_tmp, voices_tmp):
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
        _set_estado(
            ativo=False,
            concluido=False,
            cancelado=False,
            etapa="erro",
            mensagem="Falha ao baixar os modelos TTS.",
            erro=str(exc),
            finalizado_em=time.time(),
        )
        logger.exception("Falha no download dos modelos TTS")


def iniciar_download_modelos_tts() -> dict:
    """Inicia um novo download em segundo plano, inclusive para reinstalação."""
    global _thread
    with _estado_lock:
        ja_ativo = bool(_estado.get("ativo"))
        if not ja_ativo:
            _estado.update(
                {
                    "ativo": True,
                    "concluido": False,
                    "cancelado": False,
                    "etapa": "preparando",
                    "mensagem": "Preparando download dos modelos TTS...",
                    "erro": "",
                    "arquivo_atual": "",
                    "arquivo_indice": 0,
                    "arquivo_total_itens": 2,
                    "bytes_recebidos": 0,
                    "bytes_total": 0,
                    "percentual": 0.0,
                    "iniciado_em": time.time(),
                    "finalizado_em": None,
                }
            )
    if ja_ativo:
        return {"ok": True, "ja_ativo": True, "estado": status_modelos_tts()}

    _cancelar.clear()
    _thread = Thread(target=_worker_download, name="GutenbergTTSModelsDownload", daemon=True)
    _thread.start()
    return {"ok": True, "estado": status_modelos_tts()}


def cancelar_download_modelos_tts() -> dict:
    with _estado_lock:
        ativo = bool(_estado.get("ativo"))
    if ativo:
        _cancelar.set()
        _set_estado(mensagem="Cancelando download...")
    return {"ok": True, "estado": status_modelos_tts()}
