"""
Recording data model for YaverVoice.
Represents a single audio recording with its transcription state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class SourceType(str, Enum):
    """Source of the audio file."""
    RECORDING = "recording"  # Made via app's recording feature
    FILE = "file"            # Uploaded from external file


@dataclass
class Recording:
    """
    Represents a single audio recording or file upload.

    Attributes:
        id: Unique identifier (timestamp as string).
        filepath: Path to the audio file.
        created_at: When the recording was created.
        transcribed: Whether transcription is complete.
        transcript: Transcribed text (None if not transcribed).
        source: Whether this is from recording or file upload.
        is_split: True if this recording is a chunk from a split file.
        chunk_job_id: ID of the split job (original recording ID).
        chunk_part: Part number if this is a chunk (1, 2, 3...).
        parent_recording_id: Parent ID if this is a chunk.
    """
    id: str
    filepath: str
    created_at: datetime
    transcribed: bool = False
    transcript: str | None = None
    source: SourceType = SourceType.RECORDING  # Default to RECORDING for backward compatibility

    # Chunk metadata (for split files)
    is_split: bool = False  # True if this recording is a chunk from a split file
    chunk_job_id: str | None = None  # ID of the split job (original recording ID)
    chunk_part: int | None = None  # Part number if this is a chunk (1, 2, 3...)
    parent_recording_id: str | None = None  # Parent ID if this is a chunk

    @property
    def filename(self) -> str:
        """Get the filename from filepath."""
        return Path(self.filepath).name

    @property
    def file_size(self) -> int:
        """Get file size in bytes."""
        return Path(self.filepath).stat().st_size if Path(self.filepath).exists() else 0

    @property
    def file_size_mb(self) -> float:
        """Get file size in megabytes."""
        return self.file_size / (1024 * 1024)

    @property
    def file_size_kb(self) -> float:
        """Get file size in kilobytes."""
        return self.file_size / 1024

    @property
    def transcript_preview(self, max_length: int = 50) -> str:
        """
        Get a preview of the transcript text.

        Args:
            max_length: Maximum length of preview.

        Returns:
            Truncated transcript with ellipsis if needed.
        """
        if not self.transcript:
            return ""

        if len(self.transcript) <= max_length:
            return self.transcript

        return self.transcript[:max_length] + "..."
