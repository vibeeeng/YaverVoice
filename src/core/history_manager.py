"""
History Manager for YaverVoice.
Manages in-memory recording history during app session.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from src.models.recording import Recording, SourceType


class HistoryManager:
    """
    Manages recording history for the current session.

    Recordings are stored in memory during the session.
    Files are cleaned up on app shutdown.
    """

    def __init__(self):
        """Initialize empty history."""
        self._recordings: dict[str, Recording] = {}
        self._recording_counter = 0  # Counter for unique recording IDs

    def add_recording(self, filepath: str, source: SourceType = SourceType.RECORDING) -> str:
        """
        Add a recording to history.

        Args:
            filepath: Path to the audio file.
            source: Whether this is from recording or file upload.

        Returns:
            The recording ID (timestamp with counter).
        """
        # Use timestamp + counter to ensure unique IDs even for rapid additions
        import time
        timestamp_ms = int(time.time() * 1000)
        recording_id = f"{timestamp_ms}_{self._recording_counter}"
        self._recording_counter += 1

        recording = Recording(
            id=recording_id,
            filepath=filepath,
            created_at=datetime.now(),
            transcribed=False,
            transcript=None,
            source=source
        )
        self._recordings[recording_id] = recording
        return recording_id

    def get_recordings(self) -> list[Recording]:
        """
        Get all recordings with newest entries first and split parts in transcript order.

        Returns:
            List of recordings with split jobs kept as ordered groups.
        """
        entries: list[tuple[datetime, int, list[Recording]]] = []
        split_groups: dict[str, list[tuple[int, Recording]]] = {}

        for order, recording in enumerate(self._recordings.values()):
            split_group_id = recording.parent_recording_id or recording.chunk_job_id
            if recording.is_split and split_group_id:
                split_groups.setdefault(split_group_id, []).append((order, recording))
            else:
                entries.append((recording.created_at, order, [recording]))

        for group in split_groups.values():
            recordings = [recording for _, recording in group]
            recordings.sort(key=lambda recording: (recording.chunk_part is None, recording.chunk_part or 0))
            entries.append(
                (
                    max(recording.created_at for recording in recordings),
                    max(order for order, _ in group),
                    recordings,
                )
            )

        entries.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
        return [recording for _, _, recordings in entries for recording in recordings]

    def get_recording(self, recording_id: str) -> Recording | None:
        """
        Get a specific recording by ID.

        Args:
            recording_id: The recording ID.

        Returns:
            The Recording object, or None if not found.
        """
        return self._recordings.get(recording_id)

    def update_transcript(self, recording_id: str, text: str) -> None:
        """
        Update the transcript for a recording.

        Args:
            recording_id: The recording ID.
            text: The transcribed text.
        """
        if recording_id in self._recordings:
            self._recordings[recording_id].transcribed = True
            self._recordings[recording_id].transcript = text

    def delete_recording(self, recording_id: str) -> bool:
        """
        Delete a recording from history.

        Note: This only removes from history list.
        The actual file is deleted at app shutdown.

        Args:
            recording_id: The recording ID.

        Returns:
            True if deleted, False if not found.
        """
        if recording_id in self._recordings:
            del self._recordings[recording_id]
            return True
        return False

    def clear_all(self) -> None:
        """Clear all recordings from history."""
        self._recordings.clear()

    def get_count(self) -> int:
        """Get the number of recordings in history."""
        return len(self._recordings)

    def get_selected_ids(self, selected_state: dict[str, bool]) -> list[str]:
        """
        Get list of selected recording IDs.

        Args:
            selected_state: Dictionary mapping recording_id -> selected (bool).

        Returns:
            List of selected recording IDs.
        """
        return [rid for rid, selected in selected_state.items() if selected]

    def get_selected_recordings(self, selected_state: dict[str, bool]) -> list[Recording]:
        """
        Get list of selected Recording objects.

        Args:
            selected_state: Dictionary mapping recording_id -> selected (bool).

        Returns:
            List of selected Recording objects.
        """
        selected_ids = self.get_selected_ids(selected_state)
        return [self._recordings[rid] for rid in selected_ids if rid in self._recordings]
