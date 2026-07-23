from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from src.config import Config


REPO_ROOT = Path(__file__).resolve().parents[1]


class ConfigSecurityTests(unittest.TestCase):
    def test_env_values_reject_newline_injection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            config = Config(str(env_path))

            with self.assertRaisesRegex(ValueError, "newline"):
                config.save_language("tr\nGROQ_API_KEY=injected")

            self.assertFalse(env_path.exists())

    def test_env_values_reject_nul_injection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            config = Config(str(env_path))

            with self.assertRaisesRegex(ValueError, "NUL"):
                config.save_language("tr\x00GROQ_API_KEY=injected")

            self.assertFalse(env_path.exists())

    def test_api_key_rejects_env_injection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            config = Config(str(env_path))

            with self.assertRaisesRegex(ValueError, "newline"):
                config.save_api_key("gsk_safe\nTRANSCRIPTION_PROVIDER=attacker")

            self.assertFalse(env_path.exists())

    def test_local_whisper_model_must_be_supported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(str(Path(temp_dir) / ".env"))

            with self.assertRaisesRegex(ValueError, "supported Local Whisper model"):
                config.save_local_whisper_settings(model="untrusted/model")


class DesktopIpcSecurityTests(unittest.TestCase):
    @staticmethod
    def _renderer_source_paths() -> list[Path]:
        renderer_src = REPO_ROOT / "desktop" / "renderer" / "src"
        return sorted((*renderer_src.rglob("*.ts"), *renderer_src.rglob("*.tsx")))

    @staticmethod
    def _function_block(source: str, name: str, next_name: str) -> str:
        match = re.search(
            rf"function\s+{name}\(\):\s+void\s+\{{(.*?)function\s+{next_name}\(",
            source,
            re.DOTALL,
        )
        if match is None:
            raise AssertionError(f"Could not find {name} block")
        return match.group(1)

    def test_dashboard_preload_does_not_expose_generic_invoke(self):
        preload = (REPO_ROOT / "desktop" / "preload" / "preload.ts").read_text(
            encoding="utf-8"
        )

        self.assertNotRegex(preload, r"const\s+api\s*=\s*\{\s*invoke\s*,")

    def test_each_window_uses_its_own_preload_and_sandbox(self):
        main = (REPO_ROOT / "desktop" / "main" / "main.ts").read_text(
            encoding="utf-8"
        )
        quick_preload_path = REPO_ROOT / "desktop" / "preload" / "quickPreload.ts"
        main_window = self._function_block(main, "createWindow", "createQuickWindow")
        quick_window = self._function_block(main, "createQuickWindow", "positionQuickWindow")

        self.assertTrue(quick_preload_path.exists())
        self.assertIn('"preload.js"', main_window)
        self.assertNotIn('"quickPreload.js"', main_window)
        self.assertIn('"quickPreload.js"', quick_window)
        self.assertNotRegex(quick_window, r'(?<!quick)Preload\.js')
        self.assertIn("sandbox: true", main_window)
        self.assertIn("sandbox: true", quick_window)

        quick_preload = quick_preload_path.read_text(encoding="utf-8")
        for forbidden in (
            "settings",
            "files",
            "docs",
            "converter",
            "history",
            "clipboard",
        ):
                self.assertNotRegex(quick_preload, rf"\b{re.escape(forbidden)}\b")

    def test_windows_block_navigation_and_new_windows(self):
        main = (REPO_ROOT / "desktop" / "main" / "main.ts").read_text(encoding="utf-8")

        self.assertIn("setWindowOpenHandler", main)
        self.assertIn("will-navigate", main)
        self.assertIn('action: "deny"', main)

    def test_ipc_requires_main_frame_and_expected_renderer_url(self):
        main = (REPO_ROOT / "desktop" / "main" / "main.ts").read_text(encoding="utf-8")

        self.assertIn("event.senderFrame", main)
        self.assertIn("event.sender.mainFrame", main)
        self.assertIn("isExpectedRendererUrl", main)
        self.assertRegex(main, r"127\.0\.0\.1.*localhost|localhost.*127\.0\.0\.1")

    def test_quick_page_has_strict_csp_and_no_inline_assets(self):
        quick_dir = REPO_ROOT / "desktop" / "quick"
        quick_html = (quick_dir / "quick.html").read_text(encoding="utf-8")

        self.assertTrue((quick_dir / "quick.css").exists())
        self.assertTrue((quick_dir / "quick.js").exists())
        self.assertIn("Content-Security-Policy", quick_html)
        self.assertIn('href="./quick.css"', quick_html)
        self.assertIn('src="./quick.js"', quick_html)
        self.assertNotRegex(quick_html, r"<style(?:\s|>)")
        self.assertNotRegex(quick_html, r"<script(?![^>]*\bsrc=)")
        self.assertNotIn("unsafe-inline", quick_html)

    def test_linux_wayland_uses_x11_compatibility_before_runtime_start(self):
        main = (REPO_ROOT / "desktop" / "main" / "main.ts").read_text(
            encoding="utf-8"
        )

        compatibility_guard = main.find('process.platform === "linux"')
        x11_switch = main.find(
            'app.commandLine.appendSwitch("ozone-platform", "x11")'
        )
        runtime_start = main.index("const projectRoot = app.getAppPath()")

        self.assertGreaterEqual(compatibility_guard, 0)
        self.assertGreaterEqual(x11_switch, 0)
        self.assertLess(compatibility_guard, x11_switch)
        self.assertLess(x11_switch, runtime_start)
        self.assertIn("XDG_SESSION_TYPE", main[compatibility_guard:runtime_start])
        self.assertIn("WAYLAND_DISPLAY", main[compatibility_guard:runtime_start])
        self.assertIn("DISPLAY", main[compatibility_guard:runtime_start])
        self.assertIn(
            'app.commandLine.hasSwitch("ozone-platform")',
            main[compatibility_guard:runtime_start],
        )

    def test_quick_bubble_exposes_native_drag_region(self):
        quick_css = (
            REPO_ROOT / "desktop" / "quick" / "quick.css"
        ).read_text(encoding="utf-8")

        bubble_rule = re.search(r"\.bubble\s*\{(.*?)\}", quick_css, re.DOTALL)
        button_rule = re.search(r"button\s*\{(.*?)\}", quick_css, re.DOTALL)

        self.assertIsNotNone(bubble_rule)
        self.assertIsNotNone(button_rule)
        self.assertIn("-webkit-app-region: drag", bubble_rule.group(1))
        self.assertIn("-webkit-app-region: no-drag", button_rule.group(1))

    def test_dashboard_declares_content_security_policy(self):
        renderer_html = (REPO_ROOT / "desktop" / "renderer" / "index.html").read_text(encoding="utf-8")

        self.assertIn("Content-Security-Policy", renderer_html)
        self.assertNotIn("unsafe-inline", renderer_html)

    def test_main_sidecar_invoke_uses_allowlists(self):
        main = (REPO_ROOT / "desktop" / "main" / "main.ts").read_text(
            encoding="utf-8"
        )

        self.assertIn("mainSidecarMethods", main)
        self.assertIn("quickSidecarMethods", main)
        self.assertNotIn("return sidecar.invoke(method, params ?? {});", main)

        raw_methods = (
            "files.register_selected",
            "files.save_transcript",
            "docs.register_selected",
            "docs.start",
            "converter.register_selected",
            "converter.convert",
            "app.shutdown",
        )
        allowlist_match = re.search(
            r"mainSidecarMethods\s*=\s*new Set<string>\(\[(.*?)\]\)",
            main,
            re.DOTALL,
        )
        self.assertIsNotNone(allowlist_match)
        allowlist_source = allowlist_match.group(1)
        for method in raw_methods:
            self.assertNotIn(f'"{method}"', allowlist_source)

    def test_rnnoise_download_is_removed_from_desktop_bridges(self):
        paths = (
            REPO_ROOT / "desktop" / "main" / "main.ts",
            REPO_ROOT / "desktop" / "preload" / "preload.ts",
            *self._renderer_source_paths(),
        )
        for path in paths:
            self.assertNotIn("download_rnnoise_model", path.read_text(encoding="utf-8"))
            self.assertNotIn("downloadRnnoiseModel", path.read_text(encoding="utf-8"))

    def test_sidecar_client_attempts_graceful_shutdown_before_kill(self):
        client = (REPO_ROOT / "desktop" / "main" / "sidecarClient.ts").read_text(encoding="utf-8")

        self.assertIn("child.stdin.end()", client)
        self.assertIn("setTimeout", client)
        self.assertIn("child.kill()", client)
        self.assertIn("gracePeriodMs", client)

    def test_docs_preview_uses_directory_tokens(self):
        main = (REPO_ROOT / "desktop" / "main" / "main.ts").read_text(
            encoding="utf-8"
        )
        preload = (REPO_ROOT / "desktop" / "preload" / "preload.ts").read_text(
            encoding="utf-8"
        )

        self.assertIn("selectedDocsDirectories", main)
        self.assertIn("directoryToken", preload)


if __name__ == "__main__":
    unittest.main()
