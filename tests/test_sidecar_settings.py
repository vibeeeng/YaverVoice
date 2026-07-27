from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.config import Config
from src.sidecar import METHOD_NOT_FOUND, SidecarJsonRpcServer
from tests.sidecar_test_support import FAKE_GROQ_KEY, SidecarTestCase


class SidecarSettingsTests(SidecarTestCase):
    def test_settings_get_does_not_expose_api_key(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ), patch("src.core.transcriber.LocalWhisperTranscriber.dependency_error", return_value="not installed"):
            service = self.make_service(temp_dir, [f"GROQ_API_KEY={FAKE_GROQ_KEY}"])
            result = service.get_config()

        serialized = json.dumps(result)
        self.assertTrue(result["api_key_exists"])
        self.assertEqual(result["api_key_length"], len(FAKE_GROQ_KEY))
        self.assertNotIn(FAKE_GROQ_KEY, serialized)
        self.assertNotIn("api_key", result)

    def test_settings_save_uses_config_validation(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ), patch("src.core.transcriber.LocalWhisperTranscriber.dependency_error", return_value="not installed"):
            service = self.make_service(temp_dir)
            result = service.save_settings(
                {
                    "transcription_provider": "local",
                    "local_whisper_profile": "fast",
                    "local_whisper_device": "cpu",
                    "local_whisper_compute_type": "int8",
                    "local_whisper_cpu_usage": "low",
                    "translate_enabled": True,
                    "language": "en",
                }
            )

        self.assertEqual(result["transcription_provider"], "local")
        self.assertEqual(result["local_whisper_profile"], "fast")
        self.assertEqual(result["local_whisper_model"], "base")
        self.assertEqual(result["local_whisper_device"], "cpu")
        self.assertEqual(result["local_whisper_compute_type"], "int8")
        self.assertEqual(result["local_whisper_cpu_usage"], "low")
        self.assertTrue(result["translate_enabled"])
        self.assertEqual(result["language"], "en")
        self.assertEqual(result["audio_cleanup_mode"], "off")
        self.assertFalse(result["audio_cleanup_enabled"])

    def test_local_whisper_setup_info_uses_metadata_only_transcriber_contract(self):
        expected = {
            "profile": "balanced",
            "model": "small",
            "display_name": "Balanced",
            "repository": "Systran/faster-whisper-small",
            "source_url": "https://huggingface.co/Systran/faster-whisper-small",
            "total_bytes": 123,
            "model_dir": "managed-model-dir",
            "already_ready": False,
        }
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ), patch("src.core.transcriber.LocalWhisperTranscriber.get_setup_info", return_value=expected) as setup_info:
            service = self.make_service(temp_dir)

            result = service.get_local_whisper_setup_info()

        self.assertEqual(result, expected)
        setup_info.assert_called_once_with(service.config)

    def test_prepare_local_whisper_model_emits_progress_and_preserves_error_result(self):
        events = []

        def fake_prepare(_config, progress_callback=None):
            self.assertIsNotNone(progress_callback)
            progress_callback(
                {
                    "state": "error",
                    "model": "small",
                    "downloaded_bytes": 50,
                    "total_bytes": 100,
                    "percent": 50.0,
                    "model_dir": "managed-model-dir",
                    "message": "network failed",
                }
            )
            return {
                "status": "error",
                "message": "network failed",
                "transcription_ready": False,
            }

        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ), patch(
            "src.core.transcriber.LocalWhisperTranscriber.prepare_model",
            side_effect=fake_prepare,
        ), patch(
            "src.core.transcriber.LocalWhisperTranscriber.dependency_error",
            return_value="not installed",
        ):
            service = self.make_service(temp_dir)
            service._on_event = lambda method, params: events.append((method, params))

            result = service.prepare_local_whisper_model()

        self.assertEqual(result["status"], "error")
        self.assertFalse(result["transcription_ready"])
        self.assertEqual(events[0][0], "settings.local_whisper_progress")
        self.assertEqual(events[0][1]["downloaded_bytes"], 50)
        self.assertEqual(events[-1][0], "settings.changed")

    def test_settings_save_downgrades_rnnoise_modes_when_not_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ), patch("src.core.transcriber.LocalWhisperTranscriber.dependency_error", return_value="not installed"), patch(
            "src.core.backend.settings.is_ffmpeg_filter_available", return_value=False
        ):
            service = self.make_service(temp_dir)
            result = service.save_settings({"audio_cleanup_mode": "severe"})

            saved_env = (Path(temp_dir) / ".env").read_text(encoding="utf-8")

        self.assertEqual(result["audio_cleanup_mode"], "normal")
        self.assertTrue(result["audio_cleanup_enabled"])
        self.assertIn("AUDIO_CLEANUP_MODE=normal", saved_env)
        self.assertIn("AUDIO_CLEANUP_ENABLED=true", saved_env)

    def test_settings_save_downgrades_legacy_audio_cleanup_enabled_when_not_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ), patch("src.core.transcriber.LocalWhisperTranscriber.dependency_error", return_value="not installed"), patch(
            "src.core.backend.settings.is_ffmpeg_filter_available", return_value=False
        ):
            service = self.make_service(temp_dir)
            result = service.save_settings({"audio_cleanup_enabled": True})

        self.assertEqual(result["audio_cleanup_mode"], "normal")
        self.assertTrue(result["audio_cleanup_enabled"])

    def test_settings_get_reports_rnnoise_missing_status(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ), patch("src.core.transcriber.LocalWhisperTranscriber.dependency_error", return_value="not installed"), patch(
            "src.core.backend.settings.is_ffmpeg_filter_available", return_value=True
        ):
            service = self.make_service(temp_dir)
            result = service.get_config()

        status = result["audio_cleanup_status"]
        self.assertFalse(status["rnnoise_ready"])
        self.assertIsNone(status["rnnoise_model_path"])
        self.assertTrue(status["arnndn_available"])
        self.assertIn("RNNoise model missing", status["message"])

    def test_install_rnnoise_model_rejects_invalid_path_and_extension(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            service = self.make_service(temp_dir)
            bad_file = Path(temp_dir) / "model.txt"
            bad_file.write_text("model", encoding="utf-8")

            with self.assertRaises(ValueError):
                service.install_rnnoise_model(str(Path(temp_dir) / "missing.rnnn"))
            with self.assertRaises(ValueError):
                service.install_rnnoise_model(str(bad_file))

    def test_install_rnnoise_model_copies_and_saves_managed_path(self):
        events = []
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ), patch("src.core.backend.settings.is_ffmpeg_filter_available", return_value=True):
            source = Path(temp_dir) / "my model.rnnn"
            source.write_bytes(b"model")
            service = self.make_service(temp_dir)
            service._on_event = lambda method, params: events.append((method, params))

            response = service.install_rnnoise_model(str(source))
            saved_env = (Path(temp_dir) / ".env").read_text(encoding="utf-8")
            config = response["config"]
            managed_path = Path(config["audio_cleanup_status"]["rnnoise_model_path"])
            managed_exists = managed_path.exists()

        self.assertTrue(managed_exists)
        self.assertEqual(managed_path.suffix, ".rnnn")
        self.assertIn("models", str(managed_path))
        self.assertIn("AUDIO_CLEANUP_RNN_MODEL=", saved_env)
        self.assertTrue(config["audio_cleanup_status"]["rnnoise_ready"])
        self.assertEqual(events[0][0], "settings.changed")

    def test_sidecar_does_not_expose_rnnoise_download(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            service = self.make_service(temp_dir)
            server = SidecarJsonRpcServer(service)

            response = server.handle_line('{"jsonrpc":"2.0","id":4,"method":"settings.download_rnnoise_model","params":{}}')

        self.assertFalse(hasattr(service, "download_rnnoise_model"))
        self.assertEqual(response["error"]["code"], METHOD_NOT_FOUND)

    def test_settings_save_allows_rnnoise_modes_when_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ), patch("src.core.backend.settings.is_ffmpeg_filter_available", return_value=True):
            model = Path(temp_dir) / "rnnoise.rnnn"
            model.write_bytes(b"model")
            service = self.make_service(temp_dir, [f"AUDIO_CLEANUP_RNN_MODEL={model}"])

            result = service.save_settings({"audio_cleanup_mode": "severe"})

        self.assertEqual(result["audio_cleanup_mode"], "severe")
        self.assertTrue(result["audio_cleanup_status"]["rnnoise_ready"])

    def test_settings_get_maps_legacy_audio_cleanup_enabled_to_noisy(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ), patch("src.core.transcriber.LocalWhisperTranscriber.dependency_error", return_value="not installed"):
            service = self.make_service(temp_dir, ["AUDIO_CLEANUP_ENABLED=true"])
            result = service.get_config()

        self.assertEqual(result["audio_cleanup_mode"], "noisy")
        self.assertTrue(result["audio_cleanup_enabled"])

    def test_settings_save_persists_selected_microphone(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ), patch("src.core.transcriber.LocalWhisperTranscriber.dependency_error", return_value="not installed"):
            service = self.make_service(temp_dir)
            service.get_microphones = lambda: [{"index": 7, "name": "USB Mic"}]
            result = service.save_settings({"input_device_index": "7"})

        self.assertEqual(result["input_device_index"], 7)
