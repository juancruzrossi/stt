# Security

## Data flow

During normal use, STT captures microphone audio in memory, transcribes it with
a local Faster Whisper model, briefly places the result on the clipboard, and
pastes it into the focused application. Audio and transcripts are not sent to a
remote transcription service.

The installer requires network access for locked Python packages and the pinned
model revision. The installed launcher runs the virtual environment directly
with Hugging Face offline mode and telemetry disabled.

## Installation

- Review and clone a specific commit before running `install.sh`.
- Install `uv` and Python 3.12 through an approved package manager. The
  installer does not bootstrap tools or use `sudo`.
- Python packages are resolved from `uv.lock`; the model revision and required
  file hashes are fixed in `src/stt/model_config.py`.
- Re-run the installer deliberately after reviewing updates. It never performs
  `git pull` or self-updates.
- CI runs tests, static checks, and a runtime dependency audit;
  Dependabot proposes lockfile and workflow updates through pull requests.

## Local data

- Recorded microphone audio stays in memory and is discarded after processing.
- Transcripts are not logged unless `--verbose` is explicitly used.
- `--output` writes a transcript to the path selected by the user.
- Clipboard restoration occurs only if no other process changed the clipboard
  after STT initiated the paste.

## Permissions

Global hotkeys and automatic paste require Accessibility and Input Monitoring;
recording requires Microphone access. On macOS, command-line tools inherit the
terminal application's permissions. This is an operating-system limitation and
the main residual risk of the CLI architecture.

Review and revoke permissions in System Settings when STT is no longer needed.
Do not dictate secrets while an untrusted application has clipboard access.

## Reporting

Do not include corporate audio, transcripts, logs, credentials, or model files
in public issue reports. Describe security concerns without sensitive data.
