from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from modules import dicionario_online as dic


ROOT = Path(__file__).resolve().parents[1]


class DictionaryProviderTests(TestCase):
    def setUp(self):
        dic._cache.clear()

    def test_wiktionary_parser_extracts_english_definitions(self):
        dados = {
            "en": [
                {
                    "partOfSpeech": "Verb",
                    "definitions": [
                        {
                            "definition": "<span>To rise <b>above</b> a limit.</span>",
                            "examples": ["<i>They transcended expectations.</i>"],
                        }
                    ],
                }
            ]
        }
        defs = dic._parse_wiktionary_ingles(dados)
        self.assertEqual(defs[0]["texto"], "To rise above a limit.")
        self.assertEqual(defs[0]["classe"], "Verb")
        self.assertEqual(defs[0]["exemplo"], "They transcended expectations.")

    def test_english_lookup_falls_back_when_wiktionary_is_unreachable(self):
        free_data = [{
            "phonetic": "/test/",
            "meanings": [{
                "partOfSpeech": "verb",
                "definitions": [{"definition": "A fallback definition."}],
            }],
        }]

        def fake_get(url, **kwargs):
            if "wiktionary.org" in url:
                raise dic.ErroConsultaDicionario("offline")
            if "dictionaryapi.dev" in url:
                return free_data
            return {"responseData": {"translatedText": "teste"}}

        with patch.object(dic, "_get_json", side_effect=fake_get):
            resultado = dic.consultar_palavra_online("Transcending", "en_US")

        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["fonte_dicionario"], "Free Dictionary API")
        self.assertEqual(resultado["definicoes"][0]["texto"], "A fallback definition.")


    def test_wikcionario_portugues_parser_extracts_only_portuguese_definitions(self):
        dados = {
            "parse": {
                "text": """
                    <div class="mw-parser-output">
                      <h2 id="Português">Português</h2>
                      <h3>Substantivo</h3>
                      <p>coração, masculino</p>
                      <ol>
                        <li>órgão muscular que bombeia o sangue<ul><li>Exemplo brasileiro.</li></ul></li>
                        <li>o âmago, o centro</li>
                      </ol>
                      <h3>Tradução</h3>
                      <ol><li>heart</li></ol>
                      <h2 id="Francês">Francês</h2>
                      <h3>Substantivo</h3><ol><li>definição francesa</li></ol>
                    </div>
                """
            }
        }
        defs = dic._parse_wikcionario_portugues(dados)
        self.assertEqual([item["texto"] for item in defs], [
            "órgão muscular que bombeia o sangue",
            "o âmago, o centro",
        ])
        self.assertEqual(defs[0]["classe"], "Substantivo")
        self.assertEqual(defs[0]["exemplo"], "Exemplo brasileiro.")

    def test_portuguese_lookup_returns_first_valid_exact_provider(self):
        wikcionario = {
            "parse": {
                "text": "<h2 id='Português'>Português</h2><h3>Verbo</h3><ol><li>ir além de</li></ol>"
            }
        }
        aberto = [{
            "xml": "<entry><sense><gramGrp>v.</gramGrp><def>ser superior a</def></sense></entry>"
        }]

        def fake_get(url, **kwargs):
            if "pt.wiktionary.org" in url:
                return wikcionario
            if "dicionario-aberto.net" in url:
                return aberto
            return {"responseData": {"translatedText": "transcend"}}

        with patch.object(dic, "_get_json", side_effect=fake_get):
            resultado = dic.consultar_palavra_online("transcender", "pt_BR", "pt_BR", "en_US")

        self.assertTrue(resultado["ok"])
        self.assertIn(resultado["fonte_dicionario"], {"Wikcionário", "Dicionário Aberto"})
        self.assertIn(
            resultado["definicoes"][0]["texto"],
            {"ir além de", "ser superior a"},
        )

    def test_portuguese_lookup_survives_wikcionario_failure(self):
        aberto = [{
            "xml": "<entry><sense><gramGrp>s.</gramGrp><def>Uma definição de fallback.</def></sense></entry>"
        }]

        def fake_get(url, **kwargs):
            if "pt.wiktionary.org" in url:
                raise dic.ErroConsultaDicionario("offline")
            if "dicionario-aberto.net" in url:
                return aberto
            return {"responseData": {"translatedText": "fallback"}}

        with patch.object(dic, "_get_json", side_effect=fake_get):
            resultado = dic.consultar_palavra_online("teste", "pt_BR", "pt_BR", "en_US")

        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["fonte_dicionario"], "Dicionário Aberto")
        self.assertEqual(resultado["definicoes"][0]["texto"], "Uma definição de fallback.")

    def test_english_provider_query_is_lowercase(self):
        urls = []

        def fake_get(url, **kwargs):
            urls.append(url)
            if "wiktionary.org" in url:
                return {"en": [{"partOfSpeech": "Verb", "definitions": [{"definition": "Definition"}]}]}
            return {"responseData": {"translatedText": "tradução"}}

        with patch.object(dic, "_get_json", side_effect=fake_get):
            dic.consultar_palavra_online("Transcending", "en_US")

        self.assertTrue(any("/transcending" in url for url in urls))


    def test_datamuse_uses_provider_headword_for_inflected_english_word(self):
        dados = [{
            "word": "running",
            "defHeadword": "run",
            "tags": ["v"],
            "defs": ["v\tTo move swiftly on foot."],
        }]
        defs, verbete = dic._parse_datamuse_ingles(dados)
        self.assertEqual(verbete, "run")
        self.assertEqual(defs[0]["classe"], "verb")
        self.assertEqual(defs[0]["texto"], "To move swiftly on foot.")

    def test_english_lookup_uses_datamuse_native_inflection_headword(self):
        def fake_get(url, **kwargs):
            if "api.datamuse.com" in url:
                return [{
                    "word": "running",
                    "defHeadword": "run",
                    "tags": ["v"],
                    "defs": ["v\tTo move swiftly on foot."],
                }]
            if "wiktionary.org" in url or "dictionaryapi.dev" in url:
                return None
            return {"responseData": {"translatedText": "correndo"}}

        with patch.object(dic, "_get_json", side_effect=fake_get):
            resultado = dic.consultar_palavra_online("running", "en_US")

        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["verbete"], "run")
        self.assertIn("Datamuse", resultado["fonte_dicionario"])

    def test_portuguese_lookup_uses_wiktionary_native_search_for_inflection(self):
        pagina_efemero = {
            "parse": {
                "text": "<h2 id='Português'>Português</h2><h3>Adjetivo</h3><ol><li>que dura pouco tempo</li></ol>"
            }
        }

        def fake_get(url, **kwargs):
            params = kwargs.get("params") or {}
            if "pt.wiktionary.org" in url:
                if params.get("action") == "query":
                    return {"query": {"searchinfo": {}, "search": [{"title": "efêmero"}]}}
                if params.get("page") == "efêmero":
                    return pagina_efemero
                return {"parse": {"text": "<h2 id='Português'>Português</h2>"}}
            if "dicionario-aberto.net/word" in url:
                return []
            if "dicionario-aberto.net/near" in url:
                return ["efêmera"]
            return {"responseData": {"translatedText": "ephemeral"}}

        with patch.object(dic, "_get_json", side_effect=fake_get):
            resultado = dic.consultar_palavra_online("efêmeras", "pt_BR", "pt_BR", "en_US")

        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["verbete"], "efêmero")
        self.assertIn("busca aproximada", resultado["fonte_dicionario"])
        self.assertEqual(resultado["definicoes"][0]["texto"], "que dura pouco tempo")

    def test_portuguese_lookup_uses_dicionario_aberto_native_near_fallback(self):
        aberto = [{
            "xml": "<entry><sense><gramGrp>adj.</gramGrp><def>Que dura pouco.</def></sense></entry>"
        }]

        def fake_get(url, **kwargs):
            params = kwargs.get("params") or {}
            if "pt.wiktionary.org" in url:
                if params.get("action") == "query":
                    return {"query": {"searchinfo": {}, "search": []}}
                return {"parse": {"text": "<h2 id='Português'>Português</h2>"}}
            if "dicionario-aberto.net/near" in url:
                return ["efêmera"]
            if url.endswith("/word/ef%C3%AAmera"):
                return aberto
            if "dicionario-aberto.net/word" in url:
                return []
            return {"responseData": {"translatedText": "ephemeral"}}

        with patch.object(dic, "_get_json", side_effect=fake_get):
            resultado = dic.consultar_palavra_online("efêmeras", "pt_BR", "pt_BR", "en_US")

        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["verbete"], "efêmera")
        self.assertIn("palavra próxima", resultado["fonte_dicionario"])


class DictionaryReaderUiTests(TestCase):
    def test_alt_hover_highlight_and_browser_fallback_are_present(self):
        js = (ROOT / "static/js/leitor_dicionario.js").read_text(encoding="utf-8")
        self.assertIn("mousemove", js)
        self.assertIn("CSS?.highlights", js)
        self.assertIn("gutenberg-dictionary-hover-overlay", js)
        self.assertIn("consultarDiretoNoNavegador", js)
        self.assertIn("en.wiktionary.org/api/rest_v1/page/definition", js)
        self.assertIn("api.dictionaryapi.dev/api/v2/entries/en", js)
        self.assertIn("api.datamuse.com/words", js)
        self.assertIn("pt.wiktionary.org/w/api.php", js)
        self.assertIn("api.dicionario-aberto.net/word", js)
        self.assertIn("api.dicionario-aberto.net/near", js)
        self.assertIn("cacheLocal", js)
        self.assertIn("CACHE_LOCAL_MAX", js)

    def test_dictionary_header_has_explicit_dark_contrast(self):
        css = (ROOT / "static/css/leitor.css").read_text(encoding="utf-8")
        self.assertIn("background:#111827", css)
        self.assertIn("color:#f8fafc !important", css)

    def test_dictionary_modal_reopens_after_outside_close_and_cache_hit(self):
        js = (ROOT / "static/js/leitor_dicionario.js").read_text(encoding="utf-8")
        self.assertIn("function mostrarModal", js)
        self.assertIn("const modal = mostrarModal(palavraExibida)", js)
        self.assertIn("overlay?.addEventListener('pointerdown'", js)
        self.assertIn("limparDestaque();", js)
        self.assertIn("devolverFocoAoLeitor();", js)


class DictionaryTranslationDirectionTests(TestCase):
    def setUp(self):
        dic._cache.clear()

    def test_portuguese_can_translate_to_english(self):
        defs = [{"texto": "Conjunto de folhas encadernadas.", "classe": "substantivo"}]
        with patch.object(dic, "_consultar_portugues", return_value=(defs, "Dicionário Aberto", "livro")), \
             patch.object(dic, "_traduzir_palavra", return_value="book") as traduzir:
            resultado = dic.consultar_palavra_online("livro", "pt_BR", "pt_BR", "en_US")

        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["traducao"], "book")
        self.assertEqual(resultado["idioma_traducao_de"], "pt_BR")
        self.assertEqual(resultado["idioma_traducao_para"], "en_US")
        traduzir.assert_called_once_with("livro", "pt_BR", "en_US")

    def test_translation_only_runs_when_dictionary_language_matches_source(self):
        defs = [{"texto": "A written or printed work.", "classe": "noun"}]
        with patch.object(dic, "_consultar_ingles", return_value=(defs, "", "Wiktionary", "book")), \
             patch.object(dic, "_traduzir_palavra", return_value="should-not-be-used") as traduzir:
            resultado = dic.consultar_palavra_online("book", "en_US", "pt_BR", "en_US")

        self.assertTrue(resultado["ok"])
        self.assertEqual(resultado["traducao"], "")
        traduzir.assert_not_called()

    def test_cache_is_separated_by_translation_direction(self):
        defs = [{"texto": "A test definition."}]
        with patch.object(dic, "_consultar_ingles", return_value=(defs, "", "Wiktionary", "book")) as consultar, \
             patch.object(dic, "_traduzir_palavra", return_value="teste"):
            primeiro = dic.consultar_palavra_online("test", "en_US", "en_US", "pt_BR")
            segundo = dic.consultar_palavra_online("test", "en_US", "pt_BR", "en_US")

        self.assertEqual(primeiro["traducao"], "teste")
        self.assertEqual(segundo["traducao"], "")
        self.assertEqual(consultar.call_count, 2)

    def test_settings_and_reader_configs_expose_translation_pair(self):
        html = (ROOT / "templates/configuracoes.html").read_text(encoding="utf-8")
        leitor = (ROOT / "templates/leitor.html").read_text(encoding="utf-8")
        leitor_alt = (ROOT / "templates/leitor_alt.html").read_text(encoding="utf-8")
        js = (ROOT / "static/js/leitor_dicionario.js").read_text(encoding="utf-8")
        self.assertIn('name="idioma_traducao_de"', html)
        self.assertIn('name="idioma_traducao_para"', html)
        self.assertIn('translationFrom:', leitor)
        self.assertIn('translationTo:', leitor)
        self.assertIn('translationFrom:', leitor_alt)
        self.assertIn('translationTo:', leitor_alt)
        self.assertIn('langpair:', js)
        self.assertIn("dados.traducao", js)
