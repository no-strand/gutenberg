from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

FONTS = [
    "Atkinson Hyperlegible", "Inter", "Source Sans 3", "Noto Sans",
    "IBM Plex Sans", "Arial", "Roboto", "Literata", "Source Serif 4",
    "Noto Serif", "Georgia", "Times New Roman", "IBM Plex Mono",
    "JetBrains Mono", "Source Code Pro", "Consolas", "Courier New",
]


class ReaderFinalPolishTests(unittest.TestCase):
    def test_width_slider_tracks_effective_limit(self):
        for name in ("leitor.js", "leitor_alt.js"):
            text = (ROOT / "static" / "js" / name).read_text(encoding="utf-8")
            self.assertIn("const LARGURA_MAX_PX = 1180;", text)
            self.assertIn("function calcularMaximoPercentualLargura()", text)
            self.assertIn("Math.ceil((LARGURA_MAX_PX / viewport) * 100)", text)
            self.assertIn("controleLargura.max = String(maximo);", text)
            self.assertIn("atualizarLimitesControleLargura();", text)
        # 1920px is the concrete case reported by the user: ceil(1180/1920*100) == 62.
        self.assertEqual(62, -(-1180 * 100 // 1920))

    def test_all_requested_fonts_are_available_in_both_readers(self):
        for template in ("leitor.html", "leitor_alt.html"):
            text = (ROOT / "templates" / template).read_text(encoding="utf-8")
            for font in FONTS:
                self.assertIn(f">{font}<", text, f"{font} missing from {template}")
        for script in ("leitor.js", "leitor_alt.js"):
            text = (ROOT / "static" / "js" / script).read_text(encoding="utf-8")
            for font in FONTS:
                self.assertIn(font, text, f"{font} missing from {script}")
            self.assertIn("'fonte-serif': 'literata'", text)
            self.assertIn("'fonte-sans': 'inter'", text)
            self.assertIn("'fonte-mono': 'ibm-plex-mono'", text)

    def test_tts_model_folder_is_clickable_and_uses_fixed_backend_path(self):
        template = (ROOT / "templates" / "configuracoes.html").read_text(encoding="utf-8")
        js = (ROOT / "static" / "js" / "configuracoes.js").read_text(encoding="utf-8")
        backend = (ROOT / "modules" / "servidor_flask.py").read_text(encoding="utf-8")
        self.assertIn('class="tts-modelos-pasta-link" id="ttsModelosPasta"', template)
        self.assertIn("/api/tts/modelos/abrir-pasta", js)
        self.assertIn('@app.post("/api/tts/modelos/abrir-pasta")', backend)
        self.assertIn("PASTA_MODELOS_TTS.mkdir(parents=True, exist_ok=True)", backend)
        self.assertIn("os.startfile(caminho)", backend)
        # The route must not accept a path supplied by the browser.
        route = backend.split('@app.post("/api/tts/modelos/abrir-pasta")', 1)[1].split('@app.post("/api/tts/modelos/baixar")', 1)[0]
        self.assertNotIn("request.get_json", route)
        self.assertNotIn("request.form", route)

    def test_user_documentation_no_longer_describes_old_reader_controls(self):
        docs = (ROOT / "documentation" / "script.js").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        old = [
            "Troca entre serifada, sem serifa e monoespaçada",
            "Switches between serif, sans, and monospaced fonts",
            "Ajusta a largura da área principal entre 30% e 90%",
            "Adjusts the main reading area from 30% to 90%",
            "três grupos principais",
            "three main groups",
        ]
        for phrase in old:
            self.assertNotIn(phrase, docs)
        self.assertIn("Atkinson Hyperlegible", docs)
        self.assertIn("1180 px", docs)
        self.assertIn("clicável e abre essa pasta diretamente no Explorer", docs)
        self.assertIn("clickable and opens that folder directly in Explorer", docs)
        self.assertIn("17 fontes específicas", readme)
        self.assertIn("17 specific fonts", readme)


if __name__ == "__main__":
    unittest.main()
