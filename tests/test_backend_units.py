from __future__ import annotations

import base64
from pathlib import Path

from modules import conversor_pdf_epub, exportador_gut, i18n, manipulador_capitulos, manipulador_projetos, manipulador_roteiros, persistencia_json, servidor_flask, utilidades
from tests.test_support import IsolatedProjectTestCase


class UtilidadesTests(IsolatedProjectTestCase):
    """
    Representa UtilidadesTests dentro do fluxo da aplicação.

    Esta classe concentra estado e comportamentos relacionados para evitar que a
    lógica fique espalhada por vários pontos do código. A intenção é oferecer uma
    interface simples para quem consome o módulo, escondendo os detalhes internos
    de organização, validação e integração com os demais componentes.
    """
    def test_nome_seguro_remove_acentos_e_ruido(self):
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
        self.assertEqual(utilidades.nome_seguro("  Árvore do Vento!!!  "), "arvore_do_vento")
        self.assertEqual(utilidades.nome_seguro("***"), "projeto")

    def test_inferir_extensao_data_url(self):
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
        raw = b"conteudo-binario"
        data_url = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
        extensao, conteudo = utilidades.inferir_extensao_data_url(data_url)
        self.assertEqual(extensao, ".png")
        self.assertEqual(conteudo, raw)

    def test_obter_configuracoes_cria_estrutura_e_defaults(self):
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
        config = utilidades.obter_configuracoes()
        self.assertTrue(self.config_file.exists())
        self.assertEqual(config["idioma_app"], "pt_BR")
        self.assertEqual(Path(config["caminho_exportacao"]), self.exports)
        self.assertEqual(Path(config["caminho_biblioteca"]), self.library)

    def test_configurar_integracao_gut_windows_nao_cria_launcher_cmd(self):
        destino = self.base / "launchers" / "gutenberg_open_gut.cmd"
        utilidades.configurar_integracao_gut_windows(caminho_launcher=destino)
        self.assertFalse(destino.exists())

class PersistenciaJsonTests(IsolatedProjectTestCase):
    """
    Representa PersistenciaJsonTests dentro do fluxo da aplicação.

    Esta classe concentra estado e comportamentos relacionados para evitar que a
    lógica fique espalhada por vários pontos do código. A intenção é oferecer uma
    interface simples para quem consome o módulo, escondendo os detalhes internos
    de organização, validação e integração com os demais componentes.
    """
    def test_salvar_e_ler_json_roundtrip(self):
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
        destino = self.base / "dados" / "arquivo.json"
        dados = {"ok": True, "valor": 3}
        persistencia_json.salvar_json(destino, dados)
        self.assertEqual(persistencia_json.ler_json(destino), dados)

    def test_ler_json_invalido_retorna_padrao(self):
        """
        Lê conteúdo persistido e devolve dados estruturados para consumo pelo restante da aplicação.
    
        A função isola esta responsabilidade para deixar o fluxo principal mais fácil
        de acompanhar. Ela recebe os dados no formato usado pelo projeto, realiza as
        normalizações ou verificações necessárias e entrega um resultado previsível
        para a próxima camada do sistema.
    
        Retorno:
            Conteúdo estruturado lido a partir da origem informada.
    
        Observações:
            Mantém a lógica centralizada e evita que detalhes de implementação vazem
            para quem apenas precisa acionar este comportamento.
        """
        destino = self.base / "dados" / "arquivo.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text("{invalido", encoding="utf-8")
        self.assertEqual(persistencia_json.ler_json(destino, {"fallback": 1}), {"fallback": 1})


class ConversorHelpersTests(IsolatedProjectTestCase):
    """
    Representa ConversorHelpersTests dentro do fluxo da aplicação.

    Esta classe concentra estado e comportamentos relacionados para evitar que a
    lógica fique espalhada por vários pontos do código. A intenção é oferecer uma
    interface simples para quem consome o módulo, escondendo os detalhes internos
    de organização, validação e integração com os demais componentes.
    """
    def test_split_glued_word_quando_lexico_permiste_divisao(self):
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
        lexicon = {"casa", "azul"}
        self.assertEqual(conversor_pdf_epub._split_glued_word("CasaAzul", lexicon), "Casa Azul")

    def test_correct_glued_words_mantem_tokens_nao_reconhecidos(self):
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
        lexicon = {"historia", "boa"}
        texto = "Historiaboa xyzabc"
        self.assertEqual(conversor_pdf_epub._correct_glued_words(texto, lexicon), "Historia boa xyzabc")

    def test_slugify_e_numeric_line(self):
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
        self.assertEqual(conversor_pdf_epub._slugify(" Meu Livro !!! "), "meu-livro")
        self.assertTrue(conversor_pdf_epub._is_standalone_numeric_line("XIV"))
        self.assertFalse(conversor_pdf_epub._is_standalone_numeric_line("Capítulo XIV"))


class ProjetoCapituloRoteiroTests(IsolatedProjectTestCase):
    """
    Representa ProjetoCapituloRoteiroTests dentro do fluxo da aplicação.

    Esta classe concentra estado e comportamentos relacionados para evitar que a
    lógica fique espalhada por vários pontos do código. A intenção é oferecer uma
    interface simples para quem consome o módulo, escondendo os detalhes internos
    de organização, validação e integração com os demais componentes.
    """
    def test_criar_projeto_listar_e_obter(self):
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
        projeto = manipulador_projetos.criar_projeto(
            "Meu Livro", descricao="Desc", autor="Autora", tags=["fantasia", " aventura "], idioma="en_US"
        )
        self.assertEqual(projeto["slug"], "meu_livro")

        projetos = manipulador_projetos.listar_projetos()
        self.assertEqual(len(projetos), 1)
        self.assertEqual(projetos[0]["idioma"], "en_US")
        self.assertEqual(projetos[0]["tags"], ["fantasia", "aventura"])

        carregado = manipulador_projetos.obter_projeto("meu_livro")
        self.assertEqual(carregado["titulo"], "Meu Livro")
        self.assertEqual(carregado["capitulos"], [])
        self.assertEqual(carregado["roteiros"], [])

    def test_criar_e_salvar_capitulo_preserva_html(self):
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
        projeto = manipulador_projetos.criar_projeto("Romance")
        pasta = manipulador_projetos.obter_pasta_projeto(projeto["slug"])
        capitulo = manipulador_capitulos.criar_capitulo(pasta, "Capítulo 1")
        salvo = manipulador_capitulos.salvar_capitulo(pasta, capitulo["id"], "Capítulo 1", "<p>Texto final</p>")
        self.assertEqual(salvo["paragrafos"], ["<p>Texto final</p>"])
        lido = manipulador_capitulos.ler_capitulo(pasta, capitulo["id"])
        self.assertEqual(lido["titulo"], "Capítulo 1")
        self.assertEqual(lido["paragrafos"], ["<p>Texto final</p>"])

    def test_recriar_projeto_com_mesmo_nome_reinicializa_banco_editor(self):
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
        projeto = manipulador_projetos.criar_projeto("Projeto 1")
        slug = projeto["slug"]
        pasta = manipulador_projetos.obter_pasta_projeto(slug)

        manipulador_capitulos.criar_capitulo(pasta, "Capítulo 1")
        manipulador_projetos.excluir_projeto(slug)

        recriado = manipulador_projetos.criar_projeto("Projeto 1")
        self.assertEqual(recriado["slug"], slug)

        carregado = manipulador_projetos.obter_projeto(slug)
        self.assertEqual(carregado["capitulos"], [])
        self.assertEqual(carregado["roteiros"], [])

    def test_criar_e_atualizar_roteiro_normaliza_campos(self):
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
        projeto = manipulador_projetos.criar_projeto("Cinema", tipo="roteiro")
        pasta = manipulador_projetos.obter_pasta_projeto(projeto["slug"])
        roteiro = manipulador_roteiros.criar_roteiro(
            pasta,
            "piloto",
            tipo_roteiro="shooting_script",
            numeracao_inicial=0,
            prefixo_cena="00",
        )
        self.assertEqual(roteiro["titulo"], "PILOTO")

        atualizado = manipulador_roteiros.atualizar_roteiro_info(
            pasta,
            roteiro["id"],
            {
                "personagens": "ANA\nBRUNO\n\n",
                "locais": ["CASA", "RUA", " "],
                "tipo_roteiro": "spec_script",
            },
        )
        self.assertEqual(atualizado["personagens"], ["ANA", "BRUNO"])
        self.assertEqual(atualizado["locais"], ["CASA", "RUA"])
        self.assertEqual(atualizado["tipo_roteiro"], "spec_script")
        self.assertFalse(atualizado["copyright"])

        salvo = manipulador_roteiros.salvar_roteiro(pasta, roteiro["id"], "novo título", "<div>cena</div>")
        self.assertEqual(salvo["titulo"], "NOVO TÍTULO")
        self.assertEqual(salvo["html_editor"], "<div>cena</div>")




    def test_exportador_gut_salva_capitulos_e_roteiro_com_payload_estruturado(self):
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
        projeto_livro = manipulador_projetos.criar_projeto("Livro Gut", autor="Autora", tags=["fantasia"], idioma="en_US")
        pasta_livro = manipulador_projetos.obter_pasta_projeto(projeto_livro["slug"])
        capitulo = manipulador_capitulos.criar_capitulo(pasta_livro, "Capítulo 1")
        manipulador_capitulos.salvar_capitulo(pasta_livro, capitulo["id"], "Capítulo 1", "<h1>Capítulo 1</h1><p>Texto do livro</p>")

        arquivo_livro = exportador_gut.exportar_gut_capitulos(projeto_livro["slug"])
        payload_livro = exportador_gut.ler_cabecalho_gut(arquivo_livro)
        self.assertEqual(payload_livro["tipo_arquivo"], "livro")
        self.assertEqual(payload_livro["projeto"]["titulo"], "Livro Gut")
        self.assertEqual(payload_livro["conteudo"]["quantidade_capitulos"], 1)
        self.assertIn("Texto do livro", payload_livro["conteudo"]["capitulos"][0]["texto"])

        projeto_roteiro = manipulador_projetos.criar_projeto("Serie Gut", tipo="roteiro", contatos="a@b.com")
        pasta_roteiro = manipulador_projetos.obter_pasta_projeto(projeto_roteiro["slug"])
        roteiro = manipulador_roteiros.criar_roteiro(pasta_roteiro, "Piloto", genero="Drama")
        manipulador_roteiros.salvar_roteiro(pasta_roteiro, roteiro["id"], "Piloto", "<div class='roteiro-bloco'>Cena inicial</div>")

        arquivo_roteiro = exportador_gut.exportar_gut_roteiro(projeto_roteiro["slug"], roteiro["id"])
        payload_roteiro = exportador_gut.ler_cabecalho_gut(arquivo_roteiro)
        self.assertEqual(payload_roteiro["tipo_arquivo"], "roteiro")
        self.assertEqual(payload_roteiro["conteudo"]["roteiro"]["id"], roteiro["id"])
        self.assertIn("Cena inicial", payload_roteiro["conteudo"]["roteiro"]["texto"])


class ValidacaoEIdiomaTests(IsolatedProjectTestCase):
    """
    Representa ValidacaoEIdiomaTests dentro do fluxo da aplicação.

    Esta classe concentra estado e comportamentos relacionados para evitar que a
    lógica fique espalhada por vários pontos do código. A intenção é oferecer uma
    interface simples para quem consome o módulo, escondendo os detalhes internos
    de organização, validação e integração com os demais componentes.
    """
    def test_validar_campos_projeto_de_roteiro_limpa_tags_e_valida_contato(self):
        """
        Confere se os dados recebidos atendem ao formato esperado antes de permitir a continuidade do fluxo.
    
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
        dados = servidor_flask._validar_campos_projeto(
            titulo="Projeto X",
            descricao="ok",
            autor="Autor",
            tipo="roteiro",
            tags_str="nao,entra",
            contatos="contato@example.com",
            informacoes_adicionais="obs",
        )
        self.assertEqual(dados["tags"], [])
        self.assertEqual(dados["contatos"], "contato@example.com")

    def test_validar_campos_projeto_recusa_contato_invalido(self):
        """
        Confere se os dados recebidos atendem ao formato esperado antes de permitir a continuidade do fluxo.
    
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
        with self.assertRaises(ValueError):
            servidor_flask._validar_campos_projeto(
                titulo="Projeto X",
                descricao="",
                autor="",
                tipo="roteiro",
                contatos="abc",
            )

    def test_validar_campos_roteiro_aplica_maiusculas_e_limites_basicos(self):
        """
        Confere se os dados recebidos atendem ao formato esperado antes de permitir a continuidade do fluxo.
    
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
        dados = servidor_flask._validar_campos_roteiro(
            titulo="piloto",
            cabecalho=" cab ",
            rodape=" rod ",
            prefixo_cena="000",
            numeracao_inicial="5",
            genero=" drama ",
        )
        self.assertEqual(dados["titulo"], "PILOTO")
        self.assertEqual(dados["cabecalho"], "cab")
        self.assertEqual(dados["rodape"], "rod")
        self.assertEqual(dados["prefixo_cena"], "000")
        self.assertEqual(dados["numeracao_inicial"], 5)
        self.assertEqual(dados["genero"], "drama")

    def test_i18n_retorna_fallback_e_normaliza_idioma(self):
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
        utilidades.salvar_configuracoes({**utilidades.configuracao_padrao(), "idioma_app": "en-US"})
        i18n.limpar_cache_i18n()
        self.assertEqual(i18n.obter_idioma_app(), "en_US")
        self.assertEqual(i18n.t("language.en_US"), "English (US)")
        self.assertEqual(i18n.t("chave.inexistente", default="fallback"), "fallback")
