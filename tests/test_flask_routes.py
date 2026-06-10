from __future__ import annotations

import io
from pathlib import Path

from modules import manipulador_capitulos, manipulador_projetos, servidor_flask
from tests.test_support import IsolatedProjectTestCase


class FlaskRoutesTests(IsolatedProjectTestCase):
    """
    Representa FlaskRoutesTests dentro do fluxo da aplicação.

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
        self.app = servidor_flask.criar_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def test_criar_projeto_livro_e_capitulo_salvar(self):
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
        resposta = self.client.post(
            "/projetos/criar",
            data={
                "titulo": "Meu Livro",
                "descricao": "Descrição",
                "autor": "Autora",
                "tipo": "livro",
                "tags": "fantasia, aventura",
                "idioma": "en-US",
            },
        )
        self.assertEqual(resposta.status_code, 200)
        payload = resposta.get_json()
        self.assertTrue(payload["ok"])
        self.assertIn("/projetos/meu_livro", payload["redirect"])

        resposta = self.client.post("/projetos/meu_livro/capitulos/criar", data={"titulo": "Capítulo 1"})
        self.assertEqual(resposta.status_code, 200)
        payload = resposta.get_json()
        self.assertTrue(payload["ok"])
        self.assertIn("/projetos/meu_livro/capitulos/1/editar", payload["redirect"])

        resposta = self.client.post(
            "/api/projetos/meu_livro/capitulos/1/autosave",
            json={"titulo": "Capítulo 1", "html": "<p>Texto salvo</p>"},
        )
        self.assertEqual(resposta.status_code, 200)
        payload = resposta.get_json()
        self.assertTrue(payload["ok"])

        pasta = manipulador_projetos.obter_pasta_projeto("meu_livro")
        capitulo = manipulador_capitulos.ler_capitulo(pasta, 1)
        self.assertEqual(capitulo["paragrafos"], ["<p>Texto salvo</p>"])

    def test_criar_projeto_rejeita_duplicado(self):
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
        primeira = self.client.post("/projetos/criar", data={"titulo": "Duplicado", "tipo": "livro"})
        self.assertEqual(primeira.status_code, 200)
        segunda = self.client.post("/projetos/criar", data={"titulo": "Duplicado", "tipo": "livro"})
        self.assertEqual(segunda.status_code, 400)
        self.assertFalse(segunda.get_json()["ok"])

    def test_criar_roteiro_fluxo_basico(self):
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
        resposta = self.client.post(
            "/projetos/criar",
            data={"titulo": "Projeto de Roteiro", "tipo": "roteiro", "contatos": "writer@example.com"},
        )
        self.assertEqual(resposta.status_code, 200)

        resposta = self.client.post(
            "/projetos/projeto_de_roteiro/roteiros/criar",
            data={
                "titulo": "piloto",
                "cabecalho": "Header",
                "rodape": "Footer",
                "prefixo_cena": "00",
                "numeracao_inicial": "2",
                "tipo_roteiro": "shooting_script",
                "copyright": "on",
            },
        )
        self.assertEqual(resposta.status_code, 200)
        payload = resposta.get_json()
        self.assertTrue(payload["ok"])
        self.assertIn("/projetos/projeto_de_roteiro/roteiros/1/editar", payload["redirect"])

        resposta = self.client.post(
            "/api/projetos/projeto_de_roteiro/capitulos/1/autosave",
            json={"titulo": "piloto", "html": "<div class='roteiro-bloco'>Cena</div>"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.get_json()["ok"])

        projeto = manipulador_projetos.obter_projeto("projeto_de_roteiro")
        self.assertEqual(projeto["roteiros"][0]["titulo"], "PILOTO")



    def test_rotas_salvar_gut_retorna_arquivo_e_payload_desktop(self):
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
        self.client.post('/projetos/criar', data={'titulo': 'Livro Save', 'tipo': 'livro'})
        self.client.post('/projetos/livro_save/capitulos/criar', data={'titulo': 'Capítulo 1'})
        self.client.post('/api/projetos/livro_save/capitulos/1/autosave', json={'titulo': 'Capítulo 1', 'html': '<p>Texto salvo</p>'})

        resposta = self.client.get('/projetos/livro_save/salvar-capitulos')
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('.gut', resposta.headers.get('Content-Disposition', ''))

        resposta = self.client.get('/projetos/livro_save/salvar-capitulos?desktop_save=1')
        self.assertEqual(resposta.status_code, 200)
        payload = resposta.get_json()
        self.assertTrue(payload['ok'])
        self.assertTrue(payload['nome'].endswith('.gut'))

        self.client.post('/projetos/criar', data={'titulo': 'Roteiro Save', 'tipo': 'roteiro', 'contatos': 'autor@example.com'})
        self.client.post('/projetos/roteiro_save/roteiros/criar', data={'titulo': 'Piloto'})
        self.client.post('/api/projetos/roteiro_save/capitulos/1/autosave', json={'titulo': 'Piloto', 'html': '<div class="roteiro-bloco">Cena</div>'})

        resposta = self.client.get('/projetos/roteiro_save/salvar-roteiro?roteiro=1')
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('.gut', resposta.headers.get('Content-Disposition', ''))



    def test_importar_gut_livro_restabelece_metadados_e_redireciona_editor(self):
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
        self.client.post('/projetos/criar', data={'titulo': 'Origem', 'tipo': 'livro', 'autor': 'Ana', 'tags': 'fantasia'})
        self.client.post('/projetos/origem/capitulos/criar', data={'titulo': 'Cap 1'})
        self.client.post('/api/projetos/origem/capitulos/1/autosave', json={'titulo': 'Cap 1', 'html': '<p>Texto importado</p>'})
        resposta = self.client.get('/projetos/origem/salvar-capitulos')
        conteudo = resposta.data

        self.client.post('/projetos/criar', data={'titulo': 'Destino', 'tipo': 'livro'})
        resposta = self.client.post('/projetos/destino/importar-gut', data={'arquivo': (io.BytesIO(conteudo), 'pacote.gut')}, content_type='multipart/form-data')
        self.assertEqual(resposta.status_code, 200)
        payload = resposta.get_json()
        self.assertTrue(payload['ok'])
        self.assertIn('/projetos/destino/capitulos/1/editar', payload['redirect'])
        projeto = manipulador_projetos.obter_projeto('destino')
        self.assertEqual(projeto['autor'], 'Ana')
        capitulo = manipulador_capitulos.ler_capitulo(manipulador_projetos.obter_pasta_projeto('destino'), 1)
        self.assertIn('Texto importado', capitulo['paragrafos'][0])

    def test_importar_gut_rejeita_tipo_incompativel(self):
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
        self.client.post('/projetos/criar', data={'titulo': 'Origem Script', 'tipo': 'roteiro', 'contatos': 'autor@example.com'})
        self.client.post('/projetos/origem_script/roteiros/criar', data={'titulo': 'Piloto'})
        self.client.post('/api/projetos/origem_script/capitulos/1/autosave', json={'titulo': 'Piloto', 'html': '<div>Cena</div>'})
        resposta = self.client.get('/projetos/origem_script/salvar-roteiro?roteiro=1')
        conteudo = resposta.data

        self.client.post('/projetos/criar', data={'titulo': 'Livro Destino', 'tipo': 'livro'})
        resposta = self.client.post('/projetos/livro_destino/importar-gut', data={'arquivo': (io.BytesIO(conteudo), 'roteiro.gut')}, content_type='multipart/form-data')
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(resposta.get_json()['ok'])

    def test_catalogo_projeto_cria_e_exclui_item(self):
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
        self.client.post("/projetos/criar", data={"titulo": "Mundo", "tipo": "livro"})
        resposta = self.client.post(
            "/api/projetos/mundo/catalogo/personagens",
            json={"nome": "Ana", "descricao": "Heroína"},
        )
        self.assertEqual(resposta.status_code, 200)
        itens = resposta.get_json()["itens"]
        self.assertEqual(itens[0]["nome"], "ANA")

        resposta = self.client.post(
            "/api/projetos/mundo/catalogo/personagens/excluir",
            json={"nome": "ANA"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json()["itens"], [])

    def test_salvar_configuracoes_leitor(self):
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
        resposta = self.client.post(
            "/api/configuracoes/leitor",
            json={"tema": "tema-escuro", "fonte": "fonte-mono", "tamanho": 24},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.get_json()["ok"])

    def test_api_catalogo_roteiro_rejeita_tipo_invalido(self):
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
        self.client.post("/projetos/criar", data={"titulo": "Series", "tipo": "roteiro", "contatos": "+5511999999999"})
        self.client.post("/projetos/series/roteiros/criar", data={"titulo": "Ep 1"})
        resposta = self.client.post(
            "/api/projetos/series/roteiros/1/catalogo/objeto",
            json={"nome": "Mesa", "descricao": "Prop"},
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(resposta.get_json()["ok"])


    def test_pagina_creditos_usa_template_e_assets_renomeados(self):
        """Créditos: a rota /creditos renderiza o template creditos.html e o CSS renomeado."""
        resposta = self.client.get("/creditos")

        self.assertEqual(resposta.status_code, 200)
        html = resposta.get_data(as_text=True)
        self.assertIn("creditos.css", html)
        self.assertIn("nostrand@outlook.com.br", html)
        self.assertNotIn("credits.css", html)

    def test_templates_nao_mantem_credits_html_antigo(self):
        """Créditos: garante que o template antigo não volte a existir no projeto."""
        raiz = Path(__file__).resolve().parents[1]

        self.assertTrue((raiz / "templates" / "creditos.html").exists())
        self.assertFalse((raiz / "templates" / "credits.html").exists())
        self.assertTrue((raiz / "static" / "css" / "creditos.css").exists())
        self.assertFalse((raiz / "static" / "css" / "credits.css").exists())

    def test_configuracoes_abre_modal_com_identificadores_creditos(self):
        """Configurações: botão e modal usam os novos identificadores em português."""
        resposta = self.client.get("/configuracoes")

        self.assertEqual(resposta.status_code, 200)
        html = resposta.get_data(as_text=True)
        self.assertIn("data-open-creditos-modal", html)
        self.assertIn("creditosModal", html)
        self.assertNotIn("data-open-credits-modal", html)
        self.assertNotIn("creditsModal", html)
