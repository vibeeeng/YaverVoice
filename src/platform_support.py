"""
Compatibility wrapper for platform-specific desktop helpers.
"""

from __future__ import annotations

from typing import Iterable

from src.platform import create_desktop_platform, get_runtime_platform_name


_PLATFORM = create_desktop_platform()


def get_runtime_platform() -> str:
    """Return a stable platform label used by the app."""
    return get_runtime_platform_name()


def is_windows() -> bool:
    """Return True on Windows runtimes."""
    return _PLATFORM.is_windows()


def is_linux() -> bool:
    """Return True on Linux runtimes."""
    return _PLATFORM.is_linux()


def has_graphical_session() -> bool:
    """Return True when a desktop session is available."""
    return _PLATFORM.has_graphical_session()


def get_primary_screen_geometry() -> tuple[int, int]:
    """Return the primary screen size with platform-aware fallbacks."""
    return _PLATFORM.get_primary_screen_geometry()


def get_preferred_input_hostapis() -> set[str]:
    """Return preferred audio host APIs for the current runtime."""
    return _PLATFORM.get_preferred_input_hostapis()


def filter_input_devices(
    devices: Iterable[dict],
    host_apis: Iterable[dict],
) -> list[dict]:
    """Filter microphone devices while respecting platform-specific host APIs."""
    return _PLATFORM.filter_input_devices(devices, host_apis)
