"""
Base desktop platform services shared by Windows and Linux runtimes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Iterable, Optional


DEFAULT_SCREEN_GEOMETRY = (1920, 1080)


@dataclass(frozen=True)
class RecordingProfile:
    """Runtime recording settings selected by the active desktop platform."""

    sample_rate: int
    channels: int
    preprocessing_mode: str = "standard"


class DesktopPlatform:
    """Provide desktop integration hooks with safe cross-platform defaults."""

    name = "unknown"
    START_BEEP_FREQ = 1000
    START_BEEP_DURATION = 200
    STOP_BEEP_FREQ = 700
    STOP_BEEP_DURATION = 200

    def is_windows(self) -> bool:
        return self.name == "windows"

    def is_linux(self) -> bool:
        return self.name == "linux"

    def has_graphical_session(self) -> bool:
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

    def global_hotkey_error(self) -> str | None:
        return None

    def get_primary_screen_geometry(self) -> tuple[int, int]:
        """Return the primary screen size with tkinter fallback."""
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            screen_width = int(root.winfo_screenwidth())
            screen_height = int(root.winfo_screenheight())
            root.destroy()
            if screen_width > 0 and screen_height > 0:
                return screen_width, screen_height
        except Exception as exc:
            print(f"Warning: Could not read screen geometry via tkinter: {exc}")

        return DEFAULT_SCREEN_GEOMETRY

    def get_preferred_input_hostapis(self) -> set[str]:
        return set()

    def filter_input_devices(
        self,
        devices: Iterable[dict],
        host_apis: Iterable[dict],
    ) -> list[dict]:
        """Filter microphone devices while respecting platform-specific host APIs."""
        preferred_hostapis = self.get_preferred_input_hostapis()
        host_api_names = {
            index: str(api.get("name", ""))
            for index, api in enumerate(host_apis)
        }

        filtered_devices: list[dict] = []
        seen_names: set[str] = set()
        bluetooth_keywords = ["airpods", "bluetooth", "hands-free", "wireless", "bt ", "bth"]
        virtual_keywords = ["default", "sysdefault", "pipewire", "pulse", "monitor", "jack", "dmix"]

        for index, device in enumerate(devices):
            if device.get("max_input_channels", 0) <= 0:
                continue

            name = str(device.get("name", "")).strip()
            hostapi_index = device.get("hostapi")
            hostapi_name = host_api_names.get(hostapi_index, "")

            if preferred_hostapis and hostapi_name not in preferred_hostapis:
                continue

            skip_keywords = ["Microsoft Ses", "Birincil Ses", "Stereo", "@System32", "Mapper"]
            if any(keyword.lower() in name.lower() for keyword in skip_keywords):
                continue

            base_name = name.split("(")[0].strip() if "(" in name else name
            if base_name in seen_names:
                continue
            seen_names.add(base_name)

            is_bluetooth = any(keyword in name.lower() for keyword in bluetooth_keywords)
            is_virtual = any(keyword in name.lower() for keyword in virtual_keywords)
            sample_rate = int(device.get("default_samplerate", 0) or 0)

            display_name = f"{name} ({sample_rate} Hz)" if sample_rate else name
            if is_bluetooth:
                display_name = f"Warning: {display_name} - Bluetooth"
            elif is_virtual:
                display_name = f"{display_name} - Virtual"

            filtered_devices.append(
                {
                    "index": index,
                    "name": display_name,
                    "sample_rate": sample_rate,
                    "is_bluetooth": is_bluetooth,
                    "is_virtual": is_virtual,
                    "hostapi": hostapi_name,
                }
            )

        filtered_devices.sort(
            key=lambda item: (
                item.get("is_virtual", False),
                item.get("is_bluetooth", False),
                item["name"].lower(),
            )
        )
        return filtered_devices

    def get_recommended_microphone(self, microphones: list[dict]) -> int:
        for mic in microphones:
            if not mic.get("is_virtual", False) and not mic.get("is_bluetooth", False):
                return mic["index"]
        for mic in microphones:
            if not mic.get("is_virtual", False):
                return mic["index"]
        return microphones[0]["index"] if microphones else -1

    def resolve_recording_device(
        self,
        configured_index: int,
        recommended_index: int,
    ) -> Optional[int]:
        del recommended_index
        if configured_index != -1:
            return configured_index
        return None

    def get_recording_profile(
        self,
        configured_index: int,
        resolved_index: Optional[int],
        microphones: list[dict],
        default_sample_rate: int,
        default_channels: int,
    ) -> RecordingProfile:
        del configured_index, resolved_index, microphones
        return RecordingProfile(
            sample_rate=default_sample_rate,
            channels=default_channels,
            preprocessing_mode="standard",
        )

    def should_log_recording_diagnostics(self) -> bool:
        return False

    def get_quick_dictation_window_options(self) -> dict[str, Any]:
        return {
            "width": 196,
            "height": 64,
            "min_size": (196, 64),
            "transparent": True,
            "background_color": "#000000",
        }

    def paste_hotkey(self) -> tuple[str, ...]:
        return ("ctrl", "v")

    def paste_clipboard(self, pyautogui) -> bool:
        pyautogui.hotkey(*self.paste_hotkey())
        return True

    def play_start_beep(self, enabled: bool) -> None:
        if enabled:
            self._play_beep(self.START_BEEP_FREQ, self.START_BEEP_DURATION)

    def play_stop_beep(self, enabled: bool) -> None:
        if enabled:
            self._play_beep(self.STOP_BEEP_FREQ, self.STOP_BEEP_DURATION)

    def on_tray_started(self) -> None:
        """Hook invoked after the tray icon starts."""

    @staticmethod
    def _play_beep(frequency: int, duration: int) -> None:
        del frequency, duration
        try:
            print("\a", end="", flush=True)
        except Exception:
            pass
