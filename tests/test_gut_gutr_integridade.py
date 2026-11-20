from __future__ import annotations

import base64
from pathlib import Path

from modules import (
    exportador_gut,
    manipulador_capitulos,
    manipulador_projetos,
    manipulador_recursos_projeto,
    manipulador_roteiros,
    revisao_editorial,
)
from tests.test_support import IsolatedProjectTestCase


DATA_ANTIGA = "2024-02-03T04:05:06+00:00"
DATA_RECENTE = "2024-03-04T05:06:07+00:00"


class GutGutrIntegridadeTests(IsolatedProjectTestCase):
    def test_gut_livro_preserva_html_revisao_datas_e_metadados_editaveis(self):
        origem = manipulador_projetos.criar_projeto(
            "Livro Origem", descricao="Descrição completa", autor="Autora",
            tags=["fantasia", "mistério"], idioma="en_US", tipo="livro",
            contatos="contato@example.org",
        )
        pasta_origem = manipulador_projetos.obter_pasta_projeto(origem["slug"])
        capitulo = manipulador_capitulos.criar_capitulo(pasta_origem, "Capítulo preservado")
        manipulador_capitulos.salvar_capitulo(
            pasta_origem, capitulo["id"], "Capítulo preservado",
            '<h1>Capítulo preservado</h1><p>Conteúdo íntegro.</p>',
            data_criacao=DATA_ANTIGA, data_atualizacao=DATA_RECENTE,
        )
        segundo = manipulador_capitulos.criar_capitulo(pasta_origem, "Segundo capítulo")
        manipulador_capitulos.salvar_capitulo(
            pasta_origem, segundo["id"], "Segundo capítulo",
            '<p>O segundo capítulo também deve ser exportado.</p>',
        )
        arquivo = exportador_gut.exportar_gut_capitulos(origem["slug"])
        payload = exportador_gut.ler_payload_gut(arquivo)
        self.assertEqual(payload["conteudo"]["capitulos"][0]["data_criacao"], DATA_ANTIGA)
        self.assertEqual(payload["conteudo"]["capitulos"][0]["data_atualizacao"], DATA_RECENTE)
        self.assertIn("Conteúdo íntegro", payload["conteudo"]["capitulos"][0]["html"])
        self.assertEqual([item["titulo"] for item in payload["conteudo"]["capitulos"]],
                         ["Capítulo preservado", "Segundo capítulo"])

        destino = manipulador_projetos.criar_projeto("Livro Destino", tipo="livro")
        resultado = exportador_gut.importar_gut_em_projeto(destino["slug"], arquivo)
        pasta_destino = manipulador_projetos.obter_pasta_projeto(destino["slug"])
        capitulo_importado = manipulador_capitulos.ler_capitulo(pasta_destino, resultado["editor_numero"])
        projeto_importado = manipulador_projetos.obter_projeto(destino["slug"])

        self.assertEqual(capitulo_importado["data_criacao"], DATA_ANTIGA)
        self.assertEqual(capitulo_importado["data_atualizacao"], DATA_RECENTE)
        self.assertIn("Conteúdo íntegro", capitulo_importado["paragrafos"][0])
        self.assertEqual(projeto_importado["descricao"], "Descrição completa")
        self.assertEqual(projeto_importado["autor"], "Autora")
        self.assertEqual(projeto_importado["tags"], ["fantasia", "mistério"])
        self.assertEqual(projeto_importado["contatos"], "contato@example.org")
        self.assertEqual(projeto_importado["idioma"], "en_US")

    def test_gut_roteiro_preserva_todos_os_campos_e_datas(self):
        origem = manipulador_projetos.criar_projeto(
            "Roteiro Origem", descricao="Drama serializado", autor="Roteirista",
            idioma="pt-BR", tipo="roteiro", contatos="agente@example.org",
            informacoes_adicionais="Produção independente",
        )
        pasta_origem = manipulador_projetos.obter_pasta_projeto(origem["slug"])
        roteiro = manipulador_roteiros.criar_roteiro(
            pasta_origem, "Episódio piloto", cabecalho="ABERTURA", rodape="FIM",
            prefixo_cena="A", numeracao_inicial=12, logline="Uma descoberta",
            sinopse="Uma equipe encontra uma pista.", genero="Mistério",
            tipo_roteiro="shooting_script", copyright=True,
            data_criacao=DATA_ANTIGA, data_atualizacao=DATA_RECENTE,
        )
        html = '<div class="roteiro-bloco" data-block-type="scene_heading">INT. ARQUIVO - NOITE</div><div data-block-type="dialogue">A pista está aqui.</div>'
        manipulador_roteiros.salvar_roteiro(pasta_origem, roteiro["id"], "Episódio piloto", html)
        manipulador_roteiros.atualizar_roteiro_info(
            pasta_origem, roteiro["id"], {
                "personagens": ["LIA", "MARCOS"],
                "locais": ["ARQUIVO", "ESTAÇÃO"],
                "catalogo_personagens": [{"nome": "LIA", "descricao": "Investigadora"}],
                "catalogo_locais": [{"nome": "ARQUIVO", "descricao": "Local principal"}],
            },
            data_atualizacao=DATA_RECENTE,
        )
        arquivo = exportador_gut.exportar_gut_roteiro(origem["slug"], roteiro["id"])
        payload = exportador_gut.ler_payload_gut(arquivo)["conteudo"]["roteiro"]
        self.assertEqual(payload["data_criacao"], DATA_ANTIGA)
        self.assertEqual(payload["data_atualizacao"], DATA_RECENTE)
        self.assertEqual(payload["numeracao_inicial"], 12)
        self.assertEqual(payload["tipo_roteiro"], "shooting_script")
        self.assertTrue(payload["copyright"])
        self.assertEqual(payload["catalogo_personagens"][0]["descricao"], "Investigadora")

        destino = manipulador_projetos.criar_projeto("Roteiro Destino", tipo="roteiro")
        resultado = exportador_gut.importar_gut_em_projeto(destino["slug"], arquivo)
        pasta_destino = manipulador_projetos.obter_pasta_projeto(destino["slug"])
        roteiro_importado = manipulador_roteiros.ler_roteiro(pasta_destino, resultado["roteiro_importado"])
        projeto_importado = manipulador_projetos.obter_projeto(destino["slug"])

        self.assertEqual(roteiro_importado["data_criacao"], DATA_ANTIGA)
        self.assertEqual(roteiro_importado["data_atualizacao"], DATA_RECENTE)
        self.assertEqual(roteiro_importado["cabecalho"], "ABERTURA")
        self.assertEqual(roteiro_importado["rodape"], "FIM")
        self.assertEqual(roteiro_importado["prefixo_cena"], "A")
        self.assertEqual(roteiro_importado["numeracao_inicial"], 12)
        self.assertEqual(roteiro_importado["logline"], "Uma descoberta")
        self.assertEqual(roteiro_importado["sinopse"], "Uma equipe encontra uma pista.")
        self.assertEqual(roteiro_importado["genero"], "Mistério")
        self.assertEqual(roteiro_importado["tipo_roteiro"], "shooting_script")
        self.assertTrue(roteiro_importado["copyright"])
        self.assertEqual(roteiro_importado["personagens"], ["LIA", "MARCOS"])
        self.assertEqual(roteiro_importado["locais"], ["ARQUIVO", "ESTAÇÃO"])
        self.assertEqual(roteiro_importado["catalogo_personagens"], [{"nome": "LIA", "descricao": "Investigadora"}])
        self.assertEqual(roteiro_importado["catalogo_locais"], [{"nome": "ARQUIVO", "descricao": "Local principal"}])
        self.assertIn("A pista está aqui", roteiro_importado["html_editor"])
        self.assertEqual(projeto_importado["contatos"], "agente@example.org")
        self.assertEqual(projeto_importado["informacoes_adicionais"], "Produção independente")

    def _criar_gutr_completo(self, pasta_origem: Path) -> Path:
        recursos = manipulador_recursos_projeto.ler_recursos_projeto(pasta_origem)
        recursos["informacoes_abas"] = [
            {
                "id": "info_aba_cronologia", "titulo": "Cronologia",
                "data_criacao": DATA_ANTIGA, "data_atualizacao": DATA_RECENTE,
                "paginas": [{
                    "id": "info_pagina_cronologia", "titulo": "Linha do tempo",
                    "html": "<p>Evento inicial preservado.</p>",
                    "data_criacao": DATA_ANTIGA, "data_atualizacao": DATA_RECENTE,
                }],
            },
            {
                "id": "info_aba_mundo", "titulo": "Mundo",
                "data_criacao": DATA_ANTIGA, "data_atualizacao": DATA_RECENTE,
                "paginas": [{
                    "id": "info_pagina_mundo", "titulo": "Regras do mundo",
                    "html": "<p>Regra especial.</p>",
                    "data_criacao": DATA_ANTIGA, "data_atualizacao": DATA_RECENTE,
                }],
            },
        ]
        recursos["fluxos"] = [
            {
                "id": "fluxo_ato_1", "titulo": "Ato I",
                "data_criacao": DATA_ANTIGA, "data_atualizacao": DATA_RECENTE,
                "nodes": [
                    {"id": "no_inicio", "titulo": "Início", "texto": "A história começa", "x": 100, "y": 120},
                    {"id": "no_conflito", "titulo": "Conflito", "texto": "Surge um problema", "x": 400, "y": 220},
                ],
                "edges": [{"id": "ligacao_inicio_conflito", "from": "no_inicio", "to": "no_conflito", "fromSide": "right", "toSide": "left"}],
            },
            {
                "id": "fluxo_ato_2", "titulo": "Ato II",
                "data_criacao": DATA_ANTIGA, "data_atualizacao": DATA_RECENTE,
                "nodes": [{"id": "no_reviravolta", "titulo": "Reviravolta", "texto": "Nova informação", "x": 200, "y": 200}],
                "edges": [],
            },
        ]
        recursos["personagens_paginas"] = [{"id": "personagens_fichas", "titulo": "Fichas", "data_criacao": DATA_ANTIGA, "data_atualizacao": DATA_RECENTE}]
        recursos["lugares_paginas"] = [{"id": "lugares_cenarios", "titulo": "Cenários", "data_criacao": DATA_ANTIGA, "data_atualizacao": DATA_RECENTE}]
        recursos["anotacoes_paginas"] = [{"id": "anotacoes_segredos", "titulo": "Segredos", "data_criacao": DATA_ANTIGA, "data_atualizacao": DATA_RECENTE}]
        # PNG real e íntegro: o validador agora confere os bytes da imagem,
        # não apenas o prefixo e o tamanho da data URL.
        from io import BytesIO
        from PIL import Image

        buffer_imagem = BytesIO()
        Image.new("RGBA", (1, 1), (12, 34, 56, 255)).save(buffer_imagem, format="PNG")
        imagem_png = base64.b64encode(buffer_imagem.getvalue()).decode("ascii")
        recursos["personagens"] = [{
            "id": "personagem_ana", "pagina_id": "personagens_fichas", "nome": "ANA",
            "descricao": "Protagonista", "imagem": f"data:image/png;base64,{imagem_png}",
            "data_criacao": DATA_ANTIGA, "data_atualizacao": DATA_RECENTE,
        }]
        recursos["lugares"] = [{
            "id": "lugar_praca", "pagina_id": "lugares_cenarios", "nome": "PRAÇA",
            "descricao": "Local do encontro", "imagem": "", "data_criacao": DATA_ANTIGA, "data_atualizacao": DATA_RECENTE,
        }]
        recursos["anotacoes"] = [{
            "id": "nota_segredo", "pagina_id": "anotacoes_segredos", "nome": "SEGREDO",
            "descricao": "Uma pista importante", "data_criacao": DATA_ANTIGA, "data_atualizacao": DATA_RECENTE,
        }]
        recursos["ocultos"] = {
            "personagens": ["PERSONAGEM HERDADO"],
            "lugares": ["LOCAL HERDADO"],
            "anotacoes": ["ANOTAÇÃO HERDADA"],
        }
        recursos["planejamento"] = {
            "fontes": [{
                "id": "fonte_livro", "titulo": "Livro de pesquisa", "tipo": "livro",
                "autor": "Pesquisador", "url": "https://example.org/livro",
                "citacao": "Capítulo 3", "notas": "Consultar a edição revisada",
                "verificada": True, "data_criacao": DATA_ANTIGA, "data_atualizacao": DATA_RECENTE,
            }],
            "cenas": [{
                "id": "cena_descoberta", "titulo": "A descoberta", "resumo": "Encontram um registro.",
                "objetivo": "Revelar uma pista", "conflito": "O registro está incompleto.",
                "desfecho": "Uma data é identificada", "status": "em_andamento",
                "personagens": ["personagem_ana"], "lugares": ["lugar_praca"],
                "anotacoes": ["nota_segredo"], "referencias": ["fonte_livro"],
                "paginas_info": ["info_pagina_cronologia"], "nos_fluxo": ["no_inicio", "no_conflito"],
                "data_criacao": DATA_ANTIGA, "data_atualizacao": DATA_RECENTE,
            }],
        }
        manipulador_recursos_projeto.salvar_recursos_projeto(pasta_origem, recursos)
        projeto = manipulador_projetos.obter_projeto(pasta_origem.name)
        from unittest.mock import patch
        export_dir = pasta_origem / "exports"
        export_dir.mkdir(exist_ok=True)
        with patch.object(exportador_gut, "obter_projeto", return_value=projeto), \
             patch.object(exportador_gut, "obter_pasta_projeto", return_value=pasta_origem), \
             patch.object(exportador_gut, "obter_pasta_exportacao_projeto", return_value=export_dir):
            return exportador_gut.exportar_gutr_recursos(projeto["slug"])

    def test_gutr_preserva_recursos_imagens_ocultos_datas_multiplos_fluxos_e_vinculos(self):
        origem = manipulador_projetos.criar_projeto("GUTR Origem", tipo="livro")
        pasta_origem = manipulador_projetos.obter_pasta_projeto(origem["slug"])
        arquivo = self._criar_gutr_completo(pasta_origem)
        payload = exportador_gut.ler_payload_gutr(arquivo)
        self.assertEqual(payload["conteudo"]["quantidades"]["fluxogramas"], 2)
        self.assertEqual(payload["conteudo"]["quantidades"]["balões_fluxo"], 3)
        self.assertEqual(payload["conteudo"]["quantidades"]["ligacoes_fluxo"], 1)

        destino = manipulador_projetos.criar_projeto("GUTR Destino", tipo="livro")
        importacao = exportador_gut.importar_gutr_em_projeto(destino["slug"], arquivo)
        pasta_destino = manipulador_projetos.obter_pasta_projeto(destino["slug"])
        recursos = manipulador_recursos_projeto.ler_recursos_projeto(pasta_destino)

        self.assertEqual(importacao["importados"]["fluxogramas"], 2)
        self.assertEqual(importacao["importados"]["balões_fluxo"], 3)
        self.assertEqual(importacao["importados"]["ligacoes_fluxo"], 1)
        self.assertEqual(len(recursos["informacoes_abas"]), 2)
        self.assertEqual(len(recursos["fluxos"]), 2)
        self.assertEqual(sum(len(item["nodes"]) for item in recursos["fluxos"]), 3)
        self.assertEqual(sum(len(item["edges"]) for item in recursos["fluxos"]), 1)
        self.assertEqual(recursos["personagens"][0]["imagem"].split(",", 1)[0], "data:image/png;base64")
        self.assertEqual(recursos["personagens"][0]["data_criacao"], DATA_ANTIGA)
        self.assertEqual(recursos["personagens"][0]["data_atualizacao"], DATA_RECENTE)
        self.assertEqual(recursos["informacoes_abas"][0]["paginas"][0]["data_atualizacao"], DATA_RECENTE)
        self.assertEqual(recursos["fluxos"][0]["data_atualizacao"], DATA_RECENTE)
        self.assertEqual(recursos["ocultos"]["personagens"], ["PERSONAGEM HERDADO"])
        self.assertEqual(recursos["ocultos"]["lugares"], ["LOCAL HERDADO"])
        self.assertEqual(recursos["ocultos"]["anotacoes"], ["ANOTAÇÃO HERDADA"])

        cena = recursos["planejamento"]["cenas"][0]
        self.assertEqual(cena["personagens"], [recursos["personagens"][0]["id"]])
        self.assertEqual(cena["lugares"], [recursos["lugares"][0]["id"]])
        self.assertEqual(cena["anotacoes"], [recursos["anotacoes"][0]["id"]])
        self.assertEqual(cena["referencias"], [recursos["planejamento"]["fontes"][0]["id"]])
        self.assertEqual(cena["paginas_info"], [recursos["informacoes_abas"][0]["paginas"][0]["id"]])
        no_inicio = next(no for fluxo in recursos["fluxos"] for no in fluxo["nodes"] if no["titulo"] == "Início")
        self.assertEqual(cena["nos_fluxo"][0], no_inicio["id"])
        self.assertEqual(cena["data_criacao"], DATA_ANTIGA)
        self.assertEqual(cena["data_atualizacao"], DATA_RECENTE)

        # Um segundo ciclo .gutr conserva dados já importados e seus vínculos.
        do_meio = Path(self.base) / "segundo_ciclo"
        do_meio.mkdir()
        metadata = manipulador_projetos.obter_projeto(destino["slug"])
        export_dir = do_meio / "exports"
        export_dir.mkdir()
        from unittest.mock import patch
        with patch.object(exportador_gut, "obter_projeto", return_value=metadata), \
             patch.object(exportador_gut, "obter_pasta_projeto", return_value=pasta_destino), \
             patch.object(exportador_gut, "obter_pasta_exportacao_projeto", return_value=export_dir):
            segundo_arquivo = exportador_gut.exportar_gutr_recursos(destino["slug"])
        terceiro = manipulador_projetos.criar_projeto("GUTR Terceiro", tipo="livro")
        exportador_gut.importar_gutr_em_projeto(terceiro["slug"], segundo_arquivo)
        recursos_terceiro = manipulador_recursos_projeto.ler_recursos_projeto(
            manipulador_projetos.obter_pasta_projeto(terceiro["slug"])
        )
        self.assertEqual(recursos_terceiro["ocultos"], recursos["ocultos"])
        self.assertEqual([n["titulo"] for f in recursos_terceiro["fluxos"] for n in f["nodes"]],
                         [n["titulo"] for f in recursos["fluxos"] for n in f["nodes"]])
        self.assertEqual(recursos_terceiro["planejamento"]["cenas"][0]["titulo"], "A descoberta")


    def _reempacotar_payload(self, payload: dict, nome: str) -> Path:
        caminho = Path(self.base) / nome
        exportador_gut._empacotar_payload(payload, caminho)
        return caminho

    def test_gut_rejeita_revisao_editorial_invalida_antes_de_alterar_projeto(self):
        origem = manipulador_projetos.criar_projeto("GUT Revisão Inválida", tipo="livro")
        pasta_origem = manipulador_projetos.obter_pasta_projeto(origem["slug"])
        capitulo = manipulador_capitulos.criar_capitulo(pasta_origem, "Capítulo")
        manipulador_capitulos.salvar_capitulo(pasta_origem, capitulo["id"], "Capítulo", "<p>Conteúdo</p>")
        arquivo = exportador_gut.exportar_gut_capitulos(origem["slug"])
        payload = exportador_gut.ler_payload_gut(arquivo)
        payload["conteudo"]["capitulos"][0]["revisao_editorial"] = {
            "itens": [{"tipo": "comentario_desconhecido", "estado": "pendente", "trecho": "Conteúdo", "nota": "Nota", "inicio": 0}],
            "versoes": [],
        }
        arquivo_invalido = self._reempacotar_payload(payload, "revisao_invalida.gut")

        destino = manipulador_projetos.criar_projeto("Destino Sem Alterações", tipo="livro", descricao="Original")
        with self.assertRaisesRegex(ValueError, "tipo ou estado"):
            exportador_gut.importar_gut_em_projeto(destino["slug"], arquivo_invalido)
        projeto_depois = manipulador_projetos.obter_projeto(destino["slug"])
        self.assertEqual(projeto_depois["descricao"], "Original")
        self.assertEqual(projeto_depois["capitulos"], [])

    def test_exportacao_gutr_recusa_imagem_corrompida_no_banco_local(self):
        origem = manipulador_projetos.criar_projeto("Projeto com imagem local corrompida", tipo="livro")
        pasta_origem = manipulador_projetos.obter_pasta_projeto(origem["slug"])
        recursos = manipulador_recursos_projeto.ler_recursos_projeto(pasta_origem)
        recursos["personagens"] = [{
            "id": "personagem_corrompida",
            "pagina_id": recursos["personagens_paginas"][0]["id"],
            "nome": "PERSONAGEM",
            "descricao": "Ficha de teste",
            "imagem": "data:image/png;base64,AAAA",
        }]
        manipulador_recursos_projeto.salvar_recursos_projeto(pasta_origem, recursos)

        from unittest.mock import patch
        export_dir = pasta_origem / "exports"
        export_dir.mkdir(exist_ok=True)
        metadata = manipulador_projetos.obter_projeto(origem["slug"])
        with patch.object(exportador_gut, "obter_projeto", return_value=metadata), \
             patch.object(exportador_gut, "obter_pasta_projeto", return_value=pasta_origem), \
             patch.object(exportador_gut, "obter_pasta_exportacao_projeto", return_value=export_dir):
            with self.assertRaisesRegex(ValueError, "incompleta ou corrompida"):
                exportador_gut.exportar_gutr_recursos(origem["slug"])

    def test_gutr_rejeita_imagem_corrompida_sem_descartar_silenciosamente(self):
        origem = manipulador_projetos.criar_projeto("GUTR Imagem Inválida", tipo="livro")
        arquivo = self._criar_gutr_completo(manipulador_projetos.obter_pasta_projeto(origem["slug"]))
        payload = exportador_gut.ler_payload_gutr(arquivo)
        payload["conteudo"]["recursos"]["personagens"][0]["imagem"] = "data:image/png;base64,AAAA"
        arquivo_invalido = self._reempacotar_payload(payload, "imagem_invalida.gutr")

        destino = manipulador_projetos.criar_projeto("GUTR Destino Imagem", tipo="livro")
        pasta_destino = manipulador_projetos.obter_pasta_projeto(destino["slug"])
        antes = manipulador_recursos_projeto.ler_recursos_projeto(pasta_destino)
        with self.assertRaisesRegex(ValueError, "incompleta ou corrompida"):
            exportador_gut.importar_gutr_em_projeto(destino["slug"], arquivo_invalido)
        depois = manipulador_recursos_projeto.ler_recursos_projeto(pasta_destino)
        self.assertEqual(depois["personagens"], antes["personagens"])
        self.assertEqual(depois["informacoes_abas"], antes["informacoes_abas"])

    def test_gutr_rejeita_texto_que_seria_truncado_pelo_normalizador(self):
        origem = manipulador_projetos.criar_projeto("GUTR Texto Longo", tipo="livro")
        arquivo = self._criar_gutr_completo(manipulador_projetos.obter_pasta_projeto(origem["slug"]))
        payload = exportador_gut.ler_payload_gutr(arquivo)
        payload["conteudo"]["recursos"]["fluxos"][0]["nodes"][0]["texto"] = "x" * 4001
        arquivo_invalido = self._reempacotar_payload(payload, "texto_longo.gutr")
        with self.assertRaisesRegex(ValueError, "campo texto"):
            exportador_gut.ler_payload_gutr(arquivo_invalido)


    def test_gut_preserva_comentarios_e_versoes_da_revisao_editorial(self):
        origem = manipulador_projetos.criar_projeto("Livro com revisão", tipo="livro")
        pasta_origem = manipulador_projetos.obter_pasta_projeto(origem["slug"])
        capitulo = manipulador_capitulos.criar_capitulo(pasta_origem, "Capítulo revisado")
        manipulador_capitulos.salvar_capitulo(
            pasta_origem, capitulo["id"], "Capítulo revisado", "<p>Texto com revisão.</p>"
        )
        revisao_editorial.criar_item(pasta_origem, "livro", capitulo["id"], {
            "tipo": "comentario", "trecho": "Texto com revisão.",
            "nota": "Conferir a fonte desta afirmação.", "inicio": 0,
        })
        revisao_editorial.criar_versao(
            pasta_origem, "livro", capitulo["id"], "Versão antes da revisão",
            "<p>Texto original arquivado.</p>", "Antes",
        )
        arquivo = exportador_gut.exportar_gut_capitulos(origem["slug"])

        destino = manipulador_projetos.criar_projeto("Livro destino da revisão", tipo="livro")
        resultado = exportador_gut.importar_gut_em_projeto(destino["slug"], arquivo)
        pasta_destino = manipulador_projetos.obter_pasta_projeto(destino["slug"])
        estado = revisao_editorial.ler(
            pasta_destino, "livro", resultado["editor_numero"], incluir_html=True
        )
        self.assertEqual(len(estado["itens"]), 1)
        self.assertEqual(estado["itens"][0]["nota"], "Conferir a fonte desta afirmação.")
        self.assertEqual(len(estado["versoes"]), 1)
        self.assertEqual(estado["versoes"][0]["titulo"], "Versão antes da revisão")
        self.assertEqual(estado["versoes"][0]["rotulo"], "Antes")
        self.assertEqual(estado["versoes"][0]["html"], "<p>Texto original arquivado.</p>")

    def test_gut_rejeita_versao_editorial_com_hash_incorreto(self):
        origem = manipulador_projetos.criar_projeto("Livro revisão corrompida", tipo="livro")
        pasta_origem = manipulador_projetos.obter_pasta_projeto(origem["slug"])
        capitulo = manipulador_capitulos.criar_capitulo(pasta_origem, "Capítulo")
        manipulador_capitulos.salvar_capitulo(pasta_origem, capitulo["id"], "Capítulo", "<p>Texto.</p>")
        revisao_editorial.criar_versao(
            pasta_origem, "livro", capitulo["id"], "Versão válida", "<p>Conteúdo original.</p>"
        )
        arquivo = exportador_gut.exportar_gut_capitulos(origem["slug"])
        payload = exportador_gut.ler_payload_gut(arquivo)
        payload["conteudo"]["capitulos"][0]["revisao_editorial"]["versoes"][0]["hash"] = "0" * 64
        arquivo_invalido = self._reempacotar_payload(payload, "revisao_hash_invalido.gut")

        destino = manipulador_projetos.criar_projeto(
            "Destino sem mutação", tipo="livro", descricao="Não alterar"
        )
        with self.assertRaisesRegex(ValueError, "hash da versão"):
            exportador_gut.importar_gut_em_projeto(destino["slug"], arquivo_invalido)
        self.assertEqual(
            manipulador_projetos.obter_projeto(destino["slug"])["descricao"], "Não alterar"
        )
        self.assertEqual(
            manipulador_projetos.obter_projeto(destino["slug"])["capitulos"], []
        )

    def test_exportacao_gut_recusa_versao_editorial_ausente_ou_alterada(self):
        origem = manipulador_projetos.criar_projeto("Livro com arquivo de versão ausente", tipo="livro")
        pasta_origem = manipulador_projetos.obter_pasta_projeto(origem["slug"])
        capitulo = manipulador_capitulos.criar_capitulo(pasta_origem, "Capítulo")
        manipulador_capitulos.salvar_capitulo(pasta_origem, capitulo["id"], "Capítulo", "<p>Texto.</p>")
        versao = revisao_editorial.criar_versao(
            pasta_origem, "livro", capitulo["id"], "Versão arquivada", "<p>Não perder.</p>"
        )
        caminho_html = revisao_editorial.arquivo_versao(
            pasta_origem, "livro", capitulo["id"], versao["id"]
        )
        caminho_html.write_text("<p>Conteúdo alterado fora do editor.</p>", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "hash da versão"):
            exportador_gut.exportar_gut_capitulos(origem["slug"])

    def test_gutr_rejeita_item_vinculado_a_aba_inexistente(self):
        origem = manipulador_projetos.criar_projeto("GUTR vínculo inválido", tipo="livro")
        arquivo = self._criar_gutr_completo(
            manipulador_projetos.obter_pasta_projeto(origem["slug"])
        )
        payload = exportador_gut.ler_payload_gutr(arquivo)
        payload["conteudo"]["recursos"]["personagens"][0]["pagina_id"] = "aba_que_nao_existe"
        arquivo_invalido = self._reempacotar_payload(payload, "pagina_catalogo_invalida.gutr")

        destino = manipulador_projetos.criar_projeto("Destino GUTR sem mutação", tipo="livro")
        pasta_destino = manipulador_projetos.obter_pasta_projeto(destino["slug"])
        antes = manipulador_recursos_projeto.ler_recursos_projeto(pasta_destino)
        with self.assertRaisesRegex(ValueError, "aba inexistente"):
            exportador_gut.importar_gutr_em_projeto(destino["slug"], arquivo_invalido)
        depois = manipulador_recursos_projeto.ler_recursos_projeto(pasta_destino)
        self.assertEqual(depois["personagens"], antes["personagens"])
        self.assertEqual(depois["informacoes_abas"], antes["informacoes_abas"])

    def test_gutr_rejeita_excesso_de_abas_sem_alterar_destino(self):
        origem = manipulador_projetos.criar_projeto("GUTR Limites Origem", tipo="livro")
        pasta_origem = manipulador_projetos.obter_pasta_projeto(origem["slug"])
        arquivo = self._criar_gutr_completo(pasta_origem)

        destino = manipulador_projetos.criar_projeto("GUTR Limites Destino", tipo="livro")
        pasta_destino = manipulador_projetos.obter_pasta_projeto(destino["slug"])
        recursos = manipulador_recursos_projeto.ler_recursos_projeto(pasta_destino)
        recursos["informacoes_abas"] = [
            {
                "id": f"aba_cheia_{i}", "titulo": f"Informações {i}",
                "paginas": [{"id": f"pagina_cheia_{i}", "titulo": f"Conteúdo {i}", "html": "<p>Já preenchida</p>"}],
            }
            for i in range(7)
        ]
        manipulador_recursos_projeto.salvar_recursos_projeto(pasta_destino, recursos)
        antes = manipulador_recursos_projeto.ler_recursos_projeto(pasta_destino)

        with self.assertRaisesRegex(ValueError, "limite de 7 abas de Informações"):
            exportador_gut.importar_gutr_em_projeto(destino["slug"], arquivo)
        depois = manipulador_recursos_projeto.ler_recursos_projeto(pasta_destino)
        self.assertEqual([a["id"] for a in depois["informacoes_abas"]], [a["id"] for a in antes["informacoes_abas"]])
        self.assertEqual([a["titulo"] for a in depois["informacoes_abas"]], [a["titulo"] for a in antes["informacoes_abas"]])
