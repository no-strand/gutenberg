"""Recursos de planejamento por projeto: informações, fluxo, personagens, lugares e anotações."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha1
from pathlib import Path
from typing import Any
from uuid import uuid4

from .persistencia_json import ler_json
from .persistencia_editor_db import BancoEditorLocal
from .utilidades import agora_iso
from .i18n import t
from .logging_config import obter_logger, registrar_etapa

logger = obter_logger(__name__)

ARQUIVO_RECURSOS_PROJETO = "recursos_projeto.json"
_DB_CACHE: dict[Path, BancoEditorLocal] = {}
MAX_HTML_INFO = 1_200_000
MAX_IMAGEM_DATA_URL = 900_000
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


@registrar_etapa
def _imagem(valor: Any) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""
    if not texto.startswith("data:image/"):
        return ""
    return texto[:MAX_IMAGEM_DATA_URL]


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
        "html": t("resources.default_page_html", default="<h2>Ideias do projeto</h2><p>Escreva aqui resumos, regras do mundo, cenas soltas e referências.</p>"),
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
        "versao": 3,
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
        normalizados.append({
            "id": _texto(item.get("id"), 80) or _novo_id("cat"),
            "pagina_id": pagina_id,
            "nome": nome,
            "descricao": _texto(item.get("descricao") or item.get("anotacao") or item.get("texto") or item.get("description") or item.get("text"), MAX_DESCRICAO_CATALOGO),
            "imagem": _imagem(item.get("imagem") or item.get("image")) if permitir_imagem else "",
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
        "versao": 3,
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
    novo = {
        "id": item_id or _novo_id("cat"),
        "pagina_id": pagina_id,
        "nome": nome,
        "descricao": _texto(item.get("descricao"), MAX_DESCRICAO_CATALOGO),
        "imagem": "" if chave == "anotacoes" else _imagem(item.get("imagem")),
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


@registrar_etapa
def mesclar_recursos_importados(pasta_projeto: Path, recursos_importados: dict[str, Any]) -> dict[str, Any]:
    """Adiciona ao projeto atual os recursos vindos de um pacote .gutr sem apagar o que já existe."""
    atuais = ler_recursos_projeto(pasta_projeto)
    importados = normalizar_recursos(recursos_importados)
    agora = agora_iso()

    abas_info = list(atuais.get("informacoes_abas") or [])
    titulos_info = {str(aba.get("titulo") or "").casefold() for aba in abas_info}
    for aba in importados.get("informacoes_abas", []):
        if len(abas_info) >= MAX_ABAS_RECURSOS or not isinstance(aba, dict):
            continue
        paginas_importadas: list[dict[str, Any]] = []
        for pagina in aba.get("paginas") or []:
            if not isinstance(pagina, dict):
                continue
            paginas_importadas.append({
                "id": _novo_id("info"),
                "titulo": _texto(pagina.get("titulo"), MAX_TITULO_PAGINA) or t("resources.untitled", default="Sem título"),
                "html": _html(pagina.get("html")),
                "data_criacao": _texto(pagina.get("data_criacao"), 40) or agora,
                "data_atualizacao": agora,
            })
        abas_info.append({
            "id": _novo_id("info_tab"),
            "titulo": _titulo_aba_importada_unico(_texto(aba.get("titulo"), MAX_TITULO_ABA) or _titulo_padrao_aba("informacoes"), titulos_info),
            "paginas": _normalizar_paginas(paginas_importadas),
            "data_criacao": _texto(aba.get("data_criacao"), 40) or agora,
            "data_atualizacao": agora,
        })
    atuais["informacoes_abas"] = _normalizar_abas_informacoes(abas_info)
    atuais["informacoes"] = _informacoes_planas(atuais["informacoes_abas"])

    fluxos = list(atuais.get("fluxos") or [])
    titulos_fluxo = {str(p.get("titulo") or "").casefold() for p in fluxos}
    for fluxo in importados.get("fluxos", []):
        if len(fluxos) >= MAX_ABAS_RECURSOS or not isinstance(fluxo, dict):
            continue
        fluxo_norm = _normalizar_fluxo(fluxo)
        tem_fluxo_atual = any((f.get("nodes") or []) for f in fluxos)
        deslocamento = 80 if tem_fluxo_atual else 0
        id_map: dict[str, str] = {}
        nodes: list[dict[str, Any]] = []
        for node in fluxo_norm.get("nodes", []):
            antigo_id = _texto(node.get("id"), 80) or _novo_id("node")
            novo_id = _novo_id("node")
            id_map[antigo_id] = novo_id
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
        fluxos.append({
            "id": _novo_id("fluxo"),
            "titulo": _titulo_aba_importada_unico(_texto(fluxo.get("titulo"), MAX_TITULO_ABA) or _titulo_padrao_aba("fluxo"), titulos_fluxo),
            "nodes": nodes,
            "edges": edges,
            "data_criacao": _texto(fluxo.get("data_criacao"), 40) or agora,
            "data_atualizacao": agora,
        })
    atuais["fluxos"] = _normalizar_fluxos(fluxos)
    atuais["fluxo"] = _fluxo_principal(atuais["fluxos"])

    for chave in ("personagens", "lugares", "anotacoes"):
        paginas_atuais = list(atuais.get(f"{chave}_paginas") or [])
        usados_titulos = {str(p.get("titulo") or "").casefold() for p in paginas_atuais}
        mapa_paginas: dict[str, str] = {}
        for pagina in importados.get(f"{chave}_paginas", []):
            if not isinstance(pagina, dict):
                continue
            if len(paginas_atuais) >= MAX_ABAS_RECURSOS:
                mapa_paginas[str(pagina.get("id") or "")] = paginas_atuais[0]["id"]
                continue
            novo_id = _novo_id(chave)
            mapa_paginas[str(pagina.get("id") or "")] = novo_id
            paginas_atuais.append({
                "id": novo_id,
                "titulo": _titulo_aba_importada_unico(_texto(pagina.get("titulo"), MAX_TITULO_ABA) or _titulo_padrao_aba(chave), usados_titulos),
                "data_criacao": _texto(pagina.get("data_criacao"), 40) or agora,
                "data_atualizacao": agora,
            })
        paginas_atuais = _normalizar_abas(paginas_atuais, chave)
        existentes = list(atuais.get(chave) or [])
        nomes_usados = {(str(item.get("pagina_id") or paginas_atuais[0]["id"]), str(item.get("nome") or "").casefold()) for item in existentes if str(item.get("nome") or "").strip()}
        for item in importados.get(chave, []):
            if not isinstance(item, dict):
                continue
            nome = _texto(item.get("nome"), MAX_NOME_CATALOGO)
            if not nome:
                continue
            pagina_importada = str(item.get("pagina_id") or "")
            pagina_final = mapa_paginas.get(pagina_importada) or paginas_atuais[0]["id"]
            nome_final = _nome_catalogo_importado_unico(nome, nomes_usados, pagina_final)
            existentes.append({
                "id": _novo_id("cat"),
                "pagina_id": pagina_final,
                "nome": nome_final,
                "descricao": _texto(item.get("descricao"), MAX_DESCRICAO_CATALOGO),
                "imagem": "" if chave == "anotacoes" else _imagem(item.get("imagem")),
                "origem": "projeto",
                "data_criacao": _texto(item.get("data_criacao"), 40) or agora,
                "data_atualizacao": agora,
            })
        atuais[f"{chave}_paginas"] = paginas_atuais
        atuais[chave] = _normalizar_catalogo_com_paginas(chave, existentes, paginas_atuais)

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
