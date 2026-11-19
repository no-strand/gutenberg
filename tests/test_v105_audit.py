"""Regressões V1.0.5: configurações, biblioteca e arquivos reais de exportação."""
from __future__ import annotations

import io
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import fitz
from docx import Document

from modules import (exportador_documentos, exportador_html, exportador_gut, importador_documentos, manipulador_recursos_projeto,
                     manipulador_biblioteca, manipulador_capitulos,
                     manipulador_projetos, manipulador_roteiros, utilidades)
from tests.test_support import IsolatedProjectTestCase


class Gutenberg105AuditTests(IsolatedProjectTestCase):
    def setUp(self):
        super().setUp()
        self._old_epub_root = exportador_html.PASTA_PROJETOS
        exportador_html.PASTA_PROJETOS = self.projects

    def tearDown(self):
        exportador_html.PASTA_PROJETOS = self._old_epub_root
        super().tearDown()

    def test_versao_e_intensidade_padrao(self):
        self.assertEqual(utilidades.APP_VERSAO, '1.0.6')
        self.assertEqual(utilidades.obter_configuracoes()['intensidade_particulas'], 1)
        cfg = utilidades.obter_configuracoes()
        cfg['intensidade_particulas'] = 5
        utilidades.salvar_configuracoes(cfg)
        self.assertEqual(utilidades.obter_configuracoes()['intensidade_particulas'], 5)

    def test_pdf_importado_nao_apaga_epub_existente(self):
        pdf = self.base / 'livro.pdf'
        pdf.write_bytes(b'%PDF-1.4\n')
        existente = self.base / 'livro.epub'
        existente.write_bytes(b'EPUB ORIGINAL NAO DEVE SUMIR')
        sentinel = existente.read_bytes()
        with patch.object(manipulador_biblioteca, 'converter_pdf_para_epub3') as converter, \
             patch.object(manipulador_biblioteca, 'adicionar_livro_epub', return_value={'slug':'importado'}) as adicionar, \
             patch.object(manipulador_biblioteca, 'atualizar_metadados_livro'):
            def simular(pdf_origem, epub_saida):
                self.assertNotEqual(epub_saida.resolve(), existente.resolve())
                epub_saida.write_bytes(b'epub gerado')
            converter.side_effect = simular
            resultado = manipulador_biblioteca.adicionar_livro_pdf(pdf)
            self.assertEqual(resultado['slug'], 'importado')
            self.assertTrue(adicionar.called)
        self.assertEqual(existente.read_bytes(), sentinel)

    def test_epub_com_caminho_inseguro_e_descartado(self):
        z = self.base / 'inseguro.epub'
        with zipfile.ZipFile(z, 'w') as archive:
            archive.writestr('../malicioso.txt', 'não extrair')
        with self.assertRaises(ValueError):
            manipulador_biblioteca.adicionar_livro_epub(z)
        self.assertFalse((self.library / 'inseguro').exists())

    def test_projeto_vazio_e_recusado(self):
        with self.assertRaises(ValueError):
            manipulador_projetos.criar_projeto('   ')

    def test_exportacoes_livro_reais_validas(self):
        projeto = manipulador_projetos.criar_projeto('Livro QA', autor='Autora Teste', tipo='livro')
        pasta = manipulador_projetos.obter_pasta_projeto(projeto['slug'])
        capitulo = manipulador_capitulos.criar_capitulo(pasta, 'Prólogo')
        numero = capitulo.get('id', 1)
        manipulador_capitulos.salvar_capitulo(pasta, numero, 'Prólogo', '<h1>Prólogo</h1><p>Primeiro parágrafo do ensaio.</p><p>Segundo parágrafo.</p>')

        epub2 = exportador_html.exportar_projeto_epub(projeto['slug'], '2.0')
        self._verificar_epub(epub2, '2.0', 'Primeiro parágrafo')
        epub3 = exportador_html.exportar_projeto_epub(projeto['slug'], '3.0')
        self._verificar_epub(epub3, '3.0', 'Primeiro parágrafo')
        pasta_xhtml = exportador_html.exportar_projeto_xhtml(projeto['slug'])
        documentos = list(pasta_xhtml.glob('*.xhtml'))
        self.assertTrue(documentos)
        self.assertIn('Primeiro parágrafo', documentos[0].read_text(encoding='utf-8'))
        ET.parse(documentos[0])
        self.assertTrue((pasta_xhtml / 'Style' / 'stylesheet.css').exists())

        docx = exportador_documentos.exportar_projeto_docx(projeto['slug'])
        pdf = exportador_documentos.exportar_projeto_pdf(projeto['slug'])
        self.assertTrue(docx.exists() and docx.stat().st_size > 1000)
        texto_docx = '\n'.join(p.text for p in Document(docx).paragraphs)
        self.assertIn('Primeiro parágrafo', texto_docx)
        with fitz.open(pdf) as doc:
            self.assertGreaterEqual(len(doc), 2)
            text = '\n'.join(pg.get_text() for pg in doc)
            self.assertIn('Primeiro parágrafo', text)

        # Biblioteca deve conseguir reler o EPUB que o projeto gerou.
        livro = manipulador_biblioteca.adicionar_livro_epub(epub3)
        self.assertIn('Livro', livro['titulo'])
        self.assertTrue(livro['capitulos'])

    def _verificar_epub(self, arquivo, version, snippet):
        self.assertTrue(arquivo.exists())
        with zipfile.ZipFile(arquivo) as z:
            self.assertEqual(z.testzip(), None)
            self.assertEqual(z.namelist()[0], 'mimetype')
            self.assertEqual(z.getinfo('mimetype').compress_type, zipfile.ZIP_STORED)
            self.assertEqual(z.read('mimetype'), b'application/epub+zip')
            opf = ET.fromstring(z.read('Misc/content.opf'))
            self.assertEqual(opf.attrib['version'], version)
            spine = opf.find('{http://www.idpf.org/2007/opf}spine')
            self.assertIsNotNone(spine)
            self.assertGreaterEqual(len(spine), 2)
            self.assertTrue(any(snippet.encode('utf-8') in z.read(name) for name in z.namelist() if name.endswith('.xhtml')))
            if version == '3.0':
                self.assertIn('Text/nav.xhtml', z.namelist())

    def test_epub_imagem_embutida_possui_caminho_relativo_valido(self):
        import base64
        import posixpath
        projeto = manipulador_projetos.criar_projeto('Livro Imagens QA', tipo='livro')
        pasta = manipulador_projetos.obter_pasta_projeto(projeto['slug'])
        cap = manipulador_capitulos.criar_capitulo(pasta, 'Ilustrações')
        # PNG mínimo real.
        from PIL import Image
        img = Image.new('RGB', (3, 3), 'red')
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        dado = base64.b64encode(buffer.getvalue()).decode('ascii')
        manipulador_capitulos.salvar_capitulo(pasta, cap['id'], 'Ilustrações',
            f'<p>Uma imagem.</p><img src="data:image/png;base64,{dado}" alt="Ilustração"/>')
        for version in ('2.0', '3.0'):
            epub = exportador_html.exportar_projeto_epub(projeto['slug'], version)
            with zipfile.ZipFile(epub) as z:
                chapters = [n for n in z.namelist() if n.startswith('Text/') and n.endswith('.xhtml') and 'cover' not in n and 'nav.xhtml' not in n]
                self.assertTrue(chapters)
                xhtml = ET.fromstring(z.read(chapters[0]))
                image = xhtml.find('.//{http://www.w3.org/1999/xhtml}img')
                self.assertIsNotNone(image)
                src = image.attrib.get('src')
                self.assertTrue(src.startswith('../Images/'), src)
                asset = posixpath.normpath(posixpath.join(posixpath.dirname(chapters[0]), src))
                self.assertIn(asset, z.namelist())
                self.assertEqual(z.read(asset), buffer.getvalue())

    def test_gut_livro_e_gutr_recursos_reimportam_sem_perda(self):
        original = manipulador_projetos.criar_projeto('Livro Backup Origem', tipo='livro')
        folder = manipulador_projetos.obter_pasta_projeto(original['slug'])
        chapter = manipulador_capitulos.criar_capitulo(folder, 'Parte Um')
        manipulador_capitulos.salvar_capitulo(folder, chapter['id'], 'Parte Um', '<p>Trecho protegido do livro.</p>')
        dados = manipulador_recursos_projeto.ler_recursos_projeto(folder)
        dados['informacoes_abas'][0]['paginas'][0]['html'] = '<p>Notas do rascunho.</p>'
        manipulador_recursos_projeto.salvar_recursos_projeto(folder, dados)
        gut = exportador_gut.exportar_gut_capitulos(original['slug'])
        gutr = exportador_gut.exportar_gutr_recursos(original['slug'])
        self.assertEqual(exportador_gut.ler_payload_gut(gut)['app_versao'], '1.0.6')
        self.assertEqual(exportador_gut.ler_payload_gutr(gutr)['tipo_arquivo'], 'recursos')
        novo = manipulador_projetos.criar_projeto('Livro Backup Destino', tipo='livro')
        resultado = exportador_gut.importar_gut_em_projeto(novo['slug'], gut)
        self.assertEqual(resultado['capitulos_importados'], 1)
        self.assertIn('Trecho protegido', ''.join(manipulador_capitulos.ler_capitulo(
            manipulador_projetos.obter_pasta_projeto(novo['slug']), 1)['paragrafos']))
        importacao = exportador_gut.importar_gutr_em_projeto(novo['slug'], gutr)
        self.assertTrue(importacao['ok'])
        recursos = manipulador_recursos_projeto.ler_recursos_projeto(
            manipulador_projetos.obter_pasta_projeto(novo['slug']))
        self.assertTrue(any('Notas do rascunho.' in pagina['html'] for pagina in recursos['informacoes']))

    def test_roteiro_gut_reimporta_e_pdf_importa_em_novo_roteiro(self):
        original = manipulador_projetos.criar_projeto('Roteiro de Backup', tipo='roteiro')
        pasta = manipulador_projetos.obter_pasta_projeto(original['slug'])
        r = manipulador_roteiros.criar_roteiro(pasta, 'Roteiro')
        html = ('<div data-block-type="scene_heading">INT. SALA - DIA</div>'
                '<div data-block-type="character">LIA</div>'
                '<div data-block-type="dialogue">A reunião começou.</div>')
        manipulador_roteiros.salvar_roteiro(pasta, r['id'], 'Roteiro', html)
        gut = exportador_gut.exportar_gut_roteiro(original['slug'], r['id'])
        destino = manipulador_projetos.criar_projeto('Roteiro Recebido', tipo='roteiro')
        resposta = exportador_gut.importar_gut_em_projeto(destino['slug'], gut)
        self.assertEqual(resposta['roteiro_importado'], 1)
        self.assertIn('A reunião começou.', manipulador_roteiros.ler_roteiro(
            manipulador_projetos.obter_pasta_projeto(destino['slug']), 1)['html_editor'])
        pdf = exportador_documentos.exportar_roteiro_pdf(original['slug'], r['id'])
        outro = manipulador_projetos.criar_projeto('Roteiro PDF Import', tipo='roteiro')
        imported = importador_documentos.importar_documento_como_roteiro(outro['slug'], pdf)
        self.assertTrue(imported['ok'])

    def test_exportacoes_roteiro_profissional(self):
        projeto = manipulador_projetos.criar_projeto('Roteiro QA', autor='Roteirista Teste', tipo='roteiro')
        pasta = manipulador_projetos.obter_pasta_projeto(projeto['slug'])
        roteiro = manipulador_roteiros.criar_roteiro(pasta, 'Cena Um', tipo_roteiro='spec_script')
        numero = roteiro.get('id', 1)
        html = ('<div data-block-type="scene_heading">INT. CASA - DIA</div>'
                '<div data-block-type="action">A porta se abre lentamente.</div>'
                '<div data-block-type="character">ANA</div>'
                '<div data-block-type="dialogue">Onde está a chave?</div>'
                '<div data-block-type="transition">CORTE PARA:</div>')
        manipulador_roteiros.salvar_roteiro(pasta, numero, 'Cena Um', html)
        pdf = exportador_documentos.exportar_roteiro_pdf(projeto['slug'], numero)
        docx = exportador_documentos.exportar_roteiro_docx(projeto['slug'], numero)
        with fitz.open(pdf) as doc:
            self.assertGreaterEqual(len(doc), 2)
            text = '\n'.join(pg.get_text() for pg in doc)
            self.assertIn('INT. CASA - DIA', text)
            self.assertIn('Onde está a chave?', text)
            self.assertTrue(all(abs(pg.rect.width - 612) < 1 and abs(pg.rect.height - 792) < 1 for pg in doc))
            page = doc[-1]
            fonts = {item[3] for item in page.get_fonts(full=True)}
            self.assertTrue(any('Courier' in font for font in fonts), fonts)
        documento = Document(docx)
        self.assertAlmostEqual(documento.sections[0].page_width.inches, 8.5, places=2)
        self.assertAlmostEqual(documento.sections[0].page_height.inches, 11, places=2)
        self.assertAlmostEqual(documento.sections[0].left_margin.inches, 1.5, places=2)
        self.assertAlmostEqual(documento.sections[0].right_margin.inches, 1, places=2)
        texto = '\n'.join(p.text for p in documento.paragraphs)
        self.assertIn('INT. CASA - DIA', texto)
        self.assertIn('Onde está a chave?', texto)
        corpo = [p for p in documento.paragraphs if 'INT. CASA' in p.text]
        self.assertTrue(corpo)
        self.assertEqual(corpo[0].runs[0].font.size.pt, 12)
        self.assertIn('Courier', corpo[0].runs[0].font.name)

