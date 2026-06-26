"""Verificação e aplicação de atualizações do Gutenberg via GitHub Releases."""
from __future__ import annotations

import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from .logging_config import obter_logger, registrar_etapa
from .utilidades import APP_NOME, APP_VERSAO, PASTA_APP

logger = obter_logger(__name__)

GITHUB_OWNER = "no-strand"
GITHUB_REPO = "gutenberg"
GITHUB_RELEASES_API = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
GITHUB_HTML_RELEASES = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
PASTA_ATUALIZACOES = PASTA_APP / "updates"
TIMEOUT_CONEXAO = 15
USER_AGENT = f"{APP_NOME}/{APP_VERSAO}"

ARQUITETURAS_ALIASES: dict[str, tuple[str, ...]] = {
    "x64": ("x64", "x86_64", "amd64", "64bit", "win64"),
    "arm64": ("arm64", "aarch64", "apple-silicon", "applesilicon"),
    "x86": ("x86", "i386", "i686", "ia32", "32bit", "win32"),
}

PLATAFORMAS_SUPORTADAS: dict[str, dict[str, Any]] = {
    "windows": {
        "rotulo": "Windows",
        "tokens": ("windows", "win", "win64", "win32"),
        "extensoes": (".exe", ".msi"),
        "prioridade_extensao": {".exe": 5, ".msi": 4},
        "padrao_recomendado": "Gutenberg-<versao>-windows-x64-setup.exe",
    },
    "macos": {
        "rotulo": "macOS",
        "tokens": ("macos", "mac", "darwin", "osx", "os-x"),
        "extensoes": (".dmg", ".pkg", ".zip"),
        "prioridade_extensao": {".dmg": 5, ".pkg": 4, ".zip": 2},
        "padrao_recomendado": "Gutenberg-<versao>-macos-universal.dmg",
    },
    "linux": {
        "rotulo": "Linux",
        "tokens": ("linux", "ubuntu", "debian", "fedora", "appimage", "rpm", "deb"),
        "extensoes": (".appimage", ".deb", ".rpm", ".tar.gz", ".tgz"),
        "prioridade_extensao": {".appimage": 6, ".deb": 5, ".rpm": 4, ".tar.gz": 2, ".tgz": 2},
        "padrao_recomendado": "Gutenberg-<versao>-linux-x64.AppImage",
    },
}

TODOS_TOKENS_SO = tuple(
    token
    for dados in PLATAFORMAS_SUPORTADAS.values()
    for token in dados["tokens"]
)
TODOS_TOKENS_ARQ = tuple(token for aliases in ARQUITETURAS_ALIASES.values() for token in aliases)

_ESTADO_PADRAO_ATUALIZACAO: dict[str, Any] = {
    "ativo": False,
    "cancelando": False,
    "cancelado": False,
    "concluido": False,
    "erro": "",
    "etapa": "idle",
    "mensagem": "",
    "progresso": 0,
    "bytes_baixados": 0,
    "bytes_total": 0,
    "bytes_total_formatado": "",
    "bytes_baixados_formatado": "",
    "versao": "",
    "instalador": "",
    "caminho": "",
    "atualizado_em": "",
}
_ESTADO_ATUALIZACAO: dict[str, Any] = dict(_ESTADO_PADRAO_ATUALIZACAO)
_ULTIMA_VERIFICACAO_ATUALIZACAO: dict[str, Any] = {}
_ESTADO_LOCK = threading.RLock()
_CANCELAR_ATUALIZACAO = threading.Event()
_THREAD_ATUALIZACAO: threading.Thread | None = None


class AtualizacaoErro(RuntimeError):
    """Erro esperado durante o fluxo de atualização."""


class AtualizacaoCancelada(AtualizacaoErro):
    """Sinaliza cancelamento solicitado pelo usuário."""


@registrar_etapa
def normalizar_versao(valor: str | None) -> tuple[int, int, int, tuple[str, ...]]:
    """Normaliza versões como v1.2.3 para comparação simples."""
    texto = str(valor or "").strip()
    texto = re.sub(r"^[vV]", "", texto)
    parte_numerica, _, sufixo = texto.partition("-")
    numeros: list[int] = []
    for parte in parte_numerica.split(".")[:3]:
        encontrado = re.search(r"\d+", parte)
        numeros.append(int(encontrado.group(0)) if encontrado else 0)
    while len(numeros) < 3:
        numeros.append(0)
    sufixos = tuple(item for item in re.split(r"[^A-Za-z0-9]+", sufixo.lower()) if item)
    return int(numeros[0]), int(numeros[1]), int(numeros[2]), sufixos


@registrar_etapa
def versao_remota_maior(versao_remota: str | None, versao_atual: str | None = None) -> bool:
    """Indica se a versão remota é superior à versão local."""
    atual = normalizar_versao(versao_atual or APP_VERSAO)
    remota = normalizar_versao(versao_remota)
    return remota[:3] > atual[:3]


@registrar_etapa
def _headers_github() -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }


@registrar_etapa
def _formatar_tamanho(bytes_total: int | None) -> str:
    try:
        valor = float(bytes_total or 0)
    except Exception:
        valor = 0.0
    unidades = ["B", "KB", "MB", "GB"]
    indice = 0
    while valor >= 1024 and indice < len(unidades) - 1:
        valor /= 1024
        indice += 1
    if indice == 0:
        return f"{int(valor)} {unidades[indice]}"
    return f"{valor:.1f} {unidades[indice]}"


@registrar_etapa
def _agora_estado() -> str:
    return datetime.now(timezone.utc).isoformat()


def _estado_publico() -> dict[str, Any]:
    estado = dict(_ESTADO_ATUALIZACAO)
    estado["bytes_total_formatado"] = _formatar_tamanho(int(estado.get("bytes_total") or 0)) if estado.get("bytes_total") else ""
    estado["bytes_baixados_formatado"] = _formatar_tamanho(int(estado.get("bytes_baixados") or 0)) if estado.get("bytes_baixados") else ""
    try:
        estado["progresso"] = max(0, min(100, int(round(float(estado.get("progresso") or 0)))))
    except Exception:
        estado["progresso"] = 0
    return estado


@registrar_etapa
def estado_atualizacao() -> dict[str, Any]:
    """Retorna o estado atual do fluxo de atualização."""
    with _ESTADO_LOCK:
        return _estado_publico()


@registrar_etapa
def ultima_verificacao_atualizacao() -> dict[str, Any]:
    """Retorna a última verificação de atualização conhecida nesta sessão."""
    with _ESTADO_LOCK:
        return dict(_ULTIMA_VERIFICACAO_ATUALIZACAO)


def _salvar_ultima_verificacao_atualizacao(dados: dict[str, Any]) -> dict[str, Any]:
    with _ESTADO_LOCK:
        _ULTIMA_VERIFICACAO_ATUALIZACAO.clear()
        _ULTIMA_VERIFICACAO_ATUALIZACAO.update(dados or {})
        _ULTIMA_VERIFICACAO_ATUALIZACAO["verificado_em"] = _agora_estado()
        return dict(_ULTIMA_VERIFICACAO_ATUALIZACAO)


def _atualizar_estado_atualizacao(**valores: Any) -> dict[str, Any]:
    with _ESTADO_LOCK:
        _ESTADO_ATUALIZACAO.update(valores)
        _ESTADO_ATUALIZACAO["atualizado_em"] = _agora_estado()
        return _estado_publico()


def _reiniciar_estado_atualizacao(**valores: Any) -> dict[str, Any]:
    with _ESTADO_LOCK:
        _ESTADO_ATUALIZACAO.clear()
        _ESTADO_ATUALIZACAO.update(_ESTADO_PADRAO_ATUALIZACAO)
        _ESTADO_ATUALIZACAO.update(valores)
        _ESTADO_ATUALIZACAO["atualizado_em"] = _agora_estado()
        return _estado_publico()


@registrar_etapa
def cancelar_atualizacao() -> dict[str, Any]:
    """Solicita cancelamento do download de atualização em andamento."""
    with _ESTADO_LOCK:
        if not _ESTADO_ATUALIZACAO.get("ativo"):
            return {**_estado_publico(), "ok": False, "erro": "Não há atualização em andamento."}
        if _ESTADO_ATUALIZACAO.get("etapa") in {"abrindo", "concluido"}:
            return {**_estado_publico(), "ok": False, "erro": "A atualização já está sendo finalizada."}
        _CANCELAR_ATUALIZACAO.set()
        _ESTADO_ATUALIZACAO["cancelando"] = True
        _ESTADO_ATUALIZACAO["mensagem"] = "Cancelando atualização..."
        _ESTADO_ATUALIZACAO["atualizado_em"] = _agora_estado()
        return {**_estado_publico(), "ok": True}


@registrar_etapa
def _normalizar_nome_para_tokens(nome: str) -> str:
    return " " + re.sub(r"[^a-z0-9]+", " ", str(nome or "").lower()).strip() + " "


@registrar_etapa
def _contem_token(texto_normalizado: str, token: str) -> bool:
    token_norm = re.sub(r"[^a-z0-9]+", " ", token.lower()).strip()
    if not token_norm:
        return False
    return f" {token_norm} " in texto_normalizado


@registrar_etapa
def _extensao_compativel(nome_lower: str, extensoes: tuple[str, ...]) -> str | None:
    for extensao in sorted(extensoes, key=len, reverse=True):
        if nome_lower.endswith(extensao):
            return extensao
    return None


@registrar_etapa
def _arquitetura_atual() -> str:
    maquina = platform.machine().lower().replace(" ", "")
    if maquina in {"amd64", "x86_64", "x64"}:
        return "x64"
    if maquina in {"arm64", "aarch64"}:
        return "arm64"
    if maquina in {"x86", "i386", "i686"}:
        return "x86"
    return maquina or "desconhecida"


@registrar_etapa
def detectar_plataforma_atual() -> dict[str, Any]:
    """Retorna a plataforma usada para escolher o asset correto da release."""
    sistema_platform = platform.system().lower()
    if sistema_platform.startswith("win"):
        sistema = "windows"
    elif sistema_platform == "darwin":
        sistema = "macos"
    elif sistema_platform == "linux":
        sistema = "linux"
    else:
        sistema = sistema_platform or sys.platform.lower()

    dados = PLATAFORMAS_SUPORTADAS.get(sistema, {})
    return {
        "sistema": sistema,
        "rotulo": dados.get("rotulo", sistema or "Sistema desconhecido"),
        "arquitetura": _arquitetura_atual(),
        "suportado": sistema in PLATAFORMAS_SUPORTADAS,
        "extensoes_aceitas": list(dados.get("extensoes", ())),
        "padrao_recomendado": dados.get("padrao_recomendado", ""),
    }


@registrar_etapa
def _asset_parece_codigo_fonte(nome_normalizado: str) -> bool:
    termos_codigo = ("source", "source code", "src", "codigo fonte", "código fonte", "code")
    return any(_contem_token(nome_normalizado, termo) for termo in termos_codigo)


@registrar_etapa
def _pontuar_asset_instalador(asset: dict[str, Any], plataforma: dict[str, Any]) -> int | None:
    nome = str(asset.get("name") or "").strip()
    url = str(asset.get("browser_download_url") or "").strip()
    sistema = str(plataforma.get("sistema") or "")
    dados_so = PLATAFORMAS_SUPORTADAS.get(sistema)
    if not nome or not url or not dados_so:
        return None

    nome_lower = nome.lower()
    nome_normalizado = _normalizar_nome_para_tokens(nome)
    extensao = _extensao_compativel(nome_lower, tuple(dados_so["extensoes"]))
    if not extensao:
        return None
    if _asset_parece_codigo_fonte(nome_normalizado):
        return None

    tokens_so = tuple(dados_so["tokens"])
    encontrou_token_so = any(_contem_token(nome_normalizado, token) for token in tokens_so)
    for outro_sistema, outros_dados in PLATAFORMAS_SUPORTADAS.items():
        if outro_sistema == sistema:
            continue
        if any(_contem_token(nome_normalizado, token) for token in outros_dados["tokens"]):
            return None

    # Extensões ambíguas, especialmente .zip, precisam indicar explicitamente o sistema operacional.
    if extensao == ".zip" and not encontrou_token_so:
        return None

    arquitetura = str(plataforma.get("arquitetura") or "")
    aliases_atuais = set(ARQUITETURAS_ALIASES.get(arquitetura, (arquitetura,)))
    tokens_arquitetura_no_nome = [token for token in TODOS_TOKENS_ARQ if _contem_token(nome_normalizado, token)]
    universal = _contem_token(nome_normalizado, "universal") or _contem_token(nome_normalizado, "multiarch")
    if tokens_arquitetura_no_nome and not universal and not any(token in aliases_atuais for token in tokens_arquitetura_no_nome):
        return None

    pontuacao = 0
    pontuacao += int(dados_so.get("prioridade_extensao", {}).get(extensao, 1))
    if encontrou_token_so:
        pontuacao += 12
    elif extensao in {".exe", ".msi", ".dmg", ".pkg", ".appimage", ".deb", ".rpm"}:
        pontuacao += 4
    if "gutenberg" in nome_lower:
        pontuacao += 5
    if any(_contem_token(nome_normalizado, termo) for termo in ("setup", "installer", "instalador", "install")):
        pontuacao += 4
    if any(_contem_token(nome_normalizado, termo) for termo in ("portable", "noinstall")):
        pontuacao -= 3
    if universal:
        pontuacao += 2
    if tokens_arquitetura_no_nome and any(token in aliases_atuais for token in tokens_arquitetura_no_nome):
        pontuacao += 4

    return pontuacao


@registrar_etapa
def _selecionar_asset_instalador(assets: list[dict[str, Any]], plataforma: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Seleciona o pacote de atualização compatível com o sistema operacional atual."""
    plataforma = plataforma or detectar_plataforma_atual()
    candidatos: list[tuple[int, dict[str, Any]]] = []
    for asset in assets or []:
        pontuacao = _pontuar_asset_instalador(asset, plataforma)
        if pontuacao is not None:
            candidatos.append((pontuacao, asset))
    if not candidatos:
        return None
    candidatos.sort(key=lambda item: item[0], reverse=True)
    return candidatos[0][1]


@registrar_etapa
def _selecionar_asset_sha256(assets: list[dict[str, Any]], nome_instalador: str) -> dict[str, Any] | None:
    nome_base = nome_instalador.lower()
    candidatos = []
    for asset in assets or []:
        nome = str(asset.get("name") or "").strip()
        nome_lower = nome.lower()
        url = str(asset.get("browser_download_url") or "").strip()
        if not nome or not url:
            continue
        if not (nome_lower.endswith(".sha256") or nome_lower.endswith(".sha256.txt") or "sha256" in nome_lower):
            continue
        pontuacao = 1
        if nome_base in nome_lower:
            pontuacao += 8
        if Path(nome_base).stem in nome_lower:
            pontuacao += 4
        if "gutenberg" in nome_lower:
            pontuacao += 2
        candidatos.append((pontuacao, asset))
    if not candidatos:
        return None
    candidatos.sort(key=lambda item: item[0], reverse=True)
    return candidatos[0][1]


@registrar_etapa
def _digest_asset(asset: dict[str, Any] | None) -> str | None:
    if not asset:
        return None
    digest = str(asset.get("digest") or "").strip()
    encontrado = re.search(r"sha256:([a-fA-F0-9]{64})", digest)
    if encontrado:
        return encontrado.group(1).lower()
    encontrado = re.search(r"\b([a-fA-F0-9]{64})\b", digest)
    if encontrado:
        return encontrado.group(1).lower()
    return None


@registrar_etapa
def _baixar_hash_sha256(asset_sha256: dict[str, Any] | None) -> str | None:
    if not asset_sha256:
        return None
    url = str(asset_sha256.get("browser_download_url") or "").strip()
    if not url:
        return None
    try:
        resposta = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_CONEXAO)
        resposta.raise_for_status()
        texto = resposta.text[:4096]
        encontrado = re.search(r"\b([a-fA-F0-9]{64})\b", texto)
        if encontrado:
            return encontrado.group(1).lower()
    except Exception:
        logger.warning("Não foi possível baixar o arquivo de hash SHA-256 da atualização", exc_info=True)
    return None


@registrar_etapa
def _calcular_sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest().lower()


@registrar_etapa
def consultar_release_mais_recente() -> dict[str, Any]:
    """Consulta a última release publicada no GitHub sem tratar ausência de release como erro crítico."""
    try:
        resposta = requests.get(GITHUB_RELEASES_API, headers=_headers_github(), timeout=TIMEOUT_CONEXAO)
    except requests.RequestException as exc:
        logger.info("Verificação de atualização ignorada: não foi possível conectar ao GitHub Releases (%s)", exc)
        return {
            "_indisponivel": True,
            "_motivo": "conexao",
            "_erro": "Não foi possível conectar ao GitHub para verificar atualizações.",
            "_detalhe": str(exc),
        }

    if resposta.status_code == 404:
        logger.info("Verificação de atualização ignorada: nenhuma release publicada em %s/%s", GITHUB_OWNER, GITHUB_REPO)
        return {
            "_indisponivel": True,
            "_motivo": "sem_release",
            "_erro": "Não foi encontrada nenhuma release publicada no repositório do Gutenberg.",
            "_detalhe": "Publique uma release no GitHub para ativar a verificação de atualizações.",
        }

    try:
        resposta.raise_for_status()
    except requests.RequestException as exc:
        logger.info("Verificação de atualização ignorada: GitHub Releases respondeu com erro (%s)", exc)
        return {
            "_indisponivel": True,
            "_motivo": "resposta_github",
            "_erro": "Não foi possível consultar o GitHub Releases no momento.",
            "_detalhe": str(exc),
        }

    try:
        return resposta.json()
    except ValueError as exc:
        logger.info("Verificação de atualização ignorada: resposta inválida do GitHub Releases (%s)", exc)
        return {
            "_indisponivel": True,
            "_motivo": "resposta_invalida",
            "_erro": "A resposta do GitHub Releases não pôde ser interpretada.",
            "_detalhe": str(exc),
        }


@registrar_etapa
def _mensagem_sem_pacote(plataforma: dict[str, Any]) -> str:
    if not plataforma.get("suportado"):
        return f"Este sistema operacional ({plataforma.get('rotulo')}) ainda não é suportado pelo atualizador automático."
    extensoes = ", ".join(plataforma.get("extensoes_aceitas") or [])
    return (
        f"A release mais recente não possui pacote compatível com "
        f"{plataforma.get('rotulo')} {plataforma.get('arquitetura')} ({extensoes})."
    )


@registrar_etapa
def verificar_atualizacao(automatico: bool = False) -> dict[str, Any]:
    """Verifica se existe uma versão mais recente disponível no GitHub."""

    def concluir(dados: dict[str, Any]) -> dict[str, Any]:
        return _salvar_ultima_verificacao_atualizacao(dados)

    plataforma = detectar_plataforma_atual()
    try:
        release = consultar_release_mais_recente()
        if release.get("_indisponivel"):
            return concluir({
                "ok": False,
                "atualizacao_indisponivel": True,
                "silencioso": bool(automatico),
                "motivo": str(release.get("_motivo") or "indisponivel"),
                "erro": str(release.get("_erro") or "Não foi possível verificar atualizações no momento."),
                "detalhe": str(release.get("_detalhe") or ""),
                "versao_atual": APP_VERSAO,
                "pagina_releases": GITHUB_HTML_RELEASES,
                "plataforma": plataforma,
            })
        assets = list(release.get("assets") or [])
        tag = str(release.get("tag_name") or "").strip()
        instalador = _selecionar_asset_instalador(assets, plataforma)
        hash_sha256 = _digest_asset(instalador)
        asset_sha256 = None
        if instalador and not hash_sha256:
            asset_sha256 = _selecionar_asset_sha256(assets, str(instalador.get("name") or ""))
            hash_sha256 = _baixar_hash_sha256(asset_sha256)

        ha_atualizacao = versao_remota_maior(tag, APP_VERSAO)
        dados_instalador = None
        if instalador:
            dados_instalador = {
                "nome": str(instalador.get("name") or "").strip(),
                "url": str(instalador.get("browser_download_url") or "").strip(),
                "tamanho": int(instalador.get("size") or 0),
                "tamanho_formatado": _formatar_tamanho(int(instalador.get("size") or 0)),
                "sha256": hash_sha256 or "",
                "tem_hash": bool(hash_sha256),
                "sistema": plataforma.get("sistema"),
                "rotulo_sistema": plataforma.get("rotulo"),
                "arquitetura": plataforma.get("arquitetura"),
            }

        aviso = "" if instalador else _mensagem_sem_pacote(plataforma)
        return concluir({
            "ok": True,
            "repositorio": f"{GITHUB_OWNER}/{GITHUB_REPO}",
            "pagina_releases": str(release.get("html_url") or GITHUB_HTML_RELEASES),
            "versao_atual": APP_VERSAO,
            "versao_remota": tag,
            "ha_atualizacao": ha_atualizacao,
            "titulo": str(release.get("name") or tag or "").strip(),
            "notas": str(release.get("body") or "").strip(),
            "publicada_em": str(release.get("published_at") or "").strip(),
            "verificado_em": datetime.now(timezone.utc).isoformat(),
            "plataforma": plataforma,
            "instalador": dados_instalador,
            "pode_atualizar": bool(ha_atualizacao and dados_instalador and dados_instalador.get("url")),
            "aviso": aviso,
        })
    except AtualizacaoErro as exc:
        return concluir({
            "ok": False,
            "silencioso": bool(automatico),
            "erro": str(exc),
            "versao_atual": APP_VERSAO,
            "pagina_releases": GITHUB_HTML_RELEASES,
            "plataforma": plataforma,
        })
    except requests.RequestException as exc:
        logger.warning("Falha de rede ao verificar atualização", exc_info=True)
        return concluir({
            "ok": False,
            "silencioso": bool(automatico),
            "erro": "Não foi possível conectar ao GitHub para verificar atualizações.",
            "detalhe": str(exc),
            "versao_atual": APP_VERSAO,
            "pagina_releases": GITHUB_HTML_RELEASES,
            "plataforma": plataforma,
        })
    except Exception as exc:
        logger.exception("Falha inesperada ao verificar atualização")
        return concluir({
            "ok": False,
            "silencioso": bool(automatico),
            "erro": "Não foi possível verificar atualizações no momento.",
            "detalhe": str(exc),
            "versao_atual": APP_VERSAO,
            "pagina_releases": GITHUB_HTML_RELEASES,
            "plataforma": plataforma,
        })


@registrar_etapa
def _nome_arquivo_seguro(nome: str) -> str:
    nome = Path(str(nome or "Gutenberg_Update")).name
    nome = re.sub(r"[^A-Za-z0-9._ -]+", "_", nome).strip(" .")
    return nome or "Gutenberg_Update"


@registrar_etapa
def baixar_instalador(
    info_instalador: dict[str, Any],
    versao: str,
    *,
    progresso_callback: Any | None = None,
    cancelar_evento: threading.Event | None = None,
) -> Path:
    """Baixa o pacote de atualização da release para a pasta local."""
    url = str(info_instalador.get("url") or "").strip()
    if not url:
        raise AtualizacaoErro("A release não possui URL de download do pacote de atualização.")

    PASTA_ATUALIZACOES.mkdir(parents=True, exist_ok=True)
    nome = _nome_arquivo_seguro(str(info_instalador.get("nome") or "Gutenberg_Update"))
    versao_limpa = re.sub(r"[^A-Za-z0-9._-]+", "_", str(versao or "latest").strip() or "latest")
    destino = PASTA_ATUALIZACOES / f"{versao_limpa}_{nome}"
    parcial = destino.with_name(destino.name + ".download")

    logger.info("Baixando atualização | url=%s | destino=%s", url, destino)
    bytes_total_info = int(info_instalador.get("tamanho") or 0)
    bytes_baixados = 0

    try:
        with requests.get(url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=TIMEOUT_CONEXAO) as resposta:
            resposta.raise_for_status()
            try:
                bytes_total = int(resposta.headers.get("Content-Length") or bytes_total_info or 0)
            except Exception:
                bytes_total = bytes_total_info
            if progresso_callback:
                progresso_callback(bytes_baixados, bytes_total, "download")
            with parcial.open("wb") as arquivo:
                for bloco in resposta.iter_content(chunk_size=256 * 1024):
                    if cancelar_evento is not None and cancelar_evento.is_set():
                        raise AtualizacaoCancelada("Atualização cancelada pelo usuário.")
                    if bloco:
                        arquivo.write(bloco)
                        bytes_baixados += len(bloco)
                        if progresso_callback:
                            progresso_callback(bytes_baixados, bytes_total, "download")
        if cancelar_evento is not None and cancelar_evento.is_set():
            raise AtualizacaoCancelada("Atualização cancelada pelo usuário.")
        parcial.replace(destino)
    except AtualizacaoCancelada:
        try:
            parcial.unlink(missing_ok=True)
        except Exception:
            pass
        raise
    except Exception:
        try:
            parcial.unlink(missing_ok=True)
        except Exception:
            pass
        raise

    hash_esperado = str(info_instalador.get("sha256") or "").strip().lower()
    if hash_esperado:
        if progresso_callback:
            progresso_callback(bytes_baixados, bytes_total_info or bytes_baixados, "verificando")
        hash_obtido = _calcular_sha256(destino)
        if hash_obtido != hash_esperado:
            try:
                destino.unlink(missing_ok=True)
            except Exception:
                pass
            raise AtualizacaoErro("O pacote baixado não passou na verificação de integridade SHA-256.")

    return destino


@registrar_etapa
def _obter_executavel_atual() -> Path | None:
    if getattr(sys, "frozen", False):
        try:
            caminho = Path(sys.executable).resolve()
            if caminho.exists():
                return caminho
        except Exception:
            return None
    return None


@registrar_etapa
def _montar_script_atualizacao_windows(instalador: Path, executavel_atual: Path | None) -> Path:
    PASTA_ATUALIZACOES.mkdir(parents=True, exist_ok=True)
    script = PASTA_ATUALIZACOES / "executar_atualizacao_gutenberg.cmd"
    reiniciar = ""
    if executavel_atual:
        reiniciar = f'\r\nif exist "{executavel_atual}" start "" "{executavel_atual}"\r\n'
    sufixo = instalador.suffix.lower()
    if sufixo == ".msi":
        comando = f'msiexec /i "{instalador}" /qn /norestart'
    else:
        comando = f'start "" /wait "{instalador}" /SP- /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS'
    conteudo = f"""@echo off
setlocal
timeout /t 2 /nobreak >nul
{comando}
{reiniciar}del "%~f0" >nul 2>nul
"""
    encoding_script = "mbcs" if os.name == "nt" else "utf-8"
    script.write_text(conteudo, encoding=encoding_script)
    return script


@registrar_etapa
def _executar_script_windows(script: Path) -> None:
    kwargs: dict[str, Any] = {
        "cwd": str(script.parent),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "shell": False,
    }
    flags = 0
    flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
    kwargs["creationflags"] = flags
    subprocess.Popen(["cmd.exe", "/c", str(script)], **kwargs)


@registrar_etapa
def _abrir_pacote_macos(pacote: Path) -> None:
    subprocess.Popen(["open", str(pacote)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@registrar_etapa
def _abrir_pacote_linux(pacote: Path) -> None:
    nome_lower = pacote.name.lower()
    if nome_lower.endswith(".appimage"):
        modo = pacote.stat().st_mode
        pacote.chmod(modo | 0o111)
        subprocess.Popen([str(pacote)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    abridor = shutil.which("xdg-open") or shutil.which("gio")
    if abridor and Path(abridor).name == "gio":
        subprocess.Popen([abridor, "open", str(pacote)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    if abridor:
        subprocess.Popen([abridor, str(pacote)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    raise AtualizacaoErro(f"O pacote foi baixado em {pacote}, mas não foi encontrado um abridor como xdg-open.")


@registrar_etapa
def _iniciar_pacote_atualizacao(pacote: Path, plataforma: dict[str, Any]) -> str:
    sistema = str(plataforma.get("sistema") or "")
    if sistema == "windows":
        script = _montar_script_atualizacao_windows(pacote, _obter_executavel_atual())
        _executar_script_windows(script)
        _encerrar_aplicacao_apos_resposta()
        return "O pacote de atualização foi baixado. O Gutenberg será fechado para concluir a atualização."
    if sistema == "macos":
        _abrir_pacote_macos(pacote)
        return "O pacote de atualização foi baixado e aberto. Siga as instruções do macOS para concluir a instalação."
    if sistema == "linux":
        _abrir_pacote_linux(pacote)
        return "O pacote de atualização foi baixado e aberto. Siga as instruções do seu sistema Linux para concluir a instalação."
    raise AtualizacaoErro("Este sistema operacional ainda não é suportado pelo atualizador automático.")


@registrar_etapa
def _encerrar_aplicacao_apos_resposta(delay: float = 1.2) -> None:
    def encerrar() -> None:
        time.sleep(delay)
        logger.info("Encerrando Gutenberg para permitir a atualização")
        os._exit(0)

    threading.Thread(target=encerrar, daemon=True).start()


def _worker_atualizacao(dados: dict[str, Any]) -> None:
    """Executa download e abertura do instalador em segundo plano."""
    try:
        instalador_info = dados.get("instalador") or {}
        versao = str(dados.get("versao_remota") or "latest")
        total_inicial = int(instalador_info.get("tamanho") or 0)

        def atualizar_progresso(bytes_baixados: int, bytes_total: int, etapa: str) -> None:
            total = int(bytes_total or total_inicial or 0)
            percentual = int(round((bytes_baixados / total) * 100)) if total else 0
            mensagem = "Verificando integridade..." if etapa == "verificando" else "Baixando atualização..."
            _atualizar_estado_atualizacao(
                etapa=etapa,
                mensagem=mensagem,
                bytes_baixados=int(bytes_baixados or 0),
                bytes_total=total,
                progresso=max(0, min(100, percentual)),
                cancelando=_CANCELAR_ATUALIZACAO.is_set(),
            )

        caminho_pacote = baixar_instalador(
            instalador_info,
            versao,
            progresso_callback=atualizar_progresso,
            cancelar_evento=_CANCELAR_ATUALIZACAO,
        )
        if _CANCELAR_ATUALIZACAO.is_set():
            raise AtualizacaoCancelada("Atualização cancelada pelo usuário.")
        _atualizar_estado_atualizacao(
            etapa="abrindo",
            mensagem="Abrindo pacote de atualização...",
            progresso=100,
            caminho=str(caminho_pacote),
            bytes_baixados=int(_ESTADO_ATUALIZACAO.get("bytes_total") or _ESTADO_ATUALIZACAO.get("bytes_baixados") or 0),
        )
        mensagem = _iniciar_pacote_atualizacao(caminho_pacote, dados.get("plataforma") or detectar_plataforma_atual())
        _atualizar_estado_atualizacao(
            ativo=False,
            concluido=True,
            etapa="concluido",
            mensagem=mensagem,
            progresso=100,
            caminho=str(caminho_pacote),
        )
    except AtualizacaoCancelada as exc:
        logger.info("Atualização cancelada pelo usuário")
        _atualizar_estado_atualizacao(
            ativo=False,
            cancelando=False,
            cancelado=True,
            concluido=False,
            etapa="cancelado",
            erro="",
            mensagem=str(exc),
        )
    except AtualizacaoErro as exc:
        logger.warning("Falha esperada ao iniciar atualização", exc_info=True)
        _atualizar_estado_atualizacao(
            ativo=False,
            cancelando=False,
            concluido=False,
            etapa="erro",
            erro=str(exc),
            mensagem=str(exc),
        )
    except Exception as exc:
        logger.exception("Falha inesperada ao iniciar atualização")
        _atualizar_estado_atualizacao(
            ativo=False,
            cancelando=False,
            concluido=False,
            etapa="erro",
            erro="Não foi possível iniciar a atualização automaticamente.",
            mensagem="Não foi possível iniciar a atualização automaticamente.",
        )


@registrar_etapa
def iniciar_atualizacao() -> dict[str, Any]:
    """Baixa o pacote da release mais recente e dispara o processo de atualização."""
    global _THREAD_ATUALIZACAO
    with _ESTADO_LOCK:
        if _ESTADO_ATUALIZACAO.get("ativo"):
            return {"ok": True, "em_andamento": True, "estado": _estado_publico()}

    dados = verificar_atualizacao()
    if not dados.get("ok"):
        return dados
    if not dados.get("ha_atualizacao"):
        return {**dados, "ok": False, "erro": "O Gutenberg já está na versão mais recente."}
    if not dados.get("pode_atualizar") or not dados.get("instalador"):
        return {**dados, "ok": False, "erro": dados.get("aviso") or "A release não possui pacote compatível para atualização automática."}

    instalador = dados.get("instalador") or {}
    _CANCELAR_ATUALIZACAO.clear()
    estado = _reiniciar_estado_atualizacao(
        ativo=True,
        cancelando=False,
        cancelado=False,
        concluido=False,
        erro="",
        etapa="iniciando",
        mensagem="Iniciando download da atualização...",
        progresso=0,
        bytes_baixados=0,
        bytes_total=int(instalador.get("tamanho") or 0),
        versao=str(dados.get("versao_remota") or ""),
        instalador=str(instalador.get("nome") or ""),
        caminho="",
    )
    _THREAD_ATUALIZACAO = threading.Thread(target=_worker_atualizacao, args=(dados,), daemon=True)
    _THREAD_ATUALIZACAO.start()
    return {
        **dados,
        "ok": True,
        "em_andamento": True,
        "atualizacao_iniciada": True,
        "mensagem": "Download da atualização iniciado.",
        "estado": estado,
    }
