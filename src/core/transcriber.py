"""
Groq Transcriber Module - Speech-to-text conversion using Groq API.
Uses whisper-large-v3-turbo model for low-latency transcription.
"""

import os
import sys
import threading
import time
import wave
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Callable, Optional, Protocol
from groq import Groq
import numpy as np

from src.config import Config


class Transcriber(Protocol):
    """Common transcription provider interface."""

    last_error: Optional[str]

    def transcribe(self, audio_file_path: str, language: Optional[str] = "tr", translate: bool = False) -> Optional[str]:
        ...


class GroqTranscriber:
    """
    Transcribes audio files using Groq's Whisper API.

    Features:
    - Uses whisper-large-v3-turbo model (fast transcription)
    - Automatic API key loading from .env
    - Retry logic for network failures
    - Turkish language support
    - Error handling for invalid API keys
    """

    # Groq models to use
    FINAL_MODEL = "whisper-large-v3-turbo"
    PREVIEW_MODEL = "whisper-large-v3-turbo"
    TRANSLATION_MODEL = "whisper-large-v3"
    TRANSCRIPTION_SAMPLE_RATE = 16000

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0  # seconds
    PREVIEW_TIMEOUT_SECONDS = 2.0
    PREVIEW_MAX_RETRIES = 0

    # Groq API file size limit (25 MB)
    MAX_FILE_SIZE_MB = 25
    WARNING_THRESHOLD_MB = 20  # Warn at 20 MB

    def __init__(self, api_key: Optional[str] = None, temp_dir: Optional[Path] = None):
        """
        Initialize the Groq transcriber.

        Args:
            api_key: Groq API key (if None, loads from Config)
        """
        if api_key is None:
            config = Config()
            api_key = config.get_api_key()

        if not api_key:
            raise ValueError(
                "Groq API key not found. Please set GROQ_API_KEY in .env file "
                "or pass api_key parameter."
            )

        self.api_key = api_key
        self.client = self._build_client()
        self.last_error: Optional[str] = None
        self._temp_dir = temp_dir

    def _build_client(self, timeout: float | None = None, max_retries: int | None = None) -> Groq:
        """Create a Groq client with optional request policy overrides."""
        client_kwargs = {"api_key": self.api_key}
        if timeout is not None:
            client_kwargs["timeout"] = timeout
        if max_retries is not None:
            client_kwargs["max_retries"] = max_retries
        return Groq(**client_kwargs)

    def _check_file_size(self, audio_file_path: str) -> bool:
        """
        Check audio file size against Groq API limits.

        Args:
            audio_file_path: Path to the audio file

        Returns:
            True if file size is acceptable, False if too large
        """
        file_size_bytes = Path(audio_file_path).stat().st_size
        file_size_mb = file_size_bytes / (1024 * 1024)

        print(f"[INFO] Audio file size: {file_size_mb:.2f} MB")

        if file_size_mb >= self.MAX_FILE_SIZE_MB:
            print(f"[ERROR] File too large! Groq API limit is {self.MAX_FILE_SIZE_MB} MB.")
            print(f"[ERROR] Your file is {file_size_mb:.2f} MB. Please record a shorter audio.")
            self.last_error = (
                f"Audio file exceeds Groq's {self.MAX_FILE_SIZE_MB} MB limit. "
                "Use the split workflow or a shorter recording."
            )
            return False

        if file_size_mb >= self.WARNING_THRESHOLD_MB:
            print(f"[WARNING] File is large ({file_size_mb:.2f} MB). Approaching API limit of {self.MAX_FILE_SIZE_MB} MB.")

        return True

    def get_audio_duration(self, filepath: str) -> float:
        """
        Get audio file duration in seconds.

        Args:
            filepath: Path to the audio file

        Returns:
            Duration in seconds
        """
        file_ext = Path(filepath).suffix.lower()
        print(f"[DEBUG] Getting duration for: {filepath} (format: {file_ext})")

        try:
            from tinytag import TinyTag

            duration = float(TinyTag.get(filepath).duration or 0)
            if duration > 0:
                print(f"[DEBUG] Duration from TinyTag: {duration:.2f} seconds")
                return duration
        except Exception as e:
            print(f"[DEBUG] TinyTag failed: {e}, trying soundfile...")

        # Fallback to soundfile (for wav files mainly)
        try:
            import soundfile as sf
            with sf.SoundFile(filepath) as audio_file:
                frames = len(audio_file)
                samplerate = audio_file.samplerate
                duration = frames / samplerate
                print(f"[DEBUG] Duration from soundfile: {duration:.2f} seconds")
                return duration
        except Exception as e:
            print(f"[DEBUG] soundfile failed: {e}, trying ffprobe...")

        from src.core.ffmpeg_utils import get_duration_ffprobe

        duration = get_duration_ffprobe(filepath)
        return float(duration) if duration is not None else 0.0

    def transcribe(self, audio_file_path: str, language: Optional[str] = "tr", translate: bool = False) -> Optional[str]:
        """
        Transcribe an audio file using Groq's Whisper API.

        Args:
            audio_file_path: Path to the audio file (.wav, .mp3, etc.)
            language: Language code (default: "tr" for Turkish)
            translate: If True, translate to English instead of transcribing

        Returns:
            Transcribed/translated text as string, or None if failed
        """
        self.last_error = None

        # Validate file exists
        if not Path(audio_file_path).exists():
            print(f"Error: Audio file not found: {audio_file_path}")
            self.last_error = f"Audio file not found: {audio_file_path}"
            return None

        total_start = time.perf_counter()
        upload_file_path = audio_file_path
        cleanup_upload_file = False
        try:
            upload_file_path, cleanup_upload_file = self._prepare_audio_for_upload(audio_file_path)
        except Exception as e:
            print(f"[transcribe timing] audio upload optimization skipped: {e}")

        # Check file size before attempting transcription
        if not self._check_file_size(upload_file_path):
            if cleanup_upload_file:
                self._cleanup_upload_file(upload_file_path)
            return None

        # Try transcription with retry logic
        try:
            for attempt in range(self.MAX_RETRIES):
                try:
                    result = self._transcribe_once(
                        upload_file_path,
                        language,
                        translate,
                        client=self.client,
                        model=self.TRANSLATION_MODEL if translate else self.FINAL_MODEL,
                    )
                    print(f"[transcribe timing] total={time.perf_counter() - total_start:.2f}s")
                    self.last_error = None
                    return result

                except ValueError as e:
                    self.last_error = str(e)
                    print(f"Error: {self.last_error}")
                    return None

                except Exception as e:
                    error_msg = str(e).lower()

                    # API key error - don't retry
                    if "unauthorized" in error_msg or "api key" in error_msg or "401" in error_msg:
                        print(f"Error: Invalid Groq API key. Please check your GROQ_API_KEY.")
                        self.last_error = "Invalid Groq API key. Update GROQ_API_KEY in Settings."
                        return None

                    # Network error - retry with backoff
                    if attempt < self.MAX_RETRIES - 1:
                        wait_time = self.RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                        print(f"Network error, retrying in {wait_time}s... (attempt {attempt + 1}/{self.MAX_RETRIES})")
                        time.sleep(wait_time)
                    else:
                        print(f"Error: Transcription failed after {self.MAX_RETRIES} attempts: {e}")
                        self.last_error = f"Transcription failed after {self.MAX_RETRIES} attempts: {e}"
                        return None

            return None
        finally:
            if cleanup_upload_file:
                self._cleanup_upload_file(upload_file_path)

    def _prepare_audio_for_upload(self, audio_file_path: str) -> tuple[str, bool]:
        """Create a smaller 16 kHz mono WAV upload copy when the source is PCM WAV."""
        source_path = Path(audio_file_path)
        if source_path.suffix.lower() != ".wav":
            return audio_file_path, False

        with wave.open(str(source_path), "rb") as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
            raw_audio = wav_file.readframes(frame_count)

        duration_seconds = frame_count / max(sample_rate, 1)
        original_mb = source_path.stat().st_size / (1024 * 1024)
        if channels == 1 and sample_rate == self.TRANSCRIPTION_SAMPLE_RATE:
            print(
                "[transcribe timing] upload_audio="
                f"{duration_seconds:.2f}s {original_mb:.2f}MB "
                f"{sample_rate}Hz mono already optimized"
            )
            return audio_file_path, False

        if sample_width != 2:
            print(
                "[transcribe timing] upload_audio="
                f"{duration_seconds:.2f}s {original_mb:.2f}MB "
                f"{sample_rate}Hz {channels}ch skipped; unsupported sample_width={sample_width}"
            )
            return audio_file_path, False

        audio = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32)
        if channels > 1:
            audio = audio.reshape(-1, channels).mean(axis=1)

        target_rate = self.TRANSCRIPTION_SAMPLE_RATE
        if sample_rate != target_rate and audio.size > 0:
            target_length = max(1, int(round(audio.size * target_rate / sample_rate)))
            source_positions = np.linspace(0, audio.size - 1, num=audio.size)
            target_positions = np.linspace(0, audio.size - 1, num=target_length)
            audio = np.interp(target_positions, source_positions, audio).astype(np.float32)

        optimized_audio = np.clip(audio, -32768, 32767).astype(np.int16)
        upload_path = self._get_upload_temp_dir() / f"upload_{source_path.stem}_{int(time.time() * 1000)}.wav"
        with wave.open(str(upload_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(target_rate)
            wav_file.writeframes(optimized_audio.tobytes())

        optimized_mb = upload_path.stat().st_size / (1024 * 1024)
        print(
            "[transcribe timing] upload_audio="
            f"{duration_seconds:.2f}s original={original_mb:.2f}MB "
            f"{sample_rate}Hz/{channels}ch optimized={optimized_mb:.2f}MB "
            f"{target_rate}Hz/mono"
        )
        return str(upload_path), True

    def _get_upload_temp_dir(self) -> Path:
        if self._temp_dir is not None:
            self._temp_dir.mkdir(parents=True, exist_ok=True)
            return self._temp_dir
        return Config.get_temp_dir()

    @staticmethod
    def _cleanup_upload_file(audio_file_path: str) -> None:
        try:
            Path(audio_file_path).unlink(missing_ok=True)
        except Exception as e:
            print(f"Warning: Could not delete optimized upload file {audio_file_path}: {e}")

    def transcribe_preview(
        self,
        audio_file_path: str,
        language: Optional[str] = "tr",
        translate: bool = False,
        prompt: Optional[str] = None,
    ) -> Optional[str]:
        """Transcribe a live-preview audio snapshot with low latency settings."""
        self.last_error = None

        if not Path(audio_file_path).exists():
            self.last_error = f"Audio file not found: {audio_file_path}"
            return None

        if not self._check_file_size(audio_file_path):
            return None

        preview_client = self._build_client(
            timeout=self.PREVIEW_TIMEOUT_SECONDS,
            max_retries=self.PREVIEW_MAX_RETRIES,
        )

        try:
            preview_model = self.TRANSLATION_MODEL if translate else self.PREVIEW_MODEL
            result = self._transcribe_once(
                audio_file_path,
                language,
                translate,
                client=preview_client,
                model=preview_model,
                prompt=prompt.strip() if prompt and prompt.strip() else None,
            )
            self.last_error = None
            return result
        except Exception as e:
            error_msg = str(e).lower()
            if "unauthorized" in error_msg or "api key" in error_msg or "401" in error_msg:
                self.last_error = "Invalid Groq API key. Update GROQ_API_KEY in Settings."
            else:
                self.last_error = f"Live preview failed: {e}"
            return None

    def _transcribe_once(
        self,
        audio_file_path: str,
        language: Optional[str] = "tr",
        translate: bool = False,
        client: Groq | None = None,
        model: str | None = None,
        prompt: Optional[str] = None,
    ) -> str:
        """
        Perform a single transcription/translation attempt.

        Args:
            audio_file_path: Path to the audio file
            language: Language code for transcription
            translate: If True, translate to English

        Returns:
            Transcribed or translated text

        Raises:
            Exception: If API call fails
        """
        print(f"[DEBUG] Transcriber: Processing file: {audio_file_path}")
        if client is None:
            client = self.client
        if model is None:
            model = self.FINAL_MODEL

        # Read audio file
        read_start = time.perf_counter()
        with open(audio_file_path, "rb") as audio_file:
            # Get file size for validation
            audio_file.seek(0, 2)
            file_size = audio_file.tell()
            audio_file.seek(0)

            if file_size == 0:
                raise ValueError("Audio file is empty")
            file_size_mb = file_size / (1024 * 1024)

            # Create filename for API (Groq needs the original filename)
            filename = Path(audio_file_path).name
            file_content = audio_file.read()
            print(
                "[transcribe timing] "
                f"read={time.perf_counter() - read_start:.2f}s "
                f"upload_size={file_size_mb:.2f}MB model={model}"
            )

            # Build API parameters
            api_params = {
                "file": (filename, file_content),
                "model": model,
                "response_format": "text"
            }
            if prompt:
                api_params["prompt"] = prompt

            # Use translations API if translate is True, otherwise transcriptions
            if translate:
                # Translations API converts to English (doesn't accept language param)
                api_start = time.perf_counter()
                result = client.audio.translations.create(**api_params)
            else:
                # Transcriptions API returns verbatim text
                # Only include language parameter if not None (auto-detect)
                if language is not None:
                    api_params["language"] = language
                api_start = time.perf_counter()
                result = client.audio.transcriptions.create(**api_params)

        print(f"[transcribe timing] api={time.perf_counter() - api_start:.2f}s")
        return result

    def transcribe_with_language(self, audio_file_path: str, language: str = "tr") -> Optional[str]:
        """
        Transcribe with explicit language specification.

        Args:
            audio_file_path: Path to the audio file
            language: Language code (default: "tr" for Turkish)

        Returns:
            Transcribed text, or None if failed
        """
        if not Path(audio_file_path).exists():
            print(f"Error: Audio file not found: {audio_file_path}")
            return None

        try:
            with open(audio_file_path, "rb") as audio_file:
                filename = Path(audio_file_path).name

                transcription = self.client.audio.transcriptions.create(
                    file=(filename, audio_file.read()),
                    model=self.FINAL_MODEL,
                    response_format="text",
                    language=language
                )

            return transcription

        except Exception as e:
            print(f"Transcription error: {e}")
            return None

    def test_api_key(self) -> bool:
        """
        Test if the API key is valid by making a minimal API call.

        Returns:
            True if API key is valid, False otherwise
        """
        try:
            # Try to list models (minimal API call)
            self.client.models.list()
            return True
        except Exception as e:
            error_msg = str(e).lower()
            if "unauthorized" in error_msg or "api key" in error_msg or "401" in error_msg:
                print(f"API key validation failed: {e}")
                return False
            # Other errors might be temporary network issues
            return True


class LocalWhisperTranscriber:
    """Transcribes audio files locally with faster-whisper."""

    DEFAULT_BEAM_SIZE = 5
    PROGRESS_INTERVAL_SECONDS = 0.25
    DOWNLOAD_FILE_PATTERNS = (
        "config.json",
        "preprocessor_config.json",
        "model.bin",
        "tokenizer.json",
        "vocabulary.*",
    )
    MODEL_REPOSITORIES = {
        "tiny": "Systran/faster-whisper-tiny",
        "base": "Systran/faster-whisper-base",
        "small": "Systran/faster-whisper-small",
        "deepdml/faster-whisper-large-v3-turbo-ct2": "deepdml/faster-whisper-large-v3-turbo-ct2",
        "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
        "large-v3": "Systran/faster-whisper-large-v3",
    }
    PROFILE_DISPLAY_NAMES = {
        "fast": "Fast",
        "balanced": "Balanced",
        "quality": "Quality Turbo",
        "high_quality": "High Quality",
    }
    _prepare_lock = threading.Lock()

    def __init__(
        self,
        model_name: Optional[str] = None,
        model_dir: Optional[Path] = None,
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        cpu_threads: Optional[int] = None,
        audio_cleanup_enabled: Optional[bool] = None,
        audio_cleanup_mode: Optional[str] = None,
    ):
        config = Config()
        self.model_name = model_name or config.get_local_whisper_model()
        self.model_dir = Path(model_dir) if model_dir is not None else config.get_local_whisper_model_dir()
        self.device_preference = device or config.get_local_whisper_device()
        self.compute_type_preference = compute_type or config.get_local_whisper_compute_type()
        self.cpu_threads = cpu_threads or config.get_local_whisper_cpu_threads()
        if audio_cleanup_mode is not None:
            self.audio_cleanup_mode = str(audio_cleanup_mode).strip().lower()
        elif audio_cleanup_enabled is not None:
            self.audio_cleanup_mode = "noisy" if bool(audio_cleanup_enabled) else "off"
        else:
            self.audio_cleanup_mode = config.audio_cleanup_mode()
        self.audio_cleanup_enabled = self.audio_cleanup_mode != "off"
        self.last_error: Optional[str] = None
        self._model = None
        self._loaded_device: Optional[str] = None
        self._loaded_compute_type: Optional[str] = None

    @staticmethod
    def dependency_error() -> str | None:
        """Return a user-facing dependency error when faster-whisper is unavailable."""
        try:
            import faster_whisper  # noqa: F401
        except Exception as e:
            print(f"[LocalWhisper] Optional dependency unavailable: {e}")
            return "Local mode is not installed yet. Run: pip install -r requirements-local.txt, then restart the app."
        return None

    @classmethod
    def get_status(cls, config: Optional[Config] = None) -> dict:
        """Return local model/dependency status for the UI."""
        config = config or Config()
        model = config.get_local_whisper_model()
        managed_model_dir = config.get_local_whisper_model_dir(model)
        dependency_error = cls.dependency_error()
        model_dir, model_source = (
            (managed_model_dir, "managed")
            if dependency_error
            else cls.resolve_model_dir(config, model, allow_cache=True)
        )
        model_ready = cls._model_files_ready(model_dir)
        if dependency_error:
            status = "error"
            message = dependency_error
        elif model_ready:
            status = "ready"
            message = "Local model is already installed." if model_source == "cache" else "Local mode is ready."
        elif managed_model_dir.exists() and any(managed_model_dir.iterdir()):
            status = "missing"
            message = "Local mode setup is incomplete. Set up local mode again."
        else:
            status = "missing"
            message = "Local mode is not set up yet."

        return {
            "status": status,
            "message": message,
            "profile": config.get_local_whisper_profile(),
            "model": model,
            "transcription_model": model,
            "translation_model": model,
            "model_dir": str(model_dir),
            "managed_model_dir": str(managed_model_dir),
            "model_source": model_source,
            "translation_model_dir": str(model_dir),
            "translate_enabled": config.translate_enabled(),
            "transcription_ready": model_ready,
            "translation_ready": model_ready,
            "device": config.get_local_whisper_device(),
            "compute_type": config.get_local_whisper_compute_type(),
            "cpu_usage": config.get_local_whisper_cpu_usage(),
            "cpu_threads": config.get_local_whisper_cpu_threads(),
            "dependency_available": dependency_error is None,
        }

    @classmethod
    def get_setup_info(cls, config: Optional[Config] = None) -> dict:
        """Return trusted remote model metadata without downloading model files."""
        config = config or Config()
        dependency_error = cls.dependency_error()
        if dependency_error:
            raise RuntimeError(dependency_error)

        model_name = config.get_local_whisper_model()
        repository = cls.MODEL_REPOSITORIES.get(model_name)
        if not repository:
            raise ValueError(f"Unsupported Local Whisper model: {model_name}")

        from huggingface_hub import HfApi

        model_info = HfApi().model_info(repository, files_metadata=True)
        total_bytes = sum(
            int(sibling.size)
            for sibling in (model_info.siblings or [])
            if sibling.size is not None
            and any(fnmatchcase(sibling.rfilename, pattern) for pattern in cls.DOWNLOAD_FILE_PATTERNS)
        )
        if total_bytes <= 0:
            raise RuntimeError("Local model download size could not be determined.")

        model_dir, _source = cls.resolve_model_dir(config, model_name, allow_cache=True)
        return {
            "profile": config.get_local_whisper_profile(),
            "model": model_name,
            "display_name": cls.PROFILE_DISPLAY_NAMES[config.get_local_whisper_profile()],
            "repository": repository,
            "source_url": f"https://huggingface.co/{repository}",
            "total_bytes": total_bytes,
            "model_dir": str(config.get_local_whisper_model_dir(model_name)),
            "already_ready": cls._model_files_ready(model_dir),
        }

    @classmethod
    def prepare_model(
        cls,
        config: Optional[Config] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> dict:
        """Download the configured local faster-whisper model if needed."""
        config = config or Config()
        dependency_error = cls.dependency_error()
        if dependency_error:
            return {
                **cls.get_status(config),
                "status": "error",
                "message": dependency_error,
            }

        model_name = config.get_local_whisper_model()
        model_dir = config.get_local_whisper_model_dir(model_name)
        cached_model_dir, _source = cls.resolve_model_dir(config, model_name, allow_cache=True)
        if cls._model_files_ready(cached_model_dir):
            return {
                **cls.get_status(config),
                "status": "ready",
                "message": "Local mode is already ready.",
            }

        model_dir.mkdir(parents=True, exist_ok=True)
        if cls._model_files_ready(model_dir):
            return {
                **cls.get_status(config),
                "status": "ready",
                "message": "Local mode is already ready.",
            }

        if not cls._prepare_lock.acquire(blocking=False):
            return {
                **cls.get_status(config),
                "status": "error",
                "message": "Local mode setup is already in progress.",
            }

        try:
            setup_info = cls.get_setup_info(config)
            total_bytes = int(setup_info["total_bytes"])
            cls._emit_setup_progress(
                progress_callback,
                state="preparing",
                model=model_name,
                model_dir=model_dir,
                downloaded_bytes=cls._downloaded_payload_bytes(model_dir),
                total_bytes=total_bytes,
                message="Preparing local model download...",
            )

            completed = threading.Event()
            download_error: list[Exception] = []

            def download_worker() -> None:
                try:
                    from faster_whisper.utils import download_model

                    download_model(
                        model_name,
                        output_dir=str(model_dir),
                        local_files_only=False,
                    )
                except Exception as exc:
                    download_error.append(exc)
                finally:
                    completed.set()

            threading.Thread(
                target=download_worker,
                name=f"local-whisper-download-{config.get_local_whisper_profile()}",
                daemon=True,
            ).start()

            while not completed.wait(cls.PROGRESS_INTERVAL_SECONDS):
                cls._emit_setup_progress(
                    progress_callback,
                    state="downloading",
                    model=model_name,
                    model_dir=model_dir,
                    downloaded_bytes=cls._downloaded_payload_bytes(model_dir),
                    total_bytes=total_bytes,
                    message="Downloading local model...",
                )

            if download_error:
                raise download_error[0]

            cls._emit_setup_progress(
                progress_callback,
                state="verifying",
                model=model_name,
                model_dir=model_dir,
                downloaded_bytes=cls._downloaded_payload_bytes(model_dir),
                total_bytes=total_bytes,
                message="Verifying local model files...",
            )
            if not cls._model_files_ready(model_dir):
                raise RuntimeError("Local model download is incomplete. Try setup again.")

            verified_bytes = cls._downloaded_payload_bytes(model_dir)
            cls._emit_setup_progress(
                progress_callback,
                state="complete",
                model=model_name,
                model_dir=model_dir,
                downloaded_bytes=verified_bytes,
                total_bytes=total_bytes,
                message="Local mode is ready.",
            )
            return {
                **cls.get_status(config),
                "status": "ready",
                "message": "Local mode is ready.",
            }
        except Exception as e:
            cls._emit_setup_progress(
                progress_callback,
                state="error",
                model=model_name,
                model_dir=model_dir,
                downloaded_bytes=cls._downloaded_payload_bytes(model_dir),
                total_bytes=locals().get("total_bytes", 0),
                message=f"Local mode setup failed: {e}",
            )
            return {
                **cls.get_status(config),
                "status": "error",
                "message": f"Local mode setup failed: {e}",
            }
        finally:
            cls._prepare_lock.release()

    @classmethod
    def _emit_setup_progress(
        cls,
        callback: Optional[Callable[[dict], None]],
        *,
        state: str,
        model: str,
        model_dir: Path,
        downloaded_bytes: int,
        total_bytes: int,
        message: str,
    ) -> None:
        if callback is None:
            return
        clamped_downloaded = max(0, min(downloaded_bytes, total_bytes)) if total_bytes > 0 else max(0, downloaded_bytes)
        percent = (clamped_downloaded / total_bytes * 100.0) if total_bytes > 0 else 0.0
        if state == "complete":
            percent = 100.0
        callback(
            {
                "state": state,
                "model": model,
                "downloaded_bytes": clamped_downloaded,
                "total_bytes": total_bytes,
                "percent": percent,
                "model_dir": str(model_dir),
                "message": message,
            }
        )

    @classmethod
    def _downloaded_payload_bytes(cls, model_dir: Path) -> int:
        """Count ready and in-progress model payload bytes without metadata duplicates."""
        if not model_dir.exists():
            return 0

        total = 0
        seen_files: set[tuple[int, int]] = set()
        for path in model_dir.rglob("*"):
            if not path.is_file():
                continue
            relative_parts = path.relative_to(model_dir).parts
            in_huggingface_cache = ".cache" in relative_parts and "huggingface" in relative_parts
            is_payload = any(fnmatchcase(path.name, pattern) for pattern in cls.DOWNLOAD_FILE_PATTERNS)
            is_partial_payload = in_huggingface_cache and path.name.endswith(".incomplete")
            if not is_payload and not is_partial_payload:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            identity = (stat.st_dev, stat.st_ino)
            if stat.st_ino and identity in seen_files:
                continue
            if stat.st_ino:
                seen_files.add(identity)
            total += stat.st_size
        return total

    @staticmethod
    def _model_files_ready(model_dir: Path) -> bool:
        """Check for the minimal CTranslate2 files faster-whisper needs."""
        if not model_dir.exists() or not model_dir.is_dir():
            return False
        required_files = ["model.bin", "config.json", "tokenizer.json"]
        return all(
            (model_dir / name).is_file() and (model_dir / name).stat().st_size > 0
            for name in required_files
        )

    @classmethod
    def resolve_model_dir(cls, config: Config, model_name: str, allow_cache: bool = True) -> tuple[Path, str]:
        """Resolve a ready local model directory without downloading missing models."""
        managed_model_dir = config.get_local_whisper_model_dir(model_name)
        if cls._model_files_ready(managed_model_dir) or not allow_cache or sys.platform.startswith("linux"):
            return managed_model_dir, "managed"

        try:
            from faster_whisper.utils import download_model

            cached_model_dir = Path(download_model(model_name, local_files_only=True))
            if cls._model_files_ready(cached_model_dir):
                return cached_model_dir, "cache"
        except Exception as e:
            print(f"[LocalWhisper] No ready cached model found for {model_name}: {e}")

        return managed_model_dir, "managed"

    def transcribe(self, audio_file_path: str, language: Optional[str] = "tr", translate: bool = False) -> Optional[str]:
        """Transcribe or translate an audio file using local faster-whisper."""
        self.last_error = None
        audio_path = Path(audio_file_path)
        if not audio_path.exists():
            self.last_error = f"Audio file not found: {audio_file_path}"
            return None

        dependency_error = self.dependency_error()
        if dependency_error:
            self.last_error = dependency_error
            return None

        if not self._model_files_ready(self.model_dir):
            self.last_error = (
                f"Local Whisper model is not ready: {self.model_name}. "
                "Use Set Up Local Mode in Settings."
            )
            return None

        try:
            model = self._load_model()
            task = "translate" if translate else "transcribe"
            kwargs = {
                "task": task,
                "beam_size": self.DEFAULT_BEAM_SIZE,
            }
            if language is not None:
                kwargs["language"] = language
            if self.audio_cleanup_enabled:
                kwargs["vad_filter"] = True
                kwargs["vad_parameters"] = {
                    "min_silence_duration_ms": 500,
                    "speech_pad_ms": 300,
                }

            print(
                "[LocalWhisper] "
                f"provider=local translate={translate} language={language or 'auto'} "
                f"model={self.model_name} task={task} audio_cleanup={self.audio_cleanup_mode}"
            )
            start = time.perf_counter()
            segments, _info = model.transcribe(str(audio_path), **kwargs)
            text = "".join(segment.text for segment in segments).strip()
            print(
                "[local whisper timing] "
                f"total={time.perf_counter() - start:.2f}s "
                f"device={self._loaded_device} compute_type={self._loaded_compute_type}"
            )
            self.last_error = None
            return text or None
        except Exception as e:
            self.last_error = f"Local Whisper transcription failed: {e}"
            print(self.last_error)
            return None

    def _load_model(self):
        if self._model is not None:
            return self._model

        from faster_whisper import WhisperModel

        attempts = self._build_load_attempts()
        last_exception: Exception | None = None
        for device, compute_type in attempts:
            try:
                kwargs = {
                    "device": device,
                    "compute_type": compute_type,
                }
                if device == "cpu":
                    kwargs["cpu_threads"] = self.cpu_threads
                    os.environ.setdefault("OMP_NUM_THREADS", str(self.cpu_threads))

                self._model = WhisperModel(str(self.model_dir), **kwargs)
                self._loaded_device = device
                self._loaded_compute_type = compute_type
                print(f"[LocalWhisper] Loaded {self.model_name} on {device} ({compute_type})")
                return self._model
            except Exception as e:
                last_exception = e
                print(f"[LocalWhisper] Load failed on {device} ({compute_type}): {e}")

        raise RuntimeError(f"Could not load local Whisper model: {last_exception}")

    def _build_load_attempts(self) -> list[tuple[str, str]]:
        device = self.device_preference
        compute_type = self.compute_type_preference

        if device == "cuda":
            return [("cuda", "float16" if compute_type == "auto" else compute_type)]
        if device == "cpu":
            return [("cpu", "int8" if compute_type == "auto" else compute_type)]
        if compute_type == "auto":
            return [("cuda", "float16"), ("cpu", "int8")]
        return [("cuda", compute_type), ("cpu", compute_type)]


def create_transcriber(config: Config, translate: bool = False) -> Transcriber:
    """Create the configured transcription provider."""
    provider = config.get_transcription_provider()
    if provider == "local":
        model_name = config.get_effective_local_whisper_model(translate)
        model_dir, _model_source = LocalWhisperTranscriber.resolve_model_dir(config, model_name, allow_cache=True)
        return LocalWhisperTranscriber(
            model_name=model_name,
            model_dir=model_dir,
            device=config.get_local_whisper_device(),
            compute_type=config.get_local_whisper_compute_type(),
            cpu_threads=config.get_local_whisper_cpu_threads(),
            audio_cleanup_mode=config.audio_cleanup_mode(),
        )

    return GroqTranscriber(config.get_api_key())


# Standalone test
def test_transcriber():
    """Test the transcriber standalone."""
    print("Groq Transcriber Test")
    print("=" * 40)

    # Find .env file by going up from current script location
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent  # Go up 3 levels: src/core/transcriber.py -> src/core -> src -> project_root

    env_file = project_root / ".env"

    if not env_file.exists():
        print(f"\n✗ Error: .env file not found!")
        print(f"   Expected location: {env_file}")
        print(f"\nPlease create .env file with your Groq API key:")
        print("   GROQ_API_KEY=<your Groq API key>")
        print(f"\nYou can copy .env.example to .env:")
        print(f"   cp .env.example .env")
        print(f"   Then edit .env and add your API key.")
        return

    # Check API key
    print("Checking API key...")
    try:
        transcriber = GroqTranscriber()
    except ValueError as e:
        print(f"✗ {e}")
        print("\nPlease add your Groq API key to .env file:")
        print("1. Get your key from: https://console.groq.com/keys")
        print("2. Add this line to .env:")
        print("   GROQ_API_KEY=<your Groq API key>")
        return

    if transcriber.test_api_key():
        print("✓ API key is valid")
    else:
        print("✗ API key validation failed")
        return

    # Check for test audio file (use project_root from above)
    test_file = "test_audio.wav"
    test_file_path = project_root / test_file

    if not test_file_path.exists():
        # Check temp folder for recordings
        temp_dir = Config.get_temp_dir()
        wav_files = list(temp_dir.glob("recording_*.wav")) if temp_dir.exists() else []

        if wav_files:
            # Use most recent recording
            test_file_path = max(wav_files, key=lambda p: p.stat().st_mtime)
            print(f"\nUsing most recent recording: {test_file_path.name}")
        else:
            print(f"\n✗ No test audio found!")
            print(f"   Options:")
            print(f"   1. Run: python src/core/recorder.py")
            print(f"   2. Place a .wav file at: {test_file_path}")
            print(f"   3. Record from temp folder: {temp_dir}")
            return
    else:
        test_file_path = str(test_file_path)

    # Transcribe
    print(f"\nTranscribing: {test_file_path}")
    print("(this may take a few seconds...)")

    result = transcriber.transcribe(str(test_file_path))

    if result:
        print("\n" + "=" * 40)
        print("Transcription:")
        print("=" * 40)
        print(result)
        print("=" * 40)
    else:
        print("✗ Transcription failed.")


if __name__ == "__main__":
    test_transcriber()
