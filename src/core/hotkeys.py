"""Global hotkey controller for headless sidecar entrypoints."""

from __future__ import annotations

import threading
from typing import Any, Callable

from src.config import Config
from src.core.backend_service import BackendService
from src.platform.base import DesktopPlatform

try:
    from pynput import keyboard
except Exception as exc:  # pragma: no cover - depends on desktop session packages
    keyboard = None
    PYNPUT_IMPORT_ERROR = exc
else:  # pragma: no cover - import branch depends on local environment
    PYNPUT_IMPORT_ERROR = None


class HotkeyController:
    """Listener-backed state machine shared by the Electron sidecar."""

    def __init__(
        self,
        *,
        service: BackendService,
        config: Config,
        platform: DesktopPlatform,
        on_status: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.service = service
        self.config = config
        self.platform = platform
        self._on_status = on_status
        self._listener: Any | None = None
        self._lock = threading.RLock()
        self._pressed_keys: set[str] = set()
        self._active_actions: set[str] = set()
        self._shutdown_active = False
        self._hold_candidate_active = False
        self._hold_recording_started = False
        self._hold_session_id = 0
        self._push_to_talk_key = Config.DEFAULT_PUSH_TO_TALK_KEY
        self._toggle_hotkey_tokens: set[str] = set()
        self._translate_toggle_hotkey_tokens: set[str] = set()
        self._status: dict[str, Any] = {
            "enabled": False,
            "registered": False,
            "status": "not_started",
            "error": None,
        }
        self._refresh_hotkey_state()

    def start(self) -> dict[str, Any]:
        if keyboard is None:
            return self._set_status(False, False, "disabled", f"pynput unavailable: {PYNPUT_IMPORT_ERROR}")
        if not self.platform.has_graphical_session():
            return self._set_status(False, False, "disabled", "No graphical desktop session detected")
        platform_error = self.platform.global_hotkey_error()
        if platform_error:
            return self._set_status(False, False, "unsupported", platform_error)

        try:
            self._refresh_hotkey_state()
            self._listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
            self._listener.start()
        except Exception as exc:
            self._listener = None
            return self._set_status(False, False, "error", str(exc))

        return self._set_status(True, True, "registered", None)

    def stop(self) -> None:
        listener = self._listener
        self._listener = None
        if listener:
            try:
                listener.stop()
            except Exception as exc:
                self._set_status(False, False, "error", str(exc))
                return
        self._set_status(False, False, "stopped", None)

    def reload(self) -> dict[str, Any]:
        self.refresh_config()
        listener = self._listener
        if listener:
            try:
                listener.stop()
            except Exception:
                pass
        self._listener = None
        return self.start()

    def refresh_config(self) -> None:
        self.config.reload_env()
        self._refresh_hotkey_state()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def on_key_press(self, key: Any) -> None:
        token = self.normalize_pressed_key(key)
        if token:
            self.press_token(token)

    def on_key_release(self, key: Any) -> None:
        token = self.normalize_pressed_key(key)
        if token:
            self.release_token(token)

    def press_token(self, token: str) -> None:
        should_shutdown = False
        should_toggle_translate = False
        should_toggle_recording = False
        should_discard_pending = False
        should_arm_hold = False

        with self._lock:
            self._pressed_keys.add(token)

            if self._is_shutdown_combo_pressed_locked() and not self._shutdown_active:
                self._shutdown_active = True
                should_shutdown = True

            if (
                self._hotkey_tokens_pressed_locked(self._translate_toggle_hotkey_tokens)
                and "translate_toggle" not in self._active_actions
            ):
                self._active_actions.add("translate_toggle")
                should_toggle_translate = True

            if (
                self._hotkey_tokens_pressed_locked(self._toggle_hotkey_tokens)
                and "recording_toggle" not in self._active_actions
            ):
                self._active_actions.add("recording_toggle")
                should_toggle_recording = True
                if self._hold_candidate_active and not self._hold_recording_started:
                    should_discard_pending = self.service.recording_status()["recording"]
                    self._cancel_hold_locked()
            elif self._pressed_key_matches(self._push_to_talk_key, token):
                status = self.service.recording_status()
                if (
                    not self._hold_candidate_active
                    and not status["recording"]
                    and not status["transcribing"]
                ):
                    should_arm_hold = True
            elif (
                self._hold_candidate_active
                and not self._hold_recording_started
                and not self._hotkey_tokens_pressed_locked(self._translate_toggle_hotkey_tokens)
                and not self._pressed_keys_can_match_hotkey_locked(self._toggle_hotkey_tokens)
            ):
                should_discard_pending = self.service.recording_status()["recording"]
                self._cancel_hold_locked()

        if should_shutdown:
            self.service.request_shutdown()
        if should_toggle_translate:
            self.service.toggle_translate_setting()
        if should_toggle_recording:
            if should_discard_pending:
                self.service.stop_recording(discard=True)
            self.service.toggle_recording("hotkey_toggle")
        elif should_discard_pending:
            self.service.stop_recording(discard=True)
        if should_arm_hold:
            self._arm_hold_to_talk()

    def release_token(self, token: str) -> None:
        should_stop = False
        should_discard = False

        with self._lock:
            self._pressed_keys.discard(token)

            if self._shutdown_active and not self._is_shutdown_combo_pressed_locked():
                self._shutdown_active = False
            if not self._hotkey_tokens_pressed_locked(self._translate_toggle_hotkey_tokens):
                self._active_actions.discard("translate_toggle")
            if not self._hotkey_tokens_pressed_locked(self._toggle_hotkey_tokens):
                self._active_actions.discard("recording_toggle")

            if self._pressed_key_matches(self._push_to_talk_key, token) and self._hold_candidate_active:
                status = self.service.recording_status()
                should_stop = status["recording"]
                should_discard = not self._hold_recording_started
                self._cancel_hold_locked()

        if should_stop:
            self.service.stop_recording(discard=should_discard)

    def _arm_hold_to_talk(self) -> None:
        with self._lock:
            status = self.service.recording_status()
            if self._hold_candidate_active or status["recording"] or status["transcribing"]:
                return
            self._hold_session_id += 1
            session_id = self._hold_session_id
            self._hold_candidate_active = True
            self._hold_recording_started = False

        self.service.start_recording("push_to_talk")
        if not self.service.recording_status()["recording"]:
            with self._lock:
                if self._hold_session_id == session_id:
                    self._cancel_hold_locked()
            return

        timer = threading.Timer(
            self.config.get_push_to_talk_threshold_ms() / 1000,
            self._activate_hold_to_talk,
            args=(session_id,),
        )
        timer.daemon = True
        timer.start()

    def _activate_hold_to_talk(self, session_id: int) -> None:
        with self._lock:
            if (
                not self._hold_candidate_active
                or self._hold_session_id != session_id
                or self._hold_recording_started
            ):
                return
            status = self.service.recording_status()
            if not status["recording"] or status["transcribing"]:
                self._cancel_hold_locked()
                return
            if (
                self._pressed_keys_can_match_hotkey_locked(self._toggle_hotkey_tokens)
                and not self._hotkey_tokens_pressed_locked(self._toggle_hotkey_tokens)
            ):
                timer = threading.Timer(0.05, self._activate_hold_to_talk, args=(session_id,))
                timer.daemon = True
                timer.start()
                return
            self._hold_recording_started = True

    def _refresh_hotkey_state(self) -> None:
        with self._lock:
            self._push_to_talk_key = self.config.get_push_to_talk_key()
            self._toggle_hotkey_tokens = set(Config.parse_hotkey_tokens(self.config.get_toggle_hotkey()))
            self._translate_toggle_hotkey_tokens = set(
                Config.parse_hotkey_tokens(self.config.get_translate_toggle_hotkey())
            )
            self._pressed_keys.clear()
            self._active_actions.clear()
            self._shutdown_active = False
            self._cancel_hold_locked()

    def _cancel_hold_locked(self) -> None:
        self._hold_candidate_active = False
        self._hold_recording_started = False

    def _set_status(
        self,
        enabled: bool,
        registered: bool,
        status: str,
        error: str | None,
    ) -> dict[str, Any]:
        payload = {
            "enabled": enabled,
            "registered": registered,
            "status": status,
            "error": error,
            "push_to_talk_key": self.config.get_push_to_talk_key(),
            "toggle_hotkey": self.config.get_toggle_hotkey(),
            "translate_toggle_hotkey": self.config.get_translate_toggle_hotkey(),
        }
        with self._lock:
            self._status = payload
        if self._on_status:
            self._on_status(payload)
        return payload

    @staticmethod
    def normalize_pressed_key(key: Any) -> str | None:
        if isinstance(key, str):
            return key.strip().lower() or None
        if keyboard is None:
            return None
        if isinstance(key, keyboard.KeyCode):
            return key.char.lower() if key.char else None
        key_map = {
            getattr(keyboard.Key, "ctrl", None): "ctrl",
            keyboard.Key.ctrl_r: "right_ctrl",
            keyboard.Key.ctrl_l: "left_ctrl",
            getattr(keyboard.Key, "alt", None): "alt",
            keyboard.Key.alt_r: "right_alt",
            keyboard.Key.alt_l: "left_alt",
            keyboard.Key.alt_gr: "right_alt",
            keyboard.Key.shift: "shift",
            keyboard.Key.shift_l: "left_shift",
            keyboard.Key.shift_r: "right_shift",
            keyboard.Key.enter: "enter",
            keyboard.Key.space: "space",
            keyboard.Key.tab: "tab",
            keyboard.Key.esc: "esc",
        }
        key_map.pop(None, None)
        return key_map.get(key, getattr(key, "name", None))

    @staticmethod
    def _pressed_key_matches(required_token: str, pressed_key: str) -> bool:
        equivalent_tokens = {
            "ctrl": {"ctrl", "left_ctrl", "right_ctrl"},
            "alt": {"alt", "left_alt", "right_alt"},
            "shift": {"shift", "left_shift", "right_shift"},
        }
        return pressed_key in equivalent_tokens.get(required_token, {required_token})

    def _hotkey_tokens_pressed_locked(self, required_tokens: set[str]) -> bool:
        if not required_tokens:
            return False
        return all(
            any(self._pressed_key_matches(required_token, pressed) for pressed in self._pressed_keys)
            for required_token in required_tokens
        )

    def _pressed_keys_can_match_hotkey_locked(self, required_tokens: set[str]) -> bool:
        if not required_tokens:
            return False
        return all(
            any(self._pressed_key_matches(required_token, pressed) for required_token in required_tokens)
            for pressed in self._pressed_keys
        )

    def _is_shutdown_combo_pressed_locked(self) -> bool:
        ctrl_pressed = any(self._pressed_key_matches("ctrl", key) for key in self._pressed_keys)
        alt_pressed = any(self._pressed_key_matches("alt", key) for key in self._pressed_keys)
        return ctrl_pressed and alt_pressed and "q" in self._pressed_keys
