# AGENTS.md

## Project

This is a Python CLI for local speech-to-text dictation using Faster Whisper.

## Platforms

- macOS: hotkey, paste, and overlay use PyObjC (`hotkey.py`, `paste.py`,
  `overlay.py`); audio uses `sounddevice`.
- Linux (X11 only): double-tap Ctrl via the XRecord extension (`hotkey.py`),
  clipboard + `Shift+Insert` paste via XTest (`x11_clipboard.py`), Tk overlay
  (`linux_overlay.py`), and audio via `arecord` (`audio.py`). Only
  `python-xlib` is added; no compiled or system packages beyond `alsa-utils`.
- Platform selection lives in factories (`create_recorder`,
  `create_hotkey_listener`) and `sys.platform` checks; keep macOS behavior
  unchanged when touching Linux code, and vice versa.
- Tests run on either platform: macOS-specific tests pin the platform with
  autouse fixtures, and Linux logic is covered in `tests/test_linux.py`.

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
