from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from src.config import Config
from src.core.backend_service import BackendService
from tests.sidecar_test_support import FakeInjector, SidecarTestCase


class SidecarHistoryTests(SidecarTestCase):
    def test_history_methods_mutate_and_return_list(self):
        events = []
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("", encoding="utf-8")
            config = Config(str(env_path))
            config.reload_env()
            service = BackendService(
                config=config,
                injector=FakeInjector(),
                build_info={"version": "test", "display": "Test Build"},
                on_event=lambda method, params: events.append((method, params)),
            )
            created = service.create_merged_history_entry("first")
            recording_id = created["id"]
            updated = service.update_history_text(recording_id, "edited")
            deleted = service.delete_history_item(recording_id)
            cleared = service.clear_history()

        self.assertEqual(updated["history"][0]["id"], recording_id)
        self.assertEqual(updated["history"][0]["text"], "edited")
        self.assertTrue(deleted["success"])
        self.assertEqual(deleted["history"], [])
        self.assertEqual(cleared["history"], [])
        self.assertEqual([event[0] for event in events], ["history.updated"] * 4)
        self.assertEqual(events[-1][1]["history"], [])

    def test_clipboard_copy_uses_injector(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            service = self.make_service(temp_dir)
            result = service.copy_to_clipboard("hello")

        self.assertEqual(result, {"success": True})
        self.assertEqual(service.injector.copied, ["hello"])
