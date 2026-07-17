"""
Audio Splitter Module - Splits long audio files into chunks for transcription
"""

from pathlib import Path
from typing import Dict, Any, Optional
import json
from datetime import datetime
import numpy as np

from .ffmpeg_utils import (
    is_ffmpeg_available,
    convert_to_wav,
    get_duration_ffprobe,
    needs_ffmpeg_conversion,
    FFMPEG_REQUIRED_FORMATS
)


class AudioSplitter:
    """Split audio files into overlapping chunks for safe API transcription."""

    # Constants
    CHUNK_DURATION_SECONDS = 240  # 4 minutes (reduced from 10 to stay under 25MB)
    OVERLAP_SECONDS = 3
    MAX_PART_DURATION_SECONDS = 900  # 15 minutes (API safety)

    def __init__(self, temp_dir: str = "temp"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_audio_duration(self, filepath: str) -> float:
        """Get audio duration in seconds."""
        try:
            from tinytag import TinyTag

            duration = float(TinyTag.get(filepath).duration or 0)
            if duration > 0:
                return duration
        except Exception:
            pass

        # Fallback to soundfile for formats supported by libsndfile.
        try:
            import soundfile as sf

            with sf.SoundFile(filepath) as audio_file:
                frames = len(audio_file)
                samplerate = audio_file.samplerate
                return frames / samplerate
        except Exception:
            pass

        # Final fallback: use ffprobe if available
        duration = get_duration_ffprobe(filepath)
        if duration is not None:
            return duration

        print(f"[WARNING] Could not determine duration for: {filepath}")
        return 0.0

    def should_split(self, filepath: str, threshold_seconds: int = 600) -> bool:
        """Check if audio file should be split (duration > threshold)."""
        duration_seconds = self.get_audio_duration(filepath)
        return duration_seconds > threshold_seconds

    def split(self, filepath: str, recording_id: str) -> Dict[str, Any]:
        """
        Split audio file into chunks.

        Args:
            filepath: Path to original audio file
            recording_id: Original recording ID for naming

        Returns:
            Dict with job metadata
        """
        import soundfile as sf
        import wave

        file_ext = Path(filepath).suffix.lower()
        original_filepath = filepath
        converted_temp_file: Optional[Path] = None

        # Check if format needs FFmpeg conversion
        if needs_ffmpeg_conversion(filepath):
            if not is_ffmpeg_available():
                raise ValueError(
                    f"Bu format ({file_ext}) için FFmpeg gerekli. "
                    f"Kurulum: ffmpeg.org/download.html"
                )

            # Convert to temp WAV file
            converted_temp_file = self.temp_dir / f"{recording_id}_converted.wav"
            success, error_msg = convert_to_wav(filepath, str(converted_temp_file))

            if not success:
                raise ValueError(f"Format dönüştürme hatası: {error_msg}")

            filepath = str(converted_temp_file)
            print(f"[INFO] Converted {file_ext} to WAV for processing")

        # Read the audio file
        try:
            with sf.SoundFile(filepath) as audio_file:
                samplerate = audio_file.samplerate
                total_frames = len(audio_file)
                audio_data = audio_file.read(dtype="float32")
        except Exception as e:
            # Clean up converted file if it exists
            if converted_temp_file and converted_temp_file.exists():
                converted_temp_file.unlink()
            raise ValueError(f"Dosya okunamadı. Hata: {e}")

        # Convert to mono if stereo
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=1)

        # Calculate durations
        total_duration_seconds = total_frames / samplerate
        chunk_frames = int(self.CHUNK_DURATION_SECONDS * samplerate)
        overlap_frames = int(self.OVERLAP_SECONDS * samplerate)

        chunks = []
        part_number = 1
        current_frame = 0

        while current_frame < total_frames:
            end_frame = min(current_frame + chunk_frames, total_frames)

            # Calculate actual chunk duration
            part_duration_frames = end_frame - current_frame
            part_duration_seconds = part_duration_frames / samplerate

            # Skip if chunk is too small (less than 1 second or too much overlap)
            if part_duration_seconds < 1.0:
                break

            # Check max duration
            if part_duration_seconds > self.MAX_PART_DURATION_SECONDS:
                raise ValueError(
                    f"Part {part_number} exceeds max duration: {part_duration_seconds}s"
                )

            # Extract chunk
            chunk_data = audio_data[current_frame:end_frame]

            # Write chunk - use MP3 if FFmpeg available, otherwise WAV
            chunk_data_int16 = (chunk_data * 32767).astype(np.int16)

            # Always write WAV first (required for processing)
            temp_wav_filename = f"{Path(filepath).stem}_{part_number:03d}_part.wav"
            temp_wav_path = self.temp_dir / temp_wav_filename

            with wave.open(str(temp_wav_path), "w") as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(samplerate)
                wav_file.writeframes(chunk_data_int16.tobytes())

            # Convert to MP3 if FFmpeg available (saves ~50% disk space)
            if is_ffmpeg_available():
                from .ffmpeg_utils import convert_wav_to_mp3
                mp3_filename = f"{Path(filepath).stem}_{part_number:03d}_part.mp3"
                mp3_path = self.temp_dir / mp3_filename

                success, _ = convert_wav_to_mp3(str(temp_wav_path), str(mp3_path))
                if success:
                    # Delete WAV, keep MP3
                    temp_wav_path.unlink()
                    chunk_filename = mp3_filename
                    chunk_path = mp3_path
                else:
                    # Fallback to WAV if conversion fails
                    chunk_filename = temp_wav_filename
                    chunk_path = temp_wav_path
            else:
                chunk_filename = temp_wav_filename
                chunk_path = temp_wav_path

            current_start_seconds = current_frame / samplerate
            current_end_seconds = end_frame / samplerate

            chunks.append(
                {
                    "part": part_number,
                    "filename": chunk_filename,
                    "start_ms": int(current_start_seconds * 1000),
                    "end_ms": int(current_end_seconds * 1000),
                    "start_seconds": current_start_seconds,
                    "end_seconds": current_end_seconds,
                }
            )

            # Move to next chunk (with overlap)
            # CRITICAL: If we reached the end, break to prevent infinite loop
            if end_frame >= total_frames:
                break

            current_frame = end_frame - overlap_frames

            # Safety: If we're not making progress, break
            if current_frame >= end_frame:
                break

            part_number += 1

        # Create job metadata
        job_metadata = {
            "total_parts": len(chunks),
            "chunk_duration_seconds": self.CHUNK_DURATION_SECONDS,
            "overlap_seconds": self.OVERLAP_SECONDS,
            "created_at": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "original_filename": Path(filepath).name,
            "original_recording_id": recording_id,
            "chunks": chunks,
        }

        # Save job_meta.json
        meta_path = self.temp_dir / f"{recording_id}_job_meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(job_metadata, f, indent=2, ensure_ascii=False)

        return job_metadata
