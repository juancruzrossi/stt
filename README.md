# STT

Simple, fast local python speech-to-text dictation with Faster Whisper.

## Install

macOS and Linux:

```bash
git clone https://github.com/juancruzrossi/stt.git
cd stt
./install.sh
```

Windows:

```powershell
git clone https://github.com/juancruzrossi/stt.git
cd stt
.\install.ps1
```

The installer:

- Requires an approved `uv` and Python 3.12 installation.
- Never modifies shell profiles or installs system packages.
- Installs locked Python dependencies into an isolated `.venv`.
- Downloads the local STT model from a pinned Hugging Face commit and verifies
  every required file with SHA-256.
- Installs the `stt` command into `~/.local/bin/stt`.

The installer must run from a local checkout. Remote pipe installs and automatic
repository updates are intentionally disabled.

## macOS Permissions

Enable permissions for your terminal app in:

```text
System Settings > Privacy & Security > Microphone
System Settings > Privacy & Security > Accessibility
System Settings > Privacy & Security > Input Monitoring
```

After changing permissions, quit the terminal app completely and reopen it.

## Usage

```bash
stt listen
```

On macOS:

1. Focus a text field.
2. Double-tap `Command` to start recording.
3. Speak.
4. Double-tap `Command` again to stop.
5. The transcript is pasted at the cursor.

On Linux and Windows, the default trigger is double-tap `Control`.

By default, language detection is automatic:

- Spanish audio becomes Spanish text.
- English audio becomes English text.

Force a language only when needed:

```bash
stt listen --language es
stt listen --language en
```

Print each transcription in the terminal:

```bash
stt listen --verbose
```

Verbose output is separated with:

```text
----
```

## Doctor

Check the install, model, and microphone:

```bash
stt doctor
```

## Audio Files

Transcribe a local audio/video file to text:

```bash
stt transcribe /path/to/audio.mp3
```

Save to a text file:

```bash
stt transcribe /path/to/audio.mp3 --output transcript.txt
```

## Translation

Whisper can translate speech to English:

```bash
stt transcribe /path/to/spanish-audio.mp3 --task translate
stt listen --task translate
```

## Model

The installer downloads:

```text
Systran/faster-whisper-small@536b0662742c02347bc0e980a01041f333bce120
```

Reference:

https://huggingface.co/Systran/faster-whisper-small

Check cached model size:

```bash
stt models
```

## Platform Notes

Supported targets:

- macOS Apple Silicon/Intel.
- Linux, preferably X11 for global hotkeys.
- Windows.

## Troubleshooting

### macOS

**`stt` command not found.**

Make sure `~/.local/bin` is in your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

**Double-tap Command does nothing.**

Enable Accessibility and Input Monitoring for your terminal app. Then fully
quit and reopen the terminal.

**The microphone does not record.**

Enable Microphone permission for your terminal app. Then quit and reopen the
terminal.

### Linux

**Global hotkeys do not work.**

Wayland may block global keyboard capture. Try X11, or use file transcription
with `stt transcribe`.

**Pasting fails.**

Install clipboard helpers:

```bash
sudo apt-get install -y xclip xsel
```

**The microphone fails to open.**

Install PortAudio:

```bash
sudo apt-get install -y portaudio19-dev
```

Then rerun the installer.

### Windows

**`stt` command not found.**

Add this directory to `PATH`:

```text
%USERPROFILE%\.local\bin
```

**PowerShell blocks install.ps1.**

Run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1
```

**Paste does not work in an elevated app.**

If the target app runs as Administrator, run the terminal as Administrator too.

## Privacy and Security

Network access is used for:

- Installing Python dependencies with `uv`.
- Downloading the pinned model from Hugging Face during install.

After install, the launcher executes the locked virtual environment directly,
enables Hugging Face offline mode, disables implicit tokens and telemetry, and
loads the model from its pinned local path. Runtime transcription does not need
`uv` or network access. The tool does not intentionally upload microphone audio,
transcripts, clipboard content, or keystrokes.

Security-sensitive permissions:

- Microphone access records audio.
- Accessibility/Input Monitoring enables global hotkeys and simulated paste.
- Clipboard access is used briefly to paste the transcript.

On macOS these permissions belong to the terminal application, so they also
apply to other processes launched from that terminal. Use a dedicated terminal
profile and grant only the permissions required for STT.

See [SECURITY.md](SECURITY.md) for the complete data-flow and hardening notes.
