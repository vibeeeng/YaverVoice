"""
Factory helpers for selecting the runtime desktop platform implementation.
"""

from __future__ import annotations

import sys

from src.platform.base import DesktopPlatform
from src.platform.linux import LinuxPlatform
from src.platform.windows import WindowsPlatform


def get_runtime_platform_name() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "macos"
    return sys.platform


def create_desktop_platform() -> DesktopPlatform:
    runtime_name = get_runtime_platform_name()
    if runtime_name == "windows":
        return WindowsPlatform()
    if runtime_name == "linux":
        return LinuxPlatform()
    return DesktopPlatform()
