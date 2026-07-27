from __future__ import annotations

import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.config import Config
from src.core.transcriber import GroqTranscriber, LocalWhisperTranscriber


class FakeLocalModel:
    def __init__(self):
        self.last_path = None
        self.last_kwargs = None

    def transcribe(self, path, **kwargs):
        self.last_path = path
        self.last_kwargs = kwargs
        return [SimpleNamespace(text=" hello")], SimpleNamespace(language=kwargs.get("language"))


class FakeGroqAudioEndpoint:
    def __init__(self, response: str):
        self.response = response
        self.call_count = 0
        self.last_kwargs = None

    def create(self, **kwargs):
        self.call_count += 1
        self.last_kwargs = kwargs
        return self.response


class LocalTranslateModelTests(unittest.TestCase):
    def make_ready_model_dir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        for name in ("model.bin", "config.json", "tokenizer.json"):
            (path / name).write_text("x", encoding="utf-8")

    def make_config(self, temp_dir: str, *, profile: str, translate: bool) -> Config:
        env_path = Path(temp_dir) / ".env"
        env_path.write_text(
            "\n".join(
                [
                    f"LOCAL_WHISPER_PROFILE={profile}",
                    f"TRANSLATE_TO_EN={'true' if translate else 'false'}",
                ]
            ),
            encoding="utf-8",
        )
        config = Config(str(env_path))
        config.reload_env()
        return config

    @staticmethod
    def make_huggingface_module(files: list[tuple[str, int]]) -> types.ModuleType:
        module = types.ModuleType("huggingface_hub")

        class FakeHfApi:
            def model_info(self, repo_id, *, files_metadata=False):
                if not files_metadata:
                    raise AssertionError("Local setup metadata must request file sizes")
                return SimpleNamespace(
                    id=repo_id,
                    siblings=[
                        SimpleNamespace(rfilename=filename, size=size)
                        for filename, size in files
                    ],
                )

        module.HfApi = FakeHfApi
        return module

    def test_local_setup_info_reports_allowlisted_source_size_and_destination(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            config = self.make_config(temp_dir, profile="quality", translate=False)
            huggingface_module = self.make_huggingface_module(
                [
                    ("config.json", 20),
                    ("model.bin", 1000),
                    ("tokenizer.json", 30),
                    ("vocabulary.json", 40),
                    ("README.md", 9999),
                ]
            )

            with patch.dict(sys.modules, {"huggingface_hub": huggingface_module}):
                info = LocalWhisperTranscriber.get_setup_info(config)

        self.assertEqual(info["display_name"], "Quality Turbo")
        self.assertEqual(info["repository"], "deepdml/faster-whisper-large-v3-turbo-ct2")
        self.assertEqual(
            info["source_url"],
            "https://huggingface.co/deepdml/faster-whisper-large-v3-turbo-ct2",
        )
        self.assertEqual(info["total_bytes"], 1090)
        self.assertEqual(
            info["model_dir"],
            str(Path(temp_dir) / "models" / "whisper-deepdml-faster-whisper-large-v3-turbo-ct2"),
        )
        self.assertFalse(info["already_ready"])

    def test_prepare_model_emits_real_downloaded_bytes_and_verifies_files(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            config = self.make_config(temp_dir, profile="balanced", translate=False)
            events = []
            huggingface_module = self.make_huggingface_module(
                [("config.json", 10), ("model.bin", 100), ("tokenizer.json", 10)]
            )
            utils_module = types.ModuleType("faster_whisper.utils")

            def fake_download_model(_model_name, **kwargs):
                model_dir = Path(kwargs["output_dir"])
                partial_dir = model_dir / ".cache" / "huggingface" / "download"
                partial_dir.mkdir(parents=True, exist_ok=True)
                (partial_dir / "model.bin.incomplete").write_bytes(b"x" * 60)
                time.sleep(0.08)
                self.make_ready_model_dir(model_dir)
                return str(model_dir)

            utils_module.download_model = fake_download_model
            faster_whisper_module = types.ModuleType("faster_whisper")
            faster_whisper_module.utils = utils_module

            with patch.dict(
                sys.modules,
                {
                    "faster_whisper": faster_whisper_module,
                    "faster_whisper.utils": utils_module,
                    "huggingface_hub": huggingface_module,
                },
            ), patch.object(LocalWhisperTranscriber, "PROGRESS_INTERVAL_SECONDS", 0.01):
                result = LocalWhisperTranscriber.prepare_model(config, progress_callback=events.append)

        downloading = [event for event in events if event["state"] == "downloading"]
        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["transcription_ready"])
        self.assertTrue(downloading)
        self.assertTrue(any(event["downloaded_bytes"] >= 60 for event in downloading))
        self.assertTrue(all(event["total_bytes"] == 120 for event in downloading))
        self.assertEqual(events[-1]["state"], "complete")
        self.assertEqual(events[-1]["percent"], 100.0)

    def test_prepare_model_rejects_incomplete_download_result(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            config = self.make_config(temp_dir, profile="fast", translate=False)
            huggingface_module = self.make_huggingface_module(
                [("config.json", 10), ("model.bin", 100), ("tokenizer.json", 10)]
            )
            utils_module = types.ModuleType("faster_whisper.utils")
            utils_module.download_model = lambda _model_name, **kwargs: kwargs["output_dir"]
            faster_whisper_module = types.ModuleType("faster_whisper")
            faster_whisper_module.utils = utils_module

            with patch.dict(
                sys.modules,
                {
                    "faster_whisper": faster_whisper_module,
                    "faster_whisper.utils": utils_module,
                    "huggingface_hub": huggingface_module,
                },
            ):
                result = LocalWhisperTranscriber.prepare_model(config)

        self.assertEqual(result["status"], "error")
        self.assertFalse(result["transcription_ready"])
        self.assertIn("incomplete", result["message"].lower())

    def test_model_files_ready_rejects_empty_required_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            model_dir = Path(temp_dir)
            for name in ("model.bin", "config.json", "tokenizer.json"):
                (model_dir / name).touch()

            self.assertFalse(LocalWhisperTranscriber._model_files_ready(model_dir))

    def test_prepare_model_rejects_duplicate_setup_without_downloading(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ), patch.object(LocalWhisperTranscriber, "dependency_error", return_value=None), patch.object(
            LocalWhisperTranscriber,
            "resolve_model_dir",
            side_effect=lambda config, model, allow_cache=True: (
                config.get_local_whisper_model_dir(model),
                "managed",
            ),
        ):
            config = self.make_config(temp_dir, profile="balanced", translate=False)
            acquired = LocalWhisperTranscriber._prepare_lock.acquire(blocking=False)
            self.assertTrue(acquired)
            try:
                result = LocalWhisperTranscriber.prepare_model(config)
            finally:
                LocalWhisperTranscriber._prepare_lock.release()

        self.assertEqual(result["status"], "error")
        self.assertFalse(result["transcription_ready"])
        self.assertIn("already in progress", result["message"])

    def test_prepare_model_reports_download_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            config = self.make_config(temp_dir, profile="fast", translate=False)
            events = []
            huggingface_module = self.make_huggingface_module(
                [("config.json", 10), ("model.bin", 100), ("tokenizer.json", 10)]
            )
            utils_module = types.ModuleType("faster_whisper.utils")

            def fail_download(_model_name, **_kwargs):
                raise OSError("disk full")

            utils_module.download_model = fail_download
            faster_whisper_module = types.ModuleType("faster_whisper")
            faster_whisper_module.utils = utils_module

            with patch.dict(
                sys.modules,
                {
                    "faster_whisper": faster_whisper_module,
                    "faster_whisper.utils": utils_module,
                    "huggingface_hub": huggingface_module,
                },
            ):
                result = LocalWhisperTranscriber.prepare_model(config, progress_callback=events.append)

        self.assertEqual(result["status"], "error")
        self.assertFalse(result["transcription_ready"])
        self.assertIn("disk full", result["message"])
        self.assertEqual(events[-1]["state"], "error")

    def test_quality_transcription_uses_turbo_model(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            config = self.make_config(temp_dir, profile="quality", translate=False)

            self.assertEqual(
                config.get_effective_local_whisper_model(translate=False),
                "deepdml/faster-whisper-large-v3-turbo-ct2",
            )

    def test_quality_translation_keeps_selected_turbo_model(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            config = self.make_config(temp_dir, profile="quality", translate=True)

            self.assertEqual(
                config.get_effective_local_whisper_model(translate=True),
                "deepdml/faster-whisper-large-v3-turbo-ct2",
            )

    def test_high_quality_uses_large_v3_model(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            config = self.make_config(temp_dir, profile="high_quality", translate=True)

            self.assertEqual(config.get_effective_local_whisper_model(translate=False), "large-v3")
            self.assertEqual(config.get_effective_local_whisper_model(translate=True), "large-v3")

    def test_fast_and_balanced_use_same_models_for_translation_and_transcription(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            fast = self.make_config(temp_dir, profile="fast", translate=True)
            self.assertEqual(fast.get_effective_local_whisper_model(False), "base")
            self.assertEqual(fast.get_effective_local_whisper_model(True), "base")

            balanced = self.make_config(temp_dir, profile="balanced", translate=True)
            self.assertEqual(balanced.get_effective_local_whisper_model(False), "small")
            self.assertEqual(balanced.get_effective_local_whisper_model(True), "small")

    def test_local_status_detects_ready_faster_whisper_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ), patch("src.core.transcriber.sys.platform", "win32"):
            cached_dir = Path(temp_dir) / "hf-cache" / "small"
            self.make_ready_model_dir(cached_dir)
            utils_module = types.ModuleType("faster_whisper.utils")
            utils_module.download_model = lambda *_args, **_kwargs: str(cached_dir)
            faster_whisper_module = types.ModuleType("faster_whisper")
            faster_whisper_module.utils = utils_module
            config = self.make_config(temp_dir, profile="balanced", translate=False)

            with patch.dict(sys.modules, {"faster_whisper": faster_whisper_module, "faster_whisper.utils": utils_module}):
                status = LocalWhisperTranscriber.get_status(config)

            self.assertEqual(status["status"], "ready")
            self.assertEqual(status["model_source"], "cache")
            self.assertEqual(status["model_dir"], str(cached_dir))

    def test_linux_model_dir_uses_xdg_data_home(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"XDG_DATA_HOME": temp_dir}, clear=True), patch(
            "src.config.sys.platform", "linux"
        ):
            config = self.make_config(temp_dir, profile="balanced", translate=False)

            self.assertEqual(
                config.get_local_whisper_model_dir("small"),
                Path(temp_dir) / "yavervoice" / "models" / "whisper-small",
            )

    def test_linux_model_dir_falls_back_to_home_local_share(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch(
            "src.config.sys.platform", "linux"
        ), patch.object(Path, "home", return_value=Path(temp_dir)):
            config = self.make_config(temp_dir, profile="balanced", translate=False)

            self.assertEqual(
                config.get_local_whisper_model_dir("small"),
                Path(temp_dir) / ".local" / "share" / "yavervoice" / "models" / "whisper-small",
            )

    def test_linux_status_ignores_ready_global_faster_whisper_cache(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"XDG_DATA_HOME": temp_dir}, clear=True), patch(
            "src.config.sys.platform", "linux"
        ), patch("src.core.transcriber.sys.platform", "linux"):
            cached_dir = Path(temp_dir) / "hf-cache" / "small"
            self.make_ready_model_dir(cached_dir)
            utils_module = types.ModuleType("faster_whisper.utils")
            utils_module.download_model = lambda *_args, **_kwargs: str(cached_dir)
            faster_whisper_module = types.ModuleType("faster_whisper")
            faster_whisper_module.utils = utils_module
            config = self.make_config(temp_dir, profile="balanced", translate=False)

            with patch.dict(sys.modules, {"faster_whisper": faster_whisper_module, "faster_whisper.utils": utils_module}):
                status = LocalWhisperTranscriber.get_status(config)

            self.assertEqual(status["status"], "missing")
            self.assertEqual(status["model_source"], "managed")
            self.assertEqual(
                status["model_dir"],
                str(Path(temp_dir) / "yavervoice" / "models" / "whisper-small"),
            )

    def test_linux_prepare_downloads_to_managed_model_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"XDG_DATA_HOME": temp_dir}, clear=True), patch(
            "src.config.sys.platform", "linux"
        ), patch("src.core.transcriber.sys.platform", "linux"):
            calls = []

            def fake_download_model(_model_name, **kwargs):
                calls.append(kwargs)
                self.make_ready_model_dir(Path(kwargs["output_dir"]))
                return kwargs["output_dir"]

            utils_module = types.ModuleType("faster_whisper.utils")
            utils_module.download_model = fake_download_model
            faster_whisper_module = types.ModuleType("faster_whisper")
            faster_whisper_module.utils = utils_module
            huggingface_module = self.make_huggingface_module(
                [("config.json", 10), ("model.bin", 100), ("tokenizer.json", 10)]
            )
            config = self.make_config(temp_dir, profile="balanced", translate=False)

            with patch.dict(
                sys.modules,
                {
                    "faster_whisper": faster_whisper_module,
                    "faster_whisper.utils": utils_module,
                    "huggingface_hub": huggingface_module,
                },
            ):
                status = LocalWhisperTranscriber.prepare_model(config)

            expected_dir = Path(temp_dir) / "yavervoice" / "models" / "whisper-small"
            self.assertEqual(status["status"], "ready")
            self.assertEqual(calls[0]["output_dir"], str(expected_dir))
            self.assertFalse(calls[0]["local_files_only"])

    def test_local_translate_passes_translate_task_and_language(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "audio.wav"
            audio_path.write_bytes(b"not really audio")
            fake_model = FakeLocalModel()
            transcriber = LocalWhisperTranscriber(model_name="large-v3", model_dir=Path(temp_dir))

            with patch.object(LocalWhisperTranscriber, "dependency_error", return_value=None), patch.object(
                LocalWhisperTranscriber, "_model_files_ready", return_value=True
            ), patch.object(transcriber, "_load_model", return_value=fake_model):
                result = transcriber.transcribe(str(audio_path), language="tr", translate=True)

            self.assertEqual(result, "hello")
            self.assertEqual(fake_model.last_kwargs["task"], "translate")
            self.assertEqual(fake_model.last_kwargs["language"], "tr")

    def test_local_non_translate_passes_transcribe_task(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "audio.wav"
            audio_path.write_bytes(b"not really audio")
            fake_model = FakeLocalModel()
            transcriber = LocalWhisperTranscriber(model_name="small", model_dir=Path(temp_dir), audio_cleanup_mode="off")

            with patch.object(LocalWhisperTranscriber, "dependency_error", return_value=None), patch.object(
                LocalWhisperTranscriber, "_model_files_ready", return_value=True
            ), patch.object(transcriber, "_load_model", return_value=fake_model):
                result = transcriber.transcribe(str(audio_path), language="tr", translate=False)

            self.assertEqual(result, "hello")
            self.assertEqual(fake_model.last_kwargs["task"], "transcribe")
            self.assertNotIn("vad_filter", fake_model.last_kwargs)

    def test_local_audio_cleanup_enables_vad_filter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "audio.wav"
            audio_path.write_bytes(b"not really audio")
            fake_model = FakeLocalModel()
            transcriber = LocalWhisperTranscriber(
                model_name="small",
                model_dir=Path(temp_dir),
                audio_cleanup_mode="normal",
            )

            with patch.object(LocalWhisperTranscriber, "dependency_error", return_value=None), patch.object(
                LocalWhisperTranscriber, "_model_files_ready", return_value=True
            ), patch.object(transcriber, "_load_model", return_value=fake_model):
                result = transcriber.transcribe(str(audio_path), language="tr", translate=False)

            self.assertEqual(result, "hello")
            self.assertTrue(fake_model.last_kwargs["vad_filter"])
            self.assertEqual(fake_model.last_kwargs["vad_parameters"]["min_silence_duration_ms"], 500)
            self.assertEqual(fake_model.last_kwargs["vad_parameters"]["speech_pad_ms"], 300)

    def test_groq_translate_uses_translations_endpoint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "audio.wav"
            audio_path.write_bytes(b"fake audio")
            transcriber = GroqTranscriber.__new__(GroqTranscriber)
            transcriber.client = None
            translations = FakeGroqAudioEndpoint("english")
            transcriptions = FakeGroqAudioEndpoint("source")
            client = SimpleNamespace(
                audio=SimpleNamespace(translations=translations, transcriptions=transcriptions)
            )

            result = transcriber._transcribe_once(
                str(audio_path),
                language="tr",
                translate=True,
                client=client,
                model=GroqTranscriber.TRANSLATION_MODEL,
            )

            self.assertEqual(result, "english")
            self.assertEqual(translations.call_count, 1)
            self.assertEqual(transcriptions.call_count, 0)


if __name__ == "__main__":
    unittest.main()
