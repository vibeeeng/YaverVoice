from __future__ import annotations

import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.core.audio_splitter import AudioSplitter
from src.core.transcriber import GroqTranscriber


class AudioDurationTests(unittest.TestCase):
    @staticmethod
    def _tinytag_module(*, duration: float | None = None, error: Exception | None = None):
        module = types.ModuleType("tinytag")

        class FakeTinyTag:
            @staticmethod
            def get(_filepath):
                if error:
                    raise error
                return SimpleNamespace(duration=duration)

        module.TinyTag = FakeTinyTag
        return module

    def test_transcriber_uses_tinytag_duration(self):
        transcriber = GroqTranscriber.__new__(GroqTranscriber)
        with patch.dict(sys.modules, {"tinytag": self._tinytag_module(duration=12.5)}):
            self.assertEqual(transcriber.get_audio_duration("sample.m4a"), 12.5)

    def test_transcriber_falls_back_to_ffprobe(self):
        soundfile = types.ModuleType("soundfile")
        soundfile.SoundFile = lambda _path: (_ for _ in ()).throw(RuntimeError("unsupported"))
        with patch.dict(sys.modules, {
            "tinytag": self._tinytag_module(error=RuntimeError("unsupported")),
            "soundfile": soundfile,
        }), patch("src.core.ffmpeg_utils.get_duration_ffprobe", return_value=9.25):
            transcriber = GroqTranscriber.__new__(GroqTranscriber)
            self.assertEqual(transcriber.get_audio_duration("sample.bin"), 9.25)

    def test_splitter_uses_tinytag_before_fallbacks(self):
        with patch.dict(sys.modules, {"tinytag": self._tinytag_module(duration=42.0)}):
            splitter = AudioSplitter.__new__(AudioSplitter)
            self.assertEqual(splitter.get_audio_duration("sample.mp3"), 42.0)


if __name__ == "__main__":
    unittest.main()
