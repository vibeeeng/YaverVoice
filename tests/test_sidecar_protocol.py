from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.config import Config
from src.sidecar import INVALID_PARAMS, METHOD_NOT_FOUND, SidecarJsonRpcServer
from tests.sidecar_test_support import SidecarTestCase


class SidecarProtocolTests(SidecarTestCase):
    def test_parser_accepts_valid_request(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            server = SidecarJsonRpcServer(self.make_service(temp_dir))
            request = server.parse_request('{"jsonrpc":"2.0","id":1,"method":"system.ping","params":{}}')

        self.assertEqual(request.request_id, 1)
        self.assertEqual(request.method, "system.ping")
        self.assertEqual(request.params, {})

    def test_unknown_method_returns_method_not_found(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            server = SidecarJsonRpcServer(self.make_service(temp_dir))
            response = server.handle_line('{"jsonrpc":"2.0","id":2,"method":"missing.method","params":{}}')

        self.assertEqual(response["id"], 2)
        self.assertEqual(response["error"]["code"], METHOD_NOT_FOUND)

    def test_invalid_params_returns_invalid_params(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            server = SidecarJsonRpcServer(self.make_service(temp_dir))
            response = server.handle_line(
                '{"jsonrpc":"2.0","id":3,"method":"history.update_text","params":{"id":"missing"}}'
            )

        self.assertEqual(response["id"], 3)
        self.assertEqual(response["error"]["code"], INVALID_PARAMS)

    def test_sidecar_can_return_event_before_response(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ, {"XDG_DATA_HOME": temp_dir}, clear=True
        ), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            server = SidecarJsonRpcServer()
            messages = server.handle_line_messages(
                '{"jsonrpc":"2.0","id":4,"method":"history.create_merged","params":{"text":"hello"}}'
            )

        self.assertEqual(messages[0]["jsonrpc"], "2.0")
        self.assertEqual(messages[0]["method"], "history.updated")
        self.assertEqual(messages[0]["params"]["history"][0]["text"], "hello")
        self.assertEqual(messages[1]["jsonrpc"], "2.0")
        self.assertEqual(messages[1]["id"], 4)
        self.assertEqual(messages[1]["result"]["history"][0]["text"], "hello")

    def test_sidecar_subprocess_ping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env = os.environ.copy()
            env.pop("GROQ_API_KEY", None)
            env["XDG_DATA_HOME"] = temp_dir
            process = subprocess.run(
                [sys.executable, "-m", "src.sidecar"],
                input='{"jsonrpc":"2.0","id":1,"method":"system.ping","params":{}}\n',
                text=True,
                capture_output=True,
                cwd=Path(__file__).resolve().parents[1],
                env=env,
                timeout=10,
                check=False,
            )

        self.assertEqual(process.returncode, 0, process.stderr)
        lines = [line for line in process.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, process.stdout)
        response = json.loads(lines[0])
        self.assertEqual(response, {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}})

    def test_sidecar_subprocess_register_selected_file_uses_utf8_stdio(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "deneme-çğışöü.wav"
            audio_path.write_bytes(b"RIFFfake")

            legacy_response = self._run_sidecar_register_selected(
                audio_path,
                extra_env={"PYTHONUTF8": "0", "PYTHONIOENCODING": "cp1254"},
            )
            self.assertEqual(legacy_response["error"]["message"], "File does not exist")

            utf8_response = self._run_sidecar_register_selected(
                audio_path,
                extra_env={"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
            )
            self.assertEqual(utf8_response["result"]["name"], audio_path.name)
            self.assertEqual(utf8_response["result"]["extension"], ".wav")

    def _run_sidecar_register_selected(self, audio_path: Path, *, extra_env: dict[str, str]) -> dict:
        env = os.environ.copy()
        env.pop("GROQ_API_KEY", None)
        env.update(extra_env)
        env["XDG_DATA_HOME"] = str(audio_path.parent)

        payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "files.register_selected",
                "params": {"path": str(audio_path)},
            },
            ensure_ascii=False,
        )
        process = subprocess.run(
            [sys.executable, "-m", "src.sidecar"],
            input=f"{payload}\n".encode("utf-8"),
            capture_output=True,
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            timeout=10,
            check=False,
        )

        self.assertEqual(process.returncode, 0, process.stderr.decode("utf-8", errors="replace"))
        lines = [line for line in process.stdout.decode("utf-8", errors="replace").splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, process.stdout)
        return json.loads(lines[0])
