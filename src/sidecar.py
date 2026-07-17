"""
Stdio JSON-RPC sidecar entrypoint for headless YaverVoice integrations.

Run with:
    python -m src.sidecar

Protocol:
    newline-delimited JSON-RPC 2.0 requests on stdin
    JSON-RPC responses/events only on stdout
    logs and diagnostics on stderr
"""

from __future__ import annotations

import contextlib
import json
import sys
import threading
from dataclasses import dataclass
from typing import Any, Callable, TextIO

from src.core.backend_service import BackendService, BackendValidationError
from src.core.hotkeys import HotkeyController


PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class JsonRpcError(Exception):
    """JSON-RPC error with a protocol code."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class JsonRpcRequest:
    request_id: Any
    method: str
    params: dict[str, Any]


class SidecarJsonRpcServer:
    """Small newline-delimited JSON-RPC dispatcher."""

    def __init__(
        self,
        service: BackendService | None = None,
        *,
        event_writer: Callable[[dict[str, Any]], None] | None = None,
        enable_hotkeys: bool = False,
    ) -> None:
        self._pending_events: list[dict[str, Any]] = []
        self._collecting_events = False
        self._event_writer = event_writer
        self._event_lock = threading.RLock()
        self.service = service or BackendService(on_event=self.queue_event)
        self.hotkeys: HotkeyController | None = None
        self._hotkey_status_events_enabled = False
        if enable_hotkeys:
            self.hotkeys = HotkeyController(
                service=self.service,
                config=self.service.config,
                platform=self.service.platform,
                on_status=self._queue_hotkey_status,
            )
            self.service._on_hotkeys_reload = self.reload_hotkeys
            self.hotkeys.start()
            self._hotkey_status_events_enabled = True

    def parse_request(self, line: str) -> JsonRpcRequest:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise JsonRpcError(PARSE_ERROR, "Parse error") from exc

        if not isinstance(payload, dict):
            raise JsonRpcError(INVALID_REQUEST, "Invalid Request")
        if payload.get("jsonrpc") != "2.0":
            raise JsonRpcError(INVALID_REQUEST, "Invalid Request")
        if "method" not in payload or not isinstance(payload["method"], str):
            raise JsonRpcError(INVALID_REQUEST, "Invalid Request")
        if "id" not in payload:
            raise JsonRpcError(INVALID_REQUEST, "Invalid Request")

        params = payload.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise JsonRpcError(INVALID_PARAMS, "Invalid params")

        return JsonRpcRequest(request_id=payload["id"], method=payload["method"], params=params)

    def handle_line(self, line: str) -> dict[str, Any]:
        return self.handle_line_messages(line)[-1]

    def handle_line_messages(self, line: str) -> list[dict[str, Any]]:
        with self._event_lock:
            self._pending_events = []
            self._collecting_events = True
        try:
            request = self.parse_request(line)
            result = self.dispatch(request.method, request.params)
            response = {"jsonrpc": "2.0", "id": request.request_id, "result": result}
        except JsonRpcError as exc:
            request_id = self._extract_request_id(line)
            response = self.error_response(request_id, exc.code, exc.message)
        except BackendValidationError as exc:
            request_id = self._extract_request_id(line)
            response = self.error_response(request_id, INVALID_PARAMS, str(exc) or "Invalid params")
        except ValueError as exc:
            request_id = self._extract_request_id(line)
            response = self.error_response(request_id, INVALID_PARAMS, str(exc) or "Invalid params")
        except Exception as exc:
            print(f"[sidecar] Internal error: {exc}", file=sys.stderr)
            request_id = self._extract_request_id(line)
            response = self.error_response(request_id, INTERNAL_ERROR, "Internal error")

        with self._event_lock:
            messages = [*self._pending_events, response]
            self._pending_events = []
            self._collecting_events = False
        return messages

    def dispatch(self, method: str, params: dict[str, Any]) -> Any:
        if method == "system.ping":
            return {"ok": True}
        if method == "settings.get":
            self._require_no_params(params)
            return self.service.get_config()
        if method == "settings.save":
            return self.service.save_settings(params)
        if method == "settings.save_hotkeys":
            return self.service.save_hotkeys(params)
        if method == "hotkeys.status":
            self._require_no_params(params)
            return self.hotkeys.status() if self.hotkeys else self.service.hotkeys_status()
        if method == "hotkeys.reload":
            self._require_no_params(params)
            return self.reload_hotkeys()
        if method == "settings.get_local_whisper_status":
            self._require_no_params(params)
            return self.service.get_local_whisper_status()
        if method == "settings.prepare_local_whisper_model":
            self._require_no_params(params)
            return self.service.prepare_local_whisper_model()
        if method == "settings.install_rnnoise_model":
            return self.service.install_rnnoise_model(self._require_string(params, "path"))
        if method == "devices.microphones":
            self._require_no_params(params)
            return self.service.get_microphones()
        if method == "devices.recommended_microphone":
            self._require_no_params(params)
            return self.service.get_recommended_microphone()
        if method == "recording.toggle":
            return self.service.toggle_recording(str(params.get("mode", "standard")))
        if method == "recording.status":
            self._require_no_params(params)
            return self.service.recording_status()
        if method == "quick.recording.toggle":
            self._require_no_params(params)
            return self.service.toggle_recording("bubble")
        if method == "files.register_selected":
            return self.service.register_selected_file(self._require_string(params, "path"))
        if method == "files.check_duration":
            return self.service.check_file_duration(self._require_string(params, "token"))
        if method == "files.transcribe":
            return self.service.transcribe_file(self._require_string(params, "token"))
        if method == "files.save_transcript":
            return self.service.save_transcript(
                self._require_string(params, "text"),
                self._require_string(params, "path"),
            )
        if method == "split.start":
            return self.service.start_split_workflow(self._require_string(params, "token"))
        if method == "docs.models":
            self._require_no_params(params)
            return self.service.docs_model_profiles()
        if method == "docs.details":
            self._require_no_params(params)
            return self.service.docs_detail_profiles()
        if method == "docs.register_selected":
            return self.service.register_selected_docs_file(self._require_string(params, "path"))
        if method == "docs.check_duration":
            return self.service.check_docs_duration(self._require_string(params, "token"))
        if method == "docs.preflight":
            return self.service.docs_preflight(
                self._require_string(params, "token"),
                str(params.get("model") or ""),
                str(params.get("detail") or ""),
                str(params.get("output_language") or ""),
            )
        if method == "docs.start":
            return self.service.start_docs_workflow(
                self._require_string(params, "token"),
                self._require_string(params, "path"),
                str(params.get("model") or ""),
                str(params.get("detail") or ""),
                str(params.get("output_language") or ""),
            )
        if method == "converter.status":
            self._require_no_params(params)
            return self.service.converter_status()
        if method == "converter.output_formats":
            self._require_no_params(params)
            return self.service.converter_output_formats()
        if method == "converter.register_selected":
            return self.service.register_selected_file(self._require_string(params, "path"), for_convert=True)
        if method == "converter.convert":
            return self.service.convert_file(
                self._require_string(params, "token"),
                self._require_string(params, "output_format"),
                self._require_string(params, "path"),
            )
        if method == "history.list":
            self._require_no_params(params)
            return self.service.list_history()
        if method == "history.clear":
            self._require_no_params(params)
            return self.service.clear_history()
        if method == "history.update_text":
            return self.service.update_history_text(
                self._require_string(params, "id"),
                self._require_string(params, "text"),
            )
        if method == "history.delete":
            return self.service.delete_history_item(self._require_string(params, "id"))
        if method == "history.create_merged":
            return self.service.create_merged_history_entry(self._require_string(params, "text"))
        if method == "clipboard.copy":
            return self.service.copy_to_clipboard(self._require_string(params, "text"))
        if method == "app.shutdown":
            self._require_no_params(params)
            self.service.request_shutdown()
            return {"success": True}

        raise JsonRpcError(METHOD_NOT_FOUND, "Method not found")

    @staticmethod
    def error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }

    def queue_event(self, method: str, params: dict[str, Any]) -> None:
        if not method or not isinstance(params, dict):
            return
        event = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        with self._event_lock:
            if self._collecting_events or self._event_writer is None:
                self._pending_events.append(event)
                return
        self._event_writer(event)

    def _queue_hotkey_status(self, payload: dict[str, Any]) -> None:
        if self._hotkey_status_events_enabled:
            self.queue_event("hotkeys.status", payload)

    def reload_hotkeys(self) -> dict[str, Any]:
        if not self.hotkeys:
            self.service.config.reload_env()
            return self.service.hotkeys_status()
        return self.hotkeys.reload()

    def close(self) -> None:
        if self.hotkeys:
            self._hotkey_status_events_enabled = False
            self.hotkeys.stop()
        self.service.close()

    @staticmethod
    def _extract_request_id(line: str) -> Any:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        return payload.get("id") if isinstance(payload, dict) else None

    @staticmethod
    def _require_no_params(params: dict[str, Any]) -> None:
        if params:
            raise JsonRpcError(INVALID_PARAMS, "Invalid params")

    @staticmethod
    def _require_string(params: dict[str, Any], key: str) -> str:
        value = params.get(key)
        if not isinstance(value, str):
            raise JsonRpcError(INVALID_PARAMS, "Invalid params")
        return value


def serve(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    """Run the sidecar loop."""
    protocol_stdout = stdout
    write_lock = threading.RLock()

    def write_message(message: dict[str, Any]) -> None:
        with write_lock:
            print(
                json.dumps(message, ensure_ascii=False, separators=(",", ":")),
                file=protocol_stdout,
                flush=True,
            )

    with contextlib.redirect_stdout(sys.stderr):
        server = SidecarJsonRpcServer(event_writer=write_message, enable_hotkeys=True)
        try:
            for line in stdin:
                line = line.strip()
                if not line:
                    continue
                for message in server.handle_line_messages(line):
                    write_message(message)
        finally:
            server.close()
    return 0


def main() -> int:
    return serve()


if __name__ == "__main__":
    raise SystemExit(main())
