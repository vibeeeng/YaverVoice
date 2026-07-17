"""Optional FFmpeg-backed cleanup before transcription."""

from __future__ import annotations

import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from src.core.ffmpeg_utils import get_ffmpeg_path, is_ffmpeg_available


VALID_AUDIO_CLEANUP_MODES = {"off", "normal", "noisy", "severe"}
LOUDNORM_FILTER = "loudnorm=I=-18:TP=-1.5:LRA=11"


def normalize_audio_cleanup_mode(mode: str | None) -> str:
    """Return a supported cleanup preset name."""
    value = str(mode or "off").strip().lower()
    return value if value in VALID_AUDIO_CLEANUP_MODES else "off"


def resolve_rnnoise_model_path(model_path: str | Path | None) -> str | None:
    """Return an existing RNNoise model path, or None when unavailable."""
    if not model_path:
        return None
    path = Path(model_path).expanduser()
    if path.exists() and path.is_file():
        return str(path)
    return None


def escape_filter_path(path: str) -> str:
    """Escape a filesystem path for use inside an FFmpeg filter argument."""
    return path.replace("\\", "/").replace(":", "\\:")


def build_cleanup_filter(mode: str, rnnoise_model_path: str | Path | None = None) -> tuple[str | None, str | None]:
    """
    Build the FFmpeg audio filter chain for a cleanup preset.

    Returns (filter_chain, fallback_reason). fallback_reason is set when a noisy
    preset requested RNNoise but the model path is unavailable.
    """
    normalized = normalize_audio_cleanup_mode(mode)
    rnnoise_model = resolve_rnnoise_model_path(rnnoise_model_path)
    fallback_reason = None

    if normalized == "off":
        return None, None
    if normalized == "normal":
        return f"highpass=f=80,lowpass=f=7600,{LOUDNORM_FILTER}", None
    if normalized == "noisy":
        if rnnoise_model:
            return f"arnndn=m={escape_filter_path(rnnoise_model)},{LOUDNORM_FILTER}", None
        if rnnoise_model_path:
            fallback_reason = "RNNoise model is not available; using spectral noise reduction"
        return f"afftdn=nf=-25,{LOUDNORM_FILTER}", fallback_reason
    if normalized == "severe":
        if rnnoise_model:
            return f"arnndn=m={escape_filter_path(rnnoise_model)},highpass=f=80,lowpass=f=7600,{LOUDNORM_FILTER}", None
        if rnnoise_model_path:
            fallback_reason = "RNNoise model is not available; using spectral noise reduction"
        return f"afftdn=nf=-30,highpass=f=80,lowpass=f=7600,{LOUDNORM_FILTER}", fallback_reason

    return None, None


@dataclass(frozen=True)
class AudioCleanupResult:
    """Result of preparing an audio file for transcription."""

    path: str
    cleanup_required: bool = False
    skipped_reason: str | None = None


def prepare_audio_for_transcription(
    audio_file_path: str,
    *,
    mode: str | None = None,
    temp_dir: Path,
    rnnoise_model_path: str | Path | None = None,
    enabled: bool | None = None,
) -> AudioCleanupResult:
    """Return a cleaned temp WAV path when cleanup is enabled and FFmpeg works."""
    cleanup_mode = normalize_audio_cleanup_mode(mode if mode is not None else ("noisy" if enabled else "off"))
    if cleanup_mode == "off":
        return AudioCleanupResult(path=audio_file_path)

    cleanup_filter, filter_fallback_reason = build_cleanup_filter(cleanup_mode, rnnoise_model_path)
    if not cleanup_filter:
        return AudioCleanupResult(path=audio_file_path)

    source_path = Path(audio_file_path)
    if not source_path.exists():
        return AudioCleanupResult(path=audio_file_path, skipped_reason="source file is missing")

    if not is_ffmpeg_available():
        return AudioCleanupResult(path=audio_file_path, skipped_reason="FFmpeg is not available")

    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        return AudioCleanupResult(path=audio_file_path, skipped_reason="FFmpeg is not available")

    temp_dir.mkdir(parents=True, exist_ok=True)
    output_path = temp_dir / f"cleanup_{source_path.stem}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}.wav"
    cmd = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-af",
        cleanup_filter,
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=600)
    except subprocess.TimeoutExpired:
        cleanup_audio_file(output_path)
        return AudioCleanupResult(path=audio_file_path, skipped_reason="FFmpeg cleanup timed out")
    except Exception as exc:
        cleanup_audio_file(output_path)
        return AudioCleanupResult(path=audio_file_path, skipped_reason=f"FFmpeg cleanup failed: {exc}")

    if result.returncode != 0:
        cleanup_audio_file(output_path)
        stderr = result.stderr.decode("utf-8", errors="ignore").strip()
        detail = stderr[:200] if stderr else "unknown FFmpeg error"
        return AudioCleanupResult(path=audio_file_path, skipped_reason=f"FFmpeg cleanup failed: {detail}")

    if not output_path.exists() or output_path.stat().st_size == 0:
        cleanup_audio_file(output_path)
        return AudioCleanupResult(path=audio_file_path, skipped_reason="FFmpeg cleanup produced no output")

    return AudioCleanupResult(path=str(output_path), cleanup_required=True, skipped_reason=filter_fallback_reason)


def cleanup_audio_file(audio_file_path: str | Path) -> None:
    """Delete a generated cleanup copy after it is no longer needed."""
    path = Path(audio_file_path)
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        print(f"[AudioCleanup] Could not delete temporary file {path}: {exc}")
