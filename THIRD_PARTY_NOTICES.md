# Third-Party Notices

YaverVoice is licensed under GPL-3.0-only, but its dependencies remain under their own licenses. The table lists direct dependencies and the version policies used by this source beta; it is not a replacement for upstream license texts.

## Python runtime

| Dependency | Version policy | License | Upstream |
| --- | --- | --- | --- |
| sounddevice | `>=0.4.6` | MIT | https://github.com/spatialaudio/python-sounddevice |
| NumPy | `>=1.24.0` | BSD-3-Clause | https://github.com/numpy/numpy |
| SoundFile | `>=0.12.1` | BSD-3-Clause | https://github.com/bastibe/python-soundfile |
| TinyTag | `>=2.2.1,<3` | MIT | https://github.com/tinytag/tinytag |
| pynput | `>=1.7.6` | LGPL-3.0 | https://github.com/moses-palmer/pynput |
| groq | `>=0.4.1` | Apache-2.0 | https://github.com/groq/groq-python |
| python-dotenv | `>=1.0.0` | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| PyAutoGUI | `>=0.9.54` | BSD-3-Clause | https://github.com/asweigart/pyautogui |
| Pyperclip | `>=1.8.0` | BSD-3-Clause | https://github.com/asweigart/pyperclip |

## Optional and build-only Python

| Dependency | Version policy | License | Upstream |
| --- | --- | --- | --- |
| faster-whisper | See `requirements-local.txt` | MIT | https://github.com/SYSTRAN/faster-whisper |
| PyInstaller | `>=6.0.0,<7` | GPL-2.0-or-later with a special exception | https://github.com/pyinstaller/pyinstaller |

## Node/Electron direct dependencies

| Dependency | Version policy | License | Upstream |
| --- | --- | --- | --- |
| Electron | `43.1.0` | MIT | https://github.com/electron/electron |
| React / React DOM | `^18.3.1` | MIT | https://github.com/facebook/react |
| Vite | `^6.0.7` | MIT | https://github.com/vitejs/vite |
| TypeScript | `^5.7.2` | Apache-2.0 | https://github.com/microsoft/TypeScript |
| Lucide React | `^0.468.0` | ISC | https://github.com/lucide-icons/lucide |
| electron-builder | `^26.8.1` | MIT | https://github.com/electron-userland/electron-builder |
| @vitejs/plugin-react | `^5.0.4` | MIT | https://github.com/vitejs/vite-plugin-react |
| concurrently | `^9.2.1` | MIT | https://github.com/open-cli-tools/concurrently |
| wait-on | `^8.0.1` | MIT | https://github.com/jeffbski/wait-on |
| @types/node, @types/react, @types/react-dom | See `package.json` | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped |

Before publishing a bundled executable, maintainers must generate and review a complete transitive SBOM/license inventory, include required license texts, and specifically validate LGPL/native-library redistribution obligations. No executable is part of `v0.1.0-beta.1`.
