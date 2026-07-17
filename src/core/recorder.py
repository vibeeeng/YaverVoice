"""
Audio Recorder Module - Captures audio from microphone and saves to .wav file.
Uses sounddevice and numpy for non-blocking audio capture.
"""

import numpy as np
import wave
import threading
from pathlib import Path
from typing import Optional

from src.config import Config


class AudioRecorder:
    """
    Non-blocking audio recorder using sounddevice and numpy.

    Features:
    - Records in separate thread (non-blocking)
    - Saves to temporary .wav file
    - Applies light preprocessing for live speech clarity
    - Configurable sample rate and channels
    - Graceful interruption handling
    """

    SILENCE_THRESHOLD = 0.015
    SILENCE_WINDOW_MS = 30
    SILENCE_PADDING_MS = 150
    NORMALIZATION_TARGET_PEAK = 0.92
    MAX_NORMALIZATION_GAIN = 8.0
    PREVIEW_MIN_DURATION_SECONDS = 0.5
    PREVIEW_WINDOW_SECONDS = 4.0
    PREVIEW_CONTEXT_SECONDS = 1.0
    PAUSE_WINDOW_SECONDS = 0.6
    PAUSE_ENERGY_THRESHOLD = 0.006
    PAUSE_PEAK_THRESHOLD = 0.025

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        temp_dir: Optional[Path] = None,
    ):
        """
        Initialize the audio recorder.

        Args:
            sample_rate: Audio sample rate in Hz (default: 16000 for Groq compatibility)
            channels: Number of audio channels (1=mono, 2=stereo)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.preprocessing_mode = "standard"
        self._actual_sample_rate = sample_rate  # May differ per device
        self._temp_dir = temp_dir

        # Recording state
        self._is_recording = False
        self._recording_thread: Optional[threading.Thread] = None
        self._recorded_frames = []
        self._audio_file_path: Optional[str] = None
        self._last_error: Optional[str] = None
        self._frames_lock = threading.Lock()

    def start_recording(
        self,
        device_index: Optional[int] = None,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None,
        preprocessing_mode: Optional[str] = None,
        log_diagnostics: bool = False,
    ) -> None:
        """
        Start audio recording in a separate thread.

        Args:
            device_index: Microphone device index (None for system default)
            sample_rate: Per-recording sample rate override
            channels: Per-recording channel count override
            preprocessing_mode: Per-recording preprocessing profile
            log_diagnostics: Print stream/device details after opening

        Returns:
            None (returns immediately, recording happens in background)
        """
        if self._is_recording:
            raise RuntimeError("Recording is already in progress")

        if sample_rate is not None:
            self.sample_rate = int(sample_rate)
            self._actual_sample_rate = self.sample_rate
        if channels is not None:
            self.channels = int(channels)
        if preprocessing_mode is not None:
            self.preprocessing_mode = preprocessing_mode

        self._is_recording = True
        with self._frames_lock:
            self._recorded_frames = []
        self._audio_file_path = None
        self._last_error = None

        # Start recording thread
        self._recording_thread = threading.Thread(
            target=self._record_thread,
            args=(device_index, log_diagnostics),
            daemon=True
        )
        self._recording_thread.start()

    def stop_recording(self) -> Optional[str]:
        """
        Stop recording and save to temporary .wav file.

        Returns:
            Path to the saved .wav file, or None if recording wasn't active
        """
        if not self._is_recording:
            return None

        # Signal thread to stop
        self._is_recording = False

        # Wait for thread to finish
        if self._recording_thread:
            self._recording_thread.join(timeout=5.0)
            self._recording_thread = None

        # Save to WAV file
        with self._frames_lock:
            has_frames = bool(self._recorded_frames)

        if has_frames:
            self._audio_file_path = self._save_to_wav()

        return self._audio_file_path

    def is_recording(self) -> bool:
        """Check if recording is currently active."""
        return self._is_recording

    def get_last_file(self) -> Optional[str]:
        """Get the path to the most recently recorded file."""
        return self._audio_file_path

    def get_last_error(self) -> Optional[str]:
        """Get the last recording error, if any."""
        return self._last_error

    def _record_thread(self, device_index: Optional[int], log_diagnostics: bool = False) -> None:
        """
        Recording loop running in separate thread.

        Args:
            device_index: Microphone device index
            log_diagnostics: Print stream/device details after opening
        """
        sd = self._load_sounddevice()
        if sd is None:
            self._last_error = "sounddevice/PortAudio is unavailable on this system"
            print(f"Recording error: {self._last_error}")
            self._is_recording = False
            return

        attempts: list[tuple[Optional[int], str]] = []
        if device_index is not None:
            attempts.append((device_index, f"device {device_index}"))
            new_index = self._find_device_index_by_old_index(device_index)
            if new_index is not None and new_index != device_index:
                attempts.append((new_index, f"new device index {new_index}"))
        attempts.append((None, "default system microphone"))

        last_error: Exception | None = None
        for attempt_device_index, label in attempts:
            try:
                print(f"Opening stream for {label}...")
                stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype=np.float32,
                    device=attempt_device_index,
                    callback=self._audio_callback,
                )

                with stream:
                    self._actual_sample_rate = int(stream.samplerate)
                    if log_diagnostics:
                        self._log_recording_diagnostics(sd, stream, attempt_device_index)
                    print(f"Recording started. Sample rate: {self._actual_sample_rate} Hz")

                    while self._is_recording:
                        sd.sleep(100)
                return
            except Exception as exc:
                last_error = exc
                print(f"Recording stream failed for {label}: {exc}")

        self._last_error = str(last_error) if last_error else "No recording device could be opened"
        print(f"Recording error: {self._last_error}")
        self._is_recording = False

    def _audio_callback(self, indata, frames, time, status) -> None:
        """
        Callback function for audio stream.

        Args:
            indata: Audio data chunk (numpy array)
            frames: Number of frames
            time: Timestamp info
            status: Stream status
        """
        if status:
            print(f"Stream status: {status}")

        # Store audio chunk
        if self._is_recording:
            with self._frames_lock:
                self._recorded_frames.append(indata.copy())

    def _log_recording_diagnostics(self, sd, stream, requested_device_index: Optional[int]) -> None:
        """Print concise stream diagnostics for investigating platform recording quality."""
        try:
            selected_index = self._get_stream_input_device_index(sd, stream, requested_device_index)
            device_info = sd.query_devices(selected_index) if selected_index is not None else None
            hostapi_name = ""
            if device_info is not None:
                hostapis = sd.query_hostapis()
                hostapi_index = device_info.get("hostapi")
                if hostapi_index is not None and 0 <= hostapi_index < len(hostapis):
                    hostapi_name = str(hostapis[hostapi_index].get("name", ""))

            selected_name = str(device_info.get("name", "")) if device_info is not None else "system default"
            print(
                "[recording diagnostics] "
                f"selected_device_index={selected_index}, "
                f"selected_device_name={selected_name}, "
                f"hostapi={hostapi_name or 'unknown'}, "
                f"requested_sample_rate={self.sample_rate}, "
                f"actual_stream_sample_rate={int(stream.samplerate)}, "
                f"channels={self.channels}, "
                f"preprocessing={self.preprocessing_mode}"
            )
        except Exception as exc:
            print(f"[recording diagnostics] unavailable: {exc}")

    @staticmethod
    def _get_stream_input_device_index(sd, stream, requested_device_index: Optional[int]) -> Optional[int]:
        if requested_device_index is not None:
            return requested_device_index

        stream_device = getattr(stream, "device", None)
        if isinstance(stream_device, (list, tuple)) and stream_device:
            return stream_device[0]
        if isinstance(stream_device, int):
            return stream_device

        default_device = getattr(sd, "default", None)
        default_device = getattr(default_device, "device", None)
        if isinstance(default_device, (list, tuple)) and default_device:
            default_input = default_device[0]
            return default_input if default_input is not None and default_input >= 0 else None
        if isinstance(default_device, int) and default_device >= 0:
            return default_device

        return None

    def _save_to_wav(self) -> str:
        """
        Save recorded audio to temporary WAV file.

        Returns:
            Path to the saved .wav file
        """
        # Generate unique filename with timestamp
        import time
        timestamp = int(time.time() * 1000)
        temp_file = self._get_temp_dir() / f"recording_{timestamp}.wav"

        with self._frames_lock:
            audio_data = np.concatenate(self._recorded_frames, axis=0)

        audio_data = self._prepare_audio_for_transcription(audio_data, mode="final")
        return self._write_wav_file(temp_file, audio_data)

    def export_preview_snapshot(
        self,
        min_duration_seconds: float | None = None,
        recent_window_seconds: float | None = None,
        leading_context_seconds: float | None = None,
    ) -> Optional[str]:
        """Export a temporary WAV snapshot of the active live recording."""
        if min_duration_seconds is None:
            min_duration_seconds = self.PREVIEW_MIN_DURATION_SECONDS
        if recent_window_seconds is None:
            recent_window_seconds = self.PREVIEW_WINDOW_SECONDS
        if leading_context_seconds is None:
            leading_context_seconds = self.PREVIEW_CONTEXT_SECONDS

        with self._frames_lock:
            if not self._recorded_frames:
                return None

            actual_sample_rate = self._actual_sample_rate
            target_seconds = recent_window_seconds + leading_context_seconds
            max_frames = int(max(actual_sample_rate, 1) * max(target_seconds, min_duration_seconds))
            audio_data = self._collect_recent_frames_locked(max_frames)

        duration_seconds = len(audio_data) / max(actual_sample_rate, 1)
        if duration_seconds < min_duration_seconds:
            return None

        preview_data = self._prepare_audio_for_transcription(audio_data, mode="preview")
        if preview_data.size == 0:
            return None

        import time
        timestamp = int(time.time() * 1000)
        preview_file = self._get_temp_dir() / f"preview_{timestamp}.wav"
        return self._write_wav_file(preview_file, preview_data)

    def _collect_recent_frames_locked(self, max_frames: int) -> np.ndarray:
        """Collect only the newest frames needed for preview while holding the frame lock."""
        if max_frames <= 0:
            return np.empty((0, self.channels), dtype=np.float32)

        chunks: list[np.ndarray] = []
        collected_frames = 0

        for frame_chunk in reversed(self._recorded_frames):
            chunks.append(frame_chunk)
            collected_frames += len(frame_chunk)
            if collected_frames >= max_frames:
                break

        if not chunks:
            return np.empty((0, self.channels), dtype=np.float32)

        recent_audio = np.concatenate(list(reversed(chunks)), axis=0)
        if len(recent_audio) > max_frames:
            recent_audio = recent_audio[-max_frames:]

        return recent_audio

    def is_recent_pause(
        self,
        window_seconds: float | None = None,
        energy_threshold: float | None = None,
    ) -> bool:
        """Return True when the newest audio window looks like a short pause."""
        if window_seconds is None:
            window_seconds = self.PAUSE_WINDOW_SECONDS
        if energy_threshold is None:
            energy_threshold = self.PAUSE_ENERGY_THRESHOLD

        with self._frames_lock:
            if not self._recorded_frames:
                return False

            max_frames = int(max(self._actual_sample_rate, 1) * window_seconds)
            recent_audio = self._collect_recent_frames_locked(max_frames)

        if recent_audio.size == 0:
            return False

        if recent_audio.ndim > 1:
            mono = np.mean(recent_audio, axis=1)
        else:
            mono = recent_audio

        rms_energy = float(np.sqrt(np.mean(np.square(mono))))
        peak_energy = float(np.max(np.abs(mono)))

        return (
            rms_energy < energy_threshold
            and peak_energy < self.PAUSE_PEAK_THRESHOLD
        )

    def _prepare_audio_for_transcription(self, audio_data: np.ndarray, mode: str = "final") -> np.ndarray:
        """Apply conservative preprocessing to improve live speech clarity."""
        if audio_data.size == 0:
            return audio_data

        processed = audio_data.astype(np.float32, copy=True)

        # Remove DC offset before amplitude checks.
        processed -= np.mean(processed, axis=0, keepdims=True)

        if self.preprocessing_mode == "windows_quality":
            return np.clip(processed, -1.0, 1.0)

        trim_trailing = False if mode in {"preview", "final"} else True
        trimmed = self._trim_silence(processed, trim_trailing=trim_trailing)
        if trimmed.size > 0:
            processed = trimmed

        peak = float(np.max(np.abs(processed))) if processed.size else 0.0
        if peak > 0:
            gain = min(self.NORMALIZATION_TARGET_PEAK / peak, self.MAX_NORMALIZATION_GAIN)
            processed *= gain

        return np.clip(processed, -1.0, 1.0)

    def _trim_silence(self, audio_data: np.ndarray, trim_trailing: bool = False) -> np.ndarray:
        """Trim low-energy silence from the edges of a live recording."""
        if audio_data.size == 0:
            return audio_data

        if audio_data.ndim > 1:
            amplitude = np.max(np.abs(audio_data), axis=1)
        else:
            amplitude = np.abs(audio_data)

        window_frames = max(
            1,
            int(self._actual_sample_rate * self.SILENCE_WINDOW_MS / 1000),
        )
        padding_frames = int(self._actual_sample_rate * self.SILENCE_PADDING_MS / 1000)

        if window_frames > 1 and amplitude.size >= window_frames:
            kernel = np.ones(window_frames, dtype=np.float32) / window_frames
            smoothed = np.convolve(amplitude, kernel, mode="same")
        else:
            smoothed = amplitude

        speech_indices = np.flatnonzero(smoothed >= self.SILENCE_THRESHOLD)
        if speech_indices.size == 0:
            return audio_data

        start_idx = max(0, int(speech_indices[0]) - padding_frames)
        end_idx = len(amplitude)
        if trim_trailing:
            end_idx = min(len(amplitude), int(speech_indices[-1]) + padding_frames + 1)

        if end_idx <= start_idx:
            return audio_data

        return audio_data[start_idx:end_idx]

    def _get_temp_dir(self) -> Path:
        """Resolve the temp directory used for live recording artifacts."""
        if self._temp_dir is not None:
            self._temp_dir.mkdir(parents=True, exist_ok=True)
            return self._temp_dir
        return Config.get_temp_dir()

    def _write_wav_file(self, filepath: Path, audio_data: np.ndarray) -> str:
        """Persist preprocessed audio as a mono/stereo WAV file."""
        audio_int16 = np.clip(audio_data, -1.0, 1.0)
        audio_int16 = (audio_int16 * 32767).astype(np.int16)

        with wave.open(str(filepath), 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self._actual_sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

        return str(filepath)

    def cleanup_temp_files(self) -> None:
        """
        Delete all recording files from the temp directory.
        Call this to free up disk space.
        """
        temp_dir = self._get_temp_dir()

        if temp_dir.exists():
            for pattern in ("recording_*.wav", "preview_*.wav", "upload_*.wav"):
                for file in temp_dir.glob(pattern):
                    try:
                        file.unlink()
                    except Exception as e:
                        print(f"Warning: Could not delete {file}: {e}")

    def get_available_devices(self) -> list:
        """
        Get list of available input devices.

        Returns:
            List of device names
        """
        devices = []
        try:
            sd = self._load_sounddevice()
            if sd is None:
                return ["No input backend available"]

            device_list = sd.query_devices()
            for i, device in enumerate(device_list):
                if device['max_input_channels'] > 0:
                    devices.append(f"{i}: {device['name']}")
        except Exception as e:
            print(f"Error querying devices: {e}")
            devices = ["Default Device"]

        return devices

    def _find_device_index_by_old_index(self, old_index: int) -> Optional[int]:
        """
        Attempt to find a device's new index if check failed.
        This is useful because PortAudio device indices can shift.
        """
        try:
            sd = self._load_sounddevice()
            if sd is None:
                return None

            # We can't really know the old name if we only have the index,
            # unless we stored it. But here we can try to guess or just refresh.
            # Strategy: Refresh logs to see current state (this is a blind retry usually)

            # Better strategy: List all devices, if we are looking for 'AirPods'
            # and the user selected an index that WAS airpods, maybe we can find it again?
            # Since we don't have the original name stored in this class instance easily
            # (unless we change API), we will try a heuristic:
            # Check if there is ANY device with the same name as what we expect?
            # No, we don't know the name.

            # Alternative: Just return None for now unless we store names.
            # BUT, we can try to query the device name using the OLD index
            # (often querying name works even if opening stream fails?)
            # No, if device is gone, query might fail or return different device.

            # Let's try to query the failing index to see what it *thinks* it is
            try:
                bad_device = sd.query_devices(old_index)
                target_name = bad_device['name']
                # If we got a name, search for it in current list
                current_devices = sd.query_devices()
                for i, dev in enumerate(current_devices):
                    if dev['name'] == target_name and dev['max_input_channels'] > 0:
                        # Found a match with same name!
                        return i
            except:
                pass

            return None
        except Exception:
            return None

    @staticmethod
    def _load_sounddevice():
        """Load sounddevice lazily so missing system libraries don't kill startup."""
        try:
            import sounddevice as sd

            return sd
        except Exception as e:
            print(f"sounddevice unavailable: {e}")
            return None


# Standalone test
def test_recorder():
    """Test the audio recorder standalone."""
    print("Audio Recorder Test")
    print("=" * 40)

    recorder = AudioRecorder()

    # Show available devices
    devices = recorder.get_available_devices()
    print("\nAvailable audio devices:")
    for device in devices:
        print(f"  {device}")

    print("\nInstructions:")
    print("1. Recording will start for 5 seconds")
    print("2. Speak into your microphone")
    print("3. Recording will stop and save to .wav file")
    print("\nPress Enter to start...")
    input()

    # Start recording
    print("Recording... (speak now!)")
    recorder.start_recording()

    # Record for 5 seconds
    import time
    time.sleep(5)

    # Stop recording
    print("Stopping recording...")
    file_path = recorder.stop_recording()

    if file_path:
        print(f"Audio saved to: {file_path}")
        print(f"File size: {Path(file_path).stat().st_size / 1024:.2f} KB")
    else:
        print("No audio was recorded.")


if __name__ == "__main__":
    test_recorder()
