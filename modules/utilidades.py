"""Funções utilitárias para o projeto."""
from __future__ import annotations

import base64
import ctypes
import locale
import os
import re
import sys
import unicodedata
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from typing import Tuple
from .logging_config import obter_logger, registrar_etapa
logger = obter_logger(__name__)

APP_NOME = "Gutenberg"
APP_VERSAO = "1.0.1"
RAIZ_PROJETO = Path(__file__).resolve().parent.parent
RAIZ_RECURSOS = Path(getattr(sys, "_MEIPASS", RAIZ_PROJETO))


@registrar_etapa
def _pasta_appdata_windows() -> Path:
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
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_NOME
    return RAIZ_PROJETO / APP_NOME / "appdata"


@registrar_etapa
def _obter_known_folder_documentos_windows() -> Path | None:
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
    if os.name != "nt":
        return None

    try:
        class GUID(ctypes.Structure):
            """
            Representa GUID dentro do fluxo da aplicação.
        
            Esta classe concentra estado e comportamentos relacionados para evitar que a
            lógica fique espalhada por vários pontos do código. A intenção é oferecer uma
            interface simples para quem consome o módulo, escondendo os detalhes internos
            de organização, validação e integração com os demais componentes.
            """
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



@registrar_etapa
def _nomes_candidatos_documentos() -> list[str]:
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
    idioma = (locale.getdefaultlocale()[0] or "").lower() if locale.getdefaultlocale() else ""
    if idioma.startswith("pt"):
        return ["Documentos", "documentos", "Documents", "documents"]
    if idioma.startswith("es"):
        return ["Documentos", "documentos", "Documents", "documents"]
    return ["Documents", "documents", "Documentos", "documentos"]


@registrar_etapa
def _pasta_documentos_windows() -> Path:
    """Retorna a pasta oficial de dados do Gutenberg em Documentos/Gutenberg.

    No Windows, a pasta Documentos pode estar redirecionada para OneDrive ou ter
    nome físico diferente do nome exibido no Explorador. Por isso, a prioridade é
    sempre consultar a Known Folder oficial do sistema, em vez de tentar adivinhar
    manualmente entre Documents/Documentos.
    """
    pasta_sistema = _obter_known_folder_documentos_windows()
    if pasta_sistema:
        return pasta_sistema / APP_NOME

    perfil = Path(os.environ.get("USERPROFILE") or str(Path.home()))
    nomes = _nomes_candidatos_documentos()

    candidatos: list[Path] = []
    for base in [perfil / "OneDrive", perfil]:
        for nome in nomes:
            candidatos.append(base / nome)

    for candidato in candidatos:
        if candidato.exists():
            return candidato / APP_NOME

    return perfil / nomes[0] / APP_NOME



PASTA_APP = _pasta_appdata_windows()
PASTA_DOCUMENTOS_APP = _pasta_documentos_windows()
PASTA_PROJETOS = PASTA_DOCUMENTOS_APP / "projects"
EXPORTS_PADRAO = PASTA_DOCUMENTOS_APP / "exports"
BIBLIOTECA_PADRAO = PASTA_DOCUMENTOS_APP / "library"
ARQUIVO_CONFIG = PASTA_APP / "config.json"
ARQUIVO_PROGRESSO = PASTA_APP / "progress.json"


@registrar_etapa
def garantir_estrutura_app() -> None:
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
    PASTA_APP.mkdir(parents=True, exist_ok=True)
    PASTA_DOCUMENTOS_APP.mkdir(parents=True, exist_ok=True)
    PASTA_PROJETOS.mkdir(parents=True, exist_ok=True)
    EXPORTS_PADRAO.mkdir(parents=True, exist_ok=True)
    BIBLIOTECA_PADRAO.mkdir(parents=True, exist_ok=True)
    if not ARQUIVO_CONFIG.exists():
        from .persistencia_json import salvar_json
        salvar_json(ARQUIVO_CONFIG, configuracao_padrao())
    if not ARQUIVO_PROGRESSO.exists():
        from .persistencia_json import salvar_json
        salvar_json(ARQUIVO_PROGRESSO, {"livros": {}, "projetos": {}})



@registrar_etapa
def garantir_pasta_projetos() -> None:
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
    garantir_estrutura_app()
    PASTA_PROJETOS.mkdir(parents=True, exist_ok=True)



@registrar_etapa
def garantir_pasta_exports() -> None:
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
    garantir_estrutura_app()
    obter_pasta_exportacao().mkdir(parents=True, exist_ok=True)


@registrar_etapa
def garantir_pasta_biblioteca() -> None:
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
    garantir_estrutura_app()
    obter_pasta_biblioteca().mkdir(parents=True, exist_ok=True)



@registrar_etapa
def nome_seguro(texto: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        texto: Texto bruto ou parcialmente tratado que será analisado pela função.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower().strip()
    texto = re.sub(r"[^a-zA-Z0-9\s_-]", "", texto)
    texto = re.sub(r"[-\s]+", "_", texto)
    texto = re.sub(r"_+", "_", texto)
    return texto.strip("_") or "projeto"



@registrar_etapa
def agora_iso() -> str:
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
    return datetime.now().isoformat(timespec="seconds")



@registrar_etapa
def formatar_data_br(data_iso: str | None) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        data_iso: Valor usado pela rotina para compor a operação de formatar data br.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    if not data_iso:
        return "-"
    try:
        return datetime.fromisoformat(data_iso).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return data_iso



@registrar_etapa
def configuracao_padrao() -> dict:
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
    return {
        "identacao_paragrafo_em": 2.0,
        "identacao_paragrafo_maior_em": 3.2,
        "espaco_paragrafos_em": 1.15,
        "espaco_linhas": 1.85,
        "tamanho_fonte_px": 20,
        "h1_px": 28,
        "h2_px": 22,
        "h3_px": 18,
        "largura_leitura_px": 860,
        "leitor_tema": "tema-claro",
        "leitor_fonte": "fonte-serif",
        "leitor_tamanho_fonte_px": 20,
        "leitor_modo_confortavel": False,
        "leitor_modo_ampliado": True,
        "caminho_exportacao": str(EXPORTS_PADRAO),
        "caminho_biblioteca": str(BIBLIOTECA_PADRAO),
        "modo_browser": False,
        "efeito_editor": True,
        "gemini_api_key": "",
        "idioma_app": "pt_BR",
    }



@registrar_etapa
def _caminho_exportacao_legado(caminho: Path) -> bool:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        caminho: Caminho de arquivo ou pasta usado como origem ou destino da operação.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    perfil = Path(os.environ.get("USERPROFILE") or str(Path.home()))
    candidatos = {
        (perfil / "Documents" / APP_NOME / "exports").resolve(),
        (perfil / "documents" / APP_NOME / "exports").resolve(),
        (perfil / "OneDrive" / "Documents" / APP_NOME / "exports").resolve(),
        (perfil / "OneDrive" / "documents" / APP_NOME / "exports").resolve(),
    }
    try:
        return caminho.resolve() in candidatos
    except Exception:
        return False



@registrar_etapa
def obter_configuracoes() -> dict:
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
    from .persistencia_json import ler_json

    garantir_estrutura_app()
    dados = ler_json(ARQUIVO_CONFIG, configuracao_padrao())
    base = configuracao_padrao()
    base.update(dados or {})

    caminho_exportacao = Path(str(base.get("caminho_exportacao") or EXPORTS_PADRAO))
    if not base.get("caminho_exportacao") or _caminho_exportacao_legado(caminho_exportacao):
        caminho_exportacao = EXPORTS_PADRAO
    base["caminho_exportacao"] = str(caminho_exportacao)

    caminho_biblioteca = Path(str(base.get("caminho_biblioteca") or BIBLIOTECA_PADRAO))
    if not base.get("caminho_biblioteca"):
        caminho_biblioteca = BIBLIOTECA_PADRAO
    base["caminho_biblioteca"] = str(caminho_biblioteca)

    if caminho_exportacao.resolve() != EXPORTS_PADRAO.resolve() and not caminho_exportacao.exists():
        caminho_exportacao.mkdir(parents=True, exist_ok=True)
    if caminho_biblioteca.resolve() != BIBLIOTECA_PADRAO.resolve() and not caminho_biblioteca.exists():
        caminho_biblioteca.mkdir(parents=True, exist_ok=True)
    if ler_json(ARQUIVO_CONFIG, None) != base:
        from .persistencia_json import salvar_json
        salvar_json(ARQUIVO_CONFIG, base)
    return base



@registrar_etapa
def salvar_configuracoes(dados: dict) -> dict:
    """
    Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        dados: Valor usado pela rotina para compor a operação de salvar configuracoes.

    Retorno:
        A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    from .persistencia_json import salvar_json

    garantir_estrutura_app()
    config = configuracao_padrao()
    config.update(dados or {})
    if not config.get("caminho_exportacao"):
        config["caminho_exportacao"] = str(EXPORTS_PADRAO)
    if not config.get("caminho_biblioteca"):
        config["caminho_biblioteca"] = str(BIBLIOTECA_PADRAO)
    salvar_json(ARQUIVO_CONFIG, config)
    return config



@registrar_etapa
def obter_pasta_exportacao() -> Path:
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
    config = obter_configuracoes()
    caminho = Path(config.get("caminho_exportacao") or EXPORTS_PADRAO)
    return caminho


@registrar_etapa
def obter_pasta_biblioteca() -> Path:
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
    config = obter_configuracoes()
    caminho = Path(config.get("caminho_biblioteca") or BIBLIOTECA_PADRAO)
    return caminho


@registrar_etapa
def obter_pasta_exportacao_projeto(nome_projeto: str) -> Path:
    """
    Localiza e devolve um dado ou recurso específico, aplicando as validações necessárias antes do retorno.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        nome_projeto: Valor usado pela rotina para compor a operação de obter pasta exportacao projeto.

    Retorno:
        O recurso solicitado ou uma estrutura com os dados encontrados.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    pasta = obter_pasta_exportacao() / nome_seguro(nome_projeto or 'projeto')
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta



@registrar_etapa
def progresso_padrao() -> dict:
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
    return {
        "livros": {},
        "projetos": {},
    }


@registrar_etapa
def obter_progresso() -> dict:
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
    from .persistencia_json import ler_json, salvar_json

    garantir_estrutura_app()
    dados = ler_json(ARQUIVO_PROGRESSO, progresso_padrao())
    base = progresso_padrao()
    if isinstance(dados, dict):
        base.update(dados)
    if not isinstance(base.get("livros"), dict):
        base["livros"] = {}
    if not isinstance(base.get("projetos"), dict):
        base["projetos"] = {}
    if ler_json(ARQUIVO_PROGRESSO, None) != base:
        salvar_json(ARQUIVO_PROGRESSO, base)
    return base


@registrar_etapa
def salvar_progresso(dados: dict) -> dict:
    """
    Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        dados: Valor usado pela rotina para compor a operação de salvar progresso.

    Retorno:
        A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    from .persistencia_json import salvar_json

    garantir_estrutura_app()
    base = progresso_padrao()
    if isinstance(dados, dict):
        base.update(dados)
    if not isinstance(base.get("livros"), dict):
        base["livros"] = {}
    if not isinstance(base.get("projetos"), dict):
        base["projetos"] = {}
    salvar_json(ARQUIVO_PROGRESSO, base)
    return base


@registrar_etapa
def inferir_extensao_data_url(data_url: str) -> Tuple[str, bytes]:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        data_url: Valor usado pela rotina para compor a operação de inferir extensao data url.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    cabecalho, base64_data = data_url.split(",", 1)
    mime = cabecalho.split(";")[0].replace("data:", "")
    extensao = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(mime, ".bin")
    return extensao, base64.b64decode(base64_data)

PROG_ID_GUT = "Gutenberg.GUT"
ARQUIVO_LAUNCHER_GUT_LEGADO = PASTA_APP / "gutenberg_open_gut.cmd"


@registrar_etapa
def remover_launcher_gut_legado(caminho_launcher: str | Path | None = None) -> None:
    """Remove o antigo launcher .cmd usado por versões anteriores para abrir arquivos .gut."""
    if os.name != "nt":
        return
    try:
        destino = Path(caminho_launcher or ARQUIVO_LAUNCHER_GUT_LEGADO)
        if destino.exists() and destino.is_file():
            destino.unlink()
    except Exception:
        pass


@registrar_etapa
def _broadcast_environment_change_windows() -> None:
    """Notifica o Windows sobre mudanças de associação feitas pelo instalador."""
    if os.name != "nt":
        return
    try:
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Software\\Classes",
            SMTO_ABORTIFHUNG,
            5000,
            None,
        )
    except Exception:
        pass


@registrar_etapa
def configurar_integracao_gut_windows(
    caminho_app: str | Path | None = None,
    caminho_script: str | Path | None = None,
    caminho_python: str | Path | None = None,
    caminho_icone: str | Path | None = None,
    caminho_launcher: str | Path | None = None,
) -> None:
    r"""
    Mantida apenas por compatibilidade interna.

    A associação de arquivos .gut agora é responsabilidade exclusiva do instalador
    Inno Setup, que registra o caminho real de {app}\Gutenberg.exe e o ícone
    {app}\_internal\static\img\gut_file.ico, com fallback para {app}\static\img\gut_file.ico. Executar o app pelo código-fonte ou pelo EXE
    não cria mais launcher .cmd, variáveis de ambiente nem associações no Registro.
    """
    remover_launcher_gut_legado(caminho_launcher)
