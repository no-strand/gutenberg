"""
Ponto de entrada do aplicativo desktop. Inicializa o servidor Flask, integra a janela do app e controla o modo navegador ou embutido.

"""

import sys
import time
import threading
import ctypes
import webbrowser
import shutil
import socket
from pathlib import Path

import requests

try:
    import webview
except Exception:
    webview = None

from server_only import app
from modules.i18n import t
from modules.utilidades import (
    RAIZ_RECURSOS,
    obter_configuracoes,
    obter_pasta_exportacao,
    salvar_configuracoes,
)
from modules.exportador_gut import ler_payload_gut
from modules.logging_config import obter_logger, registrar_etapa, configurar_logging, instalar_hook_excecoes
logger = obter_logger(__name__)
configurar_logging()
instalar_hook_excecoes()

PORTA_PADRAO = 5000
TITULO_JANELA = "Gutenberg"
BROWSER_URL = f"http://127.0.0.1:{PORTA_PADRAO}"
WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010


ULTIMO_DIRETORIO_GUT_CHAVE = "ultimo_diretorio_gut"


@registrar_etapa
def sistema_windows() -> bool:
    """Retorna True quando a execução atual está em Windows."""
    return sys.platform == "win32"


@registrar_etapa
def pywebview_disponivel() -> bool:
    """Retorna True quando o pywebview pode ser usado para iniciar o modo desktop."""
    return webview is not None


@registrar_etapa
def windows_10_ou_superior() -> bool:
    """Retorna True quando o sistema atual é Windows 10 ou superior."""
    if not sistema_windows():
        return False
    try:
        versao = sys.getwindowsversion()
        return int(getattr(versao, "major", 0)) >= 10
    except Exception:
        logger.exception("Não foi possível detectar a versão do Windows")
        return False


@registrar_etapa
def obter_ip_local() -> str:
    """Obtém o IP local preferencial para exibir a URL de rede do modo servidor."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


@registrar_etapa
def _executar_modo_servidor(host: str = "0.0.0.0", port: int = PORTA_PADRAO) -> int:
    """Executa o Gutenberg somente como servidor Flask, sem janela desktop nem tray."""
    ip = obter_ip_local()
    logger.info(
        "Modo servidor ativado | sistema=%s | local=http://127.0.0.1:%s | rede=http://%s:%s",
        sys.platform,
        port,
        ip,
        port,
    )
    try:
        app.run(host=host, port=port, debug=False, use_reloader=False)
        return 0
    except Exception:
        logger.exception("Erro fatal no modo servidor")
        return 1


@registrar_etapa
def _normalizar_pasta_dialogo(caminho: str | None, fallback: Path | None = None) -> Path:
    """
    Padroniza valores de entrada para que diferentes partes do sistema trabalhem com o mesmo formato.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        caminho: Caminho de arquivo ou pasta usado como origem ou destino da operação.
        fallback: Valor usado pela rotina para compor a operação de normalizar pasta dialogo.

    Retorno:
        O valor recebido em uma forma padronizada e segura para uso interno.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    base = Path(str(caminho)).expanduser() if caminho else None
    if base and base.is_file():
        base = base.parent
    if not base or not base.exists():
        base = fallback or obter_pasta_exportacao()
    base.mkdir(parents=True, exist_ok=True)
    return base


@registrar_etapa
def _obter_ultimo_diretorio_dialogo() -> str:
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
    try:
        return str(obter_configuracoes().get(ULTIMO_DIRETORIO_GUT_CHAVE) or "")
    except Exception:
        return ""


@registrar_etapa
def _salvar_ultimo_diretorio_dialogo(caminho: str | Path | None) -> None:
    """
    Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        caminho: Caminho de arquivo ou pasta usado como origem ou destino da operação.

    Retorno:
        A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    try:
        if not caminho:
            return
        pasta = Path(str(caminho)).expanduser()
        if pasta.is_file() or pasta.suffix:
            pasta = pasta.parent
        pasta.mkdir(parents=True, exist_ok=True)
        dados = obter_configuracoes()
        dados[ULTIMO_DIRETORIO_GUT_CHAVE] = str(pasta)
        salvar_configuracoes(dados)
    except Exception as exc:
        logger.exception("Falha ao salvar último diretório .gut")


@registrar_etapa
def iniciar_flask(host: str = "127.0.0.1", port: int = PORTA_PADRAO) -> None:
    """
    Prepara e inicia um componente do aplicativo, cuidando dos detalhes necessários para sua execução.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        host: Endereço local em que o servidor deve escutar conexões.
        port: Porta de rede usada pelo servidor local.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    app.run(host=host, port=port, debug=False, use_reloader=False)


@registrar_etapa
def aguardar_servidor(urls: list[str], timeout: int = 30) -> str | None:
    """
    Espera uma condição externa ficar disponível antes de seguir com a próxima etapa.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        urls: Valor usado pela rotina para compor a operação de aguardar servidor.
        timeout: Valor usado pela rotina para compor a operação de aguardar servidor.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    inicio = time.time()
    while time.time() - inicio < timeout:
        for url in urls:
            try:
                resposta = requests.get(url, timeout=1)
                if resposta.status_code == 200:
                    return url
            except Exception:
                pass
        time.sleep(0.35)
    return None


@registrar_etapa
def _aplicar_icone_janela_windows(titulo_janela: str, icon_path: Path, tentativas: int = 120, intervalo: float = 0.25) -> None:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        titulo_janela: Valor usado pela rotina para compor a operação de aplicar icone janela windows.
        icon_path: Valor usado pela rotina para compor a operação de aplicar icone janela windows.
        tentativas: Valor usado pela rotina para compor a operação de aplicar icone janela windows.
        intervalo: Valor usado pela rotina para compor a operação de aplicar icone janela windows.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    if sys.platform != "win32":
        return

    try:
        user32 = ctypes.windll.user32
    except Exception as e:
        logger.warning("Não foi possível acessar user32 para aplicar ícone da janela", exc_info=True)
        return

    icon_file = Path(icon_path).resolve()
    if not icon_file.exists():
        logger.warning("Ícone da janela não encontrado | caminho=%s", icon_file)
        return

    hwnd = None
    for _ in range(tentativas):
        hwnd = user32.FindWindowW(None, titulo_janela)
        if hwnd:
            break
        time.sleep(intervalo)

    if not hwnd:
        logger.warning("Janela principal não encontrada para aplicar o ícone da barra de tarefas")
        return

    hicon = user32.LoadImageW(
        None,
        str(icon_file),
        IMAGE_ICON,
        0,
        0,
        LR_LOADFROMFILE,
    )

    if not hicon:
        logger.warning("Não foi possível carregar o ícone da janela | caminho=%s", icon_file)
        return

    user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
    user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)


@registrar_etapa
def _iniciar_aplicacao_icone_janela_windows(titulo_janela: str, icon_path: Path) -> None:
    """
    Prepara e inicia um componente do aplicativo, cuidando dos detalhes necessários para sua execução.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        titulo_janela: Valor usado pela rotina para compor a operação de iniciar aplicacao icone janela windows.
        icon_path: Valor usado pela rotina para compor a operação de iniciar aplicacao icone janela windows.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    if sys.platform != "win32":
        return

    threading.Thread(
        target=_aplicar_icone_janela_windows,
        args=(titulo_janela, icon_path),
        daemon=True,
    ).start()


class Bridge:
    """
    Representa Bridge dentro do fluxo da aplicação.

    Esta classe concentra estado e comportamentos relacionados para evitar que a
    lógica fique espalhada por vários pontos do código. A intenção é oferecer uma
    interface simples para quem consome o módulo, escondendo os detalhes internos
    de organização, validação e integração com os demais componentes.
    """
    @registrar_etapa
    def __init__(self, window_getter, home_url: str):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            window_getter: Valor usado pela rotina para compor a operação de init  .
            home_url: Valor usado pela rotina para compor a operação de init  .
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        self._window_getter = window_getter
        self._home_url = home_url

    @registrar_etapa
    def toggle_fullscreen(self):
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
        try:
            window = self._window_getter()
            if window:
                window.toggle_fullscreen()
        except Exception as e:
            logger.exception("Bridge.toggle_fullscreen falhou")

    @registrar_etapa
    def goBack(self):
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
        try:
            window = self._window_getter()
            if not window:
                return

            js = f"""
                if (window.history.length > 1) {{
                    window.history.back();
                }} else {{
                    window.location.href = {self._home_url!r};
                }}
            """
            window.evaluate_js(js)
        except Exception as e:
            logger.exception("Bridge.goBack falhou")

    @registrar_etapa
    def openDocumentation(self):
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
        try:
            caminho = _obter_documentacao_index()
            if caminho.exists():
                webbrowser.open(caminho.as_uri())
                return True
            return False
        except Exception as e:
            logger.exception("Bridge.openDocumentation falhou")
            return False

    @registrar_etapa
    def openGutFileDialog(self, initial_dir: str | None = None):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            initial_dir: Valor usado pela rotina para compor a operação de openGutFileDialog.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        try:
            window = self._window_getter()
            if not window:
                return {"ok": False, "erro": "Janela principal indisponível."}
            pasta_preferida = _obter_ultimo_diretorio_dialogo() or initial_dir
            pasta_inicial = _normalizar_pasta_dialogo(pasta_preferida, obter_pasta_exportacao())
            selecionados = window.create_file_dialog(
                webview.FileDialog.OPEN,
                directory=str(pasta_inicial),
                allow_multiple=False,
                file_types=(
                    'Arquivos importáveis (*.gut;*.docx;*.pdf;*.txt)',
                    'Arquivos Gutenberg (*.gut)',
                    'Documentos Word (*.docx)',
                    'PDF (*.pdf)',
                    'Texto (*.txt)',
                    'Todos os arquivos (*.*)',
                ),
            )
            if not selecionados:
                return {"ok": False, "cancelado": True}
            caminho = selecionados[0] if isinstance(selecionados, (list, tuple)) else selecionados
            if not caminho:
                return {"ok": False, "cancelado": True}
            caminho_path = Path(str(caminho)).expanduser()
            _salvar_ultimo_diretorio_dialogo(caminho_path.parent)
            return {"ok": True, "caminho": str(caminho_path)}
        except Exception as e:
            logger.exception("Bridge.openGutFileDialog falhou")
            return {"ok": False, "erro": str(e)}


    @registrar_etapa
    def openGutrFileDialog(self, initial_dir: str | None = None):
        """Abre um diálogo desktop limitado a pacotes de recursos .gutr."""
        try:
            window = self._window_getter()
            if not window:
                return {"ok": False, "erro": "Janela principal indisponível."}
            pasta_preferida = _obter_ultimo_diretorio_dialogo() or initial_dir
            pasta_inicial = _normalizar_pasta_dialogo(pasta_preferida, obter_pasta_exportacao())
            selecionados = window.create_file_dialog(
                webview.FileDialog.OPEN,
                directory=str(pasta_inicial),
                allow_multiple=False,
                file_types=(
                    'Recursos Gutenberg (*.gutr)',
                    'Todos os arquivos (*.*)',
                ),
            )
            if not selecionados:
                return {"ok": False, "cancelado": True}
            caminho = selecionados[0] if isinstance(selecionados, (list, tuple)) else selecionados
            if not caminho:
                return {"ok": False, "cancelado": True}
            caminho_path = Path(str(caminho)).expanduser()
            _salvar_ultimo_diretorio_dialogo(caminho_path.parent)
            return {"ok": True, "caminho": str(caminho_path)}
        except Exception as e:
            logger.exception("Bridge.openGutrFileDialog falhou")
            return {"ok": False, "erro": str(e)}

    @registrar_etapa
    def saveExportedFile(self, source_path: str, suggested_name: str | None = None, initial_dir: str | None = None):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            source_path: Valor usado pela rotina para compor a operação de saveExportedFile.
            suggested_name: Valor usado pela rotina para compor a operação de saveExportedFile.
            initial_dir: Valor usado pela rotina para compor a operação de saveExportedFile.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        try:
            window = self._window_getter()
            if not window:
                return {"ok": False, "erro": "Janela principal indisponível."}

            origem = Path(str(source_path or "")).expanduser().resolve()
            if not origem.exists() or not origem.is_file():
                return {"ok": False, "erro": "Arquivo exportado não encontrado."}

            pasta_preferida = _obter_ultimo_diretorio_dialogo() or initial_dir
            pasta_inicial = _normalizar_pasta_dialogo(pasta_preferida, obter_pasta_exportacao())

            nome_sugerido = (suggested_name or origem.name or "arquivo").strip() or origem.name
            destino = window.create_file_dialog(
                webview.FileDialog.SAVE,
                directory=str(pasta_inicial),
                save_filename=nome_sugerido,
            )
            if not destino:
                return {"ok": False, "cancelado": True}

            if isinstance(destino, (list, tuple)):
                destino = destino[0] if destino else ""
            if not destino:
                return {"ok": False, "cancelado": True}

            destino_path = Path(str(destino)).expanduser()
            destino_path.parent.mkdir(parents=True, exist_ok=True)

            if destino_path.resolve() != origem.resolve():
                shutil.copy2(origem, destino_path)

            _salvar_ultimo_diretorio_dialogo(destino_path.parent)
            return {"ok": True, "caminho": str(destino_path)}
        except Exception as e:
            logger.exception("Bridge.saveExportedFile falhou")
            return {"ok": False, "erro": str(e)}


class AppController:
    """
    Representa AppController dentro do fluxo da aplicação.

    Esta classe concentra estado e comportamentos relacionados para evitar que a
    lógica fique espalhada por vários pontos do código. A intenção é oferecer uma
    interface simples para quem consome o módulo, escondendo os detalhes internos
    de organização, validação e integração com os demais componentes.
    """
    @registrar_etapa
    def __init__(self, initial_path: str | None = None):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            initial_path: Valor usado pela rotina para compor a operação de init  .
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        self.server_url = ""
        self.window = None
        self.initial_path = initial_path

    @registrar_etapa
    def registrar_gut_pendente(self) -> None:
        """
        Registra uma informação de estado ou progresso para que ela possa ser consultada posteriormente.
    
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
        if not self.initial_path or not self.server_url:
            return
        caminho = str(Path(self.initial_path).expanduser().resolve())
        try:
            resposta = requests.post(
                f"{self.server_url}/api/gut/pendente/registrar",
                json={"caminho": caminho},
                timeout=5,
            )
            if resposta.status_code >= 400:
                logger.error("Falha ao registrar arquivo Gutenberg pendente | status=%s | resposta=%s", resposta.status_code, resposta.text)
        except Exception as e:
            logger.exception("Falha ao registrar arquivo Gutenberg pendente")

    @registrar_etapa
    def setup_server(self) -> None:
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
        thread_flask = threading.Thread(
            target=iniciar_flask,
            args=("127.0.0.1", PORTA_PADRAO),
            daemon=True,
        )
        thread_flask.start()

        urls = [
            f"http://127.0.0.1:{PORTA_PADRAO}",
            f"http://localhost:{PORTA_PADRAO}",
        ]
        self.server_url = aguardar_servidor(urls, timeout=30) or ""
        if not self.server_url:
            raise RuntimeError("O servidor Flask não respondeu dentro do tempo limite.")

    @registrar_etapa
    def run(self):
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
        if webview is None:
            raise RuntimeError("pywebview não está disponível para iniciar o modo desktop.")

        self.setup_server()

        bridge = Bridge(lambda: self.window, self.server_url)
        self.registrar_gut_pendente()
        icon_path = str((RAIZ_RECURSOS / "static" / "img" / "icon.ico").resolve())
        taskbar_icon_path = (RAIZ_RECURSOS / "static" / "img" / "favicon.ico").resolve()
        self.window = webview.create_window(
            title=TITULO_JANELA,
            url=self.server_url,
            js_api=bridge,
            width=1280,
            height=800,
            maximized=True,
        )
        _iniciar_aplicacao_icone_janela_windows(TITULO_JANELA, taskbar_icon_path)
        logger.info("Servidor local iniciado | url=%s", self.server_url)
        webview.start(debug=False, icon=icon_path)


@registrar_etapa
def _obter_icone_tray() -> Path:
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
    return (RAIZ_RECURSOS / "static" / "img" / "favicon.ico").resolve()


@registrar_etapa
def _obter_documentacao_index() -> Path:
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
    return (RAIZ_RECURSOS / "documentation" / "index.html").resolve()


@registrar_etapa
def _manter_servidor_sem_tray(servidor: threading.Thread, url_local: str = BROWSER_URL) -> int:
    """Mantém o servidor Flask já iniciado ativo quando o tray falha durante o modo browser."""
    ip = obter_ip_local()
    logger.warning(
        "Fallback para modo servidor sem tray ativado | sistema=%s | local=%s | rede=http://%s:%s",
        sys.platform,
        url_local,
        ip,
        PORTA_PADRAO,
    )
    logger.info("Acesse o Gutenberg pelo navegador e pressione Ctrl+C no terminal para encerrar.")
    try:
        while servidor.is_alive():
            time.sleep(1)
        return 0
    except KeyboardInterrupt:
        logger.info("Encerramento solicitado pelo usuário no modo servidor sem tray.")
        return 0


@registrar_etapa
def _executar_modo_browser() -> int:
    """
    Inicia o modo browser com ícone de bandeja. Se o pystray não puder ser usado,
    cai automaticamente para o modo servidor puro, equivalente ao server_only.py.
    """

    @registrar_etapa
    def abrir_no_navegador(icon=None, item=None):
        """Abre o Gutenberg no navegador padrão."""
        webbrowser.open(BROWSER_URL)

    @registrar_etapa
    def fechar(icon, item):
        """Encerra o ícone de bandeja do modo browser."""
        icon.stop()

    try:
        import pystray
        from PIL import Image

        tooltip = t("app.browser_mode_tooltip", url=BROWSER_URL)
        icon_path = _obter_icone_tray()
        imagem = Image.open(icon_path)
        menu = pystray.Menu(
            pystray.MenuItem(t("app.open_in_browser"), abrir_no_navegador),
            pystray.MenuItem(t("common.close"), fechar),
        )
        icone = pystray.Icon("epub_browser_mode", imagem, tooltip, menu)
    except Exception:
        logger.warning(
            "pystray/Pillow indisponível ou não inicializável. O Gutenberg será iniciado em modo servidor sem tray.",
            exc_info=True,
        )
        return _executar_modo_servidor(host="0.0.0.0", port=PORTA_PADRAO)

    servidor = threading.Thread(
        target=iniciar_flask,
        args=("0.0.0.0", PORTA_PADRAO),
        daemon=True,
    )
    servidor.start()

    server_url = aguardar_servidor([BROWSER_URL, f"http://localhost:{PORTA_PADRAO}"], timeout=30)
    if not server_url:
        logger.error("Erro fatal: o servidor Flask não respondeu no modo browser")
        return 1

    try:
        icone.run()
        return 0
    except Exception:
        logger.exception(
            "Falha ao executar o pystray. Mantendo o Gutenberg em modo servidor sem tray."
        )
        return _manter_servidor_sem_tray(servidor, server_url)


@registrar_etapa
def _obter_arquivo_gutenberg_argumento(argv: list[str]) -> str | None:
    """
    Localiza e devolve um dado ou recurso específico, aplicando as validações necessárias antes do retorno.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        argv: Valor usado pela rotina para compor a operação de obter arquivo gut argumento.

    Retorno:
        O recurso solicitado ou uma estrutura com os dados encontrados.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    for item in argv[1:]:
        try:
            caminho = Path(item).expanduser()
        except Exception:
            continue
        if caminho.suffix.lower() in {".gut", ".gutr"} and caminho.exists():
            return str(caminho.resolve())
    return None


@registrar_etapa
def main() -> int:
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
    try:
        if not sistema_windows():
            logger.warning(
                "Sistema não Windows detectado (%s). O Gutenberg tentará iniciar no modo browser; se o tray falhar, usará modo servidor sem tray.",
                sys.platform,
            )
            return _executar_modo_browser()

        if not windows_10_ou_superior():
            logger.warning(
                "Windows anterior ao 10 detectado. O modo desktop com pywebview exige Windows 10 ou superior; tentando modo browser com fallback para servidor sem tray."
            )
            return _executar_modo_browser()

        if not pywebview_disponivel():
            logger.warning(
                "pywebview não está disponível no Windows. O Gutenberg tentará modo browser com fallback para servidor sem tray."
            )
            return _executar_modo_browser()

        config = obter_configuracoes()
        arquivo_gutenberg = _obter_arquivo_gutenberg_argumento(sys.argv)
        if bool(config.get("modo_browser", False)) and not arquivo_gutenberg:
            return _executar_modo_browser()
        controller = AppController(initial_path=arquivo_gutenberg)
        controller.run()
        return 0
    except Exception as e:
        logger.exception("Erro fatal na aplicação")
        return 1


if __name__ == "__main__":
    sys.exit(main())
