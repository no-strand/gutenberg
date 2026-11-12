"""Protege os requisitos da correção de fontes EPUB."""
import unittest
from pathlib import Path
from bs4 import BeautifulSoup
R=Path(__file__).resolve().parents[1]
class CorrecaoFontesEPUB(unittest.TestCase):
  def test_default_arial_ativo(self):
    html=BeautifulSoup((R/'templates/editor.html').read_text(encoding='utf8'), 'html.parser')
    select=html.select_one('#seletorFonteEditor')
    self.assertEqual(select.select_one('option[selected]')['value'], 'fonte-arial')
    self.assertNotIn('Padrão (sem fonte específica)',str(select))
    css=(R/'static/css/atelier-ui.css').read_text(encoding='utf8')
    trecho=css.split('.pagina-editor-app .painel-word #editorTexto {',1)[1].split('}',1)[0]
    self.assertIn('font-family:Arial,Helvetica,sans-serif!important;',trecho)
  def test_range_sem_marcadores(self):
    js=(R/'static/js/editor.js').read_text(encoding='utf8')
    metodo=js.split('function aplicarFonteEmSelecao(',1)[1].split('function aplicarFonte(',1)[0]
    self.assertIn('parte.extractContents()',metodo)
    self.assertNotIn('withSelectionMarkers(',metodo)
    self.assertIn('restoreLogicalSelection(selection)',metodo)
  def test_escolha_persistente(self):
    js=(R/'static/js/editor.js').read_text(encoding='utf8')
    self.assertIn('STORAGE_FONTE_EDITOR',js)
    self.assertIn('fonteDefinidaPeloUsuario ? fontePreferidaEditor',js)
