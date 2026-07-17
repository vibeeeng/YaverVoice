from __future__ import annotations

import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

from src.config import Config
from src.core.backend_service import BackendService
from tests.sidecar_test_support import (
    FAKE_SHORT_GROQ_KEY,
    BlockingDocsService,
    BlockingSplitService,
    BlockingTranscriptionService,
    FakeInjector,
    FakeRecorder,
    SidecarTestCase,
)


class SidecarWorkflowTests(SidecarTestCase):
    def test_recording_stop_returns_while_transcription_continues(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("", encoding="utf-8")
            config = Config(str(env_path))
            config.reload_env()
            service = BlockingTranscriptionService(
                config=config,
                injector=FakeInjector(),
                recorder=FakeRecorder(Path(temp_dir) / "recording.wav"),
                build_info={"version": "test", "display": "Test Build"},
            )

            service.start_recording("hotkey_toggle")
            stopped = service.stop_recording()
            self.assertFalse(stopped["recording"])
            self.assertTrue(stopped["transcribing"])
            self.assertTrue(service.transcription_started.wait(timeout=1))
            self.assertTrue(service.recording_status()["transcribing"])

            service.release_transcription.set()
            deadline = time.time() + 1
            while service.recording_status()["transcribing"] and time.time() < deadline:
                time.sleep(0.01)

        self.assertFalse(service.recording_status()["transcribing"])
        self.assertEqual(service.recording_status()["mode"], "standard")

    def test_file_transcription_request_returns_while_transcription_continues(self):
        events = []
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("", encoding="utf-8")
            audio_path = Path(temp_dir) / "selected.wav"
            audio_path.write_bytes(b"RIFFfake")
            config = Config(str(env_path))
            config.reload_env()
            service = BlockingTranscriptionService(
                config=config,
                injector=FakeInjector(),
                build_info={"version": "test", "display": "Test Build"},
                on_event=lambda method, params: events.append((method, params)),
            )

            selected = service.register_selected_file(str(audio_path))
            response = service.transcribe_file(selected["token"])
            self.assertTrue(response["accepted"])
            self.assertEqual(response["message"], "Transcription started.")
            self.assertTrue(service.transcription_started.wait(timeout=1))
            self.assertEqual(response["history"][0]["text"], "Processing...")

            service.release_transcription.set()
            deadline = time.time() + 1
            while not any(event[0] == "file.status" and event[1].get("state") == "complete" for event in events):
                self.assertLess(time.time(), deadline)
                time.sleep(0.01)

        self.assertTrue(any(event[0] == "history.updated" for event in events))
        self.assertEqual(service.injector.copied, [])
        self.assertTrue(
            any(
                event[0] == "toast" and event[1].get("message") == "Transcript ready. Saved to history."
                for event in events
            )
        )

    def test_split_request_returns_while_workflow_continues(self):
        events = []
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("", encoding="utf-8")
            audio_path = Path(temp_dir) / "long.wav"
            audio_path.write_bytes(b"RIFFfake")
            config = Config(str(env_path))
            config.reload_env()
            service = BlockingSplitService(
                config=config,
                injector=FakeInjector(),
                build_info={"version": "test", "display": "Test Build"},
                on_event=lambda method, params: events.append((method, params)),
            )

            selected = service.register_selected_file(str(audio_path))
            response = service.start_split_workflow(selected["token"])
            self.assertTrue(response["accepted"])
            self.assertEqual(response["message"], "Split workflow started.")
            self.assertTrue(service.split_started.wait(timeout=1))

            service.release_split.set()
            deadline = time.time() + 1
            while not any(event[0] == "split.step" and event[1].get("state") == "complete" for event in events):
                self.assertLess(time.time(), deadline)
                time.sleep(0.01)

    def test_docs_request_returns_while_workflow_continues(self):
        events = []
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(f"GROQ_API_KEY={FAKE_SHORT_GROQ_KEY}", encoding="utf-8")
            audio_path = Path(temp_dir) / "meeting.wav"
            output_path = Path(temp_dir) / "meeting.md"
            audio_path.write_bytes(b"RIFFfake")
            config = Config(str(env_path))
            config.reload_env()
            service = BlockingDocsService(
                config=config,
                injector=FakeInjector(),
                build_info={"version": "test", "display": "Test Build"},
                on_event=lambda method, params: events.append((method, params)),
            )

            selected = service.register_selected_docs_file(str(audio_path))
            response = service.start_docs_workflow(selected["token"], str(output_path), "qwen/qwen3-32b", "detailed", "tr")
            self.assertTrue(response["accepted"])
            self.assertEqual(response["message"], "Docs workflow started (Detailed · Turkish).")
            self.assertEqual(response["model"], "qwen/qwen3-32b")
            self.assertEqual(response["detail"], "detailed")
            self.assertEqual(response["output_language"], "tr")
            self.assertEqual(response["output_language_label"], "Turkish")
            self.assertEqual(response["history"][0]["text"], "Processing...")
            self.assertTrue(service.docs_started.wait(timeout=1))

            service.release_docs.set()
            deadline = time.time() + 1
            while not any(event[0] == "docs.status" and event[1].get("state") == "complete" for event in events):
                self.assertLess(time.time(), deadline)
                time.sleep(0.01)
            self.assertTrue(output_path.exists())

        self.assertTrue(any(event[0] == "history.updated" for event in events))

    def test_docs_requires_groq_api_key_for_markdown_generation(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("", encoding="utf-8")
            audio_path = Path(temp_dir) / "meeting.wav"
            output_path = Path(temp_dir) / "meeting.md"
            audio_path.write_bytes(b"RIFFfake")
            config = Config(str(env_path))
            config.reload_env()
            service = BackendService(
                config=config,
                injector=FakeInjector(),
                build_info={"version": "test", "display": "Test Build"},
            )

            selected = service.register_selected_docs_file(str(audio_path))
            with self.assertRaisesRegex(ValueError, "Groq API key required"):
                service.start_docs_workflow(selected["token"], str(output_path))

    def test_docs_preflight_reports_missing_api_key_before_save(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("", encoding="utf-8")
            audio_path = Path(temp_dir) / "meeting.wav"
            audio_path.write_bytes(b"RIFFfake")
            config = Config(str(env_path))
            config.reload_env()
            service = BackendService(
                config=config,
                injector=FakeInjector(),
                build_info={"version": "test", "display": "Test Build"},
            )

            selected = service.register_selected_docs_file(str(audio_path))
            response = service.docs_preflight(selected["token"], "qwen/qwen3-32b", "detailed", "tr")

        self.assertFalse(response["ready"])
        self.assertIn("Groq API key required", response["blockers"][0])
        self.assertEqual(response["model"], "qwen/qwen3-32b")
        self.assertEqual(response["detail"], "detailed")
        self.assertEqual(response["output_language"], "tr")
        self.assertEqual(response["output_language_label"], "Turkish")

    def test_docs_preflight_defaults_output_language_from_settings_language(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(f"GROQ_API_KEY={FAKE_SHORT_GROQ_KEY}\nTRANSCRIPTION_LANGUAGE=de", encoding="utf-8")
            audio_path = Path(temp_dir) / "meeting.wav"
            audio_path.write_bytes(b"RIFFfake")
            config = Config(str(env_path))
            config.reload_env()
            service = BackendService(
                config=config,
                injector=FakeInjector(),
                build_info={"version": "test", "display": "Test Build"},
            )

            selected = service.register_selected_docs_file(str(audio_path))
            response = service.docs_preflight(selected["token"], "qwen/qwen3-32b", "detailed")
            config.save_language("auto")
            auto_response = service.docs_preflight(selected["token"], "qwen/qwen3-32b", "detailed")

        self.assertTrue(response["ready"])
        self.assertEqual(response["output_language"], "de")
        self.assertEqual(response["output_language_label"], "German")
        self.assertTrue(auto_response["ready"])
        self.assertEqual(auto_response["output_language"], "same")
        self.assertEqual(auto_response["output_language_label"], "Same as transcript")

    def test_docs_preflight_rejects_invalid_token_model_and_output_language(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(f"GROQ_API_KEY={FAKE_SHORT_GROQ_KEY}", encoding="utf-8")
            config = Config(str(env_path))
            config.reload_env()
            service = BackendService(
                config=config,
                injector=FakeInjector(),
                build_info={"version": "test", "display": "Test Build"},
            )

            response = service.docs_preflight("missing", "bad-model", "bad-detail", "bad-language")
            auto_response = service.docs_preflight("missing", "qwen/qwen3-32b", "detailed", "auto")

        self.assertFalse(response["ready"])
        self.assertIn("Invalid Docs model", response["blockers"])
        self.assertIn("Invalid Docs detail", response["blockers"])
        self.assertIn("Invalid Docs output language", response["blockers"])
        self.assertIn("File must be selected from the app before use", response["blockers"])
        self.assertIn("Invalid Docs output language", auto_response["blockers"])

    def test_docs_models_return_supported_profiles(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            service = self.make_service(temp_dir)
            models = service.docs_model_profiles()

        self.assertTrue(any(model["id"] == "meta-llama/llama-4-scout-17b-16e-instruct" for model in models))
        self.assertTrue(all("chunk_chars" in model for model in models))

    def test_docs_details_return_supported_profiles(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            service = self.make_service(temp_dir)
            details = service.docs_detail_profiles()

        self.assertEqual([detail["id"] for detail in details], ["short", "standard", "detailed"])

    def test_converter_request_returns_while_conversion_continues(self):
        events = []
        conversion_started = threading.Event()
        release_conversion = threading.Event()

        def blocking_convert(_input_path: str, _output_path: str, _output_format: str) -> tuple[bool, str]:
            conversion_started.set()
            release_conversion.wait(timeout=2)
            return True, "ok"

        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ), patch("src.core.backend.converter.is_ffmpeg_available", return_value=True), patch(
            "src.core.backend.converter.convert_audio", side_effect=blocking_convert
        ):
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("", encoding="utf-8")
            audio_path = Path(temp_dir) / "input.wav"
            output_path = Path(temp_dir) / "output.mp3"
            audio_path.write_bytes(b"RIFFfake")
            config = Config(str(env_path))
            config.reload_env()
            service = BackendService(
                config=config,
                injector=FakeInjector(),
                build_info={"version": "test", "display": "Test Build"},
                on_event=lambda method, params: events.append((method, params)),
            )

            selected = service.register_selected_file(str(audio_path), for_convert=True)
            response = service.convert_file(selected["token"], "mp3", str(output_path))
            self.assertTrue(response["accepted"])
            self.assertEqual(response["message"], "Conversion started.")
            self.assertTrue(conversion_started.wait(timeout=1))

            release_conversion.set()
            deadline = time.time() + 1
            while not any(event[0] == "converter.status" and event[1].get("state") == "complete" for event in events):
                self.assertLess(time.time(), deadline)
                time.sleep(0.01)
