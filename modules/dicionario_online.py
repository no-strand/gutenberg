"""Consulta definições e traduções em provedores públicos usados pelos leitores."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from html import unescape
from threading import Lock, local
from time import monotonic
from typing import Any
import re
import unicodedata
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import requests


WIKTIONARY_INGLES_URL = "https://en.wiktionary.org/api/rest_v1/page/definition/{word}"
WIKCIONARIO_PORTUGUES_API_URL = "https://pt.wiktionary.org/w/api.php"
DICIONARIO_INGLES_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
DATAMUSE_INGLES_URL = "https://api.datamuse.com/words"
DICIONARIO_PORTUGUES_URL = "https://api.dicionario-aberto.net/word/{word}"
DICIONARIO_PORTUGUES_NEAR_URL = "https://api.dicionario-aberto.net/near/{word}"
TRADUCAO_URL = "https://api.mymemory.translated.net/get"
USER_AGENT = "Gutenberg/1.0.6 (dictionary lookup; local reader application)"
# O timeout curto é intencional: cada consulta possui fallback e não deve prender a UI.
TIMEOUT_HTTP = (1.8, 3.2)
TIMEOUT_TRADUCAO = (1.5, 2.6)
CACHE_TTL_SEGUNDOS = 6 * 60 * 60
CACHE_MAX_ITENS = 600


class ErroConsultaDicionario(RuntimeError):
    """Falha de comunicação ou resposta inválida de um provedor externo."""


@dataclass(frozen=True)
class _CacheItem:
    criado_em: float
    valor: dict[str, Any]


_cache: dict[tuple[str, str, str, str], _CacheItem] = {}
_cache_lock = Lock()
# Pool compartilhado para colocar provedores independentes em corrida. Assim, uma
# API lenta não bloqueia outra que já conseguiu encontrar a palavra.
_executor_provedores = ThreadPoolExecutor(max_workers=10, thread_name_prefix="gutenberg-dict")
_http_local = local()


def _sessao_http() -> requests.Session:
    """Mantém conexões HTTP reutilizáveis por thread (menos DNS/TLS por consulta)."""
    sessao = getattr(_http_local, "session", None)
    if sessao is None:
        sessao = requests.Session()
        adaptador = requests.adapters.HTTPAdapter(pool_connections=6, pool_maxsize=10, max_retries=0)
        sessao.mount("https://", adaptador)
        sessao.mount("http://", adaptador)
        sessao.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        _http_local.session = sessao
    return sessao


def _texto_limpo(valor: Any) -> str:
    texto = unicodedata.normalize("NFKC", unescape(str(valor or "")))
    texto = re.sub(r"\s+", " ", texto).strip()
    texto = re.sub(r"\[\[([^\]:]+)(?::\d+)?\]\]", r"\1", texto)
    return texto.replace("_", "").strip()


def _texto_html_limpo(valor: Any) -> str:
    """Converte pequenos fragmentos HTML retornados pelo Wiktionary em texto."""
    bruto = str(valor or "").strip()
    if not bruto:
        return ""
    try:
        texto = BeautifulSoup(bruto, "html.parser").get_text(" ", strip=True)
    except Exception:
        texto = re.sub(r"<[^>]+>", " ", bruto)
    return _texto_limpo(texto)


def normalizar_palavra_consulta(valor: Any) -> str:
    """Aceita uma única palavra Unicode, incluindo apóstrofo/hífen internos."""
    palavra = unicodedata.normalize("NFKC", str(valor or "")).strip()
    palavra = palavra.strip(" \t\r\n.,;:!?…()[]{}<>\"“”‘’«»—–")
    if not palavra or len(palavra) > 80:
        raise ValueError("Palavra inválida.")

    letra = r"[^\W\d_]"
    if not re.fullmatch(rf"{letra}+(?:['’\-]{letra}+)*", palavra, flags=re.UNICODE):
        raise ValueError("Selecione apenas uma palavra.")
    return palavra


def normalizar_idioma_consulta(valor: Any) -> str:
    idioma = str(valor or "pt_BR").strip().lower().replace("-", "_")
    return "en_US" if idioma in {"en", "en_us", "en_gb"} else "pt_BR"


def _get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    provedor: str = "serviço de dicionário",
    timeout: tuple[float, float] = TIMEOUT_HTTP,
) -> Any:
    try:
        resposta = _sessao_http().get(
            url,
            params=params,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise ErroConsultaDicionario(f"Não foi possível acessar {provedor}.") from exc

    if resposta.status_code == 404:
        return None
    if not resposta.ok:
        raise ErroConsultaDicionario(f"{provedor} respondeu com HTTP {resposta.status_code}.")
    try:
        return resposta.json()
    except ValueError as exc:
        raise ErroConsultaDicionario(f"{provedor} retornou uma resposta inválida.") from exc


def _adicionar_definicao(
    saida: list[dict[str, str]],
    vistos: set[str],
    texto: Any,
    *,
    classe: Any = "",
    exemplo: Any = "",
    limite: int = 6,
) -> None:
    definicao = _texto_limpo(texto)
    if not definicao:
        return
    chave = definicao.casefold()
    if chave in vistos or len(saida) >= limite:
        return
    vistos.add(chave)
    item = {"texto": definicao}
    classe_limpa = _texto_limpo(classe)
    exemplo_limpo = _texto_limpo(exemplo)
    if classe_limpa:
        item["classe"] = classe_limpa
    if exemplo_limpo:
        item["exemplo"] = exemplo_limpo
    saida.append(item)


def _parse_wiktionary_ingles(dados: Any) -> list[dict[str, str]]:
    """Extrai a seção inglesa do endpoint estruturado do Wiktionary."""
    if not isinstance(dados, dict):
        return []
    entradas = dados.get("en")
    if not isinstance(entradas, list):
        return []

    definicoes: list[dict[str, str]] = []
    vistos: set[str] = set()
    for entrada in entradas[:10]:
        if not isinstance(entrada, dict):
            continue
        classe = _texto_limpo(entrada.get("partOfSpeech"))
        for item in entrada.get("definitions") or []:
            if not isinstance(item, dict):
                continue
            definicao = _texto_html_limpo(item.get("definition"))
            exemplos = item.get("examples") or []
            exemplo = ""
            if isinstance(exemplos, list):
                for candidato in exemplos:
                    exemplo = _texto_html_limpo(candidato)
                    if exemplo:
                        break
            _adicionar_definicao(definicoes, vistos, definicao, classe=classe, exemplo=exemplo)
            if len(definicoes) >= 6:
                return definicoes
    return definicoes


def _parse_free_dictionary(dados: Any) -> tuple[list[dict[str, str]], str]:
    if not isinstance(dados, list):
        return [], ""

    definicoes: list[dict[str, str]] = []
    vistos: set[str] = set()
    fonetica = ""
    for entrada in dados[:4]:
        if not isinstance(entrada, dict):
            continue
        if not fonetica:
            fonetica = _texto_limpo(entrada.get("phonetic"))
            if not fonetica:
                for item_fon in entrada.get("phonetics") or []:
                    if isinstance(item_fon, dict) and _texto_limpo(item_fon.get("text")):
                        fonetica = _texto_limpo(item_fon.get("text"))
                        break
        for significado in entrada.get("meanings") or []:
            if not isinstance(significado, dict):
                continue
            classe = significado.get("partOfSpeech") or ""
            for item in significado.get("definitions") or []:
                if not isinstance(item, dict):
                    continue
                _adicionar_definicao(
                    definicoes,
                    vistos,
                    item.get("definition"),
                    classe=classe,
                    exemplo=item.get("example"),
                )
                if len(definicoes) >= 6:
                    return definicoes, fonetica
    return definicoes, fonetica


def _mesclar_definicoes(
    destino: list[dict[str, str]],
    novas: list[dict[str, str]],
    *,
    limite: int = 6,
) -> list[dict[str, str]]:
    """Mescla definições de provedores diferentes sem repetir o mesmo texto."""
    vistos = {_texto_limpo(item.get("texto")).casefold() for item in destino if item.get("texto")}
    for item in novas:
        texto = _texto_limpo(item.get("texto"))
        chave = texto.casefold()
        if not texto or chave in vistos:
            continue
        novo = {"texto": texto}
        classe = _texto_limpo(item.get("classe"))
        exemplo = _texto_limpo(item.get("exemplo"))
        if classe:
            novo["classe"] = classe
        if exemplo:
            novo["exemplo"] = exemplo
        destino.append(novo)
        vistos.add(chave)
        if len(destino) >= limite:
            break
    return destino


def _parse_datamuse_ingles(dados: Any) -> tuple[list[dict[str, str]], str]:
    """Usa as definições e o verbete-base calculados pelo próprio Datamuse.

    O Datamuse informa ``defHeadword`` quando a consulta é uma forma flexionada
    (por exemplo, plural ou conjugação) e também ordena resultados por proximidade
    ortográfica. Não fazemos lematização nem comparação de distância localmente.
    """
    if not isinstance(dados, list):
        return [], ""

    mapa_classes = {
        "n": "noun",
        "v": "verb",
        "adj": "adjective",
        "adv": "adverb",
    }
    for entrada in dados[:8]:
        if not isinstance(entrada, dict):
            continue
        defs_brutas = entrada.get("defs") or []
        if not isinstance(defs_brutas, list) or not defs_brutas:
            continue

        palavra_resultado = _texto_limpo(entrada.get("word"))
        verbete = _texto_limpo(entrada.get("defHeadword")) or palavra_resultado
        tags = entrada.get("tags") or []
        classe_padrao = ""
        if isinstance(tags, list):
            for tag in tags:
                classe_padrao = mapa_classes.get(str(tag).strip().lower(), "")
                if classe_padrao:
                    break

        definicoes: list[dict[str, str]] = []
        vistos: set[str] = set()
        for bruto in defs_brutas:
            bruto_texto = str(bruto or "")
            classe = classe_padrao
            if "\t" in bruto_texto:
                prefixo, texto_def = bruto_texto.split("\t", 1)
                classe = mapa_classes.get(prefixo.strip().lower(), classe)
                texto = _texto_limpo(texto_def)
            else:
                texto = _texto_limpo(bruto_texto)
            _adicionar_definicao(definicoes, vistos, texto, classe=classe)
            if len(definicoes) >= 6:
                break
        if definicoes:
            return definicoes, verbete
    return [], ""


def _consultar_ingles(palavra: str) -> tuple[list[dict[str, str]], str, str, str]:
    """Consulta inglês priorizando latência sem perder os fallbacks.

    Datamuse continua sendo a primeira fonte por resolver flexões via defHeadword.
    Se ele já trouxer definição, retornamos imediatamente. Só quando não encontra
    algo colocamos Wiktionary e Free Dictionary API em corrida e usamos o primeiro
    resultado útil.
    """
    termo = palavra.casefold()
    falhas: list[str] = []
    houve_resposta = False

    try:
        dados = _get_json(
            DATAMUSE_INGLES_URL,
            params={"sp": termo, "md": "dp", "max": 8},
            provedor="o Datamuse",
        )
        houve_resposta = True
        definicoes, verbete = _parse_datamuse_ingles(dados)
        if definicoes:
            return definicoes, "", "Datamuse (Wiktionary/WordNet)", verbete or termo
    except ErroConsultaDicionario as exc:
        falhas.append(str(exc))

    palavra_url = requests.utils.quote(termo, safe="")

    def consultar_wiktionary() -> tuple[list[dict[str, str]], str, str]:
        dados = _get_json(
            WIKTIONARY_INGLES_URL.format(word=palavra_url),
            provedor="o Wiktionary",
        )
        return _parse_wiktionary_ingles(dados), "", "Wiktionary"

    def consultar_free() -> tuple[list[dict[str, str]], str, str]:
        dados = _get_json(
            DICIONARIO_INGLES_URL.format(word=palavra_url),
            provedor="a Free Dictionary API",
        )
        definicoes, fonetica = _parse_free_dictionary(dados)
        return definicoes, fonetica, "Free Dictionary API"

    futuros = [
        _executor_provedores.submit(consultar_wiktionary),
        _executor_provedores.submit(consultar_free),
    ]
    for futuro in as_completed(futuros):
        try:
            definicoes, fonetica, fonte = futuro.result()
            houve_resposta = True
        except ErroConsultaDicionario as exc:
            falhas.append(str(exc))
            continue
        if definicoes:
            for outro in futuros:
                if outro is not futuro:
                    outro.cancel()
            return definicoes, fonetica, fonte, termo

    if falhas and not houve_resposta:
        raise ErroConsultaDicionario(
            "Não foi possível acessar os serviços de dicionário em inglês. Verifique a conexão com a internet e tente novamente."
        )
    return [], "", "", ""


def _texto_xml(elemento: ET.Element | None) -> str:
    if elemento is None:
        return ""
    return _texto_limpo(" ".join(parte for parte in elemento.itertext() if parte))


def _parse_dicionario_aberto(dados: Any) -> list[dict[str, str]]:
    if not isinstance(dados, list):
        return []

    definicoes: list[dict[str, str]] = []
    vistos: set[str] = set()
    for entrada in dados[:6]:
        if not isinstance(entrada, dict):
            continue
        xml = str(entrada.get("xml") or "").strip()
        if not xml:
            continue
        try:
            raiz = ET.fromstring(xml)
        except ET.ParseError:
            continue
        classe_padrao = _texto_xml(raiz.find(".//gramGrp"))
        for sentido in raiz.findall(".//sense"):
            classe = _texto_xml(sentido.find("gramGrp")) or classe_padrao
            defs = sentido.findall(".//def")
            if defs:
                for elemento_def in defs:
                    _adicionar_definicao(definicoes, vistos, _texto_xml(elemento_def), classe=classe)
            else:
                _adicionar_definicao(definicoes, vistos, _texto_xml(sentido), classe=classe)
            if len(definicoes) >= 6:
                return definicoes
    return definicoes


_CLASSES_WIKCIONARIO_PORTUGUES = {
    "adjetivo", "advérbio", "artigo", "conjunção", "interjeição", "numeral",
    "preposição", "pronome", "substantivo", "verbo", "locução", "expressão",
    "expressão verbal", "expressão idiomática", "forma verbal", "forma de verbo",
    "forma de substantivo", "forma de adjetivo", "forma de pronome", "sigla",
    "abreviatura", "contração", "prefixo", "sufixo", "particípio", "gerúndio",
}


def _classe_wikcionario_portugues(valor: Any) -> str:
    texto = _texto_limpo(valor)
    # Remove marcadores de edição e notas de sobrescrito que podem aparecer no HTML.
    texto = re.sub(r"\s*\[editar\]\s*$", "", texto, flags=re.I).strip()
    texto = re.sub(r"\s*\d+\s*$", "", texto).strip()
    base = texto.casefold()
    if base in _CLASSES_WIKCIONARIO_PORTUGUES:
        return texto
    if base.startswith("substantivo"):
        return "Substantivo"
    if base.startswith("adjetivo"):
        return "Adjetivo"
    if base.startswith("verbo"):
        return "Verbo"
    if base.startswith("advérbio"):
        return "Advérbio"
    if base.startswith("pronome"):
        return "Pronome"
    if base.startswith("forma "):
        return texto
    if base.startswith("expressão") or base.startswith("locução"):
        return texto
    return ""


def _texto_definicao_li(elemento: Any) -> tuple[str, str]:
    """Extrai definição e um exemplo sem misturar listas/tabelas aninhadas."""
    try:
        copia = BeautifulSoup(str(elemento), "html.parser").find("li")
    except Exception:
        copia = None
    if copia is None:
        return _texto_limpo(getattr(elemento, "get_text", lambda *a, **k: "")(" ", strip=True)), ""

    exemplo = ""
    for seletor in ("ul li", "dl dd", "blockquote"):
        candidato = copia.select_one(seletor)
        if candidato is not None:
            exemplo = _texto_limpo(candidato.get_text(" ", strip=True))
            if exemplo:
                break

    for aninhado in copia.find_all(["ul", "ol", "dl", "table", "blockquote"]):
        aninhado.decompose()
    texto = _texto_limpo(copia.get_text(" ", strip=True))
    texto = re.sub(r"^\s*\d+[.)]?\s*", "", texto).strip()
    return texto, exemplo


def _parse_wikcionario_portugues(dados: Any) -> list[dict[str, str]]:
    """Extrai definições em português do HTML estruturado do Wikcionário."""
    if not isinstance(dados, dict):
        return []
    parse = dados.get("parse")
    if not isinstance(parse, dict):
        return []
    html = parse.get("text")
    if isinstance(html, dict):
        html = html.get("*")
    if not isinstance(html, str) or not html.strip():
        return []

    soup = BeautifulSoup(html, "html.parser")
    heading_pt = None
    for h2 in soup.find_all("h2"):
        titulo = _texto_limpo(h2.get_text(" ", strip=True)).casefold()
        ident = _texto_limpo(h2.get("id") or "").casefold()
        if "português" in {titulo, ident} or titulo.startswith("português "):
            heading_pt = h2
            break
    if heading_pt is None:
        # Alguns formatos Parsoid colocam o id no span dentro do heading.
        alvo = soup.find(id=re.compile(r"^Portugu[eê]s$", re.I))
        heading_pt = alvo.find_parent("h2") if alvo is not None else None
    if heading_pt is None:
        return []

    definicoes: list[dict[str, str]] = []
    vistos: set[str] = set()
    classe_atual = ""

    for elemento in heading_pt.find_all_next():
        if elemento is heading_pt:
            continue
        nome = getattr(elemento, "name", None)
        if nome == "h2":
            break
        if nome in {"h3", "h4"}:
            classe_atual = _classe_wikcionario_portugues(elemento.get_text(" ", strip=True))
            continue
        if nome != "ol" or not classe_atual:
            continue

        # Apenas itens diretos da lista de aceções; exemplos internos ficam separados.
        for li in elemento.find_all("li", recursive=False):
            texto, exemplo = _texto_definicao_li(li)
            _adicionar_definicao(
                definicoes,
                vistos,
                texto,
                classe=classe_atual,
                exemplo=exemplo,
            )
            if len(definicoes) >= 6:
                return definicoes
    return definicoes


def _consultar_wikcionario_pagina(termo: str) -> list[dict[str, str]]:
    dados = _get_json(
        WIKCIONARIO_PORTUGUES_API_URL,
        params={
            "action": "parse",
            "page": termo,
            "prop": "text|sections",
            "redirects": "1",
            "format": "json",
            "formatversion": "2",
            "origin": "*",
        },
        provedor="o Wikcionário",
    )
    return _parse_wikcionario_portugues(dados)


def _buscar_wikcionario_portugues(termo: str) -> list[str]:
    """Retorna candidatos na ordem calculada pela busca nativa do MediaWiki."""
    dados = _get_json(
        WIKCIONARIO_PORTUGUES_API_URL,
        params={
            "action": "query",
            "list": "search",
            "srsearch": termo,
            "srlimit": 5,
            "srnamespace": 0,
            "format": "json",
            "formatversion": "2",
            "origin": "*",
        },
        provedor="a busca do Wikcionário",
    )
    if not isinstance(dados, dict):
        return []

    candidatos: list[str] = []
    vistos: set[str] = {termo.casefold()}
    info = dados.get("query", {}).get("searchinfo", {}) if isinstance(dados.get("query"), dict) else {}
    sugestao = _texto_limpo(info.get("suggestion")) if isinstance(info, dict) else ""
    if sugestao and sugestao.casefold() not in vistos:
        candidatos.append(sugestao)
        vistos.add(sugestao.casefold())

    query = dados.get("query")
    resultados = query.get("search") if isinstance(query, dict) else []
    if isinstance(resultados, list):
        for item in resultados:
            titulo = _texto_limpo(item.get("title")) if isinstance(item, dict) else ""
            chave = titulo.casefold()
            if titulo and chave not in vistos:
                candidatos.append(titulo)
                vistos.add(chave)
            if len(candidatos) >= 5:
                break
    return candidatos


def _buscar_proximas_dicionario_aberto(termo: str) -> list[str]:
    """Usa o endpoint /near do próprio Dicionário Aberto (Levenshtein 1)."""
    dados = _get_json(
        DICIONARIO_PORTUGUES_NEAR_URL.format(word=requests.utils.quote(termo, safe="")),
        provedor="a busca por palavras próximas do Dicionário Aberto",
    )
    if not isinstance(dados, list):
        return []
    candidatos: list[str] = []
    vistos = {termo.casefold()}
    for item in dados[:8]:
        candidato = _texto_limpo(item)
        chave = candidato.casefold()
        if candidato and chave not in vistos:
            candidatos.append(candidato)
            vistos.add(chave)
    return candidatos


def _consultar_portugues(palavra: str) -> tuple[list[dict[str, str]], str, str]:
    """Consulta português em paralelo e só usa aproximação quando necessário.

    Wikcionário e Dicionário Aberto disputam a consulta exata; a primeira fonte que
    devolver uma definição válida é exibida. Se nenhuma encontrar o termo, as buscas
    aproximadas nativas dos dois provedores também são executadas em paralelo.
    """
    termo = palavra.casefold()
    falhas: list[str] = []
    houve_resposta = False

    def exato_wikcionario() -> tuple[list[dict[str, str]], str, str]:
        return _consultar_wikcionario_pagina(termo), "Wikcionário", termo

    def exato_aberto() -> tuple[list[dict[str, str]], str, str]:
        dados = _get_json(
            DICIONARIO_PORTUGUES_URL.format(word=requests.utils.quote(termo, safe="")),
            provedor="o Dicionário Aberto",
        )
        return _parse_dicionario_aberto(dados), "Dicionário Aberto", termo

    futuros_exatos = [
        _executor_provedores.submit(exato_wikcionario),
        _executor_provedores.submit(exato_aberto),
    ]
    for futuro in as_completed(futuros_exatos):
        try:
            definicoes, fonte, verbete = futuro.result()
            houve_resposta = True
        except ErroConsultaDicionario as exc:
            falhas.append(str(exc))
            continue
        if definicoes:
            for outro in futuros_exatos:
                if outro is not futuro:
                    outro.cancel()
            return definicoes, fonte, verbete

    def aproximado_wikcionario() -> tuple[list[dict[str, str]], str, str]:
        candidatos = _buscar_wikcionario_portugues(termo)
        for candidato in candidatos[:4]:
            definicoes = _consultar_wikcionario_pagina(candidato)
            if definicoes:
                return definicoes, "Wikcionário (busca aproximada)", candidato
        return [], "", ""

    def aproximado_aberto() -> tuple[list[dict[str, str]], str, str]:
        candidatos = _buscar_proximas_dicionario_aberto(termo)
        for candidato in candidatos[:5]:
            dados = _get_json(
                DICIONARIO_PORTUGUES_URL.format(word=requests.utils.quote(candidato, safe="")),
                provedor="o Dicionário Aberto",
            )
            definicoes = _parse_dicionario_aberto(dados)
            if definicoes:
                return definicoes, "Dicionário Aberto (palavra próxima)", candidato
        return [], "", ""

    futuros_aproximados = [
        _executor_provedores.submit(aproximado_wikcionario),
        _executor_provedores.submit(aproximado_aberto),
    ]
    for futuro in as_completed(futuros_aproximados):
        try:
            definicoes, fonte, verbete = futuro.result()
            houve_resposta = True
        except ErroConsultaDicionario as exc:
            falhas.append(str(exc))
            continue
        if definicoes:
            for outro in futuros_aproximados:
                if outro is not futuro:
                    outro.cancel()
            return definicoes, fonte, verbete

    if falhas and not houve_resposta:
        raise ErroConsultaDicionario(
            "Não foi possível acessar os serviços de dicionário em português. Verifique a conexão com a internet e tente novamente."
        )
    return [], "", ""


def _normalizar_direcao_traducao(origem: Any, destino: Any) -> tuple[str, str]:
    origem_normalizada = normalizar_idioma_consulta(origem)
    destino_normalizado = normalizar_idioma_consulta(destino)
    if origem_normalizada == destino_normalizado:
        destino_normalizado = "pt_BR" if origem_normalizada == "en_US" else "en_US"
    return origem_normalizada, destino_normalizado


def _traduzir_palavra(palavra: str, origem: str, destino: str) -> str:
    origem_normalizada, destino_normalizado = _normalizar_direcao_traducao(origem, destino)
    if origem_normalizada == destino_normalizado:
        return ""

    codigo = {"en_US": "en", "pt_BR": "pt"}
    try:
        dados = _get_json(
            TRADUCAO_URL,
            params={
                "q": palavra,
                "langpair": f"{codigo[origem_normalizada]}|{codigo[destino_normalizado]}",
                "mt": "1",
            },
            provedor="o MyMemory",
            timeout=TIMEOUT_TRADUCAO,
        )
    except ErroConsultaDicionario:
        # A definição continua útil mesmo se o tradutor estiver temporariamente fora.
        return ""

    if not isinstance(dados, dict):
        return ""
    resposta = dados.get("responseData")
    traducao = _texto_limpo(resposta.get("translatedText")) if isinstance(resposta, dict) else ""
    if traducao and "MYMEMORY WARNING" not in traducao.upper():
        return traducao

    for item in dados.get("matches") or []:
        if not isinstance(item, dict):
            continue
        traducao = _texto_limpo(item.get("translation"))
        if traducao and "MYMEMORY WARNING" not in traducao.upper():
            return traducao
    return ""


def _cache_obter(chave: tuple[str, str, str, str]) -> dict[str, Any] | None:
    agora = monotonic()
    with _cache_lock:
        item = _cache.get(chave)
        if item and agora - item.criado_em <= CACHE_TTL_SEGUNDOS:
            return dict(item.valor)
        if item:
            _cache.pop(chave, None)
    return None


def _cache_salvar(chave: tuple[str, str, str, str], valor: dict[str, Any]) -> None:
    with _cache_lock:
        if len(_cache) >= CACHE_MAX_ITENS:
            mais_antigas = sorted(_cache.items(), key=lambda par: par[1].criado_em)[: max(1, CACHE_MAX_ITENS // 10)]
            for chave_antiga, _ in mais_antigas:
                _cache.pop(chave_antiga, None)
        _cache[chave] = _CacheItem(monotonic(), dict(valor))


def consultar_palavra_online(
    palavra: Any,
    idioma: Any,
    idioma_traducao_de: Any = "en_US",
    idioma_traducao_para: Any = "pt_BR",
) -> dict[str, Any]:
    palavra_normalizada = normalizar_palavra_consulta(palavra)
    idioma_normalizado = normalizar_idioma_consulta(idioma)
    traducao_de, traducao_para = _normalizar_direcao_traducao(idioma_traducao_de, idioma_traducao_para)
    chave = (idioma_normalizado, palavra_normalizada.casefold(), traducao_de, traducao_para)
    em_cache = _cache_obter(chave)
    if em_cache is not None:
        em_cache["cache"] = True
        return em_cache

    # Tradução e dicionário são independentes: executamos a tradução em paralelo
    # com a consulta principal para que os tempos de rede não sejam somados.
    futuro_traducao = None
    if idioma_normalizado == traducao_de:
        futuro_traducao = _executor_provedores.submit(
            _traduzir_palavra, palavra_normalizada, traducao_de, traducao_para
        )

    erro_dicionario: ErroConsultaDicionario | None = None
    definicoes: list[dict[str, str]] = []
    fonetica = ""
    fonte = ""
    verbete = ""
    try:
        if idioma_normalizado == "en_US":
            definicoes, fonetica, fonte, verbete = _consultar_ingles(palavra_normalizada)
        else:
            definicoes, fonte, verbete = _consultar_portugues(palavra_normalizada)
    except ErroConsultaDicionario as exc:
        erro_dicionario = exc

    traducao = ""
    if futuro_traducao is not None:
        try:
            traducao = futuro_traducao.result()
        except Exception:
            # A tradução é complementar; uma falha não deve atrasar/inutilizar a definição.
            traducao = ""

    # Se o dicionário estiver indisponível mas a tradução tiver funcionado, ainda
    # entregamos um resultado útil em vez de transformar toda a consulta em 502.
    if erro_dicionario is not None and not traducao:
        raise erro_dicionario

    resultado: dict[str, Any] = {
        "ok": bool(definicoes or traducao),
        "palavra": palavra_normalizada,
        "verbete": verbete or palavra_normalizada,
        "idioma": idioma_normalizado,
        "definicoes": definicoes,
        "traducao": traducao,
        "idioma_traducao_de": traducao_de,
        "idioma_traducao_para": traducao_para,
        "fonetica": fonetica,
        "fonte_dicionario": fonte,
        "fonte_traducao": "MyMemory" if traducao else "",
    }

    if resultado["ok"]:
        _cache_salvar(chave, resultado)
    resultado["cache"] = False
    return resultado

