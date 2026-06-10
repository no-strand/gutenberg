"""Aplicação Flask principal."""
from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile, mkdtemp
import os
import math
import logging
import re
import time
from collections import Counter

from bs4 import BeautifulSoup
import requests

from flask import Flask, abort, g, jsonify, redirect, render_template, request, send_file, send_from_directory, url_for
from werkzeug.exceptions import HTTPException

from .exportador_documentos import (
    exportar_projeto_docx,
    exportar_estatisticas_epub_pdf,
    exportar_projeto_pdf,
    exportar_roteiro_docx,
    exportar_roteiro_pdf,
)
from .exportador_html import exportar_projeto_epub, exportar_projeto_xhtml
from .exportador_gut import (
    exportar_gut_capitulos,
    exportar_gut_roteiro,
    importar_gut_em_projeto,
    ler_payload_gut,
    metadados_importaveis_projeto,
)
from .importador_documentos import (
    extensao_documento_importavel,
    importar_documento_como_capitulo,
    importar_documento_como_roteiro,
)
from .manipulador_capitulos import criar_capitulo, excluir_capitulo, ler_capitulo, salvar_capitulo
from .manipulador_biblioteca import (
    adicionar_livro_epub,
    adicionar_livro_pdf,
    excluir_livro,
    listar_livros,
    listar_colecoes_livros,
    marcar_livro_como_lido,
    mime_por_arquivo,
    obter_arquivo_extraido,
    obter_capitulo_livro,
    obter_caminho_capa,
    obter_livro,
    registrar_posicao_leitura_livro,
    registrar_ultimo_lido_livro,
    atualizar_progresso_livro,
)
from .manipulador_projetos import (
    atualizar_data_projeto,
    atualizar_metadados_projeto,
    criar_projeto,
    excluir_projeto,
    listar_projetos,
    obter_pasta_projeto,
    obter_projeto,
    registrar_ultimo_lido,
    registrar_posicao_leitura,
    salvar_capa_projeto,
    normalizar_idioma_projeto,
)
from .manipulador_roteiros import (
    TIPOS_ROTEIRO,
    atualizar_roteiro_info,
    criar_roteiro,
    excluir_roteiro,
    ler_roteiro,
    salvar_roteiro,
)
from .i18n import carregar_locale, idioma_projeto_rotulo, normalizar_idioma_app, t
from .utilidades import (
    EXPORTS_PADRAO,
    formatar_data_br,
    garantir_pasta_biblioteca,
    garantir_pasta_exports,
    garantir_pasta_projetos,
    obter_configuracoes,
    obter_pasta_exportacao,
    salvar_configuracoes,
    RAIZ_RECURSOS,
    APP_VERSAO,
)
from .logging_config import obter_logger, registrar_etapa
logger = obter_logger(__name__)


LIMITE_TITULO_PROJETO = 70
LIMITE_DESCRICAO_PROJETO = 500
LIMITE_AUTOR = 80
LIMITE_TAGS = 180
LIMITE_CONTATO = 70
LIMITE_INFO_ADICIONAL = 50
LIMITE_TITULO_CAPITULO = 70
LIMITE_TITULO_ROTEIRO = 70
LIMITE_CABECALHO_RODAPE = 40
LIMITE_PREFIXO_CENA = 4
LIMITE_LOGLINE = 280
LIMITE_SINOPSE = 1000
LIMITE_GENERO = 60
LIMITE_CATALOGO_NOME = 60
LIMITE_CATALOGO_DESCRICAO = 240
MAX_NUMERACAO_CENA = 9999
GEMINI_REVISAO_MODELO = "gemini-2.5-flash-lite"
GEMINI_REVISAO_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_REVISAO_MODELO}:generateContent"


@registrar_etapa
def _resposta_arquivo_exportado(arquivo: Path):
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        arquivo: Valor usado pela rotina para compor a operação de resposta arquivo exportado.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    if request.args.get("desktop_save") == "1":
        return jsonify({
            "ok": True,
            "arquivo": str(arquivo),
            "nome": arquivo.name,
            "pasta_inicial": str(obter_pasta_exportacao()),
        })
    return send_file(arquivo, as_attachment=True, download_name=arquivo.name)


@registrar_etapa
def _resposta_erro_json(mensagem: str, status_code: int = 400):
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        mensagem: Valor usado pela rotina para compor a operação de resposta erro json.
        status_code: Valor usado pela rotina para compor a operação de resposta erro json.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return jsonify({"ok": False, "erro": mensagem}), status_code


@registrar_etapa
def _tipos_roteiro_localizados() -> dict[str, dict[str, object]]:
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
    tipos = {}
    for tipo_id, meta in TIPOS_ROTEIRO.items():
        tipos[tipo_id] = {**meta, "label": t(f"script_type.{tipo_id}", default=str(meta.get("label") or tipo_id))}
    return tipos


@registrar_etapa
def _editor_redirect_importado(resultado: dict[str, object]) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        resultado: Valor usado pela rotina para compor a operação de editor redirect importado.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    slug = str(resultado.get("slug") or "")
    numero = int(resultado.get("editor_numero") or 0) if resultado.get("editor_numero") is not None else None
    if str(resultado.get("tipo_arquivo") or "") == "roteiro" and numero:
        return url_for("editar_roteiro_view", slug=slug, numero=numero)
    if numero:
        return url_for("editar_capitulo", slug=slug, numero=numero)
    return url_for("pagina_roteiro", slug=slug) if str(resultado.get("tipo_arquivo") or "") == "roteiro" else url_for("pagina_projeto", slug=slug)


@registrar_etapa
def _resolver_tipo_projeto_esperado(tipo_arquivo: str) -> str:
    """
    Resolve caminhos, referências ou conflitos de nomes de forma previsível para o restante do sistema.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        tipo_arquivo: Valor usado pela rotina para compor a operação de resolver tipo projeto esperado.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return "roteiro" if str(tipo_arquivo or "").strip().lower() == "roteiro" else "livro"


@registrar_etapa
def _obter_contexto_gut_pendente(app: Flask) -> dict[str, object] | None:
    """
    Localiza e devolve um dado ou recurso específico, aplicando as validações necessárias antes do retorno.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        app: Valor usado pela rotina para compor a operação de obter contexto gut pendente.

    Retorno:
        O recurso solicitado ou uma estrutura com os dados encontrados.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    caminho = str(app.config.get("PENDING_GUT_FILE") or "").strip()
    if not caminho:
        return None
    try:
        payload = ler_payload_gut(caminho)
        tipo_arquivo = str(payload.get("tipo_arquivo") or "")
        tipo_projeto = _resolver_tipo_projeto_esperado(tipo_arquivo)
        metadados = metadados_importaveis_projeto(payload)
        projetos = [
            {"slug": projeto.get("slug"), "titulo": projeto.get("titulo"), "tipo": projeto.get("tipo")}
            for projeto in listar_projetos()
            if projeto.get("tipo") == tipo_projeto
        ]
        return {
            "ativo": True,
            "caminho": caminho,
            "token": int(app.config.get("PENDING_GUT_TOKEN") or 0),
            "nome_arquivo": Path(caminho).name,
            "tipo_arquivo": tipo_arquivo,
            "tipo_projeto": tipo_projeto,
            "metadados": metadados,
            "projetos": projetos,
        }
    except Exception as exc:
        return {"ativo": True, "erro": str(exc)}


@registrar_etapa
def _limpar_gut_pendente(app: Flask) -> None:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        app: Valor usado pela rotina para compor a operação de limpar gut pendente.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    app.config["PENDING_GUT_FILE"] = None
    app.config["PENDING_GUT_TOKEN"] = 0


@registrar_etapa
def _registrar_gut_pendente(app: Flask, caminho_gut: str | Path) -> dict[str, object]:
    """
    Registra uma informação de estado ou progresso para que ela possa ser consultada posteriormente.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        app: Valor usado pela rotina para compor a operação de registrar gut pendente.
        caminho_gut: Valor usado pela rotina para compor a operação de registrar gut pendente.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    caminho = Path(str(caminho_gut or "")).expanduser()
    if not str(caminho):
        raise ValueError(t("backend.no_gut_file_sent"))
    if caminho.suffix.lower() != ".gut":
        raise ValueError(t("backend.invalid_gut_extension"))
    if not caminho.exists() or not caminho.is_file():
        raise FileNotFoundError(t("backend.no_gut_file_sent"))
    app.config["PENDING_GUT_FILE"] = str(caminho.resolve())
    app.config["PENDING_GUT_TOKEN"] = int(time.time() * 1000)
    contexto = _obter_contexto_gut_pendente(app)
    if not contexto or contexto.get("erro"):
        raise ValueError(str((contexto or {}).get("erro") or t("backend.no_pending_gut")))
    return contexto


@registrar_etapa
def _salvar_upload_temporario_gut(storage) -> Path:
    """
    Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        storage: Valor usado pela rotina para compor a operação de salvar upload temporario gut.

    Retorno:
        A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    nome_original = Path(str(storage.filename or "arquivo.gut")).name
    nome_seguro = re.sub(r'[\\/:*?"<>|]+', '_', nome_original).strip() or "arquivo.gut"
    if not Path(nome_seguro).suffix:
        nome_seguro += ".gut"
    pasta_tmp = Path(mkdtemp(prefix="gutenberg_import_"))
    caminho = pasta_tmp / nome_seguro
    storage.save(str(caminho))
    return caminho


@registrar_etapa
def _importar_gut_por_caminho(slug: str, caminho_gut: str | Path):
    """
    Coordena a importação de conteúdo externo para dentro do projeto, normalizando os dados para o modelo usado pela aplicação.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        caminho_gut: Valor usado pela rotina para compor a operação de importar gut por caminho.

    Retorno:
        Um resumo do conteúdo importado e dos registros criados no projeto.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    resultado = importar_gut_em_projeto(slug, caminho_gut)
    atualizar_data_projeto(slug)
    return {"ok": True, "redirect": _editor_redirect_importado(resultado), "resultado": resultado}


@registrar_etapa
def _importar_arquivo_por_caminho(slug: str, caminho: str | Path):
    """
    Coordena a importação de conteúdo externo para dentro do projeto, normalizando os dados para o modelo usado pela aplicação.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
        caminho: Caminho de arquivo ou pasta usado como origem ou destino da operação.

    Retorno:
        Um resumo do conteúdo importado e dos registros criados no projeto.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    caminho = Path(caminho)
    if caminho.suffix.lower() == ".gut":
        return _importar_gut_por_caminho(slug, caminho)
    if not extensao_documento_importavel(caminho):
        raise ValueError("Formato inválido. Use .gut, .docx, .pdf ou .txt.")
    projeto = obter_projeto(slug)
    if projeto.get("tipo") == "roteiro":
        resultado = importar_documento_como_roteiro(slug, caminho)
    else:
        resultado = importar_documento_como_capitulo(slug, caminho)
    atualizar_data_projeto(slug)
    return resultado


@registrar_etapa
def _aplicar_labels_roteiro_localizadas(projeto: dict) -> dict:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        projeto: Dicionário com os metadados e configurações do projeto atual.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    for roteiro in (projeto.get("roteiros") or []):
        tipo_id = str(roteiro.get("tipo_roteiro") or "spec_script")
        roteiro["tipo_roteiro_label"] = t(f"script_type.{tipo_id}", default=str(roteiro.get("tipo_roteiro_label") or tipo_id))
    return projeto


@registrar_etapa
def _extrair_texto_gemini(payload: dict | None) -> str:
    """
    Extrai informações de uma origem específica e devolve uma representação mais simples para as próximas etapas do fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        payload: Valor usado pela rotina para compor a operação de extrair texto gemini.

    Retorno:
        Dados extraídos em uma estrutura simplificada, adequada para as próximas etapas.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    candidatos = (payload or {}).get("candidates") or []
    for candidato in candidatos:
        partes = (((candidato or {}).get("content") or {}).get("parts") or [])
        textos = [str((parte or {}).get("text") or "") for parte in partes if (parte or {}).get("text")]
        texto = "".join(textos).strip()
        if texto:
            return texto
    return ""


@registrar_etapa
def _prompt_revisao_por_idioma(texto: str, idioma: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        texto: Texto bruto ou parcialmente tratado que será analisado pela função.
        idioma: Código de idioma usado para selecionar textos, metadados ou regras de formatação.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    idioma_normalizado = normalizar_idioma_projeto(idioma)
    if idioma_normalizado == "en_US":
        return (
            "You are an English text proofreader. "
            "Correct only spelling, punctuation, grammar, agreement, and small wording issues when necessary. "
            "Preserve meaning, style, paragraph structure, line breaks, and the original order of ideas. "
            "Do not summarize, do not explain, do not use markdown, and do not add comments. "
            "Return only the revised text.\n\n"
            f"TEXT TO PROOFREAD:\n{texto}"
        )
    return (
        "Você é um revisor de texto em português brasileiro. "
        "Corrija apenas ortografia, acentuação, pontuação, concordância e pequenos problemas gramaticais. "
        "Preserve o sentido, o estilo, a ordem das ideias, os parágrafos e as quebras de linha. "
        "Não resuma, não explique, não use markdown e não adicione comentários. "
        "Responda somente com o texto revisado.\n\n"
        f"TEXTO PARA REVISÃO:\n{texto}"
    )


@registrar_etapa
def _corrigir_texto_com_gemini(texto: str, chave_api: str, idioma: str = "pt-BR") -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        texto: Texto bruto ou parcialmente tratado que será analisado pela função.
        chave_api: Valor usado pela rotina para compor a operação de corrigir texto com gemini.
        idioma: Código de idioma usado para selecionar textos, metadados ou regras de formatação.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    prompt = _prompt_revisao_por_idioma(texto, idioma)
    corpo = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "topP": 0.8,
            "maxOutputTokens": 8192,
        },
    }
    resposta = requests.post(
        GEMINI_REVISAO_URL,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": chave_api,
        },
        json=corpo,
        timeout=60,
    )
    if not resposta.ok:
        try:
            detalhe = (resposta.json().get("error") or {}).get("message") or resposta.text
        except Exception:
            detalhe = resposta.text
        raise RuntimeError(t("backend.gemini_failed", detail=detalhe or resposta.status_code))
    texto_corrigido = _extrair_texto_gemini(resposta.json())
    if not texto_corrigido:
        raise RuntimeError(t("backend.gemini_empty"))
    return texto_corrigido


@registrar_etapa
def _texto_normalizado(valor: str | None) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        valor: Valor usado pela rotina para compor a operação de texto normalizado.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return re.sub(r"\s+", " ", str(valor or "")).strip()


@registrar_etapa
def _limitar_texto(valor: str | None, limite: int, campo: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        valor: Valor usado pela rotina para compor a operação de limitar texto.
        limite: Valor usado pela rotina para compor a operação de limitar texto.
        campo: Valor usado pela rotina para compor a operação de limitar texto.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    texto = str(valor or "").strip()
    if len(texto) > limite:
        raise ValueError(t("backend.field_max", field=campo, limit=limite))
    return texto


@registrar_etapa
def _validar_prefixo_cena(valor: str | None) -> str:
    """
    Confere se os dados recebidos atendem ao formato esperado antes de permitir a continuidade do fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        valor: Valor usado pela rotina para compor a operação de validar prefixo cena.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    texto = str(valor or "0").strip() or "0"
    if not re.fullmatch(rf"0{{1,{LIMITE_PREFIXO_CENA}}}", texto):
        raise ValueError(t("backend.scene_prefix_invalid", limit=LIMITE_PREFIXO_CENA))
    return texto


@registrar_etapa
def _validar_numeracao_cena(valor: str | int | None) -> int:
    """
    Confere se os dados recebidos atendem ao formato esperado antes de permitir a continuidade do fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        valor: Valor usado pela rotina para compor a operação de validar numeracao cena.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    try:
        numero = int(valor or 1)
    except (TypeError, ValueError) as exc:
        raise ValueError(t("backend.scene_initial_number_invalid")) from exc
    if numero < 1 or numero > MAX_NUMERACAO_CENA:
        raise ValueError(t("backend.scene_initial_number_range", max=MAX_NUMERACAO_CENA))
    return numero


@registrar_etapa
def _contato_valido(valor: str) -> bool:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        valor: Valor usado pela rotina para compor a operação de contato valido.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    if not valor:
        return True
    email_ok = bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", valor))
    telefone_compacto = re.sub(r"[^\d+]", "", valor)
    telefone_digitos = re.sub(r"\D", "", telefone_compacto)
    telefone_ok = bool(re.fullmatch(r"\+?\d+", telefone_compacto)) and 10 <= len(telefone_digitos) <= 13
    return email_ok or telefone_ok


@registrar_etapa
def _validar_campos_projeto(titulo: str, descricao: str, autor: str, tipo: str, tags_str: str = "", contatos: str = "", informacoes_adicionais: str = "") -> dict[str, object]:
    """
    Confere se os dados recebidos atendem ao formato esperado antes de permitir a continuidade do fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        titulo: Título exibido ou salvo para representar o conteúdo tratado.
        descricao: Valor usado pela rotina para compor a operação de validar campos projeto.
        autor: Valor usado pela rotina para compor a operação de validar campos projeto.
        tipo: Valor usado pela rotina para compor a operação de validar campos projeto.
        tags_str: Valor usado pela rotina para compor a operação de validar campos projeto.
        contatos: Valor usado pela rotina para compor a operação de validar campos projeto.
        informacoes_adicionais: Valor usado pela rotina para compor a operação de validar campos projeto.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    titulo_limpo = _limitar_texto(_texto_normalizado(titulo), LIMITE_TITULO_PROJETO, t('backend.field.project_title'))
    if not titulo_limpo:
        raise ValueError(t("backend.project_title_required"))
    descricao_limpa = _limitar_texto(descricao, LIMITE_DESCRICAO_PROJETO, t('backend.field.description'))
    autor_limpo = _limitar_texto(_texto_normalizado(autor), LIMITE_AUTOR, t('backend.field.author'))
    tags_limpas = [tag.strip() for tag in str(tags_str or "").split(",") if tag.strip()]
    if len(", ".join(tags_limpas)) > LIMITE_TAGS:
        raise ValueError(t("backend.tags_max_total", limit=LIMITE_TAGS))
    contato_limpo = _limitar_texto(_texto_normalizado(contatos), LIMITE_CONTATO, t('backend.field.contact'))
    if contato_limpo and not _contato_valido(contato_limpo):
        raise ValueError(t("backend.contact_invalid"))
    info_limpa = _limitar_texto(informacoes_adicionais, LIMITE_INFO_ADICIONAL, t('backend.field.additional_info'))
    return {
        "titulo": titulo_limpo,
        "descricao": descricao_limpa,
        "autor": autor_limpo,
        "tipo": tipo,
        "tags": tags_limpas if tipo != "roteiro" else [],
        "contatos": contato_limpo,
        "informacoes_adicionais": info_limpa if tipo == "roteiro" else "",
    }




@registrar_etapa
def _validar_titulo_capitulo(valor: str | None) -> str:
    """
    Confere se os dados recebidos atendem ao formato esperado antes de permitir a continuidade do fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        valor: Valor usado pela rotina para compor a operação de validar titulo capitulo.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    titulo = _limitar_texto(_texto_normalizado(valor), LIMITE_TITULO_CAPITULO, t('backend.field.chapter_title'))
    if not titulo:
        raise ValueError(t("backend.chapter_title_required"))
    return titulo

@registrar_etapa
def _validar_campos_roteiro(titulo: str, cabecalho: str = "", rodape: str = "", prefixo_cena: str = "0", numeracao_inicial: str | int | None = 1, logline: str = "", sinopse: str = "", genero: str = "") -> dict[str, object]:
    """
    Confere se os dados recebidos atendem ao formato esperado antes de permitir a continuidade do fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        titulo: Título exibido ou salvo para representar o conteúdo tratado.
        cabecalho: Valor usado pela rotina para compor a operação de validar campos roteiro.
        rodape: Valor usado pela rotina para compor a operação de validar campos roteiro.
        prefixo_cena: Valor usado pela rotina para compor a operação de validar campos roteiro.
        numeracao_inicial: Valor usado pela rotina para compor a operação de validar campos roteiro.
        logline: Valor usado pela rotina para compor a operação de validar campos roteiro.
        sinopse: Valor usado pela rotina para compor a operação de validar campos roteiro.
        genero: Valor usado pela rotina para compor a operação de validar campos roteiro.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    titulo_limpo = _limitar_texto(_texto_normalizado(titulo).upper(), LIMITE_TITULO_ROTEIRO, t('backend.field.script_name'))
    if not titulo_limpo:
        raise ValueError(t("backend.script_name_required"))
    return {
        "titulo": titulo_limpo,
        "cabecalho": _limitar_texto(_texto_normalizado(cabecalho), LIMITE_CABECALHO_RODAPE, t('backend.field.header')),
        "rodape": _limitar_texto(_texto_normalizado(rodape), LIMITE_CABECALHO_RODAPE, t('backend.field.footer')),
        "prefixo_cena": _validar_prefixo_cena(prefixo_cena),
        "numeracao_inicial": _validar_numeracao_cena(numeracao_inicial),
        "logline": _limitar_texto(logline, LIMITE_LOGLINE, t('backend.field.logline')),
        "sinopse": _limitar_texto(sinopse, LIMITE_SINOPSE, t('backend.field.synopsis')),
        "genero": _limitar_texto(_texto_normalizado(genero), LIMITE_GENERO, t('backend.field.genre')),
    }


@registrar_etapa
def _validar_item_catalogo(nome: str, descricao: str) -> tuple[str, str]:
    """
    Confere se os dados recebidos atendem ao formato esperado antes de permitir a continuidade do fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        nome: Valor usado pela rotina para compor a operação de validar item catalogo.
        descricao: Valor usado pela rotina para compor a operação de validar item catalogo.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    nome_limpo = _limitar_texto(_texto_normalizado(nome).upper(), LIMITE_CATALOGO_NOME, t('backend.field.name'))
    if not nome_limpo:
        raise ValueError(t("backend.name_required"))
    descricao_limpa = _limitar_texto(descricao, LIMITE_CATALOGO_DESCRICAO, t('backend.field.description'))
    return nome_limpo, descricao_limpa


@registrar_etapa
def icon_svg(nome: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        nome: Valor usado pela rotina para compor a operação de icon svg.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    icones = {
        "add": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>',
        "delete": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/></svg>',
        "open": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4h6v6"/><path d="M10 14 20 4"/><path d="M20 14v5H4V4h5"/></svg>',
        "edit": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 1 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/></svg>',
        "read": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 5.5A2.5 2.5 0 0 1 5.5 3H11v18H5.5A2.5 2.5 0 0 0 3 18.5z"/><path d="M21 5.5A2.5 2.5 0 0 0 18.5 3H13v18h5.5a2.5 2.5 0 0 1 2.5-2.5z"/></svg>',
        "continue": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 5 11 7-11 7z"/></svg>',
        "export": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg>',
        "back": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5"/><path d="m12 19-7-7 7-7"/></svg>',
        "config": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 15.5A3.5 3.5 0 1 0 12 8.5a3.5 3.5 0 0 0 0 7z"/><path d="M19.4 15a1.7 1.7 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1V21a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-.4-1 1.7 1.7 0 0 0-1-.6 1.7 1.7 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1-.4H3a2 2 0 1 1 0-4h.09a1.7 1.7 0 0 0 1-.4 1.7 1.7 0 0 0 .6-1 1.7 1.7 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1V3a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 .4 1 1.7 1.7 0 0 0 1 .6 1.7 1.7 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9c.26.3.47.65.6 1a1.7 1.7 0 0 0 1 .4H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1 .4c-.3.13-.65.34-1 .6z"/></svg>',
        "save": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8"/><path d="M7 3v5h8"/></svg>',
        "library": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 17A2.5 2.5 0 0 0 4 19.5V5a2 2 0 0 1 2-2h14v14"/><path d="M8 7h8"/><path d="M8 11h8"/></svg>',
        "users": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><path d="M20 8v6"/><path d="M23 11h-6"/></svg>',
        "place": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-6-5.33-6-11a6 6 0 1 1 12 0c0 5.67-6 11-6 11z"/><circle cx="12" cy="10" r="2.5"/></svg>',
        "info": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>',
        "stats": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20h16"/><path d="M7 16v-5"/><path d="M12 16V8"/><path d="M17 16V4"/></svg>',
    }
    return icones.get(nome, "")


@registrar_etapa
def _extrair_texto_capitulo_html(html: str) -> dict:
    """
    Extrai informações de uma origem específica e devolve uma representação mais simples para as próximas etapas do fluxo.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        html: Conteúdo HTML já editado ou normalizado pela aplicação.

    Retorno:
        Dados extraídos em uma estrutura simplificada, adequada para as próximas etapas.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    texto_total = soup.get_text(" ", strip=True)
    palavras = re.findall(r"[\wÀ-ÿ']+", texto_total.lower(), flags=re.UNICODE)
    sentencas = [trecho.strip() for trecho in re.split(r"(?<=[.!?…])\s+|\n+", texto_total) if trecho.strip()]

    paragrafos = []
    for bloco in soup.find_all(["p", "li", "blockquote"]):
        texto = bloco.get_text(" ", strip=True)
        if texto:
            paragrafos.append(texto)

    titulos = {}
    for nivel in ("h1", "h2", "h3"):
        titulos[nivel] = sum(1 for item in soup.find_all(nivel) if item.get_text(" ", strip=True))

    dialogos = []
    for bloco in soup.find_all(["blockquote", "q"]):
        texto = bloco.get_text(" ", strip=True)
        if texto:
            dialogos.append(texto)

    return {
        "texto": texto_total,
        "palavras": palavras,
        "total_palavras": len(palavras),
        "caracteres": len(texto_total),
        "caracteres_sem_espaco": len(re.sub(r"\s+", "", texto_total)),
        "sentencas": sentencas,
        "paragrafos": paragrafos,
        "total_paragrafos": len(paragrafos),
        "media_palavras_paragrafo": round((len(palavras) / len(paragrafos)), 1) if paragrafos else 0,
        "titulos": titulos,
        "imagens": len(soup.find_all("img")),
        "links": len(soup.find_all("a")),
        "listas": len(soup.find_all(["ul", "ol"])),
        "itens_lista": len(soup.find_all("li")),
        "citacoes": len(soup.find_all("blockquote")),
        "dialogos": dialogos,
        "total_palavras_dialogo": sum(len(re.findall(r"[\wÀ-ÿ']+", item, flags=re.UNICODE)) for item in dialogos),
    }


@registrar_etapa
def _formatar_minutos_legivel(minutos: int) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        minutos: Valor usado pela rotina para compor a operação de formatar minutos legivel.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    minutos = max(0, int(round(minutos)))
    horas, resto = divmod(minutos, 60)
    if horas and resto:
        return f"{horas}h {resto} min"
    if horas:
        return f"{horas}h"
    return f"{resto} min"


@registrar_etapa
def _calcular_estatisticas_epub(slug: str) -> dict:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    projeto = obter_projeto(slug)
    capitulos = projeto.get("capitulos") or []

    capitulos_stats = []
    todas_palavras = []
    todos_paragrafos = []
    todas_sentencas = []
    totais = Counter()

    for capitulo in capitulos:
        dados_capitulo = ler_capitulo(obter_pasta_projeto(slug), int(capitulo.get("id") or 0))
        html = "\n".join(dados_capitulo.get("paragrafos") or [])
        metricas = _extrair_texto_capitulo_html(html)
        total_palavras = metricas["total_palavras"]
        totais.update({
            "palavras": total_palavras,
            "caracteres": metricas["caracteres"],
            "caracteres_sem_espaco": metricas["caracteres_sem_espaco"],
            "paragrafos": metricas["total_paragrafos"],
            "imagens": metricas["imagens"],
            "links": metricas["links"],
            "listas": metricas["listas"],
            "itens_lista": metricas["itens_lista"],
            "citacoes": metricas["citacoes"],
            "dialogos_palavras": metricas["total_palavras_dialogo"],
            "h1": metricas["titulos"].get("h1", 0),
            "h2": metricas["titulos"].get("h2", 0),
            "h3": metricas["titulos"].get("h3", 0),
        })
        todas_palavras.extend(metricas["palavras"])
        todos_paragrafos.extend(metricas["paragrafos"])
        todas_sentencas.extend(metricas["sentencas"])
        capitulos_stats.append({
            "id": capitulo.get("id"),
            "titulo": capitulo.get("titulo") or f"Capítulo {capitulo.get('id')}",
            "data_atualizacao": capitulo.get("data_atualizacao"),
            "palavras": total_palavras,
            "caracteres": metricas["caracteres"],
            "paragrafos": metricas["total_paragrafos"],
            "tempo_leitura_min": max(1, math.ceil(total_palavras / 230)) if total_palavras else 0,
            "paginas_estimadas": round(total_palavras / 250, 1) if total_palavras else 0,
            "densidade": round(total_palavras / metricas["total_paragrafos"], 1) if metricas["total_paragrafos"] else 0,
        })

    total_capitulos = len(capitulos_stats)
    capitulos_com_texto = sum(1 for item in capitulos_stats if item["palavras"] > 0)
    capitulos_vazios = total_capitulos - capitulos_com_texto
    total_palavras = totais["palavras"]
    total_paragrafos = totais["paragrafos"]
    total_sentencas = len(todas_sentencas)
    palavras_unicas = len(set(todas_palavras))
    diversidade_lexica = round((palavras_unicas / total_palavras) * 100, 1) if total_palavras else 0
    media_palavras_capitulo = round(total_palavras / total_capitulos, 1) if total_capitulos else 0
    media_palavras_paragrafo = round(total_palavras / total_paragrafos, 1) if total_paragrafos else 0
    media_palavras_sentenca = round(total_palavras / total_sentencas, 1) if total_sentencas else 0
    tempo_leitura_min = max(1, math.ceil(total_palavras / 230)) if total_palavras else 0
    paginas_estimadas = math.ceil(total_palavras / 250) if total_palavras else 0
    laudas_estimadas = math.ceil(total_palavras / 300) if total_palavras else 0
    capitulos_ordenados = sorted(capitulos_stats, key=lambda item: item["palavras"], reverse=True)
    maior_capitulo = capitulos_ordenados[0] if capitulos_ordenados else None
    menor_capitulo = min(capitulos_stats, key=lambda item: item["palavras"], default=None)

    top_vocabulario = []
    if todas_palavras:
        stopwords = {
            "a","o","as","os","um","uma","uns","umas","de","da","do","das","dos","e","é","em","no","na","nos","nas","por","para","com","sem","sob","sobre","ao","aos","à","às","que","se","eu","tu","ele","ela","eles","elas","me","te","lhe","lhes","nos","vós","vocês","um","uma","ser","estar","foi","era","são","como","mais","mas","ou","já","também","não","sim","porque","quando","onde"
        }
        frequencia = Counter([p for p in todas_palavras if len(p) >= 4 and p not in stopwords])
        top_vocabulario = [[palavra, qtd] for palavra, qtd in frequencia.most_common(12)]

    participacao_total = total_palavras or 1
    ranking_capitulos = []
    for item in capitulos_ordenados[:12]:
        ranking_capitulos.append({
            **item,
            "participacao": round((item["palavras"] / participacao_total) * 100, 1) if total_palavras else 0,
        })

    return {
        "projeto": {
            "titulo": projeto.get("titulo") or slug,
            "autor": projeto.get("autor") or "",
            "idioma": projeto.get("idioma") or "pt-BR",
        },
        "resumo": {
            "total_capitulos": total_capitulos,
            "capitulos_com_texto": capitulos_com_texto,
            "capitulos_vazios": capitulos_vazios,
            "palavras": total_palavras,
            "caracteres": totais["caracteres"],
            "caracteres_sem_espaco": totais["caracteres_sem_espaco"],
            "paragrafos": total_paragrafos,
            "sentencas": total_sentencas,
            "tempo_leitura_min": tempo_leitura_min,
            "tempo_leitura_legivel": _formatar_minutos_legivel(tempo_leitura_min),
            "paginas_estimadas": paginas_estimadas,
            "laudas_estimadas": laudas_estimadas,
            "media_palavras_capitulo": media_palavras_capitulo,
            "media_palavras_paragrafo": media_palavras_paragrafo,
            "media_palavras_sentenca": media_palavras_sentenca,
            "diversidade_lexica": diversidade_lexica,
            "palavras_unicas": palavras_unicas,
            "imagens": totais["imagens"],
            "links": totais["links"],
            "listas": totais["listas"],
            "itens_lista": totais["itens_lista"],
            "citacoes": totais["citacoes"],
            "h1": totais["h1"],
            "h2": totais["h2"],
            "h3": totais["h3"],
            "dialogos_palavras": totais["dialogos_palavras"],
            "percentual_dialogos": round((totais["dialogos_palavras"] / total_palavras) * 100, 1) if total_palavras else 0,
        },
        "maior_capitulo": maior_capitulo,
        "menor_capitulo": menor_capitulo,
        "capitulos": capitulos_stats,
        "ranking_capitulos": ranking_capitulos,
        "top_vocabulario": top_vocabulario,
    }


@registrar_etapa
def _destino_projeto(projeto: dict, slug: str) -> str:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        projeto: Dicionário com os metadados e configurações do projeto atual.
        slug: Identificador amigável do projeto, livro ou recurso que será manipulado.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    return url_for("pagina_roteiro", slug=slug) if projeto.get("tipo") == "roteiro" else url_for("pagina_projeto", slug=slug)


@registrar_etapa
def criar_app() -> Flask:
    """
    Cria um novo registro, arquivo ou estrutura interna mantendo o padrão de armazenamento do projeto.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Retorno:
        Os dados do novo item criado, incluindo identificadores gerados quando existirem.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    app = Flask(
        __name__,
        template_folder=str((RAIZ_RECURSOS / "templates").resolve()),
        static_folder=str((RAIZ_RECURSOS / "static").resolve()),
    )
    app.config["SECRET_KEY"] = "editor-literario-local"
    garantir_pasta_projetos()
    garantir_pasta_exports()
    garantir_pasta_biblioteca()
    app.jinja_env.filters["data_br"] = formatar_data_br
    logger.info("Aplicação Flask criada e diretórios essenciais garantidos.")

    @app.before_request
    def _registrar_inicio_requisicao():
        g._gutenberg_inicio_requisicao = time.perf_counter()
        logger.info(
            "Requisição recebida | metodo=%s | caminho=%s | endpoint=%s | ip=%s",
            request.method,
            request.path,
            request.endpoint,
            request.headers.get("X-Forwarded-For", request.remote_addr),
        )

    @app.after_request
    def _registrar_fim_requisicao(resposta):
        inicio = getattr(g, "_gutenberg_inicio_requisicao", None)
        duracao_ms = ((time.perf_counter() - inicio) * 1000) if inicio else 0.0
        nivel = logging.WARNING if resposta.status_code >= 400 else logging.INFO
        logger.log(
            nivel,
            "Requisição finalizada | metodo=%s | caminho=%s | status=%s | duracao_ms=%.2f",
            request.method,
            request.path,
            resposta.status_code,
            duracao_ms,
        )
        return resposta

    @app.errorhandler(Exception)
    def _registrar_erro_requisicao(exc):
        if isinstance(exc, HTTPException):
            logger.warning(
                "Erro HTTP tratado | metodo=%s | caminho=%s | endpoint=%s | status=%s | descricao=%s",
                request.method,
                request.path,
                request.endpoint,
                exc.code,
                exc.description,
            )
            return exc
        logger.exception(
            "Erro não tratado em requisição | metodo=%s | caminho=%s | endpoint=%s",
            request.method,
            request.path,
            request.endpoint,
        )
        raise exc


    @app.context_processor
    @registrar_etapa
    def injetar_config():
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
        config = obter_configuracoes()
        idioma_app = normalizar_idioma_app(config.get("idioma_app"))
        return {
            "config_global": config,
            "icon_svg": icon_svg,
            "t": lambda key, **kwargs: t(key, idioma=idioma_app, **kwargs),
            "idioma_projeto_rotulo": idioma_projeto_rotulo,
            "idioma_app": idioma_app,
            "i18n_catalog": carregar_locale(idioma_app),
            "app_version": APP_VERSAO,
        }

    @app.get("/")
    @registrar_etapa
    def pagina_inicial():
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
        return render_template("index.html", projetos=listar_projetos(), gut_pendente=_obter_contexto_gut_pendente(app))

    @app.get("/configuracoes")
    @registrar_etapa
    def pagina_configuracoes():
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
        return render_template("configuracoes.html", config=obter_configuracoes())

    @app.post("/configuracoes/salvar")
    @registrar_etapa
    def rota_salvar_configuracoes():
        """
        Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Retorno:
            A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        config_atual = obter_configuracoes()
        dados = {
            "identacao_paragrafo_em": float(request.form.get("identacao_paragrafo_em") or 2),
            "identacao_paragrafo_maior_em": float(request.form.get("identacao_paragrafo_maior_em") or 3.2),
            "espaco_paragrafos_em": float(request.form.get("espaco_paragrafos_em") or 1.15),
            "espaco_linhas": float(request.form.get("espaco_linhas") or 1.85),
            "tamanho_fonte_px": int(request.form.get("tamanho_fonte_px") or 20),
            "h1_px": int(request.form.get("h1_px") or 28),
            "h2_px": int(request.form.get("h2_px") or 22),
            "h3_px": int(request.form.get("h3_px") or 18),
            "largura_leitura_px": int(request.form.get("largura_leitura_px") or 860),
            "leitor_tema": config_atual.get("leitor_tema", "tema-claro"),
            "leitor_fonte": config_atual.get("leitor_fonte", "fonte-serif"),
            "leitor_tamanho_fonte_px": int(config_atual.get("leitor_tamanho_fonte_px") or config_atual.get("tamanho_fonte_px") or 20),
            "leitor_modo_confortavel": bool(config_atual.get("leitor_modo_confortavel", False)),
            "leitor_modo_ampliado": bool(config_atual.get("leitor_modo_ampliado", False)),
            "caminho_exportacao": request.form.get("caminho_exportacao", str(EXPORTS_PADRAO)).strip() or str(EXPORTS_PADRAO),
            "caminho_biblioteca": request.form.get("caminho_biblioteca", config_atual.get("caminho_biblioteca", "")).strip() or str(config_atual.get("caminho_biblioteca", "")),
            "modo_browser": request.form.get("modo_browser") == "on",
            "efeito_editor": request.form.get("efeito_editor") == "on",
            "gemini_api_key": request.form.get("gemini_api_key", config_atual.get("gemini_api_key", "")).strip(),
            "idioma_app": normalizar_idioma_app(request.form.get("idioma_app", config_atual.get("idioma_app", "pt_BR"))),
        }
        salvar_configuracoes(dados)
        return redirect(url_for("pagina_configuracoes"))

    @app.get("/documentation/<path:arquivo>")
    @registrar_etapa
    def pagina_documentacao_arquivos(arquivo: str):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            arquivo: Valor usado pela rotina para compor a operação de pagina documentacao arquivos.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        pasta_documentacao = (RAIZ_RECURSOS / "documentation").resolve()
        return send_from_directory(pasta_documentacao, arquivo)

    @app.get("/creditos")
    @registrar_etapa
    def pagina_creditos():
        """Exibe a página de créditos do aplicativo."""
        return render_template("creditos.html")

    @app.post("/api/revisao/gemini")
    @registrar_etapa
    def rota_revisao_gemini():
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
        dados = request.get_json(silent=True) or {}
        texto = str(dados.get("texto") or "").strip()
        if not texto:
            return jsonify({"erro": t("backend.no_text_for_review")}), 400
        config = obter_configuracoes()
        chave_api = str(config.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY") or "").strip()
        if not chave_api:
            return jsonify({"erro": t("backend.set_api_key")}), 400
        try:
            texto_corrigido = _corrigir_texto_com_gemini(texto, chave_api, dados.get("idioma"))
        except Exception as exc:
            return jsonify({"erro": str(exc)}), 502
        return jsonify({"texto_corrigido": texto_corrigido, "modelo": GEMINI_REVISAO_MODELO})

    @app.post("/projetos/criar")
    @registrar_etapa
    def rota_criar_projeto():
        """
        Cria um novo registro, arquivo ou estrutura interna mantendo o padrão de armazenamento do projeto.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Retorno:
            Os dados do novo item criado, incluindo identificadores gerados quando existirem.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        tipo = (request.form.get("tipo") or "livro").strip().lower()
        idioma = normalizar_idioma_projeto(request.form.get("idioma", "pt-BR").strip() or "pt-BR")
        try:
            campos = _validar_campos_projeto(
                titulo=request.form.get("titulo", ""),
                descricao=request.form.get("descricao", ""),
                autor=request.form.get("autor", ""),
                tipo=tipo,
                tags_str=request.form.get("tags", ""),
                contatos=request.form.get("contatos", ""),
                informacoes_adicionais=request.form.get("informacoes_adicionais", ""),
            )
            projeto = criar_projeto(campos["titulo"], campos["descricao"], campos["autor"], campos["tags"], idioma, tipo=tipo, contatos=campos["contatos"], informacoes_adicionais=campos["informacoes_adicionais"])
            if projeto.get("tipo") == "livro" and "cover" in request.files and request.files["cover"].filename:
                with NamedTemporaryFile(delete=False, suffix=Path(request.files["cover"].filename).suffix or ".img") as tmp:
                    request.files["cover"].save(tmp.name)
                    salvar_capa_projeto(projeto["slug"], Path(tmp.name))
            return jsonify({"ok": True, "redirect": _destino_projeto(projeto, projeto["slug"])})
        except ValueError as erro:
            return jsonify({"ok": False, "erro": str(erro)}), 400
        except FileExistsError as erro:
            return jsonify({"ok": False, "erro": str(erro)}), 400

    @app.post("/projetos/<slug>/excluir")
    @registrar_etapa
    def rota_excluir_projeto(slug: str):
        """
        Remove o item indicado e executa os cuidados necessários para manter o restante do projeto consistente.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            None. A função sinaliza falhas por exceção quando a remoção não pode ser concluída.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        excluir_projeto(slug)
        return jsonify({"ok": True})

    @app.get("/projetos/<slug>")
    @registrar_etapa
    def pagina_projeto(slug: str):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        projeto = obter_projeto(slug)
        if projeto.get("tipo") == "roteiro":
            return redirect(url_for("pagina_roteiro", slug=slug))
        return render_template("projeto.html", projeto=projeto)

    @app.get("/api/projetos/<slug>/estatisticas")
    @registrar_etapa
    def api_estatisticas_projeto(slug: str):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        projeto = obter_projeto(slug)
        if projeto.get("tipo") == "roteiro":
            return jsonify({"ok": False, "erro": t('backend.use_script_editor_stats')}), 400
        return jsonify({"ok": True, "estatisticas": _calcular_estatisticas_epub(slug)})


    @app.get("/projetos/<slug>/estatisticas/exportar-pdf")
    @registrar_etapa
    def rota_exportar_estatisticas_projeto_pdf(slug: str):
        """
        Conduz a exportação dos dados do projeto para o formato esperado, preparando o conteúdo e delegando etapas auxiliares quando necessário.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            O caminho do arquivo exportado ou uma estrutura com informações da exportação.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        projeto = obter_projeto(slug)
        if projeto.get("tipo") == "roteiro":
            return jsonify({"ok": False, "erro": t('backend.exporter_only_epub_stats')}), 400
        estatisticas = _calcular_estatisticas_epub(slug)
        arquivo = exportar_estatisticas_epub_pdf(slug, estatisticas)
        return send_file(arquivo, as_attachment=True, download_name=arquivo.name)

    @app.get("/projetos/<slug>/roteiro")
    @registrar_etapa
    def pagina_roteiro(slug: str):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        projeto = obter_projeto(slug)
        if projeto.get("tipo") != "roteiro":
            return redirect(url_for("pagina_projeto", slug=slug))
        projeto = _aplicar_labels_roteiro_localizadas(projeto)
        return render_template("roteiro.html", projeto=projeto, tipos_roteiro=_tipos_roteiro_localizados())

    @app.get("/biblioteca")
    @registrar_etapa
    def pagina_biblioteca():
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
        livros = listar_livros()
        colecoes = listar_colecoes_livros()
        return render_template("biblioteca.html", livros=livros, colecoes=colecoes)

    @app.post("/biblioteca/adicionar")
    @registrar_etapa
    def rota_adicionar_livro_biblioteca():
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
        arquivos = [arquivo for arquivo in request.files.getlist("epubs") if arquivo and arquivo.filename]
        if not arquivos:
            return jsonify({"ok": False, "erro": t('backend.no_book_file_uploaded')}), 400
        adicionados = []
        for arquivo in arquivos:
            sufixo = Path(arquivo.filename).suffix.lower()
            if sufixo not in {".epub", ".pdf"}:
                continue
            with NamedTemporaryFile(delete=False, suffix=sufixo or ".epub") as tmp:
                caminho_tmp = Path(tmp.name)
                arquivo.save(tmp.name)
            caminho_origem = caminho_tmp.with_name(Path(arquivo.filename).name)
            caminho_tmp.replace(caminho_origem)
            try:
                livro = adicionar_livro_pdf(caminho_origem) if sufixo == ".pdf" else adicionar_livro_epub(caminho_origem)
            except Exception as exc:
                try:
                    caminho_origem.unlink(missing_ok=True)
                except Exception:
                    pass
                return jsonify({"ok": False, "erro": str(exc) or t('backend.error_converting_pdf_to_epub')}), 400
            try:
                caminho_origem.unlink(missing_ok=True)
            except Exception:
                pass
            adicionados.append({"slug": livro["slug"], "titulo": livro["titulo"]})
        if not adicionados:
            return jsonify({"ok": False, "erro": t('backend.no_valid_book_added')}), 400
        return jsonify({"ok": True, "adicionados": adicionados})

    @app.post("/biblioteca/<slug>/excluir")
    @registrar_etapa
    def rota_excluir_livro_biblioteca(slug: str):
        """
        Remove o item indicado e executa os cuidados necessários para manter o restante do projeto consistente.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            None. A função sinaliza falhas por exceção quando a remoção não pode ser concluída.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        excluir_livro(slug)
        return jsonify({"ok": True})

    @app.get("/biblioteca/<slug>")
    @registrar_etapa
    def abrir_livro_biblioteca(slug: str):
        """
        Abre um recurso solicitado pelo usuário ou pela aplicação usando o mecanismo apropriado para o contexto.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        livro = obter_livro(slug)
        if not livro.get("capitulos"):
            return redirect(url_for("pagina_biblioteca"))
        ultimo = livro.get("ultimo_lido")
        if ultimo:
            return redirect(url_for("ler_livro_biblioteca", slug=slug, numero=ultimo))
        return redirect(url_for("ler_livro_biblioteca", slug=slug, numero=1))

    @app.get("/biblioteca/<slug>/capa")
    @registrar_etapa
    def capa_livro_biblioteca(slug: str):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        return send_file(obter_caminho_capa(slug))

    @app.get("/biblioteca/<slug>/arquivo/<path:caminho>")
    @registrar_etapa
    def servir_arquivo_livro(slug: str, caminho: str):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
            caminho: Caminho de arquivo ou pasta usado como origem ou destino da operação.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        arquivo = obter_arquivo_extraido(slug, caminho)
        return send_file(arquivo, mimetype=mime_por_arquivo(arquivo))

    @app.get("/biblioteca/<slug>/capitulos/<int:numero>/ler")
    @registrar_etapa
    def ler_livro_biblioteca(slug: str, numero: int):
        """
        Lê conteúdo persistido e devolve dados estruturados para consumo pelo restante da aplicação.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
    
        Retorno:
            Conteúdo estruturado lido a partir da origem informada.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        try:
            livro, capitulo, capitulo_anterior, proximo_capitulo = obter_capitulo_livro(slug, numero)
        except FileNotFoundError:
            abort(404)
        registrar_ultimo_lido_livro(slug, numero)
        posicao_inicial = int((livro.get("posicoes_leitura") or {}).get(str(numero), 0) or 0)
        return render_template(
            "leitor_alt.html",
            livro=livro,
            capitulo=capitulo,
            numero=numero,
            capitulo_anterior=capitulo_anterior,
            proximo_capitulo=proximo_capitulo,
            conteudo_url=url_for("servir_arquivo_livro", slug=slug, caminho=capitulo["asset_path"]),
            posicao_inicial=posicao_inicial,
        )

    @app.post("/api/biblioteca/<slug>/capitulos/<int:numero>/posicao")
    @registrar_etapa
    def rota_salvar_posicao_livro(slug: str, numero: int):
        """
        Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
    
        Retorno:
            A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        dados = request.get_json(silent=True) or {}
        posicao = int(dados.get("posicao") or 0)
        percentual = float(dados.get("percentual") or 0)
        registrar_posicao_leitura_livro(slug, numero, posicao)
        livro = atualizar_progresso_livro(slug, numero, percentual, posicao=posicao)
        return jsonify({"ok": True, "progresso_percentual": livro.get("progresso_percentual", 0), "foi_lido": livro.get("foi_lido", False)})

    @app.post("/api/biblioteca/<slug>/marcar-lido")
    @registrar_etapa
    def rota_marcar_livro_lido(slug: str):
        """
        Altera um estado booleano ou de progresso associado ao item informado.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        dados = request.get_json(silent=True) or {}
        livro = marcar_livro_como_lido(slug, bool(dados.get("lido", False)))
        return jsonify({"ok": True, "progresso_percentual": livro.get("progresso_percentual", 0), "foi_lido": livro.get("foi_lido", False)})

    @app.post("/api/configuracoes/leitor")
    @registrar_etapa
    def rota_salvar_preferencias_leitor():
        """
        Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Retorno:
            A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        dados = request.get_json(silent=True) or {}
        config_atual = obter_configuracoes()
        atualizacoes = {
            "leitor_tema": (dados.get("tema") or config_atual.get("leitor_tema") or "tema-claro"),
            "leitor_fonte": (dados.get("fonte") or config_atual.get("leitor_fonte") or "fonte-serif"),
            "leitor_tamanho_fonte_px": int(dados.get("tamanho") or config_atual.get("leitor_tamanho_fonte_px") or config_atual.get("tamanho_fonte_px") or 20),
            "leitor_modo_confortavel": False,
            "leitor_modo_ampliado": True,
            "caminho_exportacao": str(config_atual.get("caminho_exportacao") or EXPORTS_PADRAO),
            "caminho_biblioteca": str(config_atual.get("caminho_biblioteca") or ""),
        }
        salvar_configuracoes({**config_atual, **atualizacoes})
        return jsonify({"ok": True})

    @app.post("/projetos/<slug>/atualizar")
    @registrar_etapa
    def rota_atualizar_projeto(slug: str):
        """
        Aplica alterações controladas sobre dados já existentes sem recriar estruturas desnecessariamente.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            A estrutura atualizada depois da aplicação das mudanças.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        projeto_atual = obter_projeto(slug)
        try:
            campos = _validar_campos_projeto(
                titulo=request.form.get("titulo", ""),
                descricao=request.form.get("descricao", ""),
                autor=request.form.get("autor", ""),
                tipo=projeto_atual.get("tipo") or "livro",
                tags_str=request.form.get("tags", ""),
                contatos=request.form.get("contatos", ""),
                informacoes_adicionais=request.form.get("informacoes_adicionais", ""),
            )
        except ValueError as erro:
            return jsonify({"ok": False, "erro": str(erro)}), 400
        atualizacoes = {
            "titulo": campos["titulo"],
            "descricao": campos["descricao"],
            "autor": campos["autor"],
            "idioma": normalizar_idioma_projeto(request.form.get("idioma", "pt-BR").strip() or "pt-BR"),
        }
        if projeto_atual.get("tipo") == "roteiro":
            atualizacoes.update({
                "contatos": campos["contatos"],
                "informacoes_adicionais": campos["informacoes_adicionais"],
                "tags": [],
            })
        else:
            atualizacoes.update({"tags": campos["tags"], "contatos": campos["contatos"]})
        atualizar_metadados_projeto(slug, atualizacoes)
        return jsonify({"ok": True})

    @app.get("/projetos/<slug>/cover.jpg")
    @registrar_etapa
    def obter_capa(slug: str):
        """
        Localiza e devolve um dado ou recurso específico, aplicando as validações necessárias antes do retorno.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            O recurso solicitado ou uma estrutura com os dados encontrados.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        return send_file(obter_pasta_projeto(slug) / "cover.jpg")

    @app.post("/projetos/<slug>/cover")
    @registrar_etapa
    def rota_salvar_capa(slug: str):
        """
        Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        projeto = obter_projeto(slug)
        if projeto.get("tipo") != "livro":
            return jsonify({"ok": False, "erro": t('backend.script_projects_no_cover')}), 400
        arquivo = request.files.get("cover")
        if not arquivo or not arquivo.filename:
            return jsonify({"ok": False, "erro": t("backend.no_image_sent")}), 400
        with NamedTemporaryFile(delete=False, suffix=Path(arquivo.filename).suffix or ".img") as tmp:
            arquivo.save(tmp.name)
            salvar_capa_projeto(slug, Path(tmp.name))
        return jsonify({"ok": True, "url": f"/projetos/{slug}/cover.jpg?ts=1"})

    @app.post("/projetos/<slug>/capitulos/criar")
    @registrar_etapa
    def rota_criar_capitulo(slug: str):
        """
        Cria um novo registro, arquivo ou estrutura interna mantendo o padrão de armazenamento do projeto.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            Os dados do novo item criado, incluindo identificadores gerados quando existirem.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        try:
            titulo = _validar_titulo_capitulo(request.form.get("titulo", ""))
        except ValueError as erro:
            return jsonify({"ok": False, "erro": str(erro)}), 400
        pasta = obter_pasta_projeto(slug)
        capitulo = criar_capitulo(pasta, titulo)
        atualizar_data_projeto(slug)
        return jsonify({"ok": True, "redirect": url_for("editar_capitulo", slug=slug, numero=capitulo["id"])})

    @app.post("/projetos/<slug>/capitulos/<int:numero>/excluir")
    @registrar_etapa
    def rota_excluir_capitulo(slug: str, numero: int):
        """
        Remove o item indicado e executa os cuidados necessários para manter o restante do projeto consistente.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
    
        Retorno:
            None. A função sinaliza falhas por exceção quando a remoção não pode ser concluída.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        pasta = obter_pasta_projeto(slug)
        excluir_capitulo(pasta, numero)
        atualizar_data_projeto(slug)
        return jsonify({"ok": True})

    @app.get("/projetos/<slug>/continuar")
    @registrar_etapa
    def rota_continuar_projeto(slug: str):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        projeto = obter_projeto(slug)
        if projeto.get("tipo") == "roteiro":
            return redirect(url_for("pagina_roteiro", slug=slug))
        ultimo = projeto.get("ultimo_lido")
        if ultimo:
            return redirect(url_for("ler_capitulo_view", slug=slug, numero=ultimo))
        if projeto.get("capitulos"):
            return redirect(url_for("ler_capitulo_view", slug=slug, numero=projeto["capitulos"][0]["id"]))
        return redirect(url_for("pagina_projeto", slug=slug))

    @app.get("/projetos/<slug>/capitulos/<int:numero>/editar")
    @registrar_etapa
    def editar_capitulo(slug: str, numero: int):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        projeto = obter_projeto(slug)
        if projeto.get("tipo") == "roteiro":
            return redirect(url_for("editar_roteiro_view", slug=slug, numero=numero))
        capitulo = ler_capitulo(obter_pasta_projeto(slug), numero)
        return render_template("editor.html", projeto=projeto, capitulo=capitulo, numero=numero)

    @app.get("/projetos/<slug>/capitulos/<int:numero>/ler")
    @registrar_etapa
    def ler_capitulo_view(slug: str, numero: int):
        """
        Lê conteúdo persistido e devolve dados estruturados para consumo pelo restante da aplicação.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
    
        Retorno:
            Conteúdo estruturado lido a partir da origem informada.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        projeto = obter_projeto(slug)
        if projeto.get("tipo") == "roteiro":
            return redirect(url_for("pagina_roteiro", slug=slug))
        registrar_ultimo_lido(slug, numero)
        posicao_inicial = int((projeto.get("posicoes_leitura") or {}).get(str(numero), 0) or 0)
        capitulo = ler_capitulo(obter_pasta_projeto(slug), numero)
        capitulos = projeto.get("capitulos", [])
        indice_atual = next((i for i, item in enumerate(capitulos) if item.get("id") == numero), None)
        capitulo_anterior = capitulos[indice_atual - 1] if indice_atual not in (None, 0) else None
        proximo_capitulo = capitulos[indice_atual + 1] if indice_atual is not None and indice_atual < len(capitulos) - 1 else None
        return render_template(
            "leitor.html",
            projeto=projeto,
            capitulo=capitulo,
            numero=numero,
            capitulo_anterior=capitulo_anterior,
            proximo_capitulo=proximo_capitulo,
            posicao_inicial=posicao_inicial,
        )

    @app.post("/api/projetos/<slug>/capitulos/<int:numero>/posicao")
    @registrar_etapa
    def api_salvar_posicao_leitura(slug: str, numero: int):
        """
        Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
    
        Retorno:
            A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        dados = request.get_json(silent=True) or {}
        registrar_posicao_leitura(slug, numero, int(dados.get("posicao") or 0))
        return jsonify({"ok": True})

    @app.post("/api/projetos/<slug>/capitulos/<int:numero>/autosave")
    @registrar_etapa
    def api_autosave(slug: str, numero: int):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        dados = request.get_json(silent=True) or {}
        titulo = _texto_normalizado(dados.get("titulo") or "")
        html = dados.get("html") or "<p></p>"
        try:
            pasta = obter_pasta_projeto(slug)
            projeto = obter_projeto(slug)
            if projeto.get("tipo") == "roteiro":
                titulo = titulo.upper() or t("script.untitled")
                capitulo = salvar_roteiro(pasta, numero, titulo, html)
            else:
                titulo = _validar_titulo_capitulo(titulo)
                capitulo = salvar_capitulo(pasta, numero, titulo, html)
            atualizar_data_projeto(slug)
            return jsonify({"ok": True, "mensagem": t("js.saved"), "data_atualizacao": capitulo.get("data_atualizacao")})
        except Exception as erro:
            return jsonify({"ok": False, "erro": str(erro)}), 500

    @app.post("/projetos/<slug>/roteiros/criar")
    @registrar_etapa
    def rota_criar_roteiro(slug: str):
        """
        Cria um novo registro, arquivo ou estrutura interna mantendo o padrão de armazenamento do projeto.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            Os dados do novo item criado, incluindo identificadores gerados quando existirem.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        pasta = obter_pasta_projeto(slug)
        try:
            campos = _validar_campos_roteiro(
                titulo=request.form.get("titulo", "") or t("script.new_script_default"),
                cabecalho=request.form.get("cabecalho", ""),
                rodape=request.form.get("rodape", ""),
                prefixo_cena=request.form.get("prefixo_cena", "0"),
                numeracao_inicial=request.form.get("numeracao_inicial") or 1,
                logline=request.form.get("logline", ""),
                sinopse=request.form.get("sinopse", ""),
                genero=request.form.get("genero", ""),
            )
        except ValueError as erro:
            return jsonify({"ok": False, "erro": str(erro)}), 400
        roteiro = criar_roteiro(
            pasta,
            str(campos["titulo"]),
            cabecalho=str(campos["cabecalho"]),
            rodape=str(campos["rodape"]),
            prefixo_cena=str(campos["prefixo_cena"]),
            numeracao_inicial=int(campos["numeracao_inicial"]),
            logline=str(campos["logline"]),
            sinopse=str(campos["sinopse"]),
            genero=str(campos["genero"]),
            tipo_roteiro=request.form.get("tipo_roteiro", "spec_script").strip(),
            copyright=request.form.get("copyright") == "on",
        )
        atualizar_data_projeto(slug)
        return jsonify({"ok": True, "redirect": url_for("editar_roteiro_view", slug=slug, numero=roteiro["id"])})

    @app.post("/projetos/<slug>/roteiros/<int:numero>/excluir")
    @registrar_etapa
    def rota_excluir_roteiro(slug: str, numero: int):
        """
        Remove o item indicado e executa os cuidados necessários para manter o restante do projeto consistente.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
    
        Retorno:
            None. A função sinaliza falhas por exceção quando a remoção não pode ser concluída.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        pasta = obter_pasta_projeto(slug)
        excluir_roteiro(pasta, numero)
        atualizar_data_projeto(slug)
        return jsonify({"ok": True})

    @app.get("/projetos/<slug>/roteiros/<int:numero>/editar")
    @registrar_etapa
    def editar_roteiro_view(slug: str, numero: int):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        projeto = obter_projeto(slug)
        roteiro = ler_roteiro(obter_pasta_projeto(slug), numero)
        roteiro["tipo_roteiro_label"] = t(f"script_type.{roteiro.get('tipo_roteiro') or 'spec_script'}", default=str(roteiro.get("tipo_roteiro_label") or t("script.spec_script")))
        return render_template("editor_roteiro.html", projeto=projeto, roteiro=roteiro, numero=numero, tipos_roteiro=_tipos_roteiro_localizados())

    @app.post("/projetos/<slug>/roteiros/<int:numero>/atualizar")
    @registrar_etapa
    def rota_atualizar_roteiro(slug: str, numero: int):
        """
        Aplica alterações controladas sobre dados já existentes sem recriar estruturas desnecessariamente.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
    
        Retorno:
            A estrutura atualizada depois da aplicação das mudanças.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        pasta = obter_pasta_projeto(slug)
        try:
            campos = _validar_campos_roteiro(
                titulo=request.form.get("titulo", "") or t("script.script_default_with_number", number=numero),
                cabecalho=request.form.get("cabecalho", ""),
                rodape=request.form.get("rodape", ""),
                prefixo_cena=request.form.get("prefixo_cena", "0"),
                numeracao_inicial=request.form.get("numeracao_inicial") or 1,
                logline=request.form.get("logline", ""),
                sinopse=request.form.get("sinopse", ""),
                genero=request.form.get("genero", ""),
            )
        except ValueError as erro:
            return jsonify({"ok": False, "erro": str(erro)}), 400
        atualizacoes = {
            **campos,
            "tipo_roteiro": request.form.get("tipo_roteiro", "spec_script").strip(),
            "copyright": request.form.get("copyright") == "on",
        }
        atualizar_roteiro_info(pasta, numero, atualizacoes)
        atualizar_data_projeto(slug)
        return jsonify({"ok": True})

    @app.post("/projetos/<slug>/roteiros/<int:numero>/personagens")
    @registrar_etapa
    def rota_personagens_roteiro(slug: str, numero: int):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        pasta = obter_pasta_projeto(slug)
        atualizar_roteiro_info(pasta, numero, {"personagens": request.form.get("personagens", "")})
        atualizar_data_projeto(slug)
        return jsonify({"ok": True})

    @app.post("/projetos/<slug>/roteiros/<int:numero>/locais")
    @registrar_etapa
    def rota_locais_roteiro(slug: str, numero: int):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        pasta = obter_pasta_projeto(slug)
        atualizar_roteiro_info(pasta, numero, {"locais": request.form.get("locais", "")})
        atualizar_data_projeto(slug)
        return jsonify({"ok": True})



    @app.get("/api/projetos/<slug>/roteiros/<int:numero>/catalogo")
    @registrar_etapa
    def api_catalogo_roteiro(slug: str, numero: int):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        roteiro = ler_roteiro(obter_pasta_projeto(slug), numero)
        return jsonify({
            "ok": True,
            "personagens": roteiro.get("catalogo_personagens", []),
            "locais": roteiro.get("catalogo_locais", []),
        })

    @app.post("/api/projetos/<slug>/roteiros/<int:numero>/catalogo/<tipo>")
    @registrar_etapa
    def api_salvar_item_catalogo_roteiro(slug: str, numero: int, tipo: str):
        """
        Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
            tipo: Valor usado pela rotina para compor a operação de api salvar item catalogo roteiro.
    
        Retorno:
            A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        if tipo not in {"personagens", "locais"}:
            return jsonify({"ok": False, "erro": t('backend.invalid_catalog_type')}), 400
        dados = request.get_json(silent=True) or {}
        try:
            nome, descricao = _validar_item_catalogo(dados.get("nome"), dados.get("descricao"))
        except ValueError as erro:
            return jsonify({"ok": False, "erro": str(erro)}), 400
        pasta = obter_pasta_projeto(slug)
        roteiro = ler_roteiro(pasta, numero)
        chave = "catalogo_personagens" if tipo == "personagens" else "catalogo_locais"
        itens = list(roteiro.get(chave) or [])
        atualizado = False
        for item in itens:
            if str(item.get("nome", "")).strip().lower() == nome.lower():
                item["nome"] = nome
                item["descricao"] = descricao
                item.pop("imagem", None)
                atualizado = True
                break
        if not atualizado:
            itens.append({"nome": nome, "descricao": descricao})
        atualizar_roteiro_info(pasta, numero, {chave: itens})
        atualizar_data_projeto(slug)
        return jsonify({"ok": True, "itens": itens})

    @app.post("/api/projetos/<slug>/roteiros/<int:numero>/catalogo/<tipo>/excluir")
    @registrar_etapa
    def api_excluir_item_catalogo_roteiro(slug: str, numero: int, tipo: str):
        """
        Remove o item indicado e executa os cuidados necessários para manter o restante do projeto consistente.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
            tipo: Valor usado pela rotina para compor a operação de api excluir item catalogo roteiro.
    
        Retorno:
            None. A função sinaliza falhas por exceção quando a remoção não pode ser concluída.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        if tipo not in {"personagens", "locais"}:
            return jsonify({"ok": False, "erro": t('backend.invalid_catalog_type')}), 400
        dados = request.get_json(silent=True) or {}
        nome = (dados.get("nome") or "").strip()
        pasta = obter_pasta_projeto(slug)
        roteiro = ler_roteiro(pasta, numero)
        chave = "catalogo_personagens" if tipo == "personagens" else "catalogo_locais"
        itens = [item for item in list(roteiro.get(chave) or []) if str(item.get("nome", "")).strip().lower() != nome.lower()]
        atualizar_roteiro_info(pasta, numero, {chave: itens})
        atualizar_data_projeto(slug)
        return jsonify({"ok": True, "itens": itens})

    @app.get("/api/projetos/<slug>/catalogo")
    @registrar_etapa
    def api_catalogo_projeto(slug: str):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        projeto = obter_projeto(slug)
        return jsonify({
            "ok": True,
            "personagens": projeto.get("catalogo_personagens", []),
            "locais": projeto.get("catalogo_locais", []),
        })

    @app.post("/api/projetos/<slug>/catalogo/<tipo>")
    @registrar_etapa
    def api_salvar_item_catalogo(slug: str, tipo: str):
        """
        Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
            tipo: Valor usado pela rotina para compor a operação de api salvar item catalogo.
    
        Retorno:
            A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        if tipo not in {"personagens", "locais"}:
            return jsonify({"ok": False, "erro": t('backend.invalid_catalog_type')}), 400
        dados = request.get_json(silent=True) or {}
        try:
            nome, descricao = _validar_item_catalogo(dados.get("nome"), dados.get("descricao"))
        except ValueError as erro:
            return jsonify({"ok": False, "erro": str(erro)}), 400
        projeto = obter_projeto(slug)
        chave = "catalogo_personagens" if tipo == "personagens" else "catalogo_locais"
        itens = list(projeto.get(chave) or [])
        atualizado = False
        for item in itens:
            if str(item.get("nome", "")).strip().lower() == nome.lower():
                item["nome"] = nome
                item["descricao"] = descricao
                item.pop("imagem", None)
                atualizado = True
                break
        if not atualizado:
            itens.append({"nome": nome, "descricao": descricao})
        atualizar_metadados_projeto(slug, {chave: itens})
        return jsonify({"ok": True, "itens": itens})

    @app.post("/api/projetos/<slug>/catalogo/<tipo>/excluir")
    @registrar_etapa
    def api_excluir_item_catalogo(slug: str, tipo: str):
        """
        Remove o item indicado e executa os cuidados necessários para manter o restante do projeto consistente.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
            tipo: Valor usado pela rotina para compor a operação de api excluir item catalogo.
    
        Retorno:
            None. A função sinaliza falhas por exceção quando a remoção não pode ser concluída.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        if tipo not in {"personagens", "locais"}:
            return jsonify({"ok": False, "erro": t('backend.invalid_catalog_type')}), 400
        dados = request.get_json(silent=True) or {}
        nome = (dados.get("nome") or "").strip()
        projeto = obter_projeto(slug)
        chave = "catalogo_personagens" if tipo == "personagens" else "catalogo_locais"
        itens = [item for item in list(projeto.get(chave) or []) if str(item.get("nome", "")).strip().lower() != nome.lower()]
        atualizar_metadados_projeto(slug, {chave: itens})
        return jsonify({"ok": True, "itens": itens})

    @app.get("/projetos/<slug>/salvar-capitulos")
    @registrar_etapa
    def rota_salvar_capitulos(slug: str):
        """
        Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        try:
            arquivo = exportar_gut_capitulos(slug)
            return _resposta_arquivo_exportado(arquivo)
        except FileNotFoundError as exc:
            return _resposta_erro_json(str(exc), 404)
        except ValueError as exc:
            return _resposta_erro_json(str(exc), 400)
        except Exception as exc:
            return _resposta_erro_json(str(exc), 500)

    @app.get("/projetos/<slug>/salvar-roteiro")
    @registrar_etapa
    def rota_salvar_roteiro_gut(slug: str):
        """
        Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        numero_roteiro = request.args.get("roteiro", type=int)
        try:
            arquivo = exportar_gut_roteiro(slug, numero_roteiro)
            return _resposta_arquivo_exportado(arquivo)
        except FileNotFoundError as exc:
            return _resposta_erro_json(str(exc), 404)
        except ValueError as exc:
            return _resposta_erro_json(str(exc), 400)
        except Exception as exc:
            return _resposta_erro_json(str(exc), 500)

    @app.post("/projetos/<slug>/importar-gut")
    @registrar_etapa
    def rota_importar_gut(slug: str):
        """
        Coordena a importação de conteúdo externo para dentro do projeto, normalizando os dados para o modelo usado pela aplicação.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            Um resumo do conteúdo importado e dos registros criados no projeto.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        arquivo = request.files.get("arquivo")
        if not arquivo or not arquivo.filename:
            return _resposta_erro_json(t("backend.no_gut_file_sent"), 400)
        if Path(str(arquivo.filename)).suffix.lower() not in {".gut", ".docx", ".pdf", ".txt"}:
            return _resposta_erro_json("Formato inválido. Use .gut, .docx, .pdf ou .txt.", 400)
        caminho_tmp = _salvar_upload_temporario_gut(arquivo)
        try:
            if caminho_tmp.suffix.lower() == ".gut":
                payload = ler_payload_gut(caminho_tmp)
                projeto = obter_projeto(slug)
                if projeto.get("tipo") != _resolver_tipo_projeto_esperado(payload.get("tipo_arquivo")):
                    return _resposta_erro_json(t("backend.gut_type_incompatible"), 400)
            return jsonify(_importar_arquivo_por_caminho(slug, caminho_tmp))
        except FileNotFoundError as exc:
            return _resposta_erro_json(str(exc), 404)
        except ValueError as exc:
            return _resposta_erro_json(str(exc), 400)
        except Exception as exc:
            return _resposta_erro_json(str(exc), 500)
        finally:
            try:
                pasta_tmp = caminho_tmp.parent
                caminho_tmp.unlink(missing_ok=True)
                if pasta_tmp.name.startswith("gutenberg_import_"):
                    pasta_tmp.rmdir()
            except Exception:
                pass

    @app.post("/projetos/<slug>/importar-gut-desktop")
    @registrar_etapa
    def rota_importar_gut_desktop(slug: str):
        """
        Coordena a importação de conteúdo externo para dentro do projeto, normalizando os dados para o modelo usado pela aplicação.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            Um resumo do conteúdo importado e dos registros criados no projeto.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        dados = request.get_json(silent=True) or {}
        caminho = Path(str(dados.get("caminho") or "").strip()).expanduser()
        if not str(caminho):
            return _resposta_erro_json(t("backend.no_gut_file_sent"), 400)
        if caminho.suffix.lower() not in {".gut", ".docx", ".pdf", ".txt"}:
            return _resposta_erro_json("Formato inválido. Use .gut, .docx, .pdf ou .txt.", 400)
        try:
            if caminho.suffix.lower() == ".gut":
                payload = ler_payload_gut(caminho)
                projeto = obter_projeto(slug)
                if projeto.get("tipo") != _resolver_tipo_projeto_esperado(payload.get("tipo_arquivo")):
                    return _resposta_erro_json(t("backend.gut_type_incompatible"), 400)
            return jsonify(_importar_arquivo_por_caminho(slug, caminho))
        except FileNotFoundError as exc:
            return _resposta_erro_json(str(exc), 404)
        except ValueError as exc:
            return _resposta_erro_json(str(exc), 400)
        except Exception as exc:
            return _resposta_erro_json(str(exc), 500)

    @app.post("/api/gut/pendente/registrar")
    @registrar_etapa
    def rota_registrar_gut_pendente():
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
        dados = request.get_json(silent=True) or {}
        caminho = str(dados.get("caminho") or "").strip()
        try:
            contexto = _registrar_gut_pendente(app, caminho)
            return jsonify({"ok": True, "contexto": contexto})
        except FileNotFoundError as exc:
            return _resposta_erro_json(str(exc), 404)
        except ValueError as exc:
            return _resposta_erro_json(str(exc), 400)
        except Exception as exc:
            return _resposta_erro_json(str(exc), 500)

    @app.get("/api/gut/pendente/contexto")
    @registrar_etapa
    def rota_contexto_gut_pendente():
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
        contexto = _obter_contexto_gut_pendente(app)
        return jsonify({"ok": True, "contexto": contexto or {}})

    @app.post("/api/gut/pendente/importar")
    @registrar_etapa
    def rota_importar_gut_pendente():
        """
        Coordena a importação de conteúdo externo para dentro do projeto, normalizando os dados para o modelo usado pela aplicação.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Retorno:
            Um resumo do conteúdo importado e dos registros criados no projeto.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        contexto = _obter_contexto_gut_pendente(app)
        if not contexto or contexto.get("erro"):
            return _resposta_erro_json(t("backend.no_pending_gut"), 400)
        slug = str((request.get_json(silent=True) or {}).get("slug") or "").strip()
        if not slug:
            return _resposta_erro_json(t("backend.project_not_found"), 400)
        try:
            projeto = obter_projeto(slug)
            if projeto.get("tipo") != contexto.get("tipo_projeto"):
                return _resposta_erro_json(t("backend.gut_type_incompatible"), 400)
            resposta = _importar_gut_por_caminho(slug, contexto["caminho"])
            _limpar_gut_pendente(app)
            return jsonify(resposta)
        except Exception as exc:
            return _resposta_erro_json(str(exc), 400)

    @app.post("/api/gut/pendente/criar-e-importar")
    @registrar_etapa
    def rota_criar_e_importar_gut_pendente():
        """
        Coordena a importação de conteúdo externo para dentro do projeto, normalizando os dados para o modelo usado pela aplicação.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Retorno:
            Os dados do novo item criado, incluindo identificadores gerados quando existirem.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        contexto = _obter_contexto_gut_pendente(app)
        if not contexto or contexto.get("erro"):
            return _resposta_erro_json(t("backend.no_pending_gut"), 400)
        tipo = str(contexto.get("tipo_projeto") or "livro")
        idioma = normalizar_idioma_projeto(request.form.get("idioma", "pt-BR").strip() or "pt-BR")
        try:
            campos = _validar_campos_projeto(
                titulo=request.form.get("titulo", ""),
                descricao=request.form.get("descricao", ""),
                autor=request.form.get("autor", ""),
                tipo=tipo,
                tags_str=request.form.get("tags", ""),
                contatos=request.form.get("contatos", ""),
                informacoes_adicionais=request.form.get("informacoes_adicionais", ""),
            )
            projeto = criar_projeto(campos["titulo"], campos["descricao"], campos["autor"], campos["tags"], idioma, tipo=tipo, contatos=campos["contatos"], informacoes_adicionais=campos["informacoes_adicionais"])
            resposta = _importar_gut_por_caminho(projeto["slug"], contexto["caminho"])
            atualizar_metadados_projeto(projeto["slug"], {
                "titulo": campos["titulo"],
                "descricao": campos["descricao"],
                "autor": campos["autor"],
                "idioma": idioma,
                "tags": campos["tags"] if tipo != "roteiro" else [],
                "contatos": campos["contatos"],
                "informacoes_adicionais": campos["informacoes_adicionais"] if tipo == "roteiro" else "",
            })
            _limpar_gut_pendente(app)
            return jsonify(resposta)
        except ValueError as erro:
            return _resposta_erro_json(str(erro), 400)
        except FileExistsError as erro:
            return _resposta_erro_json(str(erro), 400)

    @app.get("/projetos/<slug>/exportar")
    @registrar_etapa
    def rota_exportar(slug: str):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            slug: Identificador amigável do projeto, livro ou recurso que será manipulado.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        projeto = obter_projeto(slug)
        formato = request.args.get("formato", "epub")
        versao = request.args.get("versao", "2.0")
        if projeto.get("tipo") == "roteiro":
            numero_roteiro = request.args.get("roteiro")
            try:
                numero_roteiro = int(numero_roteiro) if numero_roteiro not in {None, ""} else None
            except ValueError:
                return jsonify({"ok": False, "erro": t('backend.invalid_script_for_export')}), 400
            if numero_roteiro is None:
                return jsonify({"ok": False, "erro": t('backend.select_script_to_export')}), 400
            tipo_documento = request.args.get("tipo_documento", "roteiro")
            if formato == "docx":
                try:
                    arquivo = exportar_roteiro_docx(slug, numero_roteiro, tipo_documento)
                except ValueError as exc:
                    return jsonify({"ok": False, "erro": str(exc)}), 400
                atualizar_metadados_projeto(slug, {})
                return _resposta_arquivo_exportado(arquivo)
            if formato == "pdf":
                try:
                    arquivo = exportar_roteiro_pdf(slug, numero_roteiro, tipo_documento)
                except ValueError as exc:
                    return jsonify({"ok": False, "erro": str(exc)}), 400
                atualizar_metadados_projeto(slug, {})
                return _resposta_arquivo_exportado(arquivo)
            return jsonify({"ok": False, "erro": t('backend.scripts_export_docx_pdf_only')}), 400
        if formato == "xhtml":
            pasta = exportar_projeto_xhtml(slug)
            return jsonify({"ok": True, "mensagem": t('backend.xhtml_exported_in', folder=pasta)})
        if formato == "docx":
            arquivo = exportar_projeto_docx(slug)
            atualizar_metadados_projeto(slug, {})
            return _resposta_arquivo_exportado(arquivo)
        if formato == "pdf":
            arquivo = exportar_projeto_pdf(slug)
            atualizar_metadados_projeto(slug, {})
            return _resposta_arquivo_exportado(arquivo)
        arquivo = exportar_projeto_epub(slug, versao)
        atualizar_metadados_projeto(slug, {})
        return _resposta_arquivo_exportado(arquivo)

    @app.get("/saude")
    @registrar_etapa
    def saude():
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
        return {"status": "ok"}

    return app
