"""
Sound Feedback Module - Audio cues for recording state changes.
"""

from typing import Callable

from src.platform import create_desktop_platform


class SoundFeedback:
    """
    Platform-aware sound feedback wrapper.
    """

    def __init__(self, enabled_check: Callable[[], bool], platform=None):
        """
        Initialize sound feedback.

        Args:
            enabled_check: Callable that returns True if beep sounds are enabled
        """
        self._enabled = enabled_check
        self._platform = platform or create_desktop_platform()

    def play_start_beep(self) -> None:
        """
        Play start recording beep sound.

        High-pitched beep (1000Hz) to indicate recording has started.
        Only plays if user has enabled beep sounds and platform is Windows.
        """
        self._platform.play_start_beep(self._enabled())

    def play_stop_beep(self) -> None:
        """
        Play stop recording beep sound.

        Lower-pitched beep (700Hz) to indicate recording has stopped.
        Only plays if user has enabled beep sounds and platform is Windows.
        """
        self._platform.play_stop_beep(self._enabled())

    def is_enabled(self) -> bool:
        """
        Check if beep sounds are enabled.

        Returns:
            True if enabled, False otherwise
        """
        return self._enabled()
