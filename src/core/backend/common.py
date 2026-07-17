"""Common validation and managed-temp cleanup primitives."""

from __future__ import annotations

import time
from pathlib import Path


class BackendValidationError(ValueError):
    """Raised when sidecar-facing params are invalid."""


TEMP_ARTIFACT_PATTERNS = (
    "recording_*.wav",
    "preview_*.wav",
    "upload_*.wav",
    "cleanup_*.wav",
    "*_converted.wav",
    "*_???_part.wav",
    "*_???_part.mp3",
    "*_job_meta.json",
)


def cleanup_stale_temp_files(temp_dir: Path, *, now: float | None = None, max_age_seconds: int = 24 * 60 * 60) -> None:
    """Remove only known YaverVoice temp artifacts left by an old process."""
    cutoff = (time.time() if now is None else now) - max_age_seconds
    for pattern in TEMP_ARTIFACT_PATTERNS:
        for path in temp_dir.glob(pattern):
            try:
                if path.is_file() and path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError as exc:
                print(f"[BackendService] Could not remove stale temp file {path}: {exc}")
