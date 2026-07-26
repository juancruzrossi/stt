# STT for macOS

Simple, fast, local speech-to-text dictation macOS app with Faster Whisper.

## Install

Download the ZIP for your Mac from Releases:

- `arm64` for Apple Silicon.
- `x86_64` for Intel.

Move `STT.app` to Applications, right-click it, and choose **Open** the first
time.

Open STT and allow Microphone and Accessibility when macOS
asks.

## Use

Open **Settings** from the Dock or menu bar to:

- Set separate shortcuts for **Toggle** and **Hold to Talk**.
- Add custom words under **Terms**.

Audio and transcripts stay on the Mac during normal use. The model and locked
Python dependencies are included in the app.

See [SECURITY.md](SECURITY.md) for the complete data flow and permissions.

## CLI

Prefer the terminal? Install the CLI from source:

```bash
git clone https://github.com/juancruzrossi/stt.git
cd stt
./cli-install.sh
```

Allow Microphone, Accessibility, and Input Monitoring for your terminal app,
then start dictation:

```bash
stt listen
```

Double-tap `Command` to start and stop. The transcription is pasted into the
focused text field or kept on the clipboard.

Other commands:

```bash
stt listen --verbose
stt doctor
stt models
stt transcribe /path/to/audio.mp3
stt transcribe /path/to/audio.mp3 --output transcript.txt
stt transcribe /path/to/audio.mp3 --task translate
```
