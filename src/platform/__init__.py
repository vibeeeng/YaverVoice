"""
Runtime-selected desktop platform services.
"""

from src.platform.base import DesktopPlatform
from src.platform.factory import create_desktop_platform, get_runtime_platform_name

__all__ = ["DesktopPlatform", "create_desktop_platform", "get_runtime_platform_name"]
