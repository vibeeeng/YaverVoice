"""
Configuration management for YaverVoice.
Loads and saves settings from .env file.
"""

import os
import re
import sys
import tempfile
from pathlib import Path
from dotenv import load_dotenv


def re_sub_unsafe_filename(value: str) -> str:
    """Return a filesystem-safe token for locally managed model directories."""
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return safe.strip(".-") or "base"


class Config:
    """Configuration manager for application settings."""

    DEFAULT_TOGGLE_HOTKEY = "<alt>+r"
    LEGACY_DEFAULT_TOGGLE_HOTKEY = "<ctrl>+<alt>+k"
    DEFAULT_TRANSLATE_TOGGLE_HOTKEY = "<shift>+t"
    DEFAULT_TRIGGER_MODE = "hold_to_talk"
    DEFAULT_PUSH_TO_TALK_KEY = "right_ctrl"
    DEFAULT_PUSH_TO_TALK_THRESHOLD_MS = 150
    DEFAULT_TRANSCRIPTION_PROVIDER = "groq"
    LOCAL_WHISPER_PROFILE_MODELS = {
        "fast": "base",
        "balanced": "small",
        "quality": "deepdml/faster-whisper-large-v3-turbo-ct2",
        "high_quality": "large-v3",
    }
    LOCAL_WHISPER_MODEL_PROFILES = {
        "tiny": "fast",
        "base": "fast",
        "small": "balanced",
        "deepdml/faster-whisper-large-v3-turbo-ct2": "quality",
        "large-v3-turbo": "quality",
        "large-v3": "high_quality",
    }
    DEFAULT_LOCAL_WHISPER_PROFILE = "balanced"
    DEFAULT_LOCAL_WHISPER_MODEL = LOCAL_WHISPER_PROFILE_MODELS[DEFAULT_LOCAL_WHISPER_PROFILE]
    DEFAULT_LOCAL_WHISPER_DEVICE = "auto"
    DEFAULT_LOCAL_WHISPER_COMPUTE_TYPE = "auto"
    DEFAULT_LOCAL_WHISPER_CPU_THREADS = 4
    DEFAULT_LOCAL_WHISPER_CPU_USAGE = "normal"
    AUDIO_CLEANUP_MODES = {"off", "normal", "noisy", "severe"}
    DEFAULT_AUDIO_CLEANUP_MODE = "off"

    PLACEHOLDER_API_KEYS = {
        "your_groq_api_key_here",
        "gsk" + "_your_api_key_here",
        "gsk" + "_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    }

    @staticmethod
    def get_app_base_dir() -> Path:
        """
        Resolve the base directory for runtime files.

        Runtime data is stored under the current user's local app data folder
        so source runs, folder builds, and one-file executables behave the same.
        """
        if sys.platform.startswith("win"):
            base_dir = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
            if base_dir:
                return Path(base_dir) / "YaverVoice"

            return Path.home() / "AppData" / "Local" / "YaverVoice"

        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "YaverVoice"

        base_dir = os.getenv("XDG_DATA_HOME")
        if base_dir:
            return Path(base_dir) / "yavervoice"

        return Path.home() / ".local" / "share" / "yavervoice"

    @staticmethod
    def get_legacy_app_base_dir() -> Path:
        """Resolve the pre-YaverVoice runtime data directory."""
        if sys.platform.startswith("win"):
            base_dir = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
            if base_dir:
                return Path(base_dir) / "GroqWhisper"

            return Path.home() / "AppData" / "Local" / "GroqWhisper"

        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "GroqWhisper"

        base_dir = os.getenv("XDG_DATA_HOME")
        if base_dir:
            return Path(base_dir) / "groqwhisper"

        return Path.home() / ".local" / "share" / "groqwhisper"

    @classmethod
    def _merge_legacy_app_data(cls, legacy_dir: Path, canonical_dir: Path) -> None:
        """Move missing legacy entries without overwriting canonical data."""
        canonical_dir.mkdir(parents=True, exist_ok=True)
        for source in legacy_dir.iterdir():
            destination = canonical_dir / source.name
            if not destination.exists():
                source.rename(destination)
            elif (
                source.is_dir()
                and not source.is_symlink()
                and destination.is_dir()
                and not destination.is_symlink()
            ):
                cls._merge_legacy_app_data(source, destination)

        try:
            legacy_dir.rmdir()
        except OSError:
            pass

    @classmethod
    def _rewrite_migrated_rnnoise_path(cls, legacy_dir: Path, canonical_dir: Path) -> None:
        """Repair a stale managed RNNoise path after app-data migration."""
        if legacy_dir.is_symlink() or canonical_dir.is_symlink():
            return

        env_path = canonical_dir / ".env"
        if not env_path.is_file():
            return

        try:
            content = env_path.read_text(encoding="utf-8")
            lines = content.splitlines(keepends=True)
            matches = [
                index
                for index, line in enumerate(lines)
                if line.rstrip("\r\n").startswith("AUDIO_CLEANUP_RNN_MODEL=")
            ]
            if len(matches) != 1:
                return

            index = matches[0]
            raw_line = lines[index]
            line = raw_line.rstrip("\r\n")
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            if not value:
                return

            configured = Path(value).expanduser()
            if configured.exists():
                return

            legacy_models = (legacy_dir / "models" / "rnnoise").resolve()
            relative_model = configured.resolve(strict=False).relative_to(legacy_models)
            canonical_models = (canonical_dir / "models" / "rnnoise").resolve()
            candidate = (canonical_models / relative_model).resolve(strict=False)
            candidate.relative_to(canonical_models)
            if not candidate.is_file():
                return

            newline = "\r\n" if raw_line.endswith("\r\n") else "\n" if raw_line.endswith("\n") else ""
            lines[index] = f"AUDIO_CLEANUP_RNN_MODEL={candidate}{newline}"
            temp_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    newline="",
                    dir=env_path.parent,
                    prefix=".env.",
                    suffix=".migration.tmp",
                    delete=False,
                ) as handle:
                    temp_path = Path(handle.name)
                    handle.write("".join(lines))
                if os.name != "nt":
                    os.chmod(temp_path, 0o600)
                temp_path.replace(env_path)
            finally:
                if temp_path is not None:
                    try:
                        temp_path.unlink(missing_ok=True)
                    except OSError:
                        pass
        except (OSError, RuntimeError, ValueError):
            return

    @classmethod
    def ensure_app_base_dir(cls) -> Path:
        """Return the active app-data root after a safe legacy migration attempt."""
        canonical_dir = cls.get_app_base_dir()
        legacy_dir = cls.get_legacy_app_base_dir()

        if canonical_dir.exists():
            if legacy_dir.exists() and not legacy_dir.is_symlink() and not canonical_dir.is_symlink():
                try:
                    cls._merge_legacy_app_data(legacy_dir, canonical_dir)
                except OSError:
                    pass
            cls._rewrite_migrated_rnnoise_path(legacy_dir, canonical_dir)
            return canonical_dir

        if legacy_dir.exists():
            try:
                canonical_dir.parent.mkdir(parents=True, exist_ok=True)
                legacy_dir.rename(canonical_dir)
                cls._rewrite_migrated_rnnoise_path(legacy_dir, canonical_dir)
                return canonical_dir
            except OSError:
                return legacy_dir

        canonical_dir.mkdir(parents=True, exist_ok=True)
        return canonical_dir

    @classmethod
    def get_temp_dir(cls) -> Path:
        """Resolve and create the runtime temp directory."""
        temp_dir = cls.ensure_app_base_dir() / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir

    @classmethod
    def get_models_dir(cls) -> Path:
        """Resolve and create the local model cache directory."""
        models_dir = cls.ensure_app_base_dir() / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        return models_dir

    @classmethod
    def get_rnnoise_models_dir(cls) -> Path:
        """Resolve and create the managed RNNoise model directory."""
        models_dir = cls.get_models_dir() / "rnnoise"
        models_dir.mkdir(parents=True, exist_ok=True)
        return models_dir

    def __init__(self, env_path: str = None):
        """
        Initialize configuration.

        Args:
            env_path: Path to .env file. If None, uses the app-data .env file.
        """
        if env_path is None:
            env_path = self.ensure_app_base_dir() / ".env"

        self.env_path = Path(env_path)
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        load_dotenv(env_path)
        self._migrate_legacy_default_toggle_hotkey()

    def get_api_key(self) -> str | None:
        """Get Groq API key from environment."""
        return os.getenv("GROQ_API_KEY")

    def _is_valid_api_key_value(self, api_key: str | None) -> bool:
        """Return True when an API key looks like a real configured value."""
        return bool(
            api_key
            and api_key.strip()
            and api_key.strip() not in self.PLACEHOLDER_API_KEYS
        )

    def has_api_key(self) -> bool:
        """
        Check if API key exists without returning it.

        Returns:
            True if a valid API key is configured, False otherwise.

        Security: This method enables existence checks without exposing the actual key.
        """
        api_key = os.getenv("GROQ_API_KEY")
        return self._is_valid_api_key_value(api_key)

    def get_api_key_length(self) -> int:
        """
        Get API key length without exposing the key itself.

        Returns:
            Length of the API key, or 0 if no key is configured.

        Security: This method returns only the length, not the actual key value.
        """
        api_key = os.getenv("GROQ_API_KEY")
        if self._is_valid_api_key_value(api_key):
            return len(api_key)
        return 0

    def save_api_key(self, api_key: str) -> None:
        """
        Save Groq API key to .env file.

        Args:
            api_key: The API key to save.

        Security: Key is written directly to .env and never logged.
        """
        # Validate key format (Groq keys start with "gsk_")
        if not api_key or not api_key.strip():
            raise ValueError("API key cannot be empty")
        if "\r" in api_key or "\n" in api_key or "\x00" in api_key:
            raise ValueError("API key must not contain newline or NUL characters")

        api_key = api_key.strip()

        # Create .env if it doesn't exist
        if not self.env_path.exists():
            self.env_path.parent.mkdir(parents=True, exist_ok=True)
            self.env_path.touch()

        # Read existing .env content
        content = ""
        if self.env_path.exists():
            with open(self.env_path, "r", encoding="utf-8") as f:
                content = f.read()

        # Update or add GROQ_API_KEY line
        lines = content.split("\n")
        updated = False
        for i, line in enumerate(lines):
            if line.startswith("GROQ_API_KEY="):
                lines[i] = f"GROQ_API_KEY={api_key}"
                updated = True
                break

        if not updated:
            lines.append(f"GROQ_API_KEY={api_key}")

        # Write back to .env
        with open(self.env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        if os.name != "nt":
            os.chmod(self.env_path, 0o600)

        # Update runtime environment immediately
        os.environ["GROQ_API_KEY"] = api_key

    def get_sample_rate(self) -> int:
        """Get recording sample rate."""
        return int(os.getenv("RECORDING_SAMPLE_RATE", "16000"))

    def get_channels(self) -> int:
        """Get recording channel count."""
        return int(os.getenv("RECORDING_CHANNELS", "1"))

    def get_hotkey(self) -> str:
        """Get the legacy primary recording trigger key."""
        return self.get_push_to_talk_key()

    def get_toggle_hotkey(self) -> str:
        """Get the configured toggle-mode recording hotkey."""
        hotkey = os.getenv("DEFAULT_HOTKEY", self.DEFAULT_TOGGLE_HOTKEY).strip().lower()
        return hotkey or self.DEFAULT_TOGGLE_HOTKEY

    def _migrate_legacy_default_toggle_hotkey(self) -> None:
        """Move the old bundled toggle hotkey default to the current default."""
        current = os.getenv("DEFAULT_HOTKEY")
        if current is None:
            return

        normalized = self.normalize_hotkey(current)
        if normalized != self.LEGACY_DEFAULT_TOGGLE_HOTKEY:
            return

        self._save_env_value("DEFAULT_HOTKEY", self.DEFAULT_TOGGLE_HOTKEY)
        os.environ["DEFAULT_HOTKEY"] = self.DEFAULT_TOGGLE_HOTKEY

    def get_translate_toggle_hotkey(self) -> str:
        """Get the hotkey that toggles persistent English translation."""
        hotkey = os.getenv("TRANSLATE_TOGGLE_HOTKEY", self.DEFAULT_TRANSLATE_TOGGLE_HOTKEY).strip().lower()
        return hotkey or self.DEFAULT_TRANSLATE_TOGGLE_HOTKEY

    def get_hotkey_display(self) -> str:
        """Get a user-friendly display string for the hold-to-talk trigger."""
        return f"{self.format_key_for_display(self.get_push_to_talk_key())} (Hold)"

    def get_translate_toggle_hotkey_display(self) -> str:
        """Get a user-friendly label for the translate toggle hotkey."""
        return self.format_hotkey_for_display(self.get_translate_toggle_hotkey())

    def get_recording_trigger_mode(self) -> str:
        """Get the saved recording mode for settings compatibility."""
        mode = os.getenv("RECORDING_TRIGGER_MODE", self.DEFAULT_TRIGGER_MODE).strip().lower()
        return mode if mode in {"hold_to_talk", "toggle"} else self.DEFAULT_TRIGGER_MODE

    def get_push_to_talk_key(self) -> str:
        """Get the configured push-to-talk trigger key name."""
        key_name = os.getenv("PUSH_TO_TALK_KEY", self.DEFAULT_PUSH_TO_TALK_KEY).strip().lower()
        tokens = self.parse_hotkey_tokens(key_name)
        if len(tokens) != 1:
            return self.DEFAULT_PUSH_TO_TALK_KEY

        token = tokens[0]
        if token == "ctrl":
            return self.DEFAULT_PUSH_TO_TALK_KEY

        return token

    def save_hotkey_settings(
        self,
        recording_trigger_mode: str,
        push_to_talk_key: str,
        toggle_hotkey: str,
        translate_toggle_hotkey: str,
    ) -> None:
        """Persist hotkey settings and update the runtime environment."""
        values = {
            "RECORDING_TRIGGER_MODE": recording_trigger_mode,
            "PUSH_TO_TALK_KEY": push_to_talk_key,
            "DEFAULT_HOTKEY": toggle_hotkey,
            "TRANSLATE_TOGGLE_HOTKEY": translate_toggle_hotkey,
        }
        for key, value in values.items():
            self._save_env_value(key, value)
            os.environ[key] = value

    def get_push_to_talk_threshold_ms(self) -> int:
        """Get the minimum hold duration before recording starts."""
        try:
            threshold_ms = int(
                os.getenv(
                    "PUSH_TO_TALK_THRESHOLD_MS",
                    str(self.DEFAULT_PUSH_TO_TALK_THRESHOLD_MS),
                )
            )
        except ValueError:
            return self.DEFAULT_PUSH_TO_TALK_THRESHOLD_MS

        return max(threshold_ms, 0)

    @staticmethod
    def format_hotkey_for_display(hotkey: str) -> str:
        """Convert pynput hotkey syntax to a compact UI label."""
        token_map = {
            "<alt>": "Alt",
            "<ctrl>": "Ctrl",
            "<shift>": "Shift",
            "<space>": "Space",
            "<cmd>": "Cmd",
            "<super>": "Super",
            "alt": "Alt",
            "ctrl": "Ctrl",
            "shift": "Shift",
            "space": "Space",
            "cmd": "Cmd",
            "super": "Super",
        }

        display_tokens = []
        for token in hotkey.split("+"):
            normalized = token.strip().lower()
            if normalized in token_map:
                display_tokens.append(token_map[normalized])
                continue

            plain = normalized.replace("<", "").replace(">", "")
            if len(plain) == 1:
                display_tokens.append(plain.upper())
            else:
                display_tokens.append(plain.title())

        return " + ".join(display_tokens)

    @staticmethod
    def format_key_for_display(key_name: str) -> str:
        """Convert a single configured key token into a compact UI label."""
        token_map = {
            "ctrl": "Ctrl",
            "alt": "Alt",
            "shift": "Shift",
            "right_ctrl": "Right Ctrl",
            "left_ctrl": "Left Ctrl",
            "right_alt": "Right Alt",
            "left_alt": "Left Alt",
            "right_shift": "Right Shift",
            "left_shift": "Left Shift",
            "space": "Space",
            "enter": "Enter",
            "tab": "Tab",
            "esc": "Esc",
            "escape": "Esc",
        }

        normalized = key_name.strip().lower()
        if normalized in token_map:
            return token_map[normalized]

        if len(normalized) == 1:
            return normalized.upper()

        return normalized.replace("_", " ").title()

    @classmethod
    def parse_hotkey_tokens(cls, hotkey: str) -> list[str]:
        """Parse a hotkey string into normalized token names."""
        if not hotkey or not hotkey.strip():
            return []

        aliases = {
            "control": "ctrl",
            "ctl": "ctrl",
            "option": "alt",
            "escape": "esc",
            "return": "enter",
            " ": "space",
        }
        tokens = []
        for raw_token in hotkey.split("+"):
            token = raw_token.strip().lower()
            token = token.replace("<", "").replace(">", "")
            token = aliases.get(token, token)
            if token:
                tokens.append(token)

        return tokens

    @classmethod
    def normalize_hotkey(cls, hotkey: str) -> str:
        """Normalize a user-provided hotkey string for storage."""
        tokens = cls.parse_hotkey_tokens(hotkey)
        if not tokens:
            return ""

        wrapped_tokens = {
            "ctrl": "<ctrl>",
            "alt": "<alt>",
            "shift": "<shift>",
            "cmd": "<cmd>",
            "super": "<super>",
            "space": "<space>",
        }
        return "+".join(wrapped_tokens.get(token, token) for token in tokens)

    def auto_copy_enabled(self) -> bool:
        """Get auto-copy to clipboard preference."""
        return os.getenv("AUTO_COPY", "true").lower() == "true"

    def play_beep(self) -> bool:
        """Get beep sound preference."""
        return os.getenv("PLAY_BEEP_SOUND", "true").lower() == "true"

    def get_language(self) -> str:
        """Get transcription language code."""
        return os.getenv("TRANSCRIPTION_LANGUAGE", "tr")

    def get_transcription_provider(self) -> str:
        """Get selected transcription provider."""
        provider = os.getenv("TRANSCRIPTION_PROVIDER", self.DEFAULT_TRANSCRIPTION_PROVIDER).strip().lower()
        return provider if provider in {"groq", "local"} else self.DEFAULT_TRANSCRIPTION_PROVIDER

    def save_transcription_provider(self, provider: str) -> None:
        """Save selected transcription provider."""
        provider = (provider or "").strip().lower()
        if provider not in {"groq", "local"}:
            raise ValueError("Transcription provider must be groq or local")
        self._save_env_value("TRANSCRIPTION_PROVIDER", provider)
        os.environ["TRANSCRIPTION_PROVIDER"] = provider

    def get_local_whisper_profile(self) -> str:
        """Get the user-facing local Whisper performance profile."""
        profile = os.getenv("LOCAL_WHISPER_PROFILE", "").strip().lower()
        if profile in self.LOCAL_WHISPER_PROFILE_MODELS:
            return profile

        model = os.getenv("LOCAL_WHISPER_MODEL", "").strip().lower()
        return self.LOCAL_WHISPER_MODEL_PROFILES.get(model, self.DEFAULT_LOCAL_WHISPER_PROFILE)

    def get_local_whisper_model(self) -> str:
        """Get local Whisper transcription model size/name."""
        return self.get_local_whisper_transcription_model()

    def get_local_whisper_transcription_model(self) -> str:
        """Get the local Whisper model used for source-language transcription."""
        profile = os.getenv("LOCAL_WHISPER_PROFILE", "").strip().lower()
        if profile in self.LOCAL_WHISPER_PROFILE_MODELS:
            return self.LOCAL_WHISPER_PROFILE_MODELS[profile]

        model = os.getenv("LOCAL_WHISPER_MODEL", "").strip()
        if model:
            return model
        return self.LOCAL_WHISPER_PROFILE_MODELS[self.get_local_whisper_profile()]

    def get_local_whisper_translation_model(self) -> str:
        """Get the local Whisper model used for translate-to-English mode."""
        return self.get_local_whisper_transcription_model()

    def get_effective_local_whisper_model(self, translate: bool = False) -> str:
        """Get the local Whisper model for the requested task."""
        return self.get_local_whisper_transcription_model()

    def get_local_whisper_model_dir(self, model_name: str | None = None) -> Path:
        """Get the local directory for a faster-whisper model."""
        safe_model = re_sub_unsafe_filename(model_name or self.get_local_whisper_model())
        return self.get_models_dir() / f"whisper-{safe_model}"

    def get_effective_local_whisper_model_dir(self, translate: bool = False) -> Path:
        """Get the local directory for the model used by the requested task."""
        safe_model = re_sub_unsafe_filename(self.get_effective_local_whisper_model(translate))
        return self.get_models_dir() / f"whisper-{safe_model}"

    def get_local_whisper_device(self) -> str:
        """Get local Whisper device preference."""
        device = os.getenv("LOCAL_WHISPER_DEVICE", self.DEFAULT_LOCAL_WHISPER_DEVICE).strip().lower()
        return device if device in {"auto", "cpu", "cuda"} else self.DEFAULT_LOCAL_WHISPER_DEVICE

    def get_local_whisper_compute_type(self) -> str:
        """Get local Whisper compute type preference."""
        compute_type = os.getenv(
            "LOCAL_WHISPER_COMPUTE_TYPE",
            self.DEFAULT_LOCAL_WHISPER_COMPUTE_TYPE,
        ).strip().lower()
        return compute_type if compute_type in {"auto", "int8", "float16", "float32"} else self.DEFAULT_LOCAL_WHISPER_COMPUTE_TYPE

    def get_local_whisper_cpu_threads(self) -> int:
        """Get local Whisper CPU thread limit."""
        default_threads = min(self.DEFAULT_LOCAL_WHISPER_CPU_THREADS, os.cpu_count() or 1)
        try:
            value = int(os.getenv("LOCAL_WHISPER_CPU_THREADS", str(default_threads)))
        except ValueError:
            return default_threads
        return max(1, min(value, os.cpu_count() or value))

    def get_local_whisper_cpu_usage(self) -> str:
        """Get the user-facing local Whisper CPU usage profile."""
        usage = os.getenv("LOCAL_WHISPER_CPU_USAGE", "").strip().lower()
        if usage in {"low", "normal", "high"}:
            return usage

        threads = self.get_local_whisper_cpu_threads()
        if threads <= self._threads_for_cpu_usage("low"):
            return "low"
        if threads <= self._threads_for_cpu_usage("normal"):
            return "normal"
        return "high"

    @staticmethod
    def _threads_for_cpu_usage(usage: str) -> int:
        cpu_count = os.cpu_count() or 1
        if usage == "low":
            return max(1, min(2, cpu_count))
        if usage == "high":
            return max(1, min(8, cpu_count))
        return max(1, min(Config.DEFAULT_LOCAL_WHISPER_CPU_THREADS, cpu_count))

    def save_local_whisper_settings(
        self,
        profile: str | None = None,
        model: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
        cpu_threads: int | str | None = None,
        cpu_usage: str | None = None,
    ) -> None:
        """Persist local Whisper settings and update runtime environment."""
        values: dict[str, str] = {}
        if profile is not None:
            profile_value = str(profile).strip().lower()
            if profile_value not in self.LOCAL_WHISPER_PROFILE_MODELS:
                raise ValueError("Local Whisper profile must be fast, balanced, quality, or high_quality")
            values["LOCAL_WHISPER_PROFILE"] = profile_value
            values["LOCAL_WHISPER_MODEL"] = self.LOCAL_WHISPER_PROFILE_MODELS[profile_value]
        if model is not None:
            model_value = str(model).strip() or self.DEFAULT_LOCAL_WHISPER_MODEL
            if model_value not in self.LOCAL_WHISPER_MODEL_PROFILES:
                raise ValueError("Local Whisper model must be a supported Local Whisper model")
            values["LOCAL_WHISPER_MODEL"] = model_value
        if device is not None:
            device_value = str(device).strip().lower()
            if device_value not in {"auto", "cpu", "cuda"}:
                raise ValueError("Local Whisper device must be auto, cpu, or cuda")
            values["LOCAL_WHISPER_DEVICE"] = device_value
        if compute_type is not None:
            compute_value = str(compute_type).strip().lower()
            if compute_value not in {"auto", "int8", "float16", "float32"}:
                raise ValueError("Local Whisper compute type must be auto, int8, float16, or float32")
            values["LOCAL_WHISPER_COMPUTE_TYPE"] = compute_value
        if cpu_threads is not None:
            try:
                threads = int(cpu_threads)
            except (TypeError, ValueError):
                raise ValueError("Local Whisper CPU threads must be a number")
            values["LOCAL_WHISPER_CPU_THREADS"] = str(max(1, threads))
        if cpu_usage is not None:
            usage_value = str(cpu_usage).strip().lower()
            if usage_value not in {"low", "normal", "high"}:
                raise ValueError("Local Whisper CPU usage must be low, normal, or high")
            values["LOCAL_WHISPER_CPU_USAGE"] = usage_value
            values["LOCAL_WHISPER_CPU_THREADS"] = str(self._threads_for_cpu_usage(usage_value))

        for key, value in values.items():
            self._save_env_value(key, value)
            os.environ[key] = value

    def save_language(self, language: str) -> None:
        """
        Save transcription language to .env.

        Args:
            language: Language code (e.g., "tr", "en", "de").
        """
        self._save_env_value("TRANSCRIPTION_LANGUAGE", language)
        os.environ["TRANSCRIPTION_LANGUAGE"] = language

    def reload_env(self) -> None:
        """Reload environment variables from .env file."""
        load_dotenv(self.env_path, override=True)

    def save_beep_setting(self, enabled: bool) -> None:
        """
        Save beep sound setting to .env and update os.environ.

        Args:
            enabled: Whether beep sound is enabled.
        """
        value = "true" if enabled else "false"
        self._save_env_value("PLAY_BEEP_SOUND", value)
        os.environ["PLAY_BEEP_SOUND"] = value

    def save_auto_copy_setting(self, enabled: bool) -> None:
        """
        Save auto-copy setting to .env and update os.environ.

        Args:
            enabled: Whether auto-copy is enabled.
        """
        value = "true" if enabled else "false"
        self._save_env_value("AUTO_COPY", value)
        os.environ["AUTO_COPY"] = value

    def auto_paste_enabled(self) -> bool:
        """Get auto-paste (Ctrl+V after copy) preference."""
        return os.getenv("AUTO_PASTE", "true").lower() == "true"

    def save_auto_paste_setting(self, enabled: bool) -> None:
        """Save auto-paste setting to .env and update os.environ."""
        value = "true" if enabled else "false"
        self._save_env_value("AUTO_PASTE", value)
        os.environ["AUTO_PASTE"] = value

    def toggle_recording_auto_paste_enabled(self) -> bool:
        """Get auto-paste preference for the toggle recording hotkey."""
        return os.getenv("TOGGLE_RECORDING_AUTO_PASTE", "false").lower() == "true"

    def save_toggle_recording_auto_paste_setting(self, enabled: bool) -> None:
        """Save toggle recording auto-paste setting to .env and update os.environ."""
        value = "true" if enabled else "false"
        self._save_env_value("TOGGLE_RECORDING_AUTO_PASTE", value)
        os.environ["TOGGLE_RECORDING_AUTO_PASTE"] = value

    def audio_cleanup_mode(self) -> str:
        """Get optional FFmpeg-backed transcription audio cleanup preset."""
        mode = os.getenv("AUDIO_CLEANUP_MODE")
        if mode is not None:
            normalized = mode.strip().lower()
            return normalized if normalized in self.AUDIO_CLEANUP_MODES else self.DEFAULT_AUDIO_CLEANUP_MODE

        legacy_enabled = os.getenv("AUDIO_CLEANUP_ENABLED", "false").lower() == "true"
        return "noisy" if legacy_enabled else self.DEFAULT_AUDIO_CLEANUP_MODE

    def audio_cleanup_enabled(self) -> bool:
        """Get legacy boolean cleanup preference for compatibility."""
        return self.audio_cleanup_mode() != "off"

    def audio_cleanup_rnnoise_model(self) -> str:
        """Get optional RNNoise model path used by noisy/severe cleanup presets."""
        return os.getenv("AUDIO_CLEANUP_RNN_MODEL", "").strip()

    def save_audio_cleanup_rnnoise_model(self, model_path: str) -> None:
        """Save managed RNNoise model path to .env and update os.environ."""
        value = str(model_path or "").strip()
        self._save_env_value("AUDIO_CLEANUP_RNN_MODEL", value)
        os.environ["AUDIO_CLEANUP_RNN_MODEL"] = value

    def save_audio_cleanup_mode(self, mode: str) -> None:
        """Save optional audio cleanup preset to .env and update os.environ."""
        value = str(mode or self.DEFAULT_AUDIO_CLEANUP_MODE).strip().lower()
        if value not in self.AUDIO_CLEANUP_MODES:
            raise ValueError("Audio cleanup mode must be off, normal, noisy, or severe")
        self._save_env_value("AUDIO_CLEANUP_MODE", value)
        os.environ["AUDIO_CLEANUP_MODE"] = value
        legacy_value = "true" if value != "off" else "false"
        self._save_env_value("AUDIO_CLEANUP_ENABLED", legacy_value)
        os.environ["AUDIO_CLEANUP_ENABLED"] = legacy_value

    def save_audio_cleanup_setting(self, enabled: bool) -> None:
        """Save legacy optional audio cleanup setting to .env and update os.environ."""
        self.save_audio_cleanup_mode("noisy" if enabled else "off")

    def always_on_top(self) -> bool:
        """Get always-on-top window preference."""
        return os.getenv("ALWAYS_ON_TOP", "false").lower() == "true"

    def save_always_on_top_setting(self, enabled: bool) -> None:
        """Save always-on-top setting to .env and update os.environ."""
        value = "true" if enabled else "false"
        self._save_env_value("ALWAYS_ON_TOP", value)
        os.environ["ALWAYS_ON_TOP"] = value

    def translate_enabled(self) -> bool:
        """Get translate to English preference."""
        return os.getenv("TRANSLATE_TO_EN", "false").lower() == "true"

    def save_translate_setting(self, enabled: bool) -> None:
        """Save translate setting to .env and update os.environ."""
        value = "true" if enabled else "false"
        self._save_env_value("TRANSLATE_TO_EN", value)
        os.environ["TRANSLATE_TO_EN"] = value

    def _save_env_value(self, key: str, value: str) -> None:
        """
        Save a key-value pair to .env file.

        Args:
            key: Environment variable name.
            value: Value to set.
        """
        if not re.fullmatch(r"[A-Z0-9_]+", key):
            raise ValueError("Environment key must contain only uppercase letters, numbers, and underscores")
        if "\r" in value or "\n" in value or "\x00" in value:
            raise ValueError("Environment value must not contain newline or NUL characters")

        # Read existing .env content
        content = ""
        if self.env_path.exists():
            with open(self.env_path, "r", encoding="utf-8") as f:
                content = f.read()

        # Update or add the key
        lines = content.split("\n")
        updated = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                updated = True
                break

        if not updated:
            lines.append(f"{key}={value}")

        # Write back to .env
        with open(self.env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        if os.name != "nt":
            os.chmod(self.env_path, 0o600)

    def get_input_device(self) -> int:
        """Get input device index from .env."""
        try:
            return int(os.getenv("INPUT_DEVICE", "-1"))
        except ValueError:
            return -1

    def save_input_device(self, device_index: int) -> None:
        """
        Save input device index to .env.

        Args:
            device_index: Device index.
        """
        self._save_env_value("INPUT_DEVICE", str(device_index))
        os.environ["INPUT_DEVICE"] = str(device_index)
