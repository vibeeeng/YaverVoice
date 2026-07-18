from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from src.config import Config
from src.core.backend_service import BackendService
from src.models.recording import SourceType
from tests.sidecar_test_support import FakeInjector, SidecarTestCase


class SidecarHistoryTests(SidecarTestCase):
    def test_split_history_groups_list_parts_in_transcript_order(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "get_models_dir", return_value=Path(temp_dir) / "models"
        ):
            service = self.make_service(temp_dir)
            base_time = datetime(2026, 7, 18, 16, 6, 3)

            def add_entry(name: str, created_at: datetime, parent_id: str | None, part: int | None) -> str:
                recording_id = service.history.add_recording(name, source=SourceType.FILE)
                recording = service.history.get_recording(recording_id)
                self.assertIsNotNone(recording)
                recording.created_at = created_at
                if parent_id is not None:
                    recording.is_split = True
                    recording.parent_recording_id = parent_id
                    recording.chunk_part = part
                return recording_id

            older_part_1 = add_entry("older-1.wav", base_time, "older-job", 1)
            older_part_2 = add_entry("older-2.wav", base_time + timedelta(milliseconds=1), "older-job", 2)
            normal_entry = add_entry("normal.wav", base_time + timedelta(milliseconds=2), None, None)
            newer_part_1 = add_entry("newer-1.wav", base_time + timedelta(milliseconds=3), "newer-job", 1)
            newer_part_2 = add_entry("newer-2.wav", base_time + timedelta(milliseconds=4), "newer-job", 2)

            history_ids = [item["id"] for item in service.list_history()]

        self.assertEqual(
            history_ids,
            [newer_part_1, newer_part_2, normal_entry, older_part_1, older_part_2],
        )

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
