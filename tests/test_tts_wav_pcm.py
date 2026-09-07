from __future__ import annotations

import io
import wave
import unittest

import numpy as np

from modules.tts_kokoro import _ajustar_pronuncia_w_ptbr, _normalizar_hw_tts, _normalizar_ordinais_numericos_tts, _samples_para_wav_pcm16, idioma_kokoro_para_voz, normalizar_voz_tts


class TtsWavPcmTests(unittest.TestCase):
    def test_float_mono_gera_wav_pcm16_valido(self):
        samples = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)
        audio = _samples_para_wav_pcm16(samples, 24000)

        self.assertTrue(audio.startswith(b"RIFF"))
        self.assertEqual(audio[8:12], b"WAVE")
        with wave.open(io.BytesIO(audio), "rb") as wav:
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.getsampwidth(), 2)
            self.assertEqual(wav.getframerate(), 24000)
            self.assertEqual(wav.getnframes(), len(samples))

    def test_layout_canais_por_frames_e_convertido_para_frames_por_canais(self):
        samples = np.array(
            [
                [0.0, 0.1, 0.2, 0.3],
                [0.0, -0.1, -0.2, -0.3],
            ],
            dtype=np.float32,
        )
        audio = _samples_para_wav_pcm16(samples, 22050)
        with wave.open(io.BytesIO(audio), "rb") as wav:
            self.assertEqual(wav.getnchannels(), 2)
            self.assertEqual(wav.getnframes(), 4)
            self.assertEqual(wav.getframerate(), 22050)

    def test_samples_vazios_falham_de_forma_controlada(self):
        with self.assertRaisesRegex(ValueError, "zero amostras"):
            _samples_para_wav_pcm16(np.array([], dtype=np.float32), 24000)


    def test_hw_global_independe_do_idioma(self):
        self.assertEqual(_normalizar_hw_tts("hwa"), "rua")
        self.assertEqual(_normalizar_hw_tts("Kae-hwa"), "Kae-rua")
        self.assertEqual(_normalizar_hw_tts("HWA"), "rua")

    def test_ptbr_w_apos_consoante_e_tratado_como_u(self):
        self.assertEqual(_ajustar_pronuncia_w_ptbr("rwa"), "rua")
        self.assertEqual(_ajustar_pronuncia_w_ptbr("hwa"), "rua")
        self.assertEqual(_ajustar_pronuncia_w_ptbr("Kae-hwa"), "Kae-rua")
        self.assertEqual(_ajustar_pronuncia_w_ptbr("Kae‑hwa"), "Kae‑rua")
        self.assertEqual(_ajustar_pronuncia_w_ptbr("HWA"), "rua")
        self.assertEqual(_ajustar_pronuncia_w_ptbr("Hwa"), "Rua")
        self.assertEqual(_ajustar_pronuncia_w_ptbr("RWA"), "rua")
        self.assertEqual(_ajustar_pronuncia_w_ptbr("kwan"), "kuan")

    def test_ordinais_hibridos_preservam_somente_numero(self):
        self.assertEqual(_normalizar_ordinais_numericos_tts("1st 20nd 20th 20rd 20st"), "1 20 20 20 20")
        self.assertEqual(_normalizar_ordinais_numericos_tts("Foi o 20th, depois o 21ST."), "Foi o 20, depois o 21.")
        self.assertEqual(_normalizar_ordinais_numericos_tts("capitulo 20"), "capitulo 20")

    def test_ptbr_w_sem_consoante_anterior_nao_e_alterado(self):
        self.assertEqual(_ajustar_pronuncia_w_ptbr("Walter"), "Walter")
        self.assertEqual(_ajustar_pronuncia_w_ptbr("awá"), "awá")
        self.assertEqual(_ajustar_pronuncia_w_ptbr("w"), "w")

    def test_vozes_configuradas_sao_normalizadas_por_idioma(self):
        self.assertEqual(normalizar_voz_tts("pm_alex", "pt_BR"), "pm_alex")
        self.assertEqual(normalizar_voz_tts("af_bella", "en_US"), "af_bella")
        self.assertEqual(normalizar_voz_tts("af_nicole", "en_US"), "af_nicole")
        self.assertEqual(normalizar_voz_tts("bf_emma", "en_US"), "bf_emma")
        self.assertEqual(normalizar_voz_tts("voz_invalida", "pt_BR"), "pf_dora")
        self.assertEqual(normalizar_voz_tts("voz_invalida", "en_US"), "af_heart")

    def test_vozes_britanicas_usam_fonemizacao_en_gb(self):
        self.assertEqual(idioma_kokoro_para_voz("en_US", "bf_emma"), "en-gb")
        self.assertEqual(idioma_kokoro_para_voz("en_US", "bm_george"), "en-gb")
        self.assertEqual(idioma_kokoro_para_voz("en_US", "am_michael"), "en-us")
        self.assertEqual(idioma_kokoro_para_voz("pt_BR", "pm_alex"), "pt-br")

if __name__ == "__main__":
    unittest.main()
