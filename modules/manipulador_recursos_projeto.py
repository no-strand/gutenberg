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
MAX_NOME_CATALOGO = 80
MAX_DESCRICAO_CATALOGO = 4000


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
def estrutura_padrao_recursos() -> dict[str, Any]:
    agora = agora_iso()
    return {
        "versao": 1,
        "informacoes": [
            {
                "id": _novo_id("info"),
                "titulo": t("resources.default_page_title", default="Página inicial"),
                "html": t("resources.default_page_html", default="<h2>Ideias do projeto</h2><p>Escreva aqui resumos, regras do mundo, cenas soltas e referências.</p>"),
                "data_criacao": agora,
                "data_atualizacao": agora,
            }
        ],
        "fluxo": {
            "nodes": [],
            "edges": [],
        },
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
    for item in paginas:
        if not isinstance(item, dict):
            continue
        pid = _texto(item.get("id"), 80) or _novo_id("info")
        titulo = _texto(item.get("titulo"), MAX_TITULO_PAGINA) or t("resources.untitled", default="Sem título")
        normalizadas.append({
            "id": pid,
            "titulo": titulo,
            "html": _html(item.get("html")),
            "data_criacao": _texto(item.get("data_criacao"), 40) or agora_iso(),
            "data_atualizacao": _texto(item.get("data_atualizacao"), 40) or agora_iso(),
        })
    if not normalizadas:
        normalizadas = estrutura_padrao_recursos()["informacoes"]
    return normalizadas[:80]


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
            w = max(170, min(520, float(item.get("width", 240))))
            h = max(96, min(420, float(item.get("height", 150))))
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
        edges.append({
            "id": _texto(item.get("id"), 80) or _novo_id("edge"),
            "from": origem,
            "to": destino,
            "fromSide": _texto(item.get("fromSide"), 10) if _texto(item.get("fromSide"), 10) in lados else "right",
            "toSide": _texto(item.get("toSide"), 10) if _texto(item.get("toSide"), 10) in lados else "left",
        })
    return {"nodes": nodes[:240], "edges": edges[:500]}


@registrar_etapa
def _normalizar_catalogo(valor: Any, *, permitir_imagem: bool = True) -> list[dict[str, Any]]:
    itens = valor if isinstance(valor, list) else []
    normalizados: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for item in itens:
        if not isinstance(item, dict):
            continue
        nome = _texto(item.get("nome") or item.get("titulo") or item.get("name") or item.get("title"), MAX_NOME_CATALOGO)
        if not nome:
            continue
        chave = nome.casefold()
        if chave in vistos:
            continue
        vistos.add(chave)
        normalizados.append({
            "id": _texto(item.get("id"), 80) or _novo_id("cat"),
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
def normalizar_recursos(dados: Any) -> dict[str, Any]:
    base = estrutura_padrao_recursos()
    if not isinstance(dados, dict):
        return base
    # Compatibilidade com rascunhos que usavam "locais" em vez de "lugares".
    lugares = dados.get("lugares") if "lugares" in dados else dados.get("locais")
    normalizados = {
        "versao": 1,
        "informacoes": _normalizar_paginas(dados.get("informacoes")),
        "fluxo": _normalizar_fluxo(dados.get("fluxo")),
        "personagens": _normalizar_catalogo(dados.get("personagens")),
        "lugares": _normalizar_catalogo(lugares),
        "anotacoes": _normalizar_catalogo(dados.get("anotacoes") or dados.get("notas") or dados.get("notes"), permitir_imagem=False),
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
def salvar_informacoes_projeto(pasta_projeto: Path, informacoes: Any) -> dict[str, Any]:
    dados = ler_recursos_projeto(pasta_projeto)
    dados["informacoes"] = _normalizar_paginas(informacoes)
    return salvar_recursos_projeto(pasta_projeto, dados)


@registrar_etapa
def salvar_fluxo_projeto(pasta_projeto: Path, fluxo: Any) -> dict[str, Any]:
    dados = ler_recursos_projeto(pasta_projeto)
    dados["fluxo"] = _normalizar_fluxo(fluxo)
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
def salvar_item_catalogo_projeto(pasta_projeto: Path, tipo: str, item: dict[str, Any]) -> dict[str, Any]:
    chave = _chave_tipo_catalogo(tipo)
    dados = ler_recursos_projeto(pasta_projeto)
    nome = _texto(item.get("nome"), MAX_NOME_CATALOGO)
    if not nome:
        raise ValueError(t("resources.name_required", default="Informe um nome."))
    item_id = _texto(item.get("id"), 80)
    agora = agora_iso()
    novo = {
        "id": item_id or _novo_id("cat"),
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
        mesmo_nome = str(existente.get("nome") or "").casefold() == nome.casefold()
        if mesmo_id or mesmo_nome:
            novo["id"] = existente.get("id") or novo["id"]
            novo["data_criacao"] = existente.get("data_criacao") or novo["data_criacao"]
            atualizados.append(novo)
            aplicado = True
        else:
            atualizados.append(existente)
    if not aplicado:
        atualizados.append(novo)
    # Caso estivesse oculto por ter sido excluído antes, reexibir ao salvar.
    dados.setdefault("ocultos", {"personagens": [], "lugares": [], "anotacoes": []})
    dados["ocultos"].setdefault(chave, [])
    dados["ocultos"][chave] = [n for n in dados["ocultos"].get(chave, []) if n.casefold() != nome.casefold()]
    dados[chave] = _normalizar_catalogo(atualizados)
    return salvar_recursos_projeto(pasta_projeto, dados)


@registrar_etapa
def excluir_item_catalogo_projeto(pasta_projeto: Path, tipo: str, identificador: str | None = None, nome: str | None = None) -> dict[str, Any]:
    chave = _chave_tipo_catalogo(tipo)
    dados = ler_recursos_projeto(pasta_projeto)
    identificador = _texto(identificador, 80)
    nome_limpo = _texto(nome, MAX_NOME_CATALOGO)
    removidos: list[str] = []
    restantes: list[dict[str, Any]] = []
    for item in dados.get(chave, []):
        mesmo_id = identificador and item.get("id") == identificador
        mesmo_nome = nome_limpo and str(item.get("nome") or "").casefold() == nome_limpo.casefold()
        if mesmo_id or mesmo_nome:
            removidos.append(str(item.get("nome") or nome_limpo).strip())
        else:
            restantes.append(item)
    if nome_limpo and nome_limpo not in removidos:
        removidos.append(nome_limpo)
    ocultos = dados.setdefault("ocultos", {"personagens": [], "lugares": [], "anotacoes": []}).setdefault(chave, [])
    ocultos_case = {str(x).casefold() for x in ocultos}
    for nome_removido in removidos:
        key = nome_removido.casefold()
        if nome_removido and key not in ocultos_case:
            ocultos.append(nome_removido)
            ocultos_case.add(key)
    dados[chave] = _normalizar_catalogo(restantes)
    return salvar_recursos_projeto(pasta_projeto, dados)


@registrar_etapa
def _nome_catalogo_importado_unico(nome: str, usados: set[str]) -> str:
    base = _texto(nome, MAX_NOME_CATALOGO) or t("resources.untitled", default="Sem título")
    if base.casefold() not in usados:
        usados.add(base.casefold())
        return base
    candidato = _texto(f"{base} (importado)", MAX_NOME_CATALOGO)
    if candidato.casefold() not in usados:
        usados.add(candidato.casefold())
        return candidato
    for indice in range(2, 1000):
        sufixo = f" (importado {indice})"
        limite_base = max(1, MAX_NOME_CATALOGO - len(sufixo))
        candidato = f"{base[:limite_base].rstrip()}{sufixo}"
        if candidato.casefold() not in usados:
            usados.add(candidato.casefold())
            return candidato
    usado = _novo_id("cat")[:MAX_NOME_CATALOGO]
    usados.add(usado.casefold())
    return usado


@registrar_etapa
def mesclar_recursos_importados(pasta_projeto: Path, recursos_importados: dict[str, Any]) -> dict[str, Any]:
    """Adiciona ao projeto atual os recursos vindos de um pacote .gutr sem apagar o que já existe."""
    atuais = ler_recursos_projeto(pasta_projeto)
    importados = normalizar_recursos(recursos_importados)
    agora = agora_iso()

    paginas = list(atuais.get("informacoes") or [])
    for pagina in importados.get("informacoes", []):
        if not isinstance(pagina, dict):
            continue
        paginas.append({
            "id": _novo_id("info"),
            "titulo": _texto(pagina.get("titulo"), MAX_TITULO_PAGINA) or t("resources.untitled", default="Sem título"),
            "html": _html(pagina.get("html")),
            "data_criacao": _texto(pagina.get("data_criacao"), 40) or agora,
            "data_atualizacao": agora,
        })
    atuais["informacoes"] = _normalizar_paginas(paginas)

    fluxo_atual = _normalizar_fluxo(atuais.get("fluxo"))
    fluxo_importado = _normalizar_fluxo(importados.get("fluxo"))
    id_map: dict[str, str] = {}
    tem_fluxo_atual = bool(fluxo_atual.get("nodes"))
    deslocamento = 80 if tem_fluxo_atual else 0
    nodes_mesclados = list(fluxo_atual.get("nodes") or [])
    for node in fluxo_importado.get("nodes", []):
        antigo_id = _texto(node.get("id"), 80) or _novo_id("node")
        novo_id = _novo_id("node")
        id_map[antigo_id] = novo_id
        nodes_mesclados.append({
            "id": novo_id,
            "x": float(node.get("x", 120)) + deslocamento,
            "y": float(node.get("y", 120)) + deslocamento,
            "width": float(node.get("width", 240)),
            "height": float(node.get("height", 150)),
            "titulo": _texto(node.get("titulo"), 120) or t("resources.new_block", default="Novo bloco"),
            "texto": _texto(node.get("texto"), 4000),
        })
    edges_mescladas = list(fluxo_atual.get("edges") or [])
    for edge in fluxo_importado.get("edges", []):
        origem = id_map.get(_texto(edge.get("from"), 80))
        destino = id_map.get(_texto(edge.get("to"), 80))
        if not origem or not destino or origem == destino:
            continue
        edges_mescladas.append({
            "id": _novo_id("edge"),
            "from": origem,
            "to": destino,
            "fromSide": _texto(edge.get("fromSide"), 10) or "right",
            "toSide": _texto(edge.get("toSide"), 10) or "left",
        })
    atuais["fluxo"] = _normalizar_fluxo({"nodes": nodes_mesclados, "edges": edges_mescladas})

    for chave in ("personagens", "lugares", "anotacoes"):
        existentes = list(atuais.get(chave) or [])
        nomes_usados = {str(item.get("nome") or "").casefold() for item in existentes if str(item.get("nome") or "").strip()}
        for item in importados.get(chave, []):
            if not isinstance(item, dict):
                continue
            nome = _texto(item.get("nome"), MAX_NOME_CATALOGO)
            if not nome:
                continue
            nome_final = _nome_catalogo_importado_unico(nome, nomes_usados)
            existentes.append({
                "id": _novo_id("cat"),
                "nome": nome_final,
                "descricao": _texto(item.get("descricao"), MAX_DESCRICAO_CATALOGO),
                "imagem": "" if chave == "anotacoes" else _imagem(item.get("imagem")),
                "origem": "projeto",
                "data_criacao": _texto(item.get("data_criacao"), 40) or agora,
                "data_atualizacao": agora,
            })
        atuais[chave] = _normalizar_catalogo(existentes, permitir_imagem=(chave != "anotacoes"))

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

    def mesclar(local: list[dict[str, Any]], herdado: list[dict[str, Any]], ocultos: set[str]) -> list[dict[str, Any]]:
        resultado: dict[str, dict[str, Any]] = {}
        for item in herdado:
            nome = str(item.get("nome") or "").strip()
            if not nome or nome.casefold() in ocultos:
                continue
            resultado[nome.casefold()] = item
        for item in local:
            nome = str(item.get("nome") or "").strip()
            if not nome or nome.casefold() in ocultos:
                continue
            local_item = deepcopy(item)
            local_item["origem"] = "projeto"
            local_item["somente_leitura"] = False
            resultado[nome.casefold()] = local_item
        return sorted(resultado.values(), key=lambda x: str(x.get("nome") or "").casefold())

    personagens_roteiro = _catalogo_herdado_de_roteiros(roteiros, "catalogo_personagens", "personagem")
    lugares_roteiro = _catalogo_herdado_de_roteiros(roteiros, "catalogo_locais", "lugar")
    dados["personagens_combinados"] = mesclar(dados.get("personagens", []), personagens_roteiro, ocultos_personagens)
    dados["lugares_combinados"] = mesclar(dados.get("lugares", []), lugares_roteiro, ocultos_lugares)
    dados["anotacoes_combinadas"] = mesclar(dados.get("anotacoes", []), [], ocultos_anotacoes)
    return dados
