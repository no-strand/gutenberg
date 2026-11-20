"""Etapa 4: importação PDF nativa e regressão com biblioteca EPUB."""
from __future__ import annotations

import hashlib
from pathlib import Path
import unittest

import fitz

from modules import manipulador_biblioteca as bib
from modules.leitor_pdf_nativo import (
    inspecionar_pdf, miniatura_pdf, renderizar_pagina_pdf,
    texto_pagina_pdf, pesquisar_pdf,
)
from tests.test_support import IsolatedProjectTestCase


def criar_pdf(caminho: Path, *, senha: bool = False) -> Path:
    doc = fitz.open()
    for indice, texto in enumerate(('Era uma vez um LIVRO especial', 'Segundo capítulo: flores e árvores', 'Fim da história do livro')):
        page = doc.new_page(width=595, height=842)
        page.insert_text((60, 80), texto, fontsize=16)
    doc.set_metadata({'title': 'O Livro Diagramado', 'author': 'Autora Teste'})
    doc.set_toc([[1, 'Capítulo A', 1], [2, 'Subcapítulo', 2], [1, 'Capítulo B', 3]])
    kwargs = {'encryption': fitz.PDF_ENCRYPT_AES_256, 'user_pw': 'senha', 'owner_pw': 'dono'} if senha else {}
    doc.save(str(caminho), **kwargs)
    doc.close()
    return caminho


class PdfNativoTests(IsolatedProjectTestCase):
    def test_importa_original_sem_converter_metadados_sumario_capa(self):
        origem = criar_pdf(self.base / 'Meu Livro.pdf')
        sha = hashlib.sha256(origem.read_bytes()).hexdigest()
        livro = bib.adicionar_livro_pdf_nativo(origem)
        self.assertEqual(livro['tipo_documento'], 'pdf')
        self.assertEqual(livro['modo_importacao'], 'nativo')
        self.assertEqual(livro['titulo'], 'O Livro Diagramado')
        self.assertEqual(livro['autor'], 'Autora Teste')
        self.assertEqual(livro['pdf_total_paginas'], 3)
        self.assertEqual([i['pagina'] for i in livro['pdf_sumario']], [1, 2, 3])
        self.assertEqual(hashlib.sha256(bib.obter_caminho_pdf(livro['slug']).read_bytes()).hexdigest(), sha)
        self.assertTrue(bib.obter_caminho_capa(livro['slug']).read_bytes().startswith(b'\x89PNG'))
        self.assertTrue(bib.listar_livros()[0]['tem_capa'])
        self.assertEqual(bib.obter_livro(livro['slug'])['total_capitulos'], 3)
        self.assertEqual(len(livro['capitulos']), 0)

    def test_paginas_renderizacao_busca_texto(self):
        origem = criar_pdf(self.base / 'L.pdf')
        meta = inspecionar_pdf(origem)
        self.assertEqual(meta['paginas'], 3)
        self.assertTrue(miniatura_pdf(origem).startswith(b'\x89PNG'))
        self.assertTrue(renderizar_pagina_pdf(origem, 2, 1.0).startswith(b'\x89PNG'))
        self.assertIn('Segundo capítulo', texto_pagina_pdf(origem, 2))
        hits = pesquisar_pdf(origem, 'livro')
        self.assertEqual([hit['pagina'] for hit in hits], [1, 3])
        self.assertEqual(pesquisar_pdf(origem, 'x'), [])
        for pagina in [0, 4]:
            with self.assertRaises(FileNotFoundError):
                renderizar_pagina_pdf(origem, pagina)
            with self.assertRaises(FileNotFoundError):
                texto_pagina_pdf(origem, pagina)

    def test_progressao_paginacao_e_retomada(self):
        livro = bib.adicionar_livro_pdf_nativo(criar_pdf(self.base / 'progresso.pdf'))
        slug = livro['slug']
        atualizado = bib.atualizar_progresso_livro(slug, 2, 100)
        self.assertAlmostEqual(atualizado['progresso_percentual'], 66.67, places=1)
        self.assertEqual(bib.obter_livro(slug)['ultimo_lido'], 2)
        concluido = bib.atualizar_progresso_livro(slug, 3, 100)
        self.assertEqual(concluido['progresso_percentual'], 100)
        self.assertTrue(concluido['foi_lido'])
        bib.excluir_livro(slug)
        with self.assertRaises(FileNotFoundError):
            bib.obter_caminho_pdf(slug)

    def test_nao_aceita_arquivo_invalido_ou_criptografado(self):
        bruto = self.base / 'falso.pdf'
        bruto.write_bytes(b'not really a pdf')
        with self.assertRaises(ValueError):
            bib.adicionar_livro_pdf_nativo(bruto)
        self.assertEqual(list(self.library.iterdir()), [])
        criptografado = criar_pdf(self.base / 'senha.pdf', senha=True)
        with self.assertRaisesRegex(ValueError, 'senha'):
            bib.adicionar_livro_pdf_nativo(criptografado)
        self.assertEqual(list(self.library.iterdir()), [])

    def test_slugs_distintos_e_bloqueio_de_metadado_de_caminho(self):
        pdf = criar_pdf(self.base / 'same.pdf')
        livro1 = bib.adicionar_livro_pdf_nativo(pdf)
        livro2 = bib.adicionar_livro_pdf_nativo(pdf)
        self.assertNotEqual(livro1['slug'], livro2['slug'])
        from modules.persistencia_json import ler_json, salvar_json
        json_path = self.library / livro1['slug'] / 'livro.json'
        meta = ler_json(json_path,{})
        meta['arquivo_pdf'] = '../same.pdf'
        salvar_json(json_path,meta)
        with self.assertRaises(FileNotFoundError):
            bib.obter_caminho_pdf(livro1['slug'])

    def test_conversao_pdf_epub_anterior_continua_disponivel(self):
        livro = bib.adicionar_livro_pdf(criar_pdf(self.base / 'modo_anterior.pdf'))
        self.assertTrue(livro['capitulos'])
        self.assertEqual(livro['arquivo_original_pdf'], 'modo_anterior.pdf')
        self.assertNotEqual(livro.get('tipo_documento'), 'pdf')

    def test_pdf_nativo_nao_afeta_leitor_epub(self):
        # Em ambiente sem Flask, isola um EPUB mínimo sem importar servidor_flask.
        import zipfile
        origem = self.base / 'e.epub'
        with zipfile.ZipFile(origem,'w') as z:
            z.writestr('mimetype','application/epub+zip', compress_type=zipfile.ZIP_STORED)
            z.writestr('META-INF/container.xml','<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
            z.writestr('OEBPS/content.opf','<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" unique-identifier="id" version="3.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">urn:uuid:test</dc:identifier><dc:title>Teste</dc:title><dc:creator>Autora</dc:creator><dc:language>pt-BR</dc:language></metadata><manifest><item id="c1" href="one.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="c1"/></spine></package>')
            z.writestr('OEBPS/one.xhtml', '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Capítulo Um</title></head><body><h1>Capítulo Um</h1><p>Olá.</p></body></html>')
        epub = bib.adicionar_livro_epub(origem)
        self.assertTrue(epub['capitulos'])
        self.assertNotEqual(epub.get('tipo_documento'), 'pdf')
        with self.assertRaises(FileNotFoundError):
            bib.obter_caminho_pdf(epub['slug'])



if __name__ == '__main__':
    unittest.main()
