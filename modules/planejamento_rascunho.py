"""Cenas e fontes de pesquisa do Rascunho, sem alterar os documentos editados.

Os registros vivem no mesmo payload versionado dos recursos do projeto. IDs e
vínculos são estáveis, inclusive em atualizações e reordenações.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from .utilidades import agora_iso

MAX_CENAS = 300
MAX_FONTES = 300
STATUS_CENAS = frozenset({"planejada", "em_andamento", "revisao", "concluida"})
TIPOS_FONTES = frozenset({"pagina_web", "livro", "artigo", "entrevista", "arquivo", "outro"})
ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")


def _texto(value: Any, size: int) -> str:
    return str(value if value is not None else "").replace("\x00", "").strip()[:size]


def _id(value: Any) -> str:
    result = _texto(value, 80)
    return result if ID_PATTERN.fullmatch(result) else ""


def _ids(value: Any, max_items: int = 100) -> list[str]:
    result: list[str] = []
    if not isinstance(value, list):
        return result
    for item in value:
        identifier = _id(item)
        if identifier and identifier not in result:
            result.append(identifier)
        if len(result) >= max_items:
            break
    return result


def _url(value: Any) -> str:
    url = _texto(value, 2000)
    if not url:
        return ""
    # Não armazenar URL com esquemas executáveis ou credenciais.
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
            return ""
        if any(c.isspace() for c in parsed.netloc) or parsed.port is not None and not (1 <= parsed.port <= 65535):
            return ""
        if any(ord(c) < 32 for c in url):
            return ""
    except ValueError:
        return ""
    return url


def _normalizar_cena(item: dict[str, Any]) -> dict[str, Any]:
    status = _texto(item.get("status"), 30)
    return {
        "id": _id(item.get("id")) or f"cena_{uuid4().hex[:16]}",
        "titulo": _texto(item.get("titulo"), 120),
        "resumo": _texto(item.get("resumo"), 6000),
        "objetivo": _texto(item.get("objetivo"), 2000),
        "conflito": _texto(item.get("conflito"), 2000),
        "desfecho": _texto(item.get("desfecho"), 2000),
        "status": status if status in STATUS_CENAS else "planejada",
        "personagens": _ids(item.get("personagens")),
        "lugares": _ids(item.get("lugares")),
        "anotacoes": _ids(item.get("anotacoes")),
        "referencias": _ids(item.get("referencias")),
        "paginas_info": _ids(item.get("paginas_info")),
        "nos_fluxo": _ids(item.get("nos_fluxo")),
        "data_criacao": _texto(item.get("data_criacao"), 40) or agora_iso(),
        "data_atualizacao": _texto(item.get("data_atualizacao"), 40) or agora_iso(),
    }


def _normalizar_fonte(item: dict[str, Any]) -> dict[str, Any]:
    tipo = _texto(item.get("tipo"), 30)
    return {
        "id": _id(item.get("id")) or f"fonte_{uuid4().hex[:16]}",
        "titulo": _texto(item.get("titulo"), 160),
        "tipo": tipo if tipo in TIPOS_FONTES else "outro",
        "autor": _texto(item.get("autor"), 160),
        "url": _url(item.get("url")),
        "citacao": _texto(item.get("citacao"), 2000),
        "notas": _texto(item.get("notas"), 6000),
        "verificada": item.get("verificada") is True or item.get("verificada") == 1,
        "data_criacao": _texto(item.get("data_criacao"), 40) or agora_iso(),
        "data_atualizacao": _texto(item.get("data_atualizacao"), 40) or agora_iso(),
    }


def normalizar_planejamento(value: Any) -> dict[str, Any]:
    data = value if isinstance(value, dict) else {}
    def uniq(items: Any, normalizer, limit: int) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            new_item = normalizer(item)
            if not new_item["titulo"] or new_item["id"] in seen:
                continue
            result.append(new_item)
            seen.add(new_item["id"])
            if len(result) >= limit:
                break
        return result

    fontes = uniq(data.get("fontes"), _normalizar_fonte, MAX_FONTES)
    cenas = uniq(data.get("cenas"), _normalizar_cena, MAX_CENAS)
    # Referências para fontes inexistentes são descartadas; personagens e locais
    # podem ser herdados de roteiros e não constam no payload local.
    fontes_ids = {item["id"] for item in fontes}
    for cena in cenas:
        cena["referencias"] = [ref for ref in cena["referencias"] if ref in fontes_ids]
    return {"cenas": cenas, "fontes": fontes}


def alterar_planejamento(recursos: dict[str, Any], tipo: str, operacao: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Aplica uma alteração isolada com rejeição de IDs inválidos e limites.

    O salvamento atômico no SQLite é realizado pelo chamador após a alteração.
    """
    if tipo not in {"cenas", "fontes"}:
        raise ValueError("Tipo de planejamento inválido.")
    if operacao not in {"salvar", "excluir", "ordenar"}:
        raise ValueError("Operação de planejamento inválida.")
    plan = normalizar_planejamento(recursos.get("planejamento"))
    itens = plan[tipo]
    if operacao == "ordenar":
        if tipo != "cenas":
            raise ValueError("Somente cenas podem ser reordenadas.")
        ordem = payload.get("ordem")
        ids = [item["id"] for item in itens]
        if not isinstance(ordem, list) or len(ordem) != len(ids) or len(set(ordem)) != len(ids) or set(ordem) != set(ids):
            raise ValueError("Ordem de cenas inválida ou desatualizada.")
        lookup = {item["id"]: item for item in itens}
        plan[tipo] = [lookup[identificador] for identificador in ordem]
    elif operacao == "excluir":
        identificador = _id(payload.get("id"))
        if not identificador or not any(item["id"] == identificador for item in itens):
            raise ValueError("Item não encontrado.")
        plan[tipo] = [item for item in itens if item["id"] != identificador]
        if tipo == "fontes":
            for cena in plan["cenas"]:
                cena["referencias"] = [ref for ref in cena["referencias"] if ref != identificador]
    else:
        raw_id = payload.get("id")
        identificador = _id(raw_id)
        if raw_id and not identificador:
            raise ValueError("Identificador inválido.")
        anterior = next((item for item in itens if item["id"] == identificador), None) if identificador else None
        if identificador and not anterior:
            raise ValueError("Item não encontrado; atualize a página.")
        if not anterior and len(itens) >= (MAX_CENAS if tipo == "cenas" else MAX_FONTES):
            raise ValueError("Limite de itens do planejamento atingido.")
        if not _texto(payload.get("titulo"), 160):
            raise ValueError("Informe um título.")
        if tipo == "fontes" and _texto(payload.get("url"), 2000) and not _url(payload.get("url")):
            raise ValueError("Utilize um endereço HTTP ou HTTPS válido, sem credenciais.")
        payload = {**payload, "id": identificador or f"{'cena' if tipo == 'cenas' else 'fonte'}_{uuid4().hex[:16]}",
                   "data_criacao": anterior["data_criacao"] if anterior else agora_iso(),
                   "data_atualizacao": agora_iso()}
        if tipo == "cenas":
            novo = _normalizar_cena(payload)
            fontes_ids = {fonte["id"] for fonte in plan["fontes"]}
            novo["referencias"] = [ref for ref in novo["referencias"] if ref in fontes_ids]
        else:
            novo = _normalizar_fonte(payload)
        if anterior:
            plan[tipo] = [novo if item["id"] == identificador else item for item in itens]
        else:
            plan[tipo].append(novo)
    updated = deepcopy(recursos)
    updated["planejamento"] = normalizar_planejamento(plan)
    return updated


def importar_planejamento(atual: Any, importado: Any, mapas_catalogo: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Mescla .gutr regenerando IDs e mantendo os vínculos para itens importados."""
    result = normalizar_planejamento(atual)
    imported = normalizar_planejamento(importado)
    fonte_map: dict[str, str] = {}
    for fonte in imported["fontes"]:
        if len(result["fontes"]) >= MAX_FONTES:
            break
        new_id = f"fonte_{uuid4().hex[:16]}"
        fonte_map[fonte["id"]] = new_id
        result["fontes"].append({**fonte, "id": new_id})
    for cena in imported["cenas"]:
        if len(result["cenas"]) >= MAX_CENAS:
            break
        new_cena = {**cena, "id": f"cena_{uuid4().hex[:16]}"}
        for key in ("personagens", "lugares", "anotacoes"):
            new_cena[key] = [mapas_catalogo.get(key, {}).get(ref, ref) for ref in cena[key]]
        # Páginas e nós que não foram importados (por limite de abas) não podem
        # apontar por acidente para itens diferentes com o mesmo identificador.
        for key in ("paginas_info", "nos_fluxo"):
            id_map = mapas_catalogo.get(key, {})
            new_cena[key] = [id_map[ref] for ref in cena[key] if ref in id_map]
        new_cena["referencias"] = [fonte_map[ref] for ref in cena["referencias"] if ref in fonte_map]
        result["cenas"].append(new_cena)
    return normalizar_planejamento(result)
