# Arquivo de build do PyInstaller
# Créditos do projeto: Nostrand
# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from importlib import metadata as importlib_metadata
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata

project_dir = Path(SPECPATH)


# Valida o ambiente ANTES da análise do PyInstaller. Isso evita gerar um EXE
# aparentemente correto com uma versão diferente do runtime nativo usado pelo TTS.
def _versao_dist(nome):
    try:
        return importlib_metadata.version(nome)
    except importlib_metadata.PackageNotFoundError:
        return None

ORT_ESPERADO = "1.28.0"
PHONEMIZER_ESPERADO = "3.4.0"
ort_instalado = _versao_dist("onnxruntime")
ort_gpu_instalado = _versao_dist("onnxruntime-gpu")
phonemizer_instalado = _versao_dist("phonemizer")
phonemizer_fork_instalado = _versao_dist("phonemizer-fork")

if ort_instalado != ORT_ESPERADO:
    raise RuntimeError(
        "Build cancelado: o ambiente esta com onnxruntime "
        f"{ort_instalado!r}, mas o Gutenberg exige {ORT_ESPERADO}. "
        "Execute: py -m pip uninstall onnxruntime onnxruntime-gpu -y && "
        f"py -m pip install --no-cache-dir --force-reinstall onnxruntime=={ORT_ESPERADO}"
    )
if ort_gpu_instalado:
    raise RuntimeError(
        "Build cancelado: onnxruntime-gpu tambem esta instalado "
        f"({ort_gpu_instalado}). Remova-o para este build CPU: "
        "py -m pip uninstall onnxruntime-gpu -y"
    )

# kokoro-onnx 0.6.1 depende oficialmente de phonemizer>=3.4.0. Não permita
# phonemizer-fork no mesmo ambiente: as duas distribuições instalam o mesmo
# namespace Python `phonemizer`, o que torna o conteúdo congelado ambíguo.
if phonemizer_fork_instalado:
    raise RuntimeError(
        "Build cancelado: phonemizer-fork tambem esta instalado "
        f"({phonemizer_fork_instalado}). O Kokoro 0.6.1 usa phonemizer 3.4.0. "
        "Execute: py -m pip uninstall phonemizer phonemizer-fork -y && "
        f"py -m pip install --no-cache-dir --force-reinstall phonemizer=={PHONEMIZER_ESPERADO}"
    )
if phonemizer_instalado != PHONEMIZER_ESPERADO:
    raise RuntimeError(
        "Build cancelado: phonemizer incorreto ou ausente: "
        f"{phonemizer_instalado!r}. Esperado: {PHONEMIZER_ESPERADO}. "
        "Execute: py -m pip uninstall phonemizer phonemizer-fork -y && "
        f"py -m pip install --no-cache-dir --force-reinstall phonemizer=={PHONEMIZER_ESPERADO}"
    )

try:
    from phonemizer.backend.espeak.wrapper import EspeakWrapper as _EspeakWrapper
except Exception as exc:
    raise RuntimeError(
        "Build cancelado: nao foi possivel importar phonemizer 3.4.0. "
        "Recrie o ambiente e instale requirements.txt antes do build."
    ) from exc

if not callable(getattr(_EspeakWrapper, "set_data_path", None)):
    raise RuntimeError(
        "Build cancelado: o phonemizer ativo nao possui EspeakWrapper.set_data_path(). "
        "Ha uma instalacao inconsistente no ambiente. Remova phonemizer e "
        "phonemizer-fork e reinstale requirements.txt em um ambiente limpo."
    )

print(
    f"[Gutenberg.spec] TTS build validado: onnxruntime={ort_instalado}; "
    f"phonemizer={phonemizer_instalado}; phonemizer-fork={phonemizer_fork_instalado}; "
    f"GPU={ort_gpu_instalado}"
)

icon_path = project_dir / "static" / "img" / "icon.ico"
version_file = project_dir / "version.txt"

# O instalador e o runtime dependem destes recursos. Falhar cedo evita gerar
# um dist parcialmente funcional (por exemplo, sem documentação ou ícones).
recursos_obrigatorios = [
    project_dir / "templates",
    project_dir / "static",
    project_dir / "locales",
    project_dir / "documentation",
    icon_path,
    project_dir / "static" / "img" / "gut_file.ico",
    project_dir / "static" / "img" / "gutr_file.ico",
    version_file,
    project_dir / "hooks" / "rthook_tts_windows.py",
]
ausentes = [str(caminho) for caminho in recursos_obrigatorios if not caminho.exists()]
if ausentes:
    raise RuntimeError(
        "Build cancelado: recursos obrigatorios ausentes:\n - " + "\n - ".join(ausentes)
    )

datas = [
    (str(project_dir / "templates"), "templates"),
    (str(project_dir / "static"), "static"),
    (str(project_dir / "locales"), "locales"),
    (str(project_dir / "documentation"), "documentation"),
    (str(version_file), "."),
]
binaries = []
hiddenimports = [
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "webview.platforms.mshtml",
    "jinja2.ext",
    "pkgutil",
    "pydoc",
    "joblib",
    "joblib.memory",
    "PIL._tkinter_finder",
    "pystray._win32",
    "fitz",
    "msgpack",
    "msgpack._cmsgpack",
    "msgpack.fallback",
    # O TTS e suas dependências são importados parcialmente em runtime.
    "kokoro_onnx",
    "onnxruntime",
    "numpy",
    "espeakng_loader",
    "phonemizer",
    "onnxruntime.capi._pybind_state",
    "onnxruntime.capi.onnxruntime_pybind11_state",
]

# Os modelos Kokoro não são mais empacotados. O aplicativo baixa o conjunto
# kokoro-v1.0.onnx + voices-v1.0.bin sob demanda para LocalAppData/Gutenberg/models.
# O bundle contém somente o motor/runtime TTS.
print("[Gutenberg.spec] Modelos TTS externos: nenhum arquivo de modelo sera incluido no bundle")

# Dados necessários de bibliotecas usadas pelo Gutenberg.
datas += collect_data_files("webview")
datas += collect_data_files("docx")
datas += collect_data_files("reportlab")

# Preserva metadata consultada em runtime e pelas próprias bibliotecas.
for dist_name in ("kokoro-onnx", "onnxruntime", "phonemizer", "espeakng-loader"):
    try:
        datas += copy_metadata(dist_name)
    except Exception:
        pass

# kokoro-onnx depende de onnxruntime, espeakng-loader, phonemizer e numpy.
# Em especial, espeakng-loader traz a DLL e os dados do eSpeak-NG. O WAV é
# serializado com a biblioteca padrão, então não dependemos mais de libsndfile.
for package_name in (
    "kokoro_onnx",
    "espeakng_loader",
    "phonemizer",
):
    try:
        package_datas, package_binaries, package_hidden = collect_all(package_name)
    except Exception:
        continue
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

# ONNX Runtime possui ferramentas opcionais (por exemplo quantization) que
# dependem do pacote `onnx`, mas elas não são usadas pelo TTS. Fazer
# A coleta recursiva de todos os submódulos de onnxruntime força o PyInstaller a tentar
# importar essas ferramentas e gera warnings desnecessários. Coletamos somente
# os dados e DLLs nativos necessários ao runtime; os módulos Python usados pelo
# inference engine são descobertos pela importação normal/hook do PyInstaller.
try:
    datas += collect_data_files("onnxruntime")
except Exception:
    pass
try:
    binaries += collect_dynamic_libs("onnxruntime")
except Exception:
    pass

# Submódulos realmente carregados dinamicamente pelo stack do Kokoro.
for package_name in ("kokoro_onnx", "espeakng_loader", "phonemizer"):
    try:
        hiddenimports += collect_submodules(package_name)
    except Exception:
        pass

# Evita duplicatas mantendo a ordem. Hooks diferentes podem coletar o mesmo
# arquivo/módulo, especialmente no stack do Kokoro/eSpeak/phonemizer.
def _sem_duplicatas_toc(itens):
    resultado = []
    vistos = set()
    for item in itens:
        chave = tuple(str(parte) for parte in item)
        if chave in vistos:
            continue
        vistos.add(chave)
        resultado.append(item)
    return resultado

hiddenimports = list(dict.fromkeys(hiddenimports))
datas = _sem_duplicatas_toc(datas)
binaries = _sem_duplicatas_toc(binaries)

excludes = [
    "PyQt5", "PyQt6", "PySide2", "PySide6",
    "tkinter", "tcl", "tcl8", "tk",
    "matplotlib", "pandas", "scipy",
    "IPython", "jupyter", "notebook",
    "pytest", "unittest", "doctest",
]

block_cipher = None

a = Analysis(
    [str(project_dir / "app.py")],
    pathex=[str(project_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_dir / "hooks" / "rthook_tts_windows.py")],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Gutenberg",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # Desabilitado: DLLs nativas do ONNX Runtime podem ser corrompidas por UPX.
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # O .iss procura os ícones de associação dentro de _internal. Fixar o
    # diretório torna explícito o contrato entre PyInstaller 6+ e Inno Setup.
    contents_directory="_internal",
    icon=str(icon_path),
    version=str(version_file),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    # Mantem DLLs do ONNX/eSpeak sem compressao UPX.
    upx=False,
    upx_exclude=[],
    name="Gutenberg",
)
