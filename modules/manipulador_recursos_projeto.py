"""Recursos de planejamento por projeto: informações, fluxo, personagens, lugares e anotações."""
from __future__ import annotations

from copy import deepcopy
from html import unescape
import re
from hashlib import sha1
from pathlib import Path
from io import BytesIO
import base64
import binascii
from typing import Any
from uuid import uuid4

from .persistencia_json import ler_json
from .planejamento_rascunho import normalizar_planejamento, alterar_planejamento, importar_planejamento
from .persistencia_editor_db import BancoEditorLocal
from .utilidades import agora_iso
from .i18n import t
from .logging_config import obter_logger, registrar_etapa

logger = obter_logger(__name__)

ARQUIVO_RECURSOS_PROJETO = "recursos_projeto.json"
_DB_CACHE: dict[Path, BancoEditorLocal] = {}
MAX_HTML_INFO = 1_200_000
# O limite antigo era aplicado com um simples slice(), cortando o Base64 no meio
# do arquivo. Mantemos o tamanho-alvo para o banco, mas otimizamos a imagem antes
# de armazená-la. O limite de entrada protege contra payloads abusivamente grandes.
MAX_IMAGEM_DATA_URL = 900_000
MAX_IMAGEM_DATA_URL_ENTRADA = 24_000_000
MAX_PIXELS_IMAGEM_REFERENCIA = 50_000_000
MAX_TITULO_PAGINA = 90
MAX_PAGINAS_INFO_LATERAIS = 300
MAX_NOME_CATALOGO = 80
MAX_DESCRICAO_CATALOGO = 4000
MAX_ABAS_RECURSOS = 7
MAX_TITULO_ABA = 60


def _novo_id(prefixo: str) -> str:
    return f"{prefixo}_{uuid4().hex[:12]}"


@registrar_etapa
def _texto(valor: Any, limite: int = 4000) -> str:
    texto = str(valor or "").replace("\x00", "").strip()
    return texto[:limite]


@registrar_etapa
def _html(valor: Any) -> str:
    texto = str(valor or "").replace("\x00", "")
    return texto[:MAX_HTML_INFO]


def _validar_e_abrir_imagem_data_url(texto: str):
    """Decodifica uma imagem Base64 e força a leitura integral dos pixels.

    Esta validação é usada para identificar referências antigas que foram
    truncadas exatamente no limite de 900.000 caracteres.
    """
    cabecalho, separador, conteudo = texto.partition(",")
    if not separador or ";base64" not in cabecalho.lower():
        raise ValueError("Formato de imagem de referência não suportado para validação.")

    try:
        dados = base64.b64decode(conteudo, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("A imagem de referência contém dados Base64 inválidos.") from exc

    from PIL import Image, ImageOps

    try:
        arquivo = BytesIO(dados)
        imagem = Image.open(arquivo)
        largura, altura = imagem.size
        if largura <= 0 or altura <= 0 or largura * altura > MAX_PIXELS_IMAGEM_REFERENCIA:
            raise ValueError("A imagem de referência tem dimensões excessivas.")
        imagem.seek(0)
        imagem = ImageOps.exif_transpose(imagem)
        imagem.load()  # força a decodificação completa; não aceita uma imagem cortada
        return imagem.copy()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("A imagem de referência está incompleta ou corrompida.") from exc


def _otimizar_imagem_referencia(imagem) -> str:
    """Regrava a imagem inteira em WebP, reduzindo tamanho sem cortar a proporção."""
    from PIL import Image

    tem_alpha = "A" in imagem.getbands() or "transparency" in imagem.info
    modo = "RGBA" if tem_alpha else "RGB"
    imagem = imagem.convert(modo)

    # Cada tentativa reduz a resolução proporcionalmente; nunca há crop.
    tamanhos_maximos = (3000, 2400, 2000, 1800, 1600, 1400, 1200, 1000, 850, 700)
    qualidades = (84, 78, 72, 66)
    dimensoes_tentadas: set[tuple[int, int]] = set()
    for lado_maximo in tamanhos_maximos:
        candidato = imagem.copy()
        if max(candidato.size) > lado_maximo:
            candidato.thumbnail((lado_maximo, lado_maximo), Image.Resampling.LANCZOS)
        if candidato.size in dimensoes_tentadas:
            continue
        dimensoes_tentadas.add(candidato.size)

        for qualidade in qualidades:
            buffer = BytesIO()
            opcoes = {"format": "WEBP", "quality": qualidade, "method": 5}
            if tem_alpha:
                opcoes["alpha_quality"] = 95
                opcoes["exact"] = True
            candidato.save(buffer, **opcoes)
            conteudo = base64.b64encode(buffer.getvalue()).decode("ascii")
            data_url = "data:image/webp;base64," + conteudo
            if len(data_url) <= MAX_IMAGEM_DATA_URL:
                logger.info(
                    "Imagem de referência otimizada sem recorte | dimensoes=%sx%s | qualidade=%s | caracteres=%s",
                    candidato.width, candidato.height, qualidade, len(data_url),
                )
                return data_url

    raise ValueError(
        "Não foi possível reduzir a imagem de referência para o tamanho permitido. "
        "Reduza a resolução ou escolha outro arquivo e tente novamente."
    )


@registrar_etapa
def _imagem(valor: Any) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""
    if not texto.startswith("data:image/"):
        return ""

    tamanho = len(texto)
    if tamanho > MAX_IMAGEM_DATA_URL_ENTRADA:
        raise ValueError(
            "A imagem de referência é muito grande (limite de aproximadamente 18 MB). "
            "Reduza o tamanho do arquivo e tente novamente."
        )

    # Imagens menores que o limite antigo não eram alteradas; mantemos esse
    # comportamento para preservar formatos já aceitos, inclusive SVGs pequenos.
    if tamanho < MAX_IMAGEM_DATA_URL:
        return texto

    try:
        imagem = _validar_e_abrir_imagem_data_url(texto)
    except ValueError as exc:
        if tamanho == MAX_IMAGEM_DATA_URL:
            # A versão anterior cortava todas as imagens grandes exatamente neste
            # ponto. Não devolvemos esse arquivo incompleto para a interface.
            logger.warning(
                "Referência visual antiga ignorada porque parece ter sido truncada pelo limite anterior de %s caracteres: %s",
                MAX_IMAGEM_DATA_URL, exc,
            )
            return ""
        raise

    # Se chegou ao limite exato e a imagem ainda é integral, não é necessário
    # recomprimir. Acima dele, convertemos para WebP dentro do limite, sem crop.
    if tamanho == MAX_IMAGEM_DATA_URL:
        return texto
    return _otimizar_imagem_referencia(imagem)


def _imagem_necessita_reenvio(valor: Any, imagem_normalizada: str = "") -> bool:
    """Marca referências que foram cortadas pelo limite antigo e perderam bytes."""
    texto = str(valor or "").strip()
    return bool(
        texto.startswith("data:image/")
        and len(texto) == MAX_IMAGEM_DATA_URL
        and not imagem_normalizada
    )


@registrar_etapa
def _titulo_padrao_aba(chave: str) -> str:
    if chave == "fluxo":
        return t("resources.flow", default="Fluxo")
    if chave == "personagens":
        return t("resources.characters", default="Personagens")
    if chave == "lugares":
        return t("resources.places", default="Lugares")
    if chave == "anotacoes":
        return t("resources.notes", default="Anotações")
    return t("resources.default_page_title", default="Página inicial")


@registrar_etapa
def _aba_padrao(chave: str) -> dict[str, Any]:
    agora = agora_iso()
    return {
        "id": f"{chave}_principal",
        "titulo": _titulo_padrao_aba(chave),
        "data_criacao": agora,
        "data_atualizacao": agora,
    }


@registrar_etapa
def _pagina_info_padrao(agora: str | None = None) -> dict[str, Any]:
    agora = agora or agora_iso()
    return {
        "id": _novo_id("info"),
        "titulo": t("resources.default_page_title", default="Página inicial"),
        "data_criacao": agora,
        "data_atualizacao": agora,
    }


@registrar_etapa
def _aba_info_padrao(agora: str | None = None, paginas: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    agora = agora or agora_iso()
    return {
        "id": "informacoes_principal",
        "titulo": t("resources.default_page_title", default="Página inicial"),
        "paginas": paginas if paginas is not None else [_pagina_info_padrao(agora)],
        "data_criacao": agora,
        "data_atualizacao": agora,
    }


@registrar_etapa
def _normalizar_abas(valor: Any, chave: str) -> list[dict[str, Any]]:
    entrada = valor if isinstance(valor, list) else []
    normalizadas: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for item in entrada:
        if not isinstance(item, dict):
            continue
        pid = _texto(item.get("id"), 80) or _novo_id(chave)
        if pid in vistos:
            continue
        vistos.add(pid)
        normalizadas.append({
            "id": pid,
            "titulo": _texto(item.get("titulo") or item.get("nome"), MAX_TITULO_ABA) or _titulo_padrao_aba(chave),
            "data_criacao": _texto(item.get("data_criacao"), 40) or agora_iso(),
            "data_atualizacao": _texto(item.get("data_atualizacao"), 40) or agora_iso(),
        })
        if len(normalizadas) >= MAX_ABAS_RECURSOS:
            break
    if not normalizadas:
        normalizadas = [_aba_padrao(chave)]
    return normalizadas[:MAX_ABAS_RECURSOS]


@registrar_etapa
def estrutura_padrao_recursos() -> dict[str, Any]:
    agora = agora_iso()
    pagina_info = _pagina_info_padrao(agora)
    abas_info = [_aba_info_padrao(agora, [pagina_info])]
    paginas_personagens = [_aba_padrao("personagens")]
    paginas_lugares = [_aba_padrao("lugares")]
    paginas_anotacoes = [_aba_padrao("anotacoes")]
    fluxos = [{**_aba_padrao("fluxo"), "nodes": [], "edges": []}]
    return {
        "versao": 4,
        "informacoes_abas": abas_info,
        "informacoes": _informacoes_planas(abas_info),
        "fluxos": fluxos,
        "fluxo": {"nodes": [], "edges": []},
        "personagens_paginas": paginas_personagens,
        "lugares_paginas": paginas_lugares,
        "anotacoes_paginas": paginas_anotacoes,
        "personagens": [],
        "lugares": [],
        "anotacoes": [],
        "ocultos": {"personagens": [], "lugares": [], "anotacoes": []},
        "planejamento": normalizar_planejamento(None),
        "data_atualizacao": agora,
    }


@registrar_etapa
def _db(pasta_projeto: Path) -> BancoEditorLocal:
    pasta = Path(pasta_projeto)
    db = _DB_CACHE.get(pasta)
    if db is None:
        db = BancoEditorLocal(pasta)
        _DB_CACHE[pasta] = db
    return db


@registrar_etapa
def caminho_recursos_projeto(pasta_projeto: Path) -> Path:
    return pasta_projeto / ARQUIVO_RECURSOS_PROJETO


@registrar_etapa
def _normalizar_paginas(valor: Any) -> list[dict[str, Any]]:
    paginas = valor if isinstance(valor, list) else []
    normalizadas: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for item in paginas:
        if not isinstance(item, dict):
            continue
        pid = _texto(item.get("id"), 80) or _novo_id("info")
        if pid in vistos:
            continue
        vistos.add(pid)
        titulo = _texto(item.get("titulo"), MAX_TITULO_PAGINA) or t("resources.untitled", default="Sem título")
        normalizadas.append({
            "id": pid,
            "titulo": titulo,
            "html": _html(item.get("html")),
            "data_criacao": _texto(item.get("data_criacao"), 40) or agora_iso(),
            "data_atualizacao": _texto(item.get("data_atualizacao"), 40) or agora_iso(),
        })
        if len(normalizadas) >= MAX_PAGINAS_INFO_LATERAIS:
            break
    if not normalizadas:
        normalizadas = [_pagina_info_padrao()]
    return normalizadas


@registrar_etapa
def _normalizar_abas_informacoes(valor: Any, paginas_legadas: Any = None) -> list[dict[str, Any]]:
    entrada = valor if isinstance(valor, list) else []
    parece_abas = any(isinstance(item, dict) and (isinstance(item.get("paginas"), list) or isinstance(item.get("pages"), list) or isinstance(item.get("informacoes"), list)) for item in entrada)
    if not parece_abas:
        paginas = _normalizar_paginas(paginas_legadas if paginas_legadas is not None else valor)
        return [_aba_info_padrao(paginas=paginas)]
    normalizadas: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for item in entrada:
        if not isinstance(item, dict):
            continue
        pid = _texto(item.get("id"), 80) or _novo_id("info_tab")
        if pid in vistos:
            continue
        vistos.add(pid)
        normalizadas.append({
            "id": pid,
            "titulo": _texto(item.get("titulo") or item.get("nome"), MAX_TITULO_ABA) or _titulo_padrao_aba("informacoes"),
            "paginas": _normalizar_paginas(item.get("paginas") or item.get("informacoes") or item.get("pages")),
            "data_criacao": _texto(item.get("data_criacao"), 40) or agora_iso(),
            "data_atualizacao": _texto(item.get("data_atualizacao"), 40) or agora_iso(),
        })
        if len(normalizadas) >= MAX_ABAS_RECURSOS:
            break
    if not normalizadas:
        normalizadas = [_aba_info_padrao()]
    return normalizadas[:MAX_ABAS_RECURSOS]


@registrar_etapa
def _informacoes_planas(abas: Any) -> list[dict[str, Any]]:
    planas: list[dict[str, Any]] = []
    ids_usados: set[str] = set()
    for aba in abas if isinstance(abas, list) else []:
        if not isinstance(aba, dict):
            continue
        aba_id = _texto(aba.get("id"), 80)
        aba_titulo = _texto(aba.get("titulo"), MAX_TITULO_ABA)
        for pagina in aba.get("paginas") or []:
            if not isinstance(pagina, dict):
                continue
            item = dict(pagina)
            pid_original = _texto(item.get("id"), 80) or _novo_id("info")
            pid_final = pid_original
            if pid_final in ids_usados:
                pid_final = _texto(f"{aba_id}_{pid_original}", 80) or _novo_id("info")
            contador = 2
            base = pid_final
            while pid_final in ids_usados:
                sufixo = f"_{contador}"
                pid_final = f"{base[:max(1, 80 - len(sufixo))]}{sufixo}"
                contador += 1
            ids_usados.add(pid_final)
            item["id"] = pid_final
            item["pagina_id_original"] = pid_original
            item["aba_id"] = aba_id
            item["aba_titulo"] = aba_titulo
            planas.append(item)
    if not planas:
        planas = [_pagina_info_padrao()]
    return planas


@registrar_etapa
def _normalizar_fluxo(valor: Any) -> dict[str, list[dict[str, Any]]]:
    fluxo = valor if isinstance(valor, dict) else {}
    nodes_in = fluxo.get("nodes") if isinstance(fluxo.get("nodes"), list) else []
    edges_in = fluxo.get("edges") if isinstance(fluxo.get("edges"), list) else []
    nodes: list[dict[str, Any]] = []
    ids_validos: set[str] = set()
    for item in nodes_in:
        if not isinstance(item, dict):
            continue
        nid = _texto(item.get("id"), 80) or _novo_id("node")
        try:
            x = max(-5000, min(5000, float(item.get("x", 120))))
            y = max(-5000, min(5000, float(item.get("y", 120))))
            w = max(170, min(760, float(item.get("width", 240))))
            h = max(96, min(620, float(item.get("height", 150))))
        except Exception:
            x, y, w, h = 120, 120, 240, 150
        nodes.append({
            "id": nid,
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "titulo": _texto(item.get("titulo"), 120) or t("resources.new_block", default="Novo bloco"),
            "texto": _texto(item.get("texto"), 4000),
        })
        ids_validos.add(nid)
    lados = {"top", "right", "bottom", "left"}
    edges: list[dict[str, Any]] = []
    for item in edges_in:
        if not isinstance(item, dict):
            continue
        origem = _texto(item.get("from"), 80)
        destino = _texto(item.get("to"), 80)
        if origem not in ids_validos or destino not in ids_validos or origem == destino:
            continue
        from_side = _texto(item.get("fromSide"), 10)
        to_side = _texto(item.get("toSide"), 10)
        edges.append({
            "id": _texto(item.get("id"), 80) or _novo_id("edge"),
            "from": origem,
            "to": destino,
            "fromSide": from_side if from_side in lados else "right",
            "toSide": to_side if to_side in lados else "left",
        })
    return {"nodes": nodes[:240], "edges": edges[:500]}


@registrar_etapa
def _normalizar_fluxos(valor: Any, fluxo_legado: Any = None) -> list[dict[str, Any]]:
    entrada = valor if isinstance(valor, list) else []
    if not entrada and isinstance(fluxo_legado, dict):
        entrada = [{**_aba_padrao("fluxo"), **_normalizar_fluxo(fluxo_legado)}]
    normalizados: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for item in entrada:
        if not isinstance(item, dict):
            continue
        pid = _texto(item.get("id"), 80) or _novo_id("fluxo")
        if pid in vistos:
            continue
        vistos.add(pid)
        bruto_fluxo = item.get("fluxo") if isinstance(item.get("fluxo"), dict) else item
        fluxo = _normalizar_fluxo(bruto_fluxo)
        normalizados.append({
            "id": pid,
            "titulo": _texto(item.get("titulo") or item.get("nome"), MAX_TITULO_ABA) or _titulo_padrao_aba("fluxo"),
            "nodes": fluxo.get("nodes", []),
            "edges": fluxo.get("edges", []),
            "data_criacao": _texto(item.get("data_criacao"), 40) or agora_iso(),
            "data_atualizacao": _texto(item.get("data_atualizacao"), 40) or agora_iso(),
        })
        if len(normalizados) >= MAX_ABAS_RECURSOS:
            break
    if not normalizados:
        normalizados = [{**_aba_padrao("fluxo"), "nodes": [], "edges": []}]
    return normalizados[:MAX_ABAS_RECURSOS]


@registrar_etapa
def _fluxo_principal(fluxos: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    primeiro = fluxos[0] if fluxos else {"nodes": [], "edges": []}
    return {"nodes": deepcopy(primeiro.get("nodes") or []), "edges": deepcopy(primeiro.get("edges") or [])}


@registrar_etapa
def _normalizar_catalogo(
    valor: Any,
    *,
    permitir_imagem: bool = True,
    paginas_validas: set[str] | None = None,
    pagina_padrao: str = "",
) -> list[dict[str, Any]]:
    itens = valor if isinstance(valor, list) else []
    normalizados: list[dict[str, Any]] = []
    vistos: set[tuple[str, str]] = set()
    pagina_padrao = pagina_padrao or (next(iter(paginas_validas)) if paginas_validas else "")
    for item in itens:
        if not isinstance(item, dict):
            continue
        nome = _texto(item.get("nome") or item.get("titulo") or item.get("name") or item.get("title"), MAX_NOME_CATALOGO)
        if not nome:
            continue
        pagina_id = _texto(item.get("pagina_id") or item.get("page_id") or item.get("pagina"), 80)
        if paginas_validas is not None and pagina_id not in paginas_validas:
            pagina_id = pagina_padrao
        chave = (pagina_id, nome.casefold())
        if chave in vistos:
            continue
        vistos.add(chave)
        imagem_original = item.get("imagem") or item.get("image")
        imagem = _imagem(imagem_original) if permitir_imagem else ""
        normalizados.append({
            "id": _texto(item.get("id"), 80) or _novo_id("cat"),
            "pagina_id": pagina_id,
            "nome": nome,
            "descricao": _texto(item.get("descricao") or item.get("anotacao") or item.get("texto") or item.get("description") or item.get("text"), MAX_DESCRICAO_CATALOGO),
            "imagem": imagem,
            "imagem_necessita_reenvio": permitir_imagem and (
                bool(item.get("imagem_necessita_reenvio"))
                or _imagem_necessita_reenvio(imagem_original, imagem)
            ),
            "origem": "projeto",
            "data_criacao": _texto(item.get("data_criacao"), 40) or agora_iso(),
            "data_atualizacao": _texto(item.get("data_atualizacao"), 40) or agora_iso(),
        })
    return normalizados[:400]


@registrar_etapa
def _normalizar_ocultos(valor: Any) -> dict[str, list[str]]:
    base = valor if isinstance(valor, dict) else {}
    resultado = {"personagens": [], "lugares": [], "anotacoes": []}
    for chave in resultado:
        lista = base.get(chave)
        if not isinstance(lista, list):
            continue
        vistos: set[str] = set()
        for nome in lista:
            texto = _texto(nome, MAX_NOME_CATALOGO)
            key = texto.casefold()
            if texto and key not in vistos:
                vistos.add(key)
                resultado[chave].append(texto)
    return resultado


@registrar_etapa
def _paginas_catalogo_de_dados(dados: dict[str, Any], chave: str) -> list[dict[str, Any]]:
    return _normalizar_abas(dados.get(f"{chave}_paginas") or dados.get(f"paginas_{chave}"), chave)


@registrar_etapa
def normalizar_recursos(dados: Any) -> dict[str, Any]:
    base = estrutura_padrao_recursos()
    if not isinstance(dados, dict):
        return base
    lugares = dados.get("lugares") if "lugares" in dados else dados.get("locais")
    fluxos = _normalizar_fluxos(dados.get("fluxos"), dados.get("fluxo"))
    paginas_personagens = _paginas_catalogo_de_dados(dados, "personagens")
    paginas_lugares = _paginas_catalogo_de_dados(dados, "lugares")
    paginas_anotacoes = _paginas_catalogo_de_dados(dados, "anotacoes")
    id_personagens = {p["id"] for p in paginas_personagens}
    id_lugares = {p["id"] for p in paginas_lugares}
    id_anotacoes = {p["id"] for p in paginas_anotacoes}
    informacoes_abas = _normalizar_abas_informacoes(
        dados.get("informacoes_abas") or dados.get("abas_informacoes"),
        dados.get("informacoes"),
    )
    normalizados = {
        "versao": 4,
        "informacoes_abas": informacoes_abas,
        "informacoes": _informacoes_planas(informacoes_abas),
        "fluxos": fluxos,
        "fluxo": _fluxo_principal(fluxos),
        "personagens_paginas": paginas_personagens,
        "lugares_paginas": paginas_lugares,
        "anotacoes_paginas": paginas_anotacoes,
        "personagens": _normalizar_catalogo(dados.get("personagens"), paginas_validas=id_personagens, pagina_padrao=paginas_personagens[0]["id"]),
        "lugares": _normalizar_catalogo(lugares, paginas_validas=id_lugares, pagina_padrao=paginas_lugares[0]["id"]),
        "anotacoes": _normalizar_catalogo(dados.get("anotacoes") or dados.get("notas") or dados.get("notes"), permitir_imagem=False, paginas_validas=id_anotacoes, pagina_padrao=paginas_anotacoes[0]["id"]),
        "ocultos": _normalizar_ocultos(dados.get("ocultos")),
        "planejamento": normalizar_planejamento(dados.get("planejamento")),
        "data_atualizacao": _texto(dados.get("data_atualizacao"), 40) or agora_iso(),
    }
    return normalizados


@registrar_etapa
def ler_recursos_projeto(pasta_projeto: Path) -> dict[str, Any]:
    """Lê recursos do banco SQLite do editor, migrando o JSON legado uma única vez quando existir."""
    banco = _db(pasta_projeto)
    dados_banco = banco.ler_recursos_projeto()
    if dados_banco:
        return normalizar_recursos(dados_banco)

    caminho_legado = caminho_recursos_projeto(Path(pasta_projeto))
    if caminho_legado.exists():
        dados = normalizar_recursos(ler_json(caminho_legado, {}))
    else:
        dados = estrutura_padrao_recursos()
    dados["data_atualizacao"] = _texto(dados.get("data_atualizacao"), 40) or agora_iso()
    return normalizar_recursos(banco.salvar_recursos_projeto(dados))


@registrar_etapa
def salvar_recursos_projeto(pasta_projeto: Path, dados: dict[str, Any]) -> dict[str, Any]:
    normalizados = normalizar_recursos(dados)
    normalizados["data_atualizacao"] = agora_iso()
    return normalizar_recursos(_db(pasta_projeto).salvar_recursos_projeto(normalizados))


@registrar_etapa
def salvar_informacoes_projeto(pasta_projeto: Path, informacoes: Any, informacoes_abas: Any | None = None) -> dict[str, Any]:
    dados = ler_recursos_projeto(pasta_projeto)
    payload_abas = informacoes_abas if informacoes_abas is not None else informacoes
    dados["informacoes_abas"] = _normalizar_abas_informacoes(payload_abas, informacoes)
    dados["informacoes"] = _informacoes_planas(dados["informacoes_abas"])
    return salvar_recursos_projeto(pasta_projeto, dados)


@registrar_etapa
def salvar_fluxo_projeto(pasta_projeto: Path, fluxo: Any) -> dict[str, Any]:
    dados = ler_recursos_projeto(pasta_projeto)
    if isinstance(fluxo, dict) and isinstance(fluxo.get("fluxos"), list):
        dados["fluxos"] = _normalizar_fluxos(fluxo.get("fluxos"), fluxo.get("fluxo"))
    else:
        fluxos = _normalizar_fluxos(None, fluxo)
        dados["fluxos"] = fluxos
    dados["fluxo"] = _fluxo_principal(dados["fluxos"])
    return salvar_recursos_projeto(pasta_projeto, dados)


@registrar_etapa
def modificar_planejamento_projeto(pasta_projeto: Path, tipo: str, operacao: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Altera apenas cenas/fontes, preservando os demais recursos do Rascunho."""
    dados = ler_recursos_projeto(pasta_projeto)
    atualizados = alterar_planejamento(dados, tipo, operacao, payload)
    return salvar_recursos_projeto(pasta_projeto, atualizados)


@registrar_etapa
def _chave_tipo_catalogo(tipo: str) -> str:
    if tipo in {"personagens", "personagem", "characters"}:
        return "personagens"
    if tipo in {"lugares", "locais", "lugar", "local", "places", "locations"}:
        return "lugares"
    if tipo in {"anotacoes", "anotacao", "notas", "nota", "annotations", "notes", "note"}:
        return "anotacoes"
    raise ValueError(t("backend.invalid_catalog_type", default="Tipo de catálogo inválido."))


@registrar_etapa
def _normalizar_catalogo_com_paginas(chave: str, itens: Any, paginas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = {p["id"] for p in paginas}
    return _normalizar_catalogo(itens, permitir_imagem=(chave != "anotacoes"), paginas_validas=ids, pagina_padrao=paginas[0]["id"])


@registrar_etapa
def salvar_paginas_catalogo_projeto(pasta_projeto: Path, tipo: str, paginas: Any, itens: Any | None = None) -> dict[str, Any]:
    chave = _chave_tipo_catalogo(tipo)
    dados = ler_recursos_projeto(pasta_projeto)
    paginas_norm = _normalizar_abas(paginas, chave)
    dados[f"{chave}_paginas"] = paginas_norm
    itens_base = dados.get(chave, []) if itens is None else itens
    dados[chave] = _normalizar_catalogo_com_paginas(chave, itens_base, paginas_norm)
    return salvar_recursos_projeto(pasta_projeto, dados)


@registrar_etapa
def salvar_item_catalogo_projeto(pasta_projeto: Path, tipo: str, item: dict[str, Any]) -> dict[str, Any]:
    chave = _chave_tipo_catalogo(tipo)
    dados = ler_recursos_projeto(pasta_projeto)
    paginas = _paginas_catalogo_de_dados(dados, chave)
    ids_paginas = {p["id"] for p in paginas}
    pagina_id = _texto(item.get("pagina_id") or item.get("page_id"), 80)
    if pagina_id not in ids_paginas:
        pagina_id = paginas[0]["id"]
    nome = _texto(item.get("nome"), MAX_NOME_CATALOGO)
    if not nome:
        raise ValueError(t("resources.name_required", default="Informe um nome."))
    item_id = _texto(item.get("id"), 80)
    agora = agora_iso()
    imagem_original = item.get("imagem")
    imagem_normalizada = "" if chave == "anotacoes" else _imagem(imagem_original)
    novo = {
        "id": item_id or _novo_id("cat"),
        "pagina_id": pagina_id,
        "nome": nome,
        "descricao": _texto(item.get("descricao"), MAX_DESCRICAO_CATALOGO),
        "imagem": imagem_normalizada,
        "imagem_necessita_reenvio": False if chave == "anotacoes" else (
            bool(item.get("imagem_necessita_reenvio"))
            or _imagem_necessita_reenvio(imagem_original, imagem_normalizada)
        ),
        "origem": "projeto",
        "data_criacao": agora,
        "data_atualizacao": agora,
    }
    atualizados: list[dict[str, Any]] = []
    aplicado = False
    for existente in dados.get(chave, []):
        mesmo_id = item_id and existente.get("id") == item_id
        mesmo_nome = (
            str(existente.get("nome") or "").casefold() == nome.casefold()
            and str(existente.get("pagina_id") or paginas[0]["id"]) == pagina_id
        )
        if mesmo_id or mesmo_nome:
            novo["id"] = existente.get("id") or novo["id"]
            novo["data_criacao"] = existente.get("data_criacao") or novo["data_criacao"]
            atualizados.append(novo)
            aplicado = True
        else:
            atualizados.append(existente)
    if not aplicado:
        atualizados.append(novo)
    dados.setdefault("ocultos", {"personagens": [], "lugares": [], "anotacoes": []})
    dados["ocultos"].setdefault(chave, [])
    dados["ocultos"][chave] = [n for n in dados["ocultos"].get(chave, []) if str(n).casefold() != nome.casefold()]
    dados[f"{chave}_paginas"] = paginas
    dados[chave] = _normalizar_catalogo_com_paginas(chave, atualizados, paginas)
    return salvar_recursos_projeto(pasta_projeto, dados)


@registrar_etapa
def excluir_item_catalogo_projeto(pasta_projeto: Path, tipo: str, identificador: str | None = None, nome: str | None = None, pagina_id: str | None = None) -> dict[str, Any]:
    chave = _chave_tipo_catalogo(tipo)
    dados = ler_recursos_projeto(pasta_projeto)
    paginas = _paginas_catalogo_de_dados(dados, chave)
    pagina_id_limpa = _texto(pagina_id, 80)
    identificador = _texto(identificador, 80)
    nome_limpo = _texto(nome, MAX_NOME_CATALOGO)
    removidos: list[str] = []
    restantes: list[dict[str, Any]] = []
    for item in dados.get(chave, []):
        item_pagina = str(item.get("pagina_id") or paginas[0]["id"])
        mesma_pagina = not pagina_id_limpa or item_pagina == pagina_id_limpa
        mesmo_id = identificador and item.get("id") == identificador
        mesmo_nome = nome_limpo and mesma_pagina and str(item.get("nome") or "").casefold() == nome_limpo.casefold()
        if mesmo_id or mesmo_nome:
            removidos.append(str(item.get("nome") or nome_limpo).strip())
        else:
            restantes.append(item)
    nomes_para_ocultar = []
    if nome_limpo and not removidos:
        nomes_para_ocultar.append(nome_limpo)
    ocultos = dados.setdefault("ocultos", {"personagens": [], "lugares": [], "anotacoes": []}).setdefault(chave, [])
    ocultos_case = {str(x).casefold() for x in ocultos}
    for nome_removido in nomes_para_ocultar:
        key = nome_removido.casefold()
        if nome_removido and key not in ocultos_case:
            ocultos.append(nome_removido)
            ocultos_case.add(key)
    dados[f"{chave}_paginas"] = paginas
    dados[chave] = _normalizar_catalogo_com_paginas(chave, restantes, paginas)
    return salvar_recursos_projeto(pasta_projeto, dados)


@registrar_etapa
def _nome_catalogo_importado_unico(nome: str, usados: set[tuple[str, str]], pagina_id: str) -> str:
    base = _texto(nome, MAX_NOME_CATALOGO) or t("resources.untitled", default="Sem título")
    if (pagina_id, base.casefold()) not in usados:
        usados.add((pagina_id, base.casefold()))
        return base
    candidato = _texto(f"{base} (importado)", MAX_NOME_CATALOGO)
    if (pagina_id, candidato.casefold()) not in usados:
        usados.add((pagina_id, candidato.casefold()))
        return candidato
    for indice in range(2, 1000):
        sufixo = f" (importado {indice})"
        limite_base = max(1, MAX_NOME_CATALOGO - len(sufixo))
        candidato = f"{base[:limite_base].rstrip()}{sufixo}"
        if (pagina_id, candidato.casefold()) not in usados:
            usados.add((pagina_id, candidato.casefold()))
            return candidato
    usado = _novo_id("cat")[:MAX_NOME_CATALOGO]
    usados.add((pagina_id, usado.casefold()))
    return usado


@registrar_etapa
def _titulo_aba_importada_unico(titulo: str, usados: set[str]) -> str:
    base = _texto(titulo, MAX_TITULO_ABA) or t("resources.untitled", default="Sem título")
    if base.casefold() not in usados:
        usados.add(base.casefold())
        return base
    candidato = _texto(f"{base} (importado)", MAX_TITULO_ABA)
    if candidato.casefold() not in usados:
        usados.add(candidato.casefold())
        return candidato
    for indice in range(2, 1000):
        sufixo = f" (importado {indice})"
        limite_base = max(1, MAX_TITULO_ABA - len(sufixo))
        candidato = f"{base[:limite_base].rstrip()}{sufixo}"
        if candidato.casefold() not in usados:
            usados.add(candidato.casefold())
            return candidato
    usado = _novo_id("aba")[:MAX_TITULO_ABA]
    usados.add(usado.casefold())
    return usado


def _html_info_tem_conteudo(valor: Any) -> bool:
    html = str(valor or "")
    if re.search(r"<(img|audio|video|iframe|object|embed|table|svg|canvas)\b", html, re.IGNORECASE):
        return True
    texto = re.sub(r"<[^>]*>", "", html)
    texto = unescape(texto).replace("\u00a0", " ").strip()
    return bool(texto)


def _aba_info_padrao_vazia(aba: dict[str, Any], planejamento: dict[str, Any]) -> bool:
    paginas = aba.get("paginas") or []
    if aba.get("id") != "informacoes_principal" or len(paginas) != 1:
        return False
    pagina = paginas[0]
    if str(aba.get("titulo") or "").casefold() != _titulo_padrao_aba("informacoes").casefold():
        return False
    if str(pagina.get("titulo") or "").casefold() != t("resources.default_page_title", default="Página inicial").casefold():
        return False
    if _html_info_tem_conteudo(pagina.get("html")):
        return False
    return not any(pagina.get("id") in cena.get("paginas_info", []) for cena in (planejamento or {}).get("cenas", []))


def _fluxo_padrao_vazio(fluxo: dict[str, Any], planejamento: dict[str, Any]) -> bool:
    if fluxo.get("id") != "fluxo_principal" or fluxo.get("nodes") or fluxo.get("edges"):
        return False
    ids_nos = {node.get("id") for item in (planejamento or {}).get("cenas", []) for node in item.get("nos_fluxo", [])}
    return not ids_nos


def _pagina_catalogo_padrao_vazia(chave: str, pagina: dict[str, Any], itens: list[dict[str, Any]]) -> bool:
    return (
        pagina.get("id") == f"{chave}_principal"
        and str(pagina.get("titulo") or "").casefold() == _titulo_padrao_aba(chave).casefold()
        and not any(item.get("pagina_id") == pagina.get("id") for item in itens)
    )


def _validar_capacidade_mesclagem(atuais: dict[str, Any], importados: dict[str, Any]) -> dict[str, bool]:
    """Faz a pré-validação de capacidade antes de alterar qualquer dado do projeto."""
    planejamento_atual = atuais.get("planejamento") or {}
    planejamento_importado = importados.get("planejamento") or {}
    reutilizar_info = bool(
        atuais.get("informacoes_abas")
        and _aba_info_padrao_vazia(atuais["informacoes_abas"][0], planejamento_atual)
    )
    reutilizar_fluxo = bool(
        atuais.get("fluxos")
        and _fluxo_padrao_vazio(atuais["fluxos"][0], planejamento_atual)
    )
    if len(atuais.get("informacoes_abas") or []) - int(reutilizar_info) + len(importados.get("informacoes_abas") or []) > MAX_ABAS_RECURSOS:
        raise ValueError(
            f"Não foi possível importar todos os recursos: o projeto já atingiu o limite de {MAX_ABAS_RECURSOS} abas de Informações. "
            "Remova uma aba ou importe os recursos em outro projeto. Nenhum dado foi alterado."
        )
    if len(atuais.get("fluxos") or []) - int(reutilizar_fluxo) + len(importados.get("fluxos") or []) > MAX_ABAS_RECURSOS:
        raise ValueError(
            f"Não foi possível importar todos os recursos: o projeto já atingiu o limite de {MAX_ABAS_RECURSOS} fluxogramas. "
            "Remova um fluxograma ou importe os recursos em outro projeto. Nenhum dado foi alterado."
        )

    reutilizar_catalogo: dict[str, bool] = {}
    for chave in ("personagens", "lugares", "anotacoes"):
        paginas = atuais.get(f"{chave}_paginas") or []
        itens_atuais = atuais.get(chave) or []
        reutilizar_catalogo[chave] = bool(
            paginas and _pagina_catalogo_padrao_vazia(chave, paginas[0], itens_atuais)
        )
        if len(paginas) - int(reutilizar_catalogo[chave]) + len(importados.get(f"{chave}_paginas") or []) > MAX_ABAS_RECURSOS:
            raise ValueError(
                f"Não foi possível importar todos os recursos: o projeto já atingiu o limite de {MAX_ABAS_RECURSOS} abas de {chave}. "
                "Remova uma aba ou importe os recursos em outro projeto. Nenhum dado foi alterado."
            )
        total_itens = len(itens_atuais) + len(importados.get(chave) or [])
        if total_itens > 400:
            raise ValueError(
                f"Não foi possível importar todos os recursos: o catálogo de {chave} ultrapassaria o limite de 400 itens. "
                "Remova itens ou importe os recursos em outro projeto. Nenhum dado foi alterado."
            )

    for chave, limite in (("cenas", 300), ("fontes", 300)):
        if len(planejamento_atual.get(chave) or []) + len(planejamento_importado.get(chave) or []) > limite:
            raise ValueError(
                f"Não foi possível importar todos os recursos: o planejamento de {chave} ultrapassaria o limite de {limite} itens. "
                "Remova itens ou importe os recursos em outro projeto. Nenhum dado foi alterado."
            )

    for indice, aba in enumerate(importados.get("informacoes_abas") or [], start=1):
        if len(aba.get("paginas") or []) > MAX_PAGINAS_INFO_LATERAIS:
            raise ValueError(f"A aba de Informações {indice} excede o limite de {MAX_PAGINAS_INFO_LATERAIS} páginas.")
    return {"informacoes": reutilizar_info, "fluxo": reutilizar_fluxo, **reutilizar_catalogo}


@registrar_etapa
def mesclar_recursos_importados(pasta_projeto: Path, recursos_importados: dict[str, Any]) -> dict[str, Any]:
    """Adiciona recursos .gutr sem apagar dados e sem descartar itens silenciosamente."""
    atuais = ler_recursos_projeto(pasta_projeto)
    importados = normalizar_recursos(recursos_importados)
    agora = agora_iso()
    reuso = _validar_capacidade_mesclagem(atuais, importados)

    planejamento_atual = atuais.get("planejamento") or {}
    abas_info = list(atuais.get("informacoes_abas") or [])
    reutilizar_info = reuso["informacoes"]
    if reutilizar_info:
        aba_vazia = abas_info.pop(0)
        titulos_info = {str(aba.get("titulo") or "").casefold() for aba in abas_info}
    else:
        aba_vazia = None
        titulos_info = {str(aba.get("titulo") or "").casefold() for aba in abas_info}
    mapa_paginas_info: dict[str, str] = {}
    for indice, aba in enumerate(importados.get("informacoes_abas", [])):
        paginas_importadas: list[dict[str, Any]] = []
        for pagina_indice, pagina in enumerate(aba.get("paginas") or []):
            novo_id_pagina = _novo_id("info")
            if reutilizar_info and indice == 0 and pagina_indice == 0 and aba_vazia:
                novo_id_pagina = str(aba_vazia["paginas"][0]["id"])
            if pagina.get("id"):
                mapa_paginas_info[str(pagina["id"])] = novo_id_pagina
            paginas_importadas.append({
                "id": novo_id_pagina,
                "titulo": _texto(pagina.get("titulo"), MAX_TITULO_PAGINA) or t("resources.untitled", default="Sem título"),
                "html": _html(pagina.get("html")),
                "data_criacao": _texto(pagina.get("data_criacao"), 40) or agora,
                "data_atualizacao": _texto(pagina.get("data_atualizacao"), 40) or agora,
            })
        id_aba = str(aba_vazia["id"]) if reutilizar_info and indice == 0 and aba_vazia else _novo_id("info_tab")
        abas_info.append({
            "id": id_aba,
            "titulo": _titulo_aba_importada_unico(_texto(aba.get("titulo"), MAX_TITULO_ABA) or _titulo_padrao_aba("informacoes"), titulos_info),
            "paginas": _normalizar_paginas(paginas_importadas),
            "data_criacao": _texto(aba.get("data_criacao"), 40) or agora,
            "data_atualizacao": _texto(aba.get("data_atualizacao"), 40) or agora,
        })
    atuais["informacoes_abas"] = _normalizar_abas_informacoes(abas_info)
    atuais["informacoes"] = _informacoes_planas(atuais["informacoes_abas"])

    fluxos = list(atuais.get("fluxos") or [])
    reutilizar_fluxo = reuso["fluxo"]
    fluxo_vazio = fluxos.pop(0) if reutilizar_fluxo else None
    titulos_fluxo = {str(item.get("titulo") or "").casefold() for item in fluxos}
    mapa_nos_fluxo: dict[str, str] = {}
    for indice, fluxo in enumerate(importados.get("fluxos", [])):
        fluxo_norm = _normalizar_fluxo(fluxo)
        tem_fluxo_atual = any((item.get("nodes") or []) for item in fluxos)
        deslocamento = 80 if tem_fluxo_atual else 0
        id_map: dict[str, str] = {}
        nodes: list[dict[str, Any]] = []
        for node in fluxo_norm.get("nodes", []):
            antigo_id = _texto(node.get("id"), 80) or _novo_id("node")
            novo_id = _novo_id("node")
            id_map[antigo_id] = novo_id
            mapa_nos_fluxo[antigo_id] = novo_id
            nodes.append({
                "id": novo_id,
                "x": float(node.get("x", 120)) + deslocamento,
                "y": float(node.get("y", 120)) + deslocamento,
                "width": float(node.get("width", 240)),
                "height": float(node.get("height", 150)),
                "titulo": _texto(node.get("titulo"), 120) or t("resources.new_block", default="Novo bloco"),
                "texto": _texto(node.get("texto"), 4000),
            })
        edges: list[dict[str, Any]] = []
        for edge in fluxo_norm.get("edges", []):
            origem = id_map.get(_texto(edge.get("from"), 80))
            destino = id_map.get(_texto(edge.get("to"), 80))
            if not origem or not destino or origem == destino:
                continue
            edges.append({
                "id": _novo_id("edge"),
                "from": origem,
                "to": destino,
                "fromSide": _texto(edge.get("fromSide"), 10) or "right",
                "toSide": _texto(edge.get("toSide"), 10) or "left",
            })
        primeiro_reutilizado = reutilizar_fluxo and indice == 0 and fluxo_vazio
        fluxos.append({
            "id": str(fluxo_vazio["id"]) if primeiro_reutilizado else _novo_id("fluxo"),
            "titulo": _titulo_aba_importada_unico(_texto(fluxo.get("titulo"), MAX_TITULO_ABA) or _titulo_padrao_aba("fluxo"), titulos_fluxo),
            "nodes": nodes,
            "edges": edges,
            "data_criacao": _texto(fluxo.get("data_criacao"), 40) or agora,
            "data_atualizacao": _texto(fluxo.get("data_atualizacao"), 40) or agora,
        })
    atuais["fluxos"] = _normalizar_fluxos(fluxos)
    atuais["fluxo"] = _fluxo_principal(atuais["fluxos"])

    mapas_catalogo: dict[str, dict[str, str]] = {}
    for chave in ("personagens", "lugares", "anotacoes"):
        mapa_itens: dict[str, str] = {}
        paginas_atuais = list(atuais.get(f"{chave}_paginas") or [])
        reutilizar_pagina = reuso[chave]
        pagina_vazia = paginas_atuais.pop(0) if reutilizar_pagina else None
        usados_titulos = {str(pagina.get("titulo") or "").casefold() for pagina in paginas_atuais}
        mapa_paginas: dict[str, str] = {}
        for indice, pagina in enumerate(importados.get(f"{chave}_paginas", [])):
            id_novo = str(pagina_vazia["id"]) if reutilizar_pagina and indice == 0 and pagina_vazia else _novo_id(chave)
            mapa_paginas[str(pagina.get("id") or "")] = id_novo
            paginas_atuais.append({
                "id": id_novo,
                "titulo": _titulo_aba_importada_unico(_texto(pagina.get("titulo"), MAX_TITULO_ABA) or _titulo_padrao_aba(chave), usados_titulos),
                "data_criacao": _texto(pagina.get("data_criacao"), 40) or agora,
                "data_atualizacao": _texto(pagina.get("data_atualizacao"), 40) or agora,
            })
        paginas_atuais = _normalizar_abas(paginas_atuais, chave)
        existentes = list(atuais.get(chave) or [])
        nomes_usados = {
            (str(item.get("pagina_id") or paginas_atuais[0]["id"]), str(item.get("nome") or "").casefold())
            for item in existentes if str(item.get("nome") or "").strip()
        }
        for item in importados.get(chave, []):
            nome = _texto(item.get("nome"), MAX_NOME_CATALOGO)
            if not nome:
                continue
            pagina_importada = str(item.get("pagina_id") or "")
            pagina_final = mapa_paginas.get(pagina_importada)
            if not pagina_final:
                raise ValueError(
                    f"O item '{nome}' do catálogo {chave} aponta para uma aba inexistente no arquivo .gutr. "
                    "Nenhum dado foi alterado."
                )
            nome_final = _nome_catalogo_importado_unico(nome, nomes_usados, pagina_final)
            novo_id_item = _novo_id("cat")
            if item.get("id"):
                mapa_itens[str(item["id"])] = novo_id_item
            existentes.append({
                "id": novo_id_item,
                "pagina_id": pagina_final,
                "nome": nome_final,
                "descricao": _texto(item.get("descricao"), MAX_DESCRICAO_CATALOGO),
                "imagem": "" if chave == "anotacoes" else _imagem(item.get("imagem")),
                "imagem_necessita_reenvio": bool(item.get("imagem_necessita_reenvio")),
                "origem": "projeto",
                "data_criacao": _texto(item.get("data_criacao"), 40) or agora,
                "data_atualizacao": _texto(item.get("data_atualizacao"), 40) or agora,
            })
        atuais[f"{chave}_paginas"] = paginas_atuais
        atuais[chave] = _normalizar_catalogo_com_paginas(chave, existentes, paginas_atuais)
        mapas_catalogo[chave] = mapa_itens

    mapas_catalogo["paginas_info"] = mapa_paginas_info
    mapas_catalogo["nos_fluxo"] = mapa_nos_fluxo
    atuais["ocultos"] = _normalizar_ocultos(atuais.get("ocultos"))
    ocultos_importados = _normalizar_ocultos(importados.get("ocultos"))
    for chave in ("personagens", "lugares", "anotacoes"):
        existentes = {nome.casefold() for nome in atuais["ocultos"][chave]}
        for nome in ocultos_importados[chave]:
            if nome.casefold() not in existentes:
                atuais["ocultos"][chave].append(nome)
                existentes.add(nome.casefold())

    atuais["planejamento"] = importar_planejamento(atuais.get("planejamento"), importados.get("planejamento"), mapas_catalogo)
    atuais["data_atualizacao"] = agora
    return salvar_recursos_projeto(pasta_projeto, atuais)


@registrar_etapa
def _catalogo_herdado_de_roteiros(roteiros: list[dict[str, Any]] | None, chave_roteiro: str, tipo: str) -> list[dict[str, Any]]:
    itens: dict[str, dict[str, Any]] = {}
    for roteiro in roteiros or []:
        titulo_roteiro = _texto(roteiro.get("titulo"), 120) or f"Roteiro {roteiro.get('id', '')}".strip()
        for item in roteiro.get(chave_roteiro) or []:
            if isinstance(item, dict):
                nome = _texto(item.get("nome") or item.get("titulo") or item.get("name") or item.get("title"), MAX_NOME_CATALOGO)
                descricao = _texto(item.get("descricao") or item.get("description"), MAX_DESCRICAO_CATALOGO)
            else:
                nome = _texto(item, MAX_NOME_CATALOGO)
                descricao = ""
            if not nome:
                continue
            key = nome.casefold()
            if key not in itens:
                itens[key] = {
                    "id": f"roteiro_{tipo}_{sha1(key.encode('utf-8')).hexdigest()[:12]}",
                    "nome": nome,
                    "descricao": descricao,
                    "imagem": "",
                    "origem": "roteiro",
                    "somente_leitura": True,
                    "fontes": [titulo_roteiro],
                }
            else:
                if descricao and not itens[key].get("descricao"):
                    itens[key]["descricao"] = descricao
                fontes = itens[key].setdefault("fontes", [])
                if titulo_roteiro not in fontes:
                    fontes.append(titulo_roteiro)
    return list(itens.values())


@registrar_etapa
def mesclar_catalogo_com_roteiros(recursos: dict[str, Any], roteiros: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    dados = deepcopy(normalizar_recursos(recursos))
    ocultos_personagens = {str(x).casefold() for x in dados.get("ocultos", {}).get("personagens", [])}
    ocultos_lugares = {str(x).casefold() for x in dados.get("ocultos", {}).get("lugares", [])}
    ocultos_anotacoes = {str(x).casefold() for x in dados.get("ocultos", {}).get("anotacoes", [])}

    def mesclar(local: list[dict[str, Any]], herdado: list[dict[str, Any]], ocultos: set[str], pagina_padrao: str) -> list[dict[str, Any]]:
        resultado: dict[tuple[str, str], dict[str, Any]] = {}
        for item in herdado:
            nome = str(item.get("nome") or "").strip()
            if not nome or nome.casefold() in ocultos:
                continue
            herdado_item = deepcopy(item)
            herdado_item["pagina_id"] = pagina_padrao
            resultado[(pagina_padrao, nome.casefold())] = herdado_item
        for item in local:
            nome = str(item.get("nome") or "").strip()
            if not nome or nome.casefold() in ocultos:
                continue
            local_item = deepcopy(item)
            local_item["origem"] = "projeto"
            local_item["somente_leitura"] = False
            pagina_id = str(local_item.get("pagina_id") or pagina_padrao)
            local_item["pagina_id"] = pagina_id
            resultado[(pagina_id, nome.casefold())] = local_item
        ordem = {p["id"]: i for i, p in enumerate(dados.get("personagens_paginas", []) + dados.get("lugares_paginas", []) + dados.get("anotacoes_paginas", []))}
        return sorted(resultado.values(), key=lambda x: (ordem.get(str(x.get("pagina_id") or ""), 999), str(x.get("nome") or "").casefold()))

    personagens_roteiro = _catalogo_herdado_de_roteiros(roteiros, "catalogo_personagens", "personagem")
    lugares_roteiro = _catalogo_herdado_de_roteiros(roteiros, "catalogo_locais", "lugar")
    dados["personagens_combinados"] = mesclar(dados.get("personagens", []), personagens_roteiro, ocultos_personagens, dados["personagens_paginas"][0]["id"])
    dados["lugares_combinados"] = mesclar(dados.get("lugares", []), lugares_roteiro, ocultos_lugares, dados["lugares_paginas"][0]["id"])
    dados["anotacoes_combinadas"] = mesclar(dados.get("anotacoes", []), [], ocultos_anotacoes, dados["anotacoes_paginas"][0]["id"])
    return dados
