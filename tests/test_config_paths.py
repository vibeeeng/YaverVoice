from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.config import Config


class ConfigPathTests(unittest.TestCase):
    def test_windows_app_base_dir_uses_yavervoice_name(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ, {"LOCALAPPDATA": temp_dir}, clear=True
        ), patch("src.config.sys.platform", "win32"):
            self.assertEqual(Config.get_app_base_dir(), Path(temp_dir) / "YaverVoice")

    def test_linux_app_base_dir_uses_yavervoice_name(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ, {"XDG_DATA_HOME": temp_dir}, clear=True
        ), patch("src.config.sys.platform", "linux"):
            self.assertEqual(Config.get_app_base_dir(), Path(temp_dir) / "yavervoice")

    def test_legacy_app_data_directory_moves_to_canonical_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "GroqWhisper"
            canonical = root / "YaverVoice"
            (legacy / "models").mkdir(parents=True)
            (legacy / ".env").write_text("GROQ_API_KEY=placeholder", encoding="utf-8")
            (legacy / "models" / "model.bin").write_bytes(b"model")

            with patch.object(Config, "get_app_base_dir", return_value=canonical), patch.object(
                Config, "get_legacy_app_base_dir", return_value=legacy
            ):
                resolved = Config.ensure_app_base_dir()

            self.assertEqual(resolved, canonical)
            self.assertFalse(legacy.exists())
            self.assertEqual((canonical / ".env").read_text(encoding="utf-8"), "GROQ_API_KEY=placeholder")
            self.assertEqual((canonical / "models" / "model.bin").read_bytes(), b"model")

    def test_existing_canonical_dir_repairs_stale_managed_rnnoise_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "GroqWhisper"
            canonical = root / "YaverVoice"
            legacy_model = legacy / "models" / "rnnoise" / "cleanup.rnnn"
            canonical_model = canonical / "models" / "rnnoise" / "cleanup.rnnn"
            canonical_model.parent.mkdir(parents=True)
            canonical_model.write_bytes(b"model")
            (canonical / ".env").write_text(
                f"GROQ_API_KEY=placeholder\nAUDIO_CLEANUP_RNN_MODEL={legacy_model}\n",
                encoding="utf-8",
            )

            with patch.object(Config, "get_app_base_dir", return_value=canonical), patch.object(
                Config, "get_legacy_app_base_dir", return_value=legacy
            ):
                resolved = Config.ensure_app_base_dir()

            self.assertEqual(resolved, canonical)
            env_text = (canonical / ".env").read_text(encoding="utf-8")
            self.assertIn(f"AUDIO_CLEANUP_RNN_MODEL={canonical_model}", env_text)
            self.assertIn("GROQ_API_KEY=placeholder", env_text)

    def test_whole_directory_migration_repairs_managed_rnnoise_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "GroqWhisper"
            canonical = root / "YaverVoice"
            legacy_model = legacy / "models" / "rnnoise" / "cleanup.rnnn"
            legacy_model.parent.mkdir(parents=True)
            legacy_model.write_bytes(b"model")
            (legacy / ".env").write_text(
                f"AUDIO_CLEANUP_RNN_MODEL={legacy_model}\n",
                encoding="utf-8",
            )

            with patch.object(Config, "get_app_base_dir", return_value=canonical), patch.object(
                Config, "get_legacy_app_base_dir", return_value=legacy
            ):
                resolved = Config.ensure_app_base_dir()

            canonical_model = canonical / "models" / "rnnoise" / "cleanup.rnnn"
            self.assertEqual(resolved, canonical)
            self.assertEqual(canonical_model.read_bytes(), b"model")
            self.assertIn(
                f"AUDIO_CLEANUP_RNN_MODEL={canonical_model}",
                (canonical / ".env").read_text(encoding="utf-8"),
            )

    def test_migration_does_not_rewrite_external_rnnoise_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "GroqWhisper"
            canonical = root / "YaverVoice"
            external_model = root / "external" / "cleanup.rnnn"
            canonical_model = canonical / "models" / "rnnoise" / "cleanup.rnnn"
            canonical_model.parent.mkdir(parents=True)
            canonical_model.write_bytes(b"managed")
            canonical_env = canonical / ".env"
            canonical_env.write_text(
                f"AUDIO_CLEANUP_RNN_MODEL={external_model}\n",
                encoding="utf-8",
            )

            with patch.object(Config, "get_app_base_dir", return_value=canonical), patch.object(
                Config, "get_legacy_app_base_dir", return_value=legacy
            ):
                Config.ensure_app_base_dir()

            self.assertEqual(
                canonical_env.read_text(encoding="utf-8"),
                f"AUDIO_CLEANUP_RNN_MODEL={external_model}\n",
            )

    def test_migration_keeps_stale_path_when_canonical_model_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "GroqWhisper"
            canonical = root / "YaverVoice"
            legacy_model = legacy / "models" / "rnnoise" / "cleanup.rnnn"
            canonical.mkdir()
            canonical_env = canonical / ".env"
            canonical_env.write_text(
                f"AUDIO_CLEANUP_RNN_MODEL={legacy_model}\n",
                encoding="utf-8",
            )

            with patch.object(Config, "get_app_base_dir", return_value=canonical), patch.object(
                Config, "get_legacy_app_base_dir", return_value=legacy
            ):
                Config.ensure_app_base_dir()

            self.assertEqual(
                canonical_env.read_text(encoding="utf-8"),
                f"AUDIO_CLEANUP_RNN_MODEL={legacy_model}\n",
            )

    def test_rnnoise_path_repair_preserves_env_when_atomic_replace_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "GroqWhisper"
            canonical = root / "YaverVoice"
            legacy_model = legacy / "models" / "rnnoise" / "cleanup.rnnn"
            canonical_model = canonical / "models" / "rnnoise" / "cleanup.rnnn"
            canonical_model.parent.mkdir(parents=True)
            canonical_model.write_bytes(b"model")
            canonical_env = canonical / ".env"
            original_env = f"AUDIO_CLEANUP_RNN_MODEL={legacy_model}\n"
            canonical_env.write_text(original_env, encoding="utf-8")

            with patch.object(Config, "get_app_base_dir", return_value=canonical), patch.object(
                Config, "get_legacy_app_base_dir", return_value=legacy
            ), patch.object(Path, "replace", side_effect=OSError("denied")):
                Config.ensure_app_base_dir()

            self.assertEqual(canonical_env.read_text(encoding="utf-8"), original_env)
            self.assertEqual(list(canonical.glob(".env.*.migration.tmp")), [])

    def test_fresh_install_does_not_create_rnnoise_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "GroqWhisper"
            canonical = root / "YaverVoice"

            with patch.object(Config, "get_app_base_dir", return_value=canonical), patch.object(
                Config, "get_legacy_app_base_dir", return_value=legacy
            ):
                resolved = Config.ensure_app_base_dir()

            self.assertEqual(resolved, canonical)
            self.assertTrue(canonical.is_dir())
            self.assertFalse((canonical / ".env").exists())

    def test_merge_never_overwrites_canonical_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "GroqWhisper"
            canonical = root / "YaverVoice"
            (legacy / "models").mkdir(parents=True)
            canonical.mkdir()
            (legacy / ".env").write_text("legacy", encoding="utf-8")
            (canonical / ".env").write_text("canonical", encoding="utf-8")
            (legacy / "models" / "model.bin").write_bytes(b"model")

            with patch.object(Config, "get_app_base_dir", return_value=canonical), patch.object(
                Config, "get_legacy_app_base_dir", return_value=legacy
            ):
                resolved = Config.ensure_app_base_dir()

            self.assertEqual(resolved, canonical)
            self.assertEqual((canonical / ".env").read_text(encoding="utf-8"), "canonical")
            self.assertEqual((legacy / ".env").read_text(encoding="utf-8"), "legacy")
            self.assertEqual((canonical / "models" / "model.bin").read_bytes(), b"model")

    def test_failed_whole_directory_move_falls_back_to_legacy_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "GroqWhisper"
            canonical = root / "YaverVoice"
            legacy.mkdir()

            with patch.object(Config, "get_app_base_dir", return_value=canonical), patch.object(
                Config, "get_legacy_app_base_dir", return_value=legacy
            ), patch.object(Path, "rename", side_effect=OSError("denied")):
                resolved = Config.ensure_app_base_dir()

            self.assertEqual(resolved, legacy)
            self.assertTrue(legacy.exists())
            self.assertFalse(canonical.exists())

    def test_existing_canonical_dir_does_not_merge_symlinked_legacy_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            legacy = root / "GroqWhisper"
            canonical = root / "YaverVoice"
            legacy.mkdir()
            canonical.mkdir()

            with patch.object(Config, "get_app_base_dir", return_value=canonical), patch.object(
                Config, "get_legacy_app_base_dir", return_value=legacy
            ), patch.object(Path, "is_symlink", autospec=True, side_effect=lambda path: path == legacy), patch.object(
                Config, "_merge_legacy_app_data", side_effect=AssertionError("symlink root must not be merged")
            ):
                resolved = Config.ensure_app_base_dir()

            self.assertEqual(resolved, canonical)

    def test_explicit_env_path_does_not_trigger_app_data_migration(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {}, clear=True), patch.object(
            Config, "ensure_app_base_dir", side_effect=AssertionError("migration must not run")
        ):
            env_path = Path(temp_dir) / ".env"
            config = Config(str(env_path))

            self.assertEqual(config.env_path, env_path)
