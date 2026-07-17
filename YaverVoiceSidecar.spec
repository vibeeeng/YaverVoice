# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all, collect_submodules


datas = [
    ("build/build_info.json", "."),
]
binaries = []
hiddenimports = []
hiddenimports += collect_submodules("pynput")
hiddenimports += collect_submodules("sounddevice")
hiddenimports += collect_submodules("soundfile")
hiddenimports += collect_submodules("tinytag")
hiddenimports += collect_submodules("pyautogui")
hiddenimports += collect_submodules("pyperclip")
hiddenimports += collect_submodules("groq")
hiddenimports += collect_submodules("dotenv")

faster_whisper_datas, faster_whisper_binaries, faster_whisper_hiddenimports = collect_all("faster_whisper")
ctranslate2_datas, ctranslate2_binaries, ctranslate2_hiddenimports = collect_all("ctranslate2")

datas += faster_whisper_datas + ctranslate2_datas
binaries += faster_whisper_binaries + ctranslate2_binaries
hiddenimports += faster_whisper_hiddenimports + ctranslate2_hiddenimports


a = Analysis(
    ["src/sidecar.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["webview"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="YaverVoiceSidecar",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="logo/logo1.ico",
)
