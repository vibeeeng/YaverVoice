"""Recording-domain behavior for BackendService."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from src.core.audio_cleanup import cleanup_audio_file
from src.core.backend.common import BackendValidationError


class RecordingMixin:
    def recording_status(self) -> dict[str, Any]:
        with self._recording_lock:
            return {
                "recording": self._is_recording,
                "transcribing": self._is_transcribing,
                "mode": self._active_recording_mode,
            }

    def toggle_recording(self, mode: str = "standard") -> dict[str, Any]:
        mode = str(mode or "standard")
        if mode not in {"standard", "bubble", "hotkey_toggle", "push_to_talk"}:
            raise BackendValidationError("Invalid recording mode")
        with self._recording_lock:
            is_recording = self._is_recording
        if is_recording:
            self.stop_recording()
        else:
            self.start_recording(mode)
        return self.recording_status()

    def start_recording(self, mode: str = "standard") -> dict[str, Any]:
        mode = str(mode or "standard")
        if mode not in {"standard", "bubble", "hotkey_toggle", "push_to_talk"}:
            raise BackendValidationError("Invalid recording mode")
        with self._recording_lock:
            if self._is_recording:
                return self.recording_status()
        self._start_recording(mode)
        return self.recording_status()

    def stop_recording(self, *, discard: bool = False) -> dict[str, Any]:
        with self._recording_lock:
            if not self._is_recording:
                return self.recording_status()
        self._stop_recording(discard=discard)
        return self.recording_status()

    def _start_recording(self, mode: str) -> None:
        with self._recording_lock:
            if self._is_recording:
                return
            if mode in {"bubble", "push_to_talk"} and self._is_transcribing:
                if mode == "bubble":
                    self._emit("quick.status", {"state": "processing", "message": "Transkripsiyon devam ediyor"})
                return

        configured_device_index = self.config.get_input_device()
        microphones = self.get_microphones()
        recommended_index = self.platform.get_recommended_microphone(microphones)
        device_index = self.platform.resolve_recording_device(configured_device_index, recommended_index)
        profile = self.platform.get_recording_profile(
            configured_index=configured_device_index,
            resolved_index=device_index,
            microphones=microphones,
            default_sample_rate=self.config.get_sample_rate(),
            default_channels=self.config.get_channels(),
        )

        self.recorder.start_recording(
            device_index=device_index,
            sample_rate=profile.sample_rate,
            channels=profile.channels,
            preprocessing_mode=profile.preprocessing_mode,
            log_diagnostics=self.platform.should_log_recording_diagnostics(),
        )
        time.sleep(0.2)
        if hasattr(self.recorder, "is_recording") and not self.recorder.is_recording():
            message = self._recorder_last_error() or "Recording device could not be opened."
            with self._recording_lock:
                self._is_recording = False
                self._active_recording_mode = "standard"
            self._emit("recording.state", self.recording_status())
            self._emit("toast", {"type": "error", "message": f"Recording failed: {message}"})
            if mode == "bubble":
                self._emit("quick.status", {"state": "error", "message": "Recording failed"})
            return

        with self._recording_lock:
            self._is_recording = True
            self._active_recording_mode = mode
        self._emit("recording.state", self.recording_status())
        if mode == "bubble":
            self._emit("quick.status", {"state": "recording", "message": "Dinleniyor"})

    def _stop_recording(self, *, discard: bool = False) -> None:
        with self._recording_lock:
            mode = self._active_recording_mode
        audio_file = self.recorder.stop_recording()
        with self._recording_lock:
            self._is_recording = False
        self._emit("recording.state", self.recording_status())

        if discard:
            with self._recording_lock:
                self._active_recording_mode = "standard"
            if audio_file:
                try:
                    Path(audio_file).unlink(missing_ok=True)
                except Exception as exc:
                    print(f"[BackendService] Could not delete discarded recording {audio_file}: {exc}")
            self._emit("recording.state", self.recording_status())
            return

        if not audio_file:
            message = self._recorder_last_error() or "No audio was recorded."
            with self._recording_lock:
                self._active_recording_mode = "standard"
            if mode == "bubble":
                self._emit("quick.status", {"state": "error", "message": "Kayıt alınamadı"})
            self._emit("toast", {"type": "error", "message": f"Recording failed: {message}"})
            return

        recording_id = self.history.add_recording(audio_file)
        self._session_temp_files.add(Path(audio_file))
        self._emit_history()
        with self._recording_lock:
            self._is_transcribing = True
        self._emit("recording.state", self.recording_status())
        if mode == "bubble":
            self._emit("quick.status", {"state": "processing", "message": "Ses yazıya çevriliyor"})

        self._start_daemon_thread(
            "sidecar-transcription",
            self._finish_recording_transcription,
            recording_id,
            mode,
        )

    def _finish_recording_transcription(self, recording_id: str, mode: str) -> None:
        success = False
        try:
            success = self._transcribe_recording(recording_id, mode=mode)
        finally:
            with self._recording_lock:
                self._is_transcribing = False
                self._active_recording_mode = "standard"
            self._emit("recording.state", self.recording_status())
            if mode == "bubble":
                self._emit(
                    "quick.status",
                    {
                        "state": "success" if success else "error",
                        "message": "Panoya kopyalandi" if success else "Transcription failed.",
                    },
                )

    def _recorder_last_error(self) -> str | None:
        get_last_error = getattr(self.recorder, "get_last_error", None)
        if not callable(get_last_error):
            return None
        error = get_last_error()
        return str(error) if error else None

    def _transcribe_recording(self, recording_id: str, *, mode: str) -> bool:
        recording = self.history.get_recording(recording_id)
        if not recording:
            return False

        translate = self.config.translate_enabled()
        transcriber = self._create_transcriber(translate=translate)
        if not transcriber:
            message = (
                "API key missing. Save GROQ_API_KEY from Settings and try again."
                if self.config.get_transcription_provider() == "groq"
                else "Local Whisper is not available. Check Settings."
            )
            self._mark_transcription_error(recording_id, message)
            self._emit("toast", {"type": "error", "message": message})
            return False

        language = self.config.get_language()
        if language == "auto":
            language = None
        cleanup_result = self._prepare_audio_for_transcription(recording.filepath)
        try:
            text = transcriber.transcribe(cleanup_result.path, language=language, translate=translate)
        finally:
            if cleanup_result.cleanup_required:
                cleanup_audio_file(cleanup_result.path)
        if not text:
            message = transcriber.last_error or "Transcription failed."
            self._mark_transcription_error(recording_id, message)
            self._emit("toast", {"type": "error", "message": f"Transcription failed: {message}"})
            return False

        self.history.update_transcript(recording_id, text)
        self._emit_history()
        self._handle_transcribed_text(text, mode)
        return True

    def _handle_transcribed_text(self, text: str, mode: str) -> None:
        if mode == "file":
            self._emit("toast", {"type": "success", "message": "Transcript ready. Saved to history."})
            return

        if mode == "bubble":
            self.injector.copy_to_clipboard(text)
            self._emit("toast", {"type": "success", "message": "Transcript ready: copied."})
            return

        if mode == "push_to_talk":
            copied, pasted = self.injector.copy_and_paste(text)
            if pasted:
                self._emit("toast", {"type": "success", "message": "Transcript ready: pasted."})
            elif copied:
                self._emit("toast", {"type": "warning", "message": "Transcript ready: copied. Auto-paste unavailable."})
            else:
                self._emit("toast", {"type": "warning", "message": "Transcript ready. Clipboard unavailable; saved to history."})
            return

        should_paste = self.config.auto_paste_enabled()
        if mode == "hotkey_toggle":
            should_paste = self.config.toggle_recording_auto_paste_enabled()

        if should_paste:
            copied, pasted = self.injector.copy_and_paste(text)
            if pasted:
                self._emit("toast", {"type": "success", "message": "Transcript ready: pasted."})
            elif copied:
                self._emit("toast", {"type": "warning", "message": "Transcript ready: copied. Auto-paste unavailable."})
            else:
                self._emit("toast", {"type": "warning", "message": "Transcript ready. Clipboard unavailable; saved to history."})
        else:
            self._emit("toast", {"type": "success", "message": "Transcript ready."})

    def _recording_exists(self, recording_id: str) -> bool:
        return (
            isinstance(recording_id, str)
            and bool(recording_id.strip())
            and self.history.get_recording(recording_id) is not None
        )
