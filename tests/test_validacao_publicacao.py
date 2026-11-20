"""Etapa 3: validação pré-publicação, integração e conferência de arquivos."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
import base64
import tempfile

from PIL import Image

from modules import (
    exportador_documentos, exportador_html, manipulador_capitulos,
    manipulador_projetos, manipulador_roteiros, revisao_editorial,
    validacao_publicacao,
)
from tests.test_support import IsolatedProjectTestCase


class PublicacaoTests(IsolatedProjectTestCase):
    def livro(self, titulo='Obra de Teste', autor='Maria'):
        return manipulador_projetos.criar_projeto(titulo, autor=autor, descricao='Sinopse.', tipo='livro')

    def capitulo(self, projeto, titulo='Capítulo 1', html='<p>Texto do capítulo.</p>'):
        pasta = manipulador_projetos.obter_pasta_projeto(projeto['slug'])
        cap = manipulador_capitulos.criar_capitulo(pasta, titulo)
        manipulador_capitulos.salvar_capitulo(pasta, cap['id'], titulo, html)
        return cap

    def codigos(self, resultado):
        return {(x['codigo'], x['nivel']) for x in resultado['itens']}

    def test_livro_antigo_sem_conteudo_sinaliza_mas_nao_bloqueia(self):
        p = self.livro(autor='')
        resultado = validacao_publicacao.validar_publicacao(p['slug'])
        self.assertTrue(resultado['aprovado'])
        for codigo in ('sem_capitulos', 'capa_ausente', 'autor_ausente'):
            self.assertIn((codigo, 'aviso'), self.codigos(resultado))
        self.assertEqual(resultado['erros'], 0)
        self.assertEqual(resultado['documentos'], 0)
        xhtml = validacao_publicacao.validar_publicacao(p['slug'], formato='xhtml')
        self.assertIn(('sem_capitulos_xhtml', 'erro'), self.codigos(xhtml))

    def test_metadados_capa_corrompida_e_versao_invalida_bloqueiam(self):
        p = self.livro()
        pasta = manipulador_projetos.obter_pasta_projeto(p['slug'])
        (pasta / 'cover.jpg').write_bytes(b'not an image')
        resultado = validacao_publicacao.validar_publicacao(p['slug'], formato='epub', versao='9.9')
        self.assertFalse(resultado['aprovado'])
        self.assertIn(('capa_corrompida','erro'), self.codigos(resultado))
        self.assertIn(('versao_invalida','erro'), self.codigos(resultado))
        self.assertIn(('formato_invalido','erro'), self.codigos(validacao_publicacao.validar_publicacao(p['slug'], formato='exe')))

    def test_sugestoes_pendentes_conteudo_duplicado_e_imagem_externa(self):
        p = self.livro()
        cap = self.capitulo(p, 'Repetido', '<p>Meu texto.</p><img src="https://site.example/figura.png">')
        self.capitulo(p, 'Repetido', '<p>Outro texto</p>')
        pasta = manipulador_projetos.obter_pasta_projeto(p['slug'])
        item = revisao_editorial.criar_item(pasta,'livro',cap['id'],{
            'tipo':'comentario', 'trecho':'Meu', 'nota':'Rever', 'inicio':0
        })
        resultado = validacao_publicacao.validar_publicacao(p['slug'], formato='epub')
        for codigo in ('titulos_repetidos', 'revisoes_pendentes', 'img_externa'):
            self.assertIn((codigo,'aviso'), self.codigos(resultado))
        self.assertTrue(resultado['aprovado'])
        revisao_editorial.alterar_item(pasta,'livro',cap['id'],item['id'],'resolvido')
        self.assertNotIn(('revisoes_pendentes','aviso'), self.codigos(validacao_publicacao.validar_publicacao(p['slug'])))

    def test_imagem_embutida_valida_e_invalida(self):
        p = self.livro()
        buf = BytesIO()
        Image.new('RGB', (2,2), 'white').save(buf,format='PNG')
        src = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
        cap = self.capitulo(p, html=f'<p>Texto.</p><img src="{src}">')
        self.assertNotIn(('img_corrompida','erro'), self.codigos(validacao_publicacao.validar_publicacao(p['slug'])))
        pasta = manipulador_projetos.obter_pasta_projeto(p['slug'])
        manipulador_capitulos.salvar_capitulo(pasta,cap['id'],'Capítulo 1','<p>Texto.</p><img src="data:image/png;base64,%%%%">')
        self.assertIn(('img_corrompida','erro'), self.codigos(validacao_publicacao.validar_publicacao(p['slug'])))

    def test_roteiro_alvo_invalidos_e_revisao(self):
        p = manipulador_projetos.criar_projeto('Roteiro de Teste', autor='Miguel', tipo='roteiro')
        pasta = manipulador_projetos.obter_pasta_projeto(p['slug'])
        r = manipulador_roteiros.criar_roteiro(pasta,'Piloto')
        manipulador_roteiros.salvar_roteiro(pasta, r['id'], 'Piloto', '<div data-block-type="action">Texto de ação.</div>')
        vazio = validacao_publicacao.validar_publicacao(p['slug'], formato='pdf')
        self.assertIn(('roteiro_nao_selecionado','erro'), self.codigos(vazio))
        ok = validacao_publicacao.validar_publicacao(p['slug'], formato='pdf', roteiro=r['id'])
        self.assertTrue(ok['aprovado'])
        self.assertEqual(ok['documentos'], 1)
        invalidos = validacao_publicacao.validar_publicacao(p['slug'], formato='epub', roteiro=r['id'],tipo_documento='desconhecido')
        self.assertIn(('formato_invalido','erro'), self.codigos(invalidos))
        self.assertIn(('tipo_documento_invalido','erro'), self.codigos(invalidos))
        revisao_editorial.criar_item(pasta,'roteiro',r['id'],{'tipo':'comentario','trecho':'Texto','nota':'Corrigir','inicio':0})
        self.assertIn(('revisoes_pendentes','aviso'), self.codigos(validacao_publicacao.validar_publicacao(p['slug'],formato='pdf',roteiro=r['id'])))

    def test_conferir_artefatos_epub2_epub3_docx_pdf_xhtml(self):
        p = self.livro()
        self.capitulo(p)
        # O exportador EPUB lê o caminho global importado no carregamento do módulo.
        with patch.object(exportador_html,'PASTA_PROJETOS', self.projects):
            for versao in ('2.0','3.0'):
                f = exportador_html.exportar_projeto_epub(p['slug'], versao)
                validacao_publicacao.conferir_arquivo_exportado(f,'epub')
            folder = exportador_html.exportar_projeto_xhtml(p['slug'])
            validacao_publicacao.conferir_arquivo_exportado(folder,'xhtml')
        docx = exportador_documentos.exportar_projeto_docx(p['slug'])
        pdf = exportador_documentos.exportar_projeto_pdf(p['slug'])
        validacao_publicacao.conferir_arquivo_exportado(docx,'docx')
        validacao_publicacao.conferir_arquivo_exportado(pdf,'pdf')
        f = self.base / 'invalido.epub'
        f.write_bytes(b'arquivo incompleto')
        with self.assertRaises(ValueError):
            validacao_publicacao.conferir_arquivo_exportado(f,'epub')
        with self.assertRaises(ValueError):
            validacao_publicacao.conferir_arquivo_exportado(f,'pdf')

    def test_roteiro_inexistente_erro_sem_traceback(self):
        p = manipulador_projetos.criar_projeto('Roteiro', tipo='roteiro')
        res = validacao_publicacao.validar_publicacao(p['slug'], formato='pdf', roteiro=999)
        self.assertFalse(res['aprovado'])
        self.assertIn(('documento_inacessivel','erro'), self.codigos(res))
