"""Settings-domain behavior for BackendService."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from src.config import Config
from src.core.audio_cleanup import resolve_rnnoise_model_path
from src.core.backend.common import BackendValidationError
from src.core.ffmpeg_utils import (
    get_ffmpeg_path,
    get_ffmpeg_version,
    get_ffprobe_path,
    is_ffmpeg_available,
    is_ffmpeg_filter_available,
    is_ffprobe_available,
)
from src.core.transcriber import LocalWhisperTranscriber


class SettingsMixin:
    def get_config(self) -> dict[str, Any]:
        """Return the settings shape consumed by the Electron settings UI."""
        self.config.reload_env()
        return {
            "api_key_exists": self.config.has_api_key(),
            "api_key_length": self.config.get_api_key_length(),
            "transcription_provider": self.config.get_transcription_provider(),
            "local_whisper_profile": self.config.get_local_whisper_profile(),
            "local_whisper_model": self.config.get_local_whisper_model(),
            "local_whisper_device": self.config.get_local_whisper_device(),
            "local_whisper_compute_type": self.config.get_local_whisper_compute_type(),
            "local_whisper_cpu_usage": self.config.get_local_whisper_cpu_usage(),
            "local_whisper_cpu_threads": self.config.get_local_whisper_cpu_threads(),
            "local_whisper_status": self.get_local_whisper_status(),
            "build_version": self.build_info.get("version", "source"),
            "build_display": self.build_info.get("display", "Source Run"),
            "input_device_index": self.config.get_input_device(),
            "recommended_microphone_index": self.platform.get_recommended_microphone([]),
            "sound_enabled": self.config.play_beep(),
            "auto_paste_enabled": self.config.auto_paste_enabled(),
            "toggle_recording_auto_paste_enabled": self.config.toggle_recording_auto_paste_enabled(),
            "audio_cleanup_mode": self.config.audio_cleanup_mode(),
            "audio_cleanup_enabled": self.config.audio_cleanup_enabled(),
            "audio_cleanup_status": self.get_audio_cleanup_status(),
            "always_on_top": self.config.always_on_top(),
            "translate_enabled": self.config.translate_enabled(),
            "language": self.config.get_language(),
            "recording_hotkey": self.config.get_hotkey(),
            "recording_hotkey_display": self.config.get_hotkey_display(),
            "recording_trigger_mode": self.config.get_recording_trigger_mode(),
            "push_to_talk_key": self.config.get_push_to_talk_key(),
            "push_to_talk_key_display": self.config.format_key_for_display(self.config.get_push_to_talk_key()),
            "toggle_hotkey": self.config.get_toggle_hotkey(),
            "toggle_hotkey_display": self.config.format_hotkey_for_display(self.config.get_toggle_hotkey()),
            "translate_toggle_hotkey": self.config.get_translate_toggle_hotkey(),
            "translate_toggle_hotkey_display": self.config.get_translate_toggle_hotkey_display(),
        }

    def save_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist supported settings using Config validation."""
        if not isinstance(payload, dict):
            raise BackendValidationError("Invalid settings payload")

        if "api_key" in payload and payload["api_key"]:
            self._save_api_key(payload["api_key"])
        if "sound_enabled" in payload:
            self.config.save_beep_setting(self._require_bool(payload["sound_enabled"], "sound_enabled"))
        if "auto_paste_enabled" in payload:
            self.config.save_auto_paste_setting(self._require_bool(payload["auto_paste_enabled"], "auto_paste_enabled"))
        if "toggle_recording_auto_paste_enabled" in payload:
            self.config.save_toggle_recording_auto_paste_setting(
                self._require_bool(
                    payload["toggle_recording_auto_paste_enabled"],
                    "toggle_recording_auto_paste_enabled",
                )
            )
        if "audio_cleanup_mode" in payload:
            try:
                self.config.save_audio_cleanup_mode(self._coerce_audio_cleanup_mode(str(payload["audio_cleanup_mode"])))
            except ValueError as e:
                raise BackendValidationError(str(e)) from e
        elif "audio_cleanup_enabled" in payload:
            enabled = self._require_bool(payload["audio_cleanup_enabled"], "audio_cleanup_enabled")
            self.config.save_audio_cleanup_mode(self._coerce_audio_cleanup_mode("noisy" if enabled else "off"))
        if "always_on_top" in payload:
            always_on_top = self._require_bool(payload["always_on_top"], "always_on_top")
            self.config.save_always_on_top_setting(always_on_top)
            if self._on_always_on_top:
                self._on_always_on_top(always_on_top)
        if "input_device_index" in payload:
            self._save_microphone(payload["input_device_index"])
        if "translate_enabled" in payload:
            self.config.save_translate_setting(self._require_bool(payload["translate_enabled"], "translate_enabled"))
        if "transcription_provider" in payload:
            self.config.save_transcription_provider(str(payload["transcription_provider"]))
        if self._LOCAL_KEYS & set(payload):
            self.config.save_local_whisper_settings(
                profile=payload.get("local_whisper_profile"),
                model=payload.get("local_whisper_model"),
                device=payload.get("local_whisper_device"),
                compute_type=payload.get("local_whisper_compute_type"),
                cpu_threads=payload.get("local_whisper_cpu_threads"),
                cpu_usage=payload.get("local_whisper_cpu_usage"),
            )
        if "language" in payload:
            self._save_language(payload["language"])

        self._reload_config()
        config = self.get_config()
        self._emit("settings.changed", {"config": config})
        return config

    def get_audio_cleanup_status(self) -> dict[str, Any]:
        """Return RNNoise readiness for the Settings UI."""
        self.config.reload_env()
        managed_model_dir = Config.get_rnnoise_models_dir()
        configured_model = self.config.audio_cleanup_rnnoise_model()
        resolved_model = resolve_rnnoise_model_path(configured_model)
        arnndn_available = is_ffmpeg_filter_available("arnndn")
        rnnoise_ready = bool(resolved_model and arnndn_available)

        if rnnoise_ready:
            message = "RNNoise ready."
        elif resolved_model:
            message = "RNNoise model found, but this FFmpeg build does not include the arnndn filter."
        elif arnndn_available:
            message = "RNNoise model missing. Noisy/Severe cleanup requires a .rnnn model."
        else:
            message = "RNNoise model missing and this FFmpeg build does not include the arnndn filter."

        return {
            "rnnoise_ready": rnnoise_ready,
            "rnnoise_model_path": resolved_model,
            "managed_model_dir": str(managed_model_dir),
            "arnndn_available": arnndn_available,
            "message": message,
        }

    def install_rnnoise_model(self, path: str) -> dict[str, Any]:
        """Copy a user-selected .rnnn model into app data and persist it."""
        source = Path(path).expanduser()
        if not source.exists() or not source.is_file():
            raise BackendValidationError("RNNoise model file was not found.")
        if source.suffix.lower() != ".rnnn":
            raise BackendValidationError("RNNoise model must be a .rnnn file.")

        target_dir = Config.get_rnnoise_models_dir()
        safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", source.stem).strip(".-") or "rnnoise"
        target = target_dir / f"{safe_stem}.rnnn"
        if source.resolve() != target.resolve():
            suffix = 1
            while target.exists():
                if target.resolve() == source.resolve():
                    break
                target = target_dir / f"{safe_stem}-{suffix}.rnnn"
                suffix += 1
            if source.resolve() != target.resolve():
                shutil.copy2(source, target)

        self.config.save_audio_cleanup_rnnoise_model(str(target))
        self._reload_config()
        config = self.get_config()
        self._emit("settings.changed", {"config": config})
        return {"success": True, "message": "RNNoise model installed.", "config": config}

    def _coerce_audio_cleanup_mode(self, mode: str) -> str:
        """Keep RNNoise-only modes from being saved while RNNoise is unavailable."""
        value = str(mode or "").strip().lower()
        if value in {"noisy", "severe"} and not self.get_audio_cleanup_status()["rnnoise_ready"]:
            return "normal"
        return value

    def save_hotkeys(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate and persist hotkey settings."""
        if not isinstance(payload, dict):
            raise BackendValidationError("Invalid hotkey payload")

        mode = str(payload.get("recording_trigger_mode", "")).strip().lower()
        if mode not in {"hold_to_talk", "toggle"}:
            raise BackendValidationError("Recording mode must be hold-to-talk or toggle")

        push_to_talk_key = Config.normalize_hotkey(str(payload.get("push_to_talk_key", "")))
        toggle_hotkey = Config.normalize_hotkey(str(payload.get("toggle_hotkey", "")))
        translate_toggle_hotkey = Config.normalize_hotkey(str(payload.get("translate_toggle_hotkey", "")))

        push_tokens = Config.parse_hotkey_tokens(push_to_talk_key)
        toggle_tokens = Config.parse_hotkey_tokens(toggle_hotkey)
        translate_tokens = Config.parse_hotkey_tokens(translate_toggle_hotkey)
        shutdown_tokens = ["ctrl", "alt", "q"]

        if not push_tokens or not toggle_tokens or not translate_tokens:
            raise BackendValidationError("Hotkeys cannot be empty")
        if len(push_tokens) != 1:
            raise BackendValidationError("Hold-to-talk requires a single key")

        push_to_talk_key = push_tokens[0]
        if push_to_talk_key == "ctrl":
            push_to_talk_key = Config.DEFAULT_PUSH_TO_TALK_KEY
            push_tokens = [push_to_talk_key]

        candidates = [
            ("hold-to-talk", push_tokens),
            ("toggle recording", toggle_tokens),
            ("translate", translate_tokens),
            ("quit", shutdown_tokens),
        ]
        for index, (left_name, left_tokens) in enumerate(candidates):
            for right_name, right_tokens in candidates[index + 1:]:
                if self._hotkeys_conflict(left_tokens, right_tokens):
                    raise BackendValidationError(
                        f"{left_name.title()} hotkey conflicts with {right_name} hotkey"
                    )

        self.config.save_hotkey_settings(
            recording_trigger_mode=mode,
            push_to_talk_key=push_to_talk_key,
            toggle_hotkey=toggle_hotkey,
            translate_toggle_hotkey=translate_toggle_hotkey,
        )
        if self._on_hotkeys_reload:
            self._on_hotkeys_reload()
        else:
            self.config.reload_env()
        config = self.get_config()
        self._emit("settings.changed", {"config": config})
        return {"success": True, "message": "Hotkeys saved.", "config": config}

    def get_local_whisper_status(self) -> dict[str, Any]:
        """Return local Whisper dependency/model status without loading a model."""
        self.config.reload_env()
        return LocalWhisperTranscriber.get_status(self.config)

    def prepare_local_whisper_model(self) -> dict[str, Any]:
        self.config.reload_env()
        result = LocalWhisperTranscriber.prepare_model(self.config)
        self._emit("settings.changed", {"config": self.get_config()})
        return result

    def get_ffmpeg_status(self) -> dict[str, Any]:
        ffmpeg_installed = is_ffmpeg_available()
        ffprobe_installed = is_ffprobe_available()
        return {
            "installed": ffmpeg_installed,
            "ffmpeg_installed": ffmpeg_installed,
            "ffprobe_installed": ffprobe_installed,
            "ffmpeg_path": get_ffmpeg_path(),
            "ffprobe_path": get_ffprobe_path(),
            "version": get_ffmpeg_version() if ffmpeg_installed else None,
            "install_url": "https://ffmpeg.org/download.html",
        }

    def get_microphones(self) -> list[dict[str, Any]]:
        sd = self._load_sounddevice()
        if sd is None:
            return []
        try:
            devices = sd.query_devices()
            host_apis = sd.query_hostapis()
            return self.platform.filter_input_devices(devices, host_apis)
        except Exception as exc:
            print(f"[BackendService] Error getting microphones: {exc}")
            return []

    def get_recommended_microphone(self) -> dict[str, int]:
        microphones = self.get_microphones()
        return {"index": self.platform.get_recommended_microphone(microphones)}

    def toggle_translate_setting(self) -> dict[str, Any]:
        self.config.reload_env()
        enabled = not self.config.translate_enabled()
        self.config.save_translate_setting(enabled)
        self.config.reload_env()
        config = self.get_config()
        self._emit("settings.changed", {"config": config})
        self._emit(
            "toast",
            {
                "type": "info",
                "message": "Translate EN enabled" if enabled else "Translate EN disabled",
            },
        )
        return {"success": True, "translate_enabled": enabled, "config": config}

    def hotkeys_status(self) -> dict[str, Any]:
        return {"enabled": False, "registered": False, "status": "managed_by_entrypoint"}

    def _reload_config(self) -> None:
        if self._on_config_reload:
            self._on_config_reload()
        else:
            self.config.reload_env()

    def _save_language(self, language: Any) -> None:
        if not isinstance(language, str) or language not in self._ALLOWED_LANGUAGES:
            raise BackendValidationError("Invalid language")
        self.config.save_language(language)

    def _save_microphone(self, device_index: Any) -> None:
        try:
            index = int(device_index)
        except (TypeError, ValueError) as exc:
            raise BackendValidationError("Invalid microphone index") from exc

        valid_indexes = {-1}
        valid_indexes.update(int(device["index"]) for device in self.get_microphones() if "index" in device)
        if index not in valid_indexes:
            raise BackendValidationError("Unknown microphone index")

        self.config.save_input_device(index)

    def _save_api_key(self, api_key: Any) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise BackendValidationError("Invalid API key")
        api_key = api_key.strip()
        if not re.fullmatch(r"gsk_[A-Za-z0-9_\-]{20,}", api_key):
            raise BackendValidationError("Invalid API key format")
        self.config.save_api_key(api_key)

    @staticmethod
    def _require_bool(value: Any, name: str) -> bool:
        if not isinstance(value, bool):
            raise BackendValidationError(f"{name} must be a boolean")
        return value

    @staticmethod
    def _load_sounddevice():
        try:
            import sounddevice as sd

            return sd
        except Exception as exc:
            print(f"[BackendService] sounddevice unavailable: {exc}")
            return None

    @staticmethod
    def _expanded_hotkey_forms(tokens: list[str]) -> set[frozenset[str]]:
        expansions = {
            "ctrl": ["ctrl", "left_ctrl", "right_ctrl"],
            "alt": ["alt", "left_alt", "right_alt"],
            "shift": ["shift", "left_shift", "right_shift"],
        }
        forms = {frozenset()}
        for token in tokens:
            next_forms = set()
            for form in forms:
                for expanded in expansions.get(token, [token]):
                    next_forms.add(frozenset([*form, expanded]))
            forms = next_forms
        return forms

    @classmethod
    def _hotkeys_conflict(cls, left: list[str], right: list[str]) -> bool:
        if not left or not right or len(left) != len(right):
            return False
        return bool(cls._expanded_hotkey_forms(left) & cls._expanded_hotkey_forms(right))
