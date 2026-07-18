"""
Headless backend service shared by non-window entrypoints.

This module intentionally avoids UI windows, tray setup, and eager transcriber
construction. It owns the sidecar-safe surface area used by non-window shells:
settings, current-session history, recording, file workflows, and clipboard copy.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable

from src.build_info import load_build_info
from src.config import Config
from src.core.backend.common import BackendValidationError, TEMP_ARTIFACT_PATTERNS, cleanup_stale_temp_files
from src.core.backend.converter import ConverterMixin
from src.core.backend.docs import DocsWorkflowMixin
from src.core.backend.files import FileWorkflowMixin
from src.core.backend.history import HistoryMixin
from src.core.backend.recording import RecordingMixin
from src.core.backend.settings import SettingsMixin
from src.core.backend.transcription import TranscriptionMixin
from src.core.history_manager import HistoryManager
from src.core.input_simulator import TextInjector
from src.core.recorder import AudioRecorder
from src.core.transcriber import LocalWhisperTranscriber
from src.models.recording import SourceType
from src.platform import create_desktop_platform
from src.platform.base import DesktopPlatform


class BackendService(
    SettingsMixin,
    HistoryMixin,
    TranscriptionMixin,
    RecordingMixin,
    FileWorkflowMixin,
    DocsWorkflowMixin,
    ConverterMixin,
):
    """Headless service for sidecar-safe settings, history, and clipboard APIs."""

    _ALLOWED_LANGUAGES = {"tr", "en", "de", "fr", "es", "it", "auto"}
    _LOCAL_KEYS = {
        "local_whisper_profile",
        "local_whisper_model",
        "local_whisper_device",
        "local_whisper_compute_type",
        "local_whisper_cpu_usage",
        "local_whisper_cpu_threads",
    }
    _ALLOWED_AUDIO_EXTENSIONS = {
        ".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus", ".mp4", ".mkv", ".webm"
    }
    _GROQ_MAX_FILE_MB = 24
    _SPLIT_THRESHOLD_SECONDS = 600

    def __init__(
        self,
        *,
        config: Config | None = None,
        history: HistoryManager | None = None,
        platform: DesktopPlatform | None = None,
        injector: TextInjector | None = None,
        recorder: AudioRecorder | None = None,
        build_info: dict[str, str] | None = None,
        on_config_reload: Callable[[], None] | None = None,
        on_hotkeys_reload: Callable[[], None] | None = None,
        on_always_on_top: Callable[[bool], None] | None = None,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.config = config or Config()
        self.history = history or HistoryManager()
        self.platform = platform or create_desktop_platform()
        self.injector = injector or TextInjector(platform=self.platform)
        self.recorder = recorder or AudioRecorder(
            sample_rate=self.config.get_sample_rate(),
            channels=self.config.get_channels(),
            temp_dir=Config.get_temp_dir(),
        )
        self.build_info = build_info or load_build_info()
        self._on_config_reload = on_config_reload
        self._on_hotkeys_reload = on_hotkeys_reload
        self._on_always_on_top = on_always_on_top
        self._on_event = on_event
        self._selected_files: dict[str, Path] = {}
        self._selected_convert_files: dict[str, Path] = {}
        self._selected_docs_files: dict[str, Path] = {}
        self._is_recording = False
        self._is_transcribing = False
        self._active_recording_mode = "standard"
        self._recording_lock = threading.RLock()
        self._local_transcriber_cache_key: tuple[Any, ...] | None = None
        self._local_transcriber: LocalWhisperTranscriber | None = None
        self._session_temp_files: set[Path] = set()
        self._closed = False
        cleanup_stale_temp_files(Config.get_temp_dir())

    def close(self) -> None:
        """Release the service and delete only session-owned temp audio files."""
        if self._closed:
            return
        self._closed = True
        temp_dir = Config.get_temp_dir().resolve()
        candidates = set(self._session_temp_files)
        for recording in self.history.get_recordings():
            if recording.source == SourceType.RECORDING or recording.is_split:
                candidates.add(Path(recording.filepath))
        for candidate in candidates:
            try:
                resolved = candidate.expanduser().resolve()
                resolved.relative_to(temp_dir)
                resolved.unlink(missing_ok=True)
            except ValueError:
                continue
            except OSError as exc:
                print(f"[BackendService] Could not remove session temp file {candidate}: {exc}")
        cleanup_stale_temp_files(temp_dir, max_age_seconds=0)

    def request_shutdown(self) -> dict[str, bool]:
        self._emit("app.shutdown", {"source": "hotkey_ctrl_alt_q"})
        return {"success": True}

    def _start_daemon_thread(self, name: str, target, *args, **kwargs) -> threading.Thread:
        def runner() -> None:
            try:
                target(*args, **kwargs)
            except Exception as exc:
                print(f"[BackendService:{name}] Unhandled exception: {exc}")

        thread = threading.Thread(target=runner, name=name, daemon=True)
        thread.start()
        return thread

    def _emit(self, method: str, params: dict[str, Any]) -> None:
        if self._on_event:
            self._on_event(method, params)
