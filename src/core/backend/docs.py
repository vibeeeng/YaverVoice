"""Docs workflow behavior for BackendService."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from src.config import Config
from src.core.audio_cleanup import cleanup_audio_file
from src.core.audio_splitter import AudioSplitter
from src.core.backend.common import BackendValidationError
from src.core.documentation import (
    DOCS_DETAIL_PROFILES,
    DOCS_MODEL_PROFILES,
    DOCS_OUTPUT_LANGUAGES,
    DEFAULT_DOCS_DETAIL,
    DEFAULT_DOCS_MODEL,
    DEFAULT_DOCS_OUTPUT_LANGUAGE,
    DocumentationError,
    GroqDocumentationGenerator,
)
from src.models.recording import SourceType


class DocsWorkflowMixin:
    def register_selected_docs_file(self, filepath: str) -> dict[str, Any]:
        path = self._resolve_audio_file(filepath)
        token = uuid.uuid4().hex
        self._selected_docs_files[token] = path
        return self._file_metadata(token, path)

    def check_docs_duration(self, token: str) -> dict[str, Any]:
        path = self._docs_file_from_token(token)
        return self._duration_metadata(path)

    def docs_model_profiles(self) -> list[dict[str, Any]]:
        return [dict(profile) for profile in DOCS_MODEL_PROFILES.values()]

    def docs_detail_profiles(self) -> list[dict[str, Any]]:
        return [dict(profile) for profile in DOCS_DETAIL_PROFILES.values()]

    def docs_preflight(
        self,
        token: str,
        model: str | None = None,
        detail: str | None = None,
        output_language: str | None = None,
    ) -> dict[str, Any]:
        self.config.reload_env()
        blockers: list[str] = []
        warnings: list[str] = []
        docs_model = str(model or DEFAULT_DOCS_MODEL)
        docs_detail = str(detail or DEFAULT_DOCS_DETAIL)
        docs_output_language = self._resolve_docs_output_language(output_language)
        profile = DOCS_MODEL_PROFILES.get(docs_model)
        detail_profile = DOCS_DETAIL_PROFILES.get(docs_detail)
        output_language_profile = DOCS_OUTPUT_LANGUAGES.get(docs_output_language)

        if profile is None:
            blockers.append("Invalid Docs model")
        if detail_profile is None:
            blockers.append("Invalid Docs detail")
        if output_language_profile is None:
            blockers.append("Invalid Docs output language")
        if not self.config.has_api_key():
            blockers.append("Groq API key required. Save GROQ_API_KEY in Settings before creating Docs markdown.")
        try:
            self._docs_file_from_token(token)
        except BackendValidationError as exc:
            blockers.append(str(exc))

        provider = self.config.get_transcription_provider()
        if provider == "local":
            warnings.append("Audio transcription can use Local Whisper, but Markdown generation still uses Groq.")

        return {
            "ready": not blockers,
            "blockers": blockers,
            "warnings": warnings,
            "provider": provider,
            "model": docs_model if profile else None,
            "model_label": profile["label"] if profile else None,
            "detail": docs_detail if detail_profile else None,
            "detail_label": detail_profile["label"] if detail_profile else None,
            "output_language": docs_output_language if output_language_profile else None,
            "output_language_label": output_language_profile["label"] if output_language_profile else None,
        }

    def start_docs_workflow(
        self,
        token: str,
        output_path: str,
        model: str | None = None,
        detail: str | None = None,
        output_language: str | None = None,
    ) -> dict[str, Any]:
        preflight = self.docs_preflight(token, model, detail, output_language)
        if preflight["blockers"]:
            raise BackendValidationError(str(preflight["blockers"][0]))
        docs_model = str(model or DEFAULT_DOCS_MODEL)
        docs_detail = str(detail or DEFAULT_DOCS_DETAIL)
        docs_output_language = self._resolve_docs_output_language(output_language)
        path = self._docs_file_from_token(token)
        output = Path(str(output_path)).expanduser().resolve()
        if output.suffix.lower() != ".md":
            output = output.with_suffix(".md")
        profile = DOCS_MODEL_PROFILES[docs_model]
        detail_profile = DOCS_DETAIL_PROFILES[docs_detail]
        recording_id = self.history.add_recording(str(path), source=SourceType.FILE)
        self._emit_history()
        self._emit(
            "docs.status",
            {
                "state": "processing",
                "phase": "transcribing",
                "percent": 4,
                "recording_id": recording_id,
                "file": self._file_metadata(token, path),
                "model": docs_model,
                "model_label": profile["label"],
                "detail": docs_detail,
                "detail_label": detail_profile["label"],
                "output_language": docs_output_language,
                "output_language_label": DOCS_OUTPUT_LANGUAGES[docs_output_language]["label"],
                "chunk_chars": profile["chunk_chars"],
                "message": f"Docs workflow started ({detail_profile['label']} · {DOCS_OUTPUT_LANGUAGES[docs_output_language]['label']}).",
            },
        )
        self._start_daemon_thread(
            "sidecar-docs-workflow",
            self._finish_docs_workflow,
            path,
            output,
            recording_id,
            docs_model,
            docs_detail,
            docs_output_language,
        )
        return {
            "success": True,
            "accepted": True,
            "id": recording_id,
            "model": docs_model,
            "model_label": profile["label"],
            "detail": docs_detail,
            "detail_label": detail_profile["label"],
            "output_language": docs_output_language,
            "output_language_label": DOCS_OUTPUT_LANGUAGES[docs_output_language]["label"],
            "message": f"Docs workflow started ({detail_profile['label']} · {DOCS_OUTPUT_LANGUAGES[docs_output_language]['label']}).",
            "history": self.list_history(),
        }

    def _finish_docs_workflow(
        self,
        path: Path,
        output_path: Path,
        recording_id: str,
        docs_model: str,
        docs_detail: str,
        docs_output_language: str,
    ) -> None:
        try:
            transcript = self._transcribe_docs_audio(path, recording_id)
            if not transcript:
                self._emit(
                    "docs.status",
                    {"state": "error", "recording_id": recording_id, "message": "Docs transcription failed."},
                )
                return

            estimated_calls = GroqDocumentationGenerator.estimate_calls(len(transcript), docs_model)
            self._emit(
                "docs.status",
                {
                    "state": "summarizing",
                    "phase": "summarizing",
                    "percent": 90,
                    "recording_id": recording_id,
                    "model": docs_model,
                    "model_label": DOCS_MODEL_PROFILES[docs_model]["label"],
                    "detail": docs_detail,
                    "detail_label": DOCS_DETAIL_PROFILES[docs_detail]["label"],
                    "output_language": docs_output_language,
                    "output_language_label": DOCS_OUTPUT_LANGUAGES[docs_output_language]["label"],
                    "estimated_calls": estimated_calls,
                    "transcript_chars": len(transcript),
                    "message": f"Creating {DOCS_DETAIL_PROFILES[docs_detail]['label']} Markdown in {DOCS_OUTPUT_LANGUAGES[docs_output_language]['label']} with {DOCS_MODEL_PROFILES[docs_model]['label']} ({estimated_calls} request estimate).",
                },
            )
            generator = GroqDocumentationGenerator(
                self.config.get_api_key() or "",
                model=docs_model,
                detail=docs_detail,
                on_progress=lambda payload: self._emit_docs_generation_progress(recording_id, payload),
            )
            result = generator.generate(transcript, source_name=path.name, language=docs_output_language)
            self._emit(
                "docs.progress",
                {
                    "phase": "writing",
                    "percent": 99,
                    "current": result.calls,
                    "total": max(result.calls, 1),
                    "model_calls_completed": result.calls,
                    "model_calls_total": max(result.calls, 1),
                    "recording_id": recording_id,
                    "message": "Writing Markdown file.",
                },
            )
            self._write_markdown_atomic(output_path, result.markdown)
        except DocumentationError as exc:
            self._emit("docs.status", {"state": "error", "recording_id": recording_id, "message": str(exc)})
            self._emit("toast", {"type": "error", "message": f"Docs failed: {exc}"})
            return
        except Exception as exc:
            self._emit("docs.status", {"state": "error", "recording_id": recording_id, "message": str(exc)})
            self._emit("toast", {"type": "error", "message": f"Docs failed: {exc}"})
            return

        self._emit(
            "docs.status",
            {
                "state": "complete",
                "phase": "complete",
                "percent": 100,
                "recording_id": recording_id,
                "display_path": str(output_path),
                "model": result.model,
                "detail": result.detail,
                "output_language": docs_output_language,
                "output_language_label": DOCS_OUTPUT_LANGUAGES[docs_output_language]["label"],
                "calls": result.calls,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "total_tokens": result.total_tokens,
                "message": f"Markdown document ready. Docs model calls: {result.calls}.",
            },
        )
        self._emit("toast", {"type": "success", "message": "Docs markdown ready."})

    def _transcribe_docs_audio(self, path: Path, recording_id: str) -> str | None:
        metadata = self._duration_metadata(path)
        if metadata["should_split"]:
            return self._transcribe_docs_split(path, recording_id)

        transcriber = self._create_transcriber(translate=self.config.translate_enabled())
        if not transcriber:
            message = (
                "API key missing. Save GROQ_API_KEY from Settings and try again."
                if self.config.get_transcription_provider() == "groq"
                else "Local Whisper is not available. Check Settings."
            )
            self._mark_transcription_error(recording_id, message)
            self._emit("toast", {"type": "error", "message": message})
            return None

        language = self.config.get_language()
        if language == "auto":
            language = None
        cleanup_result = self._prepare_audio_for_transcription(str(path))
        try:
            text = transcriber.transcribe(cleanup_result.path, language=language, translate=self.config.translate_enabled())
        finally:
            if cleanup_result.cleanup_required:
                cleanup_audio_file(cleanup_result.path)
        if not text:
            self._mark_transcription_error(recording_id, transcriber.last_error or "Transcription failed.")
            return None
        self.history.update_transcript(recording_id, text)
        self._emit_history()
        return text

    def _transcribe_docs_split(self, path: Path, recording_id: str) -> str | None:
        self._emit("docs.status", {"state": "splitting", "phase": "splitting", "percent": 10, "recording_id": recording_id, "message": "Splitting long file."})
        job_metadata = AudioSplitter(temp_dir=str(Config.get_temp_dir())).split(str(path), recording_id)
        self._track_split_artifacts(job_metadata)
        chunks = job_metadata.get("chunks", [])
        self._emit(
            "docs.status",
            {
                "state": "split_complete",
                "phase": "transcribing",
                "percent": 18,
                "recording_id": recording_id,
                "total_parts": len(chunks),
                "message": f"Split complete: {len(chunks)} parts.",
            },
        )
        transcriber = self._create_transcriber(translate=self.config.translate_enabled())
        if not transcriber:
            message = (
                "API key missing. Save GROQ_API_KEY from Settings and retry."
                if self.config.get_transcription_provider() == "groq"
                else "Local Whisper is not available. Check Settings."
            )
            self._mark_transcription_error(recording_id, message)
            return None

        language = self.config.get_language()
        if language == "auto":
            language = None
        parts: list[str] = []
        failed_parts: list[int] = []
        for index, chunk_info in enumerate(chunks):
            part = int(chunk_info["part"])
            chunk_path = Config.get_temp_dir() / chunk_info["filename"]
            self._emit(
                "docs.progress",
                {
                    "phase": "transcribing",
                    "percent": min(88, 18 + int(((index + 1) / max(len(chunks), 1)) * 68)),
                    "current": index + 1,
                    "total": len(chunks),
                    "recording_id": recording_id,
                    "message": f"Docs transcription: {index + 1}/{len(chunks)}",
                },
            )
            if self.config.get_transcription_provider() == "groq" and chunk_path.stat().st_size / (1024 * 1024) >= self._GROQ_MAX_FILE_MB:
                failed_parts.append(part)
                continue
            cleanup_result = self._prepare_audio_for_transcription(str(chunk_path))
            try:
                text = transcriber.transcribe(cleanup_result.path, language=language, translate=self.config.translate_enabled())
            finally:
                if cleanup_result.cleanup_required:
                    cleanup_audio_file(cleanup_result.path)
            if text:
                parts.append(f"[Part {part}]\n{text}")
            else:
                failed_parts.append(part)

        if not parts:
            self._mark_transcription_error(recording_id, "All split parts failed.")
            return None
        transcript = "\n\n".join(parts)
        if failed_parts:
            transcript += "\n\n[Errors]\n" + "\n".join(f"Part {part} failed." for part in failed_parts)
            self._emit(
                "docs.status",
                {
                    "state": "warning",
                    "phase": "transcribing",
                    "recording_id": recording_id,
                    "failed_parts": failed_parts,
                    "message": f"Continuing with partial transcript; failed parts: {', '.join(str(part) for part in failed_parts)}.",
                },
            )
        self.history.update_transcript(recording_id, transcript)
        self._emit_history()
        return transcript

    def _docs_file_from_token(self, token: str) -> Path:
        if not isinstance(token, str) or not token:
            raise BackendValidationError("Invalid file token")
        path = self._selected_docs_files.get(token)
        if path is None:
            raise BackendValidationError("File must be selected from the app before use")
        if not path.exists() or not path.is_file():
            raise BackendValidationError("File does not exist")
        return path

    def _emit_docs_generation_progress(self, recording_id: str, payload: dict[str, Any]) -> None:
        current = int(payload.get("current") or 0)
        total = max(1, int(payload.get("total") or 1))
        percent = min(98, 90 + int((current / total) * 8))
        phase = str(payload.get("phase") or "summarizing")
        message = "Finalizing Markdown." if phase == "final" else f"Summarizing transcript: {current}/{total}"
        self._emit(
            "docs.progress",
            {
                "phase": "summarizing",
                "percent": percent,
                "current": current,
                "total": total,
                "model_calls_completed": current,
                "model_calls_total": total,
                "recording_id": recording_id,
                "message": message,
            },
        )

    def _resolve_docs_output_language(self, output_language: str | None) -> str:
        language = str(output_language or "").strip().lower()
        if not language:
            language = str(self.config.get_language() or DEFAULT_DOCS_OUTPUT_LANGUAGE).strip().lower()
            if language == "auto":
                language = DEFAULT_DOCS_OUTPUT_LANGUAGE
        return language

    @staticmethod
    def _write_markdown_atomic(output_path: Path, markdown: str) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_path.with_name(f".{output_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temp_path.write_text(markdown, encoding="utf-8")
            temp_path.replace(output_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()
