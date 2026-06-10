from __future__ import annotations

import io
import zipfile
from pathlib import Path

from modules import manipulador_biblioteca, servidor_flask, utilidades
from tests.test_support import IsolatedProjectTestCase


PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c636000000200015d0b2a0000000000"
    "49454e44ae426082"
)


def criar_epub_minimo(destino: Path, titulo: str = "Saga Aurora - Volume 1", autor: str = "Ana Autor") -> Path:
    """Cria um EPUB mínimo, porém válido, com metadados, capa, nav e dois capítulos."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w") as epub:
        epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        epub.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>""",
        )
        epub.writestr(
            "OEBPS/content.opf",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">urn:uuid:test-book</dc:identifier>
    <dc:title>{titulo}</dc:title>
    <dc:creator>{autor}</dc:creator>
    <dc:language>pt-BR</dc:language>
    <meta name="cover" content="cover" />
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="cover" href="Images/cover.png" media-type="image/png" properties="cover-image"/>
    <item id="cap1" href="Text/cap1.xhtml" media-type="application/xhtml+xml"/>
    <item id="cap2" href="Text/cap2.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="cap1"/>
    <itemref idref="cap2"/>
  </spine>
</package>""",
        )
        epub.writestr(
            "OEBPS/nav.xhtml",
            """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
  <head><title>Sumário</title></head>
  <body><nav epub:type="toc"><ol>
    <li><a href="Text/cap1.xhtml#inicio">Capítulo Um</a></li>
    <li><a href="Text/cap2.xhtml">Capítulo Dois</a></li>
  </ol></nav></body>
</html>""",
        )
        epub.writestr(
            "OEBPS/Text/cap1.xhtml",
            """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Capítulo Um</title></head>
<body><h1 id="inicio">Capítulo Um</h1><p>Primeira página da biblioteca.</p></body></html>""",
        )
        epub.writestr(
            "OEBPS/Text/cap2.xhtml",
            """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Capítulo Dois</title></head>
<body><h1>Capítulo Dois</h1><p>Segunda página da biblioteca.</p></body></html>""",
        )
        epub.writestr("OEBPS/Images/cover.png", PNG_1X1)
    return destino


class BibliotecaBackendTests(IsolatedProjectTestCase):
    def adicionar_epub(self, nome: str = "saga_aurora_v1.epub", titulo: str = "Saga Aurora - Volume 1") -> dict:
        caminho = criar_epub_minimo(self.base / nome, titulo=titulo)
        return manipulador_biblioteca.adicionar_livro_epub(caminho)

    def test_adicionar_epub_extrai_metadados_capa_toc_e_capitulos(self):
        livro = self.adicionar_epub()

        self.assertEqual(livro["titulo"], "Saga Aurora - Volume 1")
        self.assertEqual(livro["autor"], "Ana Autor")
        self.assertEqual(livro["idioma"], "pt-BR")
        self.assertEqual(livro["cover_path"], "OEBPS/Images/cover.png")
        self.assertEqual([cap["titulo"] for cap in livro["capitulos"]], ["Capítulo Um", "Capítulo Dois"])
        self.assertEqual(livro["capitulos"][0]["fragmento_inicial"], "inicio")
        self.assertTrue((self.library / livro["slug"] / "livro.json").exists())
        self.assertTrue((self.library / livro["slug"] / "extraido" / "OEBPS" / "Text" / "cap1.xhtml").exists())

    def test_listagem_colecoes_progresso_e_ordem_de_leitura(self):
        v1 = self.adicionar_epub("aurora1.epub", "Saga Aurora - Volume 1")
        v2 = self.adicionar_epub("aurora2.epub", "Saga Aurora - Volume 2")

        atualizado = manipulador_biblioteca.atualizar_progresso_livro(v1["slug"], 2, 50, posicao=321)
        self.assertEqual(atualizado["ultimo_lido"], 2)
        self.assertEqual(atualizado["posicoes_leitura"]["2"], 321)
        self.assertAlmostEqual(atualizado["progresso_percentual"], 75.0)
        self.assertFalse(atualizado["foi_lido"])

        livros = manipulador_biblioteca.listar_livros()
        self.assertEqual(livros[0]["slug"], v1["slug"])
        self.assertTrue(all(livro["tem_colecao"] for livro in livros))
        self.assertEqual({livro["nome_colecao"] for livro in livros}, {"Saga Aurora"})
        self.assertEqual(manipulador_biblioteca.listar_colecoes_livros()[0]["total"], 2)

    def test_marcar_lido_desmarcar_e_excluir_remove_progresso(self):
        livro = self.adicionar_epub()
        marcado = manipulador_biblioteca.marcar_livro_como_lido(livro["slug"], True)
        self.assertTrue(marcado["foi_lido"])
        self.assertEqual(marcado["progresso_percentual"], 100.0)

        desmarcado = manipulador_biblioteca.marcar_livro_como_lido(livro["slug"], False)
        self.assertFalse(utilidades.obter_progresso()["livros"][livro["slug"]]["marcado_lido"])
        self.assertTrue(desmarcado["foi_lido"])  # Continua concluído após ter sido finalizado uma vez.

        progresso = utilidades.obter_progresso()
        self.assertIn(livro["slug"], progresso.get("livros", {}))
        manipulador_biblioteca.excluir_livro(livro["slug"])
        self.assertFalse((self.library / livro["slug"]).exists())
        self.assertNotIn(livro["slug"], utilidades.obter_progresso().get("livros", {}))

    def test_obter_capitulo_arquivo_capa_mime_e_bloqueio_path_traversal(self):
        livro = self.adicionar_epub()
        livro_lido, atual, anterior, proximo = manipulador_biblioteca.obter_capitulo_livro(livro["slug"], 1)

        self.assertEqual(livro_lido["titulo"], "Saga Aurora - Volume 1")
        self.assertEqual(atual["asset_path"], "OEBPS/Text/cap1.xhtml")
        self.assertIsNone(anterior)
        self.assertEqual(proximo["titulo"], "Capítulo Dois")

        arquivo = manipulador_biblioteca.obter_arquivo_extraido(livro["slug"], atual["asset_path"])
        self.assertEqual(manipulador_biblioteca.mime_por_arquivo(arquivo), "application/xhtml+xml")
        self.assertTrue(manipulador_biblioteca.obter_caminho_capa(livro["slug"]).name.endswith("cover.png"))
        with self.assertRaises(FileNotFoundError):
            manipulador_biblioteca.obter_arquivo_extraido(livro["slug"], "../../livro.json")


class BibliotecaFlaskRoutesTests(IsolatedProjectTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.app = servidor_flask.criar_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def adicionar_epub(self, nome: str = "rota.epub", titulo: str = "Rota Biblioteca - Volume 1") -> dict:
        caminho = criar_epub_minimo(self.base / nome, titulo=titulo)
        return manipulador_biblioteca.adicionar_livro_epub(caminho)

    def test_pagina_biblioteca_exibe_livro_filtros_e_colecoes(self):
        self.adicionar_epub("rota1.epub", "Rota Biblioteca - Volume 1")
        self.adicionar_epub("rota2.epub", "Rota Biblioteca - Volume 2")

        resposta = self.client.get("/biblioteca")
        self.assertEqual(resposta.status_code, 200)
        html = resposta.get_data(as_text=True)
        self.assertIn("Rota Biblioteca - Volume 1", html)
        self.assertIn("biblioteca.css", html)
        self.assertIn("data-filtro=\"lendo\"", html)
        self.assertIn("data-colecao-filtro=\"rota_biblioteca\"", html)

    def test_upload_epub_rota_adiciona_livro_e_rejeita_extensao_invalida(self):
        epub_bytes = (criar_epub_minimo(self.base / "upload.epub", titulo="Upload Livro")).read_bytes()
        resposta = self.client.post(
            "/biblioteca/adicionar",
            data={"epubs": (io.BytesIO(epub_bytes), "upload.epub")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resposta.status_code, 200)
        payload = resposta.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["adicionados"][0]["titulo"], "Upload Livro")

        resposta = self.client.post(
            "/biblioteca/adicionar",
            data={"epubs": (io.BytesIO(b"texto"), "notas.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertFalse(resposta.get_json()["ok"])

    def test_rotas_leitura_servem_capa_capitulo_posicao_e_redirecionamento(self):
        livro = self.adicionar_epub()

        resposta = self.client.get(f"/biblioteca/{livro['slug']}", follow_redirects=False)
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(f"/biblioteca/{livro['slug']}/capitulos/1/ler", resposta.headers["Location"])

        resposta = self.client.get(f"/biblioteca/{livro['slug']}/capitulos/1/ler")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Capítulo Um", resposta.get_data(as_text=True))

        resposta = self.client.get(f"/biblioteca/{livro['slug']}/arquivo/OEBPS/Text/cap1.xhtml")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Primeira página da biblioteca", resposta.get_data(as_text=True))

        resposta = self.client.get(f"/biblioteca/{livro['slug']}/capa")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.mimetype, "image/png")

        resposta = self.client.post(
            f"/api/biblioteca/{livro['slug']}/capitulos/2/posicao",
            json={"posicao": 777, "percentual": 96},
        )
        self.assertEqual(resposta.status_code, 200)
        payload = resposta.get_json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["foi_lido"])

        resposta = self.client.get(f"/biblioteca/{livro['slug']}", follow_redirects=False)
        self.assertIn(f"/biblioteca/{livro['slug']}/capitulos/2/ler", resposta.headers["Location"])

    def test_rota_marcar_lido_e_excluir_livro(self):
        livro = self.adicionar_epub()
        resposta = self.client.post(f"/api/biblioteca/{livro['slug']}/marcar-lido", json={"lido": True})
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.get_json()["foi_lido"])

        resposta = self.client.post(f"/biblioteca/{livro['slug']}/excluir")
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.get_json()["ok"])
        self.assertFalse((self.library / livro["slug"]).exists())
