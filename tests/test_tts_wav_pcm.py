from __future__ import annotations

import io
import wave
import unittest

import numpy as np

from modules.tts_kokoro import _samples_para_wav_pcm16


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


if __name__ == "__main__":
    unittest.main()
