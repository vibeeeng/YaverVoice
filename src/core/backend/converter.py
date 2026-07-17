"""Converter-domain behavior for BackendService."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.backend.common import BackendValidationError
from src.core.ffmpeg_utils import OUTPUT_FORMATS, convert_audio, is_ffmpeg_available


class ConverterMixin:
    def converter_status(self) -> dict[str, Any]:
        return self.get_ffmpeg_status()

    def converter_output_formats(self) -> list[dict[str, str]]:
        if not is_ffmpeg_available():
            return []
        return [{"key": key, "ext": config["ext"], "name": key.upper()} for key, config in OUTPUT_FORMATS.items()]

    def convert_file(self, token: str, output_format: str, output_path: str) -> dict[str, Any]:
        if not is_ffmpeg_available():
            return {"success": False, "message": "FFmpeg kurulu değil"}
        path = self._file_from_token(token, for_convert=True)
        output_format = str(output_format)
        if output_format not in OUTPUT_FORMATS:
            raise BackendValidationError(f"Unsupported output format: {output_format}")
        output = Path(str(output_path)).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        self._emit("converter.status", {"state": "processing", "format": output_format})
        self._start_daemon_thread(
            "sidecar-converter",
            self._finish_conversion,
            path,
            output,
            output_format,
        )
        return {
            "success": True,
            "accepted": True,
            "message": "Conversion started.",
            "display_path": str(output),
        }

    def _finish_conversion(self, path: Path, output: Path, output_format: str) -> None:
        try:
            success, message = convert_audio(str(path), str(output), output_format)
        except Exception as exc:
            success = False
            message = str(exc)
        payload = {
            "state": "complete" if success else "error",
            "success": success,
            "message": f"Başarıyla kaydedildi: {output}" if success else message,
            "display_path": str(output) if success else None,
        }
        self._emit("converter.status", payload)
