"""
Linux-specific desktop platform services.
"""

from __future__ import annotations

import os
from typing import Iterable

from src.platform.base import DesktopPlatform, RecordingProfile


class LinuxPlatform(DesktopPlatform):
    name = "linux"

    def global_hotkey_error(self) -> str | None:
        session_type = os.environ.get("XDG_SESSION_TYPE", "").strip().lower()
        if session_type == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
            return (
                "Global hold-to-talk hotkeys are unavailable on Wayland. "
                "Sign in with an X11 session to use Right Ctrl."
            )
        return None

    def paste_hotkey(self) -> tuple[str, ...]:
        return ("ctrl", "shift", "v")

    def resolve_recording_device(
        self,
        configured_index: int,
        recommended_index: int,
    ) -> int | None:
        del recommended_index
        if configured_index != -1:
            return configured_index
        return None

    def filter_input_devices(
        self,
        devices: Iterable[dict],
        host_apis: Iterable[dict],
    ) -> list[dict]:
        """Filter Linux microphones without demoting system default devices."""
        host_api_names = {
            index: str(api.get("name", ""))
            for index, api in enumerate(host_apis)
        }

        filtered_devices: list[dict] = []
        seen_names: set[str] = set()
        bluetooth_keywords = ["airpods", "bluetooth", "hands-free", "wireless", "bt ", "bth"]
        virtual_keywords = ["jack", "dmix"]

        for index, device in enumerate(devices):
            if device.get("max_input_channels", 0) <= 0:
                continue

            name = str(device.get("name", "")).strip()
            name_lower = name.lower()
            if "monitor" in name_lower:
                continue

            base_name = name.split("(")[0].strip() if "(" in name else name
            if base_name in seen_names:
                continue
            seen_names.add(base_name)

            is_bluetooth = any(keyword in name_lower for keyword in bluetooth_keywords)
            is_virtual = any(keyword in name_lower for keyword in virtual_keywords)
            sample_rate = int(device.get("default_samplerate", 0) or 0)
            hostapi_name = host_api_names.get(device.get("hostapi"), "")

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

    def get_recording_profile(
        self,
        configured_index: int,
        resolved_index: int | None,
        microphones: list[dict],
        default_sample_rate: int,
        default_channels: int,
    ) -> RecordingProfile:
        if configured_index != -1:
            device_sample_rate = self._find_microphone_sample_rate(resolved_index, microphones)
            sample_rate = device_sample_rate or default_sample_rate
        else:
            sample_rate = self._get_portaudio_default_input_sample_rate() or default_sample_rate

        return RecordingProfile(
            sample_rate=sample_rate,
            channels=default_channels,
            preprocessing_mode="standard",
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

    @staticmethod
    def _get_portaudio_default_input_sample_rate() -> int | None:
        try:
            import sounddevice as sd

            device_info = sd.query_devices(device=None, kind="input")
            sample_rate = int(device_info.get("default_samplerate", 0) or 0)
            return sample_rate if sample_rate > 0 else None
        except Exception as exc:
            print(f"Warning: Could not read Linux default input sample rate: {exc}")
            return None
