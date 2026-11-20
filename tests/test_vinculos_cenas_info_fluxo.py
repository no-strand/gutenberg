"""Regressões de vínculos de cenas com páginas de Informações e nós do Fluxograma."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from modules import exportador_gut, exportador_recursos_pdf
from modules.manipulador_recursos_projeto import (
    salvar_informacoes_projeto, salvar_fluxo_projeto, modificar_planejamento_projeto,
    ler_recursos_projeto, mesclar_recursos_importados,
)


class VinculosCenasInfoFluxoTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta = Path(self.temp.name) / 'origem'
        self.pasta.mkdir()
        salvar_informacoes_projeto(self.pasta, [{
            'id': 'info_biblioteca', 'titulo': 'Linha do tempo', 'html': '<p>Testes</p>'
        }])
        salvar_fluxo_projeto(self.pasta, {'fluxos': [
            {'id': 'fluxo_historia', 'titulo': 'Ato I', 'nodes': [
                {'id': 'no_encontro', 'titulo': 'Encontro', 'x': 120, 'y': 120},
                {'id': 'no_climax', 'titulo': 'Clímax', 'x': 400, 'y': 240},
            ], 'edges': []},
        ]})

    def _criar_cena(self):
        return modificar_planejamento_projeto(self.pasta, 'cenas', 'salvar', {
            'titulo': 'O primeiro ato',
            'paginas_info': ['info_biblioteca'], 'nos_fluxo': ['no_encontro', 'no_climax'],
        })['planejamento']['cenas'][0]

    def test_vinculos_persistem_e_edicao_mantem_ids(self):
        cena = self._criar_cena()
        self.assertEqual(cena['paginas_info'], ['info_biblioteca'])
        self.assertEqual(cena['nos_fluxo'], ['no_encontro', 'no_climax'])
        self.assertEqual(ler_recursos_projeto(self.pasta)['planejamento']['cenas'][0]['nos_fluxo'], ['no_encontro', 'no_climax'])
        alterada = modificar_planejamento_projeto(self.pasta, 'cenas', 'salvar', {**cena, 'resumo': 'Alterada'})
        self.assertEqual(alterada['planejamento']['cenas'][0]['paginas_info'], ['info_biblioteca'])
        self.assertEqual(alterada['planejamento']['cenas'][0]['nos_fluxo'], ['no_encontro', 'no_climax'])

    def test_gutr_importacao_remapeia_novos_vinculos_e_pdf_nomeia(self):
        self._criar_cena()
        destino = Path(self.temp.name) / 'exportacoes'
        destino.mkdir()
        metadata = {'titulo': 'Teste', 'slug': 'teste', 'tipo': 'livro', 'autor': 'Autor'}
        with patch.object(exportador_gut, 'obter_projeto', return_value=metadata), \
             patch.object(exportador_gut, 'obter_pasta_projeto', return_value=self.pasta), \
             patch.object(exportador_gut, 'obter_pasta_exportacao_projeto', return_value=destino):
            arquivo = exportador_gut.exportar_gutr_recursos('teste')
            importado = exportador_gut.ler_payload_gutr(arquivo)['conteudo']['recursos']
        pasta_nova = Path(self.temp.name) / 'destino'
        pasta_nova.mkdir()
        resultado = mesclar_recursos_importados(pasta_nova, importado)
        cena = resultado['planejamento']['cenas'][0]
        # A importação reaproveita as abas padrão vazias do projeto novo em vez
        # de criar abas extras sem necessidade.
        id_info = next(p['id'] for aba in resultado['informacoes_abas'] for p in aba['paginas'] if p['titulo'] == 'Linha do tempo')
        ids_nos = [no['id'] for fluxo in resultado['fluxos'] for no in fluxo['nodes'] if no['titulo'] in {'Encontro', 'Clímax'}]
        self.assertEqual(cena['paginas_info'], [id_info])
        self.assertEqual(cena['nos_fluxo'], ids_nos)
        self.assertNotEqual(id_info, 'info_biblioteca')
        self.assertNotEqual(ids_nos[0], 'no_encontro')
        with patch.object(exportador_recursos_pdf, 'obter_projeto', return_value=metadata), \
             patch.object(exportador_recursos_pdf, 'obter_pasta_projeto', return_value=self.pasta), \
             patch.object(exportador_recursos_pdf, 'obter_pasta_exportacao_projeto', return_value=destino):
            arquivo_pdf = exportador_recursos_pdf.exportar_recursos_pdf('teste')
        import fitz
        with fitz.open(arquivo_pdf) as doc:
            texto = '\n'.join(page.get_text() for page in doc)
        self.assertIn('Linha do tempo', texto)
        self.assertIn('Ato I', texto)
        self.assertIn('Encontro', texto)

    def test_compatibilidade_cena_versao_antiga(self):
        cena = modificar_planejamento_projeto(self.pasta, 'cenas', 'salvar', {'titulo': 'Cena legada'})['planejamento']['cenas'][0]
        self.assertEqual(cena['paginas_info'], [])
        self.assertEqual(cena['nos_fluxo'], [])
