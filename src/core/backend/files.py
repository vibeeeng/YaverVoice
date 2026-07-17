"""File and split workflow behavior for BackendService."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from src.config import Config
from src.core.audio_cleanup import cleanup_audio_file
from src.core.audio_splitter import AudioSplitter
from src.core.backend.common import BackendValidationError
from src.models.recording import SourceType


class FileWorkflowMixin:
    def register_selected_file(self, filepath: str, *, for_convert: bool = False) -> dict[str, Any]:
        path = self._resolve_audio_file(filepath)
        token = uuid.uuid4().hex
        registry = self._selected_convert_files if for_convert else self._selected_files
        registry[token] = path
        return self._file_metadata(token, path)

    def check_file_duration(self, token: str) -> dict[str, Any]:
        path = self._file_from_token(token, for_convert=False)
        return self._duration_metadata(path)

    def _duration_metadata(self, path: Path) -> dict[str, Any]:
        splitter = AudioSplitter(temp_dir=str(Config.get_temp_dir()))
        duration_seconds = splitter.get_audio_duration(str(path))
        file_size_mb = path.stat().st_size / (1024 * 1024)
        is_groq_provider = self.config.get_transcription_provider() == "groq"
        force_split_by_size = is_groq_provider and file_size_mb > self._GROQ_MAX_FILE_MB
        if duration_seconds == 0 and file_size_mb > 10:
            force_split_by_size = True
        return {
            "duration_seconds": duration_seconds,
            "duration_minutes": duration_seconds / 60 if duration_seconds > 0 else 0,
            "should_split": duration_seconds > self._SPLIT_THRESHOLD_SECONDS or force_split_by_size,
            "threshold_seconds": self._SPLIT_THRESHOLD_SECONDS,
            "file_size_mb": file_size_mb,
            "force_split_by_size": force_split_by_size,
            "provider": self.config.get_transcription_provider(),
        }

    def transcribe_file(self, token: str) -> dict[str, Any]:
        path = self._file_from_token(token, for_convert=False)
        self._emit("file.status", {"state": "processing", "file": self._file_metadata(token, path)})
        recording_id = self.history.add_recording(str(path), source=SourceType.FILE)
        self._emit_history()
        self._start_daemon_thread(
            "sidecar-file-transcription",
            self._finish_file_transcription,
            recording_id,
        )
        return {
            "success": True,
            "accepted": True,
            "id": recording_id,
            "message": "Transcription started.",
            "history": self.list_history(),
        }

    def _finish_file_transcription(self, recording_id: str) -> None:
        try:
            success = self._transcribe_recording(recording_id, mode="file")
        except Exception as exc:
            success = False
            self._mark_transcription_error(recording_id, str(exc))
        message = "Transcript ready." if success else "Transcription failed."
        self._emit(
            "file.status",
            {
                "state": "complete" if success else "error",
                "recording_id": recording_id,
                "message": message,
            },
        )

    def save_transcript(self, text: str, output_path: str) -> dict[str, Any]:
        if not isinstance(text, str):
            raise BackendValidationError("Transcript text must be a string")
        path = Path(str(output_path)).expanduser().resolve()
        if path.suffix.lower() != ".txt":
            path = path.with_suffix(".txt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return {"success": True, "display_path": str(path)}

    def start_split_workflow(self, token: str) -> dict[str, Any]:
        path = self._file_from_token(token, for_convert=False)
        recording_id = str(int(time.time() * 1000))
        self._emit("split.step", {"state": "splitting", "recording_id": recording_id})
        self._start_daemon_thread(
            "sidecar-split-transcription",
            self._finish_split_workflow,
            path,
            recording_id,
        )
        return {
            "success": True,
            "accepted": True,
            "recording_id": recording_id,
            "success_count": 0,
            "failed_chunks": [],
            "message": "Split workflow started.",
            "history": self.list_history(),
        }

    def _finish_split_workflow(self, path: Path, recording_id: str) -> None:
        try:
            job_metadata = AudioSplitter(temp_dir=str(Config.get_temp_dir())).split(str(path), recording_id)
            self._track_split_artifacts(job_metadata)
            self._emit("split.step", {
                "state": "split_complete",
                "recording_id": recording_id,
                "total_parts": job_metadata["total_parts"],
            })
            chunks = self._create_split_history_entries(recording_id, job_metadata)
            self._emit_history()
            success_count, failed_chunks = self._transcribe_chunks(chunks)
        except Exception as exc:
            self._emit("split.step", {"state": "error", "message": str(exc), "recording_id": recording_id})
            return
        total_parts = len(chunks)
        if failed_chunks:
            message = f"Transcript finished with errors: {success_count}/{total_parts} parts completed."
            toast_type = "warning"
        else:
            message = f"Transcript ready: {success_count} parts completed."
            toast_type = "success"
        self._emit("split.step", {
            "state": "complete",
            "recording_id": recording_id,
            "success_count": success_count,
            "failed_chunks": failed_chunks,
            "total_parts": total_parts,
            "message": message,
        })
        self._emit("toast", {"type": toast_type, "message": message})

    def _create_split_history_entries(self, recording_id: str, job_metadata: dict[str, Any]) -> list[dict[str, Any]]:
        chunks = []
        self._track_split_artifacts(job_metadata)
        for chunk_info in job_metadata["chunks"]:
            chunk_path = str(Config.get_temp_dir() / chunk_info["filename"])
            chunk_recording_id = self.history.add_recording(filepath=chunk_path, source=SourceType.FILE)
            recording = self.history.get_recording(chunk_recording_id)
            if recording:
                recording.is_split = True
                recording.chunk_part = chunk_info["part"]
                recording.parent_recording_id = recording_id
            chunks.append({"id": chunk_recording_id, "part": chunk_info["part"], "path": chunk_path})
        return chunks

    def _track_split_artifacts(self, job_metadata: dict[str, Any]) -> None:
        temp_dir = Config.get_temp_dir()
        for chunk in job_metadata.get("chunks", []):
            filename = chunk.get("filename")
            if isinstance(filename, str) and filename:
                self._session_temp_files.add(temp_dir / filename)
        recording_id = job_metadata.get("original_recording_id")
        if isinstance(recording_id, str) and recording_id:
            self._session_temp_files.add(temp_dir / f"{recording_id}_job_meta.json")
            self._session_temp_files.add(temp_dir / f"{recording_id}_converted.wav")

    def _transcribe_chunks(self, chunks: list[dict[str, Any]]) -> tuple[int, list[int]]:
        language = self.config.get_language()
        if language == "auto":
            language = None
        translate = self.config.translate_enabled()
        transcriber = self._create_transcriber(translate=translate)
        if not transcriber:
            message = (
                "API key missing. Save GROQ_API_KEY from Settings and retry."
                if self.config.get_transcription_provider() == "groq"
                else "Local Whisper is not available. Check Settings."
            )
            for chunk in chunks:
                self._mark_transcription_error(chunk["id"], message)
            return 0, [int(chunk["part"]) for chunk in chunks]

        success_count = 0
        failed_chunks: list[int] = []
        for index, chunk in enumerate(chunks):
            chunk_path = Path(chunk["path"])
            self._emit("split.progress", {
                "current": index + 1,
                "total": len(chunks),
                "recording_id": chunk["id"],
            })
            if self.config.get_transcription_provider() == "groq" and chunk_path.stat().st_size / (1024 * 1024) >= self._GROQ_MAX_FILE_MB:
                failed_chunks.append(int(chunk["part"]))
                self._mark_transcription_error(chunk["id"], "Chunk is too large for Groq API.")
                continue
            cleanup_result = self._prepare_audio_for_transcription(str(chunk_path))
            try:
                text = transcriber.transcribe(cleanup_result.path, language=language, translate=translate)
            finally:
                if cleanup_result.cleanup_required:
                    cleanup_audio_file(cleanup_result.path)
            if text:
                self.history.update_transcript(chunk["id"], text)
                success_count += 1
                self._emit_history()
            else:
                failed_chunks.append(int(chunk["part"]))
                self._mark_transcription_error(chunk["id"], transcriber.last_error or "Transcription failed.")
        return success_count, failed_chunks

    def _resolve_audio_file(self, filepath: str) -> Path:
        if not isinstance(filepath, str) or not filepath:
            raise BackendValidationError("Invalid file path")
        path = Path(filepath).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise BackendValidationError("File does not exist")
        if path.suffix.lower() not in self._ALLOWED_AUDIO_EXTENSIONS:
            raise BackendValidationError(f"Unsupported file extension: {path.suffix}")
        return path

    def _file_from_token(self, token: str, *, for_convert: bool) -> Path:
        if not isinstance(token, str) or not token:
            raise BackendValidationError("Invalid file token")
        registry = self._selected_convert_files if for_convert else self._selected_files
        path = registry.get(token)
        if path is None:
            raise BackendValidationError("File must be selected from the app before use")
        if not path.exists() or not path.is_file():
            raise BackendValidationError("File does not exist")
        return path

    @staticmethod
    def _file_metadata(token: str, path: Path) -> dict[str, Any]:
        return {
            "token": token,
            "name": path.name,
            "extension": path.suffix.lower(),
            "size_bytes": path.stat().st_size,
            "size_mb": path.stat().st_size / (1024 * 1024),
            "display_path": str(path),
        }
