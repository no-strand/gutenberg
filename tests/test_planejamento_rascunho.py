"""Regressões da expansão 2: cenas, pesquisa e importação sem perda de dados."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modules.manipulador_recursos_projeto import (
    ler_recursos_projeto, modificar_planejamento_projeto,
    salvar_item_catalogo_projeto, mesclar_recursos_importados,
    salvar_informacoes_projeto, normalizar_recursos,
)
from modules.planejamento_rascunho import normalizar_planejamento, alterar_planejamento


class PlanejamentoRascunhoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta = Path(self.temp.name)

    def test_compatibilidade_com_projetos_sem_planejamento(self):
        atual = ler_recursos_projeto(self.pasta)
        self.assertEqual(atual['planejamento'], {'cenas': [], 'fontes': []})
        self.assertEqual(atual['versao'], 4)
        self.assertEqual(normalizar_recursos({'versao': 3})['planejamento'], {'cenas': [], 'fontes': []})

    def test_salvar_editar_reordenar_excluir_com_vinculos(self):
        salvar_informacoes_projeto(self.pasta, [{'id':'i','titulo':'Ideias', 'html':'<p>Não perder</p>'}])
        personagem = salvar_item_catalogo_projeto(self.pasta, 'personagens', {'nome':'ANA'})['personagens'][0]
        fonte = modificar_planejamento_projeto(self.pasta, 'fontes', 'salvar', {
            'titulo':'Entrevista', 'tipo':'entrevista','url':'https://example.org/fonte',
            'notas':'Verificar capítulos', 'verificada':False,
        })['planejamento']['fontes'][0]
        cena = modificar_planejamento_projeto(self.pasta, 'cenas', 'salvar', {
            'titulo':'Primeiro encontro','resumo':'Um segredo','status':'em_andamento',
            'personagens':[personagem['id']], 'referencias':[fonte['id']],
        })['planejamento']['cenas'][0]
        self.assertEqual(cena['personagens'], [personagem['id']])
        self.assertEqual(cena['referencias'], [fonte['id']])
        self.assertEqual(cena['status'], 'em_andamento')
        self.assertEqual(ler_recursos_projeto(self.pasta)['informacoes'][0]['titulo'], 'Ideias')
        segunda = modificar_planejamento_projeto(self.pasta, 'cenas', 'salvar', {'titulo':'Depois'})['planejamento']['cenas'][1]
        reorder = modificar_planejamento_projeto(self.pasta, 'cenas', 'ordenar', {'ordem':[segunda['id'],cena['id']]})
        self.assertEqual([item['id'] for item in reorder['planejamento']['cenas']], [segunda['id'], cena['id']])
        updated = modificar_planejamento_projeto(self.pasta, 'cenas', 'salvar', {**cena,'resumo':'Mudou'})
        self.assertEqual(updated['planejamento']['cenas'][1]['resumo'], 'Mudou')
        self.assertEqual(updated['planejamento']['cenas'][1]['data_criacao'], cena['data_criacao'])
        updated = modificar_planejamento_projeto(self.pasta, 'fontes', 'excluir', {'id':fonte['id']})
        self.assertEqual(updated['planejamento']['fontes'], [])
        self.assertEqual(updated['planejamento']['cenas'][1]['referencias'], [])
        self.assertEqual(len(updated['planejamento']['cenas']), 2)

    def test_rejeita_url_danosa_reordenacao_invalida_e_ids_desconhecidos(self):
        for url in ['javascript:alert(1)', 'data:text/html,x', 'https://usuario:senha@example.org']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                modificar_planejamento_projeto(self.pasta,'fontes','salvar',{'titulo':'Fonte','url':url})
        with self.assertRaises(ValueError):
            modificar_planejamento_projeto(self.pasta, 'cenas', 'salvar', {'titulo':'Cena','id':'../../outro'})
        with self.assertRaises(ValueError):
            modificar_planejamento_projeto(self.pasta, 'cenas', 'salvar', {'titulo':'Cena','id':'cena_inexistente'})
        with self.assertRaises(ValueError):
            modificar_planejamento_projeto(self.pasta, 'cenas', 'ordenar', {'ordem':['a']})
        with self.assertRaises(ValueError):
            modificar_planejamento_projeto(self.pasta, 'fontes', 'excluir', {'id':'inexistente'})

    def test_importacao_mescla_e_remapeia_vinculos_sem_duplicar_ids(self):
        atual = modificar_planejamento_projeto(self.pasta, 'cenas', 'salvar', {'titulo':'Original'})
        antigo = atual['planejamento']['cenas'][0]
        importados = {
            'personagens':[{'id':'p_importado','nome':'Luiza'}],
            'lugares':[{'id':'l_importado','nome':'Praça'}],
            'anotacoes':[{'id':'n_importado','nome':'Segredo'}],
            'planejamento': {
                'fontes':[{'id':'f_importada','titulo':'Livro X','tipo':'livro'}],
                'cenas':[{'id':'c_importada','titulo':'Novas pistas',
                           'personagens':['p_importado'],'lugares':['l_importado'],
                           'anotacoes':['n_importado'],'referencias':['f_importada']}],
            },
        }
        merge = mesclar_recursos_importados(self.pasta, importados)
        self.assertEqual(len(merge['planejamento']['cenas']), 2)
        cena = merge['planejamento']['cenas'][1]
        self.assertNotEqual(cena['id'], 'c_importada')
        self.assertEqual(merge['planejamento']['cenas'][0]['id'], antigo['id'])
        for tipo in ['personagens','lugares','anotacoes']:
            self.assertEqual(cena[tipo], [merge[tipo][0]['id']])
        self.assertEqual(cena['referencias'], [merge['planejamento']['fontes'][0]['id']])

    def test_backup_gutr_roundtrip_e_pdf_recursos(self):
        from unittest.mock import patch
        from modules import exportador_gut, exportador_recursos_pdf
        import fitz

        ref = modificar_planejamento_projeto(self.pasta, 'fontes', 'salvar', {
            'titulo':'Acervo Municipal', 'url':'https://example.org/acervo',
        })['planejamento']['fontes'][0]
        modificar_planejamento_projeto(self.pasta, 'cenas', 'salvar', {
            'titulo':'Segredo do Portão', 'resumo':'Um documento perdido', 'referencias':[ref['id']],
        })
        destino = self.pasta / 'saidas'
        destino.mkdir()
        metadata = {'titulo':'Mundo de teste', 'slug':'mundo', 'tipo':'livro', 'autor':'Autor de teste'}
        with patch.object(exportador_gut, 'obter_projeto', return_value=metadata), \
             patch.object(exportador_gut, 'obter_pasta_projeto', return_value=self.pasta), \
             patch.object(exportador_gut, 'obter_pasta_exportacao_projeto', return_value=destino):
            arquivo = exportador_gut.exportar_gutr_recursos('mundo')
            payload = exportador_gut.ler_payload_gutr(arquivo)
        data = payload['conteudo']['recursos']
        self.assertEqual(data['planejamento']['cenas'][0]['titulo'], 'Segredo do Portão')
        self.assertEqual(data['planejamento']['fontes'][0]['titulo'], 'Acervo Municipal')
        self.assertEqual(payload['conteudo']['quantidades']['cenas'], 1)
        self.assertEqual(payload['conteudo']['quantidades']['fontes'], 1)
        outra_pasta = self.pasta / 'importado'
        outra_pasta.mkdir()
        imported = mesclar_recursos_importados(outra_pasta, data)
        self.assertEqual(imported['planejamento']['cenas'][0]['referencias'], [imported['planejamento']['fontes'][0]['id']])
        with patch.object(exportador_recursos_pdf, 'obter_projeto', return_value=metadata), \
             patch.object(exportador_recursos_pdf, 'obter_pasta_projeto', return_value=self.pasta), \
             patch.object(exportador_recursos_pdf, 'obter_pasta_exportacao_projeto', return_value=destino):
            caminho_pdf = exportador_recursos_pdf.exportar_recursos_pdf('mundo')
        with fitz.open(caminho_pdf) as doc:
            conteudo = '\n'.join(p.get_text() for p in doc)
        for label in ('Segredo do Portão', 'Acervo Municipal', 'https://example.org/acervo'):
            self.assertIn(label, conteudo)

    def test_limites_e_sanitizacao_de_ids_duplicados(self):
        data = normalizar_planejamento({
            'fontes':[{'id':'x','titulo':'A'}, {'id':'x','titulo':'B'}],
            'cenas':[{'id':'c','titulo':'Cena','referencias':['x','inexistente','x'], 'personagens':['p','p']}],
        })
        self.assertEqual(len(data['fontes']), 1)
        self.assertEqual(data['cenas'][0]['referencias'], ['x'])
        self.assertEqual(data['cenas'][0]['personagens'], ['p'])
        self.assertEqual(normalizar_planejamento({'cenas': [{'titulo':'x'}]*400})['cenas'].__len__(), 300)
        self.assertEqual(len(alterar_planejamento({'planejamento': data}, 'cenas', 'excluir', {'id':'c'})['planejamento']['cenas']),0)


if __name__ == '__main__': unittest.main()
