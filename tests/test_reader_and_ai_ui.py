from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReaderAndAiUiTests(unittest.TestCase):
    """Testes estáticos para recursos de IA e configurações dos leitores."""

    def test_botao_ia_recursos_usa_icone_svg_real(self):
        html = (ROOT / "templates" / "recursos_projeto.html").read_text(encoding="utf-8")
        self.assertIn("id=\"btnAbrirIARecursos\"", html)
        self.assertIn("icon_svg('ai')", html)
        self.assertNotIn('id="btnAbrirIARecursos" class="botao-primario botao-com-icone recursos-ai-btn" title="{{ t(\'resources.ai_generate\') }}" aria-label="{{ t(\'resources.ai_generate\') }}"><span>✨</span>', html)

        server = (ROOT / "modules" / "servidor_flask.py").read_text(encoding="utf-8")
        self.assertRegex(server, r'"ai":\s*\'<svg[^>]*>')
        self.assertIn('"ai":', server)

    def test_botoes_ia_dos_editores_usam_mesmo_icone_svg(self):
        for nome in ("editor.html", "editor_roteiro.html"):
            html = (ROOT / "templates" / nome).read_text(encoding="utf-8")
            self.assertIn('id="btnAbrirIAEditor"', html, nome)
            self.assertIn("icon_svg('ai')", html, nome)
            self.assertNotIn('>✨</button>', html, nome)

    def test_botoes_ia_tem_atalho_ctrl_alt_g(self):
        for nome in ("editor.html", "editor_roteiro.html"):
            html = (ROOT / "templates" / nome).read_text(encoding="utf-8")
            self.assertIn('id="btnAbrirIAEditor"', html, nome)
            self.assertIn("Ctrl+Alt+G", html, nome)

        recursos_html = (ROOT / "templates" / "recursos_projeto.html").read_text(encoding="utf-8")
        self.assertIn('id="btnAbrirIARecursos"', recursos_html)
        self.assertIn("Ctrl+Alt+G", recursos_html)

        ia_editor = (ROOT / "static" / "js" / "ia_editor.js").read_text(encoding="utf-8")
        ia_recursos = (ROOT / "static" / "js" / "ia_recursos.js").read_text(encoding="utf-8")
        for js in (ia_editor, ia_recursos):
            self.assertIn("ctrlKey", js)
            self.assertIn("altKey", js)
            self.assertIn("key === 'g'", js)
            self.assertIn("abrir.click()", js)

    def test_modal_ia_recursos_nao_cria_overflow_horizontal(self):
        css = (ROOT / "static" / "css" / "recursos_projeto.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"\.modal-ia-recursos\{[^}]*box-sizing:border-box")
        self.assertRegex(css, r"\.modal-ia-recursos\{[^}]*overflow-y:auto[^}]*overflow-x:hidden")
        self.assertIn("overflow-wrap:anywhere", css)
        self.assertIn("word-break:break-word", css)
        self.assertIn("flex-wrap:wrap", css)

    def test_idioma_tts_existe_nas_configuracoes_dos_dois_leitores(self):
        for nome in ("leitor.html", "leitor_alt.html"):
            html = (ROOT / "templates" / nome).read_text(encoding="utf-8")
            self.assertIn('id="controleIdiomaTts"', html, nome)
            self.assertIn("reader.tts_language", html, nome)
            self.assertIn('value="pt_BR"', html, nome)
            self.assertIn('value="en_US"', html, nome)

    def test_idioma_tts_e_persistido_e_aplicado_nos_dois_leitores(self):
        for nome in ("leitor.js", "leitor_alt.js"):
            js = (ROOT / "static" / "js" / nome).read_text(encoding="utf-8")
            self.assertIn("controleIdiomaTts", js, nome)
            self.assertIn("ttsLanguage:", js, nome)
            self.assertIn("window.LEITOR_CONFIG.ttsLanguage", js, nome)
            self.assertIn("controleIdiomaTts", js, nome)

        server = (ROOT / "modules" / "servidor_flask.py").read_text(encoding="utf-8")
        trecho = server[server.index('@app.post("/api/configuracoes/leitor")'):server.index('@app.post("/projetos/<slug>/atualizar")')]
        self.assertIn('"idioma_tts":', trecho)
        self.assertIn('"en_US"', trecho)
        self.assertIn('"pt_BR"', trecho)

    def test_locales_tem_rotulos_do_idioma_tts(self):
        for nome in ("pt_BR.json", "en_US.json"):
            data = json.loads((ROOT / "locales" / nome).read_text(encoding="utf-8"))
            self.assertIn("reader.tts_language", data)
            self.assertIn("reader.tts_portuguese", data)
            self.assertIn("reader.tts_english", data)

    def test_tts_le_editor_usa_idioma_atualizado_em_runtime(self):
        js = (ROOT / "static" / "js" / "leitor_tts.js").read_text(encoding="utf-8")
        self.assertIn("cfg.ttsLanguage", js)
        self.assertIn("language: cfg.ttsLanguage || 'pt_BR'", js)

    def test_tts_verifica_modelos_antes_de_reproduzir(self):
        js = (ROOT / "static" / "js" / "leitor_tts.js").read_text(encoding="utf-8")
        self.assertIn("async function verificarModelosTtsAntesDeReproduzir()", js)
        self.assertIn("fetch('/api/tts/modelos/status'", js)
        self.assertIn("dados?.estado?.instalado", js)
        self.assertIn("reader.tts_models_missing", js)
        self.assertIn("window.location.href = '/configuracoes'", js)
        self.assertIn("if (!(await verificarModelosTtsAntesDeReproduzir())) return;", js)

        for nome in ("pt_BR.json", "en_US.json"):
            data = json.loads((ROOT / "locales" / nome).read_text(encoding="utf-8"))
            self.assertIn("reader.tts_models_missing", data)
            self.assertIn("reader.tts_models_status_error", data)


class LastAreaPersistenceTests(unittest.TestCase):
    def test_paginas_registram_area_editor_ou_biblioteca(self):
        html = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn("registrarUltimaAreaApp", html)
        self.assertIn("caminho.startsWith('/biblioteca/')", html)
        self.assertIn("caminho.startsWith('/projetos/')", html)
        self.assertIn("fetch('/api/app/ultima-area'", html)
        self.assertIn("keepalive: true", html)

    def test_desktop_abre_na_ultima_area_salva(self):
        app_py = (ROOT / "app.py").read_text(encoding="utf-8")
        util_py = (ROOT / "modules" / "utilidades.py").read_text(encoding="utf-8")
        self.assertIn('ULTIMA_AREA_APP_CHAVE = "ultima_area_app"', app_py)
        self.assertIn("def _obter_url_inicial_por_area", app_py)
        self.assertIn('return f"{base}/biblioteca" if area == "biblioteca" else base', app_py)
        self.assertIn("url_inicial = self.server_url if self.initial_path else _obter_url_inicial_por_area(self.server_url)", app_py)
        self.assertIn('"ultima_area_app": "editor"', util_py)


class ReaderTtsEnhancementsTests(unittest.TestCase):
    def test_controle_velocidade_tts_existe_nos_dois_leitores(self):
        for nome in ('leitor.html', 'leitor_alt.html'):
            html = (ROOT / 'templates' / nome).read_text(encoding='utf-8')
            self.assertIn('id="controleVelocidadeTts"', html, nome)
            self.assertIn('min="0.75"', html, nome)
            self.assertIn('max="1.25"', html, nome)
            self.assertIn('valorVelocidadeTts', html, nome)

    def test_velocidade_tts_e_persistida_nos_dois_leitores(self):
        for nome in ('leitor.js', 'leitor_alt.js'):
            js = (ROOT / 'static' / 'js' / nome).read_text(encoding='utf-8')
            self.assertIn('controleVelocidadeTts', js, nome)
            self.assertIn('ttsSpeed:', js, nome)
            self.assertIn('normalizarVelocidadeTts', js, nome)
        server = (ROOT / 'modules' / 'servidor_flask.py').read_text(encoding='utf-8')
        self.assertIn('leitor_tts_velocidade', server)
        self.assertIn('dados.get("ttsSpeed")', server)

    def test_tts_envia_velocidade_para_o_servidor(self):
        js = (ROOT / 'static' / 'js' / 'leitor_tts.js').read_text(encoding='utf-8')
        self.assertIn('speed: Number(cfg.ttsSpeed || 1)', js)

    def test_configuracoes_oferecem_vozes_ptbr_e_ingles(self):
        html = (ROOT / 'templates' / 'configuracoes.html').read_text(encoding='utf-8')
        self.assertIn('id="cfgVozTtsPtBr"', html)
        self.assertIn('id="cfgVozTtsEn"', html)
        for voz in ('pf_dora', 'pm_alex', 'pm_santa', 'af_heart', 'af_bella', 'af_nicole', 'am_michael', 'bf_emma', 'bm_george'):
            self.assertIn(f'value="{voz}"', html)

    def test_vozes_tts_sao_persistidas_e_usadas_na_sintese(self):
        util_py = (ROOT / 'modules' / 'utilidades.py').read_text(encoding='utf-8')
        server = (ROOT / 'modules' / 'servidor_flask.py').read_text(encoding='utf-8')
        tts = (ROOT / 'modules' / 'tts_kokoro.py').read_text(encoding='utf-8')
        self.assertIn('"voz_tts_pt_BR": "pf_dora"', util_py)
        self.assertIn('"voz_tts_en_US": "af_heart"', util_py)
        self.assertIn('normalizar_voz_tts(request.form.get("voz_tts_pt_BR"', server)
        self.assertIn('normalizar_voz_tts(request.form.get("voz_tts_en_US"', server)
        self.assertIn('sintetizar_wav(texto, idioma, fallback, velocidade, voz=voz)', server)
        self.assertIn('EN_GB_VOICES = {"bf_emma", "bm_george"}', tts)
        self.assertIn('return "en-gb" if voz_normalizada in EN_GB_VOICES else "en-us"', tts)
        self.assertIn('af_bella', tts)
        self.assertIn('af_nicole', tts)

    def test_rotulos_de_voz_nao_usam_voz_atual_e_marcam_recomendadas(self):
        pt = (ROOT / 'locales' / 'pt_BR.json').read_text(encoding='utf-8')
        en = (ROOT / 'locales' / 'en_US.json').read_text(encoding='utf-8')
        self.assertNotIn('(voz atual)', pt)
        self.assertNotIn('(current voice)', en)
        self.assertIn('Dora — Feminina (recomendada)', pt)
        self.assertIn('Alex — Masculina (recomendada)', pt)
        self.assertIn('Heart — Feminina (EUA, recomendada)', pt)
        self.assertIn('Michael — Masculina (EUA, recomendada)', pt)
        self.assertIn('Bella — Feminina (EUA)', pt)
        self.assertIn('Nicole — Feminina (EUA)', pt)

    def test_cache_tts_inclui_voz_para_nao_reutilizar_audio_de_outra_voz(self):
        py = (ROOT / 'modules' / 'tts_kokoro.py').read_text(encoding='utf-8')
        self.assertIn('voz_normalizada = normalizar_voz_tts(voz, idioma_base)', py)
        self.assertIn('{voz_normalizada}', py)
        self.assertIn('{velocidade:.2f}', py)

    def test_tts_nova_sessao_comeca_no_primeiro_paragrafo_visivel(self):
        js = (ROOT / 'static' / 'js' / 'leitor_tts.js').read_text(encoding='utf-8')
        self.assertIn('function calcularIndiceInicialVisivel()', js)
        self.assertIn("trecho.closest?.('p, li, blockquote, dd, dt')", js)
        self.assertIn("origem: 'primeiro_paragrafo_visivel'", js)
        self.assertIn('indice = calcularIndiceInicialVisivel();', js)

    def test_tts_considera_barra_sticky_ao_calcular_inicio_visivel(self):
        js = (ROOT / 'static' / 'js' / 'leitor_tts.js').read_text(encoding='utf-8')
        self.assertIn('function limiteSuperiorConteudoVisivel()', js)
        self.assertIn("['sticky', 'fixed'].includes", js)
        self.assertIn('rectFrame.top + rect.top', js)

    def test_tts_pausado_pode_reiniciar_em_paragrafo_acima_do_inicio_da_sessao(self):
        js = (ROOT / 'static' / 'js' / 'leitor_tts.js').read_text(encoding='utf-8')
        self.assertIn('let indiceInicioSessao = 0;', js)
        self.assertIn('let scrollYAoPausar = null;', js)
        self.assertIn('function registrarPausaParaRetomada()', js)
        self.assertIn('function calcularIndiceReinicioAposPausa()', js)
        self.assertIn('indiceVisivel >= indiceInicioSessao', js)
        self.assertIn("enviarLogTts('tts_reinicio_acima_apos_pausa'", js)
        self.assertIn('indiceInicioSessao = indiceReinicio;', js)

    def test_kokoro_inclui_velocidade_na_chave_de_cache_e_na_sintese(self):
        py = (ROOT / 'modules' / 'tts_kokoro.py').read_text(encoding='utf-8')
        self.assertIn('_normalizar_velocidade', py)
        self.assertIn('_chave_cache(texto, idioma_base, fallback, velocidade, voz)', py)
        self.assertIn('speed=velocidade', py)

    def test_segmentos_tts_usam_limite_de_palavras_e_pontuacao(self):
        js = (ROOT / 'static' / 'js' / 'leitor_tts.js').read_text(encoding='utf-8')
        self.assertIn('function dividirTexto(texto, maxPalavras = 30)', js)
        self.assertIn('[.,;:!?…]', js)
        self.assertIn('qtd >= maxPalavras', js)

    def test_pausas_tts_foram_aumentadas_sutilmente(self):
        js = (ROOT / 'static' / 'js' / 'leitor_tts.js').read_text(encoding='utf-8')
        self.assertIn('return 0.75;', js)
        self.assertIn('return 0.42;', js)
        self.assertIn('return 0.52;', js)
        self.assertIn('if (!match) return 0.25;', js)

    def test_primeiro_audio_tts_mostra_spinner_no_botao(self):
        js = (ROOT / 'static' / 'js' / 'leitor_tts.js').read_text(encoding='utf-8')
        css = (ROOT / 'static' / 'css' / 'leitor.css').read_text(encoding='utf-8')
        self.assertIn('let carregandoPrimeiroAudio = false;', js)
        self.assertIn("botao.dataset.estado = 'loading'", js)
        self.assertIn('tts-loading-spinner', js)
        self.assertIn("carregandoPrimeiroAudio = true;", js)
        self.assertIn('.tts-loading-spinner', css)
        self.assertIn('@keyframes tts-loading-spin', css)

    def test_seletor_de_idioma_tem_largura_minima(self):
        css = (ROOT / 'static' / 'css' / 'leitor.css').read_text(encoding='utf-8')
        self.assertIn('.reader-tts-language-select{width:320px;min-width:320px;max-width:100%;}', css)
        self.assertIn('width:min(440px,calc(100vw - 28px))', css)


class Release104Tests(unittest.TestCase):
    def test_versao_do_aplicativo_e_104(self):
        py = (ROOT / 'modules' / 'utilidades.py').read_text(encoding='utf-8')
        self.assertIn('APP_VERSAO = "1.0.4"', py)

    def test_seletor_idioma_tts_tem_espaco_ampliado(self):
        css = (ROOT / 'static' / 'css' / 'leitor.css').read_text(encoding='utf-8')
        self.assertIn('.reader-tts-language-select{width:320px;min-width:320px;max-width:100%;}', css)
        self.assertIn('width:min(440px,calc(100vw - 28px))', css)

    def test_cache_tts_inclui_velocidade_normalizada(self):
        py = (ROOT / 'modules' / 'tts_kokoro.py').read_text(encoding='utf-8')
        self.assertIn('def _normalizar_velocidade(', py)
        self.assertIn('velocidade:.2f', py)
        self.assertIn('_chave_cache(texto, idioma_base, fallback, velocidade, voz)', py)


class UnifiedReaderAndPackagingTests(unittest.TestCase):
    def test_leitor_editor_usa_iframe_e_mantem_botao_editar(self):
        html = (ROOT / "templates" / "leitor.html").read_text(encoding="utf-8")
        self.assertIn('id="epubFrame"', html)
        self.assertIn('class="area-leitura area-leitura-epub', html)
        self.assertIn("url_for('editar_capitulo'", html)
        self.assertIn('conteudo_url', html)

    def test_scripts_dos_dois_leitores_usam_mesma_logica_de_iframe(self):
        leitor = (ROOT / "static" / "js" / "leitor.js").read_text(encoding="utf-8")
        alt = (ROOT / "static" / "js" / "leitor_alt.js").read_text(encoding="utf-8")
        self.assertEqual(leitor, alt)
        self.assertIn("cfg.base === 'biblioteca' ? 'biblioteca' : 'projetos'", leitor)
        self.assertIn('aplicarPreferenciasNoIframe', leitor)

    def test_kokoro_resolve_modelos_na_pasta_persistente_do_usuario(self):
        py = (ROOT / "modules" / "tts_kokoro.py").read_text(encoding="utf-8")
        self.assertIn('from .utilidades import RAIZ_RECURSOS, PASTA_MODELOS_TTS', py)
        self.assertIn('return [PASTA_MODELOS_TTS]', py)
        self.assertIn('pasta = PASTA_MODELOS_TTS', py)
        self.assertIn('MODELS_DIR, MODEL_PATH, VOICES_PATH = _resolver_modelos()', py)
        self.assertNotIn('Path(meipass) / "models"', py)

    def test_kokoro_prepara_espeak_empacotado(self):
        py = (ROOT / "modules" / "tts_kokoro.py").read_text(encoding="utf-8")
        self.assertIn('import espeakng_loader', py)
        self.assertIn('espeakng_loader.make_library_available()', py)
        self.assertIn('PHONEMIZER_ESPEAK_LIBRARY', py)

    def test_kokoro_explicita_pydoc_e_joblib_para_pyinstaller(self):
        py = (ROOT / "modules" / "tts_kokoro.py").read_text(encoding="utf-8")
        self.assertIn('import pydoc', py)
        self.assertIn('import joblib', py)
        self.assertIn('pydoc/joblib importados', py)

    def test_tts_possui_log_dedicado_em_txt(self):
        logging_py = (ROOT / "modules" / "logging_config.py").read_text(encoding="utf-8")
        kokoro_py = (ROOT / "modules" / "tts_kokoro.py").read_text(encoding="utf-8")
        server_py = (ROOT / "modules" / "servidor_flask.py").read_text(encoding="utf-8")
        js = (ROOT / "static" / "js" / "leitor_tts.js").read_text(encoding="utf-8")

        self.assertIn('ARQUIVO_LOG_TTS = "tts_debug.txt"', logging_py)
        self.assertIn('def obter_logger_tts(', logging_py)
        self.assertIn('Runtime TTS | frozen=', kokoro_py)
        self.assertIn('get_available_providers()', kokoro_py)
        self.assertIn('WAV PCM16 criado sem libsndfile | req=', kokoro_py)
        self.assertIn('@app.post("/api/tts/log")', server_py)
        self.assertIn('CLIENT | event=%s', server_py)
        self.assertIn("enviarLogTts('fetch_resposta'", js)
        self.assertIn("enviarLogTts('audio_play_rejeitado'", js)
        self.assertIn("enviarLogTts('audio_error_event'", js)

    def test_spec_mantem_modelos_externos_e_dependencias_kokoro(self):
        spec = (ROOT / "Gutenberg.spec").read_text(encoding="utf-8")
        self.assertIn('Modelos TTS externos: nenhum arquivo de modelo sera incluido no bundle', spec)
        self.assertNotIn('datas.append((str(model_file), "models"))', spec)
        self.assertIn('collect_all(package_name)', spec)
        self.assertIn('collect_dynamic_libs("onnxruntime")', spec)
        self.assertNotIn('collect_all("onnxruntime")', spec)
        self.assertNotIn('collect_submodules("onnxruntime")', spec)
        self.assertNotIn('collect_all("soundfile")', spec)
        self.assertIn('"onnxruntime"', spec)
        self.assertIn('"espeakng_loader"', spec)
        self.assertIn('"phonemizer"', spec)
        self.assertIn('"numpy"', spec)
        self.assertIn('"pydoc"', spec)
        self.assertIn('"joblib"', spec)
        excludes = spec.split('excludes = [', 1)[1].split(']', 1)[0]
        self.assertNotIn('"numpy"', excludes)
        self.assertNotIn('"pydoc"', excludes)


    def test_tts_forca_sessao_onnx_cpu_no_executavel(self):
        py = (ROOT / "modules" / "tts_kokoro.py").read_text(encoding="utf-8")
        self.assertIn('provider_cpu = "CPUExecutionProvider"', py)
        self.assertIn('providers=[provider_cpu]', py)
        self.assertIn('Kokoro.from_session(sessao', py)
        self.assertIn('ORT_SEQUENTIAL', py)

    def test_spec_e_iss_revisados_para_empacotamento_consistente(self):
        spec = (ROOT / "Gutenberg.spec").read_text(encoding="utf-8")
        iss = (ROOT / "Gutenberg.iss").read_text(encoding="utf-8")
        self.assertIn('contents_directory="_internal"', spec)
        self.assertIn('recursos_obrigatorios = [', spec)
        self.assertIn('_sem_duplicatas_toc(datas)', spec)
        self.assertIn('_sem_duplicatas_toc(binaries)', spec)
        self.assertIn('#define MyAppIcon AddBackslash(SourcePath) + "installer.ico"', iss)
        self.assertIn('OutputBaseFilename={#MyAppName}_{#MyAppVersion}_Installer', iss)
        self.assertIn('SetupLogging=yes', iss)
        self.assertIn('RestartApplications=no', iss)

    def test_spec_desabilita_upx_para_bibliotecas_nativas_do_tts(self):
        spec = (ROOT / "Gutenberg.spec").read_text(encoding="utf-8")
        self.assertGreaterEqual(spec.count('upx=False'), 2)

    def test_requirements_fixa_onnxruntime_128(self):
        req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn('kokoro-onnx==0.6.1', req)
        self.assertIn('onnxruntime==1.28.0', req)

    def test_spec_bloqueia_stack_tts_incorreto_e_nao_empacota_modelo(self):
        spec = (ROOT / "Gutenberg.spec").read_text(encoding="utf-8")
        self.assertIn('ORT_ESPERADO = "1.28.0"', spec)
        self.assertIn('ort_instalado != ORT_ESPERADO', spec)
        self.assertIn('onnxruntime-gpu', spec)
        self.assertIn('phonemizer-fork', spec)
        self.assertIn('nenhum arquivo de modelo sera incluido no bundle', spec)
        self.assertNotIn('MODEL_FP32_MIN_BYTES = 250_000_000', spec)

    def test_runtime_recusa_ort_errado_e_separa_fonemizacao_da_inferencia(self):
        py = (ROOT / "modules" / "tts_kokoro.py").read_text(encoding="utf-8")
        self.assertIn('ORT_ESPERADO_NO_EXE = "1.28.0"', py)
        self.assertIn('_validar_modelo_cpu()', py)
        self.assertIn('Fonemizacao iniciada', py)
        self.assertIn('Fonemizacao concluida', py)
        self.assertIn('is_phonemes=True', py)

    def test_requirements_fixa_stack_tts_cpu(self):
        req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn('onnxruntime==1.28.0', req)
        self.assertIn('phonemizer==3.4.0', req)
        self.assertNotIn('phonemizer-fork==', req)
        self.assertNotIn('soundfile>=', req)
        self.assertIn('pyinstaller-hooks-contrib>=2024.9', req)
        self.assertIn('espeakng-loader==0.2.4', req)

    def test_runtime_hook_registra_subpastas_dll_do_tts(self):
        spec = (ROOT / "Gutenberg.spec").read_text(encoding="utf-8")
        hook = (ROOT / "hooks" / "rthook_tts_windows.py").read_text(encoding="utf-8")
        self.assertIn('runtime_hooks=[str(project_dir / "hooks" / "rthook_tts_windows.py")]', spec)
        self.assertIn('raiz / "onnxruntime" / "capi"', hook)
        self.assertIn('raiz / "espeakng_loader"', hook)
        self.assertIn('os.add_dll_directory', hook)
        self.assertIn('PHONEMIZER_ESPEAK_LIBRARY', hook)
        self.assertIn('PHONEMIZER_ESPEAK_DATA_PATH', hook)
        self.assertIn('_gutenberg_tts_dll_handles', hook)

    def test_tts_wav_nao_depende_de_libsndfile(self):
        req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        spec = (ROOT / "Gutenberg.spec").read_text(encoding="utf-8")
        py = (ROOT / "modules" / "tts_kokoro.py").read_text(encoding="utf-8")
        self.assertNotIn('soundfile', req.lower())
        self.assertNotIn('_soundfile_data', spec)
        self.assertNotIn('import soundfile', py)
        self.assertIn('def _samples_para_wav_pcm16', py)
        self.assertIn('import wave', py)

    def test_erro_runtime_tts_e_visivel_no_executavel(self):
        js = (ROOT / "static" / "js" / "leitor_tts.js").read_text(encoding="utf-8")
        server = (ROOT / "modules" / "servidor_flask.py").read_text(encoding="utf-8")
        self.assertIn('reader.tts_runtime_error', js)
        self.assertIn('window.alert(`${titulo}', js)
        self.assertIn('"log": str(obter_caminho_log_tts())', server)
        for nome in ("pt_BR.json", "en_US.json"):
            data = json.loads((ROOT / "locales" / nome).read_text(encoding="utf-8"))
            self.assertIn("reader.tts_runtime_error", data)

    def test_ptbr_usa_g2p_espeak_dedicado_em_vez_do_tokenizer_ingles(self):
        py = (ROOT / "modules" / "tts_kokoro.py").read_text(encoding="utf-8")
        self.assertIn('language="pt-br"', py)
        self.assertIn('tie="^"', py)
        self.assertIn('return _phonemizar_ptbr_kokoro(texto), "espeak-g2p-pt-br"', py)
        self.assertIn('voice=voz', py)
        self.assertIn('is_phonemes=True', py)
        trecho_pt = py.split('if lang == "pt-br":', 1)[1].split('return kokoro.tokenizer.phonemize', 1)[0]
        self.assertNotIn('kokoro.tokenizer.phonemize(texto, lang=lang)', trecho_pt)

    def test_tts_valida_pacote_atual_de_54_vozes_e_ptbr(self):
        py = (ROOT / "modules" / "tts_kokoro.py").read_text(encoding="utf-8")
        modelos = (ROOT / "modules" / "tts_modelos.py").read_text(encoding="utf-8")
        self.assertIn('VOICES_MIN_COUNT = 54', py)
        self.assertIn('PTBR_VOICES = {"pf_dora", "pm_alex", "pm_santa"}', py)
        self.assertIn('np.load(str(VOICES_PATH), allow_pickle=False)', py)
        self.assertIn('MIN_VOICES = 54', modelos)
        self.assertIn('PTBR_VOICES = {"pf_dora", "pm_alex", "pm_santa"}', modelos)
        self.assertIn('model-files-v1.1', modelos)

    def test_gerenciador_baixa_modelo_e_vozes_do_mesmo_release(self):
        modelos = (ROOT / "modules" / "tts_modelos.py").read_text(encoding="utf-8")
        self.assertIn('model-files-v1.1/kokoro-v1.0.onnx', modelos)
        self.assertIn('model-files-v1.1/voices-v1.0.bin', modelos)
        self.assertIn('MIN_VOICES = 54', modelos)
        self.assertIn('PASTA_MODELOS_TTS / MODEL_NAME', modelos)
        self.assertIn('PASTA_MODELOS_TTS / VOICES_NAME', modelos)


if __name__ == "__main__":
    unittest.main()
