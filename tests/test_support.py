from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from modules import i18n, manipulador_projetos, manipulador_recursos_projeto, manipulador_roteiros, persistencia_editor_db, utilidades


class IsolatedProjectTestCase(unittest.TestCase):
    """
    Representa IsolatedProjectTestCase dentro do fluxo da aplicação.

    Esta classe concentra estado e comportamentos relacionados para evitar que a
    lógica fique espalhada por vários pontos do código. A intenção é oferecer uma
    interface simples para quem consome o módulo, escondendo os detalhes internos
    de organização, validação e integração com os demais componentes.
    """

    def setUp(self) -> None:
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
        super().setUp()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.base = Path(self._tmpdir.name)
        self.appdata = self.base / "appdata"
        self.documents = self.base / "documents"
        self.projects = self.documents / "projects"
        self.exports = self.documents / "exports"
        self.library = self.documents / "library"
        self.config_file = self.appdata / "config.json"
        self.progress_file = self.appdata / "progress.json"

        self._originals = {
            "utilidades.PASTA_APP": utilidades.PASTA_APP,
            "utilidades.PASTA_DOCUMENTOS_APP": utilidades.PASTA_DOCUMENTOS_APP,
            "utilidades.PASTA_PROJETOS": utilidades.PASTA_PROJETOS,
            "utilidades.EXPORTS_PADRAO": utilidades.EXPORTS_PADRAO,
            "utilidades.BIBLIOTECA_PADRAO": utilidades.BIBLIOTECA_PADRAO,
            "utilidades.ARQUIVO_CONFIG": utilidades.ARQUIVO_CONFIG,
            "utilidades.ARQUIVO_PROGRESSO": utilidades.ARQUIVO_PROGRESSO,
            "manipulador_projetos.PASTA_PROJETOS": manipulador_projetos.PASTA_PROJETOS,
        }

        utilidades.PASTA_APP = self.appdata
        utilidades.PASTA_DOCUMENTOS_APP = self.documents
        utilidades.PASTA_PROJETOS = self.projects
        utilidades.EXPORTS_PADRAO = self.exports
        utilidades.BIBLIOTECA_PADRAO = self.library
        utilidades.ARQUIVO_CONFIG = self.config_file
        utilidades.ARQUIVO_PROGRESSO = self.progress_file
        manipulador_projetos.PASTA_PROJETOS = self.projects

        persistencia_editor_db._DB_LOCKS.clear()
        persistencia_editor_db._DB_INIT_DONE.clear()
        manipulador_roteiros._DB_CACHE.clear()
        manipulador_recursos_projeto._DB_CACHE.clear()
        i18n.limpar_cache_i18n()

        utilidades.garantir_estrutura_app()

    def tearDown(self) -> None:
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
            manipulador_roteiros._DB_CACHE.clear()
            manipulador_recursos_projeto._DB_CACHE.clear()
            persistencia_editor_db._DB_LOCKS.clear()
            persistencia_editor_db._DB_INIT_DONE.clear()
            i18n.limpar_cache_i18n()
        finally:
            utilidades.PASTA_APP = self._originals["utilidades.PASTA_APP"]
            utilidades.PASTA_DOCUMENTOS_APP = self._originals["utilidades.PASTA_DOCUMENTOS_APP"]
            utilidades.PASTA_PROJETOS = self._originals["utilidades.PASTA_PROJETOS"]
            utilidades.EXPORTS_PADRAO = self._originals["utilidades.EXPORTS_PADRAO"]
            utilidades.BIBLIOTECA_PADRAO = self._originals["utilidades.BIBLIOTECA_PADRAO"]
            utilidades.ARQUIVO_CONFIG = self._originals["utilidades.ARQUIVO_CONFIG"]
            utilidades.ARQUIVO_PROGRESSO = self._originals["utilidades.ARQUIVO_PROGRESSO"]
            manipulador_projetos.PASTA_PROJETOS = self._originals["manipulador_projetos.PASTA_PROJETOS"]
            super().tearDown()
            self._tmpdir.cleanup()
