"""Shared transcription behavior for BackendService."""

from __future__ import annotations

from src.config import Config
from src.core.audio_cleanup import prepare_audio_for_transcription
from src.core.transcriber import LocalWhisperTranscriber, Transcriber, create_transcriber


class TranscriptionMixin:
    def _create_transcriber(self, translate: bool | None = None) -> Transcriber | None:
        self.config.reload_env()
        translate = self.config.translate_enabled() if translate is None else bool(translate)
        provider = self.config.get_transcription_provider()

        if provider == "groq" and not self.config.has_api_key():
            return None

        if provider == "local":
            model_name = self.config.get_effective_local_whisper_model(translate)
            model_dir, model_source = LocalWhisperTranscriber.resolve_model_dir(self.config, model_name, allow_cache=True)
            cache_key = (
                provider,
                translate,
                self.config.get_local_whisper_profile(),
                model_name,
                str(model_dir),
                model_source,
                self.config.get_local_whisper_device(),
                self.config.get_local_whisper_compute_type(),
                self.config.get_local_whisper_cpu_threads(),
                self.config.audio_cleanup_mode(),
            )
            if self._local_transcriber is None or self._local_transcriber_cache_key != cache_key:
                self._local_transcriber = LocalWhisperTranscriber(
                    model_name=model_name,
                    model_dir=model_dir,
                    device=self.config.get_local_whisper_device(),
                    compute_type=self.config.get_local_whisper_compute_type(),
                    cpu_threads=self.config.get_local_whisper_cpu_threads(),
                    audio_cleanup_mode=self.config.audio_cleanup_mode(),
                )
                self._local_transcriber_cache_key = cache_key
            return self._local_transcriber

        try:
            return create_transcriber(self.config, translate=translate)
        except ValueError:
            return None

    def _mark_transcription_error(self, recording_id: str, message: str) -> None:
        self.history.update_transcript(recording_id, f"[Error] {message}")
        self._emit_history()

    def _prepare_audio_for_transcription(self, audio_file_path: str):
        result = prepare_audio_for_transcription(
            audio_file_path,
            mode=self.config.audio_cleanup_mode(),
            temp_dir=Config.get_temp_dir(),
            rnnoise_model_path=self.config.audio_cleanup_rnnoise_model(),
        )
        if result.skipped_reason:
            message = f"Audio cleanup fallback: {result.skipped_reason}" if result.cleanup_required else f"Audio cleanup skipped: {result.skipped_reason}"
            print(f"[BackendService] {message}")
            self._emit("toast", {"type": "warning", "message": message})
        return result
