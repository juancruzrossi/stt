# STT

Local speech-to-text dictation using Python and Faster Whisper.

STT records from the microphone, transcribes locally, and pastes the text where
the cursor is focused. It does not use a paid API.

## Install

macOS or Linux:

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

The setup uses `uv`. Runtime files stay inside the project and are ignored by
Git:

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

## Dictation

```bash
./stt listen
```

Windows:

```powershell
.\stt.cmd listen
```

Usage on macOS:

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
./stt listen --language es
./stt listen --language en
```

## Audio Files

```bash
./stt transcribe /path/to/audio.mp3
```

Save to a text file:

```bash
./stt transcribe /path/to/audio.mp3 --output transcript.txt
```

## Translation

Whisper can translate speech to English:

```bash
./stt transcribe /path/to/spanish-audio.mp3 --task translate
./stt listen --task translate
```

Limitation: Whisper translates to English only. English-to-Spanish translation is
not implemented and would require an additional local translation model.

## Model

The first `listen` or `transcribe` command downloads the default model:

```text
Systran/faster-whisper-small
```

Reference:

https://huggingface.co/Systran/faster-whisper-small

It is the CTranslate2 conversion of OpenAI's `whisper-small`, used by Faster
Whisper for efficient local inference.

The model is cached inside the project:

```text
.cache/huggingface/hub/models--Systran--faster-whisper-small
```

Check cached model size:

```bash
./stt models
```

Offline mode after the first download:

```bash
./stt listen --offline
```

If the model is missing, `--offline` fails instead of downloading anything.

## Platform Notes

Supported targets:

- macOS Intel.
- macOS Apple Silicon.
- Linux, preferably X11 for global hotkeys.
- Windows.

The current full validation was done on macOS Intel. Linux and Windows should be
validated on the actual company image.

## Troubleshooting

### macOS

**Double-tap Command does nothing.**

Enable Accessibility and Input Monitoring for your terminal app. Then fully
quit and reopen the terminal.

**The microphone does not record.**

Enable Microphone permission for your terminal app. Then quit and reopen the
terminal.

**The model downloads again after moving the folder.**

That is expected because STT stores models inside the project `.cache/` folder.
Run `./stt listen` once to download it again, or copy `.cache/huggingface` from
the approved source machine.

### Linux

**Global hotkeys do not work.**

Wayland may block global keyboard capture. Try X11, or use file transcription
with `./stt transcribe`.

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

Then rerun:

```bash
uv sync --python 3.12
```

### Windows

**The command is not recognized.**

Use:

```powershell
.\stt.cmd listen
```

**PowerShell blocks setup.ps1.**

Run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup.ps1
```

**Paste does not work in an elevated app.**

If the target app runs as Administrator, run the terminal as Administrator too.

## Privacy and Security

Network access is used for:

- Installing Python dependencies with `uv`.
- Installing system audio dependencies when needed.
- Downloading the model from Hugging Face on first use.

After setup and model download, transcription runs locally. The tool does not
intentionally upload microphone audio, transcripts, clipboard content, or
keystrokes.

Security-sensitive permissions:

- Microphone access records audio.
- Accessibility/Input Monitoring enables global hotkeys and simulated paste.
- Clipboard access is used briefly to paste the transcript.

For managed company devices:

- Review the source code.
- Keep `uv.lock` committed.
- Download or copy the model in an approved process.
- Run with `--offline` after the model exists locally.
