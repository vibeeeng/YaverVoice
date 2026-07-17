from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.core.audio_cleanup import build_cleanup_filter, cleanup_audio_file, prepare_audio_for_transcription


class AudioCleanupTests(unittest.TestCase):
    def test_cleanup_audio_file_deletes_generated_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cleanup_path = Path(temp_dir) / "cleanup_audio.wav"
            cleanup_path.write_bytes(b"temporary")

            cleanup_audio_file(cleanup_path)

            self.assertFalse(cleanup_path.exists())

    def test_noops_when_disabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "audio.wav"
            audio_path.write_bytes(b"audio")

            result = prepare_audio_for_transcription(
                str(audio_path),
                mode="off",
                temp_dir=Path(temp_dir),
            )

        self.assertEqual(result.path, str(audio_path))
        self.assertFalse(result.cleanup_required)
        self.assertIsNone(result.skipped_reason)

    def test_noops_when_ffmpeg_is_unavailable(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "src.core.audio_cleanup.is_ffmpeg_available", return_value=False
        ):
            audio_path = Path(temp_dir) / "audio.wav"
            audio_path.write_bytes(b"audio")

            result = prepare_audio_for_transcription(
                str(audio_path),
                mode="noisy",
                temp_dir=Path(temp_dir),
            )

        self.assertEqual(result.path, str(audio_path))
        self.assertFalse(result.cleanup_required)
        self.assertEqual(result.skipped_reason, "FFmpeg is not available")

    def test_returns_cleanup_file_when_ffmpeg_succeeds(self):
        def fake_run(cmd, **_kwargs):
            Path(cmd[-1]).write_bytes(b"clean audio")
            return SimpleNamespace(returncode=0, stderr=b"")

        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "src.core.audio_cleanup.is_ffmpeg_available", return_value=True
        ), patch("src.core.audio_cleanup.get_ffmpeg_path", return_value="ffmpeg"), patch(
            "src.core.audio_cleanup.subprocess.run", side_effect=fake_run
        ):
            audio_path = Path(temp_dir) / "audio.wav"
            audio_path.write_bytes(b"audio")

            result = prepare_audio_for_transcription(
                str(audio_path),
                mode="normal",
                temp_dir=Path(temp_dir),
            )

        self.assertNotEqual(result.path, str(audio_path))
        self.assertTrue(result.cleanup_required)
        self.assertIsNone(result.skipped_reason)

    def test_normal_filter_chain(self):
        filter_chain, fallback = build_cleanup_filter("normal")

        self.assertEqual(filter_chain, "highpass=f=80,lowpass=f=7600,loudnorm=I=-18:TP=-1.5:LRA=11")
        self.assertIsNone(fallback)

    def test_noisy_uses_afftdn_when_rnnoise_model_is_missing(self):
        filter_chain, fallback = build_cleanup_filter("noisy", "missing.rnnn")

        self.assertEqual(filter_chain, "afftdn=nf=-25,loudnorm=I=-18:TP=-1.5:LRA=11")
        self.assertIn("RNNoise model is not available", fallback)

    def test_noisy_uses_rnnoise_when_model_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "rnnoise.rnnn"
            model_path.write_text("model", encoding="utf-8")

            filter_chain, fallback = build_cleanup_filter("noisy", model_path)

        escaped_path = str(model_path).replace("\\", "/").replace(":", "\\:")
        self.assertEqual(
            filter_chain,
            f"arnndn=m={escaped_path},loudnorm=I=-18:TP=-1.5:LRA=11",
        )
        self.assertIsNone(fallback)

    def test_severe_uses_afftdn_when_rnnoise_model_is_missing(self):
        filter_chain, fallback = build_cleanup_filter("severe", "missing.rnnn")

        self.assertEqual(
            filter_chain,
            "afftdn=nf=-30,highpass=f=80,lowpass=f=7600,loudnorm=I=-18:TP=-1.5:LRA=11",
        )
        self.assertIn("RNNoise model is not available", fallback)
