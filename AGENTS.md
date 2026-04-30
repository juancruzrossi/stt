# AGENTS.md

## Project

This is a Python CLI for local speech-to-text dictation using Faster Whisper.

## Development

- Keep changes small and focused.
- Use `uv` for Python dependency management and command execution.
- Do not introduce paid APIs or remote transcription services.
- Preserve local-first behavior: microphone audio and transcripts should stay on the user's machine during normal usage.
- Prefer simple CLI behavior over extra flags or advanced modes unless there is a clear user need.

## Checks

Before committing code changes, run:

```bash
uv run --group dev pytest
uvx ruff check src tests
```

Run mypy when changing typed Python boundaries:

```bash
uv run --group dev mypy src
```

## Versioning

For changes that affect runtime behavior, CLI UX, install flow, dependencies,
or public user-facing behavior, propose the appropriate version bump to the
user before updating `pyproject.toml`.

Only update the version after the user confirms the proposed version number.

Use SemVer:

- PATCH for bug fixes, small UX changes, usage docs, or internal improvements.
- MINOR for new commands, flags, supported workflows, or backwards-compatible features.
- MAJOR for breaking CLI or install behavior.

Do not bump the version for formatting-only edits, comments, or test-only
changes unless they are part of a release commit.
