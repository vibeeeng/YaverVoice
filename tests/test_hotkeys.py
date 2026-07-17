from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from src.config import Config
from src.core.hotkeys import HotkeyController


class FakePlatform:
    def has_graphical_session(self) -> bool:
        return True


class FakeService:
    def __init__(self) -> None:
        self.recording = False
        self.transcribing = False
        self.mode = "standard"
        self.starts: list[str] = []
        self.stops: list[bool] = []
        self.toggle_translate_calls = 0
        self.shutdown_calls = 0

    def recording_status(self) -> dict[str, object]:
        return {"recording": self.recording, "transcribing": self.transcribing, "mode": self.mode}

    def start_recording(self, mode: str = "standard") -> dict[str, object]:
        self.recording = True
        self.mode = mode
        self.starts.append(mode)
        return self.recording_status()

    def stop_recording(self, *, discard: bool = False) -> dict[str, object]:
        self.recording = False
        self.stops.append(discard)
        return self.recording_status()

    def toggle_recording(self, mode: str = "standard") -> dict[str, object]:
        if self.recording:
            return self.stop_recording()
        return self.start_recording(mode)

    def toggle_translate_setting(self) -> dict[str, object]:
        self.toggle_translate_calls += 1
        return {"success": True}

    def request_shutdown(self) -> dict[str, bool]:
        self.shutdown_calls += 1
        return {"success": True}


class HotkeyControllerTests(unittest.TestCase):
    def make_controller(self, env_lines: list[str]) -> tuple[HotkeyController, FakeService]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        env_path = Path(temp_dir.name) / ".env"
        env_path.write_text("\n".join(env_lines), encoding="utf-8")
        config = Config(str(env_path))
        config.reload_env()
        service = FakeService()
        controller = HotkeyController(
            service=service,  # type: ignore[arg-type]
            config=config,
            platform=FakePlatform(),  # type: ignore[arg-type]
        )
        return controller, service

    def test_right_ctrl_release_before_threshold_discards_recording(self):
        with patch.dict(os.environ, {}, clear=True):
            controller, service = self.make_controller(["PUSH_TO_TALK_THRESHOLD_MS=50"])
            controller.press_token("right_ctrl")
            controller.release_token("right_ctrl")
            time.sleep(0.07)

        self.assertEqual(service.starts, ["push_to_talk"])
        self.assertEqual(service.stops, [True])

    def test_right_ctrl_release_after_threshold_stops_for_transcription(self):
        with patch.dict(os.environ, {}, clear=True):
            controller, service = self.make_controller(["PUSH_TO_TALK_THRESHOLD_MS=5"])
            controller.press_token("right_ctrl")
            time.sleep(0.03)
            controller.release_token("right_ctrl")

        self.assertEqual(service.starts, ["push_to_talk"])
        self.assertEqual(service.stops, [False])

    def test_alt_r_toggle_debounces_until_release(self):
        with patch.dict(os.environ, {}, clear=True):
            controller, service = self.make_controller([])
            controller.press_token("left_alt")
            controller.press_token("r")
            controller.press_token("r")
            controller.release_token("r")
            controller.press_token("r")

        self.assertEqual(service.starts, ["hotkey_toggle"])
        self.assertEqual(service.stops, [False])

    def test_shift_t_toggles_translate_once_per_chord(self):
        with patch.dict(os.environ, {}, clear=True):
            controller, service = self.make_controller([])
            controller.press_token("left_shift")
            controller.press_token("t")
            controller.press_token("t")
            controller.release_token("t")
            controller.press_token("t")

        self.assertEqual(service.toggle_translate_calls, 2)

    def test_hotkey_state_uses_reloaded_config(self):
        with patch.dict(os.environ, {}, clear=True):
            controller, service = self.make_controller([])
            controller.config.save_hotkey_settings(
                recording_trigger_mode="hold_to_talk",
                push_to_talk_key="right_ctrl",
                toggle_hotkey="<alt>+x",
                translate_toggle_hotkey="<shift>+t",
            )
            controller.refresh_config()
            controller.press_token("left_alt")
            controller.press_token("r")
            controller.release_token("r")
            controller.press_token("x")

        self.assertEqual(service.starts, ["hotkey_toggle"])


if __name__ == "__main__":
    unittest.main()
