"""
Persistência local em SQLite para projetos, capítulos, roteiros e dados auxiliares do editor.

"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from .logging_config import obter_logger, registrar_etapa
logger = obter_logger(__name__)

_DB_LOCKS: dict[Path, threading.RLock] = {}
_DB_LOCKS_GUARD = threading.Lock()
_DB_INIT_DONE: set[Path] = set()
_DB_INIT_GUARD = threading.Lock()
NOME_BANCO = "editor_local.db"
SCHEMA_VERSION = 3
_HTML_CAPITULO_PADRAO = "<p><br></p>"
_HTML_ROTEIRO_PADRAO = '<div class="roteiro-bloco" data-block-type="neutral" data-initial-neutral="true"><br></div>'


@registrar_etapa
def fechar_conexoes_banco_editor(pasta_projeto: Path | str) -> None:
    """
    Encerra um fluxo ou recurso de maneira controlada.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pasta_projeto: Pasta raiz do projeto em que os dados relacionados serão lidos ou gravados.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    caminho_banco = Path(pasta_projeto) / NOME_BANCO
    if not caminho_banco.exists():
        return
    try:
        con = sqlite3.connect(caminho_banco, timeout=2.0)
        try:
            con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            con.commit()
        finally:
            con.close()
    except Exception:
        pass


@registrar_etapa
def limpar_estado_banco_editor(pasta_projeto: Path | str) -> None:
    """
    Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.

    A função isola esta responsabilidade para deixar o fluxo principal mais fácil
    de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
    normalizações ou verificações necessárias e entrega um resultado previsível
    para a próxima camada do sistema.

    Parâmetros:
        pasta_projeto: Pasta raiz do projeto em que os dados relacionados serão lidos ou gravados.

    Retorno:
        O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.

    Observações:
        Mantém a lógica centralizada e evita que detalhes de implementação vazem
        para quem apenas precisa acionar este comportamento.
    """
    pasta_projeto = Path(pasta_projeto)
    caminho_banco = pasta_projeto / NOME_BANCO
    fechar_conexoes_banco_editor(pasta_projeto)
    with _DB_INIT_GUARD:
        _DB_INIT_DONE.discard(caminho_banco)
    with _DB_LOCKS_GUARD:
        _DB_LOCKS.pop(caminho_banco, None)

    try:
        from . import manipulador_capitulos, manipulador_roteiros, manipulador_recursos_projeto

        manipulador_capitulos._DB_CACHE.pop(pasta_projeto, None)
        manipulador_roteiros._DB_CACHE.pop(pasta_projeto, None)
        manipulador_recursos_projeto._DB_CACHE.pop(pasta_projeto, None)
    except Exception:
        pass


class BancoEditorLocal:
    """
    Representa BancoEditorLocal dentro do fluxo da aplicação.

    Esta classe concentra estado e comportamentos relacionados para evitar que a
    lógica fique espalhada por vários pontos do código. A intenção é oferecer uma
    interface simples para quem consome o módulo, escondendo os detalhes internos
    de organização, validação e integração com os demais componentes.
    """
    @registrar_etapa
    def __init__(self, pasta_projeto: Path):
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            pasta_projeto: Pasta raiz do projeto em que os dados relacionados serão lidos ou gravados.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        self.pasta_projeto = Path(pasta_projeto)
        self.caminho_banco = self.pasta_projeto / NOME_BANCO
        with _DB_LOCKS_GUARD:
            self._lock = _DB_LOCKS.setdefault(self.caminho_banco, threading.RLock())
        self._garantir_banco_inicializado()

    @contextmanager
    @registrar_etapa
    def conexao(self) -> Iterator[sqlite3.Connection]:
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
        with self._lock:
            ultimo_erro: Exception | None = None
            for tentativa in range(6):
                con: sqlite3.Connection | None = None
                try:
                    con = sqlite3.connect(self.caminho_banco, timeout=10.0)
                    self._configurar_conexao(con)
                    yield con
                    return
                except sqlite3.OperationalError as erro:
                    ultimo_erro = erro
                    if con is not None:
                        self._rollback_silencioso(con)
                    mensagem = str(erro).lower()
                    if "locked" not in mensagem and "busy" not in mensagem:
                        raise
                    if tentativa == 5:
                        raise
                    time.sleep(0.05 * (tentativa + 1))
                except Exception:
                    if con is not None:
                        self._rollback_silencioso(con)
                    raise
                finally:
                    if con is not None:
                        try:
                            con.close()
                        except Exception:
                            pass
            if ultimo_erro:
                raise ultimo_erro

    @registrar_etapa
    def _garantir_banco_inicializado(self) -> None:
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
        self.pasta_projeto.mkdir(parents=True, exist_ok=True)
        with _DB_INIT_GUARD:
            if self.caminho_banco in _DB_INIT_DONE and self._schema_banco_esta_pronto():
                return
            con = sqlite3.connect(self.caminho_banco, timeout=10.0)
            try:
                self._configurar_conexao(con)
                self._inicializar_ou_migrar_schema(con)
                con.commit()
                _DB_INIT_DONE.add(self.caminho_banco)
            finally:
                con.close()

    @registrar_etapa
    def _schema_banco_esta_pronto(self) -> bool:
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
        if not self.caminho_banco.exists():
            return False
        try:
            con = sqlite3.connect(self.caminho_banco, timeout=2.0)
            try:
                tabelas = {
                    str(row[0])
                    for row in con.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('chapters', 'scripts', 'project_info_pages', 'project_flow_nodes', 'project_resource_catalog')"
                    ).fetchall()
                }
                return {'chapters', 'scripts', 'project_info_pages', 'project_flow_nodes', 'project_resource_catalog'}.issubset(tabelas)
            finally:
                con.close()
        except Exception:
            return False

    @staticmethod
    @registrar_etapa
    def _configurar_conexao(con: sqlite3.Connection) -> None:
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            con: Valor usado pela rotina para compor a operação de configurar conexao.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA temp_store=MEMORY")
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA cache_size=-20000")
        con.execute("PRAGMA mmap_size=268435456")
        con.execute("PRAGMA busy_timeout=10000")

    @registrar_etapa
    def _inicializar_ou_migrar_schema(self, con: sqlite3.Connection) -> None:
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            con: Valor usado pela rotina para compor a operação de inicializar ou migrar schema.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        versao = int(con.execute("PRAGMA user_version").fetchone()[0] or 0)
        self._criar_tabelas_base(con)
        if versao < 2:
            self._migrar_schema_v2(con)
        con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @registrar_etapa
    def _criar_tabelas_base(self, con: sqlite3.Connection) -> None:
        """
        Cria um novo registro, arquivo ou estrutura interna mantendo o padrão de armazenamento do projeto.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            con: Valor usado pela rotina para compor a operação de criar tabelas base.
    
        Retorno:
            Os dados do novo item criado, incluindo identificadores gerados quando existirem.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                html TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS scripts (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                html TEXT NOT NULL,
                header TEXT NOT NULL DEFAULT '',
                footer TEXT NOT NULL DEFAULT '',
                scene_prefix TEXT NOT NULL DEFAULT '0',
                start_number INTEGER NOT NULL DEFAULT 1,
                logline TEXT NOT NULL DEFAULT '',
                synopsis TEXT NOT NULL DEFAULT '',
                genre TEXT NOT NULL DEFAULT '',
                script_type TEXT NOT NULL DEFAULT 'spec_script',
                copyright_enabled INTEGER NOT NULL DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS script_characters (
                script_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                name TEXT NOT NULL,
                PRIMARY KEY (script_id, position),
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS script_locations (
                script_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                name TEXT NOT NULL,
                PRIMARY KEY (script_id, position),
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS script_character_catalog (
                script_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (script_id, position),
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS script_location_catalog (
                script_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (script_id, position),
                FOREIGN KEY (script_id) REFERENCES scripts(id) ON DELETE CASCADE
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_chapters_updated_at ON chapters(updated_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_scripts_updated_at ON scripts(updated_at DESC)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_script_characters_script_id ON script_characters(script_id, position)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_script_locations_script_id ON script_locations(script_id, position)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_script_character_catalog_script_id ON script_character_catalog(script_id, position)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_script_location_catalog_script_id ON script_location_catalog(script_id, position)")
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS project_resource_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS project_info_pages (
                id TEXT PRIMARY KEY,
                position INTEGER NOT NULL DEFAULT 0,
                title TEXT NOT NULL,
                html TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS project_flow_nodes (
                id TEXT PRIMARY KEY,
                x REAL NOT NULL DEFAULT 120,
                y REAL NOT NULL DEFAULT 120,
                width REAL NOT NULL DEFAULT 240,
                height REAL NOT NULL DEFAULT 150,
                title TEXT NOT NULL DEFAULT '',
                text TEXT NOT NULL DEFAULT '',
                position INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS project_flow_edges (
                id TEXT PRIMARY KEY,
                from_node_id TEXT NOT NULL,
                to_node_id TEXT NOT NULL,
                from_side TEXT NOT NULL DEFAULT 'right',
                to_side TEXT NOT NULL DEFAULT 'left',
                position INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (from_node_id) REFERENCES project_flow_nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (to_node_id) REFERENCES project_flow_nodes(id) ON DELETE CASCADE
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS project_resource_catalog (
                type TEXT NOT NULL,
                id TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                image TEXT NOT NULL DEFAULT '',
                created_at TEXT,
                updated_at TEXT,
                PRIMARY KEY (type, id)
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS project_resource_hidden (
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                PRIMARY KEY (type, name)
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_project_info_pages_position ON project_info_pages(position)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_project_flow_nodes_position ON project_flow_nodes(position)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_project_flow_edges_position ON project_flow_edges(position)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_project_resource_catalog_type_position ON project_resource_catalog(type, position)")
        con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_project_resource_catalog_type_name ON project_resource_catalog(type, lower(name))")
        con.execute("CREATE INDEX IF NOT EXISTS idx_project_resource_hidden_type ON project_resource_hidden(type)")

    @registrar_etapa
    def _migrar_schema_v2(self, con: sqlite3.Connection) -> None:
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            con: Valor usado pela rotina para compor a operação de migrar schema v2.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        colunas_scripts = {row[1] for row in con.execute("PRAGMA table_info(scripts)").fetchall()}
        if "characters_json" not in colunas_scripts and "locations_json" not in colunas_scripts:
            return

        possui_dados_relacionais = con.execute(
            "SELECT EXISTS(SELECT 1 FROM script_characters LIMIT 1) OR EXISTS(SELECT 1 FROM script_locations LIMIT 1) "
            "OR EXISTS(SELECT 1 FROM script_character_catalog LIMIT 1) OR EXISTS(SELECT 1 FROM script_location_catalog LIMIT 1)"
        ).fetchone()[0]
        if possui_dados_relacionais:
            return

        rows = con.execute("SELECT * FROM scripts ORDER BY id ASC").fetchall()
        for row in rows:
            script_id = int(row["id"])
            if "characters_json" in row.keys():
                self._substituir_lista_simples(con, "script_characters", script_id, self._carregar_lista_json(row["characters_json"]))
            if "locations_json" in row.keys():
                self._substituir_lista_simples(con, "script_locations", script_id, self._carregar_lista_json(row["locations_json"]))
            if "character_catalog_json" in row.keys():
                self._substituir_catalogo(con, "script_character_catalog", script_id, self._carregar_catalogo_json(row["character_catalog_json"]))
            if "location_catalog_json" in row.keys():
                self._substituir_catalogo(con, "script_location_catalog", script_id, self._carregar_catalogo_json(row["location_catalog_json"]))

    @staticmethod
    @registrar_etapa
    def _rollback_silencioso(con: sqlite3.Connection) -> None:
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            con: Valor usado pela rotina para compor a operação de rollback silencioso.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        try:
            con.rollback()
        except Exception:
            pass

    @staticmethod
    @registrar_etapa
    def _normalizar_html_capitulo(paragrafos: Any) -> str:
        """
        Padroniza valores de entrada para que diferentes partes do sistema trabalhem com o mesmo formato.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            paragrafos: Valor usado pela rotina para compor a operação de normalizar html capitulo.
    
        Retorno:
            O valor recebido em uma forma padronizada e segura para uso interno.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        if isinstance(paragrafos, list) and paragrafos:
            return str(paragrafos[0] or _HTML_CAPITULO_PADRAO)
        if isinstance(paragrafos, str):
            return paragrafos or _HTML_CAPITULO_PADRAO
        return _HTML_CAPITULO_PADRAO

    @staticmethod
    @registrar_etapa
    def _normalizar_html_roteiro(paragrafos: Any) -> str:
        """
        Padroniza valores de entrada para que diferentes partes do sistema trabalhem com o mesmo formato.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            paragrafos: Valor usado pela rotina para compor a operação de normalizar html roteiro.
    
        Retorno:
            O valor recebido em uma forma padronizada e segura para uso interno.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        if isinstance(paragrafos, str):
            html = paragrafos.strip()
            return html or _HTML_ROTEIRO_PADRAO
        if isinstance(paragrafos, list):
            partes = []
            for item in paragrafos:
                if item is None:
                    continue
                trecho = str(item).strip()
                if trecho:
                    partes.append(trecho)
            html = "".join(partes).strip()
            return html or _HTML_ROTEIRO_PADRAO
        return _HTML_ROTEIRO_PADRAO

    @staticmethod
    @registrar_etapa
    def _carregar_lista_json(valor: Any) -> list[str]:
        """
        Carrega dados externos ou persistidos e os prepara para uso imediato pela aplicação.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            valor: Valor usado pela rotina para compor a operação de carregar lista json.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        if isinstance(valor, list):
            return [str(item).strip() for item in valor if str(item).strip()]
        if not valor:
            return []
        try:
            dados = json.loads(str(valor))
        except (TypeError, json.JSONDecodeError):
            return []
        if not isinstance(dados, list):
            return []
        return [str(item).strip() for item in dados if str(item).strip()]

    @staticmethod
    @registrar_etapa
    def _carregar_catalogo_json(valor: Any) -> list[dict[str, str]]:
        """
        Carrega dados externos ou persistidos e os prepara para uso imediato pela aplicação.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            valor: Valor usado pela rotina para compor a operação de carregar catalogo json.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        if not valor:
            return []
        dados = valor
        if not isinstance(dados, list):
            try:
                dados = json.loads(str(valor))
            except (TypeError, json.JSONDecodeError):
                return []
        if not isinstance(dados, list):
            return []
        return BancoEditorLocal._normalizar_catalogo(dados)

    @staticmethod
    @registrar_etapa
    def _normalizar_lista_simples(valor: Any) -> list[str]:
        """
        Padroniza valores de entrada para que diferentes partes do sistema trabalhem com o mesmo formato.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            valor: Valor usado pela rotina para compor a operação de normalizar lista simples.
    
        Retorno:
            O valor recebido em uma forma padronizada e segura para uso interno.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        if isinstance(valor, str):
            itens = [item.strip() for item in valor.splitlines()]
        elif isinstance(valor, list):
            itens = [str(item).strip() for item in valor]
        else:
            return []
        saida: list[str] = []
        vistos: set[str] = set()
        for item in itens:
            if not item:
                continue
            chave = item.casefold()
            if chave in vistos:
                continue
            vistos.add(chave)
            saida.append(item)
        return saida

    @staticmethod
    @registrar_etapa
    def _normalizar_catalogo(valor: Any) -> list[dict[str, str]]:
        """
        Padroniza valores de entrada para que diferentes partes do sistema trabalhem com o mesmo formato.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            valor: Valor usado pela rotina para compor a operação de normalizar catalogo.
    
        Retorno:
            O valor recebido em uma forma padronizada e segura para uso interno.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        if not isinstance(valor, list):
            return []
        saida: list[dict[str, str]] = []
        vistos: set[str] = set()
        for item in valor:
            if isinstance(item, dict):
                nome = str(item.get("nome") or "").strip()
                descricao = str(item.get("descricao") or "").strip()
            else:
                nome = str(item or "").strip()
                descricao = ""
            if not nome:
                continue
            chave = nome.casefold()
            if chave in vistos:
                continue
            vistos.add(chave)
            saida.append({"nome": nome, "descricao": descricao})
        return saida

    @staticmethod
    @registrar_etapa
    def _fetchall_dicts(con: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            con: Valor usado pela rotina para compor a operação de fetchall dicts.
            sql: Valor usado pela rotina para compor a operação de fetchall dicts.
            params: Valor usado pela rotina para compor a operação de fetchall dicts.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        return [dict(row) for row in con.execute(sql, params).fetchall()]

    @registrar_etapa
    def _carregar_listas_relacionais(self, con: sqlite3.Connection, script_ids: list[int]) -> dict[int, dict[str, Any]]:
        """
        Carrega dados externos ou persistidos e os prepara para uso imediato pela aplicação.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            con: Valor usado pela rotina para compor a operação de carregar listas relacionais.
            script_ids: Valor usado pela rotina para compor a operação de carregar listas relacionais.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        base = {
            script_id: {
                "personagens": [],
                "locais": [],
                "catalogo_personagens": [],
                "catalogo_locais": [],
            }
            for script_id in script_ids
        }
        if not script_ids:
            return base
        placeholders = ",".join("?" for _ in script_ids)

        for row in self._fetchall_dicts(
            con,
            f"SELECT script_id, name FROM script_characters WHERE script_id IN ({placeholders}) ORDER BY script_id ASC, position ASC",
            tuple(script_ids),
        ):
            base[int(row["script_id"])]["personagens"].append(row["name"])

        for row in self._fetchall_dicts(
            con,
            f"SELECT script_id, name FROM script_locations WHERE script_id IN ({placeholders}) ORDER BY script_id ASC, position ASC",
            tuple(script_ids),
        ):
            base[int(row["script_id"])]["locais"].append(row["name"])

        for row in self._fetchall_dicts(
            con,
            f"SELECT script_id, name, description FROM script_character_catalog WHERE script_id IN ({placeholders}) ORDER BY script_id ASC, position ASC",
            tuple(script_ids),
        ):
            base[int(row["script_id"])]["catalogo_personagens"].append({"nome": row["name"], "descricao": row["description"] or ""})

        for row in self._fetchall_dicts(
            con,
            f"SELECT script_id, name, description FROM script_location_catalog WHERE script_id IN ({placeholders}) ORDER BY script_id ASC, position ASC",
            tuple(script_ids),
        ):
            base[int(row["script_id"])]["catalogo_locais"].append({"nome": row["name"], "descricao": row["description"] or ""})

        return base

    @registrar_etapa
    def _substituir_lista_simples(self, con: sqlite3.Connection, tabela: str, script_id: int, itens: list[str]) -> None:
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            con: Valor usado pela rotina para compor a operação de substituir lista simples.
            tabela: Valor usado pela rotina para compor a operação de substituir lista simples.
            script_id: Valor usado pela rotina para compor a operação de substituir lista simples.
            itens: Valor usado pela rotina para compor a operação de substituir lista simples.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        con.execute(f"DELETE FROM {tabela} WHERE script_id = ?", (script_id,))
        if not itens:
            return
        con.executemany(
            f"INSERT INTO {tabela}(script_id, position, name) VALUES(?, ?, ?)",
            [(script_id, indice, nome) for indice, nome in enumerate(itens)],
        )

    @registrar_etapa
    def _substituir_catalogo(self, con: sqlite3.Connection, tabela: str, script_id: int, itens: list[dict[str, str]]) -> None:
        """
        Executa uma etapa específica do fluxo do módulo, encapsulando detalhes para manter o restante do código mais claro.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            con: Valor usado pela rotina para compor a operação de substituir catalogo.
            tabela: Valor usado pela rotina para compor a operação de substituir catalogo.
            script_id: Valor usado pela rotina para compor a operação de substituir catalogo.
            itens: Valor usado pela rotina para compor a operação de substituir catalogo.
    
        Retorno:
            O resultado produzido pela etapa, ou None quando a função atua apenas por efeito colateral.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        con.execute(f"DELETE FROM {tabela} WHERE script_id = ?", (script_id,))
        if not itens:
            return
        con.executemany(
            f"INSERT INTO {tabela}(script_id, position, name, description) VALUES(?, ?, ?, ?)",
            [(script_id, indice, item["nome"], item.get("descricao", "")) for indice, item in enumerate(itens)],
        )


    @registrar_etapa
    def recursos_existem(self) -> bool:
        """Indica se já há recursos do projeto persistidos no banco local."""
        with self.conexao() as con:
            row = con.execute(
                """
                SELECT
                    EXISTS(SELECT 1 FROM project_info_pages LIMIT 1)
                    OR EXISTS(SELECT 1 FROM project_flow_nodes LIMIT 1)
                    OR EXISTS(SELECT 1 FROM project_resource_catalog LIMIT 1)
                    OR EXISTS(SELECT 1 FROM project_resource_hidden LIMIT 1)
                    AS has_data
                """
            ).fetchone()
            return bool(row["has_data"] if row else False)

    @registrar_etapa
    def ler_recursos_projeto(self) -> dict[str, Any] | None:
        """Lê os recursos criativos persistidos nas tabelas SQLite do projeto."""
        if not self.recursos_existem():
            return None
        with self.conexao() as con:
            meta = {
                row["key"]: row["value"]
                for row in con.execute("SELECT key, value FROM project_resource_meta").fetchall()
            }
            paginas = [
                {
                    "id": row["id"],
                    "titulo": row["title"],
                    "html": row["html"],
                    "data_criacao": row["created_at"],
                    "data_atualizacao": row["updated_at"],
                }
                for row in con.execute(
                    "SELECT id, title, html, created_at, updated_at FROM project_info_pages ORDER BY position ASC, rowid ASC"
                ).fetchall()
            ]
            nodes = [
                {
                    "id": row["id"],
                    "x": row["x"],
                    "y": row["y"],
                    "width": row["width"],
                    "height": row["height"],
                    "titulo": row["title"],
                    "texto": row["text"],
                }
                for row in con.execute(
                    "SELECT id, x, y, width, height, title, text FROM project_flow_nodes ORDER BY position ASC, rowid ASC"
                ).fetchall()
            ]
            edges = [
                {
                    "id": row["id"],
                    "from": row["from_node_id"],
                    "to": row["to_node_id"],
                    "fromSide": row["from_side"],
                    "toSide": row["to_side"],
                }
                for row in con.execute(
                    "SELECT id, from_node_id, to_node_id, from_side, to_side FROM project_flow_edges ORDER BY position ASC, rowid ASC"
                ).fetchall()
            ]
            catalogo = {"personagens": [], "lugares": [], "anotacoes": []}
            for row in con.execute(
                """
                SELECT type, id, name, description, image, created_at, updated_at
                FROM project_resource_catalog
                ORDER BY type ASC, position ASC, rowid ASC
                """
            ).fetchall():
                tipo = row["type"] if row["type"] in catalogo else "lugares"
                catalogo[tipo].append({
                    "id": row["id"],
                    "nome": row["name"],
                    "descricao": row["description"] or "",
                    "imagem": row["image"] or "",
                    "origem": "projeto",
                    "data_criacao": row["created_at"],
                    "data_atualizacao": row["updated_at"],
                })
            ocultos = {"personagens": [], "lugares": [], "anotacoes": []}
            for row in con.execute("SELECT type, name FROM project_resource_hidden ORDER BY type ASC, name ASC").fetchall():
                tipo = row["type"] if row["type"] in ocultos else "lugares"
                ocultos[tipo].append(row["name"])
            return {
                "versao": 1,
                "informacoes": paginas,
                "fluxo": {"nodes": nodes, "edges": edges},
                "personagens": catalogo["personagens"],
                "lugares": catalogo["lugares"],
                "anotacoes": catalogo["anotacoes"],
                "ocultos": ocultos,
                "data_atualizacao": meta.get("data_atualizacao", ""),
            }

    @registrar_etapa
    def salvar_recursos_projeto(self, dados: dict[str, Any]) -> dict[str, Any]:
        """Substitui o conjunto de recursos do projeto usando tabelas relacionais SQLite."""
        with self.conexao() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute("DELETE FROM project_resource_meta")
            con.execute("DELETE FROM project_flow_edges")
            con.execute("DELETE FROM project_flow_nodes")
            con.execute("DELETE FROM project_info_pages")
            con.execute("DELETE FROM project_resource_catalog")
            con.execute("DELETE FROM project_resource_hidden")
            con.execute(
                "INSERT INTO project_resource_meta(key, value) VALUES('data_atualizacao', ?)",
                (str(dados.get("data_atualizacao") or ""),),
            )
            con.executemany(
                """
                INSERT INTO project_info_pages(id, position, title, html, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(item.get("id") or ""),
                        indice,
                        str(item.get("titulo") or ""),
                        str(item.get("html") or ""),
                        str(item.get("data_criacao") or ""),
                        str(item.get("data_atualizacao") or ""),
                    )
                    for indice, item in enumerate(dados.get("informacoes") or [])
                ],
            )
            con.executemany(
                """
                INSERT INTO project_flow_nodes(id, position, x, y, width, height, title, text)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(item.get("id") or ""),
                        indice,
                        float(item.get("x") or 0),
                        float(item.get("y") or 0),
                        float(item.get("width") or 240),
                        float(item.get("height") or 150),
                        str(item.get("titulo") or ""),
                        str(item.get("texto") or ""),
                    )
                    for indice, item in enumerate((dados.get("fluxo") or {}).get("nodes") or [])
                ],
            )
            con.executemany(
                """
                INSERT INTO project_flow_edges(id, position, from_node_id, to_node_id, from_side, to_side)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(item.get("id") or ""),
                        indice,
                        str(item.get("from") or ""),
                        str(item.get("to") or ""),
                        str(item.get("fromSide") or "right"),
                        str(item.get("toSide") or "left"),
                    )
                    for indice, item in enumerate((dados.get("fluxo") or {}).get("edges") or [])
                ],
            )
            catalog_rows = []
            for tipo in ("personagens", "lugares", "anotacoes"):
                for indice, item in enumerate(dados.get(tipo) or []):
                    catalog_rows.append((
                        tipo,
                        str(item.get("id") or ""),
                        indice,
                        str(item.get("nome") or ""),
                        str(item.get("descricao") or ""),
                        str(item.get("imagem") or ""),
                        str(item.get("data_criacao") or ""),
                        str(item.get("data_atualizacao") or ""),
                    ))
            con.executemany(
                """
                INSERT OR REPLACE INTO project_resource_catalog(type, id, position, name, description, image, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                catalog_rows,
            )
            hidden_rows = []
            ocultos = dados.get("ocultos") or {}
            for tipo in ("personagens", "lugares", "anotacoes"):
                for nome in ocultos.get(tipo) or []:
                    hidden_rows.append((tipo, str(nome or "")))
            con.executemany(
                "INSERT OR IGNORE INTO project_resource_hidden(type, name) VALUES(?, ?)",
                hidden_rows,
            )
            con.commit()
        return self.ler_recursos_projeto() or dados

    @registrar_etapa
    def listar_capitulos(self) -> list[dict[str, Any]]:
        """
        Reúne e devolve uma lista organizada de itens disponíveis para a interface ou para outra camada do sistema.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Retorno:
            Uma lista com os registros encontrados, normalmente já ordenada e pronta para a interface.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        with self.conexao() as con:
            rows = con.execute("SELECT id, title, updated_at FROM chapters ORDER BY id ASC").fetchall()
            return [
                {
                    "id": int(row["id"]),
                    "arquivo": f"capitulo_{int(row['id'])}.json",
                    "titulo": row["title"] or f"Capítulo {int(row['id'])}",
                    "data_atualizacao": row["updated_at"],
                }
                for row in rows
            ]

    @registrar_etapa
    def proximo_numero_capitulo(self) -> int:
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
        with self.conexao() as con:
            row = con.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM chapters").fetchone()
            return int(row["next_id"] or 1)

    @registrar_etapa
    def criar_capitulo(self, numero: int, titulo: str, html: str, data_criacao: str, data_atualizacao: str) -> dict[str, Any]:
        """
        Cria um novo registro, arquivo ou estrutura interna mantendo o padrão de armazenamento do projeto.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
            titulo: Título exibido ou salvo para representar o conteúdo tratado.
            html: Conteúdo HTML já editado ou normalizado pela aplicação.
            data_criacao: Valor usado pela rotina para compor a operação de criar capitulo.
            data_atualizacao: Valor usado pela rotina para compor a operação de criar capitulo.
    
        Retorno:
            Os dados do novo item criado, incluindo identificadores gerados quando existirem.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        with self.conexao() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute(
                "INSERT INTO chapters(id, title, html, created_at, updated_at) VALUES(?, ?, ?, ?, ?)",
                (numero, titulo, html, data_criacao, data_atualizacao),
            )
            con.commit()
        return {
            "id": numero,
            "titulo": titulo,
            "paragrafos": [html],
            "data_criacao": data_criacao,
            "data_atualizacao": data_atualizacao,
        }

    @registrar_etapa
    def ler_capitulo(self, numero: int) -> dict[str, Any] | None:
        """
        Lê conteúdo persistido e devolve dados estruturados para consumo pelo restante da aplicação.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
    
        Retorno:
            Conteúdo estruturado lido a partir da origem informada.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        with self.conexao() as con:
            row = con.execute(
                "SELECT id, title, html, created_at, updated_at FROM chapters WHERE id = ?",
                (numero,),
            ).fetchone()
            if row is None:
                return None
            return {
                "id": int(row["id"]),
                "titulo": row["title"] or f"Capítulo {numero}",
                "paragrafos": [row["html"] or _HTML_CAPITULO_PADRAO],
                "data_criacao": row["created_at"],
                "data_atualizacao": row["updated_at"],
            }

    @registrar_etapa
    def salvar_capitulo(self, numero: int, titulo: str, html: str, data_criacao: str, data_atualizacao: str) -> dict[str, Any] | None:
        """
        Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
            titulo: Título exibido ou salvo para representar o conteúdo tratado.
            html: Conteúdo HTML já editado ou normalizado pela aplicação.
            data_criacao: Valor usado pela rotina para compor a operação de salvar capitulo.
            data_atualizacao: Valor usado pela rotina para compor a operação de salvar capitulo.
    
        Retorno:
            A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        with self.conexao() as con:
            con.execute("BEGIN IMMEDIATE")
            cursor = con.execute(
                """
                UPDATE chapters
                SET title = ?, html = ?, created_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (titulo, html, data_criacao, data_atualizacao, numero),
            )
            con.commit()
            if cursor.rowcount < 1:
                return None
        return {
            "id": numero,
            "titulo": titulo,
            "paragrafos": [html],
            "data_criacao": data_criacao,
            "data_atualizacao": data_atualizacao,
        }

    @registrar_etapa
    def excluir_capitulo(self, numero: int) -> None:
        """
        Remove o item indicado e executa os cuidados necessários para manter o restante do projeto consistente.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
    
        Retorno:
            None. A função sinaliza falhas por exceção quando a remoção não pode ser concluída.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        with self.conexao() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute("DELETE FROM chapters WHERE id = ?", (numero,))
            con.commit()

    @registrar_etapa
    def listar_roteiros(self) -> list[dict[str, Any]]:
        """
        Reúne e devolve uma lista organizada de itens disponíveis para a interface ou para outra camada do sistema.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Retorno:
            Uma lista com os registros encontrados, normalmente já ordenada e pronta para a interface.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        with self.conexao() as con:
            rows = con.execute(
                """
                SELECT id, title, header, footer, scene_prefix, start_number,
                       logline, synopsis, genre, script_type, copyright_enabled,
                       created_at, updated_at
                FROM scripts
                ORDER BY id ASC
                """
            ).fetchall()
            if not rows:
                return []
            script_ids = [int(row["id"]) for row in rows]
            relacionais = self._carregar_listas_relacionais(con, script_ids)
            itens = []
            for row in rows:
                numero = int(row["id"])
                extras = relacionais.get(numero, {})
                itens.append({
                    "id": numero,
                    "arquivo": f"roteiro_{numero}.json",
                    "titulo": row["title"] or f"ROTEIRO {numero}",
                    "cabecalho": row["header"] or "",
                    "rodape": row["footer"] or "",
                    "prefixo_cena": row["scene_prefix"] or "0",
                    "numeracao_inicial": int(row["start_number"] or 1),
                    "logline": row["logline"] or "",
                    "sinopse": row["synopsis"] or "",
                    "genero": row["genre"] or "",
                    "personagens": extras.get("personagens", []),
                    "locais": extras.get("locais", []),
                    "catalogo_personagens": extras.get("catalogo_personagens", []),
                    "catalogo_locais": extras.get("catalogo_locais", []),
                    "data_criacao": row["created_at"],
                    "data_atualizacao": row["updated_at"],
                    "tipo_roteiro": row["script_type"] or "spec_script",
                    "copyright": bool(row["copyright_enabled"]),
                })
            return itens

    @registrar_etapa
    def proximo_numero_roteiro(self) -> int:
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
        with self.conexao() as con:
            row = con.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM scripts").fetchone()
            return int(row["next_id"] or 1)

    @registrar_etapa
    def criar_roteiro(self, numero: int, dados: dict[str, Any]) -> dict[str, Any]:
        """
        Cria um novo registro, arquivo ou estrutura interna mantendo o padrão de armazenamento do projeto.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
            dados: Valor usado pela rotina para compor a operação de criar roteiro.
    
        Retorno:
            Os dados do novo item criado, incluindo identificadores gerados quando existirem.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        personagens = self._normalizar_lista_simples(dados.get("personagens"))
        locais = self._normalizar_lista_simples(dados.get("locais"))
        catalogo_personagens = self._normalizar_catalogo(dados.get("catalogo_personagens") or [])
        catalogo_locais = self._normalizar_catalogo(dados.get("catalogo_locais") or [])
        html = self._normalizar_html_roteiro(dados.get("html_editor") or dados.get("paragrafos"))
        with self.conexao() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute(
                """
                INSERT INTO scripts(
                    id, title, html, header, footer, scene_prefix, start_number,
                    logline, synopsis, genre, script_type, copyright_enabled,
                    created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    numero,
                    dados["titulo"],
                    html,
                    dados.get("cabecalho", ""),
                    dados.get("rodape", ""),
                    dados.get("prefixo_cena", "0"),
                    dados.get("numeracao_inicial", 1),
                    dados.get("logline", ""),
                    dados.get("sinopse", ""),
                    dados.get("genero", ""),
                    dados.get("tipo_roteiro", "spec_script"),
                    1 if bool(dados.get("copyright")) else 0,
                    dados.get("data_criacao"),
                    dados.get("data_atualizacao"),
                ),
            )
            self._substituir_lista_simples(con, "script_characters", numero, personagens)
            self._substituir_lista_simples(con, "script_locations", numero, locais)
            self._substituir_catalogo(con, "script_character_catalog", numero, catalogo_personagens)
            self._substituir_catalogo(con, "script_location_catalog", numero, catalogo_locais)
            con.commit()
        return {
            "id": numero,
            **dados,
            "paragrafos": [html],
            "html_editor": html,
            "personagens": personagens,
            "locais": locais,
            "catalogo_personagens": catalogo_personagens,
            "catalogo_locais": catalogo_locais,
        }

    @registrar_etapa
    def ler_roteiro(self, numero: int) -> dict[str, Any] | None:
        """
        Lê conteúdo persistido e devolve dados estruturados para consumo pelo restante da aplicação.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
    
        Retorno:
            Conteúdo estruturado lido a partir da origem informada.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        with self.conexao() as con:
            row = con.execute(
                """
                SELECT id, title, html, header, footer, scene_prefix, start_number,
                       logline, synopsis, genre, script_type, copyright_enabled,
                       created_at, updated_at
                FROM scripts
                WHERE id = ?
                """,
                (numero,),
            ).fetchone()
            if row is None:
                return None
            html = self._normalizar_html_roteiro(row["html"])
            extras = self._carregar_listas_relacionais(con, [numero]).get(numero, {})
            return {
                "id": int(row["id"]),
                "titulo": row["title"],
                "paragrafos": [html],
                "html_editor": html,
                "cabecalho": row["header"] or "",
                "rodape": row["footer"] or "",
                "prefixo_cena": row["scene_prefix"] or "0",
                "numeracao_inicial": int(row["start_number"] or 1),
                "logline": row["logline"] or "",
                "sinopse": row["synopsis"] or "",
                "genero": row["genre"] or "",
                "tipo_roteiro": row["script_type"] or "spec_script",
                "copyright": bool(row["copyright_enabled"]),
                "personagens": extras.get("personagens", []),
                "locais": extras.get("locais", []),
                "catalogo_personagens": extras.get("catalogo_personagens", []),
                "catalogo_locais": extras.get("catalogo_locais", []),
                "data_criacao": row["created_at"],
                "data_atualizacao": row["updated_at"],
            }

    @registrar_etapa
    def salvar_roteiro(self, numero: int, dados: dict[str, Any]) -> dict[str, Any] | None:
        """
        Persiste as alterações recebidas, garantindo que o conteúdo fique disponível nas próximas execuções.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
            dados: Valor usado pela rotina para compor a operação de salvar roteiro.
    
        Retorno:
            A estrutura atualizada ou None quando a persistência não precisa devolver conteúdo.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        personagens = self._normalizar_lista_simples(dados.get("personagens"))
        locais = self._normalizar_lista_simples(dados.get("locais"))
        catalogo_personagens = self._normalizar_catalogo(dados.get("catalogo_personagens") or [])
        catalogo_locais = self._normalizar_catalogo(dados.get("catalogo_locais") or [])
        html = self._normalizar_html_roteiro(dados.get("html_editor") or dados.get("paragrafos"))
        with self.conexao() as con:
            con.execute("BEGIN IMMEDIATE")
            cursor = con.execute(
                """
                UPDATE scripts
                SET title = ?, html = ?, header = ?, footer = ?, scene_prefix = ?, start_number = ?,
                    logline = ?, synopsis = ?, genre = ?, script_type = ?, copyright_enabled = ?,
                    created_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    dados["titulo"],
                    html,
                    dados.get("cabecalho", ""),
                    dados.get("rodape", ""),
                    dados.get("prefixo_cena", "0"),
                    dados.get("numeracao_inicial", 1),
                    dados.get("logline", ""),
                    dados.get("sinopse", ""),
                    dados.get("genero", ""),
                    dados.get("tipo_roteiro", "spec_script"),
                    1 if bool(dados.get("copyright")) else 0,
                    dados.get("data_criacao"),
                    dados.get("data_atualizacao"),
                    numero,
                ),
            )
            if cursor.rowcount < 1:
                con.rollback()
                return None
            self._substituir_lista_simples(con, "script_characters", numero, personagens)
            self._substituir_lista_simples(con, "script_locations", numero, locais)
            self._substituir_catalogo(con, "script_character_catalog", numero, catalogo_personagens)
            self._substituir_catalogo(con, "script_location_catalog", numero, catalogo_locais)
            con.commit()
        return {
            "id": numero,
            **dados,
            "paragrafos": [html],
            "html_editor": html,
            "personagens": personagens,
            "locais": locais,
            "catalogo_personagens": catalogo_personagens,
            "catalogo_locais": catalogo_locais,
        }

    @registrar_etapa
    def excluir_roteiro(self, numero: int) -> None:
        """
        Remove o item indicado e executa os cuidados necessários para manter o restante do projeto consistente.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Parâmetros:
            numero: Número usado para localizar o capítulo, item ou posição correspondente.
    
        Retorno:
            None. A função sinaliza falhas por exceção quando a remoção não pode ser concluída.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        with self.conexao() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute("DELETE FROM scripts WHERE id = ?", (numero,))
            con.commit()
