# Changelog

All notable changes to YaverVoice will be documented here.

## [0.1.0-beta.1] - Unreleased

### Added

- Source-only Windows-primary/Linux desktop beta.
- Groq Cloud and Local Whisper transcription workflows.
- Recording, file transcription, split, Docs, converter, History, and Quick Dictation surfaces.
- Electron sandbox, strict preload separation, renderer CSP, navigation blocking, sender URL/frame checks, and IPC allowlists.
- Open-source community, privacy, security, third-party notice, CI, and contribution files.

### Changed

- Canonical app-data storage now uses the YaverVoice directory name; existing GroqWhisper data migrates without overwriting files already present under YaverVoice.
- Replaced GPL-licensed Mutagen with MIT-licensed TinyTag.
- Moved PyInstaller to `requirements-build.txt`.
- Upgraded Electron to 43.1.0 and Node typings to the Node 24 line.
- RNNoise models are now selected manually; automatic download was removed.

### Fixed

- Stale managed RNNoise model paths are repaired after legacy app-data migration without changing external model paths.
- Temporary cleanup WAV files are deleted after use.
- App-created recording and split artifacts are removed during graceful sidecar shutdown.
