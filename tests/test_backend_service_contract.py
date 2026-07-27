"""Behavior-preserving contracts for the sidecar facade and desktop bridge."""

from __future__ import annotations

import ast
import inspect
import re
import unittest
from pathlib import Path

from src.core.backend_service import (
    BackendService,
    BackendValidationError,
    cleanup_stale_temp_files,
)


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_JSON_RPC_METHODS = frozenset(
    {
        "app.shutdown",
        "clipboard.copy",
        "converter.convert",
        "converter.output_formats",
        "converter.register_selected",
        "converter.status",
        "devices.microphones",
        "devices.recommended_microphone",
        "docs.check_duration",
        "docs.details",
        "docs.models",
        "docs.preflight",
        "docs.register_selected",
        "docs.start",
        "files.check_duration",
        "files.register_selected",
        "files.save_transcript",
        "files.transcribe",
        "history.clear",
        "history.create_merged",
        "history.delete",
        "history.list",
        "history.update_text",
        "hotkeys.reload",
        "hotkeys.status",
        "quick.recording.toggle",
        "recording.status",
        "recording.toggle",
        "settings.get",
        "settings.get_local_whisper_setup_info",
        "settings.get_local_whisper_status",
        "settings.install_rnnoise_model",
        "settings.prepare_local_whisper_model",
        "settings.save",
        "settings.save_hotkeys",
        "split.start",
        "system.ping",
    }
)

EXPECTED_SERVICE_SIGNATURES = {
    "check_docs_duration": "self, token",
    "check_file_duration": "self, token",
    "clear_history": "self",
    "convert_file": "self, token, output_format, output_path",
    "converter_output_formats": "self",
    "converter_status": "self",
    "copy_to_clipboard": "self, text",
    "create_merged_history_entry": "self, text",
    "delete_history_item": "self, recording_id",
    "docs_detail_profiles": "self",
    "docs_model_profiles": "self",
    "docs_preflight": "self, token, model=None, detail=None, output_language=None",
    "get_config": "self",
    "get_local_whisper_setup_info": "self",
    "get_local_whisper_status": "self",
    "get_microphones": "self",
    "get_recommended_microphone": "self",
    "hotkeys_status": "self",
    "install_rnnoise_model": "self, path",
    "list_history": "self",
    "prepare_local_whisper_model": "self",
    "recording_status": "self",
    "register_selected_docs_file": "self, filepath",
    "register_selected_file": "self, filepath, *, for_convert=False",
    "request_shutdown": "self",
    "save_hotkeys": "self, payload",
    "save_settings": "self, payload",
    "save_transcript": "self, text, output_path",
    "start_docs_workflow": "self, token, output_path, model=None, detail=None, output_language=None",
    "start_split_workflow": "self, token",
    "toggle_recording": "self, mode='standard'",
    "transcribe_file": "self, token",
    "update_history_text": "self, recording_id, text",
}

EXPECTED_EVENT_NAMES = frozenset(
    {
        "app.shutdown",
        "converter.status",
        "docs.progress",
        "docs.status",
        "file.status",
        "history.updated",
        "hotkeys.status",
        "quick.status",
        "recording.state",
        "settings.changed",
        "settings.local_whisper_progress",
        "split.progress",
        "split.step",
        "toast",
    }
)

EXPECTED_BRIDGE_SURFACE = {
    "ping": None,
    "settings": frozenset(
        {
            "get",
            "getLocalWhisperSetupInfo",
            "getLocalWhisperStatus",
            "installRnnoiseModel",
            "prepareLocalWhisperModel",
            "save",
            "saveHotkeys",
        }
    ),
    "hotkeys": frozenset({"reload", "status"}),
    "devices": frozenset({"microphones", "recommendedMicrophone"}),
    "recording": frozenset({"status", "toggle"}),
    "files": frozenset({"checkDuration", "saveTranscript", "select", "transcribe"}),
    "split": frozenset({"start"}),
    "docs": frozenset(
        {
            "checkDuration",
            "createMarkdown",
            "details",
            "listDirectory",
            "models",
            "preflight",
            "readFile",
            "select",
            "selectDirectory",
        }
    ),
    "converter": frozenset({"convert", "outputFormats", "select", "status"}),
    "quick": frozenset(
        {
            "hideWindow",
            "moveWindowBy",
            "showDashboard",
            "showWindow",
            "toggleRecording",
            "toggleWindow",
        }
    ),
    "history": frozenset({"clear", "createMerged", "delete", "list", "updateText"}),
    "clipboard": frozenset({"copy"}),
    "onSidecarLog": None,
    "onSidecarEvent": None,
}

# R0 ownership evidence. These names move in later phases; the public contract above does not.
R0_RENDERER_COMPONENTS_IN_MAIN = (
    "App",
    "ToastViewport",
    "HomeView",
    "SettingsView",
    "HistoryView",
    "RecordView",
    "FileTranscriptionView",
    "DocsView",
    "ConverterView",
    "QuickDictationView",
    "Toggle",
)

R0_BACKEND_METHODS_IN_FACADE = frozenset(
    {
        "__init__",
        "close",
        "get_config",
        "save_settings",
        "get_audio_cleanup_status",
        "get_local_whisper_setup_info",
        "install_rnnoise_model",
        "_coerce_audio_cleanup_mode",
        "save_hotkeys",
        "get_local_whisper_status",
        "prepare_local_whisper_model",
        "get_ffmpeg_status",
        "get_microphones",
        "get_recommended_microphone",
        "recording_status",
        "toggle_recording",
        "start_recording",
        "stop_recording",
        "register_selected_file",
        "register_selected_docs_file",
        "check_file_duration",
        "check_docs_duration",
        "_duration_metadata",
        "transcribe_file",
        "_finish_file_transcription",
        "save_transcript",
        "start_split_workflow",
        "docs_model_profiles",
        "docs_detail_profiles",
        "docs_preflight",
        "start_docs_workflow",
        "_finish_docs_workflow",
        "_transcribe_docs_audio",
        "_transcribe_docs_split",
        "_finish_split_workflow",
        "converter_status",
        "converter_output_formats",
        "convert_file",
        "_finish_conversion",
        "list_history",
        "clear_history",
        "update_history_text",
        "delete_history_item",
        "create_merged_history_entry",
        "copy_to_clipboard",
        "toggle_translate_setting",
        "request_shutdown",
        "hotkeys_status",
        "_start_recording",
        "_stop_recording",
        "_finish_recording_transcription",
        "_recorder_last_error",
        "_start_daemon_thread",
        "_transcribe_recording",
        "_handle_transcribed_text",
        "_create_transcriber",
        "_create_split_history_entries",
        "_track_split_artifacts",
        "_transcribe_chunks",
        "_mark_transcription_error",
        "_prepare_audio_for_transcription",
        "_emit_history",
        "_resolve_audio_file",
        "_file_from_token",
        "_docs_file_from_token",
        "_file_metadata",
        "_emit_docs_generation_progress",
        "_resolve_docs_output_language",
        "_write_markdown_atomic",
        "_history_result",
        "_emit",
        "_reload_config",
        "_save_language",
        "_save_microphone",
        "_save_api_key",
        "_require_bool",
        "_recording_exists",
        "_load_sounddevice",
        "_expanded_hotkey_forms",
        "_hotkeys_conflict",
    }
)

R0_DISCOVERED_TEST_IDS = tuple(
    line.strip()
    for line in """
test_audio_cleanup.AudioCleanupTests.test_cleanup_audio_file_deletes_generated_copy
test_audio_cleanup.AudioCleanupTests.test_noisy_uses_afftdn_when_rnnoise_model_is_missing
test_audio_cleanup.AudioCleanupTests.test_noisy_uses_rnnoise_when_model_exists
test_audio_cleanup.AudioCleanupTests.test_noops_when_disabled
test_audio_cleanup.AudioCleanupTests.test_noops_when_ffmpeg_is_unavailable
test_audio_cleanup.AudioCleanupTests.test_normal_filter_chain
test_audio_cleanup.AudioCleanupTests.test_returns_cleanup_file_when_ffmpeg_succeeds
test_audio_cleanup.AudioCleanupTests.test_severe_uses_afftdn_when_rnnoise_model_is_missing
test_audio_duration.AudioDurationTests.test_splitter_uses_tinytag_before_fallbacks
test_audio_duration.AudioDurationTests.test_transcriber_falls_back_to_ffprobe
test_audio_duration.AudioDurationTests.test_transcriber_uses_tinytag_duration
test_documentation.DocumentationTests.test_can_select_qwen_model_profile
test_documentation.DocumentationTests.test_detail_profile_changes_max_tokens_and_prompt
test_documentation.DocumentationTests.test_english_output_language_prompt_uses_english_headings
test_documentation.DocumentationTests.test_generate_markdown_uses_chat_completion
test_documentation.DocumentationTests.test_invalid_output_language_is_rejected
test_documentation.DocumentationTests.test_long_paragraph_split_prefers_sentence_boundaries
test_documentation.DocumentationTests.test_long_transcript_is_reduced_before_final_markdown
test_documentation.DocumentationTests.test_progress_callback_reports_model_calls
test_documentation.DocumentationTests.test_same_language_uses_transcript_language_instruction
test_documentation.DocumentationTests.test_turkish_output_language_prompt_uses_turkish_instructions
test_hotkeys.HotkeyControllerTests.test_alt_r_toggle_debounces_until_release
test_hotkeys.HotkeyControllerTests.test_hotkey_state_uses_reloaded_config
test_hotkeys.HotkeyControllerTests.test_right_ctrl_release_after_threshold_stops_for_transcription
test_hotkeys.HotkeyControllerTests.test_right_ctrl_release_before_threshold_discards_recording
test_hotkeys.HotkeyControllerTests.test_shift_t_toggles_translate_once_per_chord
test_local_translate_models.LocalTranslateModelTests.test_fast_and_balanced_use_same_models_for_translation_and_transcription
test_local_translate_models.LocalTranslateModelTests.test_groq_translate_uses_translations_endpoint
test_local_translate_models.LocalTranslateModelTests.test_high_quality_uses_large_v3_model
test_local_translate_models.LocalTranslateModelTests.test_linux_model_dir_falls_back_to_home_local_share
test_local_translate_models.LocalTranslateModelTests.test_linux_model_dir_uses_xdg_data_home
test_local_translate_models.LocalTranslateModelTests.test_linux_prepare_downloads_to_managed_model_dir
test_local_translate_models.LocalTranslateModelTests.test_linux_status_ignores_ready_global_faster_whisper_cache
test_local_translate_models.LocalTranslateModelTests.test_local_audio_cleanup_enables_vad_filter
test_local_translate_models.LocalTranslateModelTests.test_local_non_translate_passes_transcribe_task
test_local_translate_models.LocalTranslateModelTests.test_local_status_detects_ready_faster_whisper_cache
test_local_translate_models.LocalTranslateModelTests.test_local_translate_passes_translate_task_and_language
test_local_translate_models.LocalTranslateModelTests.test_quality_transcription_uses_turbo_model
test_local_translate_models.LocalTranslateModelTests.test_quality_translation_keeps_selected_turbo_model
test_runtime_privacy.RuntimePrivacyTests.test_close_deletes_only_app_generated_files_inside_temp
test_runtime_privacy.RuntimePrivacyTests.test_env_file_permissions_are_owner_only_on_posix
test_runtime_privacy.RuntimePrivacyTests.test_stale_cleanup_removes_only_known_old_artifacts
test_security_hardening.ConfigSecurityTests.test_api_key_rejects_env_injection
test_security_hardening.ConfigSecurityTests.test_env_values_reject_newline_injection
test_security_hardening.ConfigSecurityTests.test_env_values_reject_nul_injection
test_security_hardening.ConfigSecurityTests.test_local_whisper_model_must_be_supported
test_security_hardening.DesktopIpcSecurityTests.test_dashboard_declares_content_security_policy
test_security_hardening.DesktopIpcSecurityTests.test_dashboard_preload_does_not_expose_generic_invoke
test_security_hardening.DesktopIpcSecurityTests.test_docs_preview_uses_directory_tokens
test_security_hardening.DesktopIpcSecurityTests.test_each_window_uses_its_own_preload_and_sandbox
test_security_hardening.DesktopIpcSecurityTests.test_ipc_requires_main_frame_and_expected_renderer_url
test_security_hardening.DesktopIpcSecurityTests.test_main_sidecar_invoke_uses_allowlists
test_security_hardening.DesktopIpcSecurityTests.test_quick_page_has_strict_csp_and_no_inline_assets
test_security_hardening.DesktopIpcSecurityTests.test_rnnoise_download_is_removed_from_desktop_bridges
test_security_hardening.DesktopIpcSecurityTests.test_sidecar_client_attempts_graceful_shutdown_before_kill
test_security_hardening.DesktopIpcSecurityTests.test_windows_block_navigation_and_new_windows
test_sidecar.SidecarTests.test_clipboard_copy_uses_injector
test_sidecar.SidecarTests.test_converter_request_returns_while_conversion_continues
test_sidecar.SidecarTests.test_docs_details_return_supported_profiles
test_sidecar.SidecarTests.test_docs_models_return_supported_profiles
test_sidecar.SidecarTests.test_docs_preflight_defaults_output_language_from_settings_language
test_sidecar.SidecarTests.test_docs_preflight_rejects_invalid_token_model_and_output_language
test_sidecar.SidecarTests.test_docs_preflight_reports_missing_api_key_before_save
test_sidecar.SidecarTests.test_docs_request_returns_while_workflow_continues
test_sidecar.SidecarTests.test_docs_requires_groq_api_key_for_markdown_generation
test_sidecar.SidecarTests.test_file_transcription_request_returns_while_transcription_continues
test_sidecar.SidecarTests.test_history_methods_mutate_and_return_list
test_sidecar.SidecarTests.test_install_rnnoise_model_copies_and_saves_managed_path
test_sidecar.SidecarTests.test_install_rnnoise_model_rejects_invalid_path_and_extension
test_sidecar.SidecarTests.test_invalid_params_returns_invalid_params
test_sidecar.SidecarTests.test_parser_accepts_valid_request
test_sidecar.SidecarTests.test_recording_stop_returns_while_transcription_continues
test_sidecar.SidecarTests.test_settings_get_does_not_expose_api_key
test_sidecar.SidecarTests.test_settings_get_maps_legacy_audio_cleanup_enabled_to_noisy
test_sidecar.SidecarTests.test_settings_get_reports_rnnoise_missing_status
test_sidecar.SidecarTests.test_settings_save_allows_rnnoise_modes_when_ready
test_sidecar.SidecarTests.test_settings_save_downgrades_legacy_audio_cleanup_enabled_when_not_ready
test_sidecar.SidecarTests.test_settings_save_downgrades_rnnoise_modes_when_not_ready
test_sidecar.SidecarTests.test_settings_save_persists_selected_microphone
test_sidecar.SidecarTests.test_settings_save_uses_config_validation
test_sidecar.SidecarTests.test_sidecar_can_return_event_before_response
test_sidecar.SidecarTests.test_sidecar_does_not_expose_rnnoise_download
test_sidecar.SidecarTests.test_sidecar_subprocess_ping
test_sidecar.SidecarTests.test_sidecar_subprocess_register_selected_file_uses_utf8_stdio
test_sidecar.SidecarTests.test_split_request_returns_while_workflow_continues
test_sidecar.SidecarTests.test_unknown_method_returns_method_not_found
""".splitlines()
    if line.strip()
)


def _module_tree(relative_path: str) -> ast.Module:
    path = ROOT / relative_path
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _dispatch_tree() -> ast.FunctionDef:
    tree = _module_tree("src/sidecar.py")
    server = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SidecarJsonRpcServer"
    )
    return next(
        node
        for node in server.body
        if isinstance(node, ast.FunctionDef) and node.name == "dispatch"
    )


def _dispatch_method_names() -> frozenset[str]:
    names: set[str] = set()
    for node in ast.walk(_dispatch_tree()):
        if not isinstance(node, ast.Compare):
            continue
        if not isinstance(node.left, ast.Name) or node.left.id != "method":
            continue
        names.update(
            value.value
            for value in node.comparators
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
        )
    return frozenset(names)


def _dispatch_service_calls() -> frozenset[str]:
    names: set[str] = set()
    for node in ast.walk(_dispatch_tree()):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value
        if (
            isinstance(owner, ast.Attribute)
            and isinstance(owner.value, ast.Name)
            and owner.value.id == "self"
            and owner.attr == "service"
        ):
            names.add(node.func.attr)
    return frozenset(names)


def _event_names() -> frozenset[str]:
    names: set[str] = set()
    backend_modules = sorted((ROOT / "src" / "core" / "backend").glob("*.py"))
    relative_paths = (
        "src/core/backend_service.py",
        "src/sidecar.py",
        *(path.relative_to(ROOT).as_posix() for path in backend_modules),
    )
    for relative_path in relative_paths:
        for node in ast.walk(_module_tree(relative_path)):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"_emit", "queue_event"} or not node.args:
                continue
            event_name = node.args[0]
            if isinstance(event_name, ast.Constant) and isinstance(event_name.value, str):
                names.add(event_name.value)
    return frozenset(names)


def _facade_signature(method_name: str) -> str:
    parameters = inspect.signature(getattr(BackendService, method_name)).parameters.values()
    rendered: list[str] = []
    keyword_only_started = False
    for parameter in parameters:
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY and not keyword_only_started:
            rendered.append("*")
            keyword_only_started = True
        value = parameter.name
        if parameter.default is not inspect.Parameter.empty:
            value += f"={parameter.default!r}"
        rendered.append(value)
    return ", ".join(rendered)


def _braced_block(source: str, marker: str) -> str:
    marker_start = source.index(marker)
    start = source.index("{", marker_start)
    depth = 0
    for index in range(start, len(source)):
        character = source[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Unclosed TypeScript block after {marker!r}")


def _bridge_surface(relative_path: str, marker: str) -> dict[str, frozenset[str] | None]:
    source = (ROOT / relative_path).read_text(encoding="utf-8")
    block = _braced_block(source, marker)
    top_level = re.findall(r"^  ([A-Za-z][A-Za-z0-9]*):", block, re.MULTILINE)
    surface: dict[str, frozenset[str] | None] = {}
    for name in top_level:
        group_match = re.search(rf"^  {re.escape(name)}:\s*{{", block, re.MULTILINE)
        if not group_match:
            surface[name] = None
            continue
        group = _braced_block(block, group_match.group(0))
        surface[name] = frozenset(
            re.findall(r"^    ([A-Za-z][A-Za-z0-9]*):", group, re.MULTILINE)
        )
    return surface


def _renderer_component_names() -> frozenset[str]:
    pattern = re.compile(
        r"^(?:export\s+)?(?:default\s+)?function\s+([A-Z][A-Za-z0-9]*)\s*\(",
        re.MULTILINE,
    )
    names: set[str] = set()
    for path in (ROOT / "desktop" / "renderer" / "src").rglob("*.tsx"):
        names.update(pattern.findall(path.read_text(encoding="utf-8")))
    return frozenset(names)


def _discovered_test_ids() -> frozenset[str]:
    suite = unittest.TestLoader().discover(
        str(ROOT / "tests"),
        top_level_dir=str(ROOT),
    )

    def iter_tests(current: unittest.TestSuite):
        for test in current:
            if isinstance(test, unittest.TestSuite):
                yield from iter_tests(test)
            else:
                yield test

    return frozenset(test.id().removeprefix("tests.") for test in iter_tests(suite))


def _r0_test_owners(recorded_id: str, current_ids: frozenset[str]) -> tuple[str, ...]:
    if recorded_id.startswith("test_sidecar.SidecarTests."):
        method_name = recorded_id.rsplit(".", 1)[-1]
        return tuple(
            sorted(
                test_id
                for test_id in current_ids
                if test_id.startswith("test_sidecar_")
                and test_id.endswith(f".{method_name}")
            )
        )
    return (recorded_id,) if recorded_id in current_ids else ()


class BackendServiceContractTests(unittest.TestCase):
    def test_stable_facade_symbols_remain_importable(self):
        self.assertTrue(callable(BackendService))
        self.assertTrue(issubclass(BackendValidationError, ValueError))
        self.assertTrue(callable(cleanup_stale_temp_files))

    def test_dispatch_json_rpc_method_names_match_contract(self):
        self.assertEqual(_dispatch_method_names(), EXPECTED_JSON_RPC_METHODS)

    def test_dispatch_facade_methods_exist_and_are_callable(self):
        self.assertEqual(_dispatch_service_calls(), frozenset(EXPECTED_SERVICE_SIGNATURES))
        for method_name in EXPECTED_SERVICE_SIGNATURES:
            self.assertTrue(callable(getattr(BackendService, method_name, None)), method_name)

    def test_sidecar_facing_facade_signatures_match_contract(self):
        actual = {
            method_name: _facade_signature(method_name)
            for method_name in EXPECTED_SERVICE_SIGNATURES
        }
        self.assertEqual(actual, EXPECTED_SERVICE_SIGNATURES)

    def test_sidecar_event_names_match_contract(self):
        self.assertEqual(_event_names(), EXPECTED_EVENT_NAMES)

    def test_preload_and_renderer_bridge_surfaces_match_contract(self):
        preload = _bridge_surface("desktop/preload/preload.ts", "const api =")
        renderer = _bridge_surface(
            "desktop/renderer/src/types/yaverVoice.ts",
            "export type YaverVoiceApi =",
        )
        self.assertEqual(preload, EXPECTED_BRIDGE_SURFACE)
        self.assertEqual(renderer, EXPECTED_BRIDGE_SURFACE)

    def test_local_whisper_setup_ui_requires_confirmation_and_shows_real_bytes(self):
        dialog_path = ROOT / "desktop" / "renderer" / "src" / "views" / "settings" / "LocalWhisperSetupDialog.tsx"
        self.assertTrue(dialog_path.exists())
        dialog = dialog_path.read_text(encoding="utf-8")
        settings_view = (ROOT / "desktop" / "renderer" / "src" / "views" / "settings" / "SettingsView.tsx").read_text(
            encoding="utf-8"
        )
        main = (ROOT / "desktop" / "main" / "main.ts").read_text(encoding="utf-8")
        preload = (ROOT / "desktop" / "preload" / "preload.ts").read_text(encoding="utf-8")

        self.assertIn("Download local model?", dialog)
        self.assertIn('role="progressbar"', dialog)
        self.assertIn("downloadedBytes", dialog)
        self.assertIn("totalBytes", dialog)
        self.assertIn("modelDir", dialog)
        self.assertIn("getLocalWhisperSetupInfo", settings_view)
        self.assertIn("prepareLocalWhisperModel", settings_view)
        self.assertIn('"settings.get_local_whisper_setup_info"', main)
        self.assertIn('"settings.get_local_whisper_setup_info"', preload)

    def test_r0_renderer_components_remain_owned(self):
        missing = frozenset(R0_RENDERER_COMPONENTS_IN_MAIN) - _renderer_component_names()
        self.assertEqual(missing, frozenset())

    def test_r0_backend_methods_remain_callable_through_facade(self):
        missing = frozenset(
            method_name
            for method_name in R0_BACKEND_METHODS_IN_FACADE
            if not callable(getattr(BackendService, method_name, None))
        )
        self.assertEqual(missing, frozenset())

    def test_r0_discovered_scenarios_remain_owned_once(self):
        current_ids = _discovered_test_ids()
        invalid_owners = {
            recorded_id: _r0_test_owners(recorded_id, current_ids)
            for recorded_id in R0_DISCOVERED_TEST_IDS
            if len(_r0_test_owners(recorded_id, current_ids)) != 1
        }
        self.assertEqual(invalid_owners, {})


if __name__ == "__main__":
    unittest.main()
