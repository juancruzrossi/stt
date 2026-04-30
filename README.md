# STT

Local speech-to-text dictation for macOS using Python, Faster Whisper, and
CTranslate2.

The tool records from the microphone, transcribes locally, and pastes the text
where the cursor is focused. It does not use a paid API.

## Features

- Local Spanish speech-to-text.
- Automatic language detection.
- Spanish and English transcription out of the box.
- Whisper translation mode to English.
- Global dictation shortcut.
- Double-tap `Command` mode, similar to macOS dictation.
- Hold-to-record mode as an alternative.
- File transcription from common audio formats.
- One-time model download from Hugging Face into a project-local cache.
- Offline mode after the model is cached.
- Model cache inspection with local disk usage.
- Optional LaunchAgent for running at login.

## Requirements

- macOS, Linux, or Windows.
- `uv`.
- Homebrew on macOS, or a system package manager on Linux.
- Microphone permission.
- Accessibility and Input Monitoring permissions for global keyboard capture.

On macOS, the setup script installs `uv` and `portaudio` with Homebrew when
missing. On Linux, it tries common package managers for PortAudio and clipboard
helpers. On Windows, use `setup.ps1`.

## Install

```bash
git clone <PRIVATE_REPO_URL> stt
cd stt
./setup.sh
```

Windows:

```powershell
git clone <PRIVATE_REPO_URL> stt
cd stt
.\setup.ps1
```

The project uses `uv`:

```bash
uv sync --python 3.12
```

`uv` creates and manages the local `.venv` automatically. Do not commit `.venv`.

Local runtime artifacts are isolated inside the project:

```text
.venv/
.cache/
```

Both directories are ignored by Git.

## First Model Download

On first use, preload the default model:

```bash
./stt preload
```

This downloads:

```text
Systran/faster-whisper-small
```

Reference:

https://huggingface.co/Systran/faster-whisper-small

It is the CTranslate2 conversion of OpenAI's `whisper-small` model, used by
Faster Whisper for efficient local inference.

The wrapper sets `HF_HOME` so the model is cached inside this project:

```text
.cache/huggingface/hub/models--Systran--faster-whisper-small
```

Check cached models and disk usage:

```bash
./stt models
```

## macOS Permissions

Enable permissions for the terminal app you use: Terminal, iTerm, Warp, etc.

Open:

```text
System Settings > Privacy & Security > Microphone
System Settings > Privacy & Security > Accessibility
System Settings > Privacy & Security > Input Monitoring
```

After changing permissions, quit the terminal app completely and reopen it.

## Dictation

Default mode:

```bash
./stt listen
```

Windows:

```powershell
.\stt.cmd listen
```

Usage:

1. Focus a text field.
2. Double-tap `Command` to start recording.
3. Speak.
4. Double-tap `Command` again to stop.
5. The transcription is pasted at the cursor.

By default, language detection is automatic. Spanish audio is transcribed as
Spanish text; English audio is transcribed as English text.

You can force a language:

```bash
./stt listen --language es
./stt listen --language en
```

Adjust the double-tap timing if needed:

```bash
./stt listen --tap-interval 0.6
```

## Hold-to-Record Mode

```bash
./stt listen --language es --mode hold --hotkey ctrl+option+cmd
```

Hold `Control + Option + Command` to record. Release to transcribe and paste.

## Transcribe an Audio File

```bash
./stt transcribe /path/to/audio.mp3
```

Save to a text file:

```bash
./stt transcribe /path/to/audio.mp3 --language es --output transcript.txt
```

## Translation

Whisper's built-in translation task translates speech to English:

```bash
./stt transcribe /path/to/spanish-audio.mp3 --task translate
```

For live dictation:

```bash
./stt listen --task translate
```

Important limitation: Whisper translates to English only. It does not translate
English speech to Spanish text. For English-to-Spanish translation, this project
would need an additional local translation model. That is intentionally left as
future technical debt and is not implemented in this tool.

## Offline Mode

After the model is downloaded, you can force local-only execution:

```bash
./stt listen --offline
```

If the model is missing, offline mode fails instead of downloading anything.

This is useful for managed/company computers where downloads must be approved.

## Diagnostics

Check environment, permissions guidance, and cached models:

```bash
./stt doctor
```

Test microphone without keyboard shortcuts:

```bash
./stt test-mic --seconds 5
```

Test global keyboard capture:

```bash
./stt test-keys
```

If `test-keys` does not print `press:` and `release:` events, macOS permissions
are not enabled correctly.

## Run at Login

Optional:

```bash
./install-launch-agent.sh
```

This creates:

```text
~/Library/LaunchAgents/com.local.stt.plist
```

Logs:

```text
./stt.log
./stt.err.log
```

Do not enable this until the tool has been approved for the machine.

## Platform Support

Supported targets:

- macOS Intel.
- macOS Apple Silicon.
- Linux with X11 is the most reliable target for global hotkeys.
- Windows.

Known caveats:

- Linux Wayland may block global keyboard capture depending on the desktop
  environment and security policy.
- Clipboard paste on Linux may require `xclip` or `xsel`.
- Windows and Linux support should be validated on the actual company image.
- The current development and full end-to-end validation was done on macOS Intel.

## Troubleshooting

### macOS

**Double-tap Command does nothing.**

Enable the terminal app in:

```text
System Settings > Privacy & Security > Accessibility
System Settings > Privacy & Security > Input Monitoring
```

Then fully quit and reopen the terminal.

**The microphone does not record.**

Enable the terminal app in:

```text
System Settings > Privacy & Security > Microphone
```

Then run:

```bash
./stt test-mic --seconds 5
```

**The model downloads again after moving the folder.**

This project intentionally stores model files under `.cache/huggingface` inside
the project folder. Run:

```bash
./stt preload
```

### Linux

**Global hotkeys do not work.**

Run:

```bash
./stt test-keys
```

If no keys are printed, your desktop may block global capture. X11 usually works
better than Wayland for this type of tool.

**Pasting fails.**

Install clipboard helpers:

```bash
sudo apt-get install -y xclip xsel
```

Equivalent packages exist for `dnf` and `pacman`.

**The microphone fails to open.**

Install PortAudio:

```bash
sudo apt-get install -y portaudio19-dev
```

Then rerun:

```bash
uv sync --python 3.12
```

### Windows

**The command is not recognized.**

Use the Windows wrapper:

```powershell
.\stt.cmd doctor
```

If `uv` is missing, run:

```powershell
.\setup.ps1
```

**Global hotkeys or paste do not work in some apps.**

Run the terminal normally first. If the target app is elevated as Administrator,
the terminal may also need to run elevated for simulated paste to work.

**PowerShell blocks setup.ps1.**

Run from the project folder:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup.ps1
```

## Privacy and Security Notes

Transcription runs locally after installation and model download.

Network access is used for:

- Installing Python dependencies with `uv`.
- Installing `portaudio` with Homebrew.
- Downloading the Faster Whisper model from Hugging Face on first use.

The tool does not intentionally upload microphone audio, transcripts, clipboard
content, or keystrokes.

The main security considerations are standard supply-chain and macOS permission
risks:

- Python dependencies are installed from package indexes.
- The model is downloaded from Hugging Face.
- Global hotkeys require Accessibility/Input Monitoring permissions.
- Microphone access is required to record audio.
- The tool uses the clipboard briefly to paste the final transcript.

For stricter company usage:

- Review the source code.
- Keep `uv.lock` committed.
- Preload the model once in an approved environment.
- Copy/cache the model on target machines.
- Run with `--offline`.
- Avoid the LaunchAgent until approved.

## Default Model

Default:

```text
small
```

Resolved by Faster Whisper to:

```text
Systran/faster-whisper-small
```

The `small` model is a practical default for Spanish dictation on CPU. Larger
models may improve accuracy but use more disk, memory, and CPU time.
