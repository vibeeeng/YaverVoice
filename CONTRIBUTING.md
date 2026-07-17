# Contributing to YaverVoice

Thanks for helping improve YaverVoice. This repository accepts issues and focused pull requests for the desktop application.

## Before opening an issue

- Search existing issues first.
- Do not include API keys, `.env` contents, private audio, transcripts, logs, or screenshots containing personal data.
- Use the bug form for reproducible defects and the feature form for scoped proposals.
- Security reports must follow [SECURITY.md](SECURITY.md), not a public issue.

## Pull requests

1. Create a branch from the current default branch.
2. Keep the change small and limited to one concern.
3. Preserve the Electron + Python sidecar contract and Windows/Linux behavior.
4. Add or update focused tests for behavior changes.
5. Update `README.md` and `CHANGELOG.md` when setup, usage, dependencies, or user-visible behavior changes.
6. Complete the pull request template and explain any validation not run.

Useful checks:

```bash
python -m unittest discover -s tests
npm run desktop:typecheck
npm audit --audit-level=high
```

Do not commit `.env`, credentials, recordings, transcripts, generated media, model caches, build output, or personal agent/tool files.

## Licensing

By submitting a contribution, you agree that it is your original work (or that you have the right to submit it) and that it may be distributed under the repository's GNU General Public License v3.0 only (GPL-3.0-only). No Contributor License Agreement is required.

All contributors must follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
