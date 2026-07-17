"""
Windows-specific desktop platform services.
"""

from __future__ import annotations

from typing import Any

from src.platform.base import DesktopPlatform, RecordingProfile


class WindowsPlatform(DesktopPlatform):
    name = "windows"

    def has_graphical_session(self) -> bool:
        return True

    def get_primary_screen_geometry(self) -> tuple[int, int]:
        try:
            import ctypes

            user32 = ctypes.windll.user32
            try:
                user32.SetProcessDPIAware()
            except Exception:
                pass

            screen_width = int(user32.GetSystemMetrics(0))
            screen_height = int(user32.GetSystemMetrics(1))
            if screen_width > 0 and screen_height > 0:
                return screen_width, screen_height
        except Exception as exc:
            print(f"Warning: Could not read Windows screen geometry: {exc}")

        return super().get_primary_screen_geometry()

    def get_preferred_input_hostapis(self) -> set[str]:
        return {"Windows WASAPI", "WASAPI"}

    def get_recommended_microphone(self, microphones: list[dict]) -> int:
        def score(mic: dict) -> tuple[int, str]:
            name = str(mic.get("name", "")).lower()
            hostapi = str(mic.get("hostapi", "")).lower()
            is_virtual = bool(mic.get("is_virtual", False))
            is_bluetooth = bool(mic.get("is_bluetooth", False))
            is_wasapi = "wasapi" in hostapi
            is_microphone = "microphone" in name or "mikrofon" in name
            is_realtek = "realtek" in name

            return (
                1 if is_virtual else 0,
                1 if is_bluetooth else 0,
                0 if is_wasapi else 1,
                0 if is_realtek else 1,
                0 if is_microphone else 1,
                name,
            )

        if not microphones:
            return -1

        return min(microphones, key=score)["index"]

    def resolve_recording_device(
        self,
        configured_index: int,
        recommended_index: int,
    ) -> int | None:
        if configured_index != -1:
            return configured_index
        return recommended_index if recommended_index != -1 else None

    def get_recording_profile(
        self,
        configured_index: int,
        resolved_index: int | None,
        microphones: list[dict],
        default_sample_rate: int,
        default_channels: int,
    ) -> RecordingProfile:
        del configured_index
        device_sample_rate = self._find_microphone_sample_rate(resolved_index, microphones)
        sample_rate = device_sample_rate or default_sample_rate

        return RecordingProfile(
            sample_rate=sample_rate,
            channels=1,
            preprocessing_mode="windows_quality",
        )

    @staticmethod
    def _find_microphone_sample_rate(
        device_index: int | None,
        microphones: list[dict],
    ) -> int | None:
        if device_index is None:
            return None

        for mic in microphones:
            if mic.get("index") == device_index:
                sample_rate = int(mic.get("sample_rate", 0) or 0)
                return sample_rate if sample_rate > 0 else None

        return None

    def should_log_recording_diagnostics(self) -> bool:
        return True

    def get_quick_dictation_window_options(self) -> dict[str, Any]:
        return {
            "width": 196,
            "height": 64,
            "min_size": (196, 64),
            "transparent": False,
            "background_color": "#070A12",
        }


    def on_tray_started(self) -> None:
        try:
            import ctypes

            shell32 = ctypes.windll.shell32
            try:
                shell32.SHChangeNotify(0x0800, 0x1000, None, None)
            except Exception:
                pass
        except Exception:
            pass

    @staticmethod
    def _play_beep(frequency: int, duration: int) -> None:
        try:
            import winsound

            winsound.Beep(frequency, duration)
        except Exception:
            DesktopPlatform._play_beep(frequency, duration)
