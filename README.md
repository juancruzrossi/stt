# STT

Simple, fast local speech-to-text dictation with Python and Faster Whisper.

STT records from the microphone, transcribes locally, and pastes the text where
the cursor is focused.

## Install

macOS and Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/juancruzrossi/stt/main/install.sh | bash
```

Private repository note: the `curl` command only works from machines with access
to the raw GitHub file. If that is not available, clone the repository:

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

The `curl | bash` installer is for macOS/Linux shells. On Windows, use
PowerShell and `install.ps1`.

The installer:

- Installs `uv` if needed.
- Installs system audio dependencies when needed.
- Installs locked Python dependencies into an isolated `.venv`.
- Downloads the local STT model.
- Installs the `stt` command into `~/.local/bin/stt`.

Runtime files stay isolated in the install directory:

```text
.venv/
.cache/
```

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

## Audio Files

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

Limitation: Whisper translates to English only. English-to-Spanish translation is
not implemented and would require an additional local translation model.

## Model

The installer downloads:

```text
Systran/faster-whisper-small
```

Reference:

https://huggingface.co/Systran/faster-whisper-small

It is the CTranslate2 conversion of OpenAI's `whisper-small`, used by Faster
Whisper for efficient local inference.

The model is cached inside the install directory:

```text
.cache/huggingface/hub/models--Systran--faster-whisper-small
```

Check cached model size:

```bash
stt models
```

## Platform Notes

Supported targets:

- macOS Intel.
- macOS Apple Silicon.
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
- Installing system audio dependencies when needed.
- Downloading the model from Hugging Face during install.

After install, transcription runs locally. The tool does not intentionally upload
microphone audio, transcripts, clipboard content, or keystrokes.

Security-sensitive permissions:

- Microphone access records audio.
- Accessibility/Input Monitoring enables global hotkeys and simulated paste.
- Clipboard access is used briefly to paste the transcript.

For managed company devices:

- Review the source code.
- Keep `uv.lock` committed.
- Download or copy the model in an approved process.
