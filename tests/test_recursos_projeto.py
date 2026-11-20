from __future__ import annotations

import base64
import io
import random

from PIL import Image, ImageDraw

from modules import manipulador_projetos, manipulador_recursos_projeto as recursos, servidor_flask, utilidades, i18n
from tests.test_support import IsolatedProjectTestCase


class RecursosProjetoUnitTests(IsolatedProjectTestCase):
    def test_estrutura_padrao_respeita_idioma_da_interface(self):
        utilidades.salvar_configuracoes({"idioma_app": "en_US"})
        i18n.limpar_cache_i18n()

        dados = recursos.estrutura_padrao_recursos()

        self.assertEqual(dados["informacoes"][0]["titulo"], "Home page")
        self.assertIn("Project ideas", dados["informacoes"][0]["html"])
        self.assertEqual(dados["fluxo"], {"nodes": [], "edges": []})
        self.assertEqual(dados["ocultos"], {"personagens": [], "lugares": [], "anotacoes": []})

    def test_normalizar_recursos_saneia_paginas_fluxo_catalogos_e_aliases(self):
        dados = recursos.normalizar_recursos({
            "informacoes": [
                {"id": "info1", "titulo": "", "html": "<p>Oi\x00</p>"},
                "ignorar",
            ],
            "fluxo": {
                "nodes": [
                    {"id": "a", "x": -99999, "y": 99999, "width": 5, "height": 9999, "titulo": "", "texto": "A"},
                    {"id": "b", "x": 20, "y": 30, "titulo": "B", "texto": "B"},
                ],
                "edges": [
                    {"id": "ok", "from": "a", "to": "b", "fromSide": "bottom", "toSide": "top"},
                    {"from": "a", "to": "a"},
                    {"from": "a", "to": "nao_existe"},
                ],
            },
            "personagens": [
                {"nome": "Ana", "descricao": "Heroína", "imagem": "data:image/png;base64,abc"},
                {"nome": "ana", "descricao": "Duplicada"},
                {"nome": ""},
            ],
            "locais": [{"name": "Castelo", "description": "Antigo", "image": "http://externa"}],
            "notes": [{"title": "Regra", "text": "Não usar magia", "image": "data:image/png;base64,abc"}],
            "ocultos": {"personagens": ["Ana", "ana", ""], "lugares": ["Castelo"]},
        })

        self.assertEqual(dados["informacoes"][0]["titulo"], "Sem título")
        self.assertEqual(dados["informacoes"][0]["html"], "<p>Oi</p>")
        self.assertEqual(len(dados["fluxo"]["nodes"]), 2)
        self.assertEqual(dados["fluxo"]["nodes"][0]["titulo"], "Novo bloco")
        self.assertEqual(dados["fluxo"]["nodes"][0]["x"], -5000)
        self.assertEqual(dados["fluxo"]["nodes"][0]["y"], 5000)
        self.assertEqual(dados["fluxo"]["nodes"][0]["width"], 170)
        self.assertEqual(dados["fluxo"]["nodes"][0]["height"], 420)
        self.assertEqual(dados["fluxo"]["edges"], [{"id": "ok", "from": "a", "to": "b", "fromSide": "bottom", "toSide": "top"}])
        self.assertEqual([p["nome"] for p in dados["personagens"]], ["Ana"])
        self.assertEqual(dados["lugares"][0]["nome"], "Castelo")
        self.assertEqual(dados["lugares"][0]["imagem"], "")
        self.assertEqual(dados["anotacoes"][0]["nome"], "Regra")
        self.assertEqual(dados["anotacoes"][0]["imagem"], "")
        self.assertEqual(dados["ocultos"]["personagens"], ["Ana"])

    def test_imagem_referencia_grande_e_otimizada_sem_cortar_a_parte_inferior(self):
        # Imagem de alta entropia para ultrapassar o limite antigo de 900 mil
        # caracteres; faixas coloridas em ambas as extremidades detectam crop.
        largura, altura = 1000, 1600
        pixels = random.Random(42).randbytes(largura * altura * 3)
        imagem = Image.frombytes("RGB", (largura, altura), pixels)
        desenho = ImageDraw.Draw(imagem)
        desenho.rectangle((0, 0, largura - 1, 159), fill=(245, 35, 45))
        desenho.rectangle((0, 1450, largura - 1, altura - 1), fill=(25, 235, 70))

        buffer = io.BytesIO()
        imagem.save(buffer, format="PNG", compress_level=0)
        original = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        self.assertGreater(len(original), recursos.MAX_IMAGEM_DATA_URL)

        normalizada = recursos._imagem(original)

        self.assertTrue(normalizada.startswith("data:image/webp;base64,"))
        self.assertLessEqual(len(normalizada), recursos.MAX_IMAGEM_DATA_URL)
        dados_otimizados = base64.b64decode(normalizada.partition(",")[2])
        with Image.open(io.BytesIO(dados_otimizados)) as exibida:
            self.assertGreater(exibida.height, exibida.width)
            self.assertAlmostEqual(exibida.width / exibida.height, largura / altura, delta=0.01)
            topo = exibida.getpixel((exibida.width // 2, 5))
            base = exibida.getpixel((exibida.width // 2, exibida.height - 5))
            self.assertGreater(topo[0], topo[1] * 2)
            self.assertGreater(base[1], base[0] * 2)

    def test_imagem_referencia_legada_truncada_nao_e_exibida_como_se_estivesse_inteira(self):
        # Reproduz a versão anterior: data URL real cortada exatamente no limite.
        imagem = Image.frombytes("RGB", (500, 500), random.Random(3).randbytes(500 * 500 * 3))
        buffer = io.BytesIO()
        imagem.save(buffer, format="PNG", compress_level=0)
        original = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        self.assertGreater(len(original), recursos.MAX_IMAGEM_DATA_URL)
        truncada = original[:recursos.MAX_IMAGEM_DATA_URL]

        self.assertEqual(len(truncada), recursos.MAX_IMAGEM_DATA_URL)
        self.assertEqual(recursos._imagem(truncada), "")
        with self.assertRaises(ValueError):
            recursos._imagem(truncada + "A")
        dados = recursos.normalizar_recursos({
            "personagens": [{"nome": "Imagem antiga", "imagem": truncada}],
            "lugares": [{"nome": "Lugar antigo", "imagem": truncada}],
        })
        self.assertTrue(dados["personagens"][0]["imagem_necessita_reenvio"])
        self.assertTrue(dados["lugares"][0]["imagem_necessita_reenvio"])

    def test_imagem_referencia_persistida_permanece_inteira_apos_leitura(self):
        largura, altura = 800, 1200
        imagem = Image.new("RGB", (largura, altura), (30, 60, 90))
        ImageDraw.Draw(imagem).rectangle((0, altura - 120, largura - 1, altura - 1), fill=(20, 230, 80))
        buffer = io.BytesIO()
        imagem.save(buffer, format="PNG", compress_level=0)
        original = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")

        pasta = self.projects / "referencias-visuais"
        pasta.mkdir(parents=True, exist_ok=True)
        recursos.salvar_item_catalogo_projeto(
            pasta, "personagens", {"nome": "Personagem de teste", "imagem": original}
        )
        recursos.salvar_item_catalogo_projeto(
            pasta, "lugares", {"nome": "Lugar de teste", "imagem": original}
        )
        dados = recursos.ler_recursos_projeto(pasta)

        for tipo in ("personagens", "lugares"):
            imagem_salva = dados[tipo][0]["imagem"]
            self.assertLessEqual(len(imagem_salva), recursos.MAX_IMAGEM_DATA_URL)
            pixels_salvos = base64.b64decode(imagem_salva.partition(",")[2])
            with Image.open(io.BytesIO(pixels_salvos)) as exibida:
                pixel_inferior = exibida.getpixel((exibida.width // 2, exibida.height - 5))
                self.assertGreater(pixel_inferior[1], pixel_inferior[0] * 2)

    def test_aviso_de_reenvio_legado_permanece_ate_uma_nova_imagem_ser_anexada(self):
        pasta = self.projects / "referencia-legada"
        pasta.mkdir(parents=True, exist_ok=True)
        recursos.salvar_item_catalogo_projeto(
            pasta, "personagens", {
                "nome": "Referência antiga",
                "imagem": "",
                "imagem_necessita_reenvio": True,
            }
        )
        dados = recursos.ler_recursos_projeto(pasta)
        self.assertTrue(dados["personagens"][0]["imagem_necessita_reenvio"])

        imagem = Image.new("RGB", (120, 180), (30, 60, 90))
        buffer = io.BytesIO()
        imagem.save(buffer, format="PNG")
        nova_imagem = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        recursos.salvar_item_catalogo_projeto(
            pasta, "personagens", {
                "id": dados["personagens"][0]["id"],
                "nome": "Referência antiga",
                "imagem": nova_imagem,
                "imagem_necessita_reenvio": False,
            }
        )
        atualizado = recursos.ler_recursos_projeto(pasta)["personagens"][0]
        self.assertFalse(atualizado["imagem_necessita_reenvio"])
        self.assertTrue(atualizado["imagem"].startswith("data:image/png;base64,"))

    def test_persistencia_salva_informacoes_fluxo_catalogo_e_exclusao(self):
        pasta = self.projects / "universo"
        pasta.mkdir(parents=True, exist_ok=True)

        recursos.salvar_informacoes_projeto(pasta, [{"id": "i1", "titulo": "Esboço", "html": "<h2>Mundo</h2>"}])
        recursos.salvar_fluxo_projeto(pasta, {
            "nodes": [{"id": "n1", "titulo": "Ato I"}, {"id": "n2", "titulo": "Ato II"}],
            "edges": [{"from": "n1", "to": "n2"}],
        })
        recursos.salvar_item_catalogo_projeto(pasta, "personagens", {"nome": "Ana", "descricao": "Heroína"})
        recursos.salvar_item_catalogo_projeto(pasta, "locais", {"nome": "Castelo", "descricao": "Cenário"})
        recursos.salvar_item_catalogo_projeto(pasta, "notes", {"nome": "Regra", "descricao": "Sem magia", "imagem": "data:image/png;base64,abc"})
        dados = recursos.ler_recursos_projeto(pasta)

        self.assertEqual(dados["informacoes"][0]["titulo"], "Esboço")
        self.assertEqual(dados["fluxo"]["edges"][0]["from"], "n1")
        self.assertEqual(dados["personagens"][0]["nome"], "Ana")
        self.assertEqual(dados["lugares"][0]["nome"], "Castelo")
        self.assertEqual(dados["anotacoes"][0]["imagem"], "")

        atualizados = recursos.excluir_item_catalogo_projeto(pasta, "personagens", nome="Ana")
        self.assertEqual(atualizados["personagens"], [])
        self.assertEqual(atualizados["ocultos"]["personagens"], ["Ana"])

    def test_mesclar_catalogo_com_roteiros_respeita_ocultos_e_prioriza_projeto(self):
        dados = recursos.normalizar_recursos({
            "personagens": [{"nome": "Ana", "descricao": "Versão projeto"}],
            "lugares": [{"nome": "Castelo", "descricao": "Projeto"}],
            "anotacoes": [{"nome": "Regra", "descricao": "Projeto"}],
            "ocultos": {"personagens": ["Bruno"], "lugares": []},
        })
        combinados = recursos.mesclar_catalogo_com_roteiros(dados, [
            {
                "titulo": "Piloto",
                "catalogo_personagens": [
                    {"nome": "Ana", "descricao": "Versão roteiro"},
                    {"nome": "Bruno", "descricao": "Oculto"},
                    {"nome": "Clara", "descricao": "Roteiro"},
                ],
                "catalogo_locais": [{"nome": "Porto", "descricao": "Roteiro"}],
            }
        ])

        personagens = {item["nome"]: item for item in combinados["personagens_combinados"]}
        lugares = {item["nome"]: item for item in combinados["lugares_combinados"]}
        self.assertEqual(personagens["Ana"]["descricao"], "Versão projeto")
        self.assertEqual(personagens["Ana"]["origem"], "projeto")
        self.assertIn("Clara", personagens)
        self.assertNotIn("Bruno", personagens)
        self.assertIn("Porto", lugares)
        self.assertEqual(combinados["anotacoes_combinadas"][0]["nome"], "Regra")


class RecursosProjetoFlaskTests(IsolatedProjectTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.app = servidor_flask.criar_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def test_apis_de_recursos_cobrem_informacoes_fluxo_catalogo_e_editor(self):
        self.client.post("/projetos/criar", data={"titulo": "Mundo", "tipo": "livro"})

        resposta = self.client.get("/api/projetos/mundo/recursos")
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.get_json()["ok"])

        resposta = self.client.post(
            "/api/projetos/mundo/recursos/informacoes",
            json={"informacoes": [{"id": "i1", "titulo": "Esboço", "html": "<p>Base</p>"}]},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json()["informacoes"][0]["titulo"], "Esboço")

        resposta = self.client.post(
            "/api/projetos/mundo/recursos/fluxo",
            json={"fluxo": {"nodes": [{"id": "a"}, {"id": "b"}], "edges": [{"from": "a", "to": "b"}]}},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.get_json()["fluxo"]["edges"]), 1)

        resposta = self.client.post(
            "/api/projetos/mundo/recursos/catalogo/personagens",
            json={"nome": "Ana", "descricao": "Heroína"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json()["personagens"][0]["nome"], "Ana")

        resposta = self.client.post(
            "/api/projetos/mundo/recursos/catalogo/anotacoes",
            json={"nome": "Regra", "descricao": "Sem magia", "imagem": "data:image/png;base64,abc"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json()["anotacoes"][0]["imagem"], "")

        resposta = self.client.get("/api/projetos/mundo/catalogo")
        payload = resposta.get_json()
        self.assertEqual(payload["personagens"][0]["nome"], "Ana")
        self.assertEqual(payload["anotacoes"][0]["nome"], "Regra")

        resposta = self.client.post(
            "/api/projetos/mundo/recursos/catalogo/personagens/excluir",
            json={"nome": "Ana"},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.get_json()["personagens"], [])
        self.assertEqual(resposta.get_json()["ocultos"]["personagens"], ["Ana"])

    def test_pagina_recursos_e_modal_do_editor_usam_ingles(self):
        utilidades.salvar_configuracoes({"idioma_app": "en_US"})
        i18n.limpar_cache_i18n()
        self.client.post("/projetos/criar", data={"titulo": "World", "tipo": "livro"})
        self.client.post("/projetos/world/capitulos/criar", data={"titulo": "Chapter"})

        resposta = self.client.get("/projetos/world/recursos")
        html = resposta.get_data(as_text=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Project planning", html)
        self.assertIn("Add balloon", html)
        self.assertIn("Reference image", html)
        self.assertNotIn("Planejamento do projeto", html)

        resposta = self.client.get("/projetos/world/capitulos/1/editar")
        html = resposta.get_data(as_text=True)
        self.assertIn("Project outline", html)
        self.assertIn("Open panel", html)
        self.assertIn("Outline", html)

    def test_documentacao_inclui_recursos_do_projeto_nos_dois_idiomas(self):
        raiz = utilidades.RAIZ_PROJETO
        script = (raiz / "documentation" / "script.js").read_text(encoding="utf-8")
        readme = (raiz / "README.md").read_text(encoding="utf-8")

        self.assertIn("recursos-projeto", script)
        self.assertIn("Project outline", script)
        self.assertIn("Rascunho do projeto", script)
        self.assertIn("Painel Rascunho do projeto", readme)
