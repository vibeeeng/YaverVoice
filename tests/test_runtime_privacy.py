from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from src.config import Config
from src.core.backend_service import BackendService, cleanup_stale_temp_files
from src.core.history_manager import HistoryManager
from src.models.recording import SourceType
from src.sidecar import SidecarJsonRpcServer


class RuntimePrivacyTests(unittest.TestCase):
    def test_close_deletes_only_app_generated_files_inside_temp(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            temp_dir = root_path / "app-temp"
            temp_dir.mkdir()
            user_file = root_path / "user-selected.wav"
            user_file.write_bytes(b"user")
            recording = temp_dir / "recording_1.wav"
            recording.write_bytes(b"recording")
            split = temp_dir / "meeting_001_part.wav"
            split.write_bytes(b"split")
            orphan_recording = temp_dir / "recording_orphan.wav"
            orphan_split = temp_dir / "meeting_002_part.mp3"
            orphan_metadata = temp_dir / "old_job_meta.json"
            unrelated = temp_dir / "test_tone.wav"
            for path in (orphan_recording, orphan_split, orphan_metadata, unrelated):
                path.write_bytes(b"temp")

            history = HistoryManager()
            history.add_recording(str(user_file), source=SourceType.FILE)
            history.add_recording(str(recording), source=SourceType.RECORDING)
            split_id = history.add_recording(str(split), source=SourceType.FILE)
            history.get_recording(split_id).is_split = True

            env_path = root_path / ".env"
            env_path.write_text("", encoding="utf-8")
            with patch.object(Config, "get_temp_dir", return_value=temp_dir):
                service = BackendService(config=Config(str(env_path)), history=history)
                SidecarJsonRpcServer(service).close()

            self.assertTrue(user_file.exists())
            self.assertFalse(recording.exists())
            self.assertFalse(split.exists())
            self.assertFalse(orphan_recording.exists())
            self.assertFalse(orphan_split.exists())
            self.assertFalse(orphan_metadata.exists())
            self.assertTrue(unrelated.exists())

    def test_stale_cleanup_removes_only_known_old_artifacts(self):
        with tempfile.TemporaryDirectory() as root:
            temp_dir = Path(root)
            stale = temp_dir / "recording_old.wav"
            recent = temp_dir / "recording_recent.wav"
            unrelated = temp_dir / "notes.txt"
            for path in (stale, recent, unrelated):
                path.write_bytes(b"data")
            old = time.time() - (25 * 60 * 60)
            os.utime(stale, (old, old))
            os.utime(unrelated, (old, old))

            cleanup_stale_temp_files(temp_dir, now=time.time())

            self.assertFalse(stale.exists())
            self.assertTrue(recent.exists())
            self.assertTrue(unrelated.exists())

    @unittest.skipIf(os.name == "nt", "POSIX mode bits are not enforced on Windows")
    def test_env_file_permissions_are_owner_only_on_posix(self):
        with tempfile.TemporaryDirectory() as root:
            env_path = Path(root) / ".env"
            config = Config(str(env_path))

            config.save_language("tr")

            self.assertEqual(env_path.stat().st_mode & 0o777, 0o600)

if __name__ == "__main__":
    unittest.main()
