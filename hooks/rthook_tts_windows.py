"""Prepara DLLs nativas do TTS antes dos imports tardios no executável.

Executado pelo PyInstaller antes de ``app.py``. O ONNX Runtime e o
espeakng-loader mantêm DLLs em subdiretórios do bundle; no Windows essas
pastas precisam permanecer registradas no mecanismo de busca de DLLs durante
toda a vida do processo.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


_DLL_HANDLES = []


def _registrar_pasta_dll(caminho: Path) -> None:
    if os.name != "nt" or not caminho.is_dir():
        return

    texto = str(caminho.resolve())
    try:
        handle = os.add_dll_directory(texto)
        _DLL_HANDLES.append(handle)
    except (AttributeError, FileNotFoundError, OSError):
        pass

    # Alguns componentes nativos ainda consultam PATH diretamente. Não remove
    # o diretório configurado pelo bootloader; apenas acrescenta subpastas do TTS.
    partes = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    if texto.lower() not in {p.lower() for p in partes}:
        os.environ["PATH"] = texto + os.pathsep + os.environ.get("PATH", "")


def _localizar_primeiro(base: Path, nomes: tuple[str, ...]) -> Path | None:
    for nome in nomes:
        candidato = base / nome
        if candidato.is_file():
            return candidato
    if base.is_dir():
        for candidato in base.glob("*.dll"):
            if "espeak" in candidato.name.lower():
                return candidato
    return None


def _preparar() -> None:
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return

    raiz = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    pasta_ort = raiz / "onnxruntime" / "capi"
    pasta_espeak = raiz / "espeakng_loader"

    for pasta in (raiz, pasta_ort, pasta_espeak):
        _registrar_pasta_dll(pasta)

    dll_espeak = _localizar_primeiro(
        pasta_espeak,
        ("espeak-ng.dll", "libespeak-ng.dll", "espeak.dll", "libespeak.dll"),
    )
    dados_espeak = pasta_espeak / "espeak-ng-data"

    if dll_espeak:
        os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = str(dll_espeak.resolve())
    if dados_espeak.is_dir():
        os.environ["PHONEMIZER_ESPEAK_DATA_PATH"] = str(dados_espeak.resolve())

    # Mantém os objetos retornados por os.add_dll_directory() vivos. Ao fechar
    # esses handles, o Windows remove a pasta da lista de busca.
    setattr(sys, "_gutenberg_tts_dll_handles", _DLL_HANDLES)


_preparar()
