"""Integração local de TTS com Kokoro-ONNX para os leitores EPUB."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import os
import sys
import platform
import time
from importlib import metadata as importlib_metadata
from threading import Lock
from hashlib import sha256
from tempfile import gettempdir
from shutil import rmtree
from atexit import register

from .utilidades import RAIZ_RECURSOS, PASTA_MODELOS_TTS
from .logging_config import obter_logger_tts, obter_caminho_log_tts

logger = obter_logger_tts("gutenberg.tts.kokoro")


ROOT = RAIZ_RECURSOS

ORT_ESPERADO_NO_EXE = "1.28.0"
MODEL_FP32_MIN_BYTES = 250_000_000
TTS_CACHE_VERSION = "ptbr-espeak-g2p-v2-voices54"
VOICES_MIN_COUNT = 54
PTBR_VOICES = {"pf_dora", "pm_alex", "pm_santa"}

# Handles devolvidos por os.add_dll_directory precisam permanecer vivos; caso
# contrário o Windows remove o diretório da busca de DLLs. O runtime hook faz
# esta preparação antes de app.py, e esta lista serve como segunda camada de
# proteção caso o módulo seja usado em outro entry point congelado.
_NATIVE_DLL_HANDLES = []
_NATIVE_RUNTIME_CONFIGURED = False


def _registrar_diretorio_dll(caminho: Path) -> None:
    if os.name != "nt" or not caminho.is_dir():
        return
    caminho = caminho.resolve()
    texto = str(caminho)
    try:
        handle = os.add_dll_directory(texto)
        _NATIVE_DLL_HANDLES.append(handle)
    except (AttributeError, FileNotFoundError, OSError):
        logger.exception("Nao foi possivel registrar diretorio de DLL | pasta=%s", caminho)

    # Alguns loaders consultam PATH diretamente mesmo em Python 3.8+.
    atual = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    if texto.lower() not in {p.lower() for p in atual}:
        os.environ["PATH"] = texto + os.pathsep + os.environ.get("PATH", "")


def _configurar_runtime_nativo_tts() -> None:
    """Prepara subdiretórios nativos usados pelo TTS no bundle do Windows."""
    global _NATIVE_RUNTIME_CONFIGURED
    if _NATIVE_RUNTIME_CONFIGURED:
        return
    _NATIVE_RUNTIME_CONFIGURED = True

    if os.name != "nt" or not getattr(sys, "frozen", False):
        return

    raiz = Path(getattr(sys, "_MEIPASS", RAIZ_RECURSOS)).resolve()
    pasta_ort = raiz / "onnxruntime" / "capi"
    pasta_espeak = raiz / "espeakng_loader"

    logger.info(
        "Preparando runtime nativo congelado | raiz=%s | ort=%s | espeak=%s",
        raiz,
        pasta_ort,
        pasta_espeak,
    )
    for pasta in (raiz, pasta_ort, pasta_espeak):
        _registrar_diretorio_dll(pasta)
        logger.info("Diretorio DLL TTS | pasta=%s | existe=%s", pasta, pasta.is_dir())

    # O runtime hook normalmente já define estas variáveis, porém resolvê-las
    # novamente aqui torna server_only.py/entry points alternativos igualmente
    # seguros se também forem congelados no futuro.
    if pasta_espeak.is_dir():
        candidatos_dll = [
            pasta_espeak / "espeak-ng.dll",
            pasta_espeak / "libespeak-ng.dll",
            pasta_espeak / "espeak.dll",
            pasta_espeak / "libespeak.dll",
        ]
        candidatos_dll.extend(
            p for p in pasta_espeak.glob("*.dll") if "espeak" in p.name.lower()
        )
        dll_espeak = next((p for p in candidatos_dll if p.is_file()), None)
        dados_espeak = pasta_espeak / "espeak-ng-data"
        if dll_espeak:
            os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = str(dll_espeak.resolve())
        if dados_espeak.is_dir():
            os.environ["PHONEMIZER_ESPEAK_DATA_PATH"] = str(dados_espeak.resolve())
        logger.info(
            "eSpeak bundle | dll=%s | dados=%s | dados_existem=%s",
            dll_espeak,
            dados_espeak,
            dados_espeak.is_dir(),
        )


def _diretorios_modelos_candidatos() -> list[Path]:
    """Retorna o único local persistente usado pelos modelos externos do TTS."""
    return [PASTA_MODELOS_TTS]


def _resolver_modelos() -> tuple[Path, Path, Path]:
    """Resolve o par de arquivos externos em LocalAppData/Gutenberg/models."""
    pasta = PASTA_MODELOS_TTS
    return pasta, pasta / "kokoro-v1.0.onnx", pasta / "voices-v1.0.bin"


MODELS_DIR, MODEL_PATH, VOICES_PATH = _resolver_modelos()


def _tamanho_arquivo(caminho: Path) -> int | None:
    try:
        return caminho.stat().st_size if caminho.is_file() else None
    except OSError:
        return None


def _classificar_modelo(caminho: Path) -> str:
    """Classifica a variante pelo nome/tamanho para evitar FP16 renomeado no build CPU."""
    nome = caminho.name.lower()
    tamanho = _tamanho_arquivo(caminho)
    if ".fp16." in nome:
        return "fp16"
    if ".int8." in nome:
        return "int8"
    if tamanho is None:
        return "ausente"
    if 140_000_000 <= tamanho < MODEL_FP32_MIN_BYTES:
        return "fp16-provavel"
    if 60_000_000 <= tamanho < 140_000_000:
        return "int8-provavel"
    if tamanho >= MODEL_FP32_MIN_BYTES:
        return "fp32"
    return "desconhecido"


def _validar_modelo_cpu() -> None:
    variante = _classificar_modelo(MODEL_PATH)
    tamanho = _tamanho_arquivo(MODEL_PATH)
    logger.info(
        "Validacao modelo CPU | arquivo=%s | bytes=%s | variante=%s | minimo_fp32=%s",
        MODEL_PATH,
        tamanho,
        variante,
        MODEL_FP32_MIN_BYTES,
    )
    if variante != "fp32":
        raise RuntimeError(
            "O modelo TTS instalado não parece ser o kokoro-v1.0.onnx FP32 oficial. "
            f"Detectado: {variante}; tamanho={tamanho} bytes. "
            "Use o botão de download em Configurações para reinstalar o modelo FP32 oficial. "
            "Nao renomeie kokoro-v1.0.fp16.onnx para kokoro-v1.0.onnx."
        )


def _versao_pacote(nome: str) -> str:
    try:
        return importlib_metadata.version(nome)
    except Exception:
        return "indisponivel"


def _registrar_diagnostico_inicial() -> None:
    """Grava o layout real do runtime sem registrar conteúdo do livro."""
    logger.info(
        "Runtime TTS | frozen=%s | python=%s | plataforma=%s",
        bool(getattr(sys, "frozen", False)),
        sys.version.replace("\n", " "),
        platform.platform(),
    )
    logger.info(
        "Caminhos runtime | executable=%s | cwd=%s | _MEIPASS=%s | RAIZ_RECURSOS=%s | modulo=%s",
        sys.executable,
        os.getcwd(),
        getattr(sys, "_MEIPASS", None),
        RAIZ_RECURSOS,
        Path(__file__).resolve(),
    )
    for idx, pasta in enumerate(_diretorios_modelos_candidatos(), start=1):
        modelo = pasta / "kokoro-v1.0.onnx"
        vozes = pasta / "voices-v1.0.bin"
        logger.info(
            "Candidato models #%d | pasta=%s | pasta_existe=%s | model_existe=%s | model_bytes=%s | voices_existe=%s | voices_bytes=%s",
            idx,
            pasta,
            pasta.exists(),
            modelo.is_file(),
            _tamanho_arquivo(modelo),
            vozes.is_file(),
            _tamanho_arquivo(vozes),
        )
    logger.info(
        "Modelos selecionados | pasta=%s | model=%s | model_bytes=%s | variante=%s | voices=%s | log=%s",
        MODELS_DIR,
        MODEL_PATH,
        _tamanho_arquivo(MODEL_PATH),
        _classificar_modelo(MODEL_PATH),
        VOICES_PATH,
        obter_caminho_log_tts(),
    )
    logger.info(
        "Versoes declaradas | kokoro-onnx=%s | onnxruntime=%s | numpy=%s | espeakng-loader=%s | phonemizer=%s | phonemizer-fork=%s",
        _versao_pacote("kokoro-onnx"),
        _versao_pacote("onnxruntime"),
        _versao_pacote("numpy"),
        _versao_pacote("espeakng-loader"),
        _versao_pacote("phonemizer"),
        _versao_pacote("phonemizer-fork"),
    )


_registrar_diagnostico_inicial()

_KOKORO = None
_KOKORO_LOCK = Lock()
_SYNTHESIS_LOCK = Lock()
_PTBR_G2P = None
_PTBR_G2P_LOCK = Lock()

# Cache temporário do processo. Os arquivos evitam que o mesmo trecho seja
# sintetizado novamente e permitem que várias requisições de pré-carregamento
# compartilhem o resultado. A pasta é removida quando o servidor termina.
_CACHE_DIR = Path(gettempdir()) / "gutenberg_kokoro_tts"
_CACHE_LOCK = Lock()


def _samples_para_wav_pcm16(samples, sample_rate: int) -> bytes:
    """Serializa samples do Kokoro em WAV PCM16 sem depender de libsndfile.

    ``soundfile`` era usado apenas para esta conversão e introduzia mais uma DLL
    nativa no EXE. A biblioteca padrão ``wave`` é suficiente para o formato PCM16.
    """
    import wave
    import numpy as np

    try:
        taxa = int(sample_rate)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Sample rate inválido: {sample_rate!r}") from exc
    if taxa <= 0:
        raise ValueError(f"Sample rate inválido: {taxa}")

    dados = np.asarray(samples)
    if dados.size == 0:
        raise ValueError("O Kokoro retornou zero amostras de áudio.")
    if dados.ndim == 0:
        dados = dados.reshape(1)
    elif dados.ndim > 2:
        dados = dados.reshape(-1)

    # Normalmente Kokoro devolve mono (N,). Se vier (canais, frames), converte
    # para a disposição intercalada (frames, canais) esperada pelo WAV.
    if dados.ndim == 2 and dados.shape[0] <= 8 and dados.shape[1] > dados.shape[0]:
        dados = dados.T
    canais = 1 if dados.ndim == 1 else int(dados.shape[1])
    if canais < 1 or canais > 8:
        raise ValueError(f"Quantidade de canais inválida: {canais}")

    if np.issubdtype(dados.dtype, np.floating):
        dados = np.nan_to_num(dados, nan=0.0, posinf=1.0, neginf=-1.0)
        pcm = np.rint(np.clip(dados, -1.0, 1.0) * 32767.0).astype("<i2")
    elif np.issubdtype(dados.dtype, np.integer):
        if dados.dtype.itemsize == 2 and np.issubdtype(dados.dtype, np.signedinteger):
            pcm = dados.astype("<i2", copy=False)
        else:
            info = np.iinfo(dados.dtype)
            escala = float(max(abs(int(info.min)), abs(int(info.max)))) or 1.0
            normalizado = np.clip(dados.astype(np.float64) / escala, -1.0, 1.0)
            pcm = np.rint(normalizado * 32767.0).astype("<i2")
    else:
        raise TypeError(f"Tipo de samples não suportado: {dados.dtype}")

    pcm = np.ascontiguousarray(pcm, dtype="<i2")
    saida = BytesIO()
    with wave.open(saida, "wb") as wav:
        wav.setnchannels(canais)
        wav.setsampwidth(2)
        wav.setframerate(taxa)
        wav.writeframes(pcm.tobytes(order="C"))
    audio = saida.getvalue()
    if not audio.startswith(b"RIFF") or audio[8:12] != b"WAVE":
        raise RuntimeError("Falha interna ao serializar o WAV PCM16.")
    return audio


def normalizar_idioma_tts(valor: str | None, fallback: str = "pt-BR") -> str:
    valor = str(valor or "").strip().lower().replace("_", "-")
    fallback = str(fallback or "pt-BR").strip().lower().replace("_", "-")
    if valor.startswith("pt"):
        return "pt-br"
    if valor.startswith("en"):
        return "en-us"
    if fallback.startswith("en"):
        return "en-us"
    return "pt-br"


def obter_kokoro():
    global _KOKORO
    if _KOKORO is not None:
        logger.debug("Kokoro reutilizado da memoria")
        return _KOKORO
    with _KOKORO_LOCK:
        if _KOKORO is not None:
            logger.debug("Kokoro reutilizado da memoria apos lock")
            return _KOKORO

        logger.info(
            "Inicializacao Kokoro solicitada | model=%s | voices=%s | model_existe=%s | voices_existe=%s",
            MODEL_PATH,
            VOICES_PATH,
            MODEL_PATH.is_file(),
            VOICES_PATH.is_file(),
        )
        if not MODEL_PATH.is_file() or not VOICES_PATH.is_file():
            procurados = " | ".join(str(p) for p in _diretorios_modelos_candidatos())
            logger.error(
                "Modelos Kokoro ausentes | model=%s | voices=%s | diretorios=%s",
                MODEL_PATH,
                VOICES_PATH,
                procurados,
            )
            raise FileNotFoundError(
                "Os modelos do TTS ainda não estão instalados. "
                "Abra Configurações e use o botão 'Baixar modelos TTS'. "
                f"Pasta esperada: {MODELS_DIR}"
            )

        # Registra subdiretórios de DLL antes do primeiro import nativo. Em
        # execução normal isso é um no-op; no PyInstaller corrige a diferença
        # entre o diretório superior (_internal) e onnxruntime/capi/espeakng_loader.
        _configurar_runtime_nativo_tts()

        # Falha de forma controlada antes de entrar em bibliotecas nativas se
        # o arquivo tiver sido trocado por uma variante FP16/INT8 renomeada.
        _validar_modelo_cpu()

        inicio_imports = time.perf_counter()
        try:
            logger.info("Importando numpy")
            import numpy as np
            logger.info(
                "numpy importado | arquivo=%s | versao=%s",
                getattr(np, "__file__", None),
                getattr(np, "__version__", None),
            )

            # O pacote antigo de voices-v1.0.bin tinha apenas 26 vozes.
            # O release atual model-files-v1.1 publica 54 vozes e deve ser
            # usado como par com o modelo atual. Validamos o conteúdo, não
            # apenas o nome/tamanho do arquivo, para impedir misturas de releases.
            try:
                with np.load(str(VOICES_PATH), allow_pickle=False) as pacote_vozes:
                    nomes_vozes = set(pacote_vozes.files)
            except Exception as exc:
                raise RuntimeError(
                    f"Não foi possível abrir voices-v1.0.bin como pacote NPZ: {exc}"
                ) from exc
            faltantes_ptbr = sorted(PTBR_VOICES - nomes_vozes)
            logger.info(
                "Pacote de vozes inspecionado | total=%d | ptbr_presentes=%s | faltantes_ptbr=%s",
                len(nomes_vozes),
                sorted(PTBR_VOICES & nomes_vozes),
                faltantes_ptbr,
            )
            if len(nomes_vozes) < VOICES_MIN_COUNT or faltantes_ptbr:
                raise RuntimeError(
                    "voices-v1.0.bin desatualizado ou incompatível. "
                    f"Foram encontradas {len(nomes_vozes)} vozes; esperado pelo menos "
                    f"{VOICES_MIN_COUNT}, incluindo pf_dora, pm_alex e pm_santa. "
                    "Baixe modelo e voices juntos do release model-files-v1.1."
                )

            logger.info("Importando onnxruntime")
            import onnxruntime as ort
            try:
                providers = ort.get_available_providers()
            except Exception:
                providers = ["erro_ao_consultar"]
                logger.exception("Falha consultando providers do onnxruntime")
            logger.info(
                "onnxruntime importado | arquivo=%s | versao=%s | providers=%s",
                getattr(ort, "__file__", None),
                getattr(ort, "__version__", None),
                providers,
            )
            ort_versao_runtime = str(getattr(ort, "__version__", "") or "")
            if getattr(sys, "frozen", False) and ort_versao_runtime != ORT_ESPERADO_NO_EXE:
                raise RuntimeError(
                    "Versao incorreta do ONNX Runtime no executavel: "
                    f"{ort_versao_runtime or 'desconhecida'}. Esperado: {ORT_ESPERADO_NO_EXE}. "
                    "Reinstale as dependencias e gere o build novamente; o Gutenberg.spec "
                    "tambem bloqueia builds com a versao errada."
                )

            # No bundle, o eSpeak-NG não é uma instalação de sistema: ele vem
            # do pacote espeakng-loader. Tornar a DLL disponível antes de criar
            # o Kokoro evita o fallback para um eSpeak inexistente no Windows.
            logger.info("Importando espeakng_loader")
            import espeakng_loader
            logger.info(
                "espeakng_loader importado | arquivo=%s",
                getattr(espeakng_loader, "__file__", None),
            )

            try:
                espeakng_loader.make_library_available()
                logger.info("espeakng_loader.make_library_available concluido")
            except Exception:
                logger.exception("Falha em espeakng_loader.make_library_available")

            try:
                espeak_lib = Path(espeakng_loader.get_library_path())
                logger.info(
                    "Biblioteca eSpeak resolvida | path=%s | existe=%s | bytes=%s",
                    espeak_lib,
                    espeak_lib.is_file(),
                    _tamanho_arquivo(espeak_lib),
                )
                espeak_data = Path(espeakng_loader.get_data_path())
                _registrar_diretorio_dll(espeak_lib.parent)
                if espeak_lib.is_file():
                    os.environ["PHONEMIZER_ESPEAK_LIBRARY"] = str(espeak_lib)
                if espeak_data.is_dir():
                    os.environ["PHONEMIZER_ESPEAK_DATA_PATH"] = str(espeak_data)
                logger.info(
                    "eSpeak configurado | library=%s | data=%s | data_existe=%s",
                    os.environ.get("PHONEMIZER_ESPEAK_LIBRARY"),
                    os.environ.get("PHONEMIZER_ESPEAK_DATA_PATH"),
                    espeak_data.is_dir(),
                )
            except Exception:
                logger.exception("Falha ao resolver/configurar a biblioteca eSpeak")

            # joblib (usado pelo phonemizer) importa pydoc. Em builds
            # PyInstaller, mantemos a importação explícita para que a stdlib
            # necessária não seja eliminada do bundle.
            logger.info("Importando pydoc e joblib")
            import pydoc
            import joblib
            logger.info(
                "pydoc/joblib importados | pydoc=%s | joblib=%s | joblib_versao=%s",
                getattr(pydoc, "__file__", None),
                getattr(joblib, "__file__", None),
                getattr(joblib, "__version__", None),
            )

            logger.info("Importando kokoro_onnx.Kokoro")
            from kokoro_onnx import Kokoro
            logger.info(
                "kokoro_onnx.Kokoro importado | duracao_ms=%.2f",
                (time.perf_counter() - inicio_imports) * 1000,
            )
        except ImportError as exc:
            logger.exception("Dependencia do Kokoro ausente durante import")
            raise RuntimeError(
                "Dependência do Kokoro ausente no executável. "
                "Recrie o build usando Gutenberg.spec e requirements.txt. "
                f"Detalhe: {exc}"
            ) from exc
        except Exception as exc:
            logger.exception("Falha inesperada preparando dependencias do Kokoro")
            raise RuntimeError(
                "Falha preparando as dependências do Kokoro no executável. "
                f"Detalhe: {exc}"
            ) from exc

        inicio_modelo = time.perf_counter()
        try:
            # O mesmo arquivo kokoro-v1.0.onnx funciona em CPU e GPU; quem
            # escolhe o dispositivo e o Execution Provider e o ONNX Runtime.
            # No executavel usamos explicitamente CPUExecutionProvider para
            # evitar providers automaticos e manter o bundle independente de
            # CUDA/DirectML. A sessao manual tambem facilita diagnosticar
            # crashes nativos do ORT dentro do PyInstaller.
            provider_cpu = "CPUExecutionProvider"
            providers_disponiveis = ort.get_available_providers()
            if provider_cpu not in providers_disponiveis:
                raise RuntimeError(
                    f"CPUExecutionProvider nao disponivel. Providers: {providers_disponiveis}"
                )

            sess_options = ort.SessionOptions()
            sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            sess_options.inter_op_num_threads = 1
            # Limita o pool interno; em aplicacao empacotada evita excesso de
            # threads nativas e deixa o comportamento mais previsivel.
            cpu_count = os.cpu_count() or 1
            sess_options.intra_op_num_threads = max(1, min(cpu_count, 4))

            logger.info(
                "Criando sessao ONNX CPU | provider=%s | intra_threads=%d | inter_threads=%d | execution_mode=ORT_SEQUENTIAL",
                provider_cpu,
                sess_options.intra_op_num_threads,
                sess_options.inter_op_num_threads,
            )
            inicio_sessao = time.perf_counter()
            sessao = ort.InferenceSession(
                str(MODEL_PATH),
                sess_options=sess_options,
                providers=[provider_cpu],
            )
            logger.info(
                "Sessao ONNX CPU criada | duracao_ms=%.2f | providers_ativos=%s",
                (time.perf_counter() - inicio_sessao) * 1000,
                sessao.get_providers(),
            )

            logger.info("Criando instancia Kokoro a partir da sessao CPU")
            _KOKORO = Kokoro.from_session(sessao, str(VOICES_PATH))
            logger.info(
                "Instancia Kokoro CPU criada | duracao_ms=%.2f | provider_primario=%s",
                (time.perf_counter() - inicio_modelo) * 1000,
                sessao.get_providers()[0] if sessao.get_providers() else None,
            )
        except Exception as exc:
            logger.exception(
                "Falha ao inicializar Kokoro | model=%s | voices=%s",
                MODEL_PATH,
                VOICES_PATH,
            )
            raise RuntimeError(
                "Falha ao inicializar Kokoro no executável. "
                f"Modelo: {MODEL_PATH}; vozes: {VOICES_PATH}; erro: {exc}"
            ) from exc
    return _KOKORO

def _obter_g2p_ptbr():
    """Cria o G2P PT-BR recomendado para Kokoro v1.0.

    O tokenizer interno do kokoro-onnx foi historicamente orientado a
    en-us/en-gb. Para as vozes multilíngues do Kokoro v1.0, o exemplo
    oficial de português usa o fluxo EspeakG2P do Misaki. Reproduzimos
    aqui apenas essa pequena etapa, usando as dependências já presentes
    (phonemizer + espeakng-loader), evitando adicionar Misaki/Spacy
    ao executável Python 3.13.
    """
    global _PTBR_G2P
    if _PTBR_G2P is not None:
        return _PTBR_G2P

    with _PTBR_G2P_LOCK:
        if _PTBR_G2P is not None:
            return _PTBR_G2P

        try:
            import espeakng_loader
            import phonemizer
            from phonemizer.backend.espeak.wrapper import EspeakWrapper

            # Força o phonemizer a usar exatamente a DLL/dados empacotados.
            lib_path = str(espeakng_loader.get_library_path())
            data_path = str(espeakng_loader.get_data_path())
            EspeakWrapper.set_library(lib_path)
            EspeakWrapper.set_data_path(data_path)

            logger.info(
                "Criando G2P PT-BR | engine=espeak-ng | language=pt-br | lib=%s | data=%s",
                lib_path,
                data_path,
            )
            _PTBR_G2P = phonemizer.backend.EspeakBackend(
                language="pt-br",
                preserve_punctuation=True,
                with_stress=True,
                tie="^",
                language_switch="remove-flags",
            )
        except Exception as exc:
            logger.exception("Falha criando G2P PT-BR compativel com Kokoro")
            raise RuntimeError(
                "Não foi possível inicializar a fonemização PT-BR do Kokoro. "
                f"Detalhe: {exc}"
            ) from exc

    return _PTBR_G2P


def _phonemizar_ptbr_kokoro(texto: str) -> str:
    """Converte português brasileiro para o alfabeto fonético do Kokoro.

    Equivale ao EspeakG2P(language='pt-br') recomendado nos exemplos
    oficiais do kokoro-onnx/Misaki para português.
    """
    backend = _obter_g2p_ptbr()

    # Mesmas normalizações estruturais do EspeakG2P do Misaki.
    preparado = str(texto or "").replace("«", "“").replace("»", "”")
    preparado = preparado.replace("(", "«").replace(")", "»")

    resultado = backend.phonemize([preparado])
    if not resultado:
        return ""
    fonemas = str(resultado[0] or "").strip()

    # Conversões espeak -> símbolos usados pelo vocabulário Kokoro v1.0.
    # A ordem acompanha o EspeakG2P do Misaki.
    conversoes = (
        ("a^ɪ", "I"),
        ("a^ʊ", "W"),
        ("d^z", "ʣ"),
        ("d^ʒ", "ʤ"),
        ("e^ɪ", "A"),
        ("o^ʊ", "O"),
        ("ə^ʊ", "Q"),
        ("s^s", "S"),
        ("t^s", "ʦ"),
        ("t^ʃ", "ʧ"),
        ("ɔ^ɪ", "Y"),
    )
    for antigo, novo in conversoes:
        fonemas = fonemas.replace(antigo, novo)

    fonemas = fonemas.replace("^", "").replace("-", "")
    fonemas = fonemas.replace("«", "(").replace("»", ")")
    return fonemas.strip()


def _fonemizar_para_kokoro(kokoro, texto: str, lang: str) -> tuple[str, str]:
    """Seleciona o G2P correto e retorna (fonemas, mecanismo)."""
    if lang == "pt-br":
        return _phonemizar_ptbr_kokoro(texto), "espeak-g2p-pt-br"
    return kokoro.tokenizer.phonemize(texto, lang=lang), "kokoro-tokenizer"


def _normalizar_velocidade(valor: float | int | str | None, padrao: float = 1.0) -> float:
    try:
        velocidade = float(valor)
    except (TypeError, ValueError):
        velocidade = padrao
    if velocidade != velocidade or velocidade in (float("inf"), float("-inf")):
        velocidade = padrao
    return round(max(0.75, min(1.25, velocidade)), 2)


def _chave_cache(texto: str, idioma: str, fallback: str, velocidade: float = 1.0) -> str:
    velocidade = _normalizar_velocidade(velocidade)
    payload = f"{TTS_CACHE_VERSION}\\0{normalizar_idioma_tts(idioma, fallback)}\\0{velocidade:.2f}\\0{texto}"
    return sha256(payload.encode("utf-8")).hexdigest()


def _arquivo_cache(texto: str, idioma: str, fallback: str, velocidade: float = 1.0) -> Path:
    return _CACHE_DIR / f"{_chave_cache(texto, idioma, fallback, velocidade)}.wav"


def limpar_cache_tts() -> None:
    try:
        if _CACHE_DIR.exists():
            rmtree(_CACHE_DIR, ignore_errors=True)
    except Exception:
        pass


register(limpar_cache_tts)


def sintetizar_wav(texto: str, idioma: str, fallback: str = "pt-BR", velocidade: float = 1.0) -> bytes:
    texto = " ".join(str(texto or "").split())
    if not texto:
        logger.warning("Sintese recusada: texto vazio")
        raise ValueError("Texto vazio para síntese.")
    if len(texto) > 1400:
        logger.warning("Sintese recusada: trecho muito grande | chars=%d", len(texto))
        raise ValueError("Trecho muito grande para síntese.")

    lang = normalizar_idioma_tts(idioma, fallback)
    velocidade = _normalizar_velocidade(velocidade)
    chave = _chave_cache(texto, lang, fallback, velocidade)
    req_id = chave[:12]
    caminho_cache = _CACHE_DIR / f"{chave}.wav"
    inicio_total = time.perf_counter()

    logger.info(
        "Sintese iniciada | req=%s | chars=%d | idioma_entrada=%s | lang=%s | velocidade=%.2f | cache=%s",
        req_id,
        len(texto),
        idioma,
        lang,
        velocidade,
        caminho_cache,
    )

    # Mais de uma requisição pode chegar ao mesmo trecho por causa do
    # pré-carregamento. O lock garante que apenas uma o sintetize.
    with _CACHE_LOCK:
        if caminho_cache.exists():
            try:
                audio_cache = caminho_cache.read_bytes()
                logger.info(
                    "Cache TTS hit | req=%s | bytes=%d | duracao_ms=%.2f",
                    req_id,
                    len(audio_cache),
                    (time.perf_counter() - inicio_total) * 1000,
                )
                return audio_cache
            except OSError:
                logger.exception("Falha lendo cache TTS | req=%s | arquivo=%s", req_id, caminho_cache)
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        except Exception:
            logger.exception("Falha criando pasta de cache TTS | req=%s | pasta=%s", req_id, _CACHE_DIR)
            raise

    kokoro = obter_kokoro()
    voz = "pf_dora" if lang == "pt-br" else "af_heart"
    logger.info("Parametros de inferencia | req=%s | voz=%s | lang=%s | speed=%.2f", req_id, voz, lang, velocidade)

    # A inferência do ONNX é serializada para evitar disputa pelo mesmo
    # objeto Kokoro. Isso não bloqueia a reprodução no navegador: enquanto
    # o áudio atual toca, a próxima requisição fica sendo processada aqui.
    with _SYNTHESIS_LOCK:
        with _CACHE_LOCK:
            if caminho_cache.exists():
                try:
                    audio_cache = caminho_cache.read_bytes()
                    logger.info("Cache TTS hit apos lock | req=%s | bytes=%d", req_id, len(audio_cache))
                    return audio_cache
                except OSError:
                    logger.exception("Falha lendo cache TTS apos lock | req=%s", req_id)

        inicio_inferencia = time.perf_counter()
        try:
            # Separamos fonemizacao e ONNX para que um eventual crash nativo
            # deixe no TXT qual das duas etapas foi a ultima executada.
            inicio_fonemas = time.perf_counter()
            logger.info("Fonemizacao iniciada | req=%s | lang=%s", req_id, lang)
            phonemes, mecanismo_g2p = _fonemizar_para_kokoro(kokoro, texto, lang)
            if not phonemes:
                raise RuntimeError("A fonemização não produziu fonemas para o trecho.")
            logger.info(
                "Fonemizacao concluida | req=%s | duracao_ms=%.2f | phonemes=%d | mecanismo=%s",
                req_id,
                (time.perf_counter() - inicio_fonemas) * 1000,
                len(phonemes),
                mecanismo_g2p,
            )

            logger.info(
                "Inferencia ONNX iniciada | req=%s | is_phonemes=True | voz=%s | g2p=%s",
                req_id,
                voz,
                mecanismo_g2p,
            )
            # Como já fornecemos fonemas prontos, não pedimos ao Kokoro para
            # reinterpretar o idioma. A voz pf_dora carrega a identidade PT-BR.
            samples, sample_rate = kokoro.create(
                phonemes,
                voice=voz,
                speed=velocidade,
                is_phonemes=True,
            )
            shape = getattr(samples, "shape", None)
            dtype = getattr(samples, "dtype", None)
            try:
                qtd_samples = len(samples)
            except Exception:
                qtd_samples = None
            logger.info(
                "Inferencia ONNX concluida | req=%s | duracao_ms=%.2f | sample_rate=%s | samples=%s | shape=%s | dtype=%s",
                req_id,
                (time.perf_counter() - inicio_inferencia) * 1000,
                sample_rate,
                qtd_samples,
                shape,
                dtype,
            )
        except Exception as exc:
            logger.exception("Falha na inferencia Kokoro | req=%s | voz=%s | lang=%s", req_id, voz, lang)
            raise RuntimeError(f"Falha ao sintetizar o trecho com Kokoro: {exc}") from exc

        inicio_wav = time.perf_counter()
        try:
            audio = _samples_para_wav_pcm16(samples, sample_rate)
            logger.info(
                "WAV PCM16 criado sem libsndfile | req=%s | bytes=%d | duracao_ms=%.2f | assinatura=%s",
                req_id,
                len(audio),
                (time.perf_counter() - inicio_wav) * 1000,
                audio[:12].hex(),
            )
        except Exception as exc:
            logger.exception("Falha convertendo samples para WAV PCM16 | req=%s", req_id)
            raise RuntimeError(f"Falha ao criar o WAV do TTS: {exc}") from exc

        # Escrita atômica: uma segunda requisição nunca verá um WAV incompleto.
        temporario = caminho_cache.with_suffix(".tmp")
        try:
            temporario.write_bytes(audio)
            temporario.replace(caminho_cache)
            logger.info("Cache TTS gravado | req=%s | arquivo=%s | bytes=%d", req_id, caminho_cache, len(audio))
        except OSError:
            logger.exception("Falha gravando cache TTS | req=%s | arquivo=%s", req_id, caminho_cache)
            try:
                temporario.unlink(missing_ok=True)
            except OSError:
                pass

        logger.info(
            "Sintese concluida | req=%s | bytes=%d | duracao_total_ms=%.2f",
            req_id,
            len(audio),
            (time.perf_counter() - inicio_total) * 1000,
        )
        return audio

