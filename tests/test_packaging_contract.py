"""Static contracts for the packaged sidecar artifact and runtime path."""

from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATHS_PATTERN = re.compile(
    r"^\$artifactPaths\s*=\s*@\(\s*(?P<body>.*?)^\)$",
    re.DOTALL | re.MULTILINE,
)
PYINSTALL_COMMAND_PATTERN = re.compile(
    r'^& \$pythonExe -m PyInstaller --noconfirm '
    r'--distpath \(Join-Path \$repoRoot "dist\\sidecar"\) '
    r'--workpath \(Join-Path \$repoRoot "build\\YaverVoiceSidecar"\) '
    r'YaverVoiceSidecar\.spec$',
    re.MULTILINE,
)
BUNDLED_SIDECAR_GUARD_PATTERN = re.compile(
    r"if \(!existsSync\(executablePath\)\) \{\s*"
    r"throw new SidecarError\(`Bundled sidecar was not found at "
    r"\$\{executablePath\}\.`\);\s*"
    r"\}\s*"
    r"return \{ command: executablePath, args: \[\], cwd: resourcesPath \};"
)


def _packaging_sources() -> tuple[str, str, dict[str, Any], str]:
    build_script = (ROOT / "build.ps1").read_text(encoding="utf-8")
    spec = (ROOT / "YaverVoiceSidecar.spec").read_text(encoding="utf-8")
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    client = (ROOT / "desktop" / "main" / "sidecarClient.ts").read_text(
        encoding="utf-8"
    )
    return build_script, spec, package, client


def _assigned_call(tree: ast.Module, target: str, callee: str) -> ast.Call | None:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(name, ast.Name) and name.id == target for name in node.targets):
            continue
        if (
            isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == callee
        ):
            return node.value
    return None


def _braced_block(source: str, marker: str, brace_number: int = 0) -> str:
    marker_start = source.index(marker)
    start = marker_start
    for _ in range(brace_number + 1):
        start = source.index("{", start + 1)
    depth = 0
    for index in range(start, len(source)):
        character = source[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise ValueError(f"Unclosed block after {marker!r}")


def _packaging_contract_errors(
    build_script: str,
    spec: str,
    package: dict[str, Any],
    client: str,
) -> tuple[str, ...]:
    artifact_paths = ARTIFACT_PATHS_PATTERN.search(build_script)
    artifact_body = artifact_paths.group("body") if artifact_paths else ""

    try:
        spec_tree = ast.parse(spec, filename="YaverVoiceSidecar.spec")
    except SyntaxError:
        spec_tree = ast.Module(body=[], type_ignores=[])
    analysis = _assigned_call(spec_tree, "a", "Analysis")
    executable = _assigned_call(spec_tree, "exe", "EXE")
    analysis_entry = None
    if analysis is not None and analysis.args:
        try:
            analysis_entry = ast.literal_eval(analysis.args[0])
        except (ValueError, TypeError):
            pass
    executable_name = None
    if executable is not None:
        name_keyword = next(
            (keyword for keyword in executable.keywords if keyword.arg == "name"),
            None,
        )
        if name_keyword is not None and isinstance(name_keyword.value, ast.Constant):
            executable_name = name_keyword.value.value

    try:
        method_block = _braced_block(
            client,
            "private resolvePythonCommand",
            brace_number=1,
        )
        packaged_block = _braced_block(method_block, "if (this.packaged)")
    except ValueError:
        packaged_block = ""

    try:
        extra_resources = package["build"]["extraResources"]
    except (KeyError, TypeError):
        extra_resources = []

    checks = {
        "artifact-paths": artifact_paths is not None
        and all(
            expected in artifact_body
            for expected in (
                '(Join-Path $repoRoot "dist\\sidecar")',
                '(Join-Path $repoRoot "dist-electron")',
                '(Join-Path $repoRoot "build\\YaverVoiceSidecar")',
            )
        ),
        "pyinstaller-distpath": PYINSTALL_COMMAND_PATTERN.search(build_script)
        is not None,
        "analysis-entry": analysis_entry == ["src/sidecar.py"],
        "exe-name": executable_name == "YaverVoiceSidecar",
        "extra-resources": {
            "from": "dist/sidecar/YaverVoiceSidecar.exe",
            "to": "sidecar/YaverVoiceSidecar.exe",
        }
        in extra_resources,
        "runtime-path": (
            'process.platform === "win32" ? "YaverVoiceSidecar.exe" : "YaverVoiceSidecar"'
            in packaged_block
            and 'join(resourcesPath, "sidecar", executableName)' in packaged_block
        ),
        "bundled-sidecar-guard": BUNDLED_SIDECAR_GUARD_PATTERN.search(
            packaged_block
        )
        is not None,
        "empty-runtime-args": (
            "return { command: executablePath, args: [], cwd: resourcesPath };"
            in packaged_block
        ),
    }
    return tuple(name for name, valid in checks.items() if not valid)


class PackagingContractTests(unittest.TestCase):
    def test_public_readme_documents_first_run_and_windows_build(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for required in (
            "screenshots/yavervoice-main.png",
            "## First run",
            "Set Up Local Mode",
            "ffmpeg -version",
            "ffprobe -version",
            "## Build Windows EXEs",
            "npm run build:windows",
            "unsigned",
            "dist-electron/",
        ):
            with self.subTest(required=required):
                self.assertIn(required, readme)

        self.assertTrue((ROOT / "screenshots" / "yavervoice-main.png").is_file())

    def test_env_example_describes_manual_rnnoise_model_selection(self):
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertNotIn("Prefer Download model in Settings", env_example)
        self.assertIn("Select a trusted .rnnn model manually", env_example)

    def test_public_windows_build_entrypoint_is_discoverable_and_pinned(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))

        self.assertIn("build:windows", package["scripts"])
        self.assertEqual(
            package["scripts"]["build:windows"],
            "powershell -NoProfile -ExecutionPolicy Bypass -File ./build.ps1",
        )
        self.assertEqual(package["engines"], {"node": ">=24 <25", "npm": ">=11"})
        self.assertEqual(package["packageManager"], "npm@11.6.2")
        self.assertEqual(package.get("author"), "vibeeeng")

    def test_windows_build_preflights_report_actionable_setup(self):
        build_script = (ROOT / "build.ps1").read_text(encoding="utf-8")

        for required_message in (
            "Windows is required to build the YaverVoice EXE artifacts",
            "Node.js 24 is required",
            "npm 11 or newer is required",
            "Run npm ci",
            "requirements-build.txt",
            "requirements-local.txt",
            "package-lock.json",
            "YaverVoiceSidecar.spec",
        ):
            with self.subTest(required_message=required_message):
                self.assertIn(required_message, build_script)

    def test_windows_build_bundles_and_smoke_checks_local_whisper(self):
        build_script = (ROOT / "build.ps1").read_text(encoding="utf-8")
        spec = (ROOT / "YaverVoiceSidecar.spec").read_text(encoding="utf-8")

        for required_build_contract in (
            "import ctranslate2, faster_whisper",
            "settings.get_local_whisper_status",
            "dependency_available",
            "Local Whisper build dependencies are missing",
        ):
            with self.subTest(required_build_contract=required_build_contract):
                self.assertIn(required_build_contract, build_script)

        self.assertIn('collect_all("faster_whisper")', spec)
        self.assertIn('collect_all("ctranslate2")', spec)

    def test_windows_build_verifies_expected_artifacts(self):
        build_script = (ROOT / "build.ps1").read_text(encoding="utf-8")

        self.assertIn("Expected packaged sidecar was not created", build_script)
        self.assertIn(
            "Expected Windows installer and portable EXE artifacts",
            build_script,
        )

    def test_normal_desktop_dev_commands_keep_chromium_sandbox_enabled(self):
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        dev_script = (ROOT / "desktop" / "scripts" / "dev.js").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("--no-sandbox", package["scripts"]["desktop:electron:dev"])
        self.assertNotIn("--no-sandbox", dev_script)

    def test_packaged_sidecar_paths_agree_across_build_and_runtime(self):
        errors = _packaging_contract_errors(*_packaging_sources())
        self.assertEqual(errors, ())

    def test_packaging_contract_rejects_wrong_distpath_and_inverted_guard(self):
        build_script, spec, package, client = _packaging_sources()
        wrong_distpath = build_script.replace(
            r'--distpath (Join-Path $repoRoot "dist\sidecar")',
            r'--distpath (Join-Path $repoRoot "dist\other")',
        )
        inverted_guard = client.replace(
            "if (!existsSync(executablePath))",
            "if (existsSync(executablePath))",
        )
        self.assertNotEqual(wrong_distpath, build_script)
        self.assertNotEqual(inverted_guard, client)

        self.assertIn(
            "pyinstaller-distpath",
            _packaging_contract_errors(wrong_distpath, spec, package, client),
        )
        self.assertIn(
            "bundled-sidecar-guard",
            _packaging_contract_errors(build_script, spec, package, inverted_guard),
        )

if __name__ == "__main__":
    unittest.main()
