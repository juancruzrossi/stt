# AGENTS.md

## Project

This is a macOS speech-to-text app with an optional Python CLI. Both use Faster
Whisper locally.

## Development

- Keep changes small and focused.
- Use `uv` for Python dependency management and command execution.
- Do not introduce paid APIs or remote transcription services.
- Preserve local-first behavior: microphone audio and transcripts should stay on the user's machine during normal usage.
- Keep the app macOS-only and use native AppKit behavior.
- GitHub Releases distribute the app; `cli-install.sh` installs only the CLI.
- Release builds bundle the pinned, verified model for an offline first launch.
- Keep both interfaces simple unless there is a clear user need.

## Checks

Before committing code changes, run:

```bash
uv run --group dev pytest
uvx ruff check src tests
```

Run `bash -n cli-install.sh build_app.sh stt` when changing shell scripts.

Run mypy when changing typed Python boundaries:

```bash
uv run --group dev mypy src
```

## Versioning

For changes that affect runtime behavior, app or CLI UX, installation,
dependencies, or other public behavior, propose the appropriate version bump
to the user before updating `pyproject.toml`.

Only update the version after the user confirms the proposed version number.

Use SemVer:

- PATCH for bug fixes, small UX changes, usage docs, or internal improvements.
- MINOR for new commands, flags, supported workflows, or backwards-compatible features.
- MAJOR for breaking app, CLI, or installation behavior.

Do not bump the version for formatting-only edits, comments, or test-only
changes unless they are part of a release commit.
