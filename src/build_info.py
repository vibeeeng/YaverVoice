"""
Build metadata helpers for packaged and source runs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


DEFAULT_BUILD_INFO = {
    "version": "source",
    "build_time": "Source Run",
    "git_commit": "working-tree",
    "display": "Source Run",
}


def load_build_info() -> dict[str, str]:
    """Load build metadata bundled by the Windows build script."""
    if not getattr(sys, "frozen", False):
        return DEFAULT_BUILD_INFO.copy()

    candidates: list[Path] = []
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidates.append(Path(bundle_dir) / "build_info.json")

    candidates.append(Path(sys.executable).resolve().parent / "build_info.json")

    for path in candidates:
        if not path.exists():
            continue

        try:
            raw_data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue

        build_info = DEFAULT_BUILD_INFO.copy()
        for key in build_info:
            value = raw_data.get(key)
            if value:
                build_info[key] = str(value)
        return build_info

    return DEFAULT_BUILD_INFO.copy()
