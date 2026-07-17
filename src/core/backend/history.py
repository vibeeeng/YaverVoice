"""History-domain behavior for BackendService."""

from __future__ import annotations

from typing import Any

from src.core.backend.common import BackendValidationError
from src.models.recording import SourceType


class HistoryMixin:
    def list_history(self) -> list[dict[str, Any]]:
        """Return current-session history in the renderer-compatible shape."""
        return [
            {
                "id": recording.id,
                "timestamp": recording.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "text": recording.transcript if recording.transcribed else "Processing...",
                "transcribed": recording.transcribed,
                "is_split": recording.is_split,
                "chunk_part": recording.chunk_part,
                "parent_recording_id": recording.parent_recording_id,
            }
            for recording in self.history.get_recordings()
        ]

    def clear_history(self) -> dict[str, Any]:
        self.history.clear_all()
        return self._history_result(True)

    def update_history_text(self, recording_id: str, text: str) -> dict[str, Any]:
        if not self._recording_exists(recording_id) or not isinstance(text, str):
            raise BackendValidationError("Invalid history update")
        self.history.update_transcript(recording_id, text)
        return self._history_result(True)

    def delete_history_item(self, recording_id: str) -> dict[str, Any]:
        if not self._recording_exists(recording_id):
            raise BackendValidationError("Invalid recording id")
        return self._history_result(self.history.delete_recording(recording_id))

    def create_merged_history_entry(self, text: str) -> dict[str, Any]:
        if not isinstance(text, str) or not text.strip():
            raise BackendValidationError("Merged text cannot be empty")
        recording_id = self.history.add_recording("merged", source=SourceType.FILE)
        self.history.update_transcript(recording_id, text)
        result = self._history_result(True)
        result["id"] = recording_id
        return result

    def copy_to_clipboard(self, text: str) -> dict[str, bool]:
        if not isinstance(text, str):
            raise BackendValidationError("Clipboard text must be a string")
        return {"success": self.injector.copy_to_clipboard(text)}

    def _emit_history(self) -> list[dict[str, Any]]:
        history = self.list_history()
        self._emit("history.updated", {"history": history})
        return history

    def _history_result(self, success: bool) -> dict[str, Any]:
        history = self.list_history()
        self._emit("history.updated", {"history": history})
        return {"success": success, "history": history}
