# STT for macOS

Simple, fast, local speech-to-text dictation with Faster Whisper.

## Install

```bash
git clone https://github.com/juancruzrossi/stt.git
cd stt
./install.sh
```

## Permissions

Enable permissions for your terminal app in:

```text
System Settings > Privacy & Security > Microphone
System Settings > Privacy & Security > Accessibility
System Settings > Privacy & Security > Input Monitoring
```

Reload terminal.

## Usage

```bash
stt listen
```

1. Double-tap `Command` to start recording.
2. Speak.
3. Double-tap the same key again to stop.
4. The transcript is pasted into the focused text field. If none is focused, it remains on the clipboard.

Print each transcription in the terminal:

```bash
stt listen --verbose
```

## Business and Custom Terms

Add them one per line in `~/.config/stt/terms.txt`.

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

Translate speech to English:

```bash
stt transcribe /path/to/spanish-audio.mp3 --task translate
```

## Model

The installer downloads:

```text
Systran/faster-whisper-base
```

Reference:

https://huggingface.co/Systran/faster-whisper-base

## Platform

- macOS Apple Silicon/Intel.

## Troubleshooting

**`stt` command not found.**

Make sure `~/.local/bin` is in your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

**Double-tap Command does nothing.**

Enable Accessibility and Input Monitoring for your terminal app. Then quit and reopen the terminal.

**The microphone does not record.**

Enable Microphone permission for your terminal app. Then quit and reopen the terminal.

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

These permissions belong to the terminal application, so they also
apply to other processes launched from that terminal. Use a dedicated terminal
profile and grant only the permissions required for STT.

See [SECURITY.md](SECURITY.md) for the complete data-flow and hardening notes.
