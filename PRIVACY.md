# Privacy

YaverVoice is a desktop application. It does not include telemetry, analytics, advertising, accounts, or hosted YaverVoice storage.

## Data flows

| Feature | Where data is processed |
| --- | --- |
| Local Whisper transcription | On your device |
| Groq Cloud transcription/translation | Audio is sent directly to Groq with your API key |
| Docs Markdown generation | Transcript text is sent directly to Groq with your API key |
| Current-session History | In sidecar memory on your device |
| Saved transcript, Markdown, converter output | At the path you select |

Groq documents its current default retention and Zero Data Retention options at [Your Data](https://console.groq.com/docs/your-data). Those terms are controlled by Groq and your Groq account, not by YaverVoice.

## Local storage

- Settings, including the Groq API key, are stored as plaintext in an `.env` file under the current user's app-data directory.
- POSIX systems set that file to mode `0600`. Windows uses the current user's app-data ACLs.
- The API key is not returned by the sidecar, displayed in full by the UI, or intentionally written to logs.
- Local Whisper models and manually imported RNNoise models are stored under user app-data.

## Temporary audio

- Cleanup and upload conversion copies are deleted when processing finishes.
- Microphone recordings and split chunks remain available for current-session History, then are removed during graceful sidecar shutdown.
- On startup, known YaverVoice temp patterns older than 24 hours are removed to recover from crashes.
- Original files selected by the user, saved transcripts, generated Markdown files, and converter outputs are never part of automatic cleanup.

Operating-system backups, crash tools, endpoint security products, or third-party services may retain data independently. Protect your device account and do not share logs or screenshots without reviewing them for secrets and personal content.
