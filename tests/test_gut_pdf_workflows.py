from __future__ import annotations

import io
from pathlib import Path

import fitz

from modules import (
    exportador_gut,
    importador_documentos,
    manipulador_capitulos,
    manipulador_projetos,
    manipulador_roteiros,
    servidor_flask,
)
from tests.test_support import IsolatedProjectTestCase


def _criar_pdf_simples(caminho: Path, linhas: list[tuple[str, float, float, int]]):
    """Cria um PDF mínimo para testar importação sem depender de arquivos externos."""
    doc = fitz.open()
    pagina = doc.new_page(width=612, height=792)
    y = 72
    for texto, x, tamanho, flags in linhas:
        pagina.insert_text((x, y), texto, fontsize=tamanho, fontname="helv", render_mode=0)
        y += 28
    doc.save(caminho)
    doc.close()
    return caminho


class GutWorkflowTests(IsolatedProjectTestCase):
    """Cobertura do ciclo .gut: criação, leitura, validação e importação."""

    def test_criar_arquivo_gut_livro_grava_assinatura_payload_e_extensao(self):
        projeto = manipulador_projetos.criar_projeto("Livro Snapshot", tipo="livro", autor="Ana", tags=["drama"])
        pasta = manipulador_projetos.obter_pasta_projeto(projeto["slug"])
        capitulo = manipulador_capitulos.criar_capitulo(pasta, "Capítulo A")
        manipulador_capitulos.salvar_capitulo(pasta, capitulo["id"], "Capítulo A", "<h1>Capítulo A</h1><p>Conteúdo .gut</p>")

        arquivo = exportador_gut.exportar_gut_capitulos(projeto["slug"])

        self.assertEqual(arquivo.suffix, ".gut")
        self.assertTrue(arquivo.exists())
        self.assertEqual(arquivo.read_bytes()[:4], exportador_gut.MAGIC)
        payload = exportador_gut.ler_payload_gut(arquivo)
        self.assertEqual(payload["container"], "gutenberg_gut")
        self.assertEqual(payload["tipo_arquivo"], "livro")
        self.assertEqual(payload["projeto"]["autor"], "Ana")
        self.assertIn("Conteúdo .gut", payload["conteudo"]["capitulos"][0]["texto"])

    def test_importar_arquivo_gut_roteiro_preserva_conteudo_e_catalogos(self):
        origem = manipulador_projetos.criar_projeto("Roteiro Origem", tipo="roteiro", contatos="autor@example.com")
        pasta_origem = manipulador_projetos.obter_pasta_projeto(origem["slug"])
        roteiro = manipulador_roteiros.criar_roteiro(pasta_origem, "Piloto", genero="Drama", logline="Uma fuga noturna")
        manipulador_roteiros.salvar_roteiro(
            pasta_origem,
            roteiro["id"],
            "Piloto",
            '<div class="roteiro-bloco" data-block-type="scene_heading">INT. CASA - NOITE</div>'
            '<div class="roteiro-bloco" data-block-type="character">ANA</div>'
            '<div class="roteiro-bloco" data-block-type="dialogue">Precisamos ir.</div>',
        )
        manipulador_roteiros.atualizar_roteiro_info(
            pasta_origem,
            roteiro["id"],
            {"personagens": ["ANA"], "locais": ["CASA"], "catalogo_personagens": [{"nome": "ANA", "descricao": "Protagonista"}]},
        )
        arquivo = exportador_gut.exportar_gut_roteiro(origem["slug"], roteiro["id"])

        destino = manipulador_projetos.criar_projeto("Roteiro Destino", tipo="roteiro")
        resultado = exportador_gut.importar_gut_em_projeto(destino["slug"], arquivo)

        self.assertEqual(resultado["tipo_arquivo"], "roteiro")
        self.assertEqual(resultado["roteiro_importado"], 1)
        pasta_destino = manipulador_projetos.obter_pasta_projeto(destino["slug"])
        roteiro_importado = manipulador_roteiros.ler_roteiro(pasta_destino, 1)
        self.assertIn("Precisamos ir.", roteiro_importado["html"])
        self.assertEqual(roteiro_importado["genero"], "Drama")
        self.assertIn("ANA", roteiro_importado["personagens"])
        self.assertIn("CASA", roteiro_importado["locais"])

    def test_ler_payload_gut_rejeita_arquivo_corrompido(self):
        projeto = manipulador_projetos.criar_projeto("Livro Corrompido", tipo="livro")
        pasta = manipulador_projetos.obter_pasta_projeto(projeto["slug"])
        capitulo = manipulador_capitulos.criar_capitulo(pasta, "Cap")
        manipulador_capitulos.salvar_capitulo(pasta, capitulo["id"], "Cap", "<p>Texto</p>")
        arquivo = exportador_gut.exportar_gut_capitulos(projeto["slug"])
        dados = bytearray(arquivo.read_bytes())
        dados[-1] ^= 0xFF
        corrompido = self.base / "corrompido.gut"
        corrompido.write_bytes(dados)

        with self.assertRaisesRegex(ValueError, "Integridade"):
            exportador_gut.ler_payload_gut(corrompido)


class PdfImportWorkflowTests(IsolatedProjectTestCase):
    """Cobertura de importação de PDF como capítulo, roteiro e upload Flask."""

    def test_importar_pdf_como_capitulo_preserva_titulo_e_paragrafos(self):
        manipulador_projetos.criar_projeto("Livro PDF", tipo="livro")
        pdf = _criar_pdf_simples(
            self.base / "capitulo_pdf.pdf",
            [
                ("Capítulo PDF", 250, 18, 0),
                ("Primeiro parágrafo importado do PDF.", 72, 11, 0),
                ("Segundo parágrafo importado do PDF.", 72, 11, 0),
            ],
        )

        resultado = importador_documentos.importar_documento_como_capitulo("livro_pdf", pdf)

        self.assertTrue(resultado["ok"])
        pasta = manipulador_projetos.obter_pasta_projeto("livro_pdf")
        capitulo = manipulador_capitulos.ler_capitulo(pasta, 1)
        html = "".join(capitulo["paragrafos"])
        self.assertIn("Capítulo PDF", html)
        self.assertIn("Primeiro parágrafo importado do PDF", html)
        self.assertIn("Segundo parágrafo importado do PDF", html)

    def test_importar_pdf_como_roteiro_classifica_cabecalho_personagem_e_dialogo(self):
        manipulador_projetos.criar_projeto("Roteiro PDF", tipo="roteiro")
        pdf = _criar_pdf_simples(
            self.base / "roteiro_pdf.pdf",
            [
                ("ROTEIRO PDF", 250, 18, 0),
                ("Autor: Ana Silva", 72, 11, 0),
                ("Contato: ana@example.com", 72, 11, 0),
                ("INT. CASA - DIA", 72, 12, 0),
                ("MARIA", 285, 12, 0),
                ("Olá do PDF.", 230, 12, 0),
            ],
        )

        resultado = importador_documentos.importar_documento_como_roteiro("roteiro_pdf", pdf)

        self.assertTrue(resultado["ok"])
        projeto = manipulador_projetos.obter_projeto("roteiro_pdf")
        self.assertEqual(projeto["autor"], "Ana Silva")
        self.assertEqual(projeto["contatos"], "ana@example.com")
        pasta = manipulador_projetos.obter_pasta_projeto("roteiro_pdf")
        roteiro = manipulador_roteiros.ler_roteiro(pasta, 1)
        self.assertIn('data-block-type="scene_heading"', roteiro["html"])
        self.assertIn('data-block-type="character"', roteiro["html"])
        self.assertIn('data-block-type="dialogue"', roteiro["html"])
        self.assertIn("MARIA", roteiro["personagens"])
        self.assertIn("CASA", roteiro["locais"])

    def test_rota_importar_pdf_upload_cria_capitulo(self):
        app = servidor_flask.criar_app()
        app.config.update(TESTING=True)
        client = app.test_client()
        client.post("/projetos/criar", data={"titulo": "Upload PDF", "tipo": "livro"})
        pdf = _criar_pdf_simples(
            self.base / "upload_pdf.pdf",
            [("Capítulo Upload", 250, 18, 0), ("Texto vindo da rota de upload PDF.", 72, 11, 0)],
        )

        resposta = client.post(
            "/projetos/upload_pdf/importar-gut",
            data={"arquivo": (io.BytesIO(pdf.read_bytes()), "upload_pdf.pdf")},
            content_type="multipart/form-data",
        )

        self.assertEqual(resposta.status_code, 200)
        payload = resposta.get_json()
        self.assertTrue(payload["ok"])
        self.assertIn("/projetos/upload_pdf/capitulos/1/editar", payload["redirect"])
        pasta = manipulador_projetos.obter_pasta_projeto("upload_pdf")
        capitulo = manipulador_capitulos.ler_capitulo(pasta, 1)
        self.assertIn("Texto vindo da rota de upload PDF", "".join(capitulo["paragrafos"]))

    def test_fluxo_gut_pendente_importa_para_projeto_existente(self):
        app = servidor_flask.criar_app()
        app.config.update(TESTING=True)
        client = app.test_client()
        origem = manipulador_projetos.criar_projeto("Pendente Origem", tipo="livro", autor="Autor Gut")
        pasta_origem = manipulador_projetos.obter_pasta_projeto(origem["slug"])
        capitulo = manipulador_capitulos.criar_capitulo(pasta_origem, "Cap Pendente")
        manipulador_capitulos.salvar_capitulo(pasta_origem, capitulo["id"], "Cap Pendente", "<p>Conteúdo pendente</p>")
        arquivo = exportador_gut.exportar_gut_capitulos(origem["slug"])
        destino = manipulador_projetos.criar_projeto("Pendente Destino", tipo="livro")

        registrar = client.post("/api/gut/pendente/registrar", json={"caminho": str(arquivo)})
        self.assertEqual(registrar.status_code, 200)
        self.assertTrue(registrar.get_json()["contexto"]["ativo"])

        contexto = client.get("/api/gut/pendente/contexto")
        self.assertEqual(contexto.status_code, 200)
        self.assertEqual(contexto.get_json()["contexto"]["tipo_projeto"], "livro")

        importar = client.post("/api/gut/pendente/importar", json={"slug": destino["slug"]})
        self.assertEqual(importar.status_code, 200)
        self.assertTrue(importar.get_json()["ok"])
        pasta_destino = manipulador_projetos.obter_pasta_projeto(destino["slug"])
        capitulo_importado = manipulador_capitulos.ler_capitulo(pasta_destino, 1)
        self.assertIn("Conteúdo pendente", "".join(capitulo_importado["paragrafos"]))
