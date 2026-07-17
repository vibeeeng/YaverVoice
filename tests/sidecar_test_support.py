from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from src.config import Config
from src.core.backend_service import BackendService


FAKE_GROQ_KEY = "gsk" + "_abcdefghijklmnopqrstuvwxyz"
FAKE_SHORT_GROQ_KEY = "gsk" + "_test"


class FakeInjector:
    def __init__(self):
        self.copied = []

    def copy_to_clipboard(self, text: str) -> bool:
        self.copied.append(text)
        return True

    def copy_and_paste(self, text: str) -> tuple[bool, bool]:
        self.copied.append(text)
        return True, True


class FakeRecorder:
    def __init__(self, audio_path: Path):
        self.audio_path = audio_path
        self.started = False

    def start_recording(self, **_kwargs):
        self.started = True

    def stop_recording(self) -> str:
        self.audio_path.write_bytes(b"RIFFfake")
        return str(self.audio_path)


class BlockingTranscriptionService(BackendService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transcription_started = threading.Event()
        self.release_transcription = threading.Event()

    def _transcribe_recording(self, recording_id: str, *, mode: str) -> bool:
        self.transcription_started.set()
        self.release_transcription.wait(timeout=2)
        self.history.update_transcript(recording_id, "done")
        self._emit_history()
        self._handle_transcribed_text("done", mode)
        return True


class BlockingSplitService(BackendService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.split_started = threading.Event()
        self.release_split = threading.Event()

    def _finish_split_workflow(self, path: Path, recording_id: str) -> None:
        self.split_started.set()
        self.release_split.wait(timeout=2)
        self._emit(
            "split.step",
            {
                "state": "complete",
                "recording_id": recording_id,
                "success_count": 1,
                "failed_chunks": [],
                "total_parts": 1,
                "message": "Transcript ready: 1 parts completed.",
            },
        )


class BlockingDocsService(BackendService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.docs_started = threading.Event()
        self.release_docs = threading.Event()

    def _finish_docs_workflow(self, path: Path, output_path: Path, recording_id: str, docs_model: str, docs_detail: str, docs_output_language: str) -> None:
        self.docs_started.set()
        self.release_docs.wait(timeout=2)
        self.history.update_transcript(recording_id, f"transcript for {path.name}")
        self._emit_history()
        output_path.write_text("# Docs\n", encoding="utf-8")
        self._emit(
            "docs.status",
            {
                "state": "complete",
                "recording_id": recording_id,
                "display_path": str(output_path),
                "model": docs_model,
                "detail": docs_detail,
                "output_language": docs_output_language,
                "output_language_label": "Turkish" if docs_output_language == "tr" else "Same as transcript",
                "message": "Markdown document ready.",
            },
        )


class SidecarTestCase(unittest.TestCase):
    def setUp(self):
        self.runtime_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.runtime_dir.cleanup)
        self.app_base_patcher = patch.object(Config, "ensure_app_base_dir", return_value=Path(self.runtime_dir.name))
        self.app_base_patcher.start()
        self.addCleanup(self.app_base_patcher.stop)

    def make_service(self, temp_dir: str, env_lines: list[str] | None = None) -> BackendService:
        env_path = Path(temp_dir) / ".env"
        env_path.write_text("\n".join(env_lines or []), encoding="utf-8")
        config = Config(str(env_path))
        config.reload_env()
        return BackendService(
            config=config,
            injector=FakeInjector(),
            build_info={"version": "test", "display": "Test Build"},
        )
